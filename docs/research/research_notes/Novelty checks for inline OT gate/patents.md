# Patent prior-art check: inline OT gate (C1-C6)

Date: 2026-11-08. Method: Google Patents pages (WebFetch), web search over USPTO/Justia/Google Patents.
Google Patents' interactive search is JS-only and could not be queried directly; keyword searches went through a
general web search, so coverage is partial. USPTO Patent Public Search and Espacenet were not queried directly.

**Not legal advice.** This is a technical overlap assessment by a non-lawyer. Claim scope, validity, equivalents and
freedom-to-operate need a registered patent attorney. Legal status and expiry dates are Google Patents' own estimates.

Claims under test:
- C1 Session-preserving refusal: rewrite the Modbus/TCP FC to illegal 0x7F (incremental TCP checksum), let the PLC
  return an exception, rewrite that exception code to 03; no seq/ack rewriting, no injected frames. Broad form: a firewall
  that answers blocked industrial requests with protocol-level responses instead of drop/RST.
- C2 Response-confirmed write tracking (pending until PLC echo; uncertain on timeout or connection loss) used in later decisions.
- C3 Admissible plant-state intervals that widen with the age of the last reading, used by an inline enforcer.
- C4 FPGA/RT-core enforcer isolated from a compromised application processor on the same SoC.
- C5 Hardware gate for AI/LLM-agent commands to industrial controllers.
- C6 Human approval bound to a digest of the exact held command bytes, with a deadline, released by hardware.

---

## 1. Flagged family: Madisetti/Bahga "securing SCADA ... through secure-write operations"

All four share priority to US prov. 63/523,362 (2023-06-26). Assignee: individual (Vijay Madisetti; Bahga assigned
his rights to him). Access level: full claims read on Google Patents for all four.

| Patent | Filed / granted | Independent claims (paraphrase) | Key language |
|---|---|---|---|
| US 12,299,087 B2 | 2024-06-26 / 2025-05-13 | Cl.1/9: **the PLC** receives a "secure write instruction", validates it, checks permissibility, and executes or rejects it. Cl.9 adds an instruction decoder and validator inside the PLC. | "receiving a secure write instruction at a programmable-logic controller" |
| US 12,443,684 B2 | 2025-01-29 (cont.) / 2025-10-14 | Cl.1/14: verify the PLC's local secure memory against a verification profile kept in tamper-resistant storage, run secure recovery on failure, otherwise add an approved operation and update the profile. Cl.5: secure boot chain (HW root of trust, two bootloader stages). | "tamper-resistant area of the PLC" |
| US 12,493,669 B2 | 2025-01-29 (cont.) / 2025-12-09 | Cl.1/9/11: like '087, but permissibility is judged by comparing parameters with a range of permitted values stored in the PLC. | "range of permitted values stored in the PLC" |
| US 12,664,237 B2 | 2025-09-22 / 2026-06-23 | Cl.1/11/21: an operator interaction at a SCADA UI generates an encoded secure write in a "tamper-resistant secure format". The PLC decodes it, extracts the operation and parameters, and executes or rejects it. | "tamper-resistant secure format" |

**Verdict:** all four claim validation **inside the PLC** (or SCADA-side encoding plus PLC-side decoding) of a
**special secure-write instruction format**. None claims an inline network device between client and PLC that
works on unmodified Modbus/TCP. None covers exception rewriting, write-echo tracking, age-widened intervals,
SoC isolation, AI agents, or digest-bound approval.
- C1: NO OVERLAP. C2: NO OVERLAP. C3: NO OVERLAP. C4: NO OVERLAP. C5: NO OVERLAP.
- C6: weak/NO OVERLAP. '237 links an operator UI action to an encoded write, but the PLC does the release, with
  no held bytes, digest binding, or deadline. '493669 (permitted ranges) is relevant background for range checks,
  but only inside the PLC.
- Practical note: '237 is a live continuation family with a 2023 priority date. Keep the gate described as
  operating on standard, unmodified Modbus frames in front of an unmodified PLC.

---

