# Agent command gate: novelty checks before committing to a hardware direction (2026-11-08)

Follows `reports/Hardware directions for inline OT gate.md`, which listed checks to run before claiming anything new.
Detailed notes, with sources and the access level actually read for each: `research_notes/Novelty checks for inline OT
gate/` (`academic_sweep.md`, `patents.md`, `commercial_and_plc.md`, `zynq_kria_isolation.md`). Patent findings are a
technical overlap assessment, not legal advice.

## Search limits

Semantic Scholar was rate-limited throughout. Google Scholar, IEEE Xplore/ACM full text, Justia and FreePatentsOnline
blocked automated access. USPTO Patent Public Search and Espacenet were not queried. SAIN had no citation sweep. SRIM,
Pearce Smart I/O, Raj & Jin (e-Energy 2025), the Fowler thesis and arXiv 2606.27231 were read at abstract level only. The
Tofino datasheet and Configurator manual were read in full; the Moxa and TXOne manuals are gated. Every "appears open"
below means "not found under these limits".

## Verdicts

| Claim | Verdict | Prior art that decides it |
|---|---|---|
| **C1 broad:** refuse a blocked Modbus request with a protocol exception instead of drop/RST | **Pre-empted** | Tofino Modbus TCP Enforcer: "Modbus exception reply on blocked traffic" (datasheet 2009; manual 2019 §7.3.1 injects the exception itself and warns of loss of communication). Rockwell US 7,990,967 (priority 2005, listed active to ~2030) claims spoof responses to blocked industrial requests: a freedom-to-operate question, not only novelty. |
| **C1 narrow:** rewrite the function code to 0x7F so the PLC itself raises the exception, rewrite the reply to code 03; no injected frames, no seq/ack change | **Mechanism appears unpublished, but partly anticipated and exposed to an obviousness argument** | Rash et al. 2005 (Snort_inline): rewrite application bytes in flight so the server returns its own error, explicitly preferred to RST. US 7,657,938 (byte replacement with checksum fix). No Modbus or ICS instance found in products, IDS source, GitHub proxies or patents. |
| **C2:** writes pending until the PLC's echo, uncertain on timeout or connection loss, used in later decisions | **Partly pre-empted** | Request/response pairing and out-of-sequence checks exist: Tofino State Check, SCADAWall, Raj & Jin 2025 (delayed or unsolicited responses in a Tofino data plane), transaction-ID IDS rules, US 9,298,175. No product or paper found that feeds an uncertain post-timeout state into later admission decisions. |
| **C3:** admissible plant intervals widening with the age of the reading | **Open only as an application** | The maths is old: ModelPlex, Simplex reachability, Foxboro US 5,570,300 / 5,774,378 (uncertainty grows with elapsed time times maximum rate). |
| **C4:** fabric/R5 enforcer isolated from Linux on the same Zynq US+ | **Appears open as an evaluated result; the mechanisms are documented** | AMD docs (XPPU, XMPU, TrustZone, XMPU_PL, authenticated boot) show it can be configured but is off by default (`zynq_kria_isolation.md`). Gross et al. 2022 tested the opposite direction (from the PL). US 10,148,761 (FPGA in an SoC isolated from the cores) overlaps the concept. Whether the Kria SOM accepts the custom boot firmware and eFUSE programming needed is undocumented. |
| **C5:** a separate hardware device enforcing policy on AI-agent commands to PLCs | **Appears open in the hardware/OT form; fast-moving** | arXiv 2606.27231 (content-bound tokens for an LLM controlling lab equipment, software), PlantShield 2026, Smart I/O, software agent-gating patents. Re-check before any submission. |
| **C6:** human approval bound to the exact held bytes with a deadline, released by the gate | **Appears open only as an OT/hardware combination** | ProtectIOn (exact values, no deadline), Approved Too Late (freshness, no binding), arXiv 2607.14155 (approval binds hash and time), Bedrock US 10,834,094 (signed operator actions), US 12,688,261 (IT agent authorisation with a hash and bounded validity). |

### Second academic pass: three close neighbours, two posted in the last three months

These tighten the C2, C3, C5 and C6 rows above:
- **D'Agati et al., arXiv 2610.27971 (20 Oct 2026), XAIR** (most of the full text read): a software edge service sending
  Modbus/TCP to OpenPLC; a released intent "stays in Unknown effect" until the controller reports back, and intents carry
  a freshness window and deadline (age of the decision, not of the sensor reading). No uncertain state on PLC timeout or
  connection loss, no protocol exception, no human approval. **Closest academic neighbour to C2; must be cited.**
- **IETF draft-das-ot-actuation-finality-00 (27 Aug 2026)** (full text read): agent writes held as not yet effective; an
  "actuation sink" in front of the I/O (a JSON-to-Modbus gateway can be the sink) refuses failing writes; approval bound to
  a hash of canonical device/tag/value with a short expiry (5 s in the example) and a human checker. Software or HSM, no
  FPGA, digest of the meaning rather than the held bytes, no wire-level refusal, no PLC confirmation. **Partly pre-empts
  C6 and narrows C5.**
- **Cano Córdoba et al., "Safety Shielding under Delayed Observation", ICAPS 2023** (abstract only): reachable states grow
  with observation delay. With real-time reachability Simplex work, **C3 is known as a concept**; only the inline,
  per-register mechanism in a gate could be new.
