# Typed intent publication: implementation and assurance milestone

Prepared 2026-10-15 after the user authorized proceeding with typed, timing-guaranteed
outputs as the primary priority. The isolated counter300 experiment is complete;
this continuation introduces no encoder arithmetic changes, FPGA physical builds,
bitstream, package, board, boot, remoteproc or automation changes. The original
hardware-qualified 200 MHz system and both sealed frequency candidates remain intact.

## Implemented result

The first service contract now has concrete numerical C code, a bounded bridge,
an ARM mailbox transport and an isolated AXI-Lite PL publication endpoint.
The [frozen contract](../../firmware/typed_intent/generated/contract.json) binds
`intent.atis`, the existing L12 model image, all 18 labels, pooling, scaling,
tie-breaking, typed failure payloads and session/request/deadline semantics.
Contract SHA256: `8133633315487f8f322ecac49e95e7aca3801d00fccb4b4fba36026c5b2752d2`.

The [protocol and register map](../../firmware/typed_intent/README.md) are the entry
point for firmware/RTL integration. A deployment certificate must additionally
bind the actual bitstream, linked firmware, loaded model, operating environment
and fresh boot session. A hash supplied by an untrusted requester is not proof
that the corresponding model is running.

| Component | Implemented behavior | Evidence and limits |
|---|---|---|
| [Frozen profile generator](../../scripts/v2/freeze_typed_intent.py) | Verifies the existing 33,916,928-byte image SHA256, extracts exact weights/bias/reciprocals/scales and labels, refuses overwrite | Profile file seal; conservative logit magnitude bound 1,893,091 < signed INT32 max |
| [C head/bridge](../../firmware/typed_intent/typed_intent.c) | Fixed arrays, bounded loops, integer pooling/logits, binary64 per-class scaling, first argmax; single request and canonical failures | 647 host cases, 11,520 exact logits, 640 exact label decisions, directed bridge tests with ASan/UBSan; no target execution/WCET claim |
| [C MMIO transport](../../firmware/typed_intent/typed_mailbox.c) | Full-frame staging, ARM barriers, one observation per call, no polling/retries/heap | Word-layout tests and R5 compile/link; MMIO instruction count does not bound AXI completion time |
| [Typed guard](../../rtl/contracts/typed_intent_v1/typed_intent_guard.sv) | Fixed profile, write-once boot session, consumed monotone IDs, validated launch; acceptance requires matching successful core epoch and live quiescence | Inductive session/identity/launch/acceptance proof plus directed RTL tests; trusted status inputs are not connected to the encoder yet |
| [AXI-Lite endpoint](../../rtl/contracts/typed_intent_v1/typed_intent_axil.sv) | Independent AW/W capture, WSTRB-aware shadow banks, complete-frame COMMIT, held read bank, independent terminal countdown | Protocol induction and directed backpressure/frame/session/fault tests; single-clock standalone endpoint, not full AXI compliance certification |
| [Original publication gate](../../rtl/contracts/typed_publication_gate.sv) | 32-bit budget, monotonic elapsed progress, deadline terminal record and quarantine | Inductive safety/progress/boundary proof for 18 labels/minimum score zero; original source byte-for-byte unchanged |

## Numerical and ARM choices

The selected model image is SHA256
`4129baded344729ccc7ef6a3f0a2b34799280a91d88173ae1c0b197cdef8c3bb`.
The C head uses the same segment word-piece rows as
[`Heads.intent`](../../src/sysone/v2/host_heads.py), excluding special-token rows
according to the supplied, validated row selection. It compares against
[`ImageMachine.head_logits`](../../src/sysone/v2/ddr_image.py), not a new approximate
floating reference. It covers all signed INT8 input codes, including -128.

Pooling explicitly implements floor division for negative values; it does not
depend on C signed right-shift behavior. INT64 pooling/dot intermediates have
conservative static bounds, and the frozen profile verifies INT32 logit storage.
Scales are the original float32 values exactly promoted to binary64 hex constants.
Per-class scaled argmax preserves the existing label decision; raw-logit argmax
would not be a valid substitution. The test includes all-zero logits for the
first-maximum tie rule. No softmax approximation, confidence threshold or quality
claim is introduced. ATIS has no selected OOS threshold in this profile; Accepted
means the finite structural/numerical contract passed, not that the semantic
classification is necessarily correct or in distribution.

At maximum input shape the main bounded loops perform 49,152 selected-code
accumulations, 384 pooling operations, 6,912 head multiply-accumulates and 18
scaled-score evaluations. These are operation bounds, not cycle/WCET bounds.
Input memory is 49,152 bytes for codes plus 256 bytes of selected row indices
and four bytes of counts. Code and weights need separate placement accounting.

