# Academic and non-patent prior-art sweep: inline OT gate (C1, C2, C3, C5, C6)

Date of sweep: 2026-11-08. Companion to `patents.md` in this folder.

Claims under test:
- C1: session-preserving refusal. Rewrite the Modbus/TCP request FC to unused 0x7F (incremental checksum), let the PLC
  return an exception, rewrite that to exception 03 for the client. Broad form: any ICS firewall, IPS or enforcer
  that answers a blocked request with a protocol-level exception instead of dropping or resetting.
- C2: each forwarded write is pending until the PLC echo or exception. The register is marked uncertain on timeout or
  connection loss, and that state feeds later decisions.
- C3: admissible plant-state intervals that widen with the age of the last reading (worst-case rate bounds), used by
  an inline enforcer.
- C5: a separate hardware device that enforces policy on AI/LLM-agent commands to PLCs.
- C6: human approval bound to the exact held command bytes, with a deadline enforced by the gate.

Already known, not re-reported: Lanotte/Merro/Munteanu (CSF 2020, TOPS 2022), SAIN, P4Ward, SCADAWall, Hu et al.
SmartGridComm 2024, Iwasawa et al. 2020, SRIM CIGRE 2026, Pearce et al. TII 2020, ProtectIOn, Approved Too Late,
Doran ETFA 2023, PLCBench, RoboGuard, SafeGate. The three items in task 3 are revisited below only for what new
text could be obtained.

## Method and coverage

- Forward citations came from OpenAlex (`filter=cites:`) and the Semantic Scholar Graph API. Semantic Scholar was
  heavily rate-limited (429), but citations for TOPS 2022, CSF 2020, P4Ward and SAIN were eventually retrieved.
  `arXiv:2105.10668/citations` returned an empty list, which looks like an ID-merge issue; the TOPS DOI covers it.
  - Lanotte CSF 2020 (W3032398683): 17 citing works. Lanotte TOPS 2022 (W4283796786): 19. Lanotte IEC 61499 TOSEM
    2024 (W4402079544): 2. P4Ward (W4414197132): 1. SAIN: 19 citing works via S2. Approved Too Late: 2. PLCBench: 0.
  - Every citing title was screened. Any title that could touch C1-C6 had its abstract read (listed below).
- Keyword searches used a general web search engine plus OpenAlex full-text search. IEEE Xplore, ACM DL and Google
  Scholar were not queried directly: there is no API access and the pages block automated fetches. dblp was not
  queried separately.
- Vendor and IPS documentation was read where a PDF could be fetched and run through `pdftotext`.

## Findings by candidate

### A. Tofino (Belden/Hirschmann, Eaton MTL) Modbus TCP Enforcer LSM: datasheet and Tofino Configurator user manual
- Citation: MTL/Eaton "Tofino Modbus TCP Enforcer LSM" datasheet DS-MBT-LSM (PDF metadata created 2009-05-29),
  https://www.mtl-inst.com/images/uploads/datasheets/DS-MBT-LSM.pdf. Hirschmann "User Manual Tofino Configurator"
  Release 03.2.00 05/2019, §7.3.1, pp. 106-107,
  https://www.doc.hirschmann.com/pdf/UM_TofinoConfigurator_03200_en_2021-11-25.pdf
- Access: FULL TEXT of both, read through pdftotext.
- Claims touched: C1 broad, C1 narrow, C2 (only slightly).
- Evidence:
  - Datasheet "user-settable options": "Modbus exception reply on blocked traffic", next to "TCP Reset on blocked
    traffic". The defaults are deny-by-default function-code and register-range lists, plus a sanity check.
  - Manual p.107: "To have the Tofino SA send a Modbus TC exception response, if appropriate, to the Modbus device that
    generated a blocked message, select 'Exception'". The manual carries a CAUTION, quoted here: "Select the Modbus
    Exception option only when you are using the product in a test environment." The vendor recommends Reset to
    avoid client lock-up.
  - Manual p.106: "State Check" will "block and report any Modbus command or response that is out of sequence for the
    current state of the connection". This is request/response pairing per connection, with no per-register
    uncertainty.
  - The exception code that is sent is not stated. The manual does not say whether the device synthesises the exception
    itself (very likely) or gets the PLC to produce it.
