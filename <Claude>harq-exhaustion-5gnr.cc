#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/nr-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/applications-module.h"
#include "ns3/antenna-module.h"
#include "ns3/point-to-point-module.h"


#include "ns3/nr-module.h"           // Main NR module header
#include "ns3/nr-ue-phy.h"           // For NrUePhy
#include "ns3/nr-gnb-phy.h"          // For NrGnbPhy  
#include "ns3/nr-ue-rrc.h"           // For NrUeRrc::State
#include "ns3/nr-gnb-rrc.h"          // For NrGnbRrc
#include "ns3/nr-mac-scheduler.h"    // For NrSchedulingCallbackInfo, DlHarqInfo

#include <fstream>
#include <sstream>
#include <iomanip>
#include <string>


#include "oai_nr_logger.h"

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("NrHarqExhaustionScenario");

std::map<uint16_t, uint8_t> harqRoundCount;

// ── Trace 1: gNB MAC receives HARQ NACK ───────────────────────
void DlHarqNackTrace(std::string context,
                     const DlHarqInfo& harqFeedback)
{
  uint16_t rnti = harqFeedback.m_rnti;

  if (harqFeedback.m_harqStatus == DlHarqInfo::NACK)
  {
    harqRoundCount[rnti]++;
    std::cout << Simulator::Now().GetSeconds()
              << "s [MAC] NR HARQ NACK #"
              << (int)harqRoundCount[rnti]
              << " for RNTI=" << rnti
              << " ProcessID=" << (int)harqFeedback.m_harqProcessId;

    if (harqRoundCount[rnti] >= 4)
      std::cout << " *** HARQ EXHAUSTED → scheduling stall";
    std::cout << std::endl;
  }
  else if (harqFeedback.m_harqStatus == DlHarqInfo::ACK)
  {
    harqRoundCount[rnti] = 0;
  }
}

// ── Trace 2: RRC connection established ───────────────────────
void NotifyConnectionEstablishedUe(std::string context,
                                    uint64_t imsi,
                                    uint16_t cellId,
                                    uint16_t rnti)
{
  std::cout << Simulator::Now().GetSeconds()
            << "s [RRC] NR UE CONNECTED:"
            << " IMSI=" << imsi
            << " RNTI=" << rnti
            << " CellID=" << cellId
            << std::endl;
}

// ── Trace 3: UE context released ──────────────────────────────
void NotifyUeConnectionReleased(std::string context,
                              const uint64_t imsi,
                              const uint16_t cellId,
                              const uint16_t rnti)
{
  std::cout << Simulator::Now().GetSeconds()
            << "s [RRC] NR UE CONTEXT RELEASED:"
            << " IMSI=" << imsi
            << " RNTI=" << rnti
            << " → End of causal chain"
            << std::endl;
}