AMD clang 16.0.6 targets Cortex-R5 / ARM EABI / VFPv3-D16 hard float with
`-O2 -ffreestanding -fno-builtin -fno-fast-math -ffp-contract=off`.
The combined relocatable head/bridge/MMIO object has `.text` 2,496 bytes,
`.rodata` 7,676 bytes and `.ARM.exidx` 96 bytes, with no undefined symbols.
Compiler-reported stack is 1,576 bytes for `ti_head`, 112 for `ti_bridge_core`,
and at most 16 for each MMIO call; the nested bridge/head path totals 1,688.
This excludes caller/startup/exception/interrupt frames and is not a linker-map
or TCM-residency proof. The runtime must initialize FPU access and round-to-nearest
ties-to-even. No R5 ELF, linker/startup/BSP integration or board execution exists.

The [previous ARM analysis](2026-10-15-typed-timing-contract-plan.md) and pinned
[authoritative ARM artifact registry](2026-10-15-typed-arm-sources.json) still
apply: Linux/A53 performs management and tokenization outside admission; a bare-metal
R5 owns the bounded head/validation path; PL owns publication even if ARM stalls.
OpenAMP may bootstrap/configure the service, but RPMsg/Linux scheduling does not
enter this initial hard-deadline claim. No remoteproc or boot configuration was changed.

## Proof scope and failure handling

Three distinct inductive property sets pass with unconstrained external input
values and first sampled edge reset:

1. **Gate:** active implies elapsed < frozen positive limit; elapsed increments
   exactly once per active edge; valid/active are exclusive; the final budget edge
   terminates; valid records are structurally legal and held until permitted ACK;
   failures carry empty payloads; quarantine cannot be cleared by ACK.
2. **Guard:** installed session remains fixed/nonzero; every increasing observed
   request ID is consumed, including INVALID; only a valid profile/ID/budget can
   launch the encoder; Accepted proposals require complete/successful matching
   core identity, live quiescence, legal label and zero reserved score.
3. **AXI-Lite:** independent AW and W capture, execution consumes both buffers and
   generates a response, accepted reads capture the selected data, B/R payloads
   remain stable under arbitrary response backpressure.

These are synchronous RTL proofs, not timing closure, CDC/reset-domain signoff,
full endpoint functional equivalence, semantic accuracy or ARM WCET proof.
The guard proof uses a formal-only observation port for the invariant
`gate.last_request <= wrapper.last_seen_request`; that port feeds assertions only,
not functional logic. The instrumented copy and all dependency/property hashes
are preserved. No assumptions require ARM to finish or DDR to respond.

Failed proof attempts remain preserved. The early gate induction attempts lacked
the invariant that active work has an empty payload. The first guard induction
attempt lacked the relation between its consumed-ID tracker and the inner gate's
valid-ID tracker. Strengthening inductive invariants discharged both; no functional
RTL was changed to hide a proof failure. First guard attempt is explicitly NOT PROVED.
An earlier AXI receipt used an overly broad generic claim string; its actual property
file was protocol-only. The final receipt describes the protocol scope correctly.

Timeout is a **bounded failure** result. It does not establish successful inference
by D. The endpoint remains clocked and publishes even when ARM stops or AXI-Lite
read/write responses are held. A matching proposal at edge D is validated before
timeout selection. Fault/timeout quarantine prevents buffer reuse and next-request
admission until coordinated recovery with a fresh session. Reset/clock failure
cancels the interval; availability after reset needs a separate recovery contract.

The local record deadline is not Linux/network delivery latency. A wall-time bound
requires a guaranteed minimum PL frequency and clock/reset ownership. The observed
199,999,998 Hz hardware frequency is not itself a minimum-frequency certificate.
Mixed ARM/PL timing also needs worst-case clock-ratio and bus-service bounds.

## Encoder integration finding: completion is not drained memory

The actual source makes the distinction concrete:

- [`encoder_system.sv`](../../rtl/v2/candidates/counter300/encoder/encoder_system.sv)
  transitions `OUT_BEAT -> FINISH` on the last accepted output W beat (around
  lines302–307), and `run_done` is `state_reg==FINISH` (line322).
- [`axi_memory_port.sv`](../../rtl/v2/candidates/counter300/platform/kr260/axi_memory_port.sv)
  enters `WRITE_RESPONSES` after that beat and waits for `responses_due_next==0`
  (lines345–353). Read outstanding count, delivery count/length FIFO and optional
  registered pending requests are additional live state.
- [`kr260_encoder.sv`](../../rtl/v2/candidates/counter300/platform/kr260/kr260_encoder.sv)
  feeds its existing deadline supervisor's `core_fault` from `run_result[71:64]`
  (line123), while the memory port exposes sticky `memory_error` separately
  (line359). Typed acceptance must combine both sources after all relevant B/R
  responses have been observed. Check the eventual wrapper/driver handling too.

