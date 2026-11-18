# Refuse without breaking: where the KR260 gate leads

The hardware direction this project should pursue first is **session-preserving, acceptance-confirmed refusal of AI-agent writes, built into a board bitstream and measured against drop-based and software baselines on real Modbus/TCP PLCs**. The second is **measured isolation of the fabric gate and R5 from a root-compromised Cortex-A53 on the same XCK26**. Both rest on results nobody in the literature read here has published. Every inline hardware enforcer we found refuses by dropping: P4Ward drops the frame and reports a connection failure, and Iwasawa's FPGA firewall corrupts the FCS. No enforcer confirms that a permitted write was actually accepted by the PLC. The one Zynq UltraScale+ isolation attack paper tests only the PL-to-PS direction, never the A53 attacking the PL or R5. Many surrounding claims are already taken and must not appear as contributions: FPGA "secure proxy" enforcers for PLCs synthesized from formal properties (Lanotte et al.), line-rate Modbus function-code whitelisting on programmable hardware (P4Ward), state-conditioned write bounds against a compromised HMI (SAIN), µs-bounded FPGA ICS firewalling at 100 Mb/s (Iwasawa, abstract and tables only), and an inline FPGA OT IPS in SFP form (Moxa's SRIM, abstract only). Hardware-bound human approval with a plant-dependent deadline looks unpublished as a combination, but US patent 12299087 and its family is unexamined prior art. Every AI-to-actuator guardrail paper from 2025–2026 that we read enforces in software on or beside the agent host, so an inline device independent of both host and PLC fills a real placement gap. It must be framed as an IEC 62443-style security conduit above the SIS, never as a safety function. That rules out promoting the gate-hosted interlock, which a single network outage defeated in the project's own simulation.

## Thirty-three primary papers read in full, and where access stopped short

The synthesis draws on five literatures: inline ICS enforcement hardware; isolated monitors and roots of trust; deterministic-latency enforcement; hardware-bound approval and tamper-evident logging; and AI-to-actuator guardrails and standards. About **33 primary sources were read in full or near-full** (body, evaluation, limitations). Two were read partially: P4ICS (no full evaluation section) and FlowBlaze (§4 plus evaluation passages). Some load-bearing sources were seen only as abstracts or summaries, and every conclusion that rests on them is provisional:

| Source | Access | What depends on it |
|---|---|---|
| SRIM / "Cyber Sentinels" (Moxa, CIGRE 2026 D2_10116) | **Abstract and keywords only** (paywalled, no preprint) ([e-cigre](https://www.e-cigre.org/publications/detail/d2-10116-2026-cyber-sentinels-harnessing-deep-packet-inspection-for-real-time-defense-of-substation.html)) | That an inline FPGA OT IPS at µs latency is already claimed. Its refusal semantics and statefulness are unknown. |
| Iwasawa et al., Hitachi FPGA ICS firewall (Trans. SICE 2020) | **Abstract and tables only** (Japanese body not read) ([J-STAGE](https://www.jstage.jst.go.jp/article/sicetr/56/2/56_51/_article/-char/en)) | The bounded 2.12–2.2 µs latency precedent and FCS-corruption refusal |
| Pearce et al., Smart I/O Modules (IEEE TII 2020) | **Abstract only**, otherwise via Lanotte's description ([IEEE Xplore](https://ieeexplore.ieee.org/document/8859335)) | Hardware enforcement at the PLC I/O boundary as 2019–2020 prior art |
| Schall, Siemens, AIS 2026 | **Abstract only** ([HEP mirror](https://journal.hep.com.cn/ais/EN/10.1007/s43684-026-00136-1)) | Where its deterministic verifier runs (it could be a separate device) |
| SnapShotter (ICPS 2018) | **Slides only** ([slides](https://chenglujin.github.io/files/Snapshotter.pdf)) | Forward-secure PLC logging overhead of 54 µs per scan |
| US 12299087 "secure-write operations" family | **Title and figure text only** ([USPTO](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12299087)) | Novelty of "approved write" claims |
| IEC 62443-3-3, ISO/IEC TS 22440-1, UG1085 | **Not read** | Standards language and A53 access to R5/PL control registers |

Two systematic blind spots cut across all five areas. **IEEE Xplore and ACM DL were not swept directly**, and there was no Google Scholar "cited-by" pass on Lanotte, SAIN or P4Ward. So a 2023–2026 conference follow-up could exist unseen. **No commercial ICS firewall manual was checked** for how the product refuses traffic. The novelty judgements below are "against the literature read", not against the field.

## Five literatures, one empty intersection

### Inline ICS enforcers either drop the packet or never see TCP at all

The closest academic ancestor is **Lanotte, Merro and Munteanu**. Their edit automata are synthesized from timed regular properties straight to Verilog and run on three NetFPGA-CML boards. Each board sits between an OpenPLC controller and a Simulink SWaT plant, where it suppresses, corrects or autonomously inserts actuator commands. The authors prove transparency, soundness, determinism preservation, deadlock- and divergence-freedom by hand ([arXiv 2105.10668](https://arxiv.org/abs/2105.10668)). The threat is malware inside the PLC, not a network or upstream client. The enforcer is trusted because it is a physically separate box with no Internet or USB access and no runtime reconfiguration. It runs at **1 MHz over a custom UDP network** and has no TCP. The authors report only percentages of the device: **~5% for 1,000-scan-cycle properties and ~13% for 10,000**, with no absolute LUT counts and no worst-case latency. All five malware cases were mitigated, with no false-positive study. The stated future work names plant uncertainty: perturbations can make enforcers take erroneous corrective actions. It also names adding state estimation inside the enforcer and physics-based detection of compromised sensors ([arXiv §9](https://arxiv.org/abs/2105.10668)). That future work is the citable motivation for the project's age-widening plant interval.

**P4Ward** (Fink et al., LCN 2025) is the line-rate counterpart. It runs a MUD-derived per-device whitelist on an Intel Tofino 1, covering MAC/IP anti-spoofing, two-rate meters, Bloom-filter connection direction, and fixed-offset application fields such as Modbus function codes ([P4Ward](https://www.comsys.rwth-aachen.de/publication/2025/2025_fink_p4ward/2025_fink_p4ward.pdf)). It matches Tofino's 3.2 Tbps, and its **0.43 ms average RTT** equals plain Tofino forwarding, against 0.26 ms for an industrial switch. It holds 512 devices and 2,048 ACEs. It cannot range-match, carries only 16 bits of ingress-to-egress metadata, and concedes that attacks within allowed patterns, or from compromised legitimate devices, are beyond it. Most important for this project: when P4Ward refused an unauthorized function code it **"immediately dropped the packet ... resulting in a connection failure."** It cites Belden Tofino-class commercial appliances at roughly **1,000 pps**.

**SCADAWall** (Li et al., 2019) is a software iptables bridge on a ThinkPad. It already inspects Modbus write *values* and FC08 sub-functions. Its OSDA tracks multi-command sequences with pending, received and not-available states and a maximum wait. Measured latency is 28.73 µs mean for 100 rules, rising to a 210 µs maximum at 15 fields and 150 rules ([SCADAWall](https://oar.a-star.edu.sg/storage/v/vdqy8j2ezv/scadawall-a-cpi-enabled-firewall-model-for-scada-security.pdf)). OSDA marks a command "received" when the firewall sees it, not when the PLC confirms it. The authors found that Tofino Xenon and Check Point 1200R accepted FC06 without value checks. Their future work is preventing transitions toward "critical states".

**SAIN** (USENIX Security 2024) derives per-PLC-state invariant bounds and denies HMI variable updates that violate them inside the OpenPLC runtime. It detects **17/17 attacks at 1–2% false positives and ~3% scan overhead** ([SAIN](https://www.usenix.org/system/files/usenixsecurity24-abbas.pdf)). It trusts PLC firmware, uses static per-state bounds with no notion of measurement age, and does not say what Modbus response a denied write produces.

**Hu et al.** (SmartGridComm 2024) keep compressed per-sensor DNP3 measurement histories in Tofino-class switch registers and run in-pipeline decision trees. The added cost is **1–20 ns per packet**, with DDoS accuracy of 86–96% and FDIA accuracy of 0.865–0.890 ([Hu et al.](https://web.uri.edu/decps/wp-content/uploads/sites/1880/2024_SmartGridComm_Leveraging_Compact_Data_Accumulator_to_Enable_In_Network_Anomaly_Detection_in_Programmable_Switches_for_Power_Grids.pdf)). Mitigation is described but not evaluated.

Two BMv2 works complete the picture. Raj and Jin's controller loop installs block rules in about 1.4 ms ([NSF PAR](https://par.nsf.gov/servlets/purl/10585925)). P4ICS concedes its data-plane crypto "cannot be directly ported" to Tofino, and points to FPGA SmartNICs as the route ([P4ICS](https://cris.unibo.it/retrieve/a3fa359c-ff86-45fc-a3ac-949e98be4979/1-s2.0-S1389128626005724-main.pdf)). **SRIM** claims an FPGA-accelerated, protocol-aware inline IPS packaged as an SFP for GOOSE/SMV substations, with "microsecond-level latency". That is the entire visible content of the paper ([e-cigre](https://www.e-cigre.org/publications/detail/d2-10116-2026-cyber-sentinels-harnessing-deep-packet-inspection-for-real-time-defense-of-substation.html)).

Read together, these papers show programmable switches hitting the same ceilings again and again: slicing, no range matching, scarce metadata, no crypto. They also show that every hardware enforcer refuses by dropping or by suppressing a signal. Nobody correlates a request with the PLC's response.

### Isolation on Zynq UltraScale+ has been broken from the fabric, never tested from the A53

**Gross et al.** (J. Cryptographic Engineering 2022) is the paper a reviewer will raise first. On a ZCU102, PL logic on the **ACP bypasses the SMMU**. The XMPU/XPPU masks that Vivado's Isolation Configuration generated (APU ID 128, mask 960) **cannot tell APU from ACP transactions**. And PL masters set their own AxPROT TrustZone bit ([JCEN](https://link.springer.com/article/10.1007/s13389-021-00273-8)). The authors patched OP-TEE's signature check, dumped 8 MB of secure memory, and wrote a second PPK hash into eFuses, which persistently subverts secure boot. Corrected masks (976, plus a core-0 entry of 160/1008) and L2 maintenance restore isolation. Moving the TEE into OCM does not. The attacker sits only in the PL; the paper does **not** study a compromised A53 attacking PL or R5 resources.

**RCTEE** (Wang et al., XCZU15EG) shows two things about PCAP. First, "PCAP cannot be isolated from ROS using isolation flow": locking out the rich OS required custom PMU firmware with XilFPGA removed. Second, the authors add CSU SHA3-384 measured boot and a ring-oscillator PUF at 18,802 LUTs, with ~51 ms to read measurements ([arXiv 2307.04375](https://arxiv.org/abs/2307.04375)). Its security analysis is a table with no attack experiments, and it relies on the AxPROT mechanism that Gross showed is forgeable.

**Abdi et al.** offer the canonical template for keeping a plant safe under a root-compromised main processor. A separate MSP430 accepts `SetRestartTime` exactly once per boot and drives the ZedBoard reset pin. Real-time reachability bounds restart windows, which are **1.23 s for a 3DOF helicopter** with a 390 ms reboot. Weighted availability is 64.3% for the helicopter and 99.9% for warehouse temperature control ([arXiv 1705.01520](https://arxiv.org/abs/1705.01520)). The root of trust is a *separate chip*, network man-in-the-middle is out of scope, and the paper assumes "commands sent to the actuators are executed accordingly". **Bak et al.** supply the Simplex reachability proof template; it is software only ([RTSS 2014](http://stanleybak.com/papers/bak2014rtss.pdf)).

Two hardware RV papers show monitors are cheap but toothless. Gautham et al.'s TeSSLa monitors use under 2% of an XC7Z010 for each property, detect only, and analyse no threat ([arXiv 2009.09533](https://arxiv.org/abs/2009.09533)). Hebballi et al.'s proven bounded-MTL monitor is reprogrammable at runtime, which is itself an attack surface ([arXiv 2603.19851](https://arxiv.org/abs/2603.19851)). **PAtt** states that PLCs lack a hardware root of trust and attests logic through physics, at 97% accuracy. It cannot cover the RTOS or processes without downtime ([RAID 2019](https://www.usenix.org/system/files/raid2019-ghaeini.pdf)). That leaves room for a gate with its own measured boot to act as the attested element. The papers name the open problems explicitly: plant uncertainty (Lanotte), the lack of a fixed security policy for PL masters (Gross), PCAP isolation and PL multi-tenancy (RCTEE), and processor-to-FPGA bandwidth on Zynq US+ (Hebballi). **Nobody names "verify the PLC acknowledged the command"**; it is hidden inside the assumptions of both Lanotte and Abdi.

### The latency case for fabric holds only past the software knee

The TUM group set the methodology bar: optical taps, per-packet hardware timestamps at 12.5 ns, percentiles to 99.9999%, and worst-5000 scatter plots. On a Xeon-D-1518, tuned DPDK Suricata sits near 10 µs median. On vanilla kernels it jumps to **~600 µs from p99.99 because of TLB shootdowns that "did not find a configuration to avoid"**, and it overloads at **~200 kpkt/s** with up to 2 ms latency and loss ([JNSM 2023](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_jnsm2022.pdf)). Snort 3 with rules overloads at **~70 kpkt/s**, where p99 reaches about 24.9 ms and the maximum about 28 ms. Bursts of 32–64 packets at a mean of only 10 kpkt/s already break a 1 ms target because of DPDK batching. Untuned Snort in a VM shows a p99.99 of 1.7 ms ([NOMS 2020](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_noms2020.pdf)). Determinism costs ~48% more idle power and dedicated cores.

On the FPGA side, Pigasus reaches 100 Gb/s IPS with ~3 µs common-case latency. It measured latency only at low load, and adversarial reordering pushed innocent goodput down to 81–90% ([OSDI 2020](https://www.usenix.org/system/files/osdi20-zhao_zhipeng.pdf)). FlowBlaze stays under 1 µs per packet at 40G with 64 B frames, at 22 W ([NSDI 2019](https://www.usenix.org/system/files/nsdi19-pontarelli.pdf)). **Iwasawa et al.** already report an FPGA ICS firewall at 100BASE-TX whose latency "ranges from 2.12 µs to 2.2 µs regardless of the frame size". It discards frames by corrupting the FCS in flight ([J-STAGE](https://www.jstage.jst.go.jp/article/sicetr/56/2/56_51/_article/-char/en); abstract and tables only).

Doran et al.'s FPGA cBPF for PROFINET names the missing piece: "A concept of state ... is necessary." Adding state breaks differential verification against software ([ETFA 2023](https://digitalcollection.zhaw.ch/bitstream/11475/28963/3/2023_Doran-etal_Hard-real-time-networked-embedded-devices-and-systems_EFTA.pdf)). TSN PSFP is zero-false-positive but blind to semantics ([Meyer et al.](https://core.inet.haw-hamburg.de/assets/bibliography/eigene/mhks-nadci-20.pdf)). TSNZeek's software lag reaches 2 ms, which its authors say is too slow for prevention ([arXiv 2303.11492](https://arxiv.org/pdf/2303.11492v1)).

The measurable regime is narrow. **A 100 Mb/s link carrying minimum-size frames delivers 148.8 kpkt/s** (derived arithmetic), already about twice Snort's per-core capacity. A Cortex-A53 is almost certainly weaker per core than the Xeon-D, but that is inferred, not measured. No paper measures Suricata or Snort on any ARM SoC, and none measures an FPGA ICS gate's p99.99 under flood with 10^6+ timestamped samples. A GOOSE TT6 budget of 3 ms at 99.9999% is cited by an SEL paper, but that rests only on a search summary ([SEL](https://selinc.com/api/download/113983)) and must be verified.

### Approval and logging pieces exist separately, never bound to a released frame

**ProtectIOn** (NDSS 2020) is the architectural ancestor of hardware-bound approval. A trusted IOHub sits between a compromised host and the keyboard, mouse and display. It renders a server-signed form as an overlay the host cannot touch, and signs the exact (element-id, value) record bound to a fresh form id ([NDSS](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24112-paper.pdf)). Its motivating attacks include early form submission misconfiguring a ControlByWeb PLC (against Fidelius) and a host rendering "10" while the device signs "1000" (against IntegriKey). It has **no deadline or expiry**, no user study, and ~122k LOC of TCB on a Raspberry Pi. The authors note it could move onto an FPGA.

**Approved Too Late** (ACSOS 2026) formalises approval-to-use staleness as Execute-stage TOCTOU. Its software Freshness-Bounded Shield expires approvals beyond a margin-over-volatility horizon. That cuts oracle-labelled expiry from **3.4–24.7% to 0–1.8%**. A fixed deadline also reaches 0% but costs reward (−1200 vs −960) ([arXiv 2608.26306](https://arxiv.org/html/2608.26306v1)). The approver is an LLM judge, approvals are not bound to action bytes at runtime, and everything runs in simulation.

**CUSTOS** hashes each log event inside SGX and signs only on audit, reaching **~1.09M events/s**. It rejects TPMs at 20 ms per extend and a 734 ms median quote ([NDSS](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24065-paper.pdf)). **Walkup et al.** replay sniffed ICS I/O against the ladder program at 99.7–99.9% accuracy. They show a malicious-but-legitimate HMI setpoint write **replays with no deviation** ([CNS 2020](https://friends.cs.purdue.edu/pubs/CNS20.pdf)), which is exactly the case an approval or gate decision record must cover.

The human-factors evidence warns against naive confirmation. Attention to warnings drops after the second exposure and across a workweek ([CHI 2017](https://www.cl.cam.ac.uk/events/shb/2017/vance1.pdf)). Users missed existing agent errors in 5 of 40 trials ([CHI 2026](https://arxiv.org/html/2510.05307v4)). The named open problems are hardening the trusted device (ProtectIOn), distinguishing faults from termination attacks and the race at the moment of compromise (CUSTOS), end-to-end evaluation against Simplex-style assurance (Approved Too Late), and mandatory checkpoints for irreversible actions (Zhou et al.).

### Every AI-to-actuator guardrail sits inside the trust boundary it protects

All nine 2025–2026 guardrail papers read enforce in software on or beside the agent stack:

- **RoboGuard** uses an LLM "root-of-trust" plus LTL synthesis. RoboPAIR attack success falls from 92.3% to 2.3% ([arXiv 2503.07885](https://arxiv.org/html/2503.07885)).
- **SafeGate** reports 0.0% unsafe acceptance at 92.8% safe acceptance ([arXiv 2604.05427](https://arxiv.org/html/2604.05427)).
- **Vyas et al.** use a pre-execution validator with 2.1–2.7 s per-call latency that "preclude[s] ... hard real-time" use ([arXiv 2606.28011](https://arxiv.org/html/2606.28011)).
- **Alhazmi** uses a bounded-interface validator on Tennessee Eastman that "acts below the safety-instrumented system". Its veto never fired ([arXiv 2608.19819](https://arxiv.org/html/2608.19819)).
- **The ARTIQ "hardware safety gate"** is really a software MCP proxy with content-bound tokens. Its authors admit bypass paths ([arXiv 2606.27231](https://arxiv.org/html/2606.27231)).

None analyses compromise of the host running the guardrail. **PLCBench** gives the offensive motivation. Autonomous agents reached sustained physical impact in **75 of 240 episodes on four real PLCs** (GPT 5.5 at 79.2%). Manipulation succeeded 100% of the time over Modbus/TCP, and agents bypassed the PLC's own protection logic. The authors conclude that independent safety mechanisms "should not rely on application objects" on the writable interface ([arXiv 2608.26882](https://arxiv.org/html/2608.26882)). The ICML position paper demands "a non-bypassable, execution-time safety architecture" that is "operationally independent", but never mentions hardware ([arXiv 2602.04056](https://arxiv.org/html/2602.04056v1)). **No author calls for hardware enforcement in so many words**; the stated requirements simply point there.

The standards picture constrains framing. The CISA-led joint guidance (Dec 2025, voluntary) says to "limit active control of OT infrastructure by AI without a human in the loop". It prefers push-based or one-way flows and asks for failsafes that revert to traditional automation. It holds that "humans are responsible for functional safety" ([CISA](https://www.cisa.gov/sites/default/files/2025-12/joint-guidance-principles-for-the-secure-integration-of-artificial-intelligence-in-operational-technology-508c.pdf)). A bidirectional write gate is therefore a *compensating control on a deliberately permitted write path*, not the guidance's preferred architecture. NVIDIA's IGX Thor shows what "safety island" means commercially: separate power and clocks, ASIL-D process, SIL-3-capable, FMEDA, and TÜV inspection ([IGX brief](https://developer.download.nvidia.com/assets/igx/robotics-product-brief-igx-thor-safety-4473375.pdf)). An uncertified KR260 must borrow none of that vocabulary. ISO/IEC TS 22440-1 is still at committee draft ([ISO](https://www.iso.org/standard/89535.html)).

## The novelty ledger: taken, named, and genuinely open

The table below lists claims a KR260 paper **cannot** make, each with its precedent and how solidly that precedent was read.

| Claim the project must not make | Precedent | Access |
|---|---|---|
| FPGA "secure proxy" enforcer for PLCs; formal-property-to-Verilog synthesis; suppress/insert commands; isolation through no Internet/USB and no reconfiguration | [Lanotte et al.](https://arxiv.org/abs/2105.10668); also [Pearce et al.](https://ieeexplore.ieee.org/document/8859335) | Full / abstract |
| Line-rate programmable-hardware Modbus FC and write-endpoint whitelisting at switch-parity RTT | [P4Ward](https://www.comsys.rwth-aachen.de/publication/2025/2025_fink_p4ward/2025_fink_p4ward.pdf) | Full |
| Inspecting Modbus write values and FC08 sub-functions; request-sequence enforcement with pending state and timeouts on a transparent bridge | [SCADAWall](https://oar.a-star.edu.sg/storage/v/vdqy8j2ezv/scadawall-a-cpi-enabled-firewall-model-for-scada-security.pdf) | Full |
| State-conditioned bounds on writes from a compromised HMI, with denial | [SAIN](https://www.usenix.org/system/files/usenixsecurity24-abbas.pdf) | Full |
| Plant measurement history held in the data plane for line-rate value-aware decisions | [Hu et al.](https://web.uri.edu/decps/wp-content/uploads/sites/1880/2024_SmartGridComm_Leveraging_Compact_Data_Accumulator_to_Enable_In_Network_Anomaly_Detection_in_Programmable_Switches_for_Power_Grids.pdf) | Full |
| Frame-size-independent ~2.2 µs bounded-latency FPGA ICS firewall at 100 Mb/s | [Iwasawa et al.](https://www.jstage.jst.go.jp/article/sicetr/56/2/56_51/_article/-char/en) | **Abstract and tables** |
| "First inline FPGA OT IPS" at deterministic µs latency in a deployable form factor | [SRIM](https://www.e-cigre.org/publications/detail/d2-10116-2026-cyber-sentinels-harnessing-deep-packet-inspection-for-real-time-defense-of-substation.html) | **Abstract only** |
| Separate hardware RoT keeping a plant safe under a root-compromised controller, with reachability proofs | [Abdi et al.](https://arxiv.org/abs/1705.01520), [Bak et al.](http://stanleybak.com/papers/bak2014rtss.pdf) | Full |
| Zynq US+ measured boot of all partitions, PCAP lock-out through PMU firmware, PUF attestation | [RCTEE](https://arxiv.org/abs/2307.04375) | Full |
| Hardware-signed, exact-value, nonce-bound approval through a trusted device between a compromised host and a PLC-like target | [ProtectIOn](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24112-paper.pdf) | Full |
| Approval freshness horizons / TOCTOU between approval and actuation | [Approved Too Late](https://arxiv.org/html/2608.26306v1) | Full |
| TEE hash-chain logging with deferred signing; deterministic ICS replay | [CUSTOS](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24065-paper.pdf), [Walkup et al.](https://friends.cs.purdue.edu/pubs/CNS20.pdf) | Full |

The open problems the authors **explicitly name**, which the project's assets touch, are these:

- Lanotte's plant uncertainty and in-enforcer state estimation, and SCADAWall's critical-state prevention. Both map to the age-widening interval.
- P4Ward's "attacks within allowed patterns" by legitimate clients. This maps to an LLM agent holding valid access.
- Doran's need for state in FPGA filters while preserving differential V&V. This maps to the bit-exact RTL-versus-Python methodology.
- Gross's missing fixed policy for PL masters, and RCTEE's PCAP isolation. These map to the isolation evidence the R5/PL split needs.
- ProtectIOn's device hardening, and CUSTOS's fault-versus-termination ambiguity. These map to a small RTL/R5 TCB with formally proved epoch and watchdog logic.
- Approved Too Late's call for end-to-end, latency-calibrated evaluation.

The problems that are **unaddressed by anyone read** are these:

- Refusal that keeps the TCP session alive. Every hardware paper drops or kills the FCS.
- Confirming that a permitted write *took effect* by matching the PLC's echo, exception or timeout. Lanotte and Abdi both assume that emitting a command means it was executed.
- Intervals that widen with the *age* of the last reading.
- A co-resident enforcer's isolation from a root A53, tested in the A53-to-PL/R5 direction.
- p99.99-and-beyond latency of a stateful FPGA ICS gate under flood, against a same-SoC software baseline running a co-located AI workload.
- A hardware release predicate that binds a human approval to the held frame's digest *and* a plant-dependent deadline.
- An explicit threat model in which the agent host is compromised. Under that model every reviewed software guardrail sits inside the trust boundary it guards.

Omission hazards, meaning failures to act, are not measured by any guardrail paper. The project's own simulation found them to be the dominant residual hazard. They are fundamentally outside what a write gate can fix.

Two calibration points prevent over-claiming. First, the pending-write table is a **response-confirmed extension of SCADAWall's request-only OSDA**, not an idea from nowhere. It can be stated formally as a refinement of Lanotte's soundness theorem, with acknowledgement and timeout events added to the trace alphabet. Second, IP/TCP checksum verification and FCS regeneration are standard bump-in-the-wire engineering, too weak to headline.

## Five hardware directions, ranked against what is already published

The ranking weighs novelty against the literature read, feasibility on the KR260 given existing assets, and publishability (venue fit and reviewer resistance). Directions 1 and 2 are the recommended programme. Direction 3 is best run as the evaluation section of Direction 1 rather than as a standalone paper.

| Rank | Direction | Novelty | Feasibility on KR260 | Publishability | Main dependency |
|---|---|---|---|---|---|
| 1 | Session-preserving, acceptance-confirmed refusal in silicon, on real PLCs | High (no read paper does it) | High: RTL exists, needs a bitstream | High (ACSAC/RAID/ESORICS-class systems security; IEEE TII) | Vendor-firewall and patent check; PLC conformance to FC 0x7F |
| 2 | Measured isolation of gate and R5 from a root-compromised A53 on XCK26 | High (Gross tested only PL→PS) | Medium: boot-chain control on the Kria SOM is a risk | High (WOOT/HOST/JCEN-style; also a strong section of #1) | UG1085 register access facts |
| 3 | Tail latency under attack: same-SoC software vs fabric, with a co-located AI workload | Medium (Iwasawa holds bounded latency; methodology and stateful parts are new) | High | Medium standalone (ETFA/FPL); high as part of #1 | Hardware timestamping rig |
| 4 | Hardware-bound approval: digest ∧ plant-dependent deadline ∧ epoch, with a sealed replayable record | High as a combination | Medium-low: needs #2, PMOD isolation, a human study | High if the human study is sound (NDSS/USENIX Sec-class) | US 12299087 family, IntegriKey, APC |
| 5 | Age-aware, response-confirmed admission validated on Tennessee Eastman with real PLCs | Medium (SAIN and Hu are adjacent) | High (Python model and RTL exist) | Medium (TII / CPS venues) | Independence from the self-authored plant |

### Direction 1: refuse in silicon without killing the session, and prove the write landed

This direction moves the v3 gate into a board bitstream and makes its two distinctive behaviours the headline. The first is **refusal by mutating the function code to 0x7F**, so the PLC itself returns an exception, which the gate rewrites to exception 03, keeping the TCP session with an incremental checksum and regenerated FCS. The second is **acceptance tracking**, which matches writes against PLC echoes, exceptions or timeouts in the 8-entry pending table. The threat model is a compromised or prompt-injected agent holding legitimate Modbus access. That is the case P4Ward explicitly cannot handle, and the one PLCBench shows reaching physical impact.

**Falsifiable claim.** On at least three Modbus/TCP servers from at least two vendors, the board-resident gate meets all of the following:

- It refuses 100% of policy-violating writes.
- It keeps the client's TCP connection open across ≥99.9% of refusals.
- It returns a well-formed exception 03 within one PLC response time.
- It adds ≤1 µs of decision latency (the RTL bound is ≤0.9 µs).
- Its accepted, rejected and timed-out classification of permitted writes agrees with ground-truth PLC register state in ≥99.9% of cases under injected loss, while a read-back-only gate's agreement falls measurably when telemetry is sparse.

**Baselines to beat.** Drop-based refusal, which reproduces P4Ward's behaviour. FCS-kill refusal, which reproduces Iwasawa's. TCP RST injection. A software inline bridge (Suricata or a minimal C filter) on both the KR260's A53 and a tuned x86. The comparison metrics are session survival, the agent's time to its next successful transaction, PLC connection-table churn, and misclassified write outcomes.

**Kill criteria.** Abandon or reframe the direction if any of these hold:

- More than one of three tested PLCs mishandles a 0x7F request: it closes the connection, stays silent, or returns something other than an exception. The mechanism would then not be portable.
- With standard clients (pymodbus, libmodbus, at least one commercial HMI or SCADA client), drop-based refusal recovers within 2× of the mutation path and loses no connection. Session preservation would then carry no operational benefit.
- The commercial-firewall check or the patent check shows that exception-injection refusal with session preservation is already shipped or claimed. The novelty then shrinks to "first academic hardware implementation with acceptance tracking", which is publishable but weaker.

**First experiment.** Run a conformance probe before building any bitstream. Send FC 0x7F requests, plus the full mutate-and-restore sequence through the existing Python model, to OpenPLC and to whatever commercial Modbus servers are available. Record response code, latency and connection state over 10,000 trials. This takes days and decides whether the mechanism generalises. Then synthesize the v3 bridge into the KR260 image at the v1 bridge's 10/100 Mb/s. Re-run the ~15k-frame bridge regression on hardware through a capture tap, so bit-exactness carries from Verilator to silicon.

### Direction 2: show the gate survives root on the A53 that shares its die

The project's architecture puts an LLM-adjacent Linux A53, the R5 ownership, deadline and quarantine logic, and the fabric gate on one XCK26. Every published root of trust that keeps a plant safe under host compromise uses a **separate chip** (Abdi's MSP430) or a **separate board** (Lanotte's NetFPGAs). The only adversarial Zynq US+ study attacks from the PL, and it shows tool-generated isolation settings are wrong ([Gross et al.](https://link.springer.com/article/10.1007/s13389-021-00273-8)). Measuring the A53-to-PL/R5 direction is therefore open and publishable. It is also a prerequisite for Direction 4 and for any claim that the gate is independent of the agent host.

**Falsifiable claim.** Under a hardened configuration, root on the A53 cannot cause a policy-violating write to be forwarded by any of at least 10 enumerated paths. The hardened configuration means: PCAP locked through custom PMU firmware following the RCTEE recipe, a published XMPU/XPPU/SMMU register manifest with lock bits, gate policy and state held only in PL BRAM, and R5 code in TCM. The paths to test:

- `/dev/mem` writes to the gate's AXI-Lite registers and BRAM tables
- writes to R5 TCM or OCM
- remoteproc stop of the R5
- CRL_APB/RPU reset
- PL clock gating
- `fpga_manager` or PCAP reload
- GDMA/ADMA DMA into R5 or gate regions
- eFuse/BBRAM writes
- PMU IPI power-down
- DDR contention

Each attempt is either blocked or fails closed (writes refused) across ≥1,000 trials per path. Because the gate sits physically in the datapath, killing the PL stops forwarding, which fails closed for writes. That is a structural argument worth stating, but it must be measured.

**Baseline to beat.** The stock Kria Ubuntu / PetaLinux image. The project's inference, still to be verified, is that most of these paths succeed by default, because the Kria runtime is designed for Linux to load PL applications.

**Kill criteria.** Stop if UG1085 or the experiments show that the A53 can rewrite gate policy or state in a way no XPPU aperture can separate, *and* that this makes the gate forward rather than stop. The claim would then degrade to tamper evidence, the territory of CUSTOS and RCTEE. Also stop if hardening requires replacing the SOM's AMD-supplied boot firmware in a way the board cannot support. That is a feasibility risk to check first, not an established fact.

**First experiment.** Run a two-day red team of the stock image. Execute every path above from a root shell and log the outcome. Then dump the as-booted XMPU/XPPU configuration and do the master-ID/mask arithmetic Gross et al. published. The negative-result table for the stock image is publishable by itself as the baseline row.

### Direction 3: find the software knee on the same die, then show the fabric has none

Iwasawa already claims bounded µs latency for an FPGA ICS firewall at 100 Mb/s, so "µs vs ms" at idle is not new. What is open: a **stateful** (TCP plus Modbus plus pending-write) fabric gate's worst case under adversarial load, measured with the TUM methodology, against a **same-SoC software baseline running while the board's own AI workload executes**. No paper measures Suricata or Snort on an ARM SoC. The co-location penalty is known only from x86: 64% LLC-contention loss, and TLB-shootdown spikes of ~600 µs.

**Falsifiable claim.** A Modbus filter on the KR260's A53 (Suricata inline, plus a minimal C bridge) exceeds 1 ms p99.99 latency for legitimate transactions in either of two conditions: offered 64-B floods at 100 Mb/s line rate (148.8 kpkt/s), or the encoder/LLM workload running on co-located cores. The fabric gate's maximum latency stays within its RTL-derived bound across ≥10^6 hardware-timestamped samples under the same conditions. That holds through SYN floods, retransmission and out-of-order storms, malformed checksums, and pending-table exhaustion.

**Baselines.** Iwasawa's 2.12–2.2 µs FPGA figure; tuned DPDK Suricata and Snort per TUM; the A53 software filter.

**Kill criterion.** If the A53 software filter holds p99.9999 below 100 µs under both flood and co-located AI load at 100 Mb/s, the latency argument at this link speed fails. In that case, move to 1 GbE or drop latency as a claim.

**First experiment.** Run the A53 minimal filter on the existing board with the encoder workload active. Measure with two hardware-timestamping NICs (i210/X550 class) on passive copper taps on both sides of the device under test, with per-packet matching over 60 s runs from 1 kpkt/s to line rate.

### Direction 4: bind a human's approval to the exact held bytes and a plant-dependent deadline

ProtectIOn binds exact values to a nonce on trusted hardware, with no deadline. Approved Too Late adds freshness horizons, with no human, no hardware and no byte binding. Nobody read combines the two at an inline OT release point. The proposed predicate is held-ADU digest = approved digest ∧ hardware timer < δ(plant state read by the gate) ∧ epoch unchanged. It would be evaluated in PL or R5, with the approver's display and button owned solely by R5/PL through PMOD, and every predicate input sealed into a hash-chained, bit-exactly replayable record. It covers the gap Walkup et al. expose: legitimate-looking malicious writes that replay cleanly.

**Falsifiable claim.** With the A53 root-compromised, the hardware predicate blocks 100% of five byte-level attack classes:

- swapping bytes after approval
- display/value substitution ("10 → 1000")
- forged or early release
- replaying an old approval
- delayed, stale release

All five succeed against an A53-hosted software dialog. In addition, the plant-dependent deadline keeps approval expiry ≤2% with less utility loss than a fixed deadline, which replicates Approved Too Late's software result in hardware.

**Baselines.** A software approval dialog on the agent host; nonce-only approval (ProtectIOn semantics); fixed-deadline approval.

**Kill criteria.** Stop if the US 12299087 family claims a held, approved write released on digest match. Stop if Direction 2 shows the PMOD/GPIO pins or the log region cannot be isolated from the A53. Stop if a pilot human study shows no gain in detection d′ over the software dialog once habituation sets in across sessions.

**First experiment.** Run a security-only bench with a scripted approver and the five injected attacks before recruiting anyone. The human study comes later: 16–48 participants over 3–5 days with a 2–5% anomaly rate, which is the size and structure Vance et al. and Zhou et al. justify.

### Direction 5: validate age-aware, response-confirmed admission on an external plant

This direction is the most feasible and the least novel. SAIN owns state-conditioned bounds, and Hu et al. own in-data-plane plant history. The new elements are intervals that widen with reading age, answering Lanotte's and SCADAWall's stated future work, and admission conditioned on PLC-confirmed outcomes. The project's evidence for both comes from a **self-authored plant and harness**, the weakness a reviewer will hit first.

**Falsifiable claim.** On the Tennessee Eastman process (the benchmark Alhazmi and Schall use), with a real PLC in the loop and telemetry polled at ≤1 Hz with injected loss, age-widening plus response-confirmed admission reduces unsafe accepted writes against SAIN-style static bounds and a read-back-only gate. The reduction must be statistically significant (paired McNemar, p<0.05), with no more than a pre-registered false-refusal budget.

**Kill criterion.** No significant improvement on the external plant means the closed-loop advantage was an artefact of the self-authored plant.

**First experiment.** Port the existing Python gate model to a Tennessee Eastman harness and re-run, before any further RTL work.

Separately, the project's own data says omission hazards dominate and that only a PLC-hosted interlock removes them robustly. The gate-hosted interlock, defeated once by an outage, should be reported as a fault-injection result, not developed into a direction. Promoting it would turn a security conduit into a de facto safety function.

## Verification before any novelty claim

Several checks are cheap compared with the cost of a rejected or retracted claim, and each one gates a specific direction:

| Check | Gates | What would change the plan |
|---|---|---|
| IEEE Xplore and ACM DL sweeps ("bump-in-the-wire" ∧ Modbus/LLM/agent; "Modbus exception" ∧ inject/forge; "TCP-preserving" ∧ block/IPS; FPGA ∧ "Zynq UltraScale+" ∧ isolation ∧ A53/RPU), plus cited-by passes on Lanotte, SAIN, P4Ward and Gross | All | Any hardware Modbus enforcer with response correlation or session-preserving refusal reframes #1 |
| SRIM full text (CIGRE delegate copy or author contact) | #1, #3 | Whether it refuses statefully, tracks GOOSE stNum/sqNum, or reports worst-case latency |
| Iwasawa body translation; Pearce et al. full text | #1, #3 | Whether either correlates responses or reports latency under flood |
| US 12299087, 12443684, 12493669, 12664237 claims | #1, #4 | Claims on held or approved writes, or on exception responses |
| Commercial ICS firewall refusal behaviour: Belden Tofino Xenon, Moxa EDR-G9010, Fortinet, Cisco ISA3000, Claroty, and Snort/Suricata inline "replace"/reject modes | #1 | Product-level exception injection weakens "new mechanism" to "new in hardware with acceptance tracking" |
| Modbus/TCP conformance of target PLCs to unknown function codes | #1 | Portability of the 0x7F mutation |
| UG1085 / XAPP1320: A53 access to RPU_GLBL_CNTL, CRL_APB resets, PL clock control, CSU/PCAP, PMU IPI; XPPU apertures available to protect them; whether Kria SOM boot firmware allows custom PMU firmware | #2, #4 | Whether "fail-closed under root" is achievable or only "tamper-evident" |
| Schall full text; IntegriKey, Fidelius, Android Protected Confirmation primary sources | #4, framing | Whether a deterministic verifier on separate hardware already exists; whether confirmation carries expiry |
| IEC 62443-3-3 SR text (conduits, SR 3.x integrity, SR 5.x restricted data flow); IEC 61850-5/-10 TT6 numbers | Framing, #3 | Exact standards language and deadlines to cite |
| Approved Too Late K_live arithmetic (it looks inconsistent in the extracted text) | #4 | Whether its example can be cited |

## Conclusion

The literature tells a consistent story. Hardware ICS enforcement has matured on the *question* side (what to allow) and neglected the *answer* side (what the PLC said back, and what happens to the session after a "no"). Meanwhile AI-guardrail research has reached the right requirements, non-bypassable, independent, fresh at actuation, without ever leaving the agent's host. The project's distinctive assets, response-matched pending writes, refusal by exception injection, age-aware intervals, and a formally reasoned R5 beside the fabric, sit precisely in that seam. The strongest paper is therefore not "an FPGA gate for AI agents". It is a demonstration that a gate on the same die as a compromised Linux host can refuse an agent's write without breaking the session, know whether permitted writes landed, and keep doing so when the host is root.

The main threat to that paper is not a competing academic result. It is an unread commercial manual or patent. That makes the vendor and patent checks, plus the PLC conformance probe, the highest-value work of the next two weeks. They are worth more than any additional RTL. The project's own simulation also argues for humility about scope. A write gate cannot cure omission, and the only configuration that reached zero hazards kept the PLC interlock in charge. The hardware contribution is strongest when it is explicitly a security conduit that makes the SIS's job easier, not a replacement for it.