- **Unread risk for C2:** SSRN doi:10.2139/ssrn.7567359, "Localizing Divergence in OT: Authorized Intent, Commanded State,
  ... Reported Observation" (403, no abstract).
- Forward citations of Lanotte (CSF'20, TOPS'22), SAIN (19), P4Ward and Approved Too Late screened: nothing further.
  SRIM confirmed by the CIGRE D2 2026 Special Report as "an FPGA-accelerated SFP module" doing DPI on the IEC 61850
  process bus; full text still unobtainable.

Updated status: C2 **partly pre-empted** (XAIR, Tofino State Check, Raj & Jin); C3 **concept known**, open only as an
inline mechanism; C5 **open only in hardware form** (software versions: the IETF draft, arXiv 2606.27231, XAIR); C6
**partly pre-empted** (IETF draft: hash-bound approval with expiry). What remains distinctive for C5/C6 is a hardware
device that holds the actual frame bytes and enforces the deadline itself.

## Practical findings for direction 1 (real-PLC refusal)

- Function code 127 is **reserved** in the Modbus spec (not user-defined; user-defined ranges are 65-72 and 100-110), and
  an unsupported code must get exception 01. OpenPLC and libmodbus do exactly that and keep the connection open. 127 remains
  the best choice: user-defined codes can trigger real functions (OpenPLC uses 0x41-0x45 for debug, including forcing a
  variable) and 0x5A/0x5B/0x7D/0x7E are Schneider programming codes.
- **False alarms:** Snort's Modbus inspector rule 144:3 ("Reserved Modbus function code in use", also in Cisco FTD/ISA3000)
  fires on every refused write on the gate-to-PLC link; Quickdraw SID 1111014 fires on three exception-01 replies within
  60 s. Suricata's stock rules and Zeek do not alert.
- **Non-conforming devices exist** (older Opto 22 firmware sent an invalid reply; AutomationDirect ECOM100 reportedly
  closes the socket), so the RTL needs a fallback that builds the exception itself after a timeout, and must handle a PLC
  closing the connection.
- **Exception 01 does not prove the PLC is running:** WAGO PFC200 in STOP answers every request with 01. Treat 0xFF with
  01, 04, 0A or 0B as "refused, not executed", and read nothing else from it. TCP-to-serial gateways may answer 0A/0B.
- Siemens S7 may set server STATUS 16#8381, which user logic could alarm on (from memory of the manual, unverified).
- Make the client-facing code configurable (01/03/04); the spec's wording for 01 arguably fits a policy refusal.
- Test order: OpenPLC, CODESYS on a Raspberry Pi, Siemens S7-1200, Schneider M221 (loose function-code handling), with a
  libmodbus/pymodbus server as baseline and Snort 3 running on the link to measure false alarms.

Second pass on products and PLCs (merged into `commercial_and_plc.md`):
- The Tofino CMP User's Guide v1.7.0 (2012, §6.4.2) gives the exception option "to prevent session lock up" and never states
  the exception code; its State Tracking checks ordering, not acknowledgement of writes. Hirschmann EAGLE has the same
  choice. Moxa EDR-G9010 defaults to Reset.
- Snort and Suricata can already rewrite bytes in place without changing length (`replace`), so the request-rewrite half
  alone is easy to reproduce; the defensible part is the combination (same-length rewrite so no seq/ack changes, the PLC's
  exception rewritten back with per-request state, acknowledgement tracking of every write).
- An inline Snort IPS on the gate-to-PLC segment with rule 144:3 enabled would **drop** the rewritten request. Nozomi and
  Radiflow would likely flag code 127 as well. Code 127 is listed for legacy products, so old Modicon equipment needs care.
- A lower-alarm alternative to evaluate: turn a refused write into a read of zero registers (the PLC must answer exception
  03, which is also the code we return); trade-offs in the notes.
- No crash advisory was found for a well-formed request carrying a merely unknown function code.

## What this changes

1. **Direction 1 survives in narrowed form.** Claim the in-band transformation (the PLC raises the refusal, the gate never
   creates a frame or holds TCP state, so it fits a stateless FPGA pipeline and the reply proves the PLC received the
   request) together with the response-confirmed pending state, not "refusal by exception". Cite Tofino, Rash 2005 and the
   Rockwell patent, and measure against all of them: drop (P4Ward), FCS corruption (Iwasawa), RST, and a Tofino-style
   injected exception. The Tofino manual's own warning about loss of communication is a measurable point of comparison.
2. **The freedom-to-operate question on Rockwell '967 should go to a patent attorney** before any commercial use;
   academic publication is not blocked by it.
3. **Direction 2 is the clearest open evaluated result**, but depends on whether the Kria SOM can run custom FSBL/PMUFW
   with the isolation configuration and authenticated boot. That is a documentation and board question to settle first.
4. Novelty for C2, C3 and C6 rests on combinations; present them as the system's design, not as standalone inventions.

## Still to read

Claims of Bayshore US 10,476,844, Bedrock US 10,834,094, US 12,688,261, US 7,657,938 and claim 1 of Rockwell '967 (and its
maintenance-fee status); full texts of Raj & Jin 2025, the Fowler thesis, arXiv 2606.27231, SRIM and Pearce; the full
Tofino manual (exception code used); assignee searches in USPTO for Claroty, Nozomi, Dragos, Siemens, Honeywell, Moxa.