- Verdict: **PRE-EMPTS C1 broad.** This commercial ICS firewall answers a blocked Modbus request with a Modbus exception
  instead of drop/RST, and it has shipped since at least 2009. **PARTIAL OVERLAP with C1 narrow:** same function, but
  the Tofino generates the reply itself, while our gate makes the PLC generate it through an FC rewrite, uses no
  injected frame and leaves seq/ack untouched. The vendor's own caution that the exception mode is test-only is useful
  for motivation: the vendor saw session problems in practice. **NO OVERLAP with C2** beyond connection-state sequencing.
- Resolves the open item in `patents.md` §3 ("whether it can return an exception ... was not verified").

### B. Snort and Suricata active response (documentation)
- Citations: Suricata docs, Rules intro (actions) https://docs.suricata.io/en/latest/rules/intro.html and payload
  keywords (`replace`) https://docs.suricata.io/en/latest/rules/payload-keywords.html. Snort 2.9 active response
  blog (2010) https://blog.snort.org/2010/11/active-response-with-snort-290.html and Snort README.active.
- Access: Suricata doc pages read in full (only the relevant sections). Snort material read as search summaries and
  list posts; README.active was not opened directly.
- Claims touched: C1 broad, C1 narrow (the in-flight same-length rewrite).
- Evidence:
  - Suricata `reject`: "send RST/ICMP unreach error to the sender". `rejectboth` sends to both sides. There is no
    application-layer reply.
  - Snort `resp`/`response`: TCP RST or ICMP unreachable. Snort `react` sends an HTTP block page to the browser and
    then closes the session. That is an application-layer reply, but it ends the session and is HTTP only.
  - Suricata `replace` (IPS mode only): the replacement must be the same length as the content it replaces, and
    checksums are recalculated. This is prior art for "same-length in-flight payload rewrite with checksum fix-up in an
    inline IPS". It is not used for refusal.
- Verdict: **PARTIAL OVERLAP with C1.** Generic IPS refusal is RST, ICMP or an HTTP page plus close. Same-length
  rewriting is an existing IPS primitive, so the narrow C1 novelty has to rest on the combination (rewrite to an
  unimplemented FC so the real PLC raises the exception, then remap it), not on in-flight rewriting itself. Zeek has no
  inline active response of its own; it relies on NetControl to signal external devices. That is from my own
  knowledge and was not re-checked this session.

### C. Moxa IEF-G9010 industrial firewall/IPS manual v1.0 (2020)
- Citation: https://moxa.com/getmedia/e6abfcb4-dcbf-4efb-acc9-7a67d72e817a/moxa-ief-g9010-series-manual-v1.0.pdf
- Access: FULL TEXT through pdftotext, searched for the action options.
- Evidence: the actions are "Monitor and Log" / "Prevent and Log" and protocol filter allow/deny. No exception option
  was found.
- Verdict: NO OVERLAP. Logged as negative evidence: not every ICS firewall offers exception replies.

### D. Fowler (Univ. Arkansas, advisor Kevin Jin), "Protocol-Aware Enforcement-Point Postcards and Collector Feedback for OT/ICS Forensic Readiness and Closed-Loop Defense," B.S. Honors thesis, May 2026
- Citation: https://scholarworks.uark.edu/elcsuht/34 (same group as P4Ward)
- Access: ABSTRACT only. The PDF returned 403.
- Claims touched: C1 (unknown), C2 (no).
- Evidence: a P4 switch "parses Modbus/TCP write traffic, applies protocol-aware policy checks" and exports postcards.
  Denied writes take a median of 1831 µs. The abstract does not say how a denial is signalled.
- Verdict: NO OVERLAP on the evidence available. The full text should be checked for an exception-reply mode.

### E. Raj & Jin, "Leveraging Data Plane Programmability Towards a Policy-driven In-Network Security Framework for Industrial Control Systems," ACM e-Energy 2025, doi:10.1145/3679240.3734619
- Access: ABSTRACT (OpenAlex).
- Claims touched: C2 (weak).
- Evidence: in-data-plane detection and mitigation on Tofino covering "protocol violations, request message rates, and
  delayed or unsolicited responses".
- Verdict: PARTIAL OVERLAP with C2, but only at the level of request/response timing. Nothing in the abstract suggests
  a per-register pending/uncertain state that is reused in later decisions.

