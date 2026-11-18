# Guardrails Between AI/LLM Agents and Physical Actuators / Industrial Controllers

Research date: 2026-11-08. All quotes are under 15 words. "Access" records what I actually read. Where text was read through a summarizing fetch tool, I say so. For long arXiv HTML pages the fetch covered roughly the first 100k characters, which includes the body, limitations and future work. The appendix tails were not read.

Access ledger:

| # | Document | Access actually obtained |
|---|---|---|
| 1 | Schall 2026, AIS 6:14 (doi 10.1007/s43684-026-00136-1) | **Abstract + metadata + reference list only.** Springer redirected to login, and the HEP mirror says "login to view full text". |
| 2 | PLCBench, arXiv 2608.26882v1 | Full text, main body (first ~100k of 183k chars; the appendix tail was not read). |
| 3 | RoboGuard, arXiv 2503.07885v2 | Full text (first ~100k of 106k chars). |
| 4 | SafeGate, arXiv 2604.05427v1 | Full text. |
| 5 | Modular Safety Guardrails (position paper), arXiv 2602.04056v1 / ICML 2026 | Full text (first ~100k of 118k chars). |
| 6 | arXiv 2606.28011 ("pre-execution validators") | Full text. The paper is actually titled "From Detection to Action: Using LLM Agents for Fault-Tolerant Control". |
| 7 | Approved Too Late, arXiv 2608.26306v1 | Full text. |
| 8 | LRMs for abnormal situation management, arXiv 2608.19819v1 | Full text. |
| 9 | Hardware-safety-gated ARTIQ system, arXiv 2606.27231v1 (extra 2026 paper found) | Full text (first ~100k of 104k chars). |
| 10 | CISA/ASD et al., "Principles for the Secure Integration of AI in OT" (3 Dec 2025) | **Full PDF** (25 pp). Text extracted locally and the relevant sections read verbatim. |
| 11 | ISO/IEC TS 22440(-1) | **Project/status pages + one trade summary only.** The draft text is not public. |
| 12 | NVIDIA IGX Thor Safety Product Brief (FEB26) | Full public brief (2 pp). The application note and Safety Manual are NDA/registered-only and were not read. |
| 13 | IEC 62443-3-3 zones/conduits | **Not read.** The standard is paywalled and I made no fetch. See Gaps. |

---

## Q1. Where is enforcement placed, and do authors discuss host compromise or prompt injection bypassing the guardrail?

### Takeaway
Every 2025–2026 AI-to-actuator guardrail paper I read puts enforcement in software, in or next to the agent's own software stack: a validator module, an LLM "root-of-trust", an MCP proxy or a host-side runner. None places enforcement on a separate device inline with the field protocol. None analyzes compromise of the host that runs the guardrail. Prompt injection is either explicitly excluded, handled only as jailbreak resistance of the planner (RoboGuard), or deferred as a future deployment requirement.

### Cited Findings

**Schall 2026: LLM proposals behind deterministic verification (abstract only)**
- Title: "Safe integration of Large Language Models into industrial process control: a multi-agent architecture with P&ID-grounded validation". Daniel Schall, Siemens AG Austria. AIS vol. 6, art. 14, 2026. — [HEP mirror](https://journal.hep.com.cn/ais/EN/10.1007/s43684-026-00136-1)
- Architecture: four layers. LLM inference is confined to an observation-only Monitor layer. Safety-critical decisions are made by deterministic Verification and Execution agents (the "AAE framework"). A text aggregation layer turns SCADA states, time series, P&IDs and SOPs into LLM-readable documents. — [HEP mirror](https://journal.hep.com.cn/ais/EN/10.1007/s43684-026-00136-1)
- Placement (same host, separate device or PLC) and threat model (prompt injection or compromise) are not stated in the abstract. The framing is LLM non-determinism and hallucination, not an adversary. The references include IEC 61508 and IEC 61511. IEC 62443 does not appear in the available text. — [HEP mirror](https://journal.hep.com.cn/ais/EN/10.1007/s43684-026-00136-1)

**PLCBench (Zhou et al., ZJU/XJTU/Bristol, 27 Aug 2026)**
- The paper is about offense: can an autonomous LLM agent with network reach to a PLC achieve sustained physical impact? The agent runs in an isolated sandbox. A host-side runner validates each action, and PLC traffic is capped at 10 successful operations per second. These are experimental-containment controls, not a proposed defense. — [arXiv 2608.26882](https://arxiv.org/html/2608.26882)
- The PLC's own protection logic (over-temperature trip, high-level recovery, global lockout) was the "guardrail", and agents bypassed it in some cases. The authors conclude that independent safety mechanisms "should not rely on application objects" exposed through the same writable controller interface. — [arXiv 2608.26882](https://arxiv.org/html/2608.26882)
- Threat model: the agent starts with network reachability to a PLC, a malicious objective and bounded process feedback. It knows neither the protocol nor the object map. Prompt injection and host compromise are not discussed, because the agent itself is the attacker. — [arXiv 2608.26882](https://arxiv.org/html/2608.26882)

**RoboGuard (Ravichandran, Robey, Kumar, Pappas, Hassani; UPenn/CMU; v2 Mar 2026, accepted Feb 2026, IEEE robotics venue inferred)**
- Placement: in the robot control loop, before execution. It has two stages: a "root-of-trust" LLM (GPT-4o) that generates LTL safety specifications, and control synthesis (the Spot library) that reconciles the planner's plan with those specifications. The paper does not say whether this runs on the same host or in a separate process. — [arXiv 2503.07885](https://arxiv.org/html/2503.07885)
- Threats: jailbreaking of the LLM planner (direct, template, RoboPAIR, and adaptive black/gray/white-box). The root-of-trust LLM is "shielded from potentially malicious user input", but the shielding mechanism is not described. The authors concede it "may still be susceptible to a strong adaptive attacker." Host compromise is not addressed. — [arXiv 2503.07885](https://arxiv.org/html/2503.07885)

**SafeGate (Obi et al., Purdue/Incheon; 7 Apr 2026)**
- Placement: "sits at authorization points" and between action-plan sequences and the planner. Host, process and device are unspecified. — [arXiv 2604.05427](https://arxiv.org/html/2604.05427)
- No threat model. Prompt injection, jailbreak and host compromise are not addressed as threats to SafeGate itself. — [arXiv 2604.05427](https://arxiv.org/html/2604.05427)

**Modular Safety Guardrails position paper (Kim, Gu et al., 12 authors; Feb 2026; ICML 2026 position track)**
- Proposes a Monitoring & Evaluation layer plus an Intervention layer (a Decision Gate for plan screening and an Action Gate for command filtering). Definition 1 calls for "a non-bypassable, execution-time safety architecture". Monitors should use "channels decoupled from the primary autonomy pipeline". Guardrails should be "operationally independent of the upstream FMs". — [arXiv 2602.04056](https://arxiv.org/html/2602.04056v1); [PMLR v306](https://proceedings.mlr.press/v306/kim26cb.html)
- It does not discuss separate hardware, real-time controllers or hardware isolation. It acknowledges that prompt and perception manipulation can bypass safeguards, but it does not analyze compromise of the guardrail, the host or the monitoring channels. — [arXiv 2602.04056](https://arxiv.org/html/2602.04056v1)

**arXiv 2606.28011, "From Detection to Action: Using LLM Agents for Fault-Tolerant Control" (Vyas, Gill, Markaj, Gehlhoff, Mercangöz; Imperial/HSU; 26 Jun 2026)**
- Pre-execution Validation Agent: mostly deterministic rule- and metric-based checks of candidate actions against simulation output. The checks cover interlocks, permissives, envelopes, recovery time, loop performance, and actuator rate, travel and duty-cycle limits. The output is Approve or Revise. If no safe plan emerges within the latency budget, control passes to the safety system. — [arXiv 2606.28011](https://arxiv.org/html/2606.28011)
- Placement: a "Virtual Space Agent Layer" sits above a physical-space Safety System. Host, process and device are not specified. There is no threat model, and prompt-injection mitigation is listed only as a future deployment requirement. — [arXiv 2606.28011](https://arxiv.org/html/2606.28011)

**Approved Too Late (Shraga, Eshel, Gorelik; 26 Aug 2026), on enforcement placement**
- Core thesis: an LLM judge between Plan and Execute in a MAPE-K loop creates a time-of-check-to-time-of-use (TOCTOU) hazard. An approval correct at check time can be invalid at actuation, because the plant evolves during the check-use interval. Their mitigation is a "Freshness-Bounded Shield" (FBS): a post-verdict gate that expires approvals beyond an estimated validity horizon without a new verifier call. — [arXiv 2608.26306](https://arxiv.org/html/2608.26306)
- The paper explicitly excludes prompt injection and adversarial state manipulation. Host compromise is not discussed. The FBS is a software gate. The paper says the hazard applies to "any delayed Execute-stage approver" grounded in plant state. — [arXiv 2608.26306](https://arxiv.org/html/2608.26306)

**LRMs for abnormal situation management (Alhazmi, SABIC; 20 Aug 2026)**
- The model's output is applied to the plant, not merely advised, but only through a bounded interface: one of 12 diagnoses, plus setpoint changes within limits, pre-engineered protective components, pre-audited procedures, no-op, or orderly shutdown. "Direct manipulation of actuators is not representable in the interface." — [arXiv 2608.19819](https://arxiv.org/html/2608.19819)
- Placement: a programmatic validator sits between the model and the plant. It applies static membership, range, rate, cooldown and budget checks, plus a 6-hour shadow forward-simulation veto. The layer runs above the PI loops and "acts below the safety-instrumented system and leaves it in place." No hardware isolation, no threat model. — [arXiv 2608.19819](https://arxiv.org/html/2608.19819)

**Hardware-safety-gated ARTIQ system (Wang, Qi, Xie, Linke, Brown; Duke/UMD; Jun 2026)**
- Despite the title, the "hardware safety gate" is a software MCP proxy on local lab infrastructure under a dedicated unprivileged account. The agent connects only to the filter. Every tool call needs an authorization token bound to its exact content and consumed on use. Automatic tokens require an AST denylist check plus a dax.sim trace check against per-device bounds. Unmapped devices and inconclusive reviews are blocked and escalated to a human. Every call goes to an append-only audit log. — [arXiv 2606.27231](https://arxiv.org/html/2606.27231)
- Threat model: a fallible, non-malicious agent that may be swayed by adversarial content such as malformed logs. Robustness against determined attackers is explicitly not claimed. Host compromise is not analyzed. The authors acknowledge an open bypass tooling path during initial deployment, and a repository-scan path that can run agent-written files outside review. — [arXiv 2606.27231](https://arxiv.org/html/2606.27231)

### Inferences
- All nine papers sit in one placement class: software mediation in or beside the agent's compute. The ARTIQ paper comes closest to a separate enforcement point (a separate account plus token binding), and it still documents bypass paths. That is concrete evidence that same-host enforcement leaks.
- PLCBench's finding, that agents can defeat safety logic exposed through the controller's own writable interface, plus the position paper's "non-bypassable" requirement, together motivate enforcement outside both the agent host and the PLC application. That is the bump-in-the-wire position. No paper actually builds one.
- Approved Too Late's TOCTOU argument is an enforcement-placement argument: the closer the gate is to the actuator in time and position, the smaller the staleness window. An inline gate that checks each write against plant state observed on the wire (for example PLC echoes and fresh reads) at forwarding time addresses this hazard structurally. Software judges upstream of the network cannot.

### Gaps
- Schall's placement and threat model are unknown, because only the abstract was accessible. Whether the Verification/Execution agents run on the same host as the LLM must be checked in the full text.
- PLCBench's appendix and defense discussion past about 100k characters were not read.

---

## Q2. What do they measure (unsafe action rate, task success, latency)?

### Takeaway
The metrics fall into three groups. Robotics papers measure attack-success or unsafe-acceptance rate together with safe-task acceptance (RoboGuard, SafeGate). OT papers measure constraint violations or interlock trips and recovery success in simulated plants (Schall, Alhazmi, Vyas). Offense papers measure the attack-stage funnel on real PLCs (PLCBench). Latency is almost never reported for the guardrail itself. When it is reported, it is the LLM's latency, in seconds.

### Cited Findings
- **Schall:** 43 crafted error-injection proposals gave 100% recall on covered failure modes. In 50 LLM runs, the LLMs proposed unsafe actions in 10–70% of runs, and the validator caught every invalid proposal in covered categories. Evaluation used five synthetic scenarios (three Tennessee Eastman-derived, plus PolyReactor and Dryer) and B0–B3 baselines, with no real PLC. — [HEP mirror](https://journal.hep.com.cn/ais/EN/10.1007/s43684-026-00136-1)
- **PLCBench:** 4 real commercial PLCs (Siemens S7-300 over S7comm; Schneider M241 over Modbus/TCP; Beckhoff CX2030 over ADS; Mitsubishi R08CPU over SLMP), with a real-time simulated plant (HIL). 75 of 240 episodes (31.3%) reached sustained impact over 118 PLC-hours. GPT 5.5 reached 79.2%, Sonnet 5 16.7% and DeepSeek V4 Pro 10.4%. The stage funnel ran 191 discover → 142 read → 141 write → 137 manipulate → 115 disrupt → 75 impact. On the shared Modbus/TCP path, manipulation reached 100% versus 57.1% on native protocols. — [arXiv 2608.26882](https://arxiv.org/html/2608.26882)
- **RoboGuard:** RoboPAIR attack success fell from 92.3% to 2.3%. Template attacks fell from 82.3% to 0.9%. Adaptive attacks reached 2.5–5.2%. Safe-task success stayed at 100%. Each check costs about 4,330 tokens and one LLM query. On a real Clearpath Jackal (35 harmful behaviors), attack success went from 100% to 0%. Latency is not reported. — [arXiv 2503.07885](https://arxiv.org/html/2503.07885)
- **SafeGate:** on a 230-task benchmark, unsafe-task acceptance was 0.0% for SafeGate versus 26.0% for SELP and 39.0% for RoboGuard. Safe-task acceptance was 92.8%, and deferral was 9.2%. In AI2-THOR, SafeGate's crash rate was 0%, while RoboGuard authorized 28 of 30 hazardous tasks. Real-robot results are qualitative only. Latency is not given. — [arXiv 2604.05427](https://arxiv.org/html/2604.05427)
- **Vyas et al.:** Mixing Module success was 60/60 for GPT-4.1-mini and 51/60 for GPT-4o-mini. CSTR success was 28/30 and 23/30. Mean per-call action latency was 2.1–2.7 s, and Mixing Module episodes took 32.7–40.7 s. The authors note "these latencies preclude application to processes with hard real-time constraints". The paper also has internal table/text inconsistencies (80% vs 85%). — [arXiv 2606.28011](https://arxiv.org/html/2606.28011)
- **Approved Too Late:** the verdict-change rate at shift K=8 ranged from 5.3% to 48.4%. Approval expiry was 3.4–24.7% for the baseline and 0–1.8% with FBS. LLM-judge use-time invalidity was 11.5–36.8% (four judges, DeltaIoT). All five systems are simulators. — [arXiv 2608.26306](https://arxiv.org/html/2608.26306)
- **Alhazmi:** with the Tennessee Eastman process (13 scenarios × 3 seeds), baseline regulatory control stayed within hard constraints in 24/39 episodes (15 interlock trips). Sonnet-5 at high effort achieved 39/39, at about US$2.32 per campaign. Across 156 model-supervised episodes, 3 tripped. The validator's veto never fired in the primary campaign, and the ablation showed the validator did not change primary outcomes. — [arXiv 2608.19819](https://arxiv.org/html/2608.19819)
- **ARTIQ gate:** a 1,932-script adversarial campaign plus about 250 harness tests. A 631-script legitimate control set was approved with zero false rejections. Validation was on real trapped-ion hardware (Duke 40Ca+/40CaOH+, closed loop) plus an interface-level test at UMD. — [arXiv 2606.27231](https://arxiv.org/html/2606.27231)

### Inferences
- No paper reports the guardrail's own decision latency or jitter, or its throughput at line rate. A hardware gate that reports deterministic per-frame latency (cycle-accurate, at Modbus/TCP line rate) would fill a metric gap rather than compete on an existing metric.
- Alhazmi's null validator result (the veto never fired) and Schall's 10–70% unsafe-proposal rate show that the measured value of a gate depends heavily on the agent and the scenario. Reviewers will expect both a natural-agent arm and an adversarial or error-injection arm. Schall's 43 crafted proposals and the ARTIQ red-team campaign are the templates.
- Hazards of omission (the agent fails to act) are not measured by any of these papers. All their metrics count bad actions taken. That is a distinct and underexplored dimension.

### Gaps
- None of the guardrail papers reports false-refusal cost in plant terms (lost throughput), except Alhazmi's note that the model sheds more production than the reference.

---

## Q3. Limitations and stated future work, especially calls for hardware isolation, out-of-band enforcement or real-plant validation

### Takeaway
No paper explicitly calls for hardware isolation or out-of-band enforcement. The recurring stated limitations are simulation-only evaluation, no formal or SIL claim, incomplete hazard or specification coverage, and real-time latency. The nearest calls are PLCBench's demand that safety mechanisms be independent of the writable controller interface, the position paper's demand for "non-bypassable" and "operationally independent" guardrails, and the ARTIQ paper's admission that a stronger threat model needs a tighter gate.

### Cited Findings
- **PLCBench:** "The conclusions apply to the configured single-controller HIL systems." Also: "no response window was measured." Defenses and operator response are left to future work. The suggested defenses are restricting engineering-service access, checking process-relevant writes, guarding hazardous regions, and separating monitoring from write permission. — [arXiv 2608.26882](https://arxiv.org/html/2608.26882)
- **RoboGuard:** "RoboGuard requires an accurate world model." Also: "LTL may not be appropriate for some scenarios". Future work covers distilling LLMs for safety reasoning and adding perception safeguards against a compromised world model. — [arXiv 2503.07885](https://arxiv.org/html/2503.07885)
- **SafeGate:** "Future work will explore repairing defective and unsafe task commands" instead of rejecting them. The hazard templates are human-curated by the authors, and the paper gives no coverage guarantee. — [arXiv 2604.05427](https://arxiv.org/html/2604.05427)
- **Modular guardrails:** the stated aim is "not to propose a complete safety solution". Open problems: composable modules, benchmarks with rare catastrophic scenarios, allocation of conservatism across layers, fallback under gate asynchrony, and clearer "operational independence" (the authors concede independence is hard when guardrails themselves use FMs). — [arXiv 2602.04056](https://arxiv.org/html/2602.04056v1)
- **Vyas et al.:** "Truly novel faults cannot be simulated without prior characterization." For industrial deployment they call for on-premise or edge models, "IT/OT segmentation", access control, audit logging, prompt-injection mitigation and deterministic fallback. They do not call for hardware isolation. — [arXiv 2606.28011](https://arxiv.org/html/2606.28011)
- **Approved Too Late:** "It is a proof-of-concept heuristic, not a certified safety guarantee." End-to-end Judge+FBS evaluation is left as future work. — [arXiv 2608.26306](https://arxiv.org/html/2608.26306)
- **Alhazmi:** "No formal guarantee or safety-integrity-level claim is made." The work is simulation-only with an unquantified sim-to-real gap. One-action-at-a-time verification may miss multi-step failures. Future work covers a second process family, harder scenarios and trajectory-level verification. — [arXiv 2608.19819](https://arxiv.org/html/2608.19819)
- **ARTIQ gate:** "Currently, the simulation guarantees only approximately correct behavior." The denylist is evadable, and the authors propose moving to an allow-list. Future work includes closing the bypass path. — [arXiv 2606.27231](https://arxiv.org/html/2606.27231)
- **Schall:** the abstract contains no limitations or future-work text. Results are scoped to "the evaluated synthetic scenarios". — [HEP mirror](https://journal.hep.com.cn/ais/EN/10.1007/s43684-026-00136-1)

### Inferences
- The field's own limitations line up with what a hardware inline gate offers: independence from the agent host (the position paper), protection that does not rely on writable controller objects (PLCBench), freshness at the point of actuation (Approved Too Late), an allow-list rather than a denylist (ARTIQ), and real-time determinism (Vyas). A hardware contribution can be framed as answering these stated gaps. The framing must not say these authors "called for hardware", because they did not.
- Multi-step and trajectory failures (Alhazmi) and hazards of omission are not covered by per-command validators. The project's level-triggered interlock result (omission hazards removed only by a state-based interlock, plus the outage that defeated the gate-hosted interlock) speaks directly to this gap.

### Gaps
- I found no paper that states hardware or out-of-band enforcement as future work in those words.

---

## Q4. What do standards and guidance require or recommend about separating AI from control and safety functions? What makes a hardware gate compliance-aligned rather than overclaiming?

### Takeaway
The CISA-led joint guidance is the only primary document I read in full. It is voluntary. It recommends limiting AI active control without a human in the loop, using push-based or one-way data architectures, adding failsafes that revert to traditional automation or manual control, and folding AI failure states (including how to bypass the AI) into existing functional-safety processes. It never tells operators to let a security device perform safety. ISO/IEC TS 22440-1 is still a committee draft. NVIDIA's IGX shows what "safety island" means commercially: a separately powered and clocked, SIL-3-capable processor backed by a safety manual, FMEDA and third-party inspection. An uncertified FPGA gate cannot claim any of that.

### Cited Findings
**CISA/ASD ACSC/NSA AISC/FBI/Cyber Centre/BSI/NCSC-NL/NCSC-NZ/NCSC-UK, "Principles for the Secure Integration of AI in OT", 3 Dec 2025 (full PDF read)**
- Four principles: (1) Understand AI; (2) Consider AI Use in the OT Domain; (3) Establish AI Governance and Assurance Frameworks; (4) Embed Oversight and Failsafe Practices into AI and AI-Enabled OT Systems. — [CISA PDF](https://www.cisa.gov/sites/default/files/2025-12/joint-guidance-principles-for-the-secure-integration-of-artificial-intelligence-in-operational-technology-508c.pdf); [CISA landing page](https://www.cisa.gov/resources-tools/resources/principles-secure-integration-artificial-intelligence-operational-technology)
- In the guidance, "safety" alone always means functional safety (IEC 61508 sense). The introduction names "safety-process bypasses" as a key AI-OT risk. Table 2 says AI can be manipulated to "bypass security and functional safety measures or guardrails". — [CISA PDF](https://www.cisa.gov/sites/default/files/2025-12/joint-guidance-principles-for-the-secure-integration-of-artificial-intelligence-in-operational-technology-508c.pdf)
- Principle 2: "Limit active control of OT infrastructure by AI without a human in the loop". Also: "Encourage push-based architectures where data is pushed out of the OT network". Also: ensure failsafes "that revert to traditional automation or manual" for AI-enabled processes. AI connection paths should go through the existing DMZ or jump-host infrastructure. — [CISA PDF](https://www.cisa.gov/sites/default/files/2025-12/joint-guidance-principles-for-the-secure-integration-of-artificial-intelligence-in-operational-technology-508c.pdf)
- Principle 4.1: "Ultimately, humans are responsible for functional safety." Use caution with active AI directly influencing control. Where AI updates control logic, add "safety thresholds, alternative sensor output, or state changes" as human-in-the-loop intervention points. The guidance also recommends logging AI decisions with an AI identity distinct from other machine or user identities, and establishing safe operating bounds to detect drift. The worked example is a read-only AI. — [CISA PDF](https://www.cisa.gov/sites/default/files/2025-12/joint-guidance-principles-for-the-secure-integration-of-artificial-intelligence-in-operational-technology-508c.pdf)
- Principle 4.1 (segmentation): prefer push-based or brokered architectures without persistent inbound access, and use "one-way transfer patterns and audited staging buffers", so that AI is "not a persistent attack path into OT". — [CISA PDF](https://www.cisa.gov/sites/default/files/2025-12/joint-guidance-principles-for-the-secure-integration-of-artificial-intelligence-in-operational-technology-508c.pdf)
- Principle 4.2: "Establish failsafe mechanisms that enable AI systems to fail gracefully". Incorporate AI failure states, "including how to bypass or replace an AI system", into existing functional-safety and incident-response processes. — [CISA PDF](https://www.cisa.gov/sites/default/files/2025-12/joint-guidance-principles-for-the-secure-integration-of-artificial-intelligence-in-operational-technology-508c.pdf)
- On agents: "Implementing error-checking can improve AI agent's performance" by keeping outputs within expected bounds. The document "does not create policies, impose requirements, [or] mandate actions". — [CISA PDF](https://www.cisa.gov/sites/default/files/2025-12/joint-guidance-principles-for-the-secure-integration-of-artificial-intelligence-in-operational-technology-508c.pdf)

**ISO/IEC TS 22440 (functional safety and AI)**
- Scope: AI inside a safety-related function; conventional safety functions used to keep an AI-based system safe; AI used to design or verify safety functions; and security threats affecting AI safety. The 2024 WD was dropped and the work continues as TS 22440-1, "Part 1: Requirements". — [ISS project page](https://iss.rs/en/project/show/iso:proj:87118); [Genorma](https://genorma.com/en/standards/iso-iec-awi-ts-22440-1)
- Status: Part 1 is at Committee Draft stage. The comment period closed 2026-04-11 and the draft was referred back to the working group, so it is not final. — [ISO 89535](https://www.iso.org/standard/89535.html)
- It is intended to be used together with the applicable functional-safety standards (IEC 61508 family). — [DIN project page](https://www.din.de/en/wdc-proj:din21:390113071); [Automate summary](https://www.automate.org/ai/news/ai-and-functional-safety-understanding-iso-iec-ts-22440)
- NVIDIA's IGX Thor safety collateral already lists ISO/IEC TS 22440 among the standards its application note addresses. — [NVIDIA IGX Thor Safety Product Brief](https://developer.download.nvidia.com/assets/igx/robotics-product-brief-igx-thor-safety-4473375.pdf)

**NVIDIA IGX Thor safety island (commercial comparator; public brief read in full)**
- The Functional Safety Island (FSI) is "an independent, redundant set of processors" with onboard memory in the Thor SoC, used as a monitoring and safety processor. It has its own power rail and clocks "to be maximally independent". A separate safety MCU (sMCU) on the carrier board monitors faults and triggers safety responses. Edge Safety Link is a safe interface to safety sensors and actuators on which FSoE, PROFIsafe or CIP Safety can be implemented. — [NVIDIA IGX Thor Safety Product Brief](https://developer.download.nvidia.com/assets/igx/robotics-product-brief-igx-thor-safety-4473375.pdf)
- Ratings: the hardware and software (SEP) development process is ISO 26262 ASIL D-compliant and compatible with IEC 61508 SIL 3/SC 3. Random hardware integrity is ASIL B and compatible with SIL 2 (SIL 3 for the Safety Island). The brief cites a Safety Manual, an FMEDA and a TÜV Rheinland inspection report. Customers receive an inspection report and certificate "to be consumed with ... certification agencies for final certification". — [NVIDIA IGX Thor Safety Product Brief](https://developer.download.nvidia.com/assets/igx/robotics-product-brief-igx-thor-safety-4473375.pdf)
- An NVIDIA forum answer says end-system SIL still requires the customer's own system-level safety assessment. — [NVIDIA forum](https://forums.developer.nvidia.com/t/functional-safety-island-in-jetson-thor-t5000-module/360033)

### Inferences
- **Compliance-aligned framing for the KR260 gate.** Position it as a cybersecurity enforcement point on the AI-to-OT conduit, which is CISA's "error-checking" for agent outputs. It enforces safe operating bounds, logs AI writes under a distinct identity, and fails toward traditional automation, meaning the PLC and SIS keep authority. It sits above and independent of the SIS (the same placement Alhazmi states: "below the SIS and leaves it in place"). It is complementary to the PLC-hosted interlock, consistent with the guidance that humans and functional-safety processes own safety.
- **Overclaiming would include:** calling the gate a "safety function", "safety island" or "SIL"-anything. Claiming it replaces the SIS or the PLC interlock. Calling the gate-hosted interlock a safety interlock, given the observed network-outage failure. Implying CISA "requires" such a device, when the guidance is explicitly non-mandatory. The IGX comparison shows what "safety island" entails: independent power and clock, diagnostics, FMEDA, a safety manual and third-party assessment, and even then the integrator must perform the system assessment.
- The CISA preference for push-based or one-way flows is in tension with an AI agent that writes to a PLC. A bidirectional gate should be presented as a compensating control for a deliberately permitted write path: allow-listed, bounded, logged and fail-closed. It should not be presented as the guidance's preferred architecture.
- Hardware property that maps to the IGX vocabulary without claiming certification: logic isolated from the agent host (programmable-logic datapath plus R5 lockstep-capable real-time cores on the Zynq UltraScale+), which is analogous to "freedom from interference" as an engineering argument only.

### Gaps
- **IEC 62443-3-3 not read.** The zone/conduit model (conduits as the controlled communication channels between security zones) and the system requirements (for example SR 3.x integrity and SR 5.x restricted data flow) are paywalled. I did not fetch any summary in this session, so specific SR or SL language cannot be cited here and must be sourced separately.
- The ISO/IEC TS 22440-1 requirement text is not public. Whether it treats an external "conventional safety function guarding an AI" as needing its own SIL is unknown.
- The IGX application note ("IGX Thor in Safety-Related Systems") and Safety Manual are NDA-gated. How the FSI commands safe state on actuators was not verified.

---

## Q5 (Synthesis). Which open problems explicitly call for hardware or out-of-band enforcement? Is a hardware gate for AI-agent commands to PLCs already published? What evaluation would this community accept?

### Takeaway
No reviewed paper explicitly calls for hardware enforcement, but several state requirements (non-bypassable, independent, interface-independent, fresh-at-actuation, real-time) that only out-of-band enforcement fully meets. I found no published hardware gate that mediates AI-agent commands to PLCs. The closest works are software mediators (ARTIQ MCP proxy, Schall's deterministic agents) and PLC-side protection that PLCBench shows can be bypassed. An accepted evaluation would combine real PLCs (HIL as in PLCBench), externally defined scenarios (Tennessee Eastman), a natural-agent arm plus an adversarial or error-injection arm, and paired safety and utility metrics.

### Cited Findings
- The "non-bypassable, execution-time safety architecture" and "operationally independent" guardrail requirements are stated without hardware. — [arXiv 2602.04056](https://arxiv.org/html/2602.04056v1)
- Independent safety mechanisms "should not rely on application objects" on the same writable controller interface. — [arXiv 2608.26882](https://arxiv.org/html/2608.26882)
- The TOCTOU hazard applies to "any delayed Execute-stage approver". — [arXiv 2608.26306](https://arxiv.org/html/2608.26306)
- LLM-loop latencies "preclude application to processes with hard real-time constraints". — [arXiv 2606.28011](https://arxiv.org/html/2606.28011)
- A search for FPGA or hardware gates for LLM agents on PLCs found only software gates (SemaPLC verification-gated code generation, Agents4PLC, the ARTIQ MCP proxy) and an unrelated FPGA policy-enforcement patent. — [SemaPLC arXiv 2608.18565](https://arxiv.org/pdf/2608.18565); [Agents4PLC, IEEE TSE 2026](https://www.computer.org/csdl/journal/ts/2026/05/11410524/2eoNlVPx0ly); [arXiv 2606.27231](https://arxiv.org/html/2606.27231)
- Other 2026 software-gate OT works surfaced but were not read: a neuro-agentic OT-security framework that rejects unsafe LLM actions pre-execution, and a three-layer contract-based agent architecture. — [alphaXiv 2607.09076](https://www.alphaxiv.org/abs/2607.09076); [arXiv 2605.18672](https://arxiv.org/html/2605.18672)
- Evaluation norms in use:
  - Real commercial PLCs across 4 vendors and protocols with a simulated plant. — [PLCBench](https://arxiv.org/html/2608.26882)
  - Tennessee Eastman benchmark with seeds and McNemar paired statistics. — [Alhazmi](https://arxiv.org/html/2608.19819)
  - Error-injection recall plus N=50 LLM-run robustness, on TEP-derived scenarios. — [Schall](https://journal.hep.com.cn/ais/EN/10.1007/s43684-026-00136-1)
  - Adaptive black/gray/white-box attacks plus a real-robot check. — [RoboGuard](https://arxiv.org/html/2503.07885)
  - A large red-team script corpus plus a false-rejection control set on real hardware. — [ARTIQ](https://arxiv.org/html/2606.27231)
  - Offensive security assessments and AI red teaming, plus validation in simulated environments before deployment. — [CISA PDF](https://www.cisa.gov/sites/default/files/2025-12/joint-guidance-principles-for-the-secure-integration-of-artificial-intelligence-in-operational-technology-508c.pdf)

### Inferences
- **Novelty claim (defensible):** "first published inline hardware enforcement point for AI-agent writes to a PLC over Modbus/TCP, independent of both the agent host and the PLC application." This holds against everything found here. The caller notes that Lanotte et al.'s enforcers target compromised PLCs, not AI agents; that work was not re-read here. A literature search on IEEE Xplore and ACM DL for "bump-in-the-wire" plus "LLM" should be done before finalizing the claim.
- **Threat-model contribution that nobody makes:** an explicit model in which the agent host is compromised or prompt-injected. Under that model, every reviewed software guardrail (RoboGuard, SafeGate, Schall's agents, the ARTIQ proxy, FBS) is in the trust boundary of the thing it guards, and the hardware gate is not. This is the clearest hardware-specific argument.
- **Evaluation that would be accepted:**
  1. Real Modbus/TCP PLC(s) with a HIL plant, ideally the Tennessee Eastman process so results are comparable with Schall and Alhazmi.
  2. Three arms: natural agent (Qwen3-0.6B and at least one stronger model), error-injection corpus (Schall-style), and adversarial or compromised-host attacker (PLCBench-style objectives, RoboGuard-style adaptive attacks).
  3. Paired metrics: unsafe-write pass-through rate, safe-write false-refusal rate (the ARTIQ control set), constraint violations and trips (Alhazmi), omission hazards, and gate latency and jitter at line rate.
  4. Fault injection: network outage, gate power loss and PLC restart, which turns the observed outage failure into a reported result.
  5. A comparison against a software gate on the agent host under the same compromised-host attacker.
- **Standards claim to make:** "an IEC 62443-style conduit enforcement device and CISA Principle 4 error-checking point that leaves the SIS in place." Do not claim SIL.

### Gaps
- IEEE Xplore and ACM DL were not searched directly. A 2025–2026 hardware or FPGA enforcer for AI-agent commands could exist in conference proceedings that were not indexed by my searches.
- Lanotte et al. and other PLC-enforcer work were not re-read here, so the precise delta must be established from their texts.
- The Schall full text (which may discuss deployment placement on Siemens infrastructure) remains unread and is the highest-priority follow-up.