int main(int argc, char* argv[])
{
  // ── Parameters ────────────────────────────────────────────────
  uint16_t numerologyBwp1  = 1;        // μ=1 → 30 kHz SCS (FR1)
  double   centralFreqHz   = 3.5e9;    // n78 band
  double   bandwidthHz     = 20e6;
  double   totalTxPower    = 1.0;      // intentionally low → drives NACKs
  double   ueNoiseFigure   = 25.0;     // intentionally high → drives NACKs

  CommandLine cmd(__FILE__);
  cmd.AddValue("numerology",   "NR numerology (0-4)",  numerologyBwp1);
  cmd.AddValue("centralFreq",  "Carrier frequency Hz", centralFreqHz);
  cmd.AddValue("bandwidth",    "Bandwidth Hz",          bandwidthHz);
  cmd.AddValue("txPower",      "gNB TX power dBm",      totalTxPower);
  cmd.AddValue("noiseFigure",  "UE noise figure dB",    ueNoiseFigure);
  cmd.Parse(argc, argv);

  NS_ABORT_IF(centralFreqHz < 0.5e9 || centralFreqHz > 100e9);

  LogComponentEnable("NrHarqExhaustionScenario", LOG_LEVEL_INFO);

  // ── RLC buffer ────────────────────────────────────────────────
  Config::SetDefault("ns3::NrRlcUm::MaxTxBufferSize", UintegerValue(999999999));

  // ── Nodes & Mobility ──────────────────────────────────────────
  NodeContainer gnbNodes, ueNodes;
  gnbNodes.Create(1);
  ueNodes.Create(1);

  MobilityHelper mobility;
  mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
  Ptr<ListPositionAllocator> posAlloc = CreateObject<ListPositionAllocator>();
  posAlloc->Add(Vector(0.0,     0.0, 10.0));  // gNB
  posAlloc->Add(Vector(10000.0, 0.0,  1.5));  // UE very far
  mobility.SetPositionAllocator(posAlloc);
  mobility.Install(gnbNodes);
  mobility.Install(ueNodes);

  // ── Helpers ───────────────────────────────────────────────────
  Ptr<NrPointToPointEpcHelper>  nrEpcHelper          = CreateObject<NrPointToPointEpcHelper>();
  Ptr<IdealBeamformingHelper>   idealBeamformingHelper = CreateObject<IdealBeamformingHelper>();
  Ptr<NrHelper>                 nrHelper             = CreateObject<NrHelper>();

  nrHelper->SetBeamformingHelper(idealBeamformingHelper);
  nrHelper->SetEpcHelper(nrEpcHelper);

  // ── Spectrum: one band, one CC, one BWP ───────────────────────
  // Mirrors the reference cttc-nr-demo.cc pattern exactly:
  // use NrChannelHelper to assign the channel model to the band,
  // replacing the old InitializeOperationBand + UMi_StreetCanyon enum.
  BandwidthPartInfoPtrVector allBwps;
  CcBwpCreator ccBwpCreator;

  CcBwpCreator::SimpleOperationBandConf bandConf(
      centralFreqHz,
      bandwidthHz,
      1            // one CC
  );
  OperationBandInfo band = ccBwpCreator.CreateOperationBandContiguousCc(bandConf);

  // ── Channel model (NrChannelHelper — ns-3.47 API) ─────────────
  // This replaces both BandwidthPartInfo::UMi_StreetCanyon and
  // nrHelper->InitializeOperationBand(), which no longer exist.
  Ptr<NrChannelHelper> channelHelper = CreateObject<NrChannelHelper>();
  channelHelper->ConfigureFactories("UMi", "Default", "ThreeGpp");
  channelHelper->SetChannelConditionModelAttribute("UpdatePeriod", TimeValue(MilliSeconds(0)));
  channelHelper->SetPathlossAttribute("ShadowingEnabled", BooleanValue(false));
  channelHelper->AssignChannelsToBands({band});   // ← replaces InitializeOperationBand

  allBwps = CcBwpCreator::GetAllBwps({band});

  // ── Beamforming ───────────────────────────────────────────────
  idealBeamformingHelper->SetAttribute(
      "BeamformingMethod",
      TypeIdValue(DirectPathBeamforming::GetTypeId()));

  nrEpcHelper->SetAttribute("S1uLinkDelay", TimeValue(MilliSeconds(0)));

  // ── Antenna arrays ────────────────────────────────────────────
  nrHelper->SetUeAntennaAttribute("NumRows",    UintegerValue(1));
  nrHelper->SetUeAntennaAttribute("NumColumns", UintegerValue(1));
  nrHelper->SetUeAntennaAttribute("AntennaElement",
      PointerValue(CreateObject<IsotropicAntennaModel>()));

  nrHelper->SetGnbAntennaAttribute("NumRows",    UintegerValue(1));
  nrHelper->SetGnbAntennaAttribute("NumColumns", UintegerValue(1));
  nrHelper->SetGnbAntennaAttribute("AntennaElement",
      PointerValue(CreateObject<IsotropicAntennaModel>()));

  // ── PHY: force bad link ───────────────────────────────────────
  nrHelper->SetUePhyAttribute("NoiseFigure", DoubleValue(ueNoiseFigure));

  // ── Install devices ───────────────────────────────────────────
  // UpdateConfig() is deprecated in ns-3.47 — NrHelper handles
  // configuration internally after InstallGnbDevice/InstallUeDevice.
  NetDeviceContainer gnbDevs = nrHelper->InstallGnbDevice(gnbNodes, allBwps);
  NetDeviceContainer ueDevs  = nrHelper->InstallUeDevice(ueNodes,  allBwps);

  // Set numerology and TX power per BWP (case iii pattern from reference)
  double x = std::pow(10.0, totalTxPower / 10.0);
  NrHelper::GetGnbPhy(gnbDevs.Get(0), 0)
      ->SetAttribute("Numerology", UintegerValue(numerologyBwp1));
  NrHelper::GetGnbPhy(gnbDevs.Get(0), 0)
      ->SetAttribute("TxPower", DoubleValue(10 * std::log10(x)));

  // ── Internet stack ────────────────────────────────────────────
  InternetStackHelper internet;
  internet.Install(ueNodes);
  Ipv4InterfaceContainer ueIpIface =
      nrEpcHelper->AssignUeIpv4Address(NetDeviceContainer(ueDevs));

  // ── Remote host (matches reference SetupRemoteHost pattern) ───
  auto [remoteHost, remoteHostAddr] =
      nrEpcHelper->SetupRemoteHost("100Gb/s", 2500, Seconds(0.0));

  // ── Attach ────────────────────────────────────────────────────
  nrHelper->AttachToClosestGnb(ueDevs, gnbDevs);

  // ── Traffic ───────────────────────────────────────────────────
  uint16_t dlPort = 1234;

  UdpServerHelper sink(dlPort);
  ApplicationContainer serverApps = sink.Install(ueNodes.Get(0));

  UdpClientHelper client;
  client.SetAttribute("MaxPackets", UintegerValue(0xFFFFFFFF));
  client.SetAttribute("PacketSize", UintegerValue(1024));
  client.SetAttribute("Interval",   TimeValue(MilliSeconds(1)));
  client.SetAttribute("Remote",
      AddressValue(addressUtils::ConvertToSocketAddress(
          ueIpIface.GetAddress(0), dlPort)));
  ApplicationContainer clientApps = client.Install(remoteHost);

  Time udpStart = MilliSeconds(400);
  Time simStop  = MilliSeconds(10000);

  serverApps.Start(udpStart);  clientApps.Start(udpStart);
  serverApps.Stop(simStop);    clientApps.Stop(simStop);

  // ── Traces ────────────────────────────────────────────────────
  Config::Connect(
    "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice"
    "/BandwidthPartMap/*/NrGnbMac/DlHarqFeedback",
    MakeCallback(&DlHarqNackTrace));

  Config::Connect(
    "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice"
    "/NrUeRrc/ConnectionEstablished",
    MakeCallback(&NotifyConnectionEstablishedUe));

  Config::Connect(
    "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice"
    "/NrGnbRrc/NotifyConnectionRelease",
    MakeCallback(&NotifyUeConnectionReleased));

  // Built-in NR traces (RxPacketTrace.txt etc.; rv column = HARQ round)
  nrHelper->EnableTraces();

  OaiNrLogger logger("my-sim.log");
  logger.Connect();

  // ── Run ───────────────────────────────────────────────────────
  Simulator::Stop(simStop);
  Simulator::Run();
  Simulator::Destroy();

  return 0;
}