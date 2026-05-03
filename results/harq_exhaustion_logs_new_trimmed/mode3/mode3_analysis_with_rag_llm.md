Based on the provided MAC layer logs and the detailed context regarding 3GPP MAC layer operation, the wireless link quality is **poor and unstable**, leading to significant throughput degradation and repeated HARQ failures.

Here is a detailed analysis of the link quality, followed by actionable improvement strategies.

---

## 📡 Wireless Link Quality Analysis

### 1. Signal Quality (SINR)
*   **Observation:** The SINR measurements are consistently low: **-17.18 dB**.
*   **Analysis:** A SINR of -17.18 dB is extremely poor. For reliable data transmission, especially in high-throughput scenarios, a SINR significantly higher (e.g., > 10 dB) is required. This low SINR is the primary root cause of the subsequent failures.

### 2. HARQ Performance (The Major Issue)
*   **Observation:** The logs show a continuous sequence of HARQ failures:
    *   `0.403s NR HARQ NACK #1 for RNTI=1 ProcessID=15`
    *   ...
    *   `0.4045s NR HARQ NACK #4 for RNTI=1 ProcessID=12 *** HARQ EXHAUSTED → scheduling stall`
    *   ...
    *   `0.411s NR HARQ NACK #17 for RNTI=1 ProcessID=14 *** HARQ EXHAUSTED → scheduling stall`
*   **Analysis:** The UE is repeatedly failing to decode the received data, resulting in a Negative Acknowledgement (NACK) for almost every scheduled transmission attempt. The system is forced to retransmit (HARQ process), but the failures continue until the maximum number of HARQ rounds is exhausted (e.g., 4 rounds, as per default configuration). This leads to the critical message: `*** HARQ EXHAUSTED → scheduling stall`.
*   **Impact:** The scheduler is repeatedly stalled because the link quality is insufficient to support successful decoding, severely limiting the effective data rate.

### 3. Modulation and Coding Scheme (MCS)
*   **Observation:** The logs repeatedly show: `MCS <MCS_INVALID>` and `CQI FEEDBACK | RNTI 1 | WB-CQI <CQI_INVALID> | MCS <MCS_INVALID> | RI 1`.
*   **Analysis:** The inability to decode data (due to low SINR) prevents the UE from accurately measuring the channel quality and reporting a valid Channel Quality Indicator (CQI). Consequently, the MAC scheduler cannot select an appropriate MCS, defaulting to an invalid state, which further limits throughput.

### 4. Resource Utilization (UsedRE/UsedSym)
*   **Observation:** When transmissions do occur, the resources are used: `UsedRE 636 UsedSym 12`.
*   **Analysis:** The system is attempting to utilize the allocated resources, but the poor channel conditions mean that the data transmitted is not successfully received, making the resource usage inefficient.

---

## 💡 Summary of Link Degradation

The primary problem is **severe radio link degradation**, evidenced by the consistently low SINR (-17.18 dB). This poor signal quality causes the UE to fail decoding the downlink data, triggering repeated HARQ NACKs, exhausting the HARQ process, and ultimately causing the MAC scheduler to stall and fail to deliver the scheduled data payload.

---

## 🛠️ Improvement Strategies

Since the root cause is poor radio conditions (low SINR), the strategies must focus on either improving the physical link or adapting the MAC layer to cope with the poor link.

### Strategy 1: Physical Layer Optimization (Highest Priority)

The most effective solution is to improve the signal strength and reduce interference.

1.  **Investigate RF Environment:**
    *   **Action:** Conduct a physical site survey. Check for sources of interference (e.g., microwave links, other wireless systems) that could be degrading the SINR.
    *   **Goal:** Increase the SINR above the required threshold (ideally > 10 dB).
2.  **Optimize Antenna Placement/Configuration:**
    *   **Action:** Adjust the gNB antenna array configuration (e.g., beamforming weights, tilt, or height) to ensure the signal reaches the UE optimally.
    *   **Goal:** Maximize the received signal power (RSRP) and minimize interference.
3.  **Check for Obstructions:**
    *   **Action:** Verify that there are no temporary or permanent physical obstructions (buildings, foliage) between the gNB and the UE.

### Strategy 2: MAC Layer Adaptation (Mitigation)

If physical improvements are not immediately possible, the MAC layer must be configured to be more robust against poor channel conditions.

1.  **Reduce Target MCS (Robustness):**
    *   **Problem:** The system is likely attempting high-order modulation (like 64QAM or higher) which requires excellent SINR.
    *   **Action:** If possible, adjust the MAC scheduler parameters to favor lower-order, more robust modulation schemes (e.g., QPSK or 16QAM) even if the channel *could* support higher rates. This increases the chance of successful decoding, even if it reduces peak throughput.
    *   **Configuration Focus:** Review `dl_min_mcs` and potentially adjust the MCS selection logic to be more conservative when SINR drops below a certain threshold.
2.  **Increase HARQ Resilience (Temporary Fix):**
    *   **Problem:** The HARQ process is exhausting too quickly.
    *   **Action:** If the network can tolerate the increased overhead, increase the maximum number of HARQ rounds.
    *   **Configuration Focus:** Increase `dl_harq_round_max` (default is 4). Increasing this gives the system more attempts to recover from transient fades.
3.  **Adjust Scheduling Parameters (Efficiency):**
    *   **Action:** If the UE is consistently failing to report CQI, consider adjusting the scheduling grant size or the scheduling interval to allow the UE more time to stabilize its link measurements.

### Summary Table of Recommendations

| Area | Issue Identified | Recommended Action | Configuration Parameter (If Applicable) | Priority |
| :--- | :--- | :--- | :--- | :--- |
| **Physical Link** | SINR is critically low (-17.18 dB). | Conduct RF site survey; eliminate interference and improve signal path. | N/A (Physical fix) | **High** |
| **MAC Layer** | HARQ failures are continuous, leading to stalls. | Increase the number of retransmission attempts. | `dl_harq_round_max` (Increase value) | Medium |
| **MAC Layer** | MCS selection is failing (`<MCS_INVALID>`). | Force the scheduler to use more robust, lower-order modulation schemes. | `dl_min_mcs` (Adjust to favor lower MCS) | Medium |
| **Overall** | High packet loss/retransmissions. | Re-evaluate the cell coverage and capacity planning for the UE's location. | N/A | High |