### F. D'Agati, Tricomi, Mirto, Merlino, "Execution-Time Validation of Context-Carrying Action Intents in Industrial Cyber-Physical Systems," arXiv:2610.27971 (20 Oct 2026). It cites Approved Too Late.
- Access: FULL TEXT (arXiv HTML), first ~100k of 159k characters. The rest is mostly evaluation and appendix.
- Claims touched: C2, C3, C6, C5 (weak).
- Evidence:
  - XAIR is "an edge service" (§4.3) that rechecks intents before release. The commands are made version-conditional
    and enforced in the controller scan. The prototype uses Modbus TCP to OpenPLC (§5.3). It is not a network
    bump-in-the-wire.
  - Intents carry a freshness window *w* and a deadline *d*, with a clock-offset bound (§3.1). This is the age of the
    *decision*, not the age of the *sensor reading*. Plant rates appear only in the cost model.
  - An intent released without feedback "stays in Unknown effect" until a controller report arrives (§4.2). There is
    no uncertainty state for PLC timeouts or connection loss. If the context store is unreachable, all intents are
    rejected (§4.3).
  - Rejected intents get policy outcomes (Revoke/Expired/Delay/Degrade). No protocol exception is sent.
  - There is no per-intent human approval with a deadline. An operator-presence predicate is mentioned as an example.
- Verdict: **PARTIAL OVERLAP with C2** (the "Unknown effect" state until the controller confirms) **and with C6**
  (deadline-bounded execution of a held command, though not human approval bound to bytes). **NO OVERLAP with C3**
  (no observation-age-widened intervals) or **C1**. Very recent and the closest academic neighbour to C2. It must be
  cited and contrasted: software edge service vs. inline gate, decision age vs. reading age, no timeout/connection-loss
  uncertainty.

