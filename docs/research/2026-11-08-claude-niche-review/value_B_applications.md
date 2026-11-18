# Value scout B: application niches where a KR260 (Zynq UltraScale+) is structurally the right hardware

Date: 2026-11-08. About 30 web searches (standard mode). I did not open the repository; project facts come from value_context.md, repo_context.md and corrections.md. Markings: **[V]** = seen in a search result or abstract; **[U]** = unverified (secondary source, abstract only, or my own inference). Numbers marked [V] are the authors' own figures, not independently reproduced.

## 0. Bottom line (read this first)

1. **"µs ML on an FPGA" is not a differentiator in itself.** LUT-based FPGA network classifiers already reach **6 ns** (FSNIC, 846 LUTs) [V] [arXiv 2609.16363](https://arxiv.org/pdf/2609.16363) and **<7 ns** on raw first-64-byte packets [V] [FPGA'25 poster](https://labs.engineering.asu.edu/advent/wp-content/uploads/sites/123/2025/04/FPGA2025_poster_Ali.pdf). FINN classified **300 M packets/s** on a ZCU104 in 2021 [V] [FINN blog](https://xilinx.github.io/finn/2021/04/12/linerate-intrusion-detection.html). hls4ml transformers run in **<2 µs** on a VU13P [V] [JINST/hls4ml](https://people.ece.uw.edu/hauck/publications/TransformerJ.pdf). Our 13 µs classifier and 8.5 ms encoder cannot win a latency race against these.
2. **Where a ≥10x or "nobody else can" gap actually exists:**
   - **(B1, strongest) A hardware-isolated "AI-to-actuator gate".** The PL plus the R5 sit between any AI planner (an LLM on the A53 or an external agent) and the fieldbus. Commands are typed, checked against an envelope, bounded by deadlines and quarantined on violation, and every decision can be replayed bit-exactly. Demand comes from CISA/NSA guidance (Dec 2025), 2026 papers showing LLMs propose unsafe OT actions in 10–70% of runs, and ISO/IEC TS 22440, which is still being drafted. Current guardrails are software in the same trust domain as the LLM. The capability gap: the gate still enforces after the Linux/LLM side is fully compromised. A software guardrail is bypassed in 100% of those cases by construction.
   - **(B2) An inline, protocol-semantic, stateful OT inspector with hard blocking and calibrated abstention.** Targets Modbus/TCP and IEC 61850 GOOSE. I found **no published FPGA Modbus/TCP deep-learning detector** and no FPGA ML detector for GOOSE. The FPGA GOOSE work I found is either inline DPI described in an abstract (SRIM, CIGRE 2026) or an older Shift-And IDS. Software ML GOOSE detectors run at about 1.1 ms. The ≥100x margin is µs vs ms. The capability gap is sequence- and semantics-level detection plus enforcement in the trip path, which the existing ns-scale FPGA classifiers (flow and header features) do not do.
3. **Weak or unsupported:** voice/text command interfaces (no documented latency requirement or demand); the in-fabric LLM as a product on its own (decode is at parity with the board's A53; no evidence of rad-tolerant, export or air-gap demand that specifically needs it). Use the decoder as the **untrusted proposer** inside B1, not as the headline.
4. **Medium:** high-rate condition monitoring (real physics need, but our text-encoder assets transfer poorly); TSN/ROS 2 integration (useful as the vehicle for B1, not a paper on its own).

---

## (a) Line-rate ML in the network path for industrial/OT security

**Demand evidence**
- FrostyGoop (Jan 2024, Lviv): malware wrote directly to ENCO controllers over **Modbus TCP port 502**. It took heating from **600+ apartment buildings** for about 2 days. It abused the protocol without exploiting any flaw, so signature or CVE filtering does not help, and semantic or behavioral checks are needed [V] [Dark Reading](https://darkreading.com/ics-ot-security/novel-ics-malware-sabotaged-water-heating-services-in-ukraine), [The Register](https://www.theregister.com/2024/07/23/frostygoop_ics_malware).
- Utilities' venue is moving to inline FPGA prevention. CIGRE 2026 D2_10116 "Cyber Sentinels" (SRIM) describes an FPGA-accelerated **inline** IPS doing protocol-aware DPI on GOOSE/SV at line rate, "microsecond-level". It also reports that CPU-based DPI "degrades significantly" under inspection load [V abstract only] [e-cigre](https://www.e-cigre.org/publications/detail/d2-10116-2026-cyber-sentinels-harnessing-deep-packet-inspection-for-real-time-defense-of-substation.html). Authorship (possibly Moxa) is [U]. CIGRE D2_11645_2026 covers a real-time ML IDS on an embedded device, lab to field [V title].
- Deadline: GOOSE trip (type 1A) and SV have a **3 ms** transfer time (TT6). IEC 61850-10 testing gives **about 20% (~600 µs)** of that to the network [V secondary] [PACW](https://www.pacw.org/real-life-case-of-routable-goose-over-mpls-tp), [IEEE TPWRD summary via scholar.utc.edu](https://scholar.utc.edu/theses/251). Class labels (P1 vs P2/3) differ between sources [V]. An inline inspector has to fit well inside about 600 µs, and ideally within tens of µs.

**Existing best solutions and numbers**
| Approach | Numbers | Limitation |
|---|---|---|
| LUT/QNN FPGA NIDS (FSNIC, LogicNets, FINN) | 6 ns, 846 LUTs; 300 Mpps [V] | Flow/header features, IT datasets (UNSW-NB15 etc.); no OT protocol semantics; detect-only in papers |
| Software GOOSE ML (arXiv 2604.14233, ERENO) | GRU F1 0.874 at **1.118 ms**; unsupervised models meet 4 ms [V] [arXiv](https://arxiv.org/html/2604.14233v1) | CPU, not inline, no enforcement |
| Commercial ICS firewalls with Modbus DPI (Tofino, Hirschmann EAGLE40) | No latency published; ETFA 2014 measured Tofino added latency (values not in snippet) [V/U] [TII 2018](https://unpaywall.org/10.1109%2FTII.2018.2802903) | Rule allow-lists, not learned or sequence-aware; DPI adds latency and jitter [V] |
| vBump (software BITW for ICS) | 150 Mbps, **~1 ms** one-way [V] [UIUC](https://experts.illinois.edu/en/publications/vbump-securing-ethernet-based-industrial-control-system-networks-/) | Software |
| SoC-e GOOSE/SV auth IP core | <7 µs [U vendor] [PACW](https://www.pacw.org/?p=4314) | Crypto only, not detection |
| Older FPGA IEC 61850 IDS (Zynq-7030, Shift-And) | no latency seen [V] [UiTM/DOAJ](https://openaccess.library.uitm.edu.my/Record/doaj-6a5fb78fb4c34127ba40d3f558fc437b/Description) | Pattern matching, no ML |
| Modbus sequence models (NFA, JISA 2025) | beat sequence DL in software [V] [Portsmouth](https://researchportal.port.ac.uk/en/publications/strengthening-ics-defense-modbus-nfa-behavior-model-for-enhanced-/) | Software |
| ET-BERT/Snort cascade (EUROSEC 2025) | 4x over ET-BERT alone [V secondary] | Software; **no FPGA transformer packet classifier found** |

**Gap/novelty.** I found no FPGA Modbus/TCP deep-learning detector and no FPGA ML GOOSE detector [V: "no published work" in two targeted searches; absence of evidence, not proof]. The open problem is **stateful, semantic** inspection: function-code and register sequences, setpoint plausibility, GOOSE stNum/sqNum and value-change consistency. It has to run inline with a **hard drop/hold**, a **calibrated abstain → hold-for-operator/alarm** path rather than a forced binary decision, and **bit-exact replay** of every verdict for forensics.

**Upgrade magnitude.** About **100–1000x** latency over software ML IDS (1.1 ms → 1–10 µs) and over software BITW (~1 ms). Against FPGA LUT nets it is a capability gain (semantic, sequential, abstaining, enforcing), not a latency gain. Do not claim latency against them.

**Asset reuse.** High. v1 raw-Ethernet path and µs classifier with integer calibrated logits and OOS abstention; v2 encoder (a small sequence model over a window of the last N Modbus PDUs or GOOSE messages as tokens); R5 deadline/quarantine logic as the enforcement policy owner; bit-exact golden models; weight-integrity tooling. KR260 has 4x GbE, two with PL TSN paths, so it can sit inline as a two-port bump-in-the-wire.

**First experiment (4–6 weeks).** A two-port PL bridge on the KR260 with a Modbus/TCP parser. Feature/token window of the last 16 PDUs (function code, address, value delta, inter-arrival). The tiny classifier first, then a 2-layer encoder. Verdict pass/drop/abstain-hold with the R5 as policy. Measure: added port-to-port latency and jitter at line rate vs a Linux nftables/Python baseline on the same board's A53; detection F1 and coverage-risk curves; replay identity. Then GOOSE using ERENO-generated traffic.

**Public datasets.** ERENO (GOOSE/SV, 7 attack classes, 69 features) [V] [SBC](https://sol.sbc.org.br/index.php/sbseg_estendido/article/view/21694). DNP3 IDS dataset (Radoglou-Grammatikis, 9 attacks) [V] [Zenodo](https://zenodo.org/records/7348493). Modbus TCP packet set, 609,934 packets [V] [IEEE DataPort ICS](https://ieee-dataport.org/keywords/industrial-control-systems-ics). ProvICS (11 M Modbus packets, process state) [V] [arXiv 2607.05989](https://arxiv.org/pdf/2607.05989). Smart-factory set (Modbus/OPC UA/MQTT, TU Wien 2024) [V] [TU Wien](https://researchdata.tuwien.ac.at/records/ghdc6-45k78). ARES 2018 Modbus set [V] [arXiv 1905.11757](https://arxiv.org/pdf/1905.11757). Edge-IIoTset, X-IIoTID, CIC IIoT 2025 (mostly flow-level IT/IoT, weak for OT semantics) [V] [CIC](https://www.unb.ca/cic/datasets/iiot-dataset-2025.html), [X-IIoTID](https://ieee-dataport.org/documents/x-iiotid-connectivity-and-device-agnostic-intrusion-dataset-industrial-internet-things). **No public labeled PROFINET/EtherNet/IP attack dataset found** [V].

**Venues.** ACM CCS/ESORICS CPS-SPC workshop, IEEE SmartGridComm, CIGRE D2, FPT/FPL (hardware), IEEE TII, ACSAC ICSS.

**Risks.** Dataset realism (ERENO is synthetic). Reviewers will ask why not just rule allow-lists. The answer has to show attacks that are protocol-valid but semantically bad, as FrostyGoop was. SRIM may already cover parts of this (full text unseen).

---

## (b) Hardware runtime assurance / AI-to-actuator gate (strongest fit)

**Demand evidence**
- CISA, ASD-ACSC, NSA et al., *Principles for the Secure Integration of AI in OT* (3 Dec 2025) [V] [PDF](https://www.cyber.gov.au/sites/default/files/2025-12/principles-for-the-secure-integration-of-artificial-intelligence-in-operational-technology.pdf), [NSA release](https://www.nsa.gov/Press-Room/Press-Releases-Statements/Press-Release-View/Article/4347041/nsa-cisa-and-others-release-guidance-on-integrating-ai-in-operational-technology/). A May 2026 agentic-AI follow-up is mentioned only by a secondary source [U].
- Schall 2026 (*Autonomous Intelligent Systems*): LLMs proposed **unsafe actions in 10–70% of runs** (N=50). A deterministic validation layer caught every invalid proposal in the covered categories [V] [journal](https://journal.hep.com.cn/ais/EN/10.1007/s43684-026-00136-1).
- RoboGuard: unsafe-plan execution falls from **92% to <2.5%** [V] [arXiv 2503.07885](https://arxiv.org/abs/2503.07885v1). SafeGate (Apr 2026), a deterministic pre-execution gate for LLM robots [V] [arXiv 2604.05427](https://arxiv.org/html/2604.05427v1). "Modular Safety Guardrails Are Necessary for Foundation-Model-Enabled Robots" (Feb 2026) argues for action-level filtering and decision gating [V] [arXiv 2602.04056](https://arxiv.org/html/2602.04056v1).
- Industry: an Automation.com article (Oct 2026) argues for a "hard boundary" between cognitive AI and deterministic safety systems [V] [automation.com](https://www.automation.com/article/securing-new-threats-industrial-ai-powered-applications-autonomous-agents). CSA research note on AI-generated S7 PLC exploits (2026) [V] [CSA](https://labs.cloudsecurityalliance.org/research/csa-research-note-siemens-s7-plc-ai-generated-exploits-20260/). Backdoored LLM PLC code generation (STBack, ACL Findings 2026) [V] [ACL](https://aclanthology.org/2026.findings-acl.609/).
- Standards gap: **ISO/IEC TS 22440** (functional safety and AI) is still at Committee Draft (CD comment period closed 2026-04-11); publication is expected in 2027 [V] [ISO](https://www.iso.org/standard/89535.html), [A3](https://www.automate.org/news/integrating-ai-in-safety-critical-systems-why-iso-iec-ts-22440-changes-the-game). Simplex/RTA is the recognized pattern [V] [Black-Box Simplex](https://arxiv.org/pdf/2102.12981), [RTA tutorial](https://arxiv.org/pdf/2110.03506).

**Existing best solutions**
- All the LLM guardrails above (RoboGuard, SafeGate, Schall's validator) are **software running on the same host/OS as the planner** [V by description]. If the host is compromised, the guardrail is gone.
- **Closest prior art:** "Runtime Enforcement of Programmable Logic Controllers" (Lanotte et al., arXiv 2105.10668). FPGA monitors act as secure proxies enforcing PLC actuator commands against forged valve/pump commands [V] [arXiv](https://arxiv.org/pdf/2105.10668). Shield synthesis [V] [arXiv 1501.02573](https://arxiv.org/pdf/1501.02573). Safety-rated FPGA template at IEC 61508 SIL 2 (SLAC) [V] [JACoW](https://proceedings.jacow.org/icalepcs2019/export/THCPR03.xml). Arm Cortex-R "safety island" actuation demo (Autoware, not an LLM) [V] [Arm docs](https://safety-island-actuation-demo.docs.arm.com/en/v2.1/overview.html). BRIK-64 "policy circuit" between AI planner and actuator [U marketing] [blog](https://brik64web-v2.pages.dev/blog/ai-guardrails-for-robots).
- Prior FPGA enforcement work targets PLC logic, **not AI/LLM-generated commands**. It does not combine typed-grammar parsing, calibrated abstention, deadline/epoch freshness or bit-exact replay of the AI's proposal.

**Gap/novelty.** An **AI-agnostic, hardware-isolated actuation gate on one $350 SoC**:
- The A53 (Linux, LLM or agent, assumed compromisable) only *proposes*.
- The PL parses a typed command grammar: tool name, fields and ranges.
- The R5 (AMP, separate memory/AXI ownership) owns envelope policy, deadline/epoch freshness, rate limits and quarantine.
- Only the PL/R5 can drive the fieldbus port (Modbus/TCP write, EtherCAT/CAN via PMOD, GPIO).
- Every proposal, verdict and the model's exact token IDs are sealed. Because the decoder is bit-exact, a disputed action can be **replayed identically** offline.

**Upgrade magnitude.**
- (i) **Capability:** enforcement survives full root compromise of the A53/LLM side. Software guardrails: 0% survival by construction. This is a qualitative capability others do not offer on commodity robot compute (Jetson has no isolated programmable logic in the actuator path).
- (ii) Gate latency of µs (PL) vs ms for software validators [U, to measure].
- (iii) Auditability: bit-exact replay of the proposal vs non-reproducible GPU outputs. Corrections.md notes llama-server is not bit-exact under caching.

**Asset reuse.** Very high. This is the v2 typed-output / R5 ownership / deadline / quarantine / formal-proof work, plus the decoder (the untrusted proposer that emits JSON tool calls), plus the weight-integrity seals, plus the raw-Ethernet path. Very little new hardware is needed.

**First experiment (3–5 weeks).**
- Setup: a Modbus/TCP-controlled plant simulator (or a small physical rig: pump/servo via PMOD) with the decoder or an external LLM issuing JSON tool calls.
- Threat model: (1) a benign LLM making errors (Schall-style unsafe proposals); (2) prompt-injected LLM; (3) **root on A53** writing directly to the bus and to the R5 shared memory.
- Metrics: unsafe actuations reaching the plant (target 0 for all three, vs software-validator baseline failing case 3 at 100%); gate added latency and jitter; false-block rate on safe commands; deadline-miss behavior; replay identity of 100% of disputed actions.
- Tie-in: map the evidence to IEC 61508-style safety-function arguments and IEC 62443-4-2 zone/conduit requirements in an assurance case. Do not claim certification.

**Datasets/benchmarks.** No standard one exists, which is itself a contribution. Possible sources: RoboGuard's unsafe-plan scenarios; Schall's 50-run OT scenario set (check availability [U]); BFCL-style tool calls with an envelope-violation injection set; the PLC enforcement paper's water-tank/valve case studies.

**Venues.** SAFECOMP, DSN (Industry/DSN-W), EMSOFT/ESWEEK, ICCPS, RV (Runtime Verification), IEEE TII. Security angle: CPS-SPC, ACSAC.

**Risks.** Reviewers may call it "just a firewall with a schema". The defense is to show the R5/PL isolation property, either formally or with fault injection, plus the replay property, against a stated threat model. Lanotte et al. must be cited and differentiated. Expressiveness of envelopes: start with box/rate constraints and plant-state-dependent interlocks read from the bus.

---

## (c) High-rate sensor condition monitoring and fault protection

**Demand/physics.** Partial discharge: pulses need 100s of MS/s (patent: 250 MS/s, 8-bit, FPGA-controlled acquisition with an MLP trigger) [V] [USPTO 10408873](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10408873). SiC short-circuit protection needs sub-µs response; FPGA-assisted DESAT detects in **72–240 ns** without ML [V] [IEICE ELEX 2021](https://www.jstage.jst.go.jp/article/elex/18/21/18_18.20210345/_article). Acoustic emission crack detection in L-PBF additive manufacturing uses high-frequency AE plus ML; no FPGA deployment found [V] [TU Dresden](https://fis.tu-dresden.de/portal/en/publications/an-in-situ-crack-detection-approach-in-additive-manufacturing-based-on-acoustic-emission-and-machine-learning(89a5ccf0-ff95-4117-ad88-6e44177a581f).html).

**Existing FPGA ML numbers.** Bearing 1D-CNN accelerator at 64 kS/s current, 0.28 s response [V] [Sensors 2023](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10346166/). Binary 1D-CNN 0.42 ms [V]. BearingPGA-Net 2.83K params, >200x vs CPU on Kintex [V] [arXiv 2307.16363](https://arxiv.org/pdf/2307.16363). FPGA MLP/DRL motor controllers at standard control rates [V] [Ohm](https://opus4.kobv.de/opus4-ohm/frontdoor/index/index/year/2024/docId/1673), [arXiv 2603.07964](https://arxiv.org/pdf/2603.07964).

**Gap.** Transformer/encoder models over raw MHz waveforms, in-loop, with calibrated abstention ("not sure → conservative trip/alarm"), are not found on FPGA [U, absence]. These are real FPGA-shaped problems.

**Asset reuse.** Low to medium. Our encoder is text/token-shaped. We would need an ADC front end (KR260 has no fast ADC; it would need a PMOD/FMC-less add-on, and the KR260 has no FMC, which is a real blocker for >100 MS/s [U]). The abstention and calibration machinery transfers. Hardware fit is better on RFSoC/Versal or boards with FMC.

**Verdict.** Valuable field, wrong board and wrong assets. Optional: an offline "abstaining PD classifier" study on public PD data. Not a primary direction.

---

## (d) Deterministic real-time language/command interfaces on machines

**Evidence.** LLM+ROS 2 voice/text command papers are simulation-only and report relative latency gains (−7%) with no requirement threshold [V] [arXiv 2506.00075](https://arxiv.org/pdf/2506.00075). I found no standard or industry survey stating a bounded-latency requirement for spoken/typed machine commands. Operators use HMIs, e-stops and teach pendants, and ISO 10218 / ISO/TS 15066 cover physical safety, not language [U, not searched in depth].

**Verdict.** Weak demand. The v1 CLINC-style µs intent classifier's latency advantage is irrelevant at human timescales (100s of ms). The only defensible version is (b): the language interface is the *untrusted* front end of a gated actuator path. Do not pursue on its own.

---

## (e) TSN-integrated ML and ROS 2 hardware acceleration on Kria

**Evidence.** RobotCore (ROS 2 HW acceleration architecture, KV260 case study) [V] [arXiv 2205.03929](https://arxiv.org/pdf/2205.03929). AMD's ROS 2 Perception Node app on KR260, and its TSN app for ROS 2 multi-node communication (two TSN ports without an external switch) [V] [AMD](https://www.amd.com/en/developer/resources/kria-apps/ros-2-perception-node.html). AMD's 2022 claims (latency "≤1/3" vs Jetson, 4.7x productivity) are vendor figures [V/U]. Survey of KR260 robotics acceleration [V] [TCI](https://ph02.tci-thaijo.org/index.php/ET/article/view/247799). In-network ML: FENIX (NSDI'26, switch ASIC features plus FPGA DNN, µs) [V] [arXiv 2507.14891](https://arxiv.org/pdf/2507.14891). ML anomaly detection for SOME/IP at line rate on ZCU102 PL (TUM) [V] [TUM](https://www.ce.cit.tum.de/lis/forschung/aktuelle-projekte/emdrive/). **No TSN-specific in-switch/in-endpoint ML found** [V].

**Gap.** "TSN-scheduled actuation gate". The B1 gate releases verified commands in a 802.1Qbv time slot, so verification latency is hidden inside the schedule and freshness is tied to the TSN time base. This is novel as an integration [U]. As a stand-alone ROS 2 acceleration paper it is crowded and vendor-led.

**Verdict.** Use it as the deployment vehicle for B1/B2 (ROS 2 node proposes, PL/R5 gate releases on the TSN port). Do not make it the headline.

---

## (f) The in-fabric LLM decoder itself

**Facts against a standalone justification.** Decode is about 6 tok/s, at parity with llama.cpp on the same board's A53 (5.78 tok/s Q8) [project data]. TeLLMe v2 gets 25 tok/s at about 5 W on the same K26 [project data]. Orin-class devices are far faster.

**Possible justifications checked**
- *Longevity / supply chain:* the K26 industrial grade has a **10-year minimum production availability**, −40 to 100 °C, and K24 is pin-compatible [V launch-era] [AMD K26I](https://www.amd.com/en/products/system-on-modules/kria/k26/k26i-industrial.html), [DigiKey](https://emedia.digikey.com/eMagazine-Vol-18-EdgeAI/34-35). This argues for the *board*, not for putting the LLM in the fabric rather than on the A53.
- *Rad-tolerance/space:* LLMs in orbit are mostly simulation or COTS demos; "sustained LLM inference requires rad-hard hardware" [V] [arXiv 2605.05615](https://arxiv.org/html/2605.05615). Boeing COTS LLM demo [U secondary]. ESA FPG-AI targets CNNs on rad-hard NanoXplore FPGAs [V] [ESA](https://activities.esa.int/node/820). No evidence of a market for an LLM on a rad-tolerant FPGA. Speculative.
- *Certification:* the EASA AI Level 1/2 concept paper plus DO-254 for FPGA (the Daedalean/Avidyne precedent puts the NN in an FPGA under DO-254) [V] [futuretransport-news](https://futuretransport-news.com/ensuring-safety-and-certification-of-our-products). A deterministic, bit-exact FPGA datapath fits hardware assurance better than GPU kernels. But no aviation use needs a generative LLM in the loop [U].
- *Determinism/replay:* this is the real, defensible property, but DetLLM (NeurIPS 2026) gives bit-identical Qwen3-0.6B on GPUs (see corrections.md). Use determinism as an enabler of auditability inside B1, not as a headline.

**Verdict.** Keep the decoder as the **untrusted, replayable proposer** in B1. That is the only setting found where an in-fabric LLM adds something: the decoder's arithmetic is not on the compromisable Linux CPU's timing/numerics path, and every proposal replays exactly. Even this is a secondary benefit. The gate is the contribution.

---

## Ranking against the four criteria

| Niche | (1) Zynq structurally right | (2) Documented demand | (3) Asset head start | (4) ≥5–10x or unique | Overall |
|---|---|---|---|---|---|
| **B1 AI-to-actuator hardware gate (PL+R5), decoder as proposer** | Yes (PL/R5 isolation, GbE, TSN) | Strong (CISA 2025, Schall 2026, RoboGuard, TS 22440 draft) | Very high | Unique: survives A53/LLM compromise; replayable | **1** |
| **B2 Inline semantic OT inspector (Modbus/GOOSE) with abstention + hard blocking** | Yes (2-port inline, µs, deterministic) | Strong (FrostyGoop, CIGRE 2026 inline FPGA IPS, 3 ms GOOSE) | High | 100–1000x vs software ML IDS; capability vs LUT NIDS | **2** (and composable with B1: same box) |
| (e) TSN-scheduled gate / ROS 2 | Yes | Medium (vendor) | Medium | Integration novelty | Vehicle for B1 |
| (c) MHz condition monitoring / PD / SiC | Partly (no fast ADC/FMC on KR260) | Real | Low | Possibly | 4 |
| (f) In-fabric LLM standalone | Weak | Weak/speculative | High | No (parity with A53) | Do not pursue on its own |
| (d) Language command interface | No (human timescale) | Not found | High | No | Drop |

**Suggested composite thesis:** "A $350 SoC that sits between AI and the plant". B2 inspects inbound and outbound OT traffic. B1 gates every AI-proposed actuation in hardware the AI cannot reach. Both use calibrated abstention and bit-exact replay. Two papers: B1 at SAFECOMP/DSN-W/EMSOFT, B2 at CPS-SPC/SmartGridComm/FPT. They share the inline Ethernet datapath, the R5 policy core and the evidence-seal format already in the repo.

## Open checks (not done here)
- Full text of SRIM (CIGRE D2_10116_2026): does it use ML, and does it block on semantics? It could pre-empt part of B2.
- Lanotte et al. follow-ups (2022–2026) on FPGA runtime enforcement: has anyone applied it to AI-generated commands?
- Availability of Schall 2026's scenario set; RoboGuard benchmark license.
- Actual Tofino/EAGLE DPI added latency (ETFA 2014 full text) for the B2 baseline table.
- Whether KR260 PL GbE paths can do a cut-through 2-port bridge without the A53 (needs a design check in the repo, not done per instructions).
