# Inline hardware enforcement and intrusion prevention for ICS/OT protocols (FPGA, P4, SmartNIC)

Notes compiled 2026-11-08. Every paper below has its access level recorded. "Full text" means I extracted and read the whole PDF (pdftotext), including the method, evaluation, limitations and conclusion. Short quotes are under 15 words.

## Q0. Which papers were read, and at what access level?

### Takeaway
Six primary papers were read in full and one in part. Two more were available only as an abstract and are flagged as such: SRIM (CIGRE 2026), which is paywalled with no preprint, and Pearce et al. Smart I/O modules (IEEE TII 2020), which is paywalled with no preprint found. Only P4Ward and Hu et al. run on real switching hardware (Tofino-class). Lanotte et al. run on real FPGA hardware (NetFPGA-CML). SRIM claims an FPGA but I could not verify it.

### Cited Findings
- Lanotte, Merro, Munteanu, "Runtime Enforcement of Programmable Logic Controllers", arXiv 2105.10668v2 (18 Nov 2021). **FULL TEXT** of the arXiv v2. It is the long version of the CSF 2020 paper and corresponds to the ACM TOPS journal line. I did not read the CSF 2020 PDF; the univr.it link returned an HTML landing page — [arXiv](https://arxiv.org/abs/2105.10668)
- Fink, Köhler, Serror, Wehrle, "P4Ward: Fine-Grained Behavioral Policy Enforcement for Industrial Networks", IEEE LCN 2025. **FULL TEXT** of the author version from the RWTH COMSYS site — [P4Ward PDF](https://www.comsys.rwth-aachen.de/publication/2025/2025_fink_p4ward/2025_fink_p4ward.pdf); code at [GitHub COMSYS/P4Ward](https://github.com/COMSYS/P4Ward)
- Abbas, Ozmen, Alsaheel, Khan, Celik, Xu, "SAIN: Improving ICS Attack Detection Sensitivity via State-Aware Invariants", USENIX Security 2024. **FULL TEXT** — [USENIX PDF](https://www.usenix.org/system/files/usenixsecurity24-abbas.pdf)
- Li, Guo, Zhou, Zhou, Wong, "SCADAWall: A CPI-Enabled Firewall Model for SCADA Security", Computers & Security 80 (2019) 134-154. **FULL TEXT** of the accepted author manuscript in the A*STAR OAR repository (CC BY-NC-ND) — [A*STAR OAR PDF](https://oar.a-star.edu.sg/storage/v/vdqy8j2ezv/scadawall-a-cpi-enabled-firewall-model-for-scada-security.pdf)
- Wu Hsi-Chin, Lu Hsin-Yu, Huang Yu-Kang (Moxa Inc.), "Cyber Sentinels: Harnessing Deep Packet Inspection for Real-Time Defense of Substation", CIGRE 2026 Session, D2_10116_2026. **ABSTRACT + KEYWORDS ONLY**. The 699 KB PDF is sold on e-cigre (€20 members / €30 non-members) and is free only to registered Session delegates. I found no preprint, product page or datasheet — [e-cigre listing](https://www.e-cigre.org/publications/detail/d2-10116-2026-cyber-sentinels-harnessing-deep-packet-inspection-for-real-time-defense-of-substation.html)
- Hu, Lin, Qu, Jin, "Leveraging Compact Data Accumulator to Enable In-Network Anomaly Detection in Programmable Switches for Power Grids", IEEE SmartGridComm 2024. **FULL TEXT** — [URI PDF](https://web.uri.edu/decps/wp-content/uploads/sites/1880/2024_SmartGridComm_Leveraging_Compact_Data_Accumulator_to_Enable_In_Network_Anomaly_Detection_in_Programmable_Switches_for_Power_Grids.pdf)
- Samson Raj, Jin, "Dynamic Data Driven Security Framework for Industrial Control Networks using Programmable Switches" (DDDAS venue). **FULL TEXT**. It is short, and the target is the BMv2 software switch — [NSF PAR PDF](https://par.nsf.gov/servlets/purl/10585925)
- Rinieri, Melis, Girau, Pau, Prandini, Callegati, "P4ICS: P4 in-network security for Industrial Control Systems networks", Computer Networks 287 (2026) 112560. **PARTIAL**: I read the abstract, introduction, threat model, parsing pipeline, case-study introduction and limitations. It covers in-network crypto, not enforcement, and runs on BMv2 — [UniBo PDF](https://cris.unibo.it/retrieve/a3fa359c-ff86-45fc-a3ac-949e98be4979/1-s2.0-S1389128626005724-main.pdf)
- Pearce, Pinisetty, Roop, Kuo, Ukil, "Smart I/O Modules for Mitigating Cyber-Physical Attacks on Industrial Control Systems", IEEE TII 16(7):4659-4669, 2020. **ABSTRACT ONLY** (paywalled, no preprint found). Most of what I know about it comes from Lanotte et al.'s related-work comparison — [IEEE Xplore](https://ieeexplore.ieee.org/document/8859335); [CPS-VO record](https://archive.cps-vo.org/node/71490)

### Inferences
- The "must-cover" set splits two ways. Three papers are actually inline hardware enforcers: Lanotte (FPGA), P4Ward (Tofino) and SRIM (FPGA, claimed). The other two are software (SCADAWall on iptables, SAIN inside the PLC runtime) and are useful mainly for their policy semantics.

### Gaps
- SRIM full text was not accessible. Its FPGA part, latency figures, GOOSE/SV handling and refusal behaviour are all unknown.
- I found no academic paper on an FPGA-based Modbus/TCP-aware inline enforcer, beyond Lanotte's I/O-level enforcer, despite several searches. This is itself a signal (see Q11).
- I found no peer-reviewed in-switch ML IDS for ICS on Tofino other than Hu et al. Others surfaced (e.g., a P4 pHeavy DNP3 result cited in a survey) but I did not read them.

---

## Q1. Lanotte, Merro, Munteanu: runtime enforcement of PLCs with FPGA "secure proxies"

### Takeaway
Formal enforcement with edit automata, synthesized automatically to Verilog and run on NetFPGA-CML boards. The enforcer sits between each PLC and its plant I/O. It forwards inputs, checks the scan-cycle outputs against timed regular properties, and suppresses, corrects or autonomously inserts actuator commands. It targets compromised PLC programs, not network attackers. It knows nothing of TCP and runs at 1 MHz over a custom UDP network.

### Cited Findings
- **Mechanism and placement.** The enforcers run on three NetFPGA-CML boards. A Python tool parses properties (ANTLR), synthesizes an edit automaton and emits Verilog, which is checked in ModelSim. Each enforcer sits between an OpenPLC-on-Raspberry-Pi controller and a Simulink plant. Before each scan cycle the enforcer forwards current inputs to the controller, then takes all outputs and forwards them to the actuators. A custom UDP network links the enforcers, PLCs and plant — [arXiv 2105.10668 §7.2](https://arxiv.org/abs/2105.10668)
- **Threat model.** Malware in one or more PLCs may forge or drop actuator commands, modify sensor readings and forge or drop inter-PLC messages, and may collude. Network-level sensor tampering is out of scope. Enforcers are assumed "physically independent secure proxies" with no Internet or USB access, and runtime reconfiguration of the proxies is disallowed — [arXiv §2](https://arxiv.org/abs/2105.10668)
- **Policy expressiveness.** Timed regular properties: the class recognized by finite automata whose cycles all contain a final state, which the authors call the largest class finite edit automata can enforce. Local (per-PLC) and global (network) properties. Formal guarantees cover transparency, soundness, determinism preservation, deadlock- and divergence-freedom, mitigation and scalability — [arXiv §1, §5-6](https://arxiv.org/abs/2105.10668)
- **Blocking action.** Monitors "correct and suppress incorrect actions" and emit actions autonomously when the controller cannot. A fixed priority picks among admissible safe outputs. Example: suppressing pump-on commands when the tank is empty — [arXiv abstract, §7.2-7.3](https://arxiv.org/abs/2105.10668)
- **Measured results.** Vivado 15.2 analysis. Resource use scales with enforcer states, which scale with the number of scan cycles a property covers: about 5% of the device for 1,000-scan-cycle properties and 13% for 10,000. The FPGAs ran at 1 MHz against PLC scan rates of 0.1-1 kHz, so overhead is called "negligible". The inter-enforcer link is 1 Gbps Ethernet, quoted as "100 microseconds latency". No absolute LUT/FF counts, power figures or worst-case latency are reported — [arXiv §7.4](https://arxiv.org/abs/2105.10668)
- **Coverage.** Five malware cases on a simulated SWaT-like plant (tank overflow, valve damage, pump damage). All were mitigated. There is no false-positive study — [arXiv §7.3](https://arxiv.org/abs/2105.10668)
- **Comparison with Pearce et al.** The authors say Pearce's smart I/O modules (also FPGA) do bi-directional, synchronous enforcement of inputs and outputs and do not cover inter-controller communications. They argue their own uni-directional design scales to networks of controllers — [arXiv §8](https://arxiv.org/abs/2105.10668)
- **Future work, paraphrased.** Robotic arms; plants with significant noise and uncertainty, where perturbations "might falsely indicate that the monitored controller is under attack"; adding state estimation from linear difference equations inside the enforcers; physics-based detection for compromised sensors — [arXiv §9](https://arxiv.org/abs/2105.10668)

### Inferences
- **Already published here:** (a) the FPGA as an isolated, non-reconfigurable "secure proxy" for PLC enforcement; (b) automatic synthesis of enforcers from formal properties to Verilog; (c) suppression or replacement of unsafe commands; (d) the argument that isolation from Internet/USB plus no runtime reconfiguration makes the enforcer trustworthy. A KR260 paper cannot claim any of these as new.
- **Not done here, and our assets add it:**
  - Network-protocol-level enforcement: Modbus/TCP parsing, checksum verification, TCP-session preservation. Lanotte has no TCP.
  - Attacker = an upstream agent/HMI rather than PLC malware.
  - Acceptance tracking through PLC echoes.
  - Age-aware state intervals. Lanotte acknowledges sensor uncertainty only as future work.
  - Line-rate operation. 1 MHz is not a datapath.
  - A heterogeneous split: R5 real-time logic plus fabric. Their "isolation" is a whole separate board.
- Their stated future work, plant uncertainty plus state estimation in the enforcer, sits close to our "interval that widens with reading age". That makes it a natural, citable motivation.

### Gaps
- No absolute LUT/FF/BRAM numbers, power figures or worst-case enforcement latency are given, so a direct resource comparison with our ~8k LUT gate is not possible beyond percentages of an unspecified NetFPGA-CML (Kintex-7) device.
- I did not read the CSF 2020 version or the final TOPS PDF. I assume the arXiv v2 matches them in substance but have not verified it.

---

## Q2. P4Ward (Fink et al., LCN 2025): MUD-based application-aware policy on Tofino

### Takeaway
A per-device whitelist enforced at line rate on an Intel Tofino 1. It covers L2/L3, connection direction (Bloom filters), rate limits, and fixed-offset application fields (Modbus function codes, OPC UA security policy). It is stateless at the application layer. Its refusal mechanism is to drop the packet, and the authors report this breaks the TCP connection.

### Cited Findings
- **Mechanism and placement.** P4 data plane on an Intel Tofino 1 with a Python control plane. Inline, as the switch itself. Supports Modbus, OPC UA, EtherNet/IP and GOOSE through MUD (RFC 8520) extensions. Three-step access control: device validation (MAC/IP/port anti-spoofing plus a per-device two-rate three-color meter), connection validation (match tables plus register-based Bloom filters of valid TCP connections, cleared by the control plane on FIN/timeout), and protocol validation (application fields parsed in egress because the ports are custom) — [P4Ward §IV-V](https://www.comsys.rwth-aachen.de/publication/2025/2025_fink_p4ward/2025_fink_p4ward.pdf)
- **Threat model.** A Dolev-Yao network attacker, which can be an insider, a BYOD device, or someone with remote or physical network access. If attackers compromise legitimate devices allowed to perform the attack pattern, "P4Ward reaches its functional limitations" — [P4Ward §III-A, §VI-B](https://www.comsys.rwth-aachen.de/publication/2025/2025_fink_p4ward/2025_fink_p4ward.pdf)
- **Policy expressiveness.** Per-packet whitelisting of protocol fields, with a relaxed blacklist mode, plus TCP connection-direction state. No sequence or plant-state awareness. Intrusion detection is explicitly out of scope — [P4Ward §IV-A](https://www.comsys.rwth-aachen.de/publication/2025/2025_fink_p4ward/2025_fink_p4ward.pdf)
- **Measured results.**
  - Throughput: matches Tofino 1's 3.2 Tbps when authentication is disabled.
  - Latency: average RTT 0.43 ms with P4Ward, the same as plain Tofino forwarding, against 0.26 ms for an industrial switch (200 measurements).
  - Rule management: installing one ACE takes 3.2-3.3 ms and disabling one 2.2-2.3 ms.
  - Authentication: EAP-OTP initial authentication 165-170 ms; re-authentication 17.9 ms with pre-computed OTPs, 150 ms fresh.
  - Capacity: 512 devices, 2,048 ACEs, 65k OTPs.
  - No per-stage resource table and no false-positive rate.
  — [P4Ward §V-B, §VI-A](https://www.comsys.rwth-aachen.de/publication/2025/2025_fink_p4ward/2025_fink_p4ward.pdf)
- **Refusal and TCP.** In the write test, P4Ward "immediately dropped the packet with the unauthorized function code, resulting in a connection failure". Rate limiting on the server side also broke a legitimate Modbus connection under a SYN flood until the limit was moved to the attacker's egress — [P4Ward §VI-B](https://www.comsys.rwth-aachen.de/publication/2025/2025_fink_p4ward/2025_fink_p4ward.pdf)
- **Admitted limitations.**
  - Only fixed-length headers and fields; no strings or nested structures.
  - No range matching, because of memory.
  - Ingress-to-egress metadata of 16 bits, i.e., 16 behaviour flags.
  - Advanced authentication is infeasible in the data plane.
  - "attacks within allowed patterns cannot be blocked".
  - DDoS within per-device limits.
  — [P4Ward §V-B, §VI-C](https://www.comsys.rwth-aachen.de/publication/2025/2025_fink_p4ward/2025_fink_p4ward.pdf)
- **Future work, paraphrased.** IDS could be integrated into the control plane later. Limits on parsing and capacity are expected to ease with future hardware. Also flags the open problem of data-plane crypto such as AES — [P4Ward §IV-A, §IV-B, §VII](https://www.comsys.rwth-aachen.de/publication/2025/2025_fink_p4ward/2025_fink_p4ward.pdf)
- **Commercial baseline cited.** Belden Tofino Security Appliance-class products are limited to about 1,000 pps depending on protocol, and support GOOSE, Modbus and EtherNet/IP — [P4Ward §II-C](https://www.comsys.rwth-aachen.de/publication/2025/2025_fink_p4ward/2025_fink_p4ward.pdf)

### Inferences
- **Already published:** line-rate hardware enforcement of Modbus function-code whitelists and "write only from authorized endpoints" on programmable hardware, with RTT measured against an industrial switch.
- **Not done, and our assets add it:**
  - Value or plant-aware checks: no range matching at all.
  - Write acceptance tracking: no request/response correlation.
  - Session-preserving refusal: P4Ward breaks the connection on refusal, which is exactly what our one-byte mutation plus PLC exception avoids. This is a crisp, measurable contrast.
  - Checksum verification and FCS regeneration in the data plane.
  - Defence against a compromised *legitimate* client. P4Ward explicitly cannot handle this, and it is our LLM-agent case.

### Gaps
- No worst-case latency or jitter, and no Tofino stage/SRAM/TCAM utilization, were published.

---

## Q3. SRIM / "Cyber Sentinels" (Moxa, CIGRE 2026 D2): inline FPGA IPS for IEC 61850

### Takeaway
Only the abstract was accessible. SRIM is described as a hardware, FPGA-accelerated, inline, protocol-aware DPI IPS, packaged as an SFP module that plugs into existing Ethernet switches. It claims wire-speed throughput and deterministic microsecond-level latency on a substation testbed, and says CPU-based inspection degrades under load. No numbers are visible.

### Cited Findings
- SRIM stands for "Substation Real-time Intrusion Prevention Module". It is hardware-based and FPGA-accelerated, for inline deployment in critical paths, packaged as an SFP for existing switches. It claims line-rate DPI at "microsecond-level latency". Keywords include GOOSE, SMV, inline protection and IPS. All three authors are Moxa employees — [e-cigre listing](https://www.e-cigre.org/publications/detail/d2-10116-2026-cyber-sentinels-harnessing-deep-packet-inspection-for-real-time-defense-of-substation.html)
- Moxa's pre-conference release lists it among three papers it will present in CIGRE 2026 D2 PS2 (Paris, 23-28 Aug 2026). This is a vendor source — [electronica-azi / Moxa release](https://international.electronica-azi.ro/cigre-2026-moxa-helps-utilities-architect-every-stage-of-the-substation-journey/)
- Moxa's existing commercial IPS (EDR-G9010) does DPI for Modbus TCP/UDP, DNP3, IEC 104 and IEC 61850 MMS. GOOSE is not listed in the sources found — [Moxa news 2022](https://moxa.com/en/about-us/news-events/news/2022/moxa-launches-industrial-intrusion-prevention-systems-on-its-edr-g9010-all-in-one-secure-routers)

### Inferences
- SRIM pre-empts a generic claim of an "inline FPGA IPS for OT at µs latency, in a deployable form factor". A KR260 paper must not position itself as the first inline FPGA OT IPS. GOOSE/SV are layer-2 multicast with no TCP, so SRIM very likely does not address TCP session preservation, Modbus write acceptance, or plant-state intervals. This is unverified.

### Gaps
- Unknown: FPGA device, resource use, latency figures, the policy language (stateless? GOOSE stNum/sqNum sequence tracking?), refusal action (drop vs. other), threat model, and future work. A delegate copy or an author contact would be needed.

---

## Q4. SCADAWall (Li et al., 2019): full-payload Modbus inspection plus out-of-sequence detection

### Takeaway
A software (Linux iptables u32) transparent bridge firewall prototype on a laptop. It inspects every Modbus field, including register values and sub-function codes. It also proposes an Out-of-Sequence Detection Algorithm (OSDA) that tracks authorized multi-command sequences with per-step state and a maximum inter-command wait. Only the CPI part is latency-evaluated.

### Cited Findings
- **Mechanism.** CPI (Comprehensive Packet Inspection) uses parent/child field trees mapped to iptables chains with u32 matches. PIPEA lets users define proprietary protocol layouts. OSDA handles sequence checks. Hardware: a ThinkPad T400 (Core 2 Duo, Ubuntu 16.04) with two NICs, one of them USB 3.0, in "non-intrusive mode" with no IP address, i.e., a transparent inline bridge — [SCADAWall manuscript §IV-V](https://oar.a-star.edu.sg/storage/v/vdqy8j2ezv/scadawall-a-cpi-enabled-firewall-model-for-scada-security.pdf)
- **Threat model (implicit).** A network attacker forges or modifies Modbus commands, e.g., writing an FC06 value or using FC08 sub-function 04 to force listen-only mode. Commands may also be out of order through attack or operator error. Case study: a metro SCADA testbed. Commercial firewalls tested were Belden Tofino Xenon and Check Point 1200R, which the authors found accept FC06 without value checks and FC08 without sub-function checks — [SCADAWall §III](https://oar.a-star.edu.sg/storage/v/vdqy8j2ezv/scadawall-a-cpi-enabled-firewall-model-for-scada-security.pdf)
- **Sequence semantics.** Each sequence-oriented command is marked pending, received or not available, with timestamps. A command arriving beyond the "maximum waiting period" is rejected and the sequence state is reset. Time-of-day activation is possible. A passive detection mode or active prevention mode can be chosen. OSDA works on commands seen ("sniffs"), not on device responses — [SCADAWall §IV-D](https://oar.a-star.edu.sg/storage/v/vdqy8j2ezv/scadawall-a-cpi-enabled-firewall-model-for-scada-security.pdf)
- **Measured results (CPI only).** With 100 rules only, the baseline is 28.73 µs mean (3.33 µs std dev). The worst reported case, 15 fields and 100+50 rules, is 195.80 µs mean with a 210 µs maximum. The test used 10,000 Modbus commands per group at 1 ms spacing. Latency grows with both the number of inspected fields and the number of rules — [SCADAWall §V-B, Tables II-VI](https://oar.a-star.edu.sg/storage/v/vdqy8j2ezv/scadawall-a-cpi-enabled-firewall-model-for-scada-security.pdf)
- **Refusal.** iptables accept/reject/drop with default-deny. TCP-session consequences are not discussed — [SCADAWall §V-A](https://oar.a-star.edu.sg/storage/v/vdqy8j2ezv/scadawall-a-cpi-enabled-firewall-model-for-scada-security.pdf)
- **Future work and limits, paraphrased.** Prevent commands that drive the plant toward "critical states", estimating "the distance between different states". Test protocols more complex than Modbus. The rule set and latency grow with plant size. Rules cannot cover emergency or unpredictable commands — [SCADAWall §VII](https://oar.a-star.edu.sg/storage/v/vdqy8j2ezv/scadawall-a-cpi-enabled-firewall-model-for-scada-security.pdf)

### Inferences
- **Already published:**
  - Inspecting Modbus write *values*, not only function codes and addresses.
  - Blocking dangerous FC08 sub-functions.
  - Sequence-of-commands enforcement with per-step pending state and timeouts on a transparent inline bridge.
- **Not done:**
  - Hardware: it is a software laptop prototype.
  - Response-side acceptance tracking: OSDA marks a command "received" when the firewall sees it, not when the PLC confirms it.
  - Plant-state awareness. This is named only as future work ("critical states"), which is directly what our plant-level interval does.
  - Session-preserving refusal.
- Our pending-write table matched to PLC echoes is a stricter, response-confirmed version of SCADAWall's pending/received sequence state. It should be framed as an extension of OSDA, not as entirely new.

### Gaps
- I found no evaluation of OSDA's latency or memory in the manuscript; the evaluation section measures CPI only. The published journal version may differ slightly from the OAR accepted manuscript.

---

## Q5. SAIN (Abbas et al., USENIX Security 2024): state-aware invariants enforced in the PLC runtime

### Takeaway
SAIN derives per-PLC-state invariant bounds from static analysis of the PLC program plus trace mining, and enforces them in the OpenPLC runtime. Variable-update requests from the HMI that violate them are denied. It is not inline network hardware. Its key idea, tighter bounds conditioned on the current process state, is the published precedent for plant-state-aware gating.

### Cited Findings
- **Mechanism and placement.** The monitor is written in C inside the OpenPLC runtime, on a Unipi PLC for a Fischertechnik plant and on a simulated Tennessee Eastman plant over Modbus/TCP. It is triggered only by external variable-update requests. On violation "the monitor denies the variable update request and alerts the operator" — [SAIN §5-7](https://www.usenix.org/system/files/usenixsecurity24-abbas.pdf)
- **Threat model.** A remote attacker compromises Level 2+ (HMI/SCADA, e.g., by spear-phishing) and injects malicious variable writes. The PLC firmware is trusted. There is no physical access. Levels 0/1 are air-gapped from Level 2 — [SAIN §3](https://www.usenix.org/system/files/usenixsecurity24-abbas.pdf)
- **Expressiveness.** An FSM of PLC states is extracted from ST/SCL code. Intra-state invariants on sensing, configuration and actuation variables have tight bounds, and inter-state invariants guard transitions. An example bound is H_Target in [890, 910] in state S6. Bounds come from association mining (QuantMiner) on state-partitioned traces — [SAIN §6, §7.2](https://www.usenix.org/system/files/usenixsecurity24-abbas.pdf)
- **Results.**
  - Detection: all 17 attacks detected, against 5/17 for Feng et al. and 6/17 for VetPLC.
  - False positives: 2% (FT) and 1% (CP), against 51%/2% for Feng and 25%/1% for VetPLC.
  - Scan-cycle overhead: FT average 37.1 ms against a normal 36 ms (150 ms limit); CP 5.56 ms against 5 ms (25 ms limit).
  - Invariants checked per update: about 5 on average (FT).
  - Overall: "false positive rate of 2% and a run-time overhead of 3%".
  — [SAIN abstract, Tables 6-9](https://www.usenix.org/system/files/usenixsecurity24-abbas.pdf)
- **Limitations and future work, paraphrased.** False positives come from overly tight bounds when traces are incomplete. An attacker with physical access can spoof sensors. Future work will "validate sensor-to-PLC and PLC-to-actuator communication" with state-aware invariants — [SAIN §8](https://www.usenix.org/system/files/usenixsecurity24-abbas.pdf)

### Inferences
- **Already published:** state-conditioned bounds on writes from a compromised HMI, with denial of the write and low false positives. A KR260 paper cannot claim "state-aware write gating" as new.
- **What we add:**
  - Enforcement *outside* the PLC, as a hardware bump-in-the-wire. SAIN requires modifying the PLC runtime and trusting its firmware.
  - Intervals that widen with the *age* of the last reading. SAIN's bounds are static per state and do not reason about measurement staleness.
  - Acceptance tracking.
  - Session preservation.
  - An LLM agent as the Level-2 attacker or mis-actor.
- How SAIN "denies" an update at protocol level is not stated: it may return an exception or silently not apply. This is a gap.

### Gaps
- The Modbus-level behaviour on denial (exception code vs. silent ignore) is not described in the text.

---

## Q6. Hu, Lin, Qu, Jin (SmartGridComm 2024): in-switch time-series anomaly detection for DNP3 on Tofino-class hardware

### Takeaway
A P4 data structure, the Meter Data Accumulator, keeps compressed per-sensor time series of DNP3 measurement values in switch registers (basis plus deviation, generalized deduplication). In-pipeline decision trees then flag DDoS and false-data injection. Measured on a hardware P4 switch, the added per-packet overhead is 1-20 ns. Mitigation, i.e., drop or redirect, is described but not evaluated.

### Cited Findings
- **Mechanism.** An Aurora 610 P4-programmable switch, a Tofino-based platform; the paper says GD "is executable in the Tofino platform". MDA is a d×m register array indexed by a CRC32 hash of the 5-tuple, one row per sensor. Decision trees run in the match-action pipeline over network features (frequency of function codes and IIN) and power features (voltage mean, min, max, change rate) — [Hu et al. §III-IV](https://web.uri.edu/decps/wp-content/uploads/sites/1880/2024_SmartGridComm_Leveraging_Compact_Data_Accumulator_to_Enable_In_Network_Anomaly_Detection_in_Programmable_Switches_for_Power_Grids.pdf)
- **Results.**
  - Overhead: 1-20 ns per packet against simple forwarding, for 8-250 B DNP3 payloads.
  - Compression ratio: 32.1-60.9%.
  - DDoS accuracy: 86.1-95.6%, with compression costing 1.08-3.22 points.
  - FDIA accuracy: 0.890 falls to 0.865 with compression.
  — [Hu et al. §IV](https://web.uri.edu/decps/wp-content/uploads/sites/1880/2024_SmartGridComm_Leveraging_Compact_Data_Accumulator_to_Enable_In_Network_Anomaly_Detection_in_Programmable_Switches_for_Power_Grids.pdf)
- **Policy expressiveness.** Plant-value-aware (value deviation from a stability point) and statistical. A detector, not a formal policy. The authors observe that normal states deviate around a stability point and that "This deviation widens when disruptions occur" — [Hu et al. §I](https://web.uri.edu/decps/wp-content/uploads/sites/1880/2024_SmartGridComm_Leveraging_Compact_Data_Accumulator_to_Enable_In_Network_Anomaly_Detection_in_Programmable_Switches_for_Power_Grids.pdf)
- **Limitations and future work, paraphrased.** Per-attack structures need redesign. A single switch has only a local view, which could be fixed by a controller or inter-switch stateful protocols. Future work: co-simulation with power simulators, LSTM models, and auto-tuning MDA from grid state — [Hu et al. §IV-D, §V](https://web.uri.edu/decps/wp-content/uploads/sites/1880/2024_SmartGridComm_Leveraging_Compact_Data_Accumulator_to_Enable_In_Network_Anomaly_Detection_in_Programmable_Switches_for_Power_Grids.pdf)

### Inferences
- **Already published:** storing plant measurement history *in the data plane* and using it for line-rate value-aware decisions. A claim that we are the first to keep plant state in the forwarding hardware would be wrong.
- **Not done:**
  - Enforcement semantics with guarantees: a decision tree has false positives and no soundness.
  - Write gating against the stored state: they detect, rather than gate, control commands.
  - Staleness or age reasoning.
  - TCP or session handling: DNP3 here is a measurement stream.

### Gaps
- Tofino stage and register utilization were not reported, and neither was false-positive behaviour under benign transients.

---

## Q7. Samson Raj and Jin: P4 DDDAS Modbus DoS defense; and P4ICS: in-network crypto

### Takeaway
Two software-switch (BMv2) works that matter for related-work completeness but are not hardware results. Raj and Jin pair Modbus function-code whitelisting and rate statistics in P4 with a controller feedback loop that installs block rules in about 1.4 ms. P4ICS moves AES/HMAC tunnels for Modbus, DNP3, EtherNet/IP and MQTT into P4 switches.

### Cited Findings
- **Raj and Jin, mechanism.** BMv2 plus Mininet. The switch checks (src IP, dst IP, dst port, FC) against tables and drops mismatches. It computes inter-arrival times per (src, dst, FC) and reports high-rate tuples to the controller. The controller blocks a tuple after more than 20 reports in a 5 s window — [Raj & Jin §3](https://par.nsf.gov/servlets/purl/10585925)
- **Raj and Jin, results.** Switch-controller-switch round trip of 1.39-1.41 ms mean across topologies. No accuracy metric is given "without a definitive ground truth" — [Raj & Jin Table 1](https://par.nsf.gov/servlets/purl/10585925)
- **P4ICS, mechanism.** BMv2 externs call C++ crypto (AES plus SHA-256 HMAC). The payload is parsed under a 256-byte slice limit. Switch-to-switch tunnels protect untrusted segments. Delay is about 12% below TLS for Modbus/DNP3. The threat model is Dolev-Yao above Level 1, with no physical access to Level 0/1 — [P4ICS abstract, §5-6](https://cris.unibo.it/retrieve/a3fa359c-ff86-45fc-a3ac-949e98be4979/1-s2.0-S1389128626005724-main.pdf)
- **P4ICS, limitation.** The design "cannot be directly ported to production ASICs" such as Tofino. The authors point to FPGA SmartNICs with HDL externs as the path to hardware — [P4ICS §9](https://cris.unibo.it/retrieve/a3fa359c-ff86-45fc-a3ac-949e98be4979/1-s2.0-S1389128626005724-main.pdf)

### Inferences
- P4 ICS work repeatedly hits the same ceilings: payload size and slicing limits, no arbitrary arithmetic or crypto on the ASIC, few metadata bits, and no range matching. P4ICS itself points to FPGAs as the escape route. That is direct motivation for an FPGA bump-in-the-wire.

### Gaps
- I did not read the full evaluation section of P4ICS.

---

## Q8. Pearce et al., Smart I/O Modules (IEEE TII 2020)

### Takeaway
This is the closest older precedent to Lanotte: runtime enforcers synthesized into PLC I/O-module hardware between controller and plant. Only the abstract plus Lanotte's description were accessible.

### Cited Findings
- Enforcers are synthesized to "a new hardware architecture within PLC I/O modules", and the abstract reports "extremely minimal" overhead on several benchmarks — [CPS-VO record](https://archive.cps-vo.org/node/71490); [IEEE Xplore](https://ieeexplore.ieee.org/document/8859335)
- According to Lanotte et al., it uses Valued Discrete Timed Automata, bi-directional synchronous enforcement of inputs and outputs, and FPGA-implemented enforcers. Its attackers cannot tamper with inter-controller communications — [arXiv 2105.10668 §8](https://arxiv.org/abs/2105.10668)

### Inferences
- With Lanotte, it establishes that hardware runtime enforcement at the PLC I/O boundary is prior art from 2019-2020.

### Gaps
- Full text was not read. Hardware details, resource figures and refusal semantics are second-hand.

---

## Q9. Which open hardware problems do these authors explicitly name?

### Takeaway
The problems named across the papers fall into five groups. (1) Plant uncertainty and state estimation inside the enforcer. (2) Moving from command or packet whitelists to *plant-state/critical-state* prevention. (3) Programmable-switch limits on parsing, ranges, metadata and crypto. (4) Attacks that stay *within* allowed patterns by legitimate-but-compromised clients. (5) Extending checks to sensor/actuator channels.

### Cited Findings
- Lanotte: perturbations can make enforcers "take erroneous correcting actions". Proposes state estimation inside the enforcers and physics-based detection for compromised sensors — [arXiv §9](https://arxiv.org/abs/2105.10668)
- SCADAWall: future prevention of transitions into "critical states" by estimating distance between states. Rule-set growth raises latency. Rules cannot capture emergency commands — [SCADAWall §VII](https://oar.a-star.edu.sg/storage/v/vdqy8j2ezv/scadawall-a-cpi-enabled-firewall-model-for-scada-security.pdf)
- P4Ward: fixed-length parsing only, no range matching, a 16-bit metadata limit, a 2,048-ACE capacity, no data-plane authentication. It cannot block attacks within allowed patterns — [P4Ward §V-B, §VI-C](https://www.comsys.rwth-aachen.de/publication/2025/2025_fink_p4ward/2025_fink_p4ward.pdf)
- SAIN: false positives from overly tight bounds, and extending monitoring to sensor-to-PLC and PLC-to-actuator links — [SAIN §8](https://www.usenix.org/system/files/usenixsecurity24-abbas.pdf)
- Hu et al.: the local view of a single switch, redesign per attack, and auto-tuning by grid state — [Hu et al. §IV-D, §V](https://web.uri.edu/decps/wp-content/uploads/sites/1880/2024_SmartGridComm_Leveraging_Compact_Data_Accumulator_to_Enable_In_Network_Anomaly_Detection_in_Programmable_Switches_for_Power_Grids.pdf)
- P4ICS: crypto is not portable to Tofino, and FPGA SmartNIC externs are the proposed route — [P4ICS §9](https://cris.unibo.it/retrieve/a3fa359c-ff86-45fc-a3ac-949e98be4979/1-s2.0-S1389128626005724-main.pdf)

### Inferences
- Two named problems line up directly with our assets. Lanotte's plant uncertainty plus state estimation, and SCADAWall's critical-state prevention, both map to the plant-level interval that widens with reading age. P4Ward's "attacks within allowed patterns" by legitimate clients maps to an LLM agent that holds valid credentials, which needs value- and state-aware gating.

### Gaps
- SRIM's stated open problems are unknown because only the abstract was available.

---

## Q10. What is unaddressed across all of them?

### Takeaway
None of the papers read does any of the following: (a) refuse a request while *preserving the TCP session*; (b) confirm that a write *took effect* by matching the device's response; (c) make the admissible interval depend on *how stale* the last plant reading is; (d) combine a line-rate fabric datapath with a separately verified real-time core on one SoC; (e) treat an AI/LLM agent as the upstream actor.

### Cited Findings
- **Refusal semantics across the set:**
  - P4Ward drops, causing "connection failure" — [P4Ward §VI-B](https://www.comsys.rwth-aachen.de/publication/2025/2025_fink_p4ward/2025_fink_p4ward.pdf)
  - SCADAWall uses iptables reject/drop with no TCP analysis — [SCADAWall §V-A](https://oar.a-star.edu.sg/storage/v/vdqy8j2ezv/scadawall-a-cpi-enabled-firewall-model-for-scada-security.pdf)
  - Raj and Jin, and Hu et al., drop or redirect via forwarding rules — [Raj & Jin](https://par.nsf.gov/servlets/purl/10585925); [Hu et al. §IV-D](https://web.uri.edu/decps/wp-content/uploads/sites/1880/2024_SmartGridComm_Leveraging_Compact_Data_Accumulator_to_Enable_In_Network_Anomaly_Detection_in_Programmable_Switches_for_Power_Grids.pdf)
  - SAIN denies inside the PLC runtime, which is a different trust boundary — [SAIN §5](https://www.usenix.org/system/files/usenixsecurity24-abbas.pdf)
  - Lanotte suppresses or replaces I/O signals with no TCP — [arXiv §7](https://arxiv.org/abs/2105.10668)
- **State tracking across the set:**
  - SCADAWall's OSDA tracks command order from requests only — [SCADAWall §IV-D](https://oar.a-star.edu.sg/storage/v/vdqy8j2ezv/scadawall-a-cpi-enabled-firewall-model-for-scada-security.pdf)
  - P4Ward tracks TCP connection existence only — [P4Ward §V-A](https://www.comsys.rwth-aachen.de/publication/2025/2025_fink_p4ward/2025_fink_p4ward.pdf)
- **Plant-state awareness:**
  - SAIN uses static per-state bounds — [SAIN §6](https://www.usenix.org/system/files/usenixsecurity24-abbas.pdf)
  - Hu et al. use value statistics with no staleness model — [Hu et al.](https://web.uri.edu/decps/wp-content/uploads/sites/1880/2024_SmartGridComm_Leveraging_Compact_Data_Accumulator_to_Enable_In_Network_Anomaly_Detection_in_Programmable_Switches_for_Power_Grids.pdf)
  - Lanotte uses timed properties over scan cycles, with uncertainty left as future work — [arXiv §9](https://arxiv.org/abs/2105.10668)
- **Bit-exact verification.** None reports equivalence of the hardware against a reference software model. Lanotte checks generated Verilog in ModelSim but proves properties of the abstract automaton, not the RTL — [arXiv §7.2](https://arxiv.org/abs/2105.10668)
- **Worst-case numbers.** None of the hardware papers reports worst-case per-packet latency with protocol parsing. P4Ward gives a mean RTT. Hu et al. give a mean per-packet difference. SCADAWall (software) reports maxima of up to 210 µs — [P4Ward](https://www.comsys.rwth-aachen.de/publication/2025/2025_fink_p4ward/2025_fink_p4ward.pdf); [Hu et al.](https://web.uri.edu/decps/wp-content/uploads/sites/1880/2024_SmartGridComm_Leveraging_Compact_Data_Accumulator_to_Enable_In_Network_Anomaly_Detection_in_Programmable_Switches_for_Power_Grids.pdf); [SCADAWall](https://oar.a-star.edu.sg/storage/v/vdqy8j2ezv/scadawall-a-cpi-enabled-firewall-model-for-scada-security.pdf)

### Inferences
- Candidate hardware contributions that look open, at least among the papers read:
  1. Session-preserving refusal in hardware: rewrite the request so the PLC itself returns a Modbus exception, with checksum and FCS fix-up at line rate. Compare against a drop baseline (P4Ward-style) on session survival, HMI/agent recovery time, and the PLC connection table.
  2. Response-confirmed write acceptance (pending-write table) as hardware state. This extends SCADAWall's request-only OSDA.
  3. Age-widening plant intervals as hardware-enforced write admission. This answers Lanotte's and SCADAWall's named future work.
  4. A Zynq-specific split: fabric datapath plus formally proven R5 ownership/deadline/quarantine logic. That is a finer-grained isolation story than Lanotte's "separate board".
  5. Worst-case latency and jitter with full parsing, reported as a distribution.
- **Caution:** "first FPGA ICS enforcer" and "first inline hardware Modbus whitelist" are not available claims (see Q11).

### Gaps
- I did not check commercial ICS firewalls (Tofino Xenon, Fortinet, Claroty and others) for whether they inject Modbus exceptions or TCP RSTs on refusal. Some vendor products may already return Modbus exception responses, which would weaken a "session-preserving refusal is new" claim at the product level, though not necessarily in the academic literature. This needs a targeted check of vendor manuals before submission.
- The academic literature beyond these papers was not exhaustively searched for "Modbus exception injection" or "TCP-preserving blocking". In particular I did not search IDS/IPS normalizer work (e.g., Snort/Suricata inline modes, Bro/Zeek normalizers) for response forging.

---

## Q11. Which claims would a KR260 inline gate paper be unable to make, because they are already published?

### Takeaway
A KR260 paper could not claim novelty for: FPGA enforcers or "secure proxies" for PLCs; automatic synthesis of enforcers to HDL; suppressing or replacing unsafe commands; line-rate hardware Modbus function-code and write-endpoint whitelisting; full-payload Modbus value inspection; request-sequence enforcement with timeouts; state-aware (per-process-state) write bounds; in-data-plane plant measurement history with value-aware detection; inline FPGA OT IPS at µs latency. Each has a precedent below.

### Cited Findings
- FPGA secure-proxy enforcers for PLCs, synthesized from formal timed properties to Verilog, suppressing or inserting commands — [Lanotte et al.](https://arxiv.org/abs/2105.10668); also hardware enforcers in I/O modules — [Pearce et al.](https://ieeexplore.ieee.org/document/8859335)
- Isolation argument (no Internet/USB, no runtime reconfiguration) as the root of trust — [Lanotte §2, §7.1](https://arxiv.org/abs/2105.10668)
- Line-rate programmable-hardware enforcement of Modbus function codes and write restrictions, with RTT parity against industrial switches — [P4Ward](https://www.comsys.rwth-aachen.de/publication/2025/2025_fink_p4ward/2025_fink_p4ward.pdf)
- Full-payload inspection, including register values and FC08 sub-functions, plus sequence enforcement with pending state and timeouts on a transparent bridge — [SCADAWall](https://oar.a-star.edu.sg/storage/v/vdqy8j2ezv/scadawall-a-cpi-enabled-firewall-model-for-scada-security.pdf)
- State-aware bounds on writes from a compromised HMI, with denial — [SAIN](https://www.usenix.org/system/files/usenixsecurity24-abbas.pdf)
- Per-sensor measurement history in switch registers with value-aware line-rate decisions at ns overhead — [Hu et al.](https://web.uri.edu/decps/wp-content/uploads/sites/1880/2024_SmartGridComm_Leveraging_Compact_Data_Accumulator_to_Enable_In_Network_Anomaly_Detection_in_Programmable_Switches_for_Power_Grids.pdf)
- Inline FPGA protocol-aware IPS for OT (IEC 61850) at deterministic µs latency in an SFP form factor — [SRIM abstract](https://www.e-cigre.org/publications/detail/d2-10116-2026-cyber-sentinels-harnessing-deep-packet-inspection-for-real-time-defense-of-substation.html)

### Inferences
- **Mechanism-by-mechanism status of our assets** (judged only against the papers read):
  - **Session-preserving refusal** by one-byte mutation so the PLC returns an exception: not found in any paper read. Every hardware paper drops, and P4Ward explicitly reports a connection failure. Likely novel academically, but check the vendor products and IPS normalizer literature first (Q10 gaps).
  - **Acceptance tracking** (pending writes matched to PLC echoes): not found. The closest is SCADAWall's OSDA, which keeps request-side pending/received states. Frame it as response-confirmed sequencing.
  - **Age-widening plant interval:** not found. The closest are SAIN (static per-state bounds) and Hu et al. (deviation statistics). Lanotte and SCADAWall name the need as future work.
  - **IP/TCP checksum verification plus FCS regeneration inline:** not presented as a contribution anywhere. It is standard bump-in-the-wire engineering and weak as a headline claim.
  - **R5 ownership/deadline/quarantine with formal proofs, split from the fabric:** not found as such. Lanotte has formal enforcer guarantees but on a separate board; there is no heterogeneous-SoC partitioning.
  - **Bit-exact RTL against a Python model:** not reported by others. A methodological strength, not a headline.
  - **LLM/AI agent as the upstream actor, with hazard-removal evidence:** not found. P4Ward's "compromised legitimate client" limitation is the closest acknowledged gap.
- The defensible headline is therefore the *combination*: a hardware gate on a compromised-but-legitimate client that admits writes against age-aware plant state, confirms that they took effect, and refuses without breaking the session. It should not be "inline FPGA ICS enforcement" in general.

### Gaps
- The SRIM full text could pre-empt part of the "inline FPGA" or "deterministic latency" framing. Its refusal semantics and any stateful features are unknown.
- I did not do an exhaustive "cited-by" sweep of Lanotte or SAIN for 2024-2026 follow-ups; Google Scholar was not accessible via these tools. A 2023+ hardware follow-up I missed is possible.
