#pragma once

// =============================================================
//  OAI-Style NR Logger for NS-3 NR Module
//  Paths verified from actual simulation trace path dump.
//
//  Usage:
//    OaiNrLogger logger("simulation.log");
//    logger.Connect();   // call after InstallGnbDevice/InstallUeDevice
// =============================================================

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/config.h"
#include "ns3/simulator.h"

#include <fstream>
#include <sstream>
#include <iomanip>
#include <string>

// =============================================================
//  OAI-Style NR Logger for NS-3 NR Module
// =============================================================


#include "ns3/nr-module.h"           // Main NR module header
#include "ns3/nr-ue-phy.h"           // For NrUePhy
#include "ns3/nr-gnb-phy.h"          // For NrGnbPhy  
#include "ns3/nr-ue-rrc.h"           // For NrUeRrc::State
#include "ns3/nr-gnb-rrc.h"          // For NrGnbRrc
#include "ns3/nr-mac-scheduler.h"    // For NrSchedulingCallbackInfo, DlHarqInfo


using namespace ns3;

class OaiNrLogger
{
public:
  explicit OaiNrLogger(const std::string &filename = "nr_oai.log")
    : m_filename(filename)
  {
    m_file.open(filename, std::ios::out | std::ios::trunc);
    if (!m_file.is_open())
      NS_FATAL_ERROR("OaiNrLogger: cannot open log file " << filename);
  }

  ~OaiNrLogger() { if (m_file.is_open()) m_file.close(); }

  // ------------------------------------------------------------------
  //  Call once after nrHelper->InstallGnbDevice() / InstallUeDevice()
  // ------------------------------------------------------------------
  void Connect()
  {
    ConnectPhy();
    ConnectMac();
    ConnectRlc();
    ConnectPdcp();
    ConnectRrc();
  }

private:

