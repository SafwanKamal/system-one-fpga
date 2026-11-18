# Hardware-isolated runtime monitors, Simplex/RTA, hardware RV/enforcement, Zynq US+ isolation, and RoT/attestation for OT gateways

Scope note: 8 primary papers were read in full (text extracted from the PDFs, reference lists excluded). Access level is recorded for each one. Papers that are only mentioned (R2U2, SACHa, Benhani et al., Pearce et al. smart I/O, McLaughlin C2, Mohan S3A) were **not** read in full. Their status is given under Gaps, and anything said about them comes from search abstracts or from how the papers that were read describe them.

| # | Paper | Venue/year | Access read | Area |
|---|---|---|---|---|
| P1 | Lanotte, Merro, Munteanu, "Runtime Enforcement of Programmable Logic Controllers" | arXiv 2105.10668v2 (Nov 2021); journal version of the CSF 2020 paper ("Industrial Control Systems Security via Runtime Enforcement", ACM TOPS 2022 per repository metadata) | Full text (arXiv v2) | Formally synthesized enforcer on an FPGA proxy for networked PLCs |
| P2 | Gross, Jacob, Zankl, Sigl, "Breaking TrustZone memory isolation and secure boot through malicious hardware on a modern FPGA-SoC" | J. Cryptographic Engineering 12:181-196, 2022 (open access) | Full text | Zynq US+ isolation broken from the PL |
| P3 | Abdi, Chen, Hasan, Liu, Mohan, Caccamo, "Restart-Based Security Mechanisms for Safety-Critical Embedded Systems" | arXiv 1705.01520 (2017); later ICCPS 2018 / IEEE IoT-J 2019 | Full text (arXiv v1) | Simplex plus an isolated hardware RoT timer that survives a root-compromised controller |
| P4 | Bak, Johnson, Caccamo, Sha, "Real-Time Reachability for Verified Simplex Design" | RTSS 2014 (just before the 2015 window, included as the core Simplex/RTA formal primary) | Full text (author PDF) | Simplex switching logic with proof |
| P5 | Gautham, Rajagopala, Jayakumar, Deloglos, Karincic, Elks, "Heterogeneous Runtime Verification of Safety Critical Cyber Physical Systems" | arXiv 2009.09533 (2020), venue not confirmed | Full text | FPGA stream RV monitors (TeSSLa) on Zynq-7000 |
| P6 | Hebballi, Poptani, Benny, Kalayappan, Chandran, Phawade, "Dynamically Reprogrammable Runtime Monitors for Bounded-time MTL" | arXiv 2603.19851 (Mar 2026) | Full text | Hardware MTL monitor with correctness proofs |
| P7 | Wang, Chang, Zhu, Wang, Gong, Li, "Towards Runtime Customizable Trusted Execution Environment on FPGA-SoC" (RCTEE) | arXiv 2307.04375v2 (2023), venue not confirmed | Full text | Zynq US+ trusted boot, PUF attestation, PCAP lock-down |
| P8 | Ghaeini, Chan, Bahmani, Brasser, Garcia, Zhou, Sadeghi, Tippenhauer, Zonouz, "PAtt: Physics-based Attestation of Control Systems" | RAID 2019 (USENIX) | Full text | Remote attestation of PLCs without a hardware RoT |

---

## Q1. Per-paper extraction: mechanism, isolation boundary/TCB, threat model, results, formal guarantees, limitations and future work, relevance to our device

### Takeaway
The closest published prior art is P1: formally synthesized enforcers, run on FPGAs as physically separate proxies between PLCs and the field and inter-PLC network. It already claims transparency, soundness, deadlock-freedom and divergence-freedom, which pre-empts a bare claim of a "formally verified FPGA bump-in-the-wire for PLCs". P1 is still a lab proxy over UDP on discrete NetFPGA boards. It assumes the enforcer is a separate trusted device, it does not track whether a write was actually accepted or applied, and it has no SoC co-residency story. P2 shows the opposite risk on our exact silicon family: on Zynq US+ with Xilinx-tool-generated XMPU/XPPU settings, a PL master on the ACP reaches APU secure memory, OCM, eFuses and BBRAM. Any claim that "enforcement survives a compromised A53" therefore needs explicit evidence about configuration and the direction of each port.

### Cited Findings