## 2. Key finding for C1: Rockwell "Firewall method and apparatus for industrial systems" (spoof response)

Assignee Rockwell Automation Technologies. Priority 2005-01-06 (provisionals). Inventors: Brandt, Batke, Singer et al.
Litigation is flagged on the family.

| Patent | Status (Google est.) | Access | Relevant independent claims |
|---|---|---|---|
| **US 7,990,967 B2** (filed 2006-01-06, granted 2011-08-02) | **Active, expires 2030-01-14** (PTA) | Claims read (excerpt from cl.6 onward; cl.1 not seen) | **Cl.31 / 36 (method), 63 (apparatus):** a firewall intercepts a packet, identifies it as unauthorized, and sends the source a spoof response that simulates the target so the source moves on to the next communication in its stack. Cl.36: the spoof is filled with generated "bogus" data. Cl.23: an unauthorized source gets a response packet carrying the T-O ID. |
| **US 8,774,186 B2** (cont., filed 2011, granted 2014-07-08) | Active per Google; adjusted expiry **2026-09-12** (so probably expired by now; verify) | Claims read | **Cl.25 / 29 / 31 / 33:** same spoof-response concept ("reducing processing delays when unauthorized requests occur"). The source runs a single-string stack and waits for each reply; the firewall sends a spoof response it accepts. |
| US 9,369,436 B2; US 10,091,208 B2 | Expired (lifetime), 2026-01 | Metadata only; claims not read | Same specification; the spoof response is in the description. |
| US 2006/0155865 A1 (published 2006) | Publication | Not read | Same disclosure. **This is the prior-art publication date for the broad C1 concept.** |

Spec details: FIG. 30 spoof packet with an "Invalid Access Request" message field and fabricated connection serial
number. FIG. 32 shows the spoof generation steps. The stated purpose matches ours: stop the requesting device from
hanging until timeout. The examples are CIP/EtherNet/IP; I found no mention of Modbus.

**Assessment against C1:**
- **Broad C1 ("answer blocked industrial requests with a protocol-level response instead of drop/RST") is
  PRE-EMPTED as prior art**, publicly disclosed since 2006 (Rockwell). It is also *claimed* in US 7,990,967, which
  Google lists as active until 2030-01-14. That is an FTO issue for the broad behaviour, not just a novelty one.
- **Narrow C1 (our mechanism) differs technically:** (a) the gate does not create or encapsulate a response. The PLC
  creates the exception, and the gate rewrites one byte in each direction. (b) No frames are injected and seq/ack is
  untouched. (c) The trick is to rewrite the request to an illegal FC so the real target produces the refusal.
  Whether "rewriting the target's real exception" falls under "a spoof response packet that simulates a response
  from the target device" is a claim-construction and equivalents question for counsel. A literal reading of
  "encapsulating a spoof response packet" and "bogus information" fits a gate-generated frame better than a
  modified real one, but the functional overlap is clear. **Rate: OVERLAPS (functional), mechanism not seen in claims.**
- Earlier/other C1 prior art: US 2015/0156286 A1 (message tunnelling, industrial gateway) has the gateway send a
  "MODBUS exception response" for errors, generated by the gateway (claims not read). US 6,233,626 and US 7,051,143
  (old, expired) describe Modbus adapters/gateways replying with exception 01 to unsupported messages. These are not
  firewalls, but they show that "a proxy answers with a Modbus exception" is old. Background, not pre-emption, for
  the narrow mechanism.
- Incremental TCP checksum update after a same-length payload rewrite is old and generic: RFC 1624; US 7,453,874;
  US 7,441,179; US 10,651,974. These add no novelty on their own.

**I found no patent that claims rewriting the request FC to an illegal value so the real PLC generates the exception,
then remapping the exception code.** Only a web search was run, so treat this as "not found", not "does not exist".

---

## 3. Other patents examined

