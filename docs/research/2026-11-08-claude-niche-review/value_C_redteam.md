# Value red team C: trying to kill B1, B2, T1, T2/T4 and the hybrid H (2026-11-08)

I did not open the repository. Inputs were value_context.md, value_A_landscape.md, value_B_applications.md, discussion_round2.md (T1–T8) and corrections.md, plus about 25 web searches and fetches in this session.

How the facts are labelled:
- **[V]**: I read it on a fetched page or abstract.
- **[S]**: it comes from a search-result summary only.
- **[U]**: unverified, or my own inference.

The board facts used throughout:
- The fabric decoder is at decode parity with the KR260's own A53 cores (about 170 ms per token on both).
- An Orin Nano decodes about 13x faster.
- Fabric prefill is 2–4.5x faster than the A53.

---

## 0. Verdict first

1. **Every latency argument is weaker than earlier rounds claimed.** The physical processes the KR260 would guard all have millisecond budgets:
   - PLC scan times are 1–100 ms [U].
   - Drive Safe Torque Off (STO) responds in 2 ms typical and 5–30 ms maximum [S] ([ABB ACQ580](https://www.manualslib.com/manual/1658679/Abb-Acq580-34.html?page=149); [Kollmorgen AKD2G](https://webhelp.kollmorgen.com/AKD2G/English/Content/AKD2G-S%20Install/e/fsm/fs1/AKD2S_install_21_04_00_STO.htm)).
   - A GOOSE trip has a 3 ms budget, of which about 600 µs is allotted to the network (value_B).

   A µs gate in front of a 10 ms actuator chain buys nothing measurable. The one place where latency can matter is inline inspection of GOOSE/SV traffic (B2), and even there only the latency *tail* matters, not the median.
2. **Incumbents already provide "independence from the AI host".** Several kinds of device sit apart from whatever runs the AI, and some are certified:
   - safety PLCs and safety instrumented systems (SIS);
   - robot safety controllers: ABB SafeMove2 is PL d cat. 3 and computes position "independently from the robot controller" [S] ([ABB SafeMove2](https://ingenieria.uncuyo.edu.ar/catedras/abb-safemove2-overview-external-2017.pdf)); FANUC DCS removes motor power when position or speed limits are exceeded [S] ([FANUC DCS](https://www.fanucamerica.com/products/software/fanuc-dual-check-safety-dcs));
   - STO drives;
   - OT deep-packet-inspection (DPI) firewalls;
   - data diodes.

   NVIDIA now ships AI compute and an isolated, SIL 3-capable safety island in one product. IGX Thor's Functional Safety Island has its own I/O, power and clocks and is "physically isolated from the main compute domain". TÜV Rheinland certification readiness work started in June 2026, targeting IEC 61508 SIL 2 / ISO 13849 PL d [S] ([NVIDIA Halos blog](https://developer.nvidia.com/blog/inside-nvidia-halos-for-robotics-a-full-stack-functional-safety-system-for-physical-ai/); [TÜV Rheinland](https://www.tuv.com/press/en/press-releases/tuv-rheinland-supports-nvidia-halos-for-robotics.html)). IGX Orin pairs its safety island with an Infineon AURIX TC397 safety MCU [S] ([NVIDIA IGX Orin safety MCU](https://docs.nvidia.com/igx-orin/product-specification/latest/safety-mcu.html)). **"An AI SoC with a hardware-isolated safety island" is therefore not unique to Zynq.** NVIDIA's version is further along on certification. The KR260 is not SIL-certified.
3. **A second cheap device kills the "survives root compromise" headline.** Any separate box running a validator also survives compromise of the AI host: a Pi, an MCU, an Xage gateway or a Tofino. What the KR260 adds over a $10–80 second device is narrower:
   - **(a)** a small, formally verifiable trusted computing base (TCB): RTL plus bare-metal R5, with no OS;
   - **(b)** line-rate parsing and enforcement in the PL beside TSN ports;
   - **(c)** bit-exact replay of the AI's proposal, but only when the proposer is the fabric decoder;
   - **(d)** one board with a 10-year industrial supply life.

   These are assurance and integration properties. They are real but not ≥10x, except (a) measured as TCB size.
4. **T1 dies** as a hardware contribution. **T4 loses its rationale inside B1**: authenticating the weights of a proposer that is untrusted by design adds little. T4 survives only if retargeted to the model that holds *blocking authority* (B2 or H).

---

## 1. B1: AI-to-actuator hardware gate

### 1.1 What practitioners use today, and how well it works

The defenses are layered.

| Layer | Incumbent | What it enforces | Strength vs an AI proposer | Evidence |
|---|---|---|---|---|
| Safety function | SIS, safety PLC (SIL 2/3), safety relays | Trips on process limits, independently of the control system | Very strong for the hazards it was designed for. Any AI write still passes through it. | IEC 61508/61511 practice [U] |
| Drive | STO (SIL 3 / PL e typical) | Removes torque | Strong; 2–30 ms response | ABB, Kollmorgen manuals [S] (links above) |
| Robot | ABB SafeMove2, FANUC DCS | Safe speed, zones, standstill on a separate safety computer | Strong for motion envelopes. Indifferent to *who* commanded the motion. | [S] (links above) |
| AI compute with a safety island | NVIDIA IGX Orin/Thor FSI + sMCU, Halos | Independent safety processor, own I/O | Strong, and on a certification path | [S] (links above) |
| Wireless/mode safety for autonomous machines | FORT Robotics Vehicle Safety Controller / Oversight, claimed SIL 3 | E-stop, mode select | Coarse but certified | [S] ([BusinessWire 2020](https://www.businesswire.com/news/home/20200304005153/en); profile [U]) |
| BPCS | PLC-side setpoint clamps, interlocks, rate limits in ladder/ST | Plant logic | Strong if the PLC program itself is protected | [U] standard practice |
| Network | OT DPI firewalls: Tofino/EAGLE (function code, unit ID, **register/coil range per connection**, Modbus sanity check); EAGLE40 (Modbus, GOOSE DPI); FortiGate OT signatures | Per-packet static allow-lists | Blocks off-range writes, but *in-range unsafe* writes pass. Throughput is modest: the vendor page cites about 1,000 packets/s with full content inspection [S]. | [S] ([Belden Tofino Modbus LSM](https://www.belden.com/products/industrial-networking-cybersecurity/cybersecurity/firewalls/tofino-xenon-modbustcp-lsm)); EAGLE40 [S] ([networking-book](https://networking-book.pages.dev/ch19/eagle40/)); [Fortinet tip](https://community.fortinet.com/t5/FortiGate/Technical-Tip-Application-Control-signatures-belonging-to/ta-p/190157) [S] |
| Identity and policy for AI agents | Xage "Zero Trust for AI": per-agent identity and protocol-layer policy for MCP/agent traffic. Behavioural flagging when a read-only agent starts writing. | Who may do what | Detection plus coarse authorization; no plant-state semantics found | [S] ([SiliconANGLE May 2026](https://siliconangle.com/2026/05/27/xage-extends-zero-trust-autonomous-ai-agents-across-cloud-saas-edge/); [Xage CISA whitepaper](https://info.xage.com/hubfs/Whitepapers_Guides_ebooks_Use%20Cases/Xage-WP-Operationalizing%20CISAs%20AI-in-OT%20Principles.pdf)) |
| Topology | Unidirectional gateways. Waterfall uses a second one-way link, or a reversible FLIP, for remote setpoints. | Direction of flow | Strongest isolation. Setpoint paths need an explicit second channel. | [S] ([ARC on Waterfall](https://www.arcweb.com/blog/unidirectional-security-gateways-reduce-risk-industrial-cyber-attacks)) |
| Software AI guardrails | RoboGuard, SafeGate, Schall's deterministic verifier, pre-execution validators (arXiv 2606.28011) | Plan/action checks | Good coverage in papers, but in the same trust domain as the planner | value_B [V]; [arXiv 2606.28011](https://arxiv.org/pdf/2606.28011) [S] |

Standards and guidance:
- **CISA/NSA, December 2025.** "Limit active control of OT infrastructure by AI without a human in the loop." Where AI updates control logic, use "safety thresholds … human-in-the-loop intervention points" and "failsafe mechanisms that revert to traditional automation or manual control" [S] ([CISA PDF](https://www.cisa.gov/sites/default/files/2025-12/joint-guidance-principles-for-the-secure-integration-of-artificial-intelligence-in-operational-technology-508c.pdf); my direct fetch of the PDF timed out).
- **ISO/IEC TR 5469:2024** names "supervisory controls" (boundary systems constraining AI outputs) and non-AI backup functions as the architectures [S] ([A3 on TS 22440](https://automate.org/news/ai-and-functional-safety-understanding-iso-iec-ts-22440)).
- **TS 22440** Parts 1 and 3 explicitly cover "non-AI technology that ensures the safety of a system using AI" [S].

**The demand is real, but the pattern being standardised is already "a non-AI supervisor in certified hardware".**

Attack evidence:
- **PLCBench** (arXiv 2608.26882): 240 real-PLC episodes; LLM agents sustained physical objectives in **31.3%** of them. After a process-linked write, richer observation raised attainment from 44.2% to 64.0% [V] ([arXiv 2608.26882](https://arxiv.org/abs/2608.26882)).
- **Schall 2026**: LLMs proposed unsafe actions in 10–70% of runs (value_B [V]).

### 1.2 Kill attempts

- **K1. "Safety envelope" is the wrong word.** The safety envelope already belongs to SIS, safety controllers and STO. A non-certified KR260 cannot take that role, and claiming it will draw reviewer fire. *Survives only if* B1 is reframed as a **security/operational conduit**: IEC 62443 zone/conduit at SL 3–4, operating *above* the SIS, never replacing it.
- **K2. Latency.** Downstream chains run at ms scale, so a µs PL gate brings no benefit. **Killed as a claim.**
- **K3. Isolation.** Any separate device survives compromise of the AI host. Tofino plus PLC clamps already enforce register ranges outside the AI host. **The headline "software guardrails 0% vs us 100%" is a straw man.** The fair baselines are a separate validator box and a static DPI allow-list.
- **K4. Single-box AI plus safety island.** IGX Thor does it and is on a certification path. A KR260+Orin pair costs about $600 against IGX's several thousand [U], so a cost niche exists. It is not a capability gap.
- **K5. Policy demand.** CISA says to keep humans in the loop. Fully autonomous AI writes are discouraged, which shrinks the "agent writes to plant" market.

### 1.3 What survives (sharpened B1)

The gap no incumbent covers is **semantic, stateful, plant-state-conditioned policy for in-range writes, with hardware-bound human approval and replay, in a minimal TCB**. It has five elements:

1. **Policy over sequences, not packets.** Rate-of-change limits, cross-register interlocks conditioned on live values read off the bus, per-plan write budgets, and freshness tied to deadlines and epochs. Tofino-class firewalls check function codes and ranges per packet [S]. Xage scopes identity and flags anomalies [S]. Neither checks "in-range but unsafe given the current tank level" [U: I found no product that does].
2. **Hardware-bound human-in-the-loop.** The AI proposal is hashed. The operator approves on a separate channel (an HMI key or button on the PMOD). The PL/R5 releases *only* the byte-identical approved command, inside its deadline. This turns CISA's "HITL intervention points" into an enforced protocol rather than a UI convention. It is the strongest demand link found.
3. **A minimal, formally verified TCB.** RTL plus bare-metal R5, with the existing formal proofs, against a Linux plus validator stack whose TCB is ~10^7 lines [U]. Measured as TCB size this is a ≥1,000x difference. It is the only ≥10x quantity B1 has.
4. **A replayable audit log.** Every proposal, verdict and approval is sealed. If the proposer is the fabric decoder, a disputed proposal can be re-derived bit-exactly. That is a secondary benefit: DetLLM shows bit-exact replay is achievable on GPUs too (corrections.md).
5. **Honesty clause.** The *policy* may be the contribution and the KR260 just a host. The falsifier below tests exactly this.

**Most convincing upgrade claim (B1).** On PLCBench-style and Schall-style episodes, a static allow-list (Tofino-equivalent function code, register and value ranges) blocks only ≤X% of physically unsafe write sequences. The stateful gate blocks ≥95% at ≤1% false blocks on benign operator traces. It also blocks 100% under root on the AI host, with a TCB ≥1,000x smaller than a Linux-hosted validator.

**First falsifying experiment (2–3 weeks, mostly software).**
- Replay PLCBench's released software-only pipeline, or a Modbus water-tank plant, under three conditions: (i) no filter; (ii) a static allow-list; (iii) the stateful policy.
- Use the same hold-out benign traces for all three.
- **Kill B1 as a paper** if (iii) beats (ii) by <10 percentage points of unsafe-episode blocking at equal false-block rate. The semantic policy then adds nothing over a Tofino.
- **Kill the KR260-specific part** if a bare-metal STM32/RP2040 implementation of (iii) matches it on latency and coverage. Then the value is the policy, and the paper must be framed as a policy/assurance paper, with the KR260 used only for the TSN or replay angle.

**Closest academic work.**
- Lanotte et al., FPGA runtime enforcement of PLCs (CSF 2020; arXiv 2105.10668; journal 2022). It is a secure proxy against compromised PLCs, not against AI proposers. It has no HITL binding and no replay. I found no 2023–2026 follow-up [S] ([arXiv 2105.10668](https://arxiv.org/abs/2105.10668)).
- Software validators: Schall 2026; arXiv 2606.28011; RoboGuard.
- Dual-RK3588 LLM safety agent aiming at Cat. 3 / PL d (arXiv 2604.20193): redundant SoCs, no FPGA, no latency numbers [V abstract] ([arXiv 2604.20193](https://arxiv.org/abs/2604.20193)).
- The BRIK-64 "policy circuit" blog is marketing only [S].

**Novelty is moderate.** It rests on the combination of AI-proposer threat model, HITL binding, stateful plant-conditioned policy, formal proof and replay. None of these alone is new.

---

## 2. B2: inline stateful semantic OT inspector

### 2.1 Incumbents

- **Inline allow-list DPI:**
  - Tofino/EAGLE20 for Modbus function codes and register ranges [S].
  - EAGLE40 with GOOSE/Modbus DPI [S].
- **SDN deny-by-default flow allow-listing for substations:** SEL-2740S. It inspects every layer against configured flows and recovers from failures in under 100 µs. Note that it is under a **last-time buy, with orders closing 30 Nov 2026** (successors SEL-2731/2741) [S] ([SEL-2740S](https://selinc.com/products/2740S/)).
- **GOOSE/SV authentication (IEC 62351-6) in FPGA:** SoC-e's core ciphers, signs and authenticates in under 7 µs [S] ([PACW](https://www.pacw.org/?p=4314); [Design-Reuse](https://design-reuse.com/news/43520/soc-e-iec-61850-62351-ip-core.html)). This removes the spoofing class of attacks that most GOOSE ML papers target.
- **Passive IDS (the dominant practice):**
  - Commercial sensors: Nozomi, Claroty, Dragos.
  - Zeek's built-in Modbus/DNP3 parsers, extended by CISA ICSNPP (S7comm, BACnet, PROFINET IO CM, C37.118, ENIP/CIP, EtherCAT, OPC UA). **ICSNPP has no GOOSE parser** [S] ([cisagov/ICSNPP](https://github.com/cisagov/ICSNPP)).
  - Suricata has Modbus/DNP3/ENIP parsers [U].
  - OT practice prefers IDS over IPS because inline drops threaten availability [S] ([OT IDS/IPS course notes](https://mniedermaier.github.io/OTsecNotes/520-ids-ips-ot.pdf)). I did not find this stated in NIST 800-82r3 itself.
- **Research prototypes:**
  - NetFPGA IEC 61850 firewall: +77 µs per 1,518-byte frame; it blocked forged GOOSE [S] ([USP thesis](https://teses.usp.br/teses/disponiveis/18/18154/tde-11112016-090545/en.php)).
  - KC705 hardware firewall: 627 ns, 0.98 Gb/s [S].
  - Software GOOSE ML: 1.1 ms. vBump: about 1 ms (value_B).
  - CIGRE 2026 SRIM describes an inline FPGA DPI IPS (full text unseen).

**Traffic volume is small.** One 9-2LE SV stream is about 4.8–5.3 Mbps [S] ([OPAL-RT](https://opal-rt.atlassian.net/wiki/spaces/PDOCHS/pages/149817818/IEC+61850+legacy+Supported+Features+and+Limitations)), and Modbus traffic is smaller still. **CPUs are not throughput-limited here.**

### 2.2 Kill attempts

- **K1. Operators will not let an ML verdict drop trip traffic.** A false positive on GOOSE means a protection failure. **This kills "ML hard-blocking GOOSE".**
- **K2. Static methods already cover most of the space.** Deny-by-default (SEL SDN, Tofino) plus 62351-6 authentication cover spoofing, injection and off-list flows. ML can only add *protocol-valid, authenticated, semantically wrong* messages, such as FrostyGoop-style writes or a compromised IED sending a valid but wrong GOOSE.
- **K3. The 100–1000x latency claim (value_B) compares against Python or vBump-class software.** A tuned DPDK or XDP CPU path probably adds tens of µs at the median [U, to measure]. The honest FPGA advantage lies in the **worst-case tail and jitter under load and attack**, plausibly ≥10x at p99.99 [U]. The median gain is closer to 2–5x.
- **K4. Detection quality doesn't need an FPGA.** Novelty from "first FPGA Modbus DL detector" is real but thin if a CPU suffices.

### 2.3 What survives (sharpened B2)

**A bounded-latency inline conduit for write-type and control-type traffic.** Deterministic rules hard-block. The ML model only *holds or escalates* a narrow class of messages (setpoint writes, breaker-control GOOSE status changes), with calibrated abstention. Everything else is mirrored to a passive IDS. Its value is a guaranteed worst-case added latency, independent of attack load. A CPU IPS cannot guarantee that.

**Most convincing upgrade claim (B2).** At 1 GbE line rate with an attack flood, the KR260 adds ≤10 µs worst-case latency (p100 over ≥10^9 frames) with zero GOOSE 600 µs budget violations. Suricata or nfqueue IPS on the same A53, and on an x86 N100, shows p99.99 above 600 µs under the same load. Measured as tail latency, that is a ≥50x gap [U, the hypothesis to test].

**First falsifying experiment (2 weeks).**
- Run Suricata IPS (and/or a DPDK filter) with Modbus/DNP3 allow-list rules on the A53 and on a ~$150 x86 mini-PC.
- Replay ERENO GOOSE traffic plus a Modbus flood at line rate, using hardware timestamps from a TSN port or tap.
- **Kill the hardware case** if the x86 p99.99 added latency is under 100 µs. Then B2 is a software semantic-IDS paper and the KR260 contributes nothing essential.
- In parallel, measure the semantic gain: the fraction of protocol-valid attacks (ProvICS, FrostyGoop-like) caught by the model but missed by the allow-list. **Kill the ML part** if the gain is under 10 percentage points.

---

## 3. T1: exact grammar-aware decoding on the fabric LLM

**Incumbent.** XGrammar or llguidance on CPU: about 40–50 µs per token of mask cost [S] ([XGrammar](https://arxiv.org/pdf/2411.15100); [llguidance](https://www.gitlink.org.cn/dnrops/llguidance)). llama.cpp GBNF also works on the A53.

**Kill.**
- Forcing and restricted-head tricks are *algorithmic*. A restricted LM head saves the same ~165 MB per token on the A53 as on the fabric.
- The projected 1.5–2.3x speedup therefore applies equally to llama.cpp on the A53 (and on an Orin). The relative position does not change: fabric ≈ A53, and Orin ≈ 13x faster.
- Mask cost is negligible against 170 ms per token.
- Academic novelty reduces to "first FPGA port of XGrammar-style decoding", which reviewers will discount.

**Rescue.** The only defensible remnant is the *exactness* result: forced or batched paths produce token streams bit-identical to sequential masked greedy. That result supports B1's replay of the proposer. **T1 is dead as a flagship**; keep it as one section of B1 or C.

**Falsifier, if anyone insists.** Implement the restricted head and forcing in llama.cpp on the A53. If the A53 gains at least 80% of the fabric's speedup, T1 has no hardware story. This is the expected outcome.

---

## 4. T2/T4: fault attribution and inline weight authentication

**Incumbents:**
- ECC DRAM. Whether the K26 SOM DDR4 has ECC enabled is unconfirmed [U]; check it before any DDR-flip study.
- Startup hashing and secure boot (Zynq CSU) [U].
- SILK, an Ascon-PRF streaming checker at about 0.7 GB/s (corrections.md).
- GPU SDC studies, which separate faults from nondeterminism statistically.

**Kill:**
- Inside B1, the LLM is untrusted by design. A root attacker who can flip weights can simply write proposals directly, and the gate must stop both. **T4's marginal value for the proposer is about zero.**
- T2's "TOCTOU: startup SHA misses post-load tampering" is true but obvious.

**Survives, retargeted:**
- **T4** pays off only for a model holding *blocking authority* whose weights stream from DDR: the B2/H encoder (MiniLM-class, ~22 MB INT8 [U], too large for the ~2.9 MB of on-chip RAM). Models that fit on chip need only startup authentication.
  - **Claim:** in-stream authentication at ≥3.5 GB/s, 4.6–5.2x SILK, with 0% slowdown.
  - **Falsifier:** SILK's full text already has a GB/s or DSP variant, or the gate model fits on chip.
- **T2** survives as a dependability workshop paper: exact-golden attribution of faults in the *inspector's or gate's* model, measuring silent wrong-verdict rates with and without the R5 checks.
  - It is marginal in value: a new methodology, not a ≥10x upgrade.
  - **Falsifier:** if ≥99% of flips are masked, the study is too weak to publish.

---

## 5. Hybrid H: the KR260 as "System One" front end with an external LLM

**Incumbents:**
- Orin or IGX alone: GPU LLM plus a small classifier on the same GPU in ms, plus the safety island [S].
- Orin plus a safety PLC plus an OT firewall (the common brownfield answer) [U].

**Kill attempts:**
- Gating "what reaches the LLM" has no latency value. The LLM itself takes hundreds of ms or more, so routing a request in 13 µs instead of 2 ms on the Orin is invisible.
- The "what reaches actuators" half is just B1, and the in-line traffic half is B2.

**Survives as framing, not as a separate claim.** Cognition goes on cheap NPUs and GPUs. I/O authority sits in a small, formally verified, long-lived PL/R5 box:
- UltraScale+ supply is promised to 2045 [S]; K26I production availability is 10 years [S].

This is the honest system story and positions the board correctly against value_A. Cost: KR260 plus Orin Nano is about $600, against IGX Thor's several-thousand-dollar class [U].

**Upgrade claim.** It does the same gating job as IGX-class hardware at ≤1/5 the cost, with an open, inspectable RTL TCB. It is not certified, which is the stated trade-off.

**Falsifier.** If the identical policy runs on the Orin plus a $10 MCU with the same coverage and with tail latency inside the plant budget, H reduces to cost alone.

---

## 6. Final ranked list of survivors

| Rank | Survivor (sharpened) | Single most convincing quantitative claim | Substantial? | First falsifying experiment |
|---|---|---|---|---|
| **1** | **B1′: agent command conduit.** Stateful, plant-conditioned policy for in-range writes, plus hardware-bound HITL approval (byte-identical release within a deadline), plus a sealed replay log. Runs in an RTL + bare-metal R5 TCB. It is a *security* conduit above the SIS, never a safety function. | Blocks ≥95% of PLCBench/Schall-style unsafe in-range write sequences that a Tofino-equivalent static allow-list passes, at ≤1% false blocks. Holds at 100% under AI-host root. TCB ≥1,000x smaller than a Linux-hosted validator. | Capability gain vs static DPI; the TCB-size ratio is the ≥10x quantity. **Not** latency. | Static allow-list vs stateful policy on PLCBench's software pipeline or a Modbus tank plant. Kill if the gain is under 10 pp. Port the policy to bare-metal STM32: if it is equivalent, re-frame as a policy paper. |
| **2** | **B2′: bounded-latency inline conduit for control traffic.** Rules hard-block. ML only holds or escalates setpoint writes and status-changing GOOSE, with calibrated abstention. All else is mirrored to a passive IDS. | ≤10 µs worst-case added latency at 1 GbE under attack load, against software IPS p99.99 above 600 µs (≥50x in tail) [hypothesis]. | Substantial only if the CPU tail really breaks the 600 µs budget. | Suricata/DPDK IPS on the A53 and an x86 N100, with hardware timestamps. Kill the hardware case if x86 p99.99 is under 100 µs. Kill the ML part if it adds under 10 pp over the allow-list on protocol-valid attacks. |
| 3 | **H: KR260 as the I/O-authority box beside a cheap LLM device.** Framing for papers 1–2, not a separate paper. | Same gating role as IGX-class hardware at ≤1/5 the cost, with open RTL and supply to 2045. | Cost and assurance only. | The Orin + MCU baseline from rank 1. |
| 4 | **T4′: in-stream weight authentication for the model with blocking authority** (the B2/H encoder streamed from DDR). | ≥3.5 GB/s authenticated streaming (4.6–5.2x SILK) at 0% slowdown, ≤2k LUTs. | ~5x over SILK; borderline. | Read SILK's full text; check whether the gate model fits on chip; check timing closure with CLB at 92–96%. |
| 5 | **T2′: exact-golden fault attribution of the gate's or inspector's model.** | Fully attributed outcome taxonomy, with silent wrong-verdict bounds with and without R5 checks. | Methodological, marginal. | 550-flip pilot. Kill if ≥99% masked or no difference with and without the gate. First confirm whether ECC is present. |
| — | **T1: grammar decoding on the fabric LLM.** **Killed** as a contribution; keep the exactness proof as a section of B1′ replay. | (The 1.5–2.3x applies equally to the A53.) | No | Same tricks in llama.cpp on the A53: if it gets ≥80% of the gain, T1 is confirmed dead. |

**One-sentence positioning after the red team:**
> The KR260's defensible value is not speed but *authority with a tiny, provable TCB*. It is the box that decides which AI-proposed writes and which control frames reach the plant, with bounded worst-case latency and replayable evidence. It must beat a static OT allow-list on semantics and a CPU IPS on tail latency, or it has no hardware story.

## Open checks
- CISA PDF exact wording: my direct fetch timed out; the wording above comes from search summaries.
- SRIM CIGRE 2026 full text: does it already do ML or semantic blocking inline?
- Whether IGX Thor or a Jetson Orin safety cluster offers programmable-logic I/O enforcement.
- ECC status of the K26 DDR4.
- Tofino throughput and latency: the "1,000 pps full inspection" figure is from a search summary only.
