# Commercial and open-source Modbus refusal behaviour, and PLC handling of unsupported function codes

Date of check: 2026-11-08. Scope: (A) how industrial firewalls and IDS/IPS refuse blocked Modbus/TCP requests; (B) how PLCs answer an unsupported function code, and whether FC 127 traffic would trip common IDS rules.

Planned approach being checked: the inline gate refuses a write by rewriting the function code to 0x7F, with an incremental checksum update. The PLC is expected to answer `0xFF / 01`. The gate rewrites that answer to `orig_fc|0x80 / 03` for the client, the TCP session stays up, and acknowledgements of permitted writes are tracked.

Access-level legend:
- **P-doc**: public vendor document, read directly.
- **P-src**: public source code, read directly.
- **P-snip**: public page seen only as a search snippet or summary, not read in full.
- **Gated**: manual behind a login or a WAF, not read.
- **Memory**: my prior knowledge, not re-verified in this session.

---

## Part A: How products refuse a blocked Modbus request

| Product | Refusal behaviour (documented) | Checks PLC responses / acknowledgements? | Source | Access |
|---|---|---|---|---|
| Belden/Hirschmann **Tofino Xenon + Modbus TCP Enforcer LSM** | Configurable per connection. Deny by default; blocked traffic is "blocked and reported". **Tofino CMP User's Guide v1.7.0 (2012), section 6.4.2**, lists three behaviours for an illegal or filtered message: (a) drop and do nothing; (b) drop and "send a TCP reset message to both Modbus devices"; (c) drop and "send a Modbus TCP exception response (if appropriate) to the Modbus device that generated a blocked message". Both (b) and (c) are justified as preventing "session lock up on certain loosely written Modbus systems". The guide adds that "not all illegal Modbus TCP messages have a defined exception response". **The exception code is not stated.** | **Partly.** "State Tracking" blocks out-of-sequence traffic: two commands without an intervening response, a command from the slave, or a response from the master. That is request/response alternation, **not acknowledgement accounting**. Sanity checks cover FCs 1–6, 15, 16 and 20–24; the MBAP header is always checked. | Belden techdata PDF; **Tofino Argon CMP User's Guide v1.7.0** (icscsi.org library), pp. 228–234 | P-doc (datasheet and full user guide) |
| **Hirschmann EAGLE20/30/40** (HiSecOS DPI, Tofino lineage) | The CLI `dpi modbus addprofile` takes `exception` ("Device exception message") and `reset` ("Reset connection message") parameters, plus `sanity-check`, `function-code-list` and `unit-identifier-list`. This is the same exception-or-RST choice as Tofino. | Not documented in the excerpt | manualslib.de EAGLE CLI reference, p. 516 | P-snip |
| **Moxa EDR-G9010** (also IEF-G9010, EDF-G1002-BP, IEC-G102-BP: same MX-ROS DPI family) | **EDR-G9010 manual v2.0, read directly**: the policy and ADP actions are **Accept**, **Monitor** (accept and log), and **Reset**, where "the packet will by [sic] dropped by the firewall ... The session will also be disconnected". The protocol-filter default action is **Reset**. The Modbus function code is entered as 0–255. Security package v2.0.48 "Changed the action for the Master Query and Slave Response command types from 'Drop' to 'Reset'"; the entry is generic, not DNP3-specific. Package v3.0.23 fixed "The system crashes when receiving a Modbus packet with an incorrect length", which shows that **the firewall itself** can be the fragile element. No Modbus exception synthesis. | Partly: rule "command types" include *Slave Response*, so responses can be filtered. No acknowledgement tracking documented. | EDR-G9010 manual v2.0, pp. 185–196; security package release history (moxa.com) | P-doc |
| Phoenix Contact **mGuard** (fw 8.4+, 10.x) | Modbus TCP rule sets offer **Accept or Drop only**. Drop means packets "are discarded, rendering the TCP connection unusable". Unmatched packets are discarded. Reject exists only in the general (non-Modbus) firewall. | **No.** DPI checks incoming requests, and responses are not inspected again. | mGuard 10.5 manual, Network Security menu (help.mguard.com) | P-doc |
| Siemens **SCALANCE S / SC600** | No Modbus function-code DPI documented. A SANS product review says SC600 "does not attempt to be a full-blown NGFW". Effectively L3/L4 only: drop or reject at the port level. | No | SANS SC600 product review (assets.new.siemens.com) | P-snip |
| **Fortinet FortiGate** (OT / industrial signatures, App Control) | IPS signature actions are **block** (silent drop), **reset**, **monitor/pass** and **quarantine**. OT virtual-patch profile allows pass or block. Modbus function-level app signatures need the OT Security Service license. No Modbus exception synthesis. | Some signatures key on responses, e.g. FortiGuard IPS 15291 fires on "3 exception code 01 responses ... in 60 seconds". No acknowledgement tracking. | FortiOS admin guide / 7.6.0 new features (docs.fortinet.com); FortiGuard encyclopedia | P-snip |
| **Cisco ISA3000** (FTD / Snort 2 and 3 Modbus inspector) | Snort rule actions: drop/block silently, or **reject** (drop plus TCP RST / ICMP unreachable). Inspector rules GID 144: 1 = length mismatch, 2 = non-zero protocol ID, **3 = reserved function code in use**. | The inspector parses both directions (length checks on responses). No acknowledgement tracking. | snort.org readme-modbus; Cisco "Modbus Preprocessor" doc; Cisco TechNote 222693 (Snort 3 rule actions) | P-doc / P-snip |
| **Palo Alto** (Modbus App-IDs, e.g. `modbus-write-single-register`) | Security-policy actions: allow, deny (uses the App-ID's default deny action), drop, reset-client, reset-server, reset-both. No Modbus exception synthesis. | No acknowledgement tracking documented. | App-IDs for ICS/SCADA datasheet; LIVEcommunity lab article; PAN-OS policy actions | P-snip + Memory (action list) |
| **TXOne EdgeIPS / EdgeIPS Pro / EdgeFire** | Deny action has connection options. The FAQ recommends "**drop** connection for optimal compatibility". Modbus advanced settings exist in protocol filter profiles. No exception synthesis found. | Not documented | help.txone.com FAQs EdgeIPS Pro (Q32, Q34); EdgeIPS Pro admin guide 2.2 (policy actions: Accept, Accept and Log, Deny and Log, Advanced Filter; "Drop Malformed" per ICS protocol) | P-doc |
| **Stormshield SNS** (extra, found incidentally) | The "function code denied" alarm can be switched to **Block**. The resulting wire behaviour is not stated. | Not documented | documentation.stormshield.eu, "Building a customized security policy" | P-doc |
| Secure Crossing **Zenwall** | Nothing public found | — | — | Gated / not found |
| **Bayshore** (SCADAfuse / NetWall / OTaccess, now OPSWAT) | Marketing only: application-layer policy and "read-only / read-write" controls for Modbus. Refusal mechanism undocumented. | — | Carahsoft page, OTaccess datasheet | P-snip |
| **Suricata** (IPS) | Modbus keywords (`modbus: function ...`, app-layer events). `drop` is silent. `reject` sends a **TCP RST (or ICMP unreachable) to the sender**; `rejectdst` / `rejectboth` send to the receiver or both. In IPS mode, reject also drops. There was a bug where reject degraded to drop in firewall mode (redmine #8390, marked resolved). **No Modbus exception synthesis.** | Partly, as IDS checks: `modbus.unsolicited_response` and `modbus.value_mismatch` ("Value field in Modbus Response does not match with Modbus Request", i.e. write-echo consistency) | docs.suricata.io rules intro; OISF `rules/modbus-events.rules`; `rust/src/modbus/modbus.rs` | P-doc / P-src |
| **Snort 3** | `reject` = drop, block the flow, and send TCP RST or ICMP unreachable (configured via `reject = { reset = 'both', control = ... }`). `drop` / `block` are silent. No Modbus exception synthesis. | No | Cisco TechNote 222693; snort-users list | P-snip |
| **Zeek** | Passive only, no refusal. The Modbus analyzer logs unknown FCs as `unknown-<n>` and exceptions as `*_EXCEPTION`. No weird/notice for unknown FCs. | Logs request/response pairs (modbus.log) | zeek `src/analyzer/protocol/modbus/*.pac`, `scripts/base/protocols/modbus/main.zeek` | P-src |
| **containd** (tonylturner, open-source ICS NGFW, NFQUEUE) | Denied ICS command is **dropped inline**, later packets of that TCP incarnation keep dropping, and then "a best-effort **RST to each peer**". | Has a Modbus request/response pairing anomaly detector (`pkg/dp/anomaly/modbus_pairing.go`) | github.com/tonylturner/containd `docs/mkdocs/dataplane-enforcement.md` | P-src |
| **modbusfw** (61131 / sourceforge, iptables match) | Netfilter match on FC / unit / ref / length, combined with iptables DROP or REJECT (RST). Its docs give a deny example for FC 0x7E on Modicon. | No | modbusfw.sourceforge.net; github 61131/modbusfw | P-snip |
| **PlcSentinel** (mosafariuk, Python inline DPI proxy) | **Synthesizes Modbus exceptions**: `orig_fc|0x80` with **01** (blocked function) or **03** (blocked value/range). Session kept for policy denials; malformed MBAP or rate-cap violations tear the session down. | Not observed | github.com/mosafariuk/PlcSentinel `plcsentinel/gateways/modbus_dpi_proxy.py` | P-src |
| Ursescu/modbus-firewall (freemodbus on ESP32/AVR) | A terminating Modbus stack, so it presumably answers with exceptions. Not verified. | — | github.com/Ursescu/modbus-firewall | P-src (tree only) |

### Observations for Part A
- **The dominant commercial refusal is silent drop or TCP reset.** That covers mGuard, Moxa, TXOne, Fortinet, Palo Alto, Cisco/Snort, Suricata and containd.
- **The Tofino lineage (Tofino Xenon, and Hirschmann EAGLE HiSecOS DPI) is the only commercial family found with a documented "Modbus exception reply on blocked traffic"**, alongside TCP RST as a separate option. It has been documented since at least 2012 (CMP guide v1.7.0). The exception code is undocumented publicly.
- **Why everyone else uses RST: TCP sequence state.** A bump-in-the-wire that *drops* request bytes leaves a sequence gap, so the client retransmits and the stream stalls. mGuard says this outright: Drop renders "the TCP connection unusable". Moxa moved from Drop to Reset (v2.0.48). Tofino justifies both RST and exception as preventing "session lock up". A middlebox that drops a request and injects a synthesized exception must also fake the server's ACK and shift sequence numbers for the rest of the connection, or terminate TCP as a proxy. **Rewriting the request to a same-length one avoids this entirely**: the PLC's own stack ACKs the bytes, and only the FC byte and checksum change in each direction. Of everything in this check, this is the most defensible technical differentiator.
- A few hobby or research proxies (PlcSentinel) synthesize `fc|0x80` with 01 or 03 directly at the proxy. In each case **the proxy itself fabricates the exception and terminates the request**. Nothing found forwards a mutated request so that the PLC produces the exception.
- **Response checking**: Tofino ("command and response", state tracking), Moxa (Slave Response command type) and Suricata (unsolicited_response, value_mismatch) inspect responses. **None documents tracking whether permitted writes were acknowledged as an enforcement or audit feature.** Suricata's value_mismatch, an IDS event, comes closest.

---

## Part B: The Modbus specification, and PLC behaviour on unsupported function codes

### Specification facts
Read directly from the Modbus Application Protocol Spec **V1.1b** (Dec 2006, mirror at cars.uchicago.edu). modbus.org's V1.1b3 PDF was blocked by a WAF and not read. As far as I know, V1.1b3 keeps sections 4–7 and Annex A unchanged; verify this when you have the b3 PDF.
- Function code field: "Valid codes are in the range of 1 ... 255 decimal (the range 128 – 255 is reserved and used for exception responses)". FC 0 is not valid.
- Section 5, categories: Public; **User-defined = 65–72 and 100–110** (confirmed); Reserved = "used by some companies for legacy products".
- **Annex A: reserved function codes: 8/19, 8/21–65535, 9, 10, 13, 14, 41, 42, 90, 91, 125, 126 and 127.** So **FC 127 (0x7F) is a Reserved function code**: not public, not user-defined.
- Section 4 / 6 server state diagrams: "Function code supported? NO → **ExceptionCode = 01**". The exception function code is the request function code + 0x80, so the expected answer to 0x7F is **0xFF / 01**.
- Exception 01 ILLEGAL FUNCTION: "not an allowable action for the server ... could also indicate that the server is in the wrong state to process a request". Note: a STOPPED PLC may therefore also answer 01. Exception 03 ILLEGAL DATA VALUE: "a value contained in the query data field is not an allowable value".

### Device behaviour

| Device / runtime | Documented or observed behaviour for unsupported FC (and FC 127) | Source | Access |
|---|---|---|---|
| **OpenPLC v3** (`webserver/core/modbus.cpp`) | Dispatch on `buffer[7]`; the final `else` calls `ModbusError(ERR_ILLEGAL_FUNCTION)`, which sets `fc|0x80` and code 01, so **0x7F → 0xFF/01**, and the connection stays open (the server loop only closes on a socket read error). Also a short frame (<8 bytes) → 01. **Caution: OpenPLC implements user-defined FCs 0x41–0x45 as debug functions, including 0x42 "Debug set trace (force variable)"**. 0x7F is not among them. | github thiagoralves/OpenPLC_v3 master, `modbus.cpp` lines 46–60, 164–170, 1203–1208 | P-src |
| **libmodbus** (`modbus_reply`, used by many Linux/Pi soft-PLCs and gateways) | `default:` → `MODBUS_EXCEPTION_ILLEGAL_FUNCTION`, "Unknown Modbus function code: 0x%0X". FC 7 is also answered with 01. | github stephane/libmodbus `src/modbus.c` ~line 1246 | P-src |
| **Siemens S7-1200 / S7-1500 MB_SERVER** | Supports FC 1, 2, 3, 4, 5, 6, 15, 16 (FC 23 on newer TIA/firmware per secondary sources). On an unsupported FC the server answers exception 01 and MB_SERVER reports STATUS 16#8381 "Function code not supported" (it shows on the PLC block output as a diagnostic). The connection is not closed. Third-party blogs conflict on the exact status-code mapping. | S7-1200 System Manual MB_SERVER status table (from memory); industrialmonitordirect.com blogs; Siemens forum post 126845 | Memory + P-snip (verify in manual A5E03099794 / TIA help) |
| **Schneider M340 / M580 / Quantum** (Unity/EcoStruxure) | Supported FCs per FAQ FA284826: 1, 2, 3, (4–7, 11, 12 depending on region/version), 15, 16, 22, 23, 43. Unsupported → 01 (standard). **Schneider uses reserved FC 90 (0x5A, UMAS) and 125/126 (0x7D/0x7E, legacy Modicon programming).** Quickdraw `modicon.rules` alerts on FC 90 program download/upload. 127 is not known to be used. | se.com FAQ FA284826; Quickdraw-Snort `modicon.rules`; modbusfw docs (deny 0x7E on Modicon) | P-snip / P-src |
| **Schneider M221** | FAQ FA295250 says FC02 is **not rejected** but answered as if it were FC01: an example of non-strict FC handling. Behaviour on other unsupported FCs is not documented publicly. | se.com FAQ FA295250 | P-snip |
| **Rockwell Micro800** (Micro820/850/870 Modbus TCP server) | Supported FCs 1, 2, 3, 4, 5, 6, 15, 16 (from memory). Unsupported FC behaviour not found in public docs; Rockwell KB 574730 is gated. | Rockwell KB 574730 (gated); secondary blogs | Gated / Memory |
| **WAGO PFC200** (750-8207, CODESYS 2 and e!COCKPIT) | "10 supported MODBUS services: FC1 to FC6, FC15, FC16, FC22, FC23". **Configurable: when the PLC is in STOP with "No data exchange", "MODBUS requests will always be answered by the exception response ILLEGAL FUNCTION"**, so 01 is not unique to unsupported FCs. Watchdog-expired state also returns 01 for some commands. Unsupported-FC handling is not stated explicitly. | WAGO 750-8207 manual pp. 277, 279, 298 (manualslib) | P-doc |
| **Beckhoff TwinCAT TF6250 / TS6250** Modbus TCP server | Gives access to the PLC memory areas. Supported FC list and unsupported-FC behaviour not retrieved; a blog maps ErrorID 1 to ILLEGAL_FUNCTION. | infosys.beckhoff.com TF6250; TS6250 PDF; blog | P-snip |
| **CODESYS** (Modbus TCP Slave device, e.g. CODESYS Control for Raspberry Pi) | CODESYS forum lists exception 01 as "function code is unknown by the server". No official statement on unsupported-FC handling retrieved. Expect 01 (spec-conformant stack), but **untested**. | forge.codesys.com thread 7f859f63b5 | P-snip |
| Counter-examples (non-conformant devices) | **Opto 22 SNAP PAC** (pre-fix firmware): unsupported FC produced "an invalid response rather than the expected ... Invalid Function Error" (KB83595, since fixed). **AutomationDirect ECOM100** reportedly replies with zero bytes and closes the socket on unmapped requests. | opto22.com KB83595; industrialmonitordirect blog | P-snip |

### Will FC 127 traffic trip downstream IDS? (between gate and PLC)

| Rule set | Fires on 0x7F request? | Fires on the PLC's 0xFF/01 reply? | Fires on the client-side 0x86/03 (etc.)? | Source |
|---|---|---|---|---|
| **Snort 2/3 Modbus inspector (also Cisco FTD/ISA3000)** | **YES: 144:3 "Reserved Modbus function code in use"** (0x7F is in its hard-coded list: 09, 0A, 0D, 0E, 29, 2A, 5A, 5B, 7D, 7E, 7F) | No (0xFF is not in the list; the length check skips unknown FCs) | No | snort3 `src/service_inspectors/modbus/modbus_decode.cc` lines 393–406; snort.org readme-modbus |
| **Digital Bond Quickdraw** (also in ET Open "emerging-scada"), SID 1111014 "Modbus TCP – Function Code Scan" | — | **YES, if 3 or more exception-01 responses from a server in 60 s** (`byte_test >=0x80` at FC, content 01 at offset 8, threshold 3/60 s by_src) | No (exception 03) | github digitalbond/Quickdraw-Snort `modbus.rules` line 33 |
| Quickdraw SID 1111006 / 1111007 (unauthorized read/write from !$MODBUS_CLIENT) | No (0x7F is not in its FC list) | — | Unchanged by the gate | same |
| **FortiGuard IPS 15291** | — | **Likely YES** (described as firing on 3 exception-01 responses in 60 s, same heuristic as Quickdraw) | No | fortiguard.com/encyclopedia/ips/15291 (snippet) |
| **Suricata stock `modbus-events.rules`** | No: `invalid_function_code` is only raised for FC 0 or ≥0x80 in a request (sawp-modbus `ERROR_MASK`); 0x7F is categorized RESERVED but not flagged | No: exception 01 is valid for any FC; requests and responses pair fine | No: exception 03 is flagged only for FC 7–14 and 17–19 | OISF `rules/modbus-events.rules`; sawp-modbus `lib.rs` lines 141–157, 505–527, 825–827 |
| Suricata custom rules using `modbus: function reserved` | **YES**, by design | — | — | Suricata Modbus keyword docs; ANSSI Suricata-Modbus presentation |
| Radiflow iSID "Invalid Modbus Function Code" (content/byte_test threshold ≥0x5A) | **Likely YES** | — | — | isid-analyst.radiflow.com ?p=2241 (snippet) |
| **Zeek** | No alert; logged as `unknown-127` | Logged as `unknown-255` with exception ILLEGAL_FUNCTION | Logged normally | zeek modbus `main.zeek` `build_func` |
| **Nozomi Guardian** (passive) | **Likely YES**: `SIGN:UNSUPPORTED-FUNC` ("An unsupported function has been used on the OT device", medium severity) and the learned-baseline `VI:NEW-FUNC-CODE` (a node uses a function code never seen before). A Schneider community thread shows Nozomi raising "Unsupported function code" warnings on M580-to-M580 traffic, so false positives already occur in practice. | Possibly (`SIGN:PROTOCOL-ERROR` is generic) | Unlikely | technicaldocs.nozominetworks.com protocol-validation alerts; community.se.com thread 513260 |
| **Tenable NNM / OT** plugin 114 | — | **YES** (Info severity): "MODBUS/TCP 'Illegal Function Code' Exception Code Detection" | No | tenable.com/plugins/nnm/114 |

**So yes, false alarms downstream are likely.** A Snort-based sensor (Cisco, pfSense/OPNsense Snort, Security Onion with Snort) on the gate→PLC segment raises 144:3 on every refused write. A Quickdraw or FortiGuard sensor raises "Function Code Scan" once refusals exceed 3 per minute per PLC. The client-side segment looks benign (exception 03).

---

## Verdicts

### (1) Is refusal by synthesized Modbus exception standard commercial practice?
**No. It exists, but it is a minority option.** The mainstream commercial and open-source refusal is a **silent drop or TCP RST** (mGuard Drop-only, Moxa Drop/Reset, TXOne drop recommended, Fortinet block/reset, Palo Alto drop/reset-*, Snort/Suricata drop/reject = RST, containd drop+RST). **Tofino Modbus TCP Enforcer is the one documented commercial product with a "Modbus exception reply on blocked traffic" option**, configurable alongside TCP reset; its exception code is not publicly documented. Small open-source proxies (e.g. PlcSentinel) fabricate `fc|0x80` + 01/03 at the proxy. So "answer the client with a Modbus exception and keep the session" has precedent (Tofino since at least 2012, and Hirschmann EAGLE DPI) and is not novel on its own. Do not claim "first to refuse with a Modbus exception" or "first to keep the TCP session".

### (2) Does anyone refuse by mutating the request so the PLC generates the exception?
**No instance found** in any vendor manual, release note, KB, Snort/Suricata/Zeek source, or GitHub proxy examined. Every exception-based refusal found is **synthesized by the middlebox**, which drops or absorbs the request. The closest relatives are drop-and-RST (containd) and the IDS value_mismatch / unsolicited_response pairing (Suricata), which are passive. **Tracking acknowledgement of permitted writes** is also not documented as a firewall feature: Tofino "state tracking" and Moxa "Slave Response" filtering inspect responses but do not advertise write-acknowledgement accounting. Caveats: Zenwall and Bayshore have no public docs, and patents were covered separately in `patents.md`. Generic same-length payload rewriting (Suricata/Snort `replace`) makes the request-mutation half look easy to reproduce. The defensible claim is the combination: a length-preserving refusal that needs no TCP sequence or ACK translation, a stateful rewrite of the PLC-originated exception back to the client, and per-write acknowledgement accounting.

### (3) Compatibility risks
1. **Reserved FC 127 trips IDS**: Snort 144:3 on every refusal; Quickdraw 1111014 / FortiGuard 15291 at ≥3 refusals per minute. Document this for operators, or offer an alternative FC. Trade-off: user-defined FCs (65–72, 100–110) are *more* dangerous because runtimes implement them (OpenPLC 0x41–0x45 includes a **force-variable** debug function). FC 0 is "not valid" and may be dropped or closed by strict stacks. 0x7F remains the best choice; vendor-reserved neighbours 0x5A/0x5B/0x7D/0x7E are Schneider programming codes and must be avoided.
2. **Non-conformant servers**: some devices drop silently, close the socket, or send malformed replies to unknown FCs (Opto 22 pre-fix, ECOM100). The gate needs a **timeout fallback**: if no 0xFF/01 arrives within T, synthesize `fc|0x80`/03 itself and mark the PLC as non-conformant. The gate must also handle a server-initiated FIN or RST after a mutated request.
3. **Ambiguous 01**: WAGO (STOP + "no data exchange") and spec-conformant "wrong state" servers return 01 for *everything*, so a 0xFF/01 reply proves only that the PLC did not execute FC 127. That is still a valid refusal confirmation, but the acknowledgement tracker should not infer the PLC's run state from it. The response must be matched on transaction ID, unit ID and FC 0xFF; also accept 0xFF with other codes (04 or vendor-specific) as "refused", and log them.
4. **Vendor-proprietary use of reserved codes**: Annex A reserves 127 for "legacy products". No current user of 127 was found, but a vendor stack *could* implement it (the Tofino allow-list notably includes 125/126 but not 127). Add an FC-127 probe to the per-device commissioning test.
5. **Gateways and serial**: Modbus TCP→RTU gateways (e.g. MGate) may not know how to frame or forward an unknown FC. They may answer 0x0A/0x0B (gateway path/target) or 01 themselves, and the PLC behind them never sees it. Handle 0xFF with 0A/0B as refused-by-gateway.
6. **Diagnostics on the PLC**: S7-1200/1500 MB_SERVER surfaces STATUS 16#8381 on the block (visible to the PLC programmer; it may latch an error bit in user logic that alarms on MB_SERVER ERROR). Schneider and others may increment diagnostic or exception counters (FC 8 counters on serial). Not a protocol break, but operators may notice it.
7. **Client-facing code 03**: harmless for Suricata (03 is flagged only for FC 7–14 and 17–19), and the spec text for 01 arguably fits a policy refusal better ("not an allowable action ... wrong state"). PlcSentinel uses 01 for blocked FCs and 03 for blocked values. Consider making the client-facing code configurable (01/03/04), and check SCADA driver reactions (some drivers disable tags on 02; none found for 03).
8. **M221 non-strict FC handling** (FC02 answered as FC01) shows that some PLCs map unknown or unsupported FCs to something else rather than rejecting them. Test 0x7F explicitly.

### First PLCs to test (ordered)
1. **OpenPLC v3 / OpenPLC Runtime on Linux or Raspberry Pi**: free; source confirms 0x7F → 0xFF/01, so it serves as the reference positive. Also test that it never treats 0x7F as debug.
2. **CODESYS Control for Raspberry Pi SL** (Modbus TCP Slave device): cheap; covers the CODESYS stack family (WAGO, many OEM controllers). Behaviour on 0x7F is undocumented, so it is a high-value test.
3. **Siemens S7-1200** (MB_SERVER): very common; verify the 0xFF/01 reply, that the connection stays up, and the STATUS 16#8381 side-effect on the PLC block.
4. **Schneider M221** (Modbus TCP server): cheap; documented non-strict FC handling, and Schneider uses neighbouring reserved FCs.
5. Optional fifth: a **libmodbus / pymodbus server** as a software baseline, or a **Micro820** if available (undocumented behaviour, gated KB).

Also run a Snort 3 sensor (Modbus inspector on) and the Quickdraw rules on the gate→PLC segment during the tests, to measure the 144:3 / 1111014 false-alarm rate.

---

## Addendum (second pass, same date)

### Prior-art and obviousness risk for the mutation idea
- **Stock IPS engines can already do a same-length FC rewrite.** Suricata's `replace` keyword (IPS/NFQ mode only) replaces matched content with an equal-length string and recalculates checksums. Snort inline has an equivalent `replace` option. So a rule that matches a write FC byte at offset 7 on port 502 and rewrites it to 0x7F is a one-line configuration. **No documented use of this for Modbus refusal was found.** A reviewer could still argue the half of the idea that rewrites requests is obvious. What a stateless `replace` cannot do is the **stateful return path**: remember the original FC for each transaction ID, rewrite `0xFF/01` back to `orig|0x80/03`, and account for whether permitted writes were acknowledged. Claim those parts, plus the no-seq-translation property, rather than "rewriting the FC" as such.
- **Suricata already validates write echoes.** sawp-modbus `Message::matches` pairs requests and responses by transaction ID, unit ID and FC, and raises `modbus.value_mismatch` when the response does not match the request. Suricata also has `modbus.unsolicited_response`. So "check that the PLC's response matches the forwarded write" exists as a passive IDS check. Gate-side **acknowledgement accounting** (pending, acked, excepted, timed out, per write) as an enforcement or audit primitive was not found anywhere.
- Fortinet App Control also has a **Reset** action ("resets the session or connection between the FortiGate and the initiating node", FortiOS 5.4 help). Current 7.x docs list monitor/allow/block/quarantine. Palo Alto: `drop` is silent, `reset-client/server/both` sends RST, and `deny` follows the App-ID default (docs.paloaltonetworks.com, Security Policy Actions).

### Crash advisories (does an illegal FC endanger PLCs?)
- None of the advisories found involves a *well-formed* request with a merely unknown FC. Modbus-triggered crashes found: Schneider Modicon (ICSA-25-114-01: invalid **private-command (FC 90/UMAS)** parameters, debug or breakpoint parameters, and invalid memory-block reads); Modicon Quantum (Tenable, CVE-2018-7831 family: specific Schneider Modbus functions shut down the comm module); the EcoStruxure PLC simulator (ICSA-20-315-03, a crafted Modbus request); and older slave drivers (CVE-2014-0777, out-of-bounds read). The lesson: **never use 0x5A/0x5B/0x7D/0x7E**, which are Schneider-proprietary paths with a CVE history, and always keep the MBAP length and PDU consistent. 0x7F has no known proprietary handler, but Annex A reserves it for "legacy products", so it cannot be ruled out on old Modicon gear.
- Middleboxes crash too: Moxa EDR-G9010 security package v3.0.23 fixed a crash on Modbus packets with incorrect length.

### Alternative refusal encodings worth testing (to reduce IDS noise)
1. **FC 0x7F (current plan).** Distinctive reply (0xFF) that is easy to match. Trips Snort 144:3, likely Nozomi UNSUPPORTED-FUNC / NEW-FUNC-CODE, and Radiflow's FC>0x5A rule.
2. **Unassigned public FC** (e.g. one in 25–40 or 44–64). Avoids Snort 144:3 and the Radiflow FC>0x5A threshold, but the spec reserves these "for future use", Nozomi-style learners will still flag a new FC, and the replies are less distinctive. Make the sentinel FC a configuration register so it can be chosen per site.
3. **Semantic mutation for FC 6 only: rewrite to FC 3 with quantity 0** (both PDUs are 5 bytes). Per the spec, quantity must be 1–125, otherwise exception 03, so the PLC itself returns `0x83/03`. That reply rewrites to `0x86/03` with the exception code unchanged. FC 3 is universally implemented and not "reserved", but Suricata may raise `invalid_value`, and non-strict stacks (cf. M221) might answer normally. It does not generalize to FC 15/16 (variable length), so it is at best an option for FC 5/6.
In every case, keep the timeout fallback (gate-synthesized exception) for silent or non-conformant servers.

---

## Sources (key)
- Belden Tofino Xenon Modbus TCP LSM techdata: https://catalog.belden.com/techdata/EN/TOFINOXENONModbusTCPLSM_techdata.pdf
- mGuard 10.5 manual, Network Security: https://help.mguard.com/en/mguard10/manual/10.5/110191_en_09/Section08/Section08.htm
- Moxa EDR-G9010 security package v3.0.24 release notes: https://moxa.com/Moxa/media/PDIM/S000000001/EDR-G9010%20Series_moxa-edr-g9010-series-security-package-v3.0.24.pkg_Software%20Release%20History.pdf
- TXOne EdgeIPS Pro FAQ: https://help.txone.com/docs/faqs-edgeips-pro
- Fortinet IPS actions / OT signatures: https://docs.fortinet.com/document/fortigate/7.6.5/administration-guide/318637 ; https://fortiguard.com/encyclopedia/ips/15291
- Cisco Modbus preprocessor: https://docs.manage.security.cisco.com/cdfmc/c_the_modbus_preprocessor.html ; Snort 3 rule actions: https://www.cisco.com/c/en/us/support/docs/security/secure-firewall-management-center-virtual/222693-configure-additional-snort-3-rule-action.html
- Snort Modbus README: https://snort.org/faq/readme-modbus ; snort3 source: https://github.com/snort3/snort3/blob/master/src/service_inspectors/modbus/modbus_decode.cc
- Suricata rule actions: https://docs.suricata.io/en/latest/rules/intro.html ; events: https://github.com/OISF/suricata/blob/master/rules/modbus-events.rules ; sawp-modbus: https://github.com/CybercentreCanada/sawp/blob/main/sawp-modbus/src/lib.rs ; reject bug: https://redmine.openinfosecfoundation.org/issues/8390
- Zeek Modbus: https://github.com/zeek/zeek/tree/master/src/analyzer/protocol/modbus
- Palo Alto ICS App-IDs: https://cdn.blueally.com/paloguard/datasheets/app-ids-for-ics-scada.pdf
- Stormshield: https://documentation.stormshield.eu/SNS/v4/en/Content/Identifying_industrial_protocol_commands/70-Build-Policy.htm
- SANS SC600 review: https://assets.new.siemens.com/siemens/assets/api/uuid:c82e7042-4f8d-4345-94f0-50be88657ef5/di-pa-dcp-sc600-sans-product-review.pdf
- containd: https://github.com/tonylturner/containd ; PlcSentinel: https://github.com/mosafariuk/PlcSentinel ; modbusfw: https://modbusfw.sourceforge.net/
- Modbus Application Protocol V1.1b (mirror): https://cars.uchicago.edu/software/epics/Modbus_Application_Protocol_V1_1b.pdf ; V1.1b3 index: https://modbus.org/modbus-specifications
- OpenPLC v3 Modbus server: https://github.com/thiagoralves/OpenPLC_v3/blob/master/webserver/core/modbus.cpp
- libmodbus: https://github.com/stephane/libmodbus/blob/master/src/modbus.c
- Quickdraw: https://github.com/digitalbond/Quickdraw-Snort (modbus.rules, modicon.rules)
- WAGO 750-8207 manual: https://www.manualslib.com/manual/1300320/Wago-750-8207.html?page=277 (also p. 279, p. 298)
- Schneider FAQs: https://www.se.com/in/en/faqs/FA295250/ (M221) ; https://www.se.com/au/en/faqs/FA284826/ (M340/M580)
- Opto 22 KB83595: https://www.opto22.com/support/resources-tools/knowledgebase/kb83595
- CODESYS forum: https://forge.codesys.com/forge/talk/Engineering/thread/7f859f63b5/
- Beckhoff TF6250: https://infosys.beckhoff.com/content/1033/tf6250_tc3_modbus_tcp/192708875.html

- Tofino Argon CMP User's Guide v1.7.0: https://icscsi.org/library/Documents/Manuals/Tofino%20Argon%20CMP%20User's%20Guide%20v1.7.0.pdf (section 6.4.2, pp. 228–234)
- Hirschmann EAGLE CLI DPI Modbus: https://www.manualslib.de/manual/820678/Belden-Hirschmann-Eagle.html?page=516
- Moxa EDR-G9010 manual v2.0: https://moxa.com/getmedia/a4d3401f-e5bc-4c30-8121-b33108f109ac/moxa-edr-g9010-series-manual-v2.0.pdf
- TXOne EdgeIPS Pro admin guide 2.2: https://docs.trendmicro.com/all/ent/txone-eips/1.0/en-us/eips_2.2_ag.pdf
- Palo Alto policy actions: https://docs.paloaltonetworks.com/pan-os/11-1/pan-os-admin/policy/security-policy/security-policy-actions
- Fortinet App Control actions (5.4): https://help.fortinet.com/fos50hlp/54/Content/FortiOS/fortigate-security-profiles-54/Application_Control/Application%20Control%20Actions.htm
- Suricata replace keyword: https://docs.suricata.io/en/latest/rules/payload-keywords.html#replace
- Nozomi protocol validations: https://technicaldocs.nozominetworks.com/products/n2os/topics/autogenerated/security_features/r_n2os_alerts_protocols-validation.html
- Tenable NNM 114: https://tenable.com/plugins/nnm/114 ; Radiflow: https://isid-analyst.radiflow.com/isid-analyst-knowledge-base/4000012
- CISA ICSA-25-114-01: https://www.cisa.gov/news-events/ics-advisories/icsa-25-114-01 ; ICSA-20-315-03: https://www.cisa.gov/news-events/ics-advisories/icsa-20-315-03 ; Tenable Quantum advisory: https://www.tenable.com/blog/tenable-research-advisory-multiple-ics-vulnerabilities-in-schneider-modicon-quantum-plc
- Control.com thread on FC 126 (ProWORX / Schneider programming): https://control.com/forums/threads/modbus-function-code-126-hex-7e.32956/post-32956

## Gaps / not verified
- Tofino's exception code is still unknown. The full CMP v1.7.0 guide was read: it says only "a Modbus TCP exception response (if appropriate)". Its state tracking enforces request/response alternation, not write-acknowledgement accounting. How Tofino keeps TCP sequence numbers consistent after dropping a request and injecting an exception is not documented.
- Modbus V1.1b3 itself (WAF-blocked); V1.1b was used instead.
- Siemens MB_SERVER status table (from memory). Micro800, Beckhoff and CODESYS unsupported-FC behaviour (no primary doc retrieved; test instead).
- Moxa: resolved in the second pass (manual v2.0 read: Accept/Monitor/Reset only). Zenwall and Bayshore have no public technical docs. Claroty is detection-focused (passive) and Waterfall/Owl are unidirectional: no write path exists, so "refusal" does not apply. Neither was checked further.