| Patent | Assignee / priority / status | Access | Relevance |
|---|---|---|---|
| US 11,546,295 B2, "Industrial control system firewall module" | A*STAR (Singapore), prio 2018-03-29, active to 2039 | Description excerpt; claims not read | Modbus DPI that checks the FC and register/value per PLC rules and drops/rejects bad packets. No exception response, no FC rewrite, no write-ack tracking, no FPGA. Background for any Modbus DPI claim. NO OVERLAP with the distinctive parts of C1-C6. |
| US 10,148,761 B2, "System-on-chip data security appliance" | Web Sensing LLC, prio 2015-04-09, active to 2036-08-31 | Description; claims not read | **Closest to C4.** In a single-chip SoC, the FPGA control plane is isolated from the processing cores, configuration becomes inaccessible to the cores, and the FPGA logic inspects, modifies, drops, or forwards traffic. The examples include a guard next to SCADA in a power/chemical plant. **OVERLAPS C4** (the broad SoC-FPGA isolation idea). Read claims 1+ before asserting any C4 claim. |
| US 10,834,094 B2 / US 11,722,495 B2 / EP 3823425 B1, "Operator action authentication in an ICS" | Bedrock Automation, prio 2013-14, active | Snippets only | Operator action requests (setpoint changes, actuator commands) are signed by an action authenticator and verified before execution. **Partial overlap with C6** (cryptographic binding of an operator action to a command). The snippets show no held bytes at an inline gate, no digest-plus-deadline, and no hardware release. Read claims. |
| US 2013/0212669 A1 | Expired/abandoned | Snippet | Hash codes over command units in an ICS protection network. Background for C6 hashing. |
| WO 2016/206947 A1 | n/a | Snippet | ICS security gateway that checks token validity periods. Background for the C6 deadline. |
| US 5,774,378 (Foxboro "self-validating sensors") | prio ~1993, expired | Snippet | Uncertainty grows with the time since the measurement. **Prior art for the "uncertainty widens with age" element of C3**, but not used by an inline enforcer. Kalman-filter covariance growth is textbook. |
| US 7,293,400 B2 / EP 1650616 B1; US 5,115,396 | Older | Snippets | Validation gates from physical rate limits; decaying error limits. Background for C3. |
| US 12,140,915 B2 (McCarson, generative/agentic AI for industrial equipment control) | granted 2024-11-12 | Snippet | AI agents that issue control commands and alter recipes. No inline hardware gate found. Background for C5. |
| US 2025/0021061 A1 (deterministic industrial process control) | application | Snippet | An AI sets setpoints next to a legacy PLC/BMS, with checks against constraints. Background for C5 (software). |
| US 12,775,684 (AI traceability and control, granted 2026-10-27); US 12,619,741 (agentic policy enforcement); US 12,670,274 (securing agentic AI operations, human approval workflow); Daon agent tool-authorization patents | various, 2025-26 | Snippets/Justia | Intercept agent tool calls, block or quarantine, and invoke human approval. These are generic IT agent governance with no OT/PLC and no hardware. **Partial overlap with C5/C6 in concept** (intercept plus human approval of agent actions). The OT, hardware, and wire-level elements are not shown. |

Non-patent items to cite as prior art (they limit novelty even though they are not patents): the Tofino/EAGLE Modbus
TCP Enforcer (DPI, FC and register whitelists, drops writes; **second pass confirmed its 2009 datasheet lists "Modbus exception reply on blocked traffic"**, see
section 5.1); Lanotte/Merro et al., "Industrial Control Systems
Security via Runtime Enforcement" (ACM TOPS 2022: FPGA-implemented runtime enforcers between PLC and plant), which
bears on C4/C5; "Plug in the Safety Chip" (constraint enforcement for LLM robot agents), which bears on C5.

Searches that found **no** patent hits: write tracking that confirms on response and marks uncertain on
timeout/connection loss (C2); age-widened admissible intervals in an inline enforcer (C3); LLM/AI-agent plus PLC
inline hardware gate (C5); digest-bound held-command approval with a deadline in an OT gate (C6). Vendors checked in
queries: Belden/Tofino/Hirschmann, Honeywell, Fortinet, Rockwell, Siemens/Schneider (indirectly). The only claimed
art relevant to C1 that turned up was Rockwell's. Claroty, Nozomi, Dragos, Waterfall, Owl, Bayshore, Mission Secure,
Hitachi, Mitsubishi, Moxa and Cisco were in the target list, but no specific hits came up. Those assignees were
**not** searched exhaustively.

