Based on the provided logs and technical context, the root cause of the observed connection quality degradation is the **physical layer signal strength**.

---

### 🔍 Root Cause Event

**Event 1:** `[PHY ][0.400000] UE MEAS | RNTI 1 | RSRP -137.41 dBm | RSRQ 0.00 dB | Serv Y CC 0`

### 🔬 Analysis of the Root Cause Error

The critical piece of information here is the **Reference Signal Received Power (RSRP)** of **-137.41 dBm**.

1.  **Severity:** RSRP measures the received power of the cell's reference signals. For reliable 5G service, the context notes that RSRP should ideally be $>-80$ dBm. An RSRP of -137.41 dBm is extremely low, indicating that the UE is receiving signals far below the minimum threshold required for stable communication.
2.  **Impact:** This low signal strength means that the received signal is heavily attenuated, likely due to excessive distance, severe blockage (e.g., deep indoor penetration loss), or extreme interference.
3.  **Consequence:** When the signal is this weak, the data transmitted by the gNB (even if correctly encoded) will arrive at the UE corrupted, making successful decoding impossible, regardless of the scheduler's efforts.

---

### 🔗 Causal Chain and Impact

The extremely poor RSRP initiates a cascading failure across all layers of the protocol stack, leading to the observed HARQ failures and scheduling stalls.

#### 1. Physical Layer Failure (Root Cause $\rightarrow$ Immediate Symptom)
*   **Cause:** RSRP of -137.41 dBm.
*   **Effect:** The Signal-to-Noise Ratio (SINR) and Signal-to-Interference Ratio (SIR) are critically low.
*   **Log Evidence:** The subsequent SINR readings (e.g., `-17.18 dB`) are poor, but the underlying issue is the lack of raw power.

#### 2. MAC/PHY Layer Failure (Symptom $\rightarrow$ Secondary Symptom)
*   **Cause:** Corrupted physical layer data due to low RSRP.
*   **Effect:** The UE cannot reliably decode the transmitted data, leading to failure in Channel State Information (CSI) reporting.
*   **Log Evidence:**
    *   `CQI FEEDBACK | WB-CQI <CQI_INVALID> | MCS <MCS_INVALID>`: The invalid CQI and MCS values confirm that the UE cannot accurately estimate the channel quality or determine a suitable modulation/coding scheme for the scheduler.
    *   `[MAC ][0.400500] DL SCHED | ... | MCS <MCS_INVALID>`: The scheduler is forced to operate with invalid parameters because the feedback is unusable.

#### 3. HARQ Layer Failure (Secondary Symptom $\rightarrow$ Tertiary Symptom)
*   **Cause:** The MAC layer attempts to transmit data using invalid parameters over a severely degraded physical link.
*   **Effect:** The data packets are lost or corrupted upon reception. The HARQ mechanism detects these failures.
*   **Log Evidence:**
    *   `0.403s NR HARQ NACK #1 for RNTI=1 ProcessID=15` (and subsequent NACKs): The repeated Negative Acknowledgements confirm that the data is not being successfully decoded by the UE.
    *   `*** HARQ EXHAUSTED → scheduling stall`: This is the critical failure point. The system exhausts its maximum number of retransmissions (HARQ rounds) because the underlying physical link quality is too poor to allow for successful decoding, regardless of how many times the data is resent.

#### 4. Application Layer Failure (Final Impact)
*   **Cause:** HARQ exhaustion and scheduling stall.
*   **Effect:** The MAC layer cannot successfully deliver the data payload to the upper layers (RLC/PDCP).
*   **Log Evidence:** The repeated attempts to send the application data (`[APP] DL packet SENT size=1012`) are effectively blocked by the continuous HARQ failures, leading to a complete failure to maintain the data connection.

### Summary of Impact

The root cause is **severe signal attenuation (RSRP -137.41 dBm)**. This physical layer failure prevents the UE from providing accurate channel feedback (invalid CQI/MCS), which in turn causes the MAC scheduler to fail, leading to repeated HARQ failures and ultimately resulting in a **scheduling stall** and the inability to deliver the application data.