### G. Das, "A Setpoint Write Is Not Actuation: Finality for ICS, Grid, and Robot Command," IETF Internet-Draft draft-das-ot-actuation-finality-00 (individual, Informational, 27 Aug 2026)
- Citation: https://datatracker.ietf.org/doc/html/draft-das-ot-actuation-finality-00
- Access: FULL TEXT (read through the fetch tool's summary, with quotes checked against the returned text).
- Claims touched: C5, C6, C2 (weak), C1 (no).
- Evidence:
  - Agent-generated writes are "Actuation Candidate Acts" held non-effective. A Protected Enforcement Domain issues
    scoped authority, and an "actuation sink" in front of I/O consumes it. The sink is "The last software component
    that can still refuse before I/O changes". A JSON-to-Modbus gateway "IS the sink" (§16.4).
  - Authority is bound to a "Hash over canonical device, tag, value, units, mode, zone, and interlock flags", with a
    short expiry (5 s in the example) and maker-checker dual control ("An agent SHOULD NOT be the sole checker").
  - "Timeout MUST NOT actuate". There is no PLC echo confirmation and no uncertain state. Nothing on wire-level refusal.
    It is software and HSM based, with no FPGA.
- Verdict: **PARTIAL OVERLAP with C5** (an enforcement point specifically for agent-generated OT writes, though software
  and not a separate hardware device) and **PARTIAL OVERLAP with C6** (digest-bound authority with expiry, human
  checker). It binds a canonical semantic digest, not the raw held bytes, and no gate holds the actual frame. An
  individual I-D has no standing, but it is public prior art dated 27 Aug 2026. An SSRN paper, "Localizing Divergence
  in Operational Technology: Authorized Intent, Commanded State, Physical Process and Reported Observation"
  (doi:10.2139/ssrn.7567359, 2026), is likely related but could not be read (403, no abstract in OpenAlex). Its title
  points at C2 (commanded vs. reported state), so it is an **unread risk for C2**.

### H. Wang, Qi, Xie, Linke, Brown, "A hardware-safety-gated system for LLM-written native ARTIQ control code on a trapped-ion platform," arXiv:2606.27231 (25 Jun 2026)
- Access: FULL TEXT (arXiv HTML, ~96%).
- Claims touched: C5, C6.
- Evidence: an MCP proxy safety filter is the single enforcement point (§II.1). Each token is "bound to a single tool
  call with specific contents". Automatic tokens come from simulation against per-device bounds, and a human issues
  tokens for sensitive actions. Automatic tokens are single-use. Human tokens "persist across sessions" and may carry
  a usage quota. There is no TTL/deadline. The gate is software only, despite the title.
- Verdict: **PARTIAL OVERLAP with C6** (approval bound to exact call contents) and **PARTIAL OVERLAP with C5**
  (an LLM agent gated before lab hardware, but in software, not PLCs, and not a separate device). The absence of
  deadlines is the explicit contrast with C6.

### I. Cano Córdoba, Palmisano, Fränzle, Bloem, Könighofer, "Safety Shielding under Delayed Observation," ICAPS 2023, arXiv:2307.02164
- Access: ABSTRACT and metadata.
- Claims touched: C3.
- Evidence: delay-resilient shields that "guarantee safety under worst-case assumptions on the delays of the input
  signals". In effect the shield reasons over every state reachable during the delay.
- Verdict: **PARTIAL OVERLAP with C3.** Enforcing over a state set that grows with observation delay is known in
  shield synthesis (formal methods/RL, CARLA). Not inline and not ICS. Related background, also not read in full:
  real-time reachability Simplex (Bak et al.) and NASA hybrid-program RTA, which derives sensor sample-rate
  requirements. C3 novelty must rest on doing this inline, per register, with interval arithmetic in hardware on a
  Modbus path, not on the idea that worst-case reach grows with staleness.

### J. Lanotte, SAIN, P4Ward forward-citation candidates (abstracts read)
| Work | Access | Claims | Verdict |
|---|---|---|---|
| "Beyond Anomaly Detection: Securing Critical Infrastructure Using PlantShield," IEEE CCWC 2026, doi:10.1109/ccwc67433.2026.11393869 | Abstract | C3/C5 weak | NO OVERLAP on what is visible. It stops actuators receiving commands that would move the plant to an undesirable state (SWaT testbed). The mechanism and signalling are not described. Probably in the SafeCI line (Adepu & Mathur, IJCIP 34, 2021, abstract read: validates a command "prior to its reception at the target actuator"). No staleness, exception or confirmation handling is mentioned. |
| (authors not recorded) "A Framework for Runtime Safety of ICS Through Runtime Verification," IEEE IoT-J 2025, doi:10.1109/jiot.2025.3529887 | Abstract | C2 weak | NO OVERLAP. A stream-based RV over an OPC UA bridge, with timeouts in specifications and online correction. |
| "Mitigation of Cyber-physical Attacks in Industry 4.0 using Secure Function Blocks," MEMOCODE 2025, doi:10.1145/3742875.3754685 (Pearce/Roop group) | Abstract | — | NO OVERLAP. IEC 61499 enforcers. |
| "Runtime Verification Framework for Monitoring PLCs," SSRN 2026, doi:10.2139/ssrn.7299989 | Title only | — | Not assessable. |
| EmuGuard (CCIS 2025) | Title only | — | Honeypot/emulation active defense, not relevant. |
| "You Can't Always Check What You Wanted," ISORC 2023, doi:10.1109/isorc58943.2023.00017 | Title | C5 weak | TEE-based actuation checking in RT-IoT. Not agent-specific, NO OVERLAP. |
| "RISK: Auditing ICS for Too-Late-to-Recover Vulnerabilities," arXiv:2609.38528 (cites SAIN) | Abstract | C3/C6 thematic | NO OVERLAP. Offline auditing of whether detection leaves enough recovery margin. Useful to cite for timing-margin arguments. |
| MARS (arXiv 2609.06306), ReVISE (ICCPS 2026), ADIS (TIFS 2025), ICSTracker (DSN 2025), Fuzzing the Physical Space (S&P 2026) (SAIN citers) | Titles | — | Attack, detection or forensics on PLC variables. No enforcement relevant to C1-C6. |
| Protocol-Aware Semantic MoE Graph Learning (ICCCN 2026), only P4Ward citer | Title | — | IDS, NO OVERLAP. |

### K. LLM-agent and OT works (keyword sweep)
| Work | Access | Claims | Verdict |
|---|---|---|---|
| "A Multi-Agent Framework for Step-Level Tool-Call Safety Evaluation in ICS," AIITA 2026, doi:10.1109/aiita69518.2026.11567230 | Abstract | C5 | NO OVERLAP. A benchmark/dataset for LLM guardrails on PLC/SCADA tool calls, software only, with no enforcement device. Useful for motivation. |
| IndustriConnect, arXiv:2603.24703 | Abstract | C5 weak | NO OVERLAP. MCP adapters for Modbus/OPC UA with adapter-level uint16 range validation. Software. |
| "Organizational Control Layer," arXiv:2606.04306; "Runtime Policy Enforcement for MCP-Based LLM Agents," Electronics 15(13):2829; AgentSpec (ICSE '26) | Search summaries | C5/C6 generic | NO OVERLAP with OT hardware. Generic software policy enforcement points for agent tool calls. |
| Agent Operating System (AOS), arXiv:2608.03214 | Abstract | — | NO OVERLAP. Physical infrastructure is explicitly out of scope. |
| LLM-Guided Safety Agent for Edge Robotics, arXiv:2604.20193 | Abstract | C5 weak | NO OVERLAP. LLM translates rules into predicates on a dual-RK3588 DMR runtime. Not a gate on agent commands. |
| Practitioner blogs on agent approval gates (scalekit, agentdraft, etc.) | Search summaries | C6 | Background. "Only the approved payload executes, checked against a hash", "Expiry is mandatory". Hash-plus-TTL approval is folk practice for software agents. Not citable as academic prior art, but it undercuts any broad C6 novelty claim. |

### L. Task 3 items (fuller text attempts)
- **SRIM (CIGRE 2026 paper 10116).** The CIGRE SC D2 2026 Special Report was read in full (PDF): "a hardware-based
  Substation Real-time Intrusion Prevention Module (SRIM) for protecting IEC 61850 process bus communications.
  Implemented as an FPGA-accelerated SFP module ... deep packet inspection at line rate". The session title is "Cyber
  Sentinels: Harnessing Deep Packet Inspection for Real-Time Defense of Substation". Moxa's CIGRE 2026 announcement
  names King Wu, Hilbert Lu and Kate Huang. The paper itself and any Moxa white paper or slides were **not obtainable**.
  It covers the process bus (GOOSE/SV, layer 2), not Modbus/TCP sessions. Verdict unchanged: it pre-empts "FPGA inline
  OT IPS at µs latency" but has NO OVERLAP with C1-C3, C5 or C6 on the available text.
- **Iwasawa et al. (Trans. SICE 56(2):51-56, 2020).** The J-STAGE English abstract and the Hitachi 2019 press release
  ("Unauthorized communication data can be judged and eliminated in about two microseconds",
  https://www-hitachi-com.itdweb.ext.hitachi.co.jp/rd/news/topics/2019/0919.html) were seen as search summaries. Hitachi
  also has a 2021 TSN follow-up (Trans. SICE 57(9):391-398) at ~2.12 µs max. No English full text or Hitachi Review
  article was found. It enforces by FCS corruption (drop). NO OVERLAP with C1 narrow or C2-C6.
- **Pearce et al. TII 2020.** Abstract read through Semantic Scholar. No author copy is on arXiv, and Unpaywall/S2 list
  no OA PDF. Lanotte's arXiv:2105.10668 describes it as "bi-directional runtime enforcement over valued signals ... smart
  I/O modules". It sits at the I/O module, not the network. NO OVERLAP with C1/C2. Possible C3 contact (timed
  enforcers) could not be checked without the full text.

### M. Negative searches (nothing found)
- "Modbus firewall exception response", "ICS IPS negative response block", "transparent Modbus proxy exception code
  policy": no academic paper found that synthesises Modbus exceptions on block. The only hits were Tofino (A) and the
  patents in `patents.md` (Rockwell spoof response, gateway exception patents).
- "PLC write acknowledgement monitoring", "unconfirmed command uncertain state enforcer": only HMI/driver vendor notes
  (C-more NAK vs ACK timeout; a nautilus GitHub issue on gateway exceptions 0x0A/0x0B being dropped) and XAIR (F).
  Passive state reconstruction exists (Hadžiosmanović et al., "Through the eye of the PLC", ACSAC 2014, abstract only),
  but it has no pending/uncertain write state used for enforcement.
- "Age of information / stale observation admission of actuator commands": AoI scheduling papers and hobby-project
  staleness failsafes only, plus shield/RTA work (I). No inline ICS enforcer was found that widens admissible intervals
  with reading age.
- "LLM agent PLC hardware gateway FPGA": nothing found that puts a separate hardware device between an LLM agent and a
  PLC. The nearest are G (software sink, I-D), H (software proxy, lab hardware) and NVIDIA's DPU-based agent
  monitoring (search summary only, data centre, not OT).
- "Operator approval industrial command deadline hardware": nothing found beyond G, H and F.

## Verdict table

| Claim | Status | Closest prior art | Confidence | Not searched / not read |
|---|---|---|---|---|
| C1 broad (protocol-level exception instead of drop/RST) | **Pre-empted** | Tofino Modbus TCP Enforcer "Modbus exception reply on blocked traffic" (datasheet ~2009; manual 2019 §7.3.1); Rockwell US 2006/0155865 / US 7,990,967 (see patents.md); Snort `react` (HTTP analogue) | High | Fortinet, Claroty, Nozomi, Cisco ISA3000, Siemens SCALANCE S manuals not read |
| C1 narrow (FC→0x7F so the real PLC raises the exception, remap to 03, incremental checksum, no injection, seq/ack untouched) | **Open, function overlaps** | Tofino exception mode (self-generated reply, which the vendor itself flags as test-only); Suricata `replace` (same-length rewrite with checksum fix-up) | Medium | Fowler 2026 thesis full text (403); IEEE/ACM DL not queried directly |
| C2 (pending until echo/exception; uncertain on timeout or connection loss; used in later decisions) | **Partially pre-empted** (the "unknown effect until confirmed" idea exists; inline per-register uncertainty with timeout/connection-loss semantics was not found) | D'Agati et al. XAIR arXiv:2610.27971 ("Unknown effect" until controller report); Tofino State Check; Raj & Jin e-Energy 2025 (delayed/unsolicited responses) | Medium | SSRN 7567359 "Localizing Divergence ... Commanded State ... Reported Observation" (unread, title is on-topic); Claroty/Nozomi docs |
| C3 (age-widened admissible intervals in an inline enforcer) | **Partially pre-empted** in concept; open as an inline ICS enforcer mechanism | Delay-resilient shields (ICAPS 2023); real-time reachability Simplex/RTA; XAIR freshness windows (decision age only) | Medium | Pearce TII 2020 and Lanotte TOPS full texts for timed enforcers; Hu et al. 2024 recheck; control-barrier-function-with-delay literature only lightly searched |
| C5 (separate hardware device enforcing policy on AI/LLM-agent commands to PLCs) | **Open** (software analogues exist) | IETF draft-das-ot-actuation-finality-00 (software sink for agent OT writes, Aug 2026); ARTIQ safety filter arXiv:2606.27231 (software proxy, lab hardware); AIITA 2026 ICS tool-call guardrail benchmark | Medium | Google Scholar not queried; industry products (e.g. NVIDIA BlueField agent monitoring) not read |
| C6 (approval bound to exact held bytes, with a gate-enforced deadline) | **Partially pre-empted** | IETF draft-das (canonical-digest-bound authority, 5 s expiry, maker-checker); ARTIQ arXiv:2606.27231 (token bound to exact call contents, no TTL); XAIR (deadline on intents, no human binding); folk practice in agent-tooling blogs | Medium | ProtectIOn-style trusted-path follow-ups since 2024 not re-swept |

### Positioning implications
- Drop any claim of the form "first to answer a blocked ICS request with an exception". Claim the specific
  PLC-generated-exception mechanism and its properties: no injected segments, no seq/ack change, the PLC's real
  exception is reused, session survival is measured. Contrast explicitly with Tofino's self-generated exception mode
  and its "test environment only" caution.
- For C2, cite XAIR and state the differences: inline at the wire, per register, timeout and connection-loss
  transitions, and uncertainty that changes later admission decisions.
- For C3, cite delay-resilient shields and RTA. Claim the inline, per-register, rate-bound interval mechanism in the
  datapath, not the concept.
- For C5 and C6, the defensible delta is the separate hardware device holding the actual frame bytes and enforcing the
  deadline itself. Cite the IETF draft and the ARTIQ paper as the closest software analogues.
