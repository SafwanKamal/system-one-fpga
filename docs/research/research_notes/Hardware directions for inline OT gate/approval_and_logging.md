# Hardware-enforced human approval and tamper-evident / replayable logging for an inline OT command gate

Scope note: 7 primary sources were read (6 papers plus 1 slide deck). The table below gives the access level actually obtained for each. Secondary sources found only as search snippets are marked as such and are not counted. Quotes are under 15 words.

| # | Source | Venue/year | Access level actually read |
|---|---|---|---|
| P1 | Shraga, Eshel, Gorelik, "Approved Too Late: Verdict Staleness in LLM-Guarded Self-Adaptive Systems" | arXiv 2608.26306, accepted ACSOS 2026 | Full arXiv HTML text, read through an extraction tool (body, tables, limitations, related work) |
| P2 | Dhar, Ulqinaku, Kostiainen, Capkun, "ProtectIOn: Root-of-Trust for IO in Compromised Platforms" | NDSS 2020 | Full PDF text read end to end, including appendix proof and implementation |
| P3 | Paccagnella et al., "CUSTOS: Practical Tamper-Evident Auditing of Operating Systems Using Trusted Execution" | NDSS 2020 | Full PDF obtained. Read: intro, threat model/goals, logger design, microbenchmarks, discussion, related work, conclusion. Audit-protocol probability analysis skimmed only |
| P4 | Walkup, Etigowni, Xu, Urias, Lin, "Forensic Investigation of Industrial Control Systems Using Deterministic Replay" | IEEE CNS 2020 (Purdue/Sandia) | Full PDF text read (some long lines truncated in extraction; attacker model and limitations re-read in full) |
| P5 | Jin, Valizadeh, van Dijk, "SnapShotter: Lightweight Intrusion Detection and Prevention System for ICS" | ICPS 2018 (CSAW'17 ESC) | **Slide deck only** (full paper PDF not found) plus VU portal abstract |
| P6 | Vance, Kirwan, Bjornn, Jenkins, Anderson, "What Do We Really Know about How Habituation to Warnings Occurs Over Time? A Longitudinal fMRI Study" | CHI 2017 | Full PDF text read (abstract, method, results, discussion, limitations) |
| P7 | Zhou, Roy, Gupta, Weitekamp, MacLellan, "When Should Users Check? Modeling Confirmation Frequency in Multi-Step Agentic AI Tasks" | CHI 2026 (arXiv 2510.05307v4) | First ~100k of 176k characters of the HTML, read through an extraction tool (method, study, results, discussion incl. §8.1.1). Appendix not read |

Not obtained, despite attempts: IntegriKey (ePrint 2017/1245; bot-blocked), Fidelius (S&P 2019), VButton (MobiSys 2018), and Android Protected Confirmation. These are characterised here only through P2's analysis of them.

---

## Q1. Per-paper extraction: mechanism, TCB, threat model, measured results, limitations and future work, applicability to an inline OT gate

### Takeaway
The trusted-path literature (P2 and the systems it dissects) has already shown how to build a low-TCB hardware box. The box sits between a compromised host and the human, signs exactly what the human entered on a trusted overlay, and binds it to a server nonce. P2's own motivating example is a remote PLC. The logging literature (P3–P5) gives hardware/TEE-anchored hash-chain commitment at about 1M events/s, forward-secure PLC logging at 54 µs per scan, and deterministic replay of logged ICS I/O against the PLC program, accurate to 99.7–99.9%. None of these combine approval, a byte-exact release, a deadline, and a sealed, replayable decision record in one inline OT device. The human-factors papers (P6, P7) and P1 explain why naive confirmation fails: habituation, missed errors, and approvals that go stale before use.

### Cited Findings

#### P1 — Approved Too Late (verdict staleness)
- **Mechanism.** The paper frames the gap between guardrail approval and actuation as an Execute-stage TOCTOU hazard in MAPE-K loops. The hazard comes from ordinary plant evolution, not from an attacker. The proposed Freshness-Bounded Shield (FBS) computes a signed safe-side margin m_t = θ − z_t on a scalar feature and keeps an EMA of feature volatility (α = 0.1). From these it derives a validity horizon δ_t = min(δ_max, max(m_t,0)/max(vol_t,ε)). An approval passes only if the judge approved, m_t > 0, and the age K ≤ ⌊δ_t⌋; otherwise a fallback runs. The cost is O(1) scalar work with no model call — [P1](https://arxiv.org/html/2608.26306v1)
- **Freshness contract.** Each approval must be correct at check time and still valid at use time — [P1](https://arxiv.org/html/2608.26306v1)
- **Threat model.** Prompt injection and adversarial state manipulation are explicitly excluded. Grounding age is measured from when the observation was acquired, so it includes all latency before actuation — [P1](https://arxiv.org/html/2608.26306v1)
- **Results.** The all-candidate verdict-change rate at K = 8 ranges from 5.3% (SimDex) to 48.4% (DeltaIoT). Oracle-labelled expiry of approvals with no freshness check is 3.4–24.7%; FBS reduces it to 0–1.8% (82–100% relative reduction, n = 30 paired seeds, Wilcoxon p < 0.001). On DeltaIoT, FBS kept the same reward as no-check (−960). A fixed deadline (e_deadline) also reached 0% expiry but cost reward (−1200). Four LLM judges (qwen2.5:0.5b, llama3.2:1b, Claude Haiku, gpt-4o-mini) showed 11.5–36.8% use-time invalidity — [P1](https://arxiv.org/html/2608.26306v1)
- **Human approvers.** None. The approver is an LLM judge. The paper does not discuss runtime cryptographic or byte-level binding of approval to the action; it says only that an approval should record its checked context and action. The SHA-256 manifest pins experiment artifacts, not runtime actions — [P1](https://arxiv.org/html/2608.26306v1)
- **Limitations.** The authors call FBS "a proof-of-concept heuristic, not a certified safety guarantee." Results are simulation-only (five environments), the volatility estimate is not a worst-case bound, and equal K values are not equal physical durations — [P1](https://arxiv.org/html/2608.26306v1)
- **Future work.** The authors list four items: an end-to-end Judge+FBS run on the same approval stream, calibration against measured deployment latency traces, parameter sensitivity, and matched comparisons with Simplex and model-predictive shielding — [P1](https://arxiv.org/html/2608.26306v1)
- **Related work cited.** Lilienthal & Hong (2025) on TOCTOU in LLM agents, and Jiang et al. (2026) on revalidating browser-agent state before dispatch — [P1](https://arxiv.org/html/2608.26306v1)

#### P2 — ProtectIOn (NDSS 2020)
- **Mechanism.** An external trusted "IOHub" sits between the attacker-controlled host and the keyboard, mouse, and monitor. The server signs a UI specification, which the host renders as a QR code in the HDMI stream. The IOHub verifies the signature, draws the protected form as an overlay the host cannot read or alter, takes input only from the devices attached to it, and signs the (element-id, value) record when the user clicks a trigger element. The host serves only as an untrusted transport. Upstream data travels as emulated keystrokes, downstream as HDMI QR codes — [P2](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24112-paper.pdf)
- **Binding and replay.** The server adds a random form id to each signed specification and rejects any submission whose id does not match. Fields marked protect="true" are refused without the IOHub signature. Integrity therefore covers exact values bound to a fresh server nonce. **There is no deadline or expiry on the approval** — [P2](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24112-paper.pdf)
- **TCB and threat model.** Host OS, applications, host hardware, and network are attacker-controlled. Trusted: the monitor, keyboard, mouse, and IOHub. The attacker cannot break the IOHub's physical security. BadUSB and hardening of the IOHub itself are out of scope. The paper says such hardening "is engineering intensive and out-of-scope" — [P2](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24112-paper.pdf)
- **Attacks on prior work.**
  - IntegriKey signs input but not output. A host can render "10" while the user types "100"; the user then adds a zero, and the device signs "1000".
  - Fidelius ignores the mouse. The OS can click submit mid-entry (an "early form submission"); the paper's Fig. 2 shows this misconfiguring a ControlByWeb X-600M PLC. Fidelius is also open to fake-pointer clickjacking and to label manipulation outside its overlay.
  - Transaction-confirmation devices (ZTIC, Android Protected Confirmation) suffer from habituation, poor usability, and support only simple UIs.
  - [P2](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24112-paper.pdf)
- **Design principles.** Three: input integrity requires output integrity; all input modalities must be protected together; and integrity must not depend on error-prone tasks such as checking security indicators. To enforce these, a lightbox (dimming the rest of the screen) triggers automatically when the pointer enters the overlay. The paper cites Huang et al. for lightbox and freeze effectiveness of 98% and 97% against a 69% baseline. This figure is borrowed from that work, not measured on ProtectIOn — [P2](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24112-paper.pdf)
- **Prototype and results.**
  - Hardware: Raspberry Pi 4, Auvidea B101 HDMI-to-CSI bridge, Arduino Due and Zero; about USD 140.
  - Latency: keyboard 170 µs, mouse 250 µs, effective display latency 21.76 ms (pointer detect 1.76 ms + QR detect 14 ms + decode/overlay 6 ms), maximum 47.69 fps.
  - Pointer-detection accuracy 0.997 over 4196 frames; upstream keystroke channel about 5 ms per 256-byte chunk.
  - Code base: about 121,899 LOC including Tiny Core Linux.
  - **No user study was run.**
  - The authors note the IOHub could be moved onto an FPGA to shrink the TCB further.
  - [P2](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24112-paper.pdf)
- **Limitations and future work.** Side-channel leakage (time spent, pointer entry and exit) is deferred: "We leave as future work defining such policies." Withholding the QR code counts as denial of service. SAS effectiveness is not evaluated — [P2](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24112-paper.pdf)
- **Related work.** P2's Table I lists an FPGA-based trusted display and input system (Brandon & Trimarchi, "Trusted display and input using screen overlays," ReConFig 2017). It is a direct FPGA precedent for a trusted display path, but it was not read here — [P2](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24112-paper.pdf)

#### P3 — CUSTOS (NDSS 2020)
- **Mechanism.** Each log event updates an incremental hash inside an SGX enclave; this is the only per-event cost. The enclave signs the block hash only when an audit challenge arrives ("commitment"), then starts a new block. Startup unseals the key, block ID, and monotonic-counter ID and increments the counter to defeat rollback. Shutdown seals the block ID together with the counter. Auditing is either centralised or a decentralised peer-to-peer protocol with replication — [P3](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24065-paper.pdf)
- **Threat model.** An APT-style attacker eventually gains root and attempts anti-forensics. The goal is tamper-evidence for events logged **before** compromise. The enclave's crypto is assumed side-channel-free. The authors state that post-compromise events cannot be protected by any logging scheme — [P3](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24065-paper.pdf)
- **Results.**
  - Throughput: up to 1,086,956 events/s, against 1,266 events/s for prior SGX-Log on the same hardware.
  - Overhead: 2–7% runtime on intensive workloads (e.g. blast 1.65%), 16.6% on auditd's own log processing, about 3% network.
  - Scale: evaluated on 100 EC2 hosts.
  - TPM comparison: an extend takes 20 ms, and a TPM quote proof adds a median 734 ms per block. On this basis the authors rule out off-chip TPMs, which they call "notoriously slow."
  - Hardware counters are said to wear out after about 1M uses.
  - [P3](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24065-paper.pdf)
- **Limitations.**
  - There is a race between an event reaching the enclave and the attacker erasing it.
  - CUSTOS cannot tell benign power failures from termination attacks, so false alerts are possible.
  - It depends on a TEE.
  - It offers no replay or reproduction of decisions; it is tamper-evidence only.
  - [P3](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24065-paper.pdf)

#### P4 — Forensic Investigation of ICS Using Deterministic Replay (CNS 2020)
- **Mechanism.**
  1. Passively sniff ICS traffic (EtherNet/IP via pyshark) into a uniform read/write variable log.
  2. Ingest the clean ladder-logic program as a hierarchical execution model.
  3. Replay the logged inputs in a discrete-event simulator, with periodic program-execution events.
  4. Compare simulated outputs with logged outputs (warning above 1% deviation, error above 10%).
  5. Propagate per-log-entry taint traces for forward and backward causality queries.

  The authors argue determinism makes ICS replay practical — [P4](https://friends.cs.purdue.edu/pubs/CNS20.pdf)
- **Threat model.** The logging/defense system is trusted, isolated from the control network, and the attacker cannot manipulate or delete its entries. All controller actions are logged correctly. A clean copy of the program is available. **Log integrity is assumed, not enforced** — [P4](https://friends.cs.purdue.edu/pubs/CNS20.pdf)
- **Results.** Tested on GRFICS (simplified Tennessee Eastman) with a physical Allen-Bradley MicroLogix 1100 in the loop:
  - Normal run: 40,060 log entries, 99.9% accuracy, 72 s simulation; 58 warnings and 2 errors, a 0.1% false-positive rate.
  - Program-modification attack: 55,379 entries, 99.8% accuracy, detected with sustained deviations.
  - Data attack (malicious HMI DLL writing a setpoint of 0): 50,881 entries, 99.7%. **Replay showed no deviation, because the command looked legitimate.** Taint tracing narrowed the cause to 3 log entries out of tens of thousands.
  - [P4](https://friends.cs.purdue.edu/pubs/CNS20.pdf)
- **Limitations and future work.** The method needs a clean program copy and a one-off manual effort per vendor format. Future work: "testing on a wider variety of hardware, and on more complicated systems" — [P4](https://friends.cs.purdue.edu/pubs/CNS20.pdf)

#### P5 — SnapShotter (ICPS 2018; slides only)
- **Mechanism.** An agent on the PLC (OpenPLC) logs each event as a 16-byte record: start, event ID, device ID, time, digital inputs and outputs, analog outputs, end. Records are encrypted with AES under a key evolved by SHA each period (forward security) and sent to a trusted monitoring server. The server verifies integrity, compares behaviour against the expected PLC profile, and can restore the PLC or switch to a backup — [P5 slides](https://chenglujin.github.io/files/Snapshotter.pdf); [VU abstract](https://research.vu.nl/en/publications/snapshotter-lightweight-intrusion-detection-and-prevention-system/)
- **Threat model.** The attacker can upload arbitrary logic remotely or physically, but cannot tamper with PLC hardware. Some logs are assumed to be produced between the start of the attack and the compromise of the logger — [P5 slides](https://chenglujin.github.io/files/Snapshotter.pdf)
- **Results.** At most 54 µs overhead per scan cycle compared with stock OpenPLC. A malicious logic upload was caught as soon as the logs arrived at the server — [P5 slides](https://chenglujin.github.io/files/Snapshotter.pdf); [VU abstract](https://research.vu.nl/en/publications/snapshotter-lightweight-intrusion-detection-and-prevention-system/)

#### P6 — Longitudinal fMRI habituation study (CHI 2017)
- **Design.** 16 participants recruited (results report about 15 usable), aged 19–29. Five daily fMRI scans with eye tracking; 260 images per session (80 static warnings, 80 polymorphic warnings, 80 general-software images, 20 others) — [P6](https://www.cl.cam.ac.uk/events/shb/2017/vance1.pdf)
- **Results.**
  - Attention dropped sharply after only the second exposure and across the workweek. Eye fixations: β = −0.103 per presentation, p < .001, N = 11,976.
  - Attention recovered partially overnight on days 2–4, but not on day 5. Recovery did not offset continued exposure.
  - Polymorphic warnings, cycling four variations (pictorial symbol, red background, jiggle, zoom), habituated significantly less over the full week.
  - Polymorphic warnings did not recover more strongly overnight than static ones (H2b not supported).
  - [P6](https://www.cl.cam.ac.uk/events/shb/2017/vance1.pdf)
- **Limitations.** Supine fMRI setting, an unrealistically high warning count, viewing images rather than acting on real warnings, measuring attention rather than secure behaviour, and a 5-day window. Future work: corroborate with a study of warnings "in their natural setting" — [P6](https://www.cl.cam.ac.uk/events/shb/2017/vance1.pdf)

#### P7 — When Should Users Check? (CHI 2026)
- **Mechanism.** Confirmation placement is cast as minimum-time scheduling. Inputs are the per-step agent success probability p_ai (Beta-Bernoulli updatable) and the costs t_confirm, t_diagnose, t_correct, and t_redo. A dynamic-programming solver picks checkpoints — [P7](https://arxiv.org/html/2510.05307v4)
- **Study.**
  - Formative: n = 8, using Manus, ChatGPT Agent, and Browser Use.
  - Main: n = 48, within-subjects (intermediate vs confirm-at-end) in simulated shopping, image-editing, and Overcooked tasks, with errors injected early, mid, or late.
  - [P7](https://arxiv.org/html/2510.05307v4)
- **Results.**
  - Completion time fell from 264.70 s to 228.86 s (−13.54%, p < 0.001). The gain was −29% for early errors, −2% for mid-task errors, and **+4.5% for late errors**.
  - Confirmation took 13% of time (32.08 s) and diagnosis 9%; time per confirmation fell 38%.
  - 81% (39/48) preferred intermediate confirmation.
  - In the formative study, participants **missed existing errors in 5 of 40 trials**; some assumed the agent would self-correct.
  - The main study did not report error-detection rates.
  - [P7](https://arxiv.org/html/2510.05307v4)
- **Limitations and future work.** The environment was simulated with fixed parameters. The model assumes clear right/wrong outputs and that verified steps stay correct. The authors propose **mandatory checkpoints for high-stakes or irreversible actions** but did not test them. No hardware was involved — [P7](https://arxiv.org/html/2510.05307v4)

#### Secondary (not read in full; leads only)
- Practitioner blogs claim Claude Code users approve 93% of permission prompts, and that human reviewers caught 13.6% of harmful actions against 89% for a classifier. **The primary Anthropic source was not located; treat as unverified** — [blog, secondhand](https://tianpan.co/blog/2026-06-25-approval-fatigue-how-human-in-the-loop-gates-decay-into-rubber-stamps)
- An Illinois paper on on-device PLC runtime verification describes TSV-style bump-in-the-wire verification between operator or programmer and the PLC: writes are staged in a buffer, checked against safety constraints, then forwarded or blocked with operator notification. Seen as a search snippet only — [Illinois PDF](https://ws.engr.illinois.edu/sitemanager/getfile.asp?id=2344)
- Lehigh's "PLC guard" (CNS 2018) intercepts engineering-workstation-to-PLC traffic so engineers can review code before it reaches the controller. Seen as a snippet only — [Lehigh PDF](https://www.cse.lehigh.edu/~chuah/publications/CNS18-PLC_Payload_Attack_Detection.pdf)
- A US patent family, "Method and system for securing SCADA and industrial control software through secure-write operations" (e.g. 12299087, 12443684, 12493669, 12664237). Only the title and figure text were seen; the mechanism is unknown. This is **potential prior art** for "approved write" claims and must be checked — [USPTO 12299087](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12299087)

### Inferences
- P2 is the closest architectural ancestor of the proposed gate, with the roles reversed: the "server" becomes the PLC side and the "untrusted host" becomes the LLM agent plus A53 Linux. P2's three principles carry over directly. The command shown to the approver must be rendered by the trusted device itself (output integrity). Every path that can trigger release (button, network, timer) must be in the TCB (all modalities, compare early-form-submission). Approval must not depend on the operator spotting indicators.
- P2's "10 → 1000" and early-submission attacks are concrete test cases for an OT gate: the agent displays one value while the gate releases another, or release is triggered before the operator has finished reviewing.
- P3's numbers favour a per-event hash update in the fabric or on the R5, with signatures (or TPM operations) deferred to periodic commitments. A per-decision TPM extend (about 20 ms) would be the bottleneck at Modbus rates. (Inference: whether the KR260 carrier's TPM matches P3's figures was not measured here.)
- P4 shows that replay catches tampered controller logic but **not** a legitimate-looking malicious command; the data attack replayed perfectly. That is exactly the gap a human-approval gate addresses. It also means a replay log for the gate must record approval provenance (who approved, which digest, when) as well as I/O.
- P6 and P7 suggest that any approval mechanism will see operator attention decay and missed errors, so an evaluation without repeated sessions and injected anomalies will look unrealistically good. This is the reviewer's warning, and it is supported by primary data.

### Gaps
- IntegriKey, Fidelius, VButton, Android Protected Confirmation, and hardware-wallet confirmation attacks were not read in full. Their characterisation here comes only from P2.
- No primary study of **industrial operators'** approval latency or error rates under command-confirmation workloads was found. Alarm-flood and ISA-18.2 literature was not reached.
- P1's extracted text appears to contain an arithmetic inconsistency in its K_live example (latency/period ≠ 8). Re-check against the PDF before citing that example.
- Custos's Table V column alignment was ambiguous in extraction, so only the throughput figures given in prose are reported.

---

## Q2. Is "hardware-bound approval of exact command bytes with a deadline" already published (any domain)?

### Takeaway
The parts are published separately; the combination is not, as far as these sources show. P2 publishes hardware-bound, exact-value, nonce-bound approval through a trusted device, but with no deadline. P1 publishes approval freshness and validity horizons, but with no human, no hardware, and no byte binding. A fixed-deadline baseline in P1 shows deadlines alone are safe but costly. No source found combines a human approver, a hardware-enforced byte-identity check at release, and a hardware timer deadline in an inline OT device. The secure-write patent family is unexamined possible prior art.

### Cited Findings
- **Exact values, hardware-signed, nonce-bound, no expiry.** ProtectIOn signs the (element-id, value) record on a trusted device, and the server rejects stale form ids — [P2](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24112-paper.pdf)
- **Transaction confirmation on separate devices (ZTIC, Android Protected Confirmation, Filyanov et al. DSN 2011) exists.** P2 criticises it for habituation, poor usability, and simple UIs only — [P2](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24112-paper.pdf)
- **Approval-to-use staleness formalised as TOCTOU, with validity horizons; LLM judge, simulation only.** A fixed deadline reaches 0% expiry at a reward cost (−1200 vs −960 for FBS) — [P1](https://arxiv.org/html/2608.26306v1)
- **P1 explicitly does not bind approvals to action bytes at runtime** — [P1](https://arxiv.org/html/2608.26306v1)
- **OT bump-in-the-wire verification exists, but is automated rather than human-approved.** Writes are staged, checked against safety constraints, then forwarded or blocked (TSV lineage). Snippet only — [Illinois](https://ws.engr.illinois.edu/sitemanager/getfile.asp?id=2344)
- **The secure-write patents cover the SCADA → PLC write path; mechanism not verified** — [USPTO](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12299087)

### Inferences
- A defensible novelty claim, pending a patent check and a read of IntegriKey, Fidelius, and APC: **an inline OT gate where release of a held command is a hardware predicate on (digest of held bytes = digest the human approved on a trusted display) ∧ (hardware timer < deadline) ∧ (epoch/session unchanged), with the predicate's inputs and outcome sealed into a replayable record.**
- P1's data supports a deadline that depends on plant state (a margin/volatility horizon) over a fixed one. A hardware version could compute δ from a register value read by the gate. That would be a genuine hardware contribution beyond P1's software heuristic.

### Gaps
- The secure-write patents (12299087 and others) were not read. Android Protected Confirmation's protocol details (whether its signed confirmation carries an expiry or nonce) were not verified from a primary source.

---

## Q3. Is hardware-anchored, replayable decision logging for OT gates published?

### Takeaway
Three separate pieces exist. Tamper-evident logs anchored in a TEE (P3) are published for OS audit, not OT. Forward-secure logging on a PLC (P5) is published, but as an encrypted event log without replay. Deterministic replay of ICS I/O (P4) is published, but it assumes the log is trustworthy and does not cover gate decisions. No source found anchors an inline gate's accept/refuse decisions in hardware so that they can be replayed bit-exactly.

### Cited Findings
- TEE hash-chain with deferred signing, monotonic-counter rollback defence, and third-party verifiability, at about 1M events/s — [P3](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24065-paper.pdf)
- P3 provides no replay; it protects only pre-compromise events, and a race window exists at the moment of compromise — [P3](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24065-paper.pdf)
- PLC agent with 16-byte records, AES under a SHA-evolved key, and at most 54 µs per scan; detection happens on the server — [P5 slides](https://chenglujin.github.io/files/Snapshotter.pdf)
- Deterministic discrete-event replay of sniffed ICS I/O against the ladder program, 99.7–99.9% accurate. The trusted, isolated logger is assumed rather than built — [P4](https://friends.cs.purdue.edu/pubs/CNS20.pdf)

### Inferences
- A gate decision is a pure function of (frame bytes, gate state, policy, time/epoch). That makes it far more replayable than P4's physical-process replay, which reached 99.7–99.9% because of timing jitter. Bit-exact replay of gate decisions is therefore a realistic and checkable claim, and it fits the project's existing bit-exact RTL-vs-Python methodology.
- Combining P3's "hash per event, sign on audit" with a PL/R5 implementation, and logging the decision inputs rather than only the outputs, would yield records that are both tamper-evident (P3) and replayable (P4).

### Gaps
- PLC forensics work on vendor logs (Siemens), the JTAG "Aye" method, and forward-secure logging papers beyond SnapShotter were seen only in search snippets and are not covered here.

---

## Q4. Open problems the authors name

### Takeaway
Six open problems are named across the sources:
1. Hardening the trusted device itself (P2).
2. Side channels and timing policies (P2).
3. Telling benign faults from termination attacks (P3).
4. The race at the moment of compromise (P3).
5. End-to-end evaluation of freshness checks against measured latency, compared with Simplex-style runtime assurance (P1).
6. Ecological validity of habituation findings, and mandatory checkpoints for irreversible actions (P6, P7).

### Cited Findings
- IOHub hardening is out of scope; formally verified embedded Rust is suggested; side-channel policies are future work — [P2](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24112-paper.pdf)
- Benign power failures cannot be distinguished from protocol-termination attacks; a race exists between an event reaching the enclave and its erasure — [P3](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24065-paper.pdf)
- Open items: end-to-end Judge+FBS on one approval stream, calibration on measured latency traces, and matched comparisons with Simplex and model-predictive shielding — [P1](https://arxiv.org/html/2608.26306v1)
- Replay needs testing on wider hardware and real systems, and needs a clean program copy — [P4](https://friends.cs.purdue.edu/pubs/CNS20.pdf)
- Results must be corroborated "in their natural setting," and secure behaviour measured rather than attention — [P6](https://www.cl.cam.ac.uk/events/shb/2017/vance1.pdf)
- Proposed but untested: mandatory checkpoints for high-stakes actions, per-user adaptation, and calibrated trust — [P7](https://arxiv.org/html/2510.05307v4)

### Inferences
- An FPGA/R5 gate speaks directly to P2's hardening problem: the TCB is a small, verifiable RTL plus R5 code rather than a Pi running Linux. It also speaks to P3's fault-versus-attack problem: the gate's own watchdog and epoch logic, already formally proved on the R5, can record a fault cause in the sealed log.

### Gaps
- No author surveyed here names "operator decision quality for agent-issued OT commands" as an open problem explicitly. That framing is ours.

---

## Q5. What would a convincing experiment look like, and what is the minimum viable hardware?

### Takeaway
A convincing study needs four elements:
1. A security evaluation under a compromised agent host, using P2-style attacks: display/value substitution, early or forged release, replay, and TOCTOU byte swaps after approval.
2. A freshness evaluation using P1's metrics on a real plant model.
3. A human study over repeated sessions with rare injected anomalies. This follows from P6's habituation and P7's missed errors, and measures latency distributions, detection d′, and deadline expiries.
4. Hardware cost measurements: added latency, TCB size, log throughput and storage, and bit-exact replay.

The minimum hardware is an R5- or PL-owned button and small display on PMOD/GPIO, firewalled from the A53. The PL holds the frame and computes its digest; release is a PL predicate; each decision record is hash-chained.

### Cited Findings (basis for design choices)
- The display must be rendered by the trusted device, and all trigger paths must be inside the TCB, to stop value-rendering and early-submission attacks — [P2](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24112-paper.pdf)
- Attention drops after the second exposure and across a workweek; polymorphic presentation slows habituation; overnight recovery is partial — [P6](https://www.cl.cam.ac.uk/events/shb/2017/vance1.pdf)
- People miss errors (5 of 40 trials) and assume self-correction. Intermediate checks help for early errors but cost time for late errors (+4.5%) — [P7](https://arxiv.org/html/2510.05307v4)
- Freshness metrics to reuse: oracle-labelled approval-expiry rate, judge-conditioned use-time invalidity, and the safety–utility trade-off against a fixed deadline — [P1](https://arxiv.org/html/2608.26306v1)
- Logging cost reference: per-event hash with signing on audit; TPM extend about 20 ms is too slow per event — [P3](https://www.ndss-symposium.org/wp-content/uploads/2020/02/24065-paper.pdf)
- Replay reference: ICS replay accuracy of 99.7–99.9% on a real PLC; data attacks are invisible to replay — [P4](https://friends.cs.purdue.edu/pubs/CNS20.pdf)
- Per-cycle overhead reference for embedded logging: 54 µs — [P5 slides](https://chenglujin.github.io/files/Snapshotter.pdf)

### Inferences (proposed design; not from any source)

**Conditions** (within-subjects, counterbalanced):
- (B0) No approval: the gate's automatic policy only.
- (B1) Software approval dialog on the agent-side host, which is compromisable.
- (H1) Hardware approval: the gate renders the decoded Modbus semantics (unit ID, function code, register, value, and an engineering-unit label from a signed register map) plus a short digest; the operator presses a physical button.
- (H2) H1 plus polymorphic or forced-attention presentation (after P6) and plant-state-dependent deadlines (after P1).

**Attacks injected** (the agent host is assumed compromised):
- Swap bytes after approval (TOCTOU).
- Show the operator one value and send another (P2's "10 → 1000").
- Forge or auto-click release (early submission).
- Replay an old approval.
- Delay release until the plant state invalidates the approval (staleness).

The hardware conditions should block the byte-level attacks by construction. The human-detectable ones, where the decoded command is semantically malicious, test the operator.

**Participants.** Ideally ICS operators or engineers; otherwise trained engineering students, reported as a limitation. About 16–48, which matches P6 and P7 sizes. Run **3–5 sessions on separate days** so habituation can appear. Use a low anomaly base rate (e.g. 2–5% of approval requests) to mimic rubber-stamping conditions.

**Metrics:**
- Approval latency (median and p95) and deadline-expiry rate.
- Detection of malicious or mismatched commands as hit rate, false-alarm rate, and d′, tracked per session to show the habituation slope.
- Wrongly released commands; refused-but-benign commands (utility).
- P1's oracle-labelled approval expiry.
- Hardware: added forwarding latency (µs) for non-approval traffic, approval-path latency, LUT/BRAM and R5 code size (TCB), log bytes per decision and sustained decisions per second, and bit-exact replay pass rate across N recorded sessions.

**Minimum viable hardware on the KR260:**
- A PMOD push-button (plus a second, two-key "arm/confirm" button if a two-person-style control is wanted), and a small SPI/I2C OLED or 7-segment PMOD driven **only** by the R5 or PL.
- The A53 must not be able to write the display or GPIO. This needs XMPU/XPPU isolation and must be verified on the XCK26.
- PL frame-hold buffer with streaming SHA-256 (or a truncated digest) of the held Modbus ADU.
- Approval register written only by the button path: {digest, epoch, nonce, deadline}.
- A release comparator in the PL.
- A hardware timer for the deadline.
- An append-only hash-chained decision record in R5-owned memory, with periodic signing on audit (P3 pattern) using a device key (eFUSE/BBRAM/PUF-derived, or the carrier TPM for rare anchors only).

### Gaps
- No primary data was found on typical operator latency for single-command confirmation in OT, so deadline values must be piloted.
- Whether the XCK26 XMPU/XPPU configuration can fully stop A53 access to the chosen PMOD pins and the R5 log region was not verified.
- Whether operators can reliably verify digests on small displays is not established; P2 argues against relying on indicator checking. A semantic decode is probably needed, but this is untested.