  // ================================================================
  //  PHY
  //  UE PHY : .../NrUeNetDevice/ComponentCarrierMapUe/*/NrUePhy/...
  //  gNB PHY: .../NrGnbNetDevice/BandwidthPartMap/*/NrGnbPhy/...
  //  Spectrum: .../NrUePhy/SpectrumPhy/...  or .../NrGnbPhy/SpectrumPhy/...
  // ================================================================
  void ConnectPhy()
  {
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/ComponentCarrierMapUe/*/NrUePhy/DlDataSinr",
      MakeCallback(&OaiNrLogger::TraceDlDataSinr, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/ComponentCarrierMapUe/*/NrUePhy/DlCtrlSinr",
      MakeCallback(&OaiNrLogger::TraceDlCtrlSinr, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/ComponentCarrierMapUe/*/NrUePhy/ReportUeMeasurements",
      MakeCallback(&OaiNrLogger::TraceUeMeasurements, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/ComponentCarrierMapUe/*/NrUePhy/CqiFeedbackTrace",
      MakeCallback(&OaiNrLogger::TraceCqiFeedback, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/ComponentCarrierMapUe/*/NrUePhy/ReportDownlinkTbSize",
      MakeCallback(&OaiNrLogger::TraceDlTbSize, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/ComponentCarrierMapUe/*/NrUePhy/ReportUplinkTbSize",
      MakeCallback(&OaiNrLogger::TraceUlTbSize, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/BandwidthPartMap/*/NrGnbPhy/SlotDataStats",
      MakeCallback(&OaiNrLogger::TraceSlotDataStats, this));

    // Config::ConnectFailSafe(
    //   "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/BandwidthPartMap/*/NrGnbPhy/UlSinrTrace",
    //   MakeCallback(&OaiNrLogger::TraceUlSinr, this));

    // Config::ConnectFailSafe(
    //   "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/ComponentCarrierMapUe/*/NrUePhy/SpectrumPhy/DlDataSnrTrace",
    //   MakeCallback(&OaiNrLogger::TraceDlDataSnr, this));

    // Config::ConnectFailSafe(
    //   "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/BandwidthPartMap/*/NrGnbPhy/SpectrumPhy/DlDataPathloss",
    //   MakeCallback(&OaiNrLogger::TraceDlDataPathloss, this));
  }

  // ================================================================
  //  MAC
  //  gNB MAC: .../NrGnbNetDevice/BandwidthPartMap/*/NrGnbMac/...
  // ================================================================
  void ConnectMac()
  {
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/BandwidthPartMap/*/NrGnbMac/DlScheduling",
      MakeCallback(&OaiNrLogger::TraceDlScheduling, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/BandwidthPartMap/*/NrGnbMac/UlScheduling",
      MakeCallback(&OaiNrLogger::TraceUlScheduling, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/BandwidthPartMap/*/NrGnbMac/DlHarqFeedback",
      MakeCallback(&OaiNrLogger::TraceDlHarqFeedback, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/BandwidthPartMap/*/NrGnbMac/SrReq",
      MakeCallback(&OaiNrLogger::TraceSrReq, this));
  }

  // ================================================================
  //  RLC
  //
  //  UE side:
  //    .../NrUeNetDevice/NrUeRrc/DataRadioBearerMap/*/NrRlc/...
  //    .../NrUeNetDevice/NrUeRrc/Srb0/NrRlc/...
  //    .../NrUeNetDevice/NrUeRrc/Srb1/NrRlc/...
  //
  //  gNB side (per UE in UeMap):
  //    .../NrGnbNetDevice/NrGnbRrc/UeMap/*/DataRadioBearerMap/*/NrRlc/...
  //    .../NrGnbNetDevice/NrGnbRrc/UeMap/*/Srb0/NrRlc/...
  //    .../NrGnbNetDevice/NrGnbRrc/UeMap/*/Srb1/NrRlc/...
  //
  //  NOTE: DataRadioBearerMap entries only appear after RRC connection.
  //  ConnectFailSafe silently skips unmatched paths at t=0.
  // ================================================================
  void ConnectRlc()
  {
    // UE data bearers
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/NrUeRrc/DataRadioBearerMap/*/NrRlc/TxPDU",
      MakeCallback(&OaiNrLogger::TraceRlcTxPdu, this));
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/NrUeRrc/DataRadioBearerMap/*/NrRlc/RxPDU",
      MakeCallback(&OaiNrLogger::TraceRlcRxPdu, this));
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/NrUeRrc/DataRadioBearerMap/*/NrRlc/TxDrop",
      MakeCallback(&OaiNrLogger::TraceRlcTxDrop, this));

    // UE SRB0 / SRB1
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/NrUeRrc/Srb0/NrRlc/TxPDU",
      MakeCallback(&OaiNrLogger::TraceRlcTxPdu, this));
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/NrUeRrc/Srb0/NrRlc/RxPDU",
      MakeCallback(&OaiNrLogger::TraceRlcRxPdu, this));
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/NrUeRrc/Srb1/NrRlc/TxPDU",
      MakeCallback(&OaiNrLogger::TraceRlcTxPdu, this));
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/NrUeRrc/Srb1/NrRlc/RxPDU",
      MakeCallback(&OaiNrLogger::TraceRlcRxPdu, this));

    // gNB data bearers
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/NrGnbRrc/UeMap/*/DataRadioBearerMap/*/NrRlc/TxPDU",
      MakeCallback(&OaiNrLogger::TraceRlcTxPdu, this));
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/NrGnbRrc/UeMap/*/DataRadioBearerMap/*/NrRlc/RxPDU",
      MakeCallback(&OaiNrLogger::TraceRlcRxPdu, this));
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/NrGnbRrc/UeMap/*/DataRadioBearerMap/*/NrRlc/TxDrop",
      MakeCallback(&OaiNrLogger::TraceRlcTxDrop, this));

    // gNB SRB0 / SRB1
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/NrGnbRrc/UeMap/*/Srb0/NrRlc/TxPDU",
      MakeCallback(&OaiNrLogger::TraceRlcTxPdu, this));
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/NrGnbRrc/UeMap/*/Srb0/NrRlc/RxPDU",
      MakeCallback(&OaiNrLogger::TraceRlcRxPdu, this));
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/NrGnbRrc/UeMap/*/Srb1/NrRlc/TxPDU",
      MakeCallback(&OaiNrLogger::TraceRlcTxPdu, this));
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/NrGnbRrc/UeMap/*/Srb1/NrRlc/RxPDU",
      MakeCallback(&OaiNrLogger::TraceRlcRxPdu, this));
  }

  // ================================================================
  //  PDCP  (same structure as RLC; SRB0 uses RLC-TM so no PDCP)
  // ================================================================
  void ConnectPdcp()
  {
    // UE data bearers
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/NrUeRrc/DataRadioBearerMap/*/NrPdcp/TxPDU",
      MakeCallback(&OaiNrLogger::TracePdcpTxPdu, this));
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/NrUeRrc/DataRadioBearerMap/*/NrPdcp/RxPDU",
      MakeCallback(&OaiNrLogger::TracePdcpRxPdu, this));

    // UE SRB1
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/NrUeRrc/Srb1/NrPdcp/TxPDU",
      MakeCallback(&OaiNrLogger::TracePdcpTxPdu, this));
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/NrUeRrc/Srb1/NrPdcp/RxPDU",
      MakeCallback(&OaiNrLogger::TracePdcpRxPdu, this));

    // gNB data bearers
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/NrGnbRrc/UeMap/*/DataRadioBearerMap/*/NrPdcp/TxPDU",
      MakeCallback(&OaiNrLogger::TracePdcpTxPdu, this));
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/NrGnbRrc/UeMap/*/DataRadioBearerMap/*/NrPdcp/RxPDU",
      MakeCallback(&OaiNrLogger::TracePdcpRxPdu, this));

    // gNB SRB1
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/NrGnbRrc/UeMap/*/Srb1/NrPdcp/TxPDU",
      MakeCallback(&OaiNrLogger::TracePdcpTxPdu, this));
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/NrGnbRrc/UeMap/*/Srb1/NrPdcp/RxPDU",
      MakeCallback(&OaiNrLogger::TracePdcpRxPdu, this));
  }

  // ================================================================
  //  RRC
  //  UE RRC : .../NrUeNetDevice/NrUeRrc/...
  //  gNB RRC: .../NrGnbNetDevice/NrGnbRrc/...
  // ================================================================
  void ConnectRrc()
  {
    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/NrUeRrc/StateTransition",
      MakeCallback(&OaiNrLogger::TraceUeRrcState, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/NrUeRrc/ConnectionEstablished",
      MakeCallback(&OaiNrLogger::TraceConnectionEstablished, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/NrUeRrc/HandoverStart",
      MakeCallback(&OaiNrLogger::TraceHandoverStart, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/NrUeRrc/HandoverEndOk",
      MakeCallback(&OaiNrLogger::TraceHandoverEndOk, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/NrUeRrc/HandoverEndError",
      MakeCallback(&OaiNrLogger::TraceHandoverEndError, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/NrUeRrc/RadioLinkFailure",
      MakeCallback(&OaiNrLogger::TraceRadioLinkFailure, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/NrUeRrc/RandomAccessSuccessful",
      MakeCallback(&OaiNrLogger::TraceRandomAccessSuccessful, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/NrUeRrc/RandomAccessError",
      MakeCallback(&OaiNrLogger::TraceRandomAccessError, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/NrUeRrc/MibReceived",
      MakeCallback(&OaiNrLogger::TraceMibReceived, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrUeNetDevice/NrUeRrc/Sib1Received",
      MakeCallback(&OaiNrLogger::TraceSib1Received, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/NrGnbRrc/ConnectionEstablished",
      MakeCallback(&OaiNrLogger::TraceGnbConnectionEstablished, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/NrGnbRrc/HandoverStart",
      MakeCallback(&OaiNrLogger::TraceGnbHandoverStart, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/NrGnbRrc/HandoverEndOk",
      MakeCallback(&OaiNrLogger::TraceGnbHandoverEndOk, this));

    Config::ConnectFailSafe(
      "/NodeList/*/DeviceList/*/$ns3::NrGnbNetDevice/NrGnbRrc/NotifyConnectionRelease",
      MakeCallback(&OaiNrLogger::TraceConnectionRelease, this));
  }

  // ================================================================
  //  Helpers
  // ================================================================
  std::string SimTime() const
  {
    std::ostringstream oss;
    oss << std::fixed << std::setprecision(6) << Simulator::Now().GetSeconds();
    return oss.str();
  }

  void Log(const std::string &layer, const std::string &msg)
  {
    std::ostringstream line;
    line << "[" << std::setw(5) << std::left << layer << "]"
         << "[" << SimTime() << "] "
         << msg;
    std::cout << line.str() << "\n";
    m_file   << line.str() << "\n";
    m_file.flush();
  }

  static std::string DbStr(double linear, int prec = 2)
  {
    std::ostringstream oss;
    oss << std::fixed << std::setprecision(prec)
        << 10.0 * std::log10(linear) << " dB";
    return oss.str();
  }

  // ================================================================
  //  PHY callbacks
  // ================================================================

  void TraceDlDataSinr(std::string ctx, uint16_t cellId, uint16_t rnti, double sinr, uint16_t bwpId)
  {
    std::ostringstream msg;
    msg << "DL DATA SINR  | RNTI " << rnti << " | SINR " << DbStr(sinr);
    Log("PHY", msg.str());
  }

  void TraceDlCtrlSinr(std::string ctx, uint16_t cellId, uint16_t rnti, double sinr, uint16_t bwp)
  {
    std::ostringstream msg;
    msg << "DL CTRL SINR  | RNTI " << rnti << " | SINR " << DbStr(sinr);
    Log("PHY", msg.str());
  }

  void TraceUlSinr(std::string ctx, uint16_t rnti, double sinr)
  {
    std::ostringstream msg;
    msg << "UL SINR       | RNTI " << rnti << " | SINR " << DbStr(sinr);
    Log("PHY", msg.str());
  }

  void TraceDlDataSnr(const std::string ctx, const SfnSf &sfnSf,  const uint16_t cellId, const uint8_t bwpId,  const uint64_t imsi,  const double snr)
  {
    std::ostringstream msg;
    msg << "DL DATA SNR   | CELL-ID " << cellId << " | SNR " << DbStr(snr);
    Log("PHY", msg.str());
  }

  void TraceDlDataPathloss(std::string ctx, uint16_t cell_id, uint8_t bwp_id, uint32_t ue_node_id, double pathloss)
  {
    std::ostringstream msg;
    msg << "DL PATHLOSS   | "
        << std::fixed << std::setprecision(2) << pathloss << " dB";
    Log("PHY", msg.str());
  }

  void TraceSlotDataStats(std::string ctx, const SfnSf &sfnSf,
                          uint32_t activeUe,
                          uint32_t usedRe,
                          uint32_t  usedSym,
                          uint32_t availRb,
                          uint32_t  availSym,
                          uint16_t bwpId,
                          uint16_t cellId)
  {
    std::ostringstream msg;
    msg << "SLOT DATA     | Frame " << sfnSf.GetFrame()
        << " Sub " << +sfnSf.GetSubframe()
        << " Slot " << +sfnSf.GetSlot()
        << " | Cell " << cellId << " BWP " << bwpId
        << " | ActiveUE " << activeUe
        << " | UsedRE " << usedRe << " UsedSym " << +usedSym
        << " | AvailRB " << availRb << " AvailSym " << +availSym;
    Log("PHY", msg.str());
  }

  void TraceUeMeasurements(std::string ctx, uint16_t rnti, uint16_t cellId, double rsrp, double rsrq,
                           bool isServCell, uint8_t ccId)
  {
    std::ostringstream msg;
    msg << "UE MEAS       | RNTI " << rnti
        << " | RSRP " << std::fixed << std::setprecision(2) << rsrp << " dBm"
        << " | RSRQ " << rsrq << " dB"
        << " | Serv " << (isServCell ? "Y" : "N")
        << " CC " << +ccId;
    Log("PHY", msg.str());
  }

  void TraceCqiFeedback(std::string ctx, uint16_t rnti, uint8_t wbCqi, uint8_t mcs, uint8_t ri)
  {
    std::ostringstream msg;
    msg << "CQI FEEDBACK  | RNTI " << rnti
        << " | WB-CQI " << +wbCqi
        << " | MCS " << +mcs
        << " | RI " << +ri;
    Log("PHY", msg.str());
  }

  void TraceDlTbSize(std::string ctx, uint64_t rnti, uint64_t tbSize)
  {
    std::ostringstream msg;
    msg << "DL TB SIZE    | RNTI " << rnti << " | TBS " << tbSize << " B";
    Log("PHY", msg.str());
  }

  void TraceUlTbSize(std::string ctx, uint64_t rnti, uint64_t tbSize)
  {
    std::ostringstream msg;
    msg << "UL TB SIZE    | RNTI " << rnti << " | TBS " << tbSize << " B";
    Log("PHY", msg.str());
  }

  // ================================================================
  //  MAC callbacks
  // ================================================================

  void TraceDlScheduling(std::string ctx, NrSchedulingCallbackInfo info)
  {
    std::ostringstream msg;
    msg << "DL SCHED      | Frame " << info.m_frameNum
        << " Slot " << info.m_slotNum
        << " | RNTI " << info.m_rnti
        << " | MCS " << +info.m_mcs
        << " | TBS " << info.m_tbSize << " B"
        //<< " | RBs " << info.m_numRbs
        << " | HARQ " << +info.m_harqId;
    Log("MAC", msg.str());
  }

  void TraceUlScheduling(std::string ctx, NrSchedulingCallbackInfo info)
  {
    std::ostringstream msg;
    msg << "UL SCHED      | Frame " << info.m_frameNum
        << " Slot " << info.m_slotNum
        << " | RNTI " << info.m_rnti
        << " | MCS " << +info.m_mcs
        << " | TBS " << info.m_tbSize << " B"
        //<< " | RBs " << info.m_numRbs
        << " | HARQ " << +info.m_harqId;
    Log("MAC", msg.str());
  }

  void TraceDlHarqFeedback(std::string ctx, const DlHarqInfo& info)
  {
    std::string fb = (info.m_harqStatus == DlHarqInfo::ACK) ? "ACK" : "NACK";
    std::ostringstream msg;
    msg << "DL HARQ       | RNTI " << info.m_rnti
        << " | PID " << +info.m_harqProcessId
        << " | " << fb
        << " | Retx " << +info.m_numRetx;
    Log("MAC", msg.str());
  }

  void TraceSrReq(std::string ctx, const uint8_t bwpId, const uint16_t rnti)
  {
    std::ostringstream msg;
    msg << "SR REQ        | RNTI " << rnti << " | BWP_ID " << bwpId;
    Log("MAC", msg.str());
  }

  // ================================================================
  //  RLC callbacks
  // ================================================================

  void TraceRlcTxPdu(std::string ctx, uint16_t rnti, uint8_t lcid, uint32_t size)
  {
    std::ostringstream msg;
    msg << "TX PDU        | RNTI " << rnti
        << " | LCID " << +lcid << " | " << size << " B";
    Log("RLC", msg.str());
  }

  void TraceRlcRxPdu(std::string ctx, uint16_t rnti, uint8_t lcid, uint32_t size, uint64_t delay)
  {
    std::ostringstream msg;
    msg << "RX PDU        | RNTI " << rnti
        << " | LCID " << +lcid << " | " << size << " B";
    Log("RLC", msg.str());
  }

  void TraceRlcTxDrop(std::string ctx, Ptr<const Packet> p)
  {
    std::ostringstream msg;
    msg << "TX DROP       | " << p->GetSize() << " B";
    Log("RLC", msg.str());
  }

  // ================================================================
  //  PDCP callbacks
  // ================================================================

  void TracePdcpTxPdu(std::string ctx, uint16_t rnti, uint8_t lcid, uint32_t size)
  {
    std::ostringstream msg;
    msg << "TX PDU        | RNTI " << rnti
        << " | LCID " << +lcid << " | " << size << " B";
    Log("PDCP", msg.str());
  }

  void TracePdcpRxPdu(std::string ctx, const uint16_t rnti, const uint8_t lcid, const uint32_t size, const uint64_t delay)
  {
    std::ostringstream msg;
    msg << "RX PDU        | RNTI " << rnti
        << " | LCID " << +lcid << " | " << size << " B";
    Log("PDCP", msg.str());
  }

  // ================================================================
  //  RRC callbacks
  // ================================================================

  void TraceUeRrcState(std::string ctx, uint64_t imsi, uint16_t cellId, uint16_t rnti,
                       NrUeRrc::State oldState, NrUeRrc::State newState)
  {
    std::ostringstream msg;
    msg << "STATE         | IMSI " << imsi
        << " Cell " << cellId << " RNTI " << rnti;
        //<< " | " << NrUeRrc::ToString(oldState)
        //<< " --> " << NrUeRrc::ToString(newState);
    Log("RRC", msg.str());
  }

  void TraceConnectionEstablished(std::string ctx, uint64_t imsi, uint16_t cellId, uint16_t rnti)
  {
    std::ostringstream msg;
    msg << "CONN EST      | IMSI " << imsi
        << " | Cell " << cellId << " | RNTI " << rnti;
    Log("RRC", msg.str());
  }

  void TraceHandoverStart(std::string ctx, uint64_t imsi, uint16_t cellId, uint16_t rnti,
                          uint16_t targetCellId)
  {
    std::ostringstream msg;
    msg << "HO START      | IMSI " << imsi << " RNTI " << rnti
        << " | Src " << cellId << " --> Tgt " << targetCellId;
    Log("RRC", msg.str());
  }

  void TraceHandoverEndOk(std::string ctx, uint64_t imsi, uint16_t cellId, uint16_t rnti)
  {
    std::ostringstream msg;
    msg << "HO END OK     | IMSI " << imsi
        << " | New Cell " << cellId << " | RNTI " << rnti;
    Log("RRC", msg.str());
  }

  void TraceHandoverEndError(std::string ctx, uint64_t imsi, uint16_t cellId, uint16_t rnti)
  {
    std::ostringstream msg;
    msg << "HO FAIL       | IMSI " << imsi
        << " | Cell " << cellId << " | RNTI " << rnti;
    Log("RRC", msg.str());
  }

  void TraceRadioLinkFailure(std::string ctx, uint64_t imsi, uint16_t cellId, uint16_t rnti)
  {
    std::ostringstream msg;
    msg << "RLF           | IMSI " << imsi
        << " | Cell " << cellId << " | RNTI " << rnti;
    Log("RRC", msg.str());
  }

  void TraceRandomAccessSuccessful(std::string ctx, uint64_t imsi, uint16_t cellId, uint16_t rnti)
  {
    std::ostringstream msg;
    msg << "RA SUCCESS    | IMSI " << imsi
        << " | Cell " << cellId << " | RNTI " << rnti;
    Log("RRC", msg.str());
  }

  void TraceRandomAccessError(std::string ctx, uint64_t imsi, uint16_t cellId, uint16_t rnti)
  {
    std::ostringstream msg;
    msg << "RA ERROR      | IMSI " << imsi
        << " | Cell " << cellId << " | RNTI " << rnti;
    Log("RRC", msg.str());
  }

  void TraceMibReceived(std::string ctx, uint64_t imsi, uint16_t cellId, uint16_t rnti, uint16_t other_cid)
  {
    std::ostringstream msg;
    msg << "MIB RX        | IMSI " << imsi
        << " | Cell " << cellId << " | RNTI " << rnti;
    Log("RRC", msg.str());
  }

  void TraceSib1Received(std::string ctx, uint64_t imsi, uint16_t cellId, uint16_t rnti, uint16_t other_cid)
  {
    std::ostringstream msg;
    msg << "SIB1 RX       | IMSI " << imsi
        << " | Cell " << cellId << " | RNTI " << rnti;
    Log("RRC", msg.str());
  }

  void TraceGnbConnectionEstablished(std::string ctx, uint64_t imsi, uint16_t cellId, uint16_t rnti)
  {
    std::ostringstream msg;
    msg << "GNB CONN EST  | IMSI " << imsi
        << " | Cell " << cellId << " | RNTI " << rnti;
    Log("RRC", msg.str());
  }

  void TraceGnbHandoverStart(std::string ctx, uint64_t imsi, uint16_t cellId, uint16_t rnti,
                             uint16_t targetCellId)
  {
    std::ostringstream msg;
    msg << "GNB HO START  | IMSI " << imsi << " RNTI " << rnti
        << " | Src " << cellId << " --> Tgt " << targetCellId;
    Log("RRC", msg.str());
  }

  void TraceGnbHandoverEndOk(std::string ctx, uint64_t imsi, uint16_t cellId, uint16_t rnti)
  {
    std::ostringstream msg;
    msg << "GNB HO END OK | IMSI " << imsi
        << " | Cell " << cellId << " | RNTI " << rnti;
    Log("RRC", msg.str());
  }

  void TraceConnectionRelease(std::string ctx, uint64_t imsi, uint16_t cellId, uint16_t rnti)
  {
    std::ostringstream msg;
    msg << "CONN RELEASE  | IMSI " << imsi
        << " | Cell " << cellId << " | RNTI " << rnti;
    Log("RRC", msg.str());
  }

  // ----------------------------------------------------------------
  std::string   m_filename;
  std::ofstream m_file;
};