---

## 4. Verdict table

| Claim | Verdict | Closest patent(s) | Confidence |
|---|---|---|---|
| C1 broad (protocol-level reply instead of drop/RST) | **PRE-EMPTED** (prior art since 2006; Modbus-specific since the 2009 Tofino datasheet) and **claimed in an active patent** | Tofino Modbus TCP Enforcer (2009); Rockwell US 7,990,967 cl.31/36/63 (active to ~2030-01-14); US 8,774,186 cl.25-33 (expiry ~2026-09-12) | High |
| C1 narrow (FC→0x7F so the real PLC raises the exception, remap to 03, no injection, no seq/ack change) | **OPEN as a mechanism, but OVERLAPPING in function** with the Rockwell spoof-response claims. Counsel should decide FTO against '967 until 2030. | Rockwell '967/'186; US 2015/0156286 A1 (gateway-generated Modbus exception); RFC 1624 / US 7,453,874 (checksum) | Medium (no claim found reciting the rewrite-to-illegal-FC trick; search was web-based) |
| C2 response-confirmed write tracking | **OPEN** (no patent found) | none close; US 6,233,626 (write reservation timers) is distant | Low-medium (limited search; "stateful" ICS DPI is common, so check Claroty/Nozomi filings) |
| C3 age-widened admissible intervals in an enforcer | **OPEN as a combination**. The element "uncertainty grows with age" is old. | US 5,774,378 (expired); Kalman covariance (textbook) | Medium |
| C4 FPGA enforcer isolated from a compromised APU on the same SoC | **OVERLAPPING** | Web Sensing US 10,148,761 (active to 2036); Lanotte/Merro FPGA enforcers (non-patent) | Medium (claims of '761 not read) |
| C5 hardware gate for AI/LLM-agent commands to PLCs | **OPEN** in the OT-plus-hardware form; generic agent intercept is crowded | US 12,775,684; US 12,619,741; US 12,670,274; US 12,140,915 | Medium-low (very active 2025-26 filing area; unpublished applications are invisible for 18 months) |
| C6 digest-bound approval with deadline released by hardware | **OPEN as a combination**; partial overlap | Bedrock US 10,834,094 / 11,722,495 (signed operator actions); WO 2016/206947 (token validity) | Medium-low |
| Madisetti family (US 12,299,087 / 12,443,684 / 12,493,669 / 12,664,237) | **NO OVERLAP** with C1-C6 (PLC-internal secure-write format) | n/a | High |

### Expiry and priority notes for C1
- Rockwell US 2006/0155865 A1 (published 2006) and US 7,990,967 are prior art against any broad C1 claim. The
  priority of 2005-01-06 is well before ours.
- US 7,990,967: Google lists it as active, adjusted expiry **2030-01-14**. Its spoof-response claims (31, 36, 63)
  are the main FTO item for the refusal behaviour. Confirm maintenance-fee status on USPTO Patent Center.
- US 8,774,186: adjusted expiry **2026-09-12** (likely lapsed by 2026-11-08; confirm). US 9,369,436 and US 10,091,208
  are listed as expired (Jan 2026).
- Suggested framing for a filing: claim the specific in-band transformation (request FC rewritten to an
  unimplemented code, the target's own exception reused with its code remapped, same-length edits with incremental
  checksum, no injected segments, TCP sequence space unchanged), combined with C2/C3 state. Do not claim "respond
  with an exception instead of dropping".

### Gaps / next steps
- Read the full claim sets of US 10,148,761, US 10,834,094, US 11,722,495, US 2015/0156286.
- Run assignee-restricted queries in USPTO PPUBS (CPC H04L63/0245, H04L63/1441, G05B19/4185, G05B19/05) for
  Claroty, Nozomi, Dragos, Waterfall, Siemens, Schneider and Honeywell, using "exception response" and "Modbus".
- ~~Check the Tofino Modbus TCP Enforcer manual~~ Done in the second pass (section 5): confirmed.

---

## 5. Second pass (2026-11-08, later the same day)

Method: re-read the four Madisetti patents on Google Patents (same result as section 1). Read claims 1-67 of
US 7,990,967 from the page. Ran direct Google Patents queries through the `patents.google.com/xhr/query` JSON endpoint
for the first three queries; later queries hit HTTP 503 rate limiting and fell back to web search. Extracted the text
of the Tofino Modbus TCP Enforcer datasheet PDF with pdftotext.

### 5.1 C1: new and confirmed prior art

- **Tofino Modbus TCP Enforcer datasheet (MTL/Byres Security, (c) 2009), non-patent.** The "options" list includes
  "Modbus exception reply on blocked traffic" and, separately, "TCP Reset on blocked traffic". This is a commercial
  firewall answering a blocked Modbus/TCP request with a Modbus exception instead of drop/RST, published by 2009. **It
  pre-empts the broad Modbus form of C1** on its own, independently of Rockwell. The datasheet does not say how the
  reply is built. The Tofino is a stateful L2 bridge, so the device almost certainly originates the frame and adjusts
  TCP state. Nothing suggests it forwards a rewritten request to the PLC. Source:
  mtl-inst.com/images/uploads/datasheets/tofino/DS-LSM-MBT.pdf.
- **US 7,990,967 B2 claims, now fully read.** There are 14 independent claims: 1, 23, 24, 28, 30, 31, 36, 37, 43, 57,
  59, 62, 63, 64. Cl.1 is generic intercept/compare/restrict for a second protocol embedded in a first. The
  C1-relevant claims are 31/63 ("encapsulating a spoof response packet that simulates a response from the target
  device"), 36 (spoof filled with bogus information) and 6 (signal back to the source that the packet was halted).
  This confirms section 2.
- **Bayshore Networks (now OPSWAT) US 10,476,844 B2**, "Content-aware firewalling, policy regulation, and policy
  management for industrial networks". Priority 2014-09-16, granted 2019-11-12, active to about 2035-09-16. Access:
  description read, claims not read. Policy dispositions include DENY (block) and **MODIFY, which changes "parameters
  or data elements in the transaction before passing it on"**, plus SET/session variables that keep dynamic state.
  The description has no exception response to the client and no FC rewrite to an illegal code. **Relevance to
  narrow C1: OVERLAPS in kind.** It is prior art for "an inline industrial firewall rewrites fields of a transaction and
  forwards it". Our step of rewriting the FC so that the PLC refuses is a specific use of a MODIFY-type action. Read
  its claims before filing. Also partial background for C2 (stateful session variables), with no echo-confirmation
  semantics seen.
- **US 7,657,938 B2** (Palmer et al., filed 2004-05, "protecting computer networks by altering unwanted network data
  traffic"). Access: abstract and application snippets only. An IPS substitutes benign bytes for malicious bytes in
  the stream and forwards, with checksum correction, instead of dropping. Generic IT. **This is prior art for
  "neutralise in place and forward so the session survives"**, which is the core of narrow C1 minus the Modbus
  specifics. Combined with Tofino (exception reply) or the Modbus spec (an unsupported FC yields exception 01), an
  examiner could argue obviousness. **This is the strongest obviousness risk for narrow C1.**
- US 2007/0025374 A1 (TCP normalization engine) and WO 2018/226919 A1 (dynamic TCP stream modification) show that
  in-line payload modification with seq/ack fix-up is known. Our design avoids seq/ack fix-up by keeping lengths equal,
  which helps distinguish it but is still a small step.
- Secure Crossing US 9,100,324 B2 (prio 2011, expired). Description read. Its ICS firewall drops silently or sends a
  TCP RST on reject, with no protocol exception. It is a useful contrast showing that drop/RST was the norm.
- A*STAR US 11,546,295 B2 (description read). Drops or rejects only, no exception, no rewrite.

**Google Patents direct queries (xhr endpoint) that ran:**
`modbus firewall "exception response"` (9 hits, none relevant);
`modbus "function code" (block|deny|reject) exception (firewall|gateway|filter)` (about 81 hits reviewed, none that
send an exception or rewrite the FC; mostly Chinese DPI/ACL filters that discard);
`industrial firewall ("exception response"|"error response"|"spoof response") (blocked|denied|unauthorized)`
(only Rockwell US 8,774,186 is on point);
`(modbus|"industrial protocol"|DNP3) ("exception response"|"exception code") (firewall|security device|inline) (block|deny)`
(23 hits, none on point).
**Result: no patent found that claims rewriting the request FC to an unimplemented code so the PLC itself raises
the exception, then remapping the exception code.**

### 5.2 C2-C6: additions

- C2: the A*STAR '295 "sequence check" tracks each command step and marks it complete once its response is
  forwarded. ETRI US 9,298,175 B2 (prio 2013) matches Modbus requests and responses in a session table keyed by
  transaction ID. These are request/response correlation for anomaly detection. Neither has a write that stays
  "pending until echo" and becomes "uncertain on timeout/connection loss" and then feeds later admission decisions.
  Verdict unchanged: **OPEN, low-medium confidence.** The correlation element itself is known.
- C3: **Foxboro US 5,570,300** (sibling of US 5,774,378, expired) claims that uncertainty grows by "the time
  difference multiplied by the maximum observed rate of change". That is exactly the widening rule. The element is
  prior art, so only its use as an admission envelope in an inline enforcer is new. US 7,302,362 B2 (time-varying
  acceptable bounds for sensor reporting) is further background. Verdict: **OPEN only as a combination; the core
  formula is pre-empted.**
- C5: WO 2026/102013 A2 (PCT filed 2025, applicant not identified) covers verification and validation of LLM+RAG in
  industrial automation systems integrated with controllers. Snippets describe model-consistency and robustness checks,
  not a wire-level gate on runtime writes. US 12,254,082 B1 covers pre-execution rule validation of AI commands
  ("safe AI"), generic. Verdict unchanged: **OPEN in the hardware/OT form**, crowded in software.
- C6: US 12,688,261 (granted 2026-07-21, assignee not identified; "authorizing invocation of a tool by an autonomous
  AI agent"). Snippets describe a delegation artifact with a hash/signature bound to the agent's runtime and a
  "bounded validity interval". It is IT, not OT, and no held-bytes digest released by hardware was seen. This adds to
  the partial overlap with C6, so read its claims. Bedrock US 10,834,094 claims were not re-read (Google Patents
  returned 503).

### 5.3 Revised C1 verdicts

| C1 form | Verdict | Closest art | Confidence |
|---|---|---|---|
| Broad: firewall answers a blocked industrial request with a protocol-level reply | **PRE-EMPTED** | Tofino Modbus TCP Enforcer datasheet (2009, Modbus exception reply); Rockwell US 2006/0155865 / US 7,990,967 cl.31/36/63 (spoof response, active to about 2030) | High |
| Narrow: FC rewritten to 0x7F, the real PLC raises the exception, the gate remaps it to 03, same-length edits, incremental checksum, no injected frames | **OPEN as a specific mechanism, but with obviousness exposure** (Tofino exception reply + in-place neutralisation of US 7,657,938 / Bayshore MODIFY + Modbus spec's exception 01 for unimplemented FCs). FTO overlap with Rockwell '967 is functional only. | Bayshore US 10,476,844; US 7,657,938; Rockwell '967 | Medium |

Filing advice (technical, not legal): build the narrow claim around what the prior art lacks. (1) No frame is
originated by the gate, so it holds no TCP state and needs no seq/ack fix-up. (2) The refusal is produced by the target
itself, which proves the PLC was reachable and saw the request. (3) Pending-write bookkeeping (C2) closes on the
exception echo. (4) This fits a stateless FPGA pipeline. Argue (1), (2) and (4) as technical effects.