Thus `!busy`, `run_done`, performance-counter snapshot readiness or delayed
telemetry outstanding totals cannot independently certify typed success. A future
isolated integration needs a memory-port-owned `idle/drained` output derived
from read/write FSMs, pending input slots, read outstanding bursts, read delivery
count, length FIFO, write responses and output-buffer/stream state. Include
in-flight handshakes when sampling it; latch/verify epoch completion and response
errors before accepting the R5 proposal. Do not clear a sticky memory error as
an admission convenience or reset counters while transactions can still return.
This finding does not invalidate the prior qualified numerical measurements;
it identifies the stronger completion boundary needed for the new service contract.

## Next experiments, in priority order

| Priority | Work | Evidence/benefit | Effort / risk | Required pass criteria |
|---|---|---|---|---|
| P0 | Isolated typed200 encoder integration: export live drain and latched memory-error/epoch status; connect validated launch and guard | Direct source evidence above; closes the most immediate false-success/ownership risk | Medium / medium | Delay final B beyond run_done; inject RRESP/BRESP faults, pending requests, stalled R/W, timeout and late completions. No Accepted before successful drain. Frozen encoder numerical outputs and compute cycles remain exact; publication adds separately reported latency |
| P0 | Integrate the dedicated AXI-Lite slave at the same PL clock and review PS clock conversion/reset | Atomic standalone protocol already tested/proved; actual path unbound | Medium / medium | Complete AW/W/R/B stress, reset-domain/CDC report, byte-order/WSTRB tests, physical 200 MHz setup/hold closure. Do not wire raw asynchronous multi-bit state |
| P1 | Link R5 bare-metal image with explicit TCM/code/data/stack placement and bounded interrupt policy | Cross-compiled self-contained object exists; eliminates interpreter/heap/Linux from admitted path | Medium / medium | Linker map fits configured TCM regions with interrupt margin; startup initializes FPU and model certificate; replay/session/ownership tests; target PMU/GPIO timing and static WCET review under declared memory service |
| P1 | Compare full R5 head with existing PL POOL/raw-LINEAR head plus R5 `ti_choose` | Existing [head_program](../../src/sysone/v2/ddr_image.py) already defines integer operations; only 18 INT32 logits =72 bytes need transfer instead of up to49,152 hidden bytes | Medium / medium | Exact logits/labels on all pool counts and real encoder fixtures; count added PL/DDR work and transfer latency. Do not assume less transfer alone proves a faster request |
| P1 | Certify one request envelope/deadline and consumer endpoint | Needed to turn the distinguishing claim into evidence | High / medium | Declare T/rows, exclusive buffers/DDR service, clocks, admission point, failure/recovery model. Prove/measure encoder + transfer + R5 + commit WCET and choose D with justified margin; separately demonstrate bounded terminal failure under unbounded DDR/ARM stalls |
| P2 | End-to-end typed quality and fault-injection suite | Structural type legality is proved; semantic task quality remains the existing model's measured property | Medium / low | Run original held-out ATIS fixtures with exact label agreement, report accuracy unchanged; measure valid/accepted/fault/timeout fractions and publish contract-bound traces |
| Deferred | More 300 MHz pipeline work | counter300 placed300 setup remains -0.781 ns, hold -0.071 ns; not admitted to route | High / high | Keep independent from typed200; layernorm sqrt carry chain and remaining telemetry input stage require separate numerical/cycle/timing experiments |

To certify successful inference in PL cycles, bound encoder/drain cycles and every
external-stage duration under its worst permitted ARM/PL clock ratio, transfer
service and preemption. Their sum plus commit/validation margin must fit D. For a
wall-time terminal bound use D divided by a **guaranteed** PL minimum frequency.
Observed latency maxima, a nominal frequency or a best-case DDR rate cannot fill
in missing bounds. Start with one small admitted envelope; reject other shapes
before admission instead of silently extending the deadline.

The defensible research contribution is the measured and specified combination:
numerically pinned encoder/head, finite typed outcomes, identity-bound admission,
independent PL terminal publication, bounded ARM decision path, and explicit
success/failure/recovery/clock/memory assumptions. A finite enum or a watchdog
alone is insufficient novelty or an end-to-end successful-inference guarantee.

## Evidence and preservation

The [machine-readable validation record](2026-10-15-typed-intent-validation.json)
binds current sources, final proof receipts, RTL logs, numerical/ARM receipts and
baseline preservation checks. Final successful attempts are listed there. Early
attempts are retained under `build/v2/typed-*`; intermediate objects/tests are
superseded by the final named attempts, not deleted or relabeled as failures.
The existing 67 host contract/timing/candidate tests pass. All 602 protected
baseline/package/recovery/numerical files, sealed candidate source hashes, prior
placement-review evidence and the original typed prototype hashes are rechecked.
No new encoder regression or physical build is claimed for this standalone module.