#### P1. Lanotte et al., runtime enforcement of PLCs (full text)
- **Mechanism and placement.** One "secure proxy" (an edit automaton) sits on the network interface of each PLC. It mediates sensor readings in, actuator commands out, and inter-PLC channel messages. It can allow, suppress or insert actions. On a violation it suppresses the rest of the PLC's scan cycle and then inserts a safe trace ending in `end`, autonomously if necessary. — [P1 arXiv](https://arxiv.org/abs/2105.10668)
- **Isolation assumption, not demonstrated.** Enforcers are "physically independent secure proxies with no Internet or USB access, and connected with the controller via secure channels". The model also states that "runtime reconfigurations of secure proxies are not allowed". FPGAs are argued to be suitable only "under the assumption that the adversary does not have physical access to the FPGA and she cannot do remote updates". — [P1](https://arxiv.org/abs/2105.10668)
- **Threat model.** Malware in one or more PLCs, possibly colluding, may forge or drop actuator commands, modify sensor readings inside the PLC, and forge or drop inter-PLC messages. Network-level or sensor-device tampering is explicitly out of scope. Malware is assumed never to violate the PLC maximum cycle limit, and the `end` signal cannot be forged. — [P1](https://arxiv.org/abs/2105.10668)
- **Formal guarantees.** Synthesis from a timed regular-property language (a subclass enforceable by finite edit automata, following Beauquier et al.). Proven: determinism preservation (Prop. 2), transparency (Thm 1), soundness (Thm 2), deadlock-freedom for k-sleeping properties (Thm 3), divergence-freedom (Thm 4), and scalability to networks (Cor. 1). Synthesis complexity is O(|P|^(k+1)), where k = dim(property). Proofs are pen-and-paper in an appendix; no mechanized proof is mentioned. — [P1](https://arxiv.org/abs/2105.10668)
- **Implementation.** A Python synthesizer (ANTLR parser) emits Verilog, which is checked in ModelSim and run on 3 NetFPGA-CML boards. PLCs are OpenPLC on Raspberry Pi 4 and the plant is SWaT simulated in Simulink, all connected by UDP implemented on the FPGAs. — [P1](https://arxiv.org/abs/2105.10668)
- **Measured results.** Resource use scales with the number of scan cycles a property spans: 1000-scan-cycle properties use about 5% of the FPGA and 10000 cycles use about 13% (absolute LUT counts not reported). FPGAs were clocked at 1 MHz against 0.1-1 kHz PLC scans, so overhead is called "negligible". Ethernet is 1 Gbps with about 100 µs latency. Five ladder-logic malware attacks were mitigated: a valve-command drop (DoS), an offset of -30 on a level sensor, valve chattering by injection, chattering by sensor flipping, and a pump turned on while dry. The first enforced property (φ1) failed to stop the DoS, so a stronger property, CBE[1,1](close_req, close), was needed. — [P1](https://arxiv.org/abs/2105.10668)
- **Related prior art P1 cites as hardware proxies.** McLaughlin's C2 can suppress PLC commands but "cannot autonomously send commands". Mohan et al.'s S3A uses side-channel timing monitors with a Simplex switch, and its stated limitations are possible compromise of the side channels and manual tuning of timing parameters. Pearce et al.'s "smart I/O modules" do bi-directional enforcement on FPGA, but "a networked system featuring multiple I/O modules may significantly complicate the enforcement". — [P1](https://arxiv.org/abs/2105.10668)
- **Future work.** The authors plan to "consider physical plants with significant uncertainties", using estimators based on control theory. They also want to "deal with malicious alterations of sensor measurements" by adding physics-based detection, and to target robotic arms. — [P1](https://arxiv.org/abs/2105.10668)
- **Relevance to us.** Already published: an FPGA enforcer between PLC and network, synthesized from timed properties, with transparency and soundness proofs and autonomous insertion of a safe action. What our assets add:
  - (a) Our gate is a transparent, protocol-level Modbus/TCP inline device: checksum/FCS regeneration and a one-byte refusal mutation that keeps the session alive. P1 works on abstract signals over custom UDP.
  - (b) Acceptance tracking. Our pending-write table is matched against the PLC's echoes. P1 assumes an actuator command that is emitted is also executed.
  - (c) Plant-interval widening with reading age. P1 has no notion of stale sensor data.
  - (d) Co-residence on an MPSoC with an R5 and a Linux A53 that may be compromised. P1 assumes a separate box.
  - (e) The protected party is an AI agent upstream of the PLC, not malware inside the PLC.

#### P2. Gross et al., breaking TrustZone and secure boot on Zynq US+ from malicious PL (full text)
- **Platform.** ZCU102 (ZU+ EG: 4x A53 APU, 2x R5 RPU, 256 KB OCM, 2 GB DDR), Vivado/PetaLinux 2018.2, OP-TEE 3.4.0. Portability was checked by comparing the generated `psu_init.c` for ZCU104, ZCU106 and Ultra96-V2, which configure the same masks. — [P2 JCEN](https://link.springer.com/article/10.1007/s13389-021-00273-8)
- **Isolation primitives described.** The SMMU does two-stage translation for I/O masters. There are 8 XMPUs at the DDR and OCM controllers that check address range, master ID with mask, and the TrustZone bit. The XPPU uses 400 apertures with master-ID permission lists and a TrustZone bit. XMPU registers can be locked after configuration. — [P2](https://link.springer.com/article/10.1007/s13389-021-00273-8)
- **Root cause 1: ACP bypasses the SMMU.** The ACP connects directly to the APU snoop control unit, uses 40-bit physical addresses, and "is not connected to the SMMU". ACP and ACE are the only PL interfaces with physical-address access; the other PL ports go through the SMMU. — [P2](https://link.springer.com/article/10.1007/s13389-021-00273-8)
- **Root cause 2: XMPU/XPPU mask misconfiguration by Xilinx tooling.** The Vivado Isolation Configuration produced APU core-0 entries (ID 128, mask 960) that cannot tell APU transactions from ACP ones (ACP IDs 144/148/152/160 masked down to 128). XMPUs also sit at the DDR controller, so data already in L2 is reachable from the ACP whatever the XMPU says. — [P2](https://link.springer.com/article/10.1007/s13389-021-00273-8)
- **Root cause 3: the TrustZone bit is controlled by the PL master.** A PL master can set AxPROT[0]=0 to mark its transactions secure. The authors note that Xilinx provides no way to impose a fixed security policy on PL AXI masters. — [P2](https://link.springer.com/article/10.1007/s13389-021-00273-8)
- **Attacks demonstrated.**
  - (PoC1) Overwrote OP-TEE's `shdr_verify_signature` in secure-world DDR, so unsigned trustlets run.
  - (PoC2) Dumped 8 MB of secure-world memory and recovered an AES-128 key schedule.
  - (PoC3) Through the ACP and XPPU flaw, programmed a second PPK hash into eFuses and an AES key into BBRAM. This lets an attacker boot an authenticated image of their own under "hardware root of trust" secure boot, and the change persists across reboots.
  — [P2](https://link.springer.com/article/10.1007/s13389-021-00273-8)
- **Mitigations evaluated.**
  - Manually changing the XMPU/XPPU masks to 976 plus an added core-0 entry (160, 1008) restores isolation. Changing only the mask to 976 stops the system booting.
  - L2 cache maintenance on the secure-to-normal switch is still required.
  - Not using the ACP, or sandboxing it ("Border Control" or an AXI firewall wrapper), works.
  - Programming both PPK eFuse sets blocks the boot attack.
  - Putting the TEE in OCM does **not** help, because the XMPU fails there too.
  - CPU-bound and cache-locked execution (Sentry, CaSE) does not help, because the ACP snoops caches.
  — [P2](https://link.springer.com/article/10.1007/s13389-021-00273-8)
- **Disclosure.** Xilinx Answer Record 72654 (July 2019). Xilinx acknowledged the peripheral (XPPU) issue on 26 Jan 2021, and ZU+ documentation now advises care with the ACP. — [P2](https://link.springer.com/article/10.1007/s13389-021-00273-8)
- **Threat-model direction.** The attacker is malicious PL logic attacking the PS. The paper does **not** study a compromised A53 attacking the PL or the R5. It states that XMPU registers are locked and that the fabric is loaded after the processor boots. — [P2](https://link.springer.com/article/10.1007/s13389-021-00273-8)
- **Recommendations.** Authors "strongly recommend to perform a security risk assessment" before using the ACP, and prefer "sandboxing for ACP accelerators". — [P2](https://link.springer.com/article/10.1007/s13389-021-00273-8)
- **Relevance to us.** The PL-to-PS direction matters if our gate RTL shares the fabric with third-party or HLS IP that has ACP/HP master ports, or with the LLM encoder RTL that already uses AXI memory ports. The broader lesson is that XMPU/XPPU settings generated by the tool cannot be trusted as evidence, so any isolation claim must publish the actual register values and a negative test. The paper also enumerates the shared-resource paths (DDR, OCM, L2/SCU, eFuse/BBRAM controllers) that a reviewer will ask about in the A53-to-gate direction.

#### P3. Abdi et al., restart-based security with a hardware RoT (full text)
- **Mechanism.** System-wide restarts reload a clean image from read-only storage. After each restart a Secure Execution Interval (SEI) runs with all external interfaces disabled. During it the safety controller runs and `FindRestartTime` computes the next safe restart time with real-time reachability. An isolated hardware RoT accepts `SetRestartTime` exactly once per boot and then drives the reset pin. — [P3 arXiv](https://arxiv.org/abs/1705.01520)
- **TCB and isolation.** The RoT is an MSP430G2452 (LaunchPad) with a 16-bit Timer A at 1 MHz, connected over I2C, which it disables after receiving the time, plus pin P2.0 wired to the ZedBoard reset. It is required to have "no connectivity except for the HW interface setRestartTime". The main controller is a ZedBoard (Zynq-7000 XC7Z020) running FreeRTOS on one A9 core, with PL providing I2C/UART. — [P3](https://arxiv.org/abs/1705.01520)
- **Threat model.** The attacker can fully compromise the RTOS and applications once interfaces are enabled ("root/administrative access"). Assumed trusted: the original image, read-only storage, an incorruptible RoT, and sensor/actuator integrity. Out of scope: network MITM/DoS and sensor jamming. — [P3](https://arxiv.org/abs/1705.01520)
- **Formal guarantee (Thm 3).** Restarting at t+r is safe if three conditions hold: (1) Reach_{≤r+Tr}(x, UC) ⊆ S; (2) Reach_{≤T}(Reach_{=r+Tr}(x, UC), SC) ⊆ S; (3) Reach_{=T}(·) ⊆ R. Here R comes from the Lyapunov/LMI ellipsoid xᵀPx < 1. The proof is adapted from P4. — [P3](https://arxiv.org/abs/1705.01520)
- **Results.**
  - Reboot time on the ZedBoard is 390 ms, with a 20 ms (50 Hz) safety-controller period.
  - The maximum safe restart window is 1.23 s for the 3DOF helicopter and up to 6235 s for warehouse temperature control.
  - Weighted availability is 64.3% for the helicopter and 99.9% for temperature control.
  - Three attacks on the real helicopter (kill the controller task, corrupt sensor values in software, a worst-case fan-off immediately after the SEI) and one heater attack in hardware-in-the-loop all stayed safe.
  — [P3](https://arxiv.org/abs/1705.01520)
- **Limitations.** "Restarting does not fix the vulnerabilities of the system". The approach is unsuitable for fast dynamics, and the attacker can re-enter after each reboot (mitigated by schedule randomization with TaskShuffler). The paper says it "does not mitigate network attacks such as man-in-the-middle". — [P3](https://arxiv.org/abs/1705.01520)
- **Relevance to us.** This is the canonical published template for "safety survives full compromise of the main processor, because a tiny, isolated hardware RoT can only be configured once per epoch". Our R5 ownership, deadline and quarantine logic plus the PL gate map naturally onto the RoT/SEI roles. The difference is that P3's RoT is a *separate chip*. Putting that role on the same MPSoC (R5 plus PL) as the A53 is exactly the claim that would need new isolation evidence. P3 also leaves network-path enforcement out of scope, which is our gate's whole job.

#### P4. Bak, Johnson, Caccamo, Sha, Real-time reachability for verified Simplex (full text)
- **Mechanism.** In Simplex, a complex controller is wrapped by a verified safety controller and a decision module. The new switching rule (Thm 3) allows the complex controller if, for one decision period δ followed by a horizon T under the safety controller, the system stays admissible and lands inside the LMI ellipsoid R. — [P4](http://stanleybak.com/papers/bak2014rtss.pdf)
- **Algorithm.** Real-time mixed face-lifting reachability: an anytime/imprecise-computation method with no dynamic memory or recursion. Each advance costs O(n), and the time step is halved on each refinement. — [P4](http://stanleybak.com/papers/bak2014rtss.pdf)
- **Results.** On an inverted pendulum with saturation, the region where the complex controller may be used is 227% of the LMI-only region at 20 ms runtime and 213% at 5 ms, against an estimated optimum of 247%. Measured in software on an i7 laptop, not on embedded hardware or an FPGA. — [P4](http://stanleybak.com/papers/bak2014rtss.pdf)
- **Assumptions.** The plant model is correct and the complex controller is over-approximated by actuator limits. "Accuracy and validation of the model itself is an important problem" is left out of scope. Future work covers more hybrid-automaton classes, online system identification, and "detecting sensor spoofing". — [P4](http://stanleybak.com/papers/bak2014rtss.pdf)
- **Relevance to us.** This is the formal shape of a Simplex decision module. Our plant-level interval widening with reading age is a coarse, conservative cousin: interval over-approximation of plant state under staleness. P4 gives the proof template, but it has no hardware isolation and no network semantics.

#### P5. Gautham et al., heterogeneous FPGA RV monitors (full text)
- **Mechanism.** Stream runtime verification monitors written in TeSSLa and compiled to Verilog, running on a Zynq-7000 XC7Z010 in Simulink FPGA-in-the-loop mode. There are two layers: "data monitors" (sensor plausibility such as rate limits) and "functional monitors" (controller input-to-output relations). A Cortex-M4 AEB controller is observed through CoreSight ITM over SWO. — [P5](https://arxiv.org/abs/2009.09533)
- **Isolation claim.** Monitors are "on a separate platform and isolated from the system being monitored". The paper analyses no threat to the monitor itself. The monitors only detect; they do not enforce. — [P5](https://arxiv.org/abs/2009.09533)
- **Results.** One TeSSLa property uses less than 2% of LUTs and less than 1% of slice registers on an XC7Z010. Data and functional monitors each detect attacks the other misses (relative-velocity injection versus a failure to escalate braking). No latency figures are given. — [P5](https://arxiv.org/abs/2009.09533)
- **Formal guarantees.** None beyond TeSSLa semantics. Future work: execution monitoring with ETM/PTM, and to "verify the completeness of monitors using property based fault injection". — [P5](https://arxiv.org/abs/2009.09533)
- **Relevance to us.** This is evidence that FPGA RV monitors are cheap and that layering helps. It is weak on threat model and enforcement, so it is useful mainly as a contrast case for our enforcing, inline design.

#### P6. Hebballi et al., reprogrammable bounded-MTL hardware monitor (full text)
- **Mechanism.** Homogeneous "Abstract Machines" (not/and/or/implies/wire plus a queue with conditional modify), composed through crossbar interconnects to realize any bounded discrete-time MTL formula. The design is reprogrammed through 8-bit program words rather than by FPGA reconfiguration. It is a standard-cell design in a 32 nm educational library. — [P6](https://arxiv.org/abs/2603.19851)
- **Formal guarantees.** Theorems 1-2 and Corollary 1 show that each Evaluator Machine emits the correct verdict at latency l(φ) and that verdicts are stable. Proposition 1 shows the three AMs of the Until operator never write the same cells. Proofs are by hand in an appendix. Verification of the generated hardware was by simulation only. — [P6](https://arxiv.org/abs/2603.19851)
- **Results.** The largest configuration (16 APs, 16 PEs/queues, queue depth 256) takes 0.55 mm² at 1.25 GHz with one verdict per cycle. Reprogramming took 41 cycles in the simulated configuration, with verdict latency of 8-11 cycles for the example formulas. — [P6](https://arxiv.org/abs/2603.19851)
- **Stated motivation relevant to Zynq.** Processor-to-FPGA bandwidth "is limited even on state-of-the-art Systems-on-Chip (SoCs) such as Zynq Ultrascale+". Future work: better interconnects. — [P6](https://arxiv.org/abs/2603.19851)
- **Relevance to us.** The current state of the art for hardware temporal-logic monitors with proofs. These are detection-only verdict streams with no threat model and no network or protocol layer. A runtime-reprogrammable monitor is also an attack surface (programmable through I/O pins), which conflicts with the "no runtime reconfiguration" stance taken in P1 and P3.

#### P7. Wang et al., RCTEE on Zynq US+ (full text)
- **Platform.** XCZU15EG with Vivado/Vitis/PetaLinux 2020.1. The design starts from FPGA-SoC tbTEE (Gross et al. trusted boot): a custom FSBL measures each partition with the CSU SHA3-384 engine, writes the measurements to the last chunk of OCM, and OP-TEE copies them into secure memory and clears them. — [P7](https://arxiv.org/abs/2307.04375)
- **Isolation mechanisms used.**
  - (a) A custom PMU firmware with the XilFPGA library removed, so neither the rich OS nor the trusted OS can use PCAP directly. The authors note that "PCAP cannot be isolated from ROS using isolation flow".
  - (b) A new OP-TEE syscall is the only route that programs PL, through CSUDMA to PCAP.
  - (c) A ring-oscillator PUF exposed as an AXI-secure IP (AxPROT) that only OP-TEE can reach.
  - (d) TA authentication with a key held by a trusted third party.
  — [P7](https://arxiv.org/abs/2307.04375)
- **Threat model.** Includes insiders with physical access who control the rich OS and some hardware. Readback of bitstreams through PCAP/ICAP is named as a known threat. — [P7](https://arxiv.org/abs/2307.04375)
- **Results.** The initial design uses 18,802 LUTs (4.10%) and 20,069 FFs. Key generation takes 5 ms, ECDH 2 ms, the PUF read 53 ms and the boot-hash read 51 ms. Bitstream checks cost 0.01345 ms/KB, programming 0.0071 ms/KB, and the REE copy 0.2242 ms/KB. — [P7](https://arxiv.org/abs/2307.04375)
- **Limitations.** The security analysis is informal (a table of attacks against requirements) with no attack experiments. The experiment used a BBRAM "test mode" rather than eFuse secure boot. P7 relies on TrustZone and AxPROT, which P2 showed a malicious PL master can forge. P7 does not engage with P2's ACP and mask findings. Future work: "exploring support for multi-tenancy in FPGA-SoC by partitioning PL". — [P7](https://arxiv.org/abs/2307.04375)
- **Relevance to us.** A concrete, ZU+-specific recipe for (i) measured boot of all partitions including the bitstream, (ii) locking PCAP away from Linux through custom PMU firmware, and (iii) a PUF-backed attestation key. Point (ii) matters for us: if root on the A53 can reach PCAP/`fpga_manager`, it can replace the gate bitstream, and our claim of survival under A53 compromise collapses.

#### P8. Ghaeini et al., PAtt (full text)
- **Mechanism.** The verifier sends a nonce. The PLC (Siemens S7-1200) hashes its logic blocks plus the nonce with SHA-256 and turns the hash into an actuation path (orderings of x/y micro-steps of a robot arm that reach the same endpoint). IMU sensor traces are decoded by an ML classifier, and a weighted Hamming distance against the expected hash authenticates both the logic and the "physical PUF". — [P8](https://www.usenix.org/system/files/raid2019-ghaeini.pdf)
- **Threat model and TCB.** The PLC is fully compromised, cannot reach external compute, and has limited memory. There is no hardware RoT. The hash covers only memory the logic can access, **not the RTOS/firmware**. The attestation server is trusted. — [P8](https://www.usenix.org/system/files/raid2019-ghaeini.pdf)
- **Results.**
  - Prover code is 315 LoC in function blocks and the verifier is more than 3000 LoC of Python.
  - Each 10 ms scan cycle carries 8 micro-commands, so a full attestation takes 32 rounds with fresh nonces. The response window is two scan cycles (20 ms).
  - Random Forest decoding accuracy is 0.9923.
  - With τ = 0.95, accuracy is 97%, sensitivity 96% and MCC 0.95 (one false positive in 60 normal runs).
  - With τ = 1, 1-bit flips are detected only 7 of 20 times; 2-bit and replay attacks are detected 20 of 20.
  — [P8](https://www.usenix.org/system/files/raid2019-ghaeini.pdf)
- **Limitations.** Needs "critical zones" and spare motion, so "processes that have no downtime or are always performing some critical action" cannot use it. It also needs high-speed actuation and sensing. — [P8](https://www.usenix.org/system/files/raid2019-ghaeini.pdf)
- **Relevance to us.** The paper states that PLCs "do not have hardware support to provide a hardware root-of-trust". That is the gap an inline gate with its own RoT (ZU+ CSU secure boot, PUF, measured bitstream) can fill: attesting the *gate* rather than the PLC, and logging PLC acceptance evidence.

### Inferences
- **Already published:**
  - (i) Formally synthesized FPGA enforcers between PLCs and the network, with soundness and transparency proofs (P1, and per P1, Pearce et al.).
  - (ii) An isolated hardware RoT that keeps physical safety under a root-compromised main controller, with Simplex reachability proofs (P3, P4).
  - (iii) Cheap FPGA RV monitors (P5) and proven reprogrammable MTL hardware (P6).
  - (iv) ZU+ measured boot and PCAP lock-down (P7).
- **Not published in what was read:**
  - (a) An enforcer that tracks whether each write was *actually accepted* by the PLC (P1 assumes emitted equals executed; P3 assumes "commands sent to the actuators are executed accordingly").
  - (b) Enforcement over a real TCP-session protocol that stays inline without breaking sessions.
  - (c) Isolation evidence for an enforcer co-resident on one MPSoC with a compromised Linux A53, in the A53-to-PL/R5 direction.
  - (d) Plant-interval reasoning that accounts for the age of sensor data.
- The strongest hardware contribution the evidence supports is "P1/P3-style guarantees on a single MPSoC, with acceptance-aware enforcement and measured isolation from a root-compromised A53". It is not "first FPGA enforcer for PLCs" and not "first hardware RoT for CPS safety".

### Gaps
- R2U2 (Moosbrugger, Rozier, Schumann, FMSD 51(1) 2017; RV 2015): the NTRS and repository PDFs could not be downloaded, so only search abstracts were seen ("runtime observer pairs for linear and metric temporal logics", FPGA, Bayesian diagnosis, DragonEye UAS). Area and latency numbers were not extracted. — [R2U2 search record](https://link.springer.com/article/10.1007/s10703-017-0275-x)
- SACHa (Vliegen, Rabbani, Conti, Mentens, DATE 2019; extended in IACR ePrint 2019/405): the PDF download returned HTML, so only the abstract was seen (an FPGA prover core that attests the whole FPGA, including itself). — [ePrint 2019/405](https://eprint.iacr.org/2019/405)
- Benhani, Bossuet, Aubert, "The Security of ARM TrustZone in a FPGA-Based SoC" (IEEE TC 2019, six attacks on Zynq-7000): abstract only.
- Pearce et al. FPGA smart I/O runtime enforcement, McLaughlin C2, and Mohan S3A: known only through P1's description.
- Official AMD/Xilinx documentation (UG1085 isolation chapter, XAPP1320 isolation methods, Answer Record 72654) could not be retrieved through the docs portal, so ZU+ facts here come only from P2 and P7.
- No paper read gives a hardware enforcer's TCB in LUTs alongside a mechanized proof. P1 reports only percentage utilization.

---

## Q2. Which open hardware problems do these authors explicitly name?

### Takeaway
Across the papers, the open problems the authors name are: plant uncertainty and sensor compromise in enforcers (P1, P4); sandboxing PL masters that bypass the SMMU and the lack of a fixed security policy for PL masters (P2); restart and re-infection and unsuitability for fast plants (P3); completeness of monitors (P5); monitor interconnect and processor-FPGA bandwidth on Zynq US+ (P6); PCAP isolation from Linux and PL multi-tenancy (P7); and attestation without downtime (P8).

### Cited Findings
- Enforcers must handle "physical plants with significant uncertainties", because noise can make enforcers take erroneous corrective actions; the authors also plan defences against compromised sensors. — [P1](https://arxiv.org/abs/2105.10668)
- The ACP needs sandboxing ("Border Control" or an AXI wrapper firewall), and a "security policy table" for PL masters' AxPROT bits does not exist on ZU+: "Xilinx does not provide any means to define a fixed security policy" for PL AXI masters. — [P2](https://link.springer.com/article/10.1007/s13389-021-00273-8)
- Restarting does not remove the vulnerability, so re-entry needs randomization. Fast-dynamics plants need restart rates that may be impractical. Network MITM is out of scope. — [P3](https://arxiv.org/abs/1705.01520)
- Real-time reachability for more classes of hybrid automata, model validation, and "detecting sensor spoofing" remain open. — [P4](http://stanleybak.com/papers/bak2014rtss.pdf)
- Monitor completeness through "property based fault injection", and execution-trace monitoring (ETM/PTM), remain future work. — [P5](https://arxiv.org/abs/2009.09533)
- FPGA monitors are slow to reconfigure and limited by processor-FPGA bandwidth on Zynq US+; better monitor interconnects are left open. — [P6](https://arxiv.org/abs/2603.19851)
- "PCAP cannot be isolated from ROS using isolation flow" and needs custom PMU firmware; multi-tenant PL partitioning is future work. — [P7](https://arxiv.org/abs/2307.04375)
- PLCs lack a hardware RoT, and physics-based attestation fails for processes with no downtime. — [P8](https://www.usenix.org/system/files/raid2019-ghaeini.pdf)

### Inferences
- Several named problems line up with what our board already has. P1's "plant uncertainty" matches our interval widening with reading age. P1 and P3's "commands actually executed" assumption matches our acceptance tracking. P7's "PCAP isolation" and P2's "PL master policy" match the evidence our isolation claim needs. P8's "PLCs lack RoT" matches the gate acting as an attested proxy.

### Gaps
- None of the 8 papers names "verify the actuator/PLC acknowledged the command" as an open problem. The gap is implicit in their assumptions, not stated by the authors.

---

## Q3. What is unaddressed? (acceptance tracking, networked controllers, isolation against a root-compromised A53)

### Takeaway
Three things are unaddressed in the papers read. (1) Acceptance-aware enforcement: no paper checks that a permitted write was acknowledged or applied. (2) Enforcement at the level of the real network protocol: P1 is networked but abstracts the protocol into UDP signals, and the others are bus-attached or software-only. (3) Isolation evidence for a co-resident enforcer against a root-level A53: P2 tests only the PL-to-PS direction, P7 tests nothing empirically, and P3 avoids the question by using a separate MCU.

### Cited Findings
- P1's enforcer emits or inserts actuator commands and assumes they take effect. Its malware model forbids network or sensor tampering and sees PLC outputs only at the end of each scan, with no acknowledgement channel. — [P1](https://arxiv.org/abs/2105.10668)
- P3 assumes "commands sent to the actuators are executed accordingly" and explicitly excludes network attacks. — [P3](https://arxiv.org/abs/1705.01520)
- P5 monitors through debug trace (ITM/SWO) and Simulink FIL, which is bus- or debug-attached, not inline on a network. — [P5](https://arxiv.org/abs/2009.09533)
- P2's attacker is in the PL, and it notes that XMPU registers lock after configuration and that the PL loads after the PS boots. It does not evaluate A53 root against R5/PL resources (for example A53 writes to RPU TCM, the PL's AXI-Lite control registers, CSU/PCAP, clock and reset registers, or PMU calls). — [P2](https://link.springer.com/article/10.1007/s13389-021-00273-8)
- P7 locks PCAP by removing XilFPGA from the PMU firmware but gives no adversarial test of that, and it uses the AxPROT mechanism that P2 showed PL masters can forge. — [P7](https://arxiv.org/abs/2307.04375); [P2](https://link.springer.com/article/10.1007/s13389-021-00273-8)
- P8's attestation covers PLC logic memory but "not the RTOS", and it needs PLC downtime. — [P8](https://www.usenix.org/system/files/raid2019-ghaeini.pdf)

### Inferences
- **Acceptance tracking as a hardware contribution.** A pending-write table matched against PLC echoes turns the enforcer's guarantee from "only safe commands were emitted" (P1 soundness) into "the believed plant/PLC state equals the acknowledged state". That closes the gap P1 and P3 assume away. Formally, it is a refinement of P1's soundness theorem that adds an acknowledgement event and a timeout to the trace alphabet. This could be stated as an extension of P1's TCMC model, which would be a cleaner way to position the work than claiming novelty outright.
- **Networked, session-preserving enforcement.** P1's insert and suppress operations correspond to our refusal by one-byte mutation, which keeps the TCP session alive, plus FCS regeneration, done at line rate. Showing that this does not break Modbus/TCP sessions while preserving soundness would be new relative to P1, which uses custom UDP.
- **Co-resident isolation.** Moving P3's "separate MCU RoT" onto R5 plus PL inside the same XCK26 is the risky claim. P2 shows the default isolation tooling on this family is wrong, so the claim is publishable only with measured, adversarial evidence (see Q4).

### Gaps
- No paper read evaluates the KR260/K26 SOM specifically. All the evidence on ZU+ is from ZCU102 (P2) and XCZU15EG (P7).
- No paper read measures A53-to-RPU or A53-to-PL interference (DDR bandwidth contention, interconnect starvation of the PL gate's AXI ports), which matters for deadline guarantees.

---

## Q4. What evidence would a reviewer require for an "isolated from compromised host and A53" claim on Zynq US+?

### Takeaway
Going by the attacks and assumptions in P2, P3 and P7, a reviewer would want five things. (1) The concrete XMPU/XPPU/SMMU register values, with negative tests from a root A53 *and* from every PL master port. (2) Proof that Linux cannot reprogram the PL (PCAP/`fpga_manager` locked through PMU firmware) or change gate configuration. (3) That the gate's data path and enforcement state do not depend on DDR, OCM or caches the A53 can write. (4) That A53 root cannot stop, reset, unclock or starve the R5 or the PL gate, or that doing so makes the gate fail closed. (5) Measured boot plus attestation of the bitstream and R5 firmware, with eFuse settings fixed (both PPK sets, or revocation policy).

### Cited Findings
- Tool-generated isolation can be wrong: Vivado Isolation Configuration produced masks under which ACP and APU masters were indistinguishable. Only manually corrected masks, plus L2 maintenance, restored isolation. — [P2](https://link.springer.com/article/10.1007/s13389-021-00273-8)
- The ACP and ACE bypass the SMMU and use physical addresses, and XMPUs sit at the DDR controller, so cached data is exposed. — [P2](https://link.springer.com/article/10.1007/s13389-021-00273-8)
- AxPROT[0] from the PL is attacker-controlled, so TrustZone tagging is not evidence of isolation for PL masters. — [P2](https://link.springer.com/article/10.1007/s13389-021-00273-8)
- eFuse and BBRAM are writable through XPPU-reachable peripherals. If only one PPK set is programmed, an attacker can add a second and boot their own authenticated image, persistently. — [P2](https://link.springer.com/article/10.1007/s13389-021-00273-8)
- PCAP is reachable from the rich OS by default; isolating it required custom PMU firmware with XilFPGA removed. — [P7](https://arxiv.org/abs/2307.04375)
- Measured boot with the CSU SHA3-384 engine across FSBL, bitstream, PMU firmware, ATF, OP-TEE, u-boot and Linux is feasible on ZU+, with about 51 ms to read the measurements. — [P7](https://arxiv.org/abs/2307.04375)
- P3's guarantee depends on the RoT having "no connectivity except for the HW interface setRestartTime", with set-once semantics per boot and direct control of a hardware reset pin. — [P3](https://arxiv.org/abs/1705.01520)
- P1's guarantee depends on no runtime reconfiguration of the proxy and no remote updates. — [P1](https://arxiv.org/abs/2105.10668)

### Inferences
A reviewer-proof evidence package, derived from the attacks and assumptions above:
1. **Register-level isolation manifest.** Dump and publish the XMPU (DDR, OCM), XPPU and SMMU configuration as booted, together with the lock bits. Show master-ID/mask arithmetic proving that the A53 cannot reach gate or R5 regions and that each PL master (HP/HPC/ACP/LPD) is confined. Do not use the ACP for anything near the gate, or firewall it (P2's mitigation).
2. **Negative tests from root.** From a root shell on the A53 (with `/dev/mem`, a custom kernel module, and A53-programmed DMA engines such as GDMA/ADMA), attempt to: write gate AXI-Lite registers and BRAM tables; write R5 TCM/OCM; issue PMU/IPI requests to halt, reset or power down the RPU or PL; reprogram PL through PCAP or `fpga_manager`; change PL clocks (PS clock wizard registers for pl_clk) or assert PL resets; and write eFuse/BBRAM. Each attempt should be blocked (an XMPU/XPPU error) or detected and fail closed. P2 and P7 together show every one of these paths exists on ZU+.
3. **Fail-closed semantics under denial.** P3's RoT works because a set-once timer plus a hardware reset cannot be overridden. The analogue for our board: if the A53 starves or resets the R5, or gates the PL clock, the inline path must default to blocking writes (or to a hardware-level pass-through only for reads). This needs to be demonstrated by fault injection.
4. **Data-path independence.** Show that gate verdicts never read DDR or cache lines the A53 can write. The P2 L2 and ACP findings make shared DDR the most suspect channel, so on-fabric BRAM state is the strongest argument.
5. **Boot chain and RoT.** Hardware-RoT secure boot with eFuse-programmed PPK (both sets, or deliberately revoked), and a measured bitstream and R5 image (P7 recipe). Lock PCAP from Linux. Optionally attest the gate's identity with a PUF-derived key (P7) to support a remote "the gate is the gate" claim, which complements PAtt-style PLC attestation (P8).
6. **Physical and fault attacks.** Clock and voltage glitching and DVFS-style attacks (Benhani's DVFS work, abstract only) are probably outside an OT network threat model. State the scope explicitly.

### Gaps
- No paper read reports fault-injection, clock-glitch or DVFS results on Zynq US+ against R5 lockstep or the PMU. Benhani's DVFS and TrustZone attacks target Zynq-7000 and were seen only as abstracts.
- AMD documentation on whether RPU lockstep, the PMU and the XPPU protect RPU control registers (`RPU_GLBL_CNTL`, CRL_APB reset registers) from A53 masters by default was not retrieved. This must be verified from UG1085 before any claim is made.
- No paper read quantifies DDR or interconnect contention from a malicious A53 on PL-side deadlines. This is needed if the gate's latency or deadline guarantee is part of the claim.
