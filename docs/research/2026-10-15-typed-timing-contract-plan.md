# Typed, timing-bounded outputs: first priority at qualified 200 MHz

The research target is an admitted request producing a structurally checked result or an explicit non-actionable failure by a declared deadline. Higher fabric frequency is an independent optimization. Build the first guarantee at the already qualified 200 MHz operating point, preserving its sources/package; any integrated successor still needs separate physical and hardware qualification.

## What exists today

| Component | Implemented evidence | What it does not establish |
|---|---|---|
| Qualified encoder | Hardware-qualified 200 MHz, frozen numerical baseline | A bound on shared DDR service or successful inference WCET |
| `TimingPolicy` | Model/clock/input admission and measured budget checks | Hard host or shared-DDR timing |
| `contract_service.py` | Finite schemas, enum/BIO/shape checks, model/schema/contract identities, explicit failure variants, no prediction payload on nonacceptance | Bounded Python/NumPy/Linux execution or external delivery; semantic truth |
| `deadline_supervisor.sv` | Independent core-outcome cycle budget; boundary simulations and counter argument; timeout quarantine | A typed task-head result or guaranteed core success |
| `typed_publication_gate.sv` (new standalone prototype) | Request/contract identity checks, finite single-label result, threshold abstention, canonical empty failure variants, exact terminal deadline, held publication and stale/replay rejection | Integrated MMIO/CDC, model/head computation, R5 firmware, formal proof, physical timing or board qualification |

The prototype is **not integrated into counter300 or the qualified package**. Its regression is `simulation/v2/run_typed_publication.sh`, with successful evidence under `build/v2/typed-publication-prototype-v2/`. The earlier prototype attempt preserves a testbench dangling-`else` compilation failure, corrected before the successful run. No functional module failure was hidden.

## Choose the guarantee boundary first

Initial claim: from the clock edge accepting a complete, admitted tokenized request at the local PL endpoint, a stable typed terminal record becomes available in that endpoint by D fabric cycles. This excludes arbitrary Linux input arrival, tokenization and network delivery. It includes the head/validation stage for an accepted task output. Failures have the same declared response type and no action authority.

Three claims need separate evidence:

1. **Structural type validity:** accepted label IDs belong to the bound finite schema; shapes/lengths and scalar encodings are valid. Slot BIO syntax or argument ranges need additional validators. This cannot prove the model's meaning is correct.
2. **Bounded terminal outcome:** accepted/clarify/abstain/fault/deadline/invalid becomes available by D, even if inference or ARM stalls. This is feasible with a local independent PL timer and publication register.
3. **Guaranteed successful typed inference:** every admitted input completes encoder, heads, validation and publication by D under the declared environment. This additionally needs core WCET, DDR/interconnect service, firmware and head execution bounds. A timeout mechanism does not prove this claim.

The endpoint is result-register availability. Hard delivery to an external controller requires a bounded consumer link and response service too. Reporting observed maxima or percentiles is useful characterization, not a hard bound.

A fabric-cycle bound is not automatically a millisecond guarantee. Conversion requires a justified minimum clock frequency over the admitted environment, including reference-clock tolerance, and a rule excluding clock gating/frequency changes during the request. Use `T_outcome <= D / f_min` plus any explicitly bounded admission/CDC terms. The qualified driver's reported 199,999,998 Hz is an operating observation, not a proved minimum across conditions. Wall-clock guarantees also need a stated reset/power/fault model. Clock ownership and monitoring belong in the certificate, not just a nominal MHz field.

## Proposed KR260 partition

AMD documents APU/RPU asymmetric multiprocessing for Zynq UltraScale+ and an OpenAMP flow on Kria. The RPU is an appropriate place to investigate deterministic small services, while A53/Linux provides the management plane. These are platform capabilities, not a timing certificate. See [AMD AMP guidance](https://docs.amd.com/r/2024.2-English/ug1137-zynq-ultrascale-mpsoc-swdev/Asymmetric-Multiprocessing-AMP), [Kria OpenAMP implementation](https://xilinx.github.io/kria-apps-docs/openamp/build/html/openamp_landing.html), and [Zynq UltraScale+ lock-step/TCM map](https://docs.amd.com/r/2021.1-English/ug1137-zynq-ultrascale-mpsoc-swdev/Lock-Step-Operation). Do not substitute Versal RPU documentation for K26 details.

| Owner | Work | Timing/ownership requirement |
|---|---|---|
| A53/Linux | Provision verified model and schema, tokenize before admission, configure service, log/render results | Outside initial hard deadline; cannot mutate model/clock/profile while admitted service is active |
| R5 bare metal, initially one core | Single-request admission, bounded small head, structural validation, policy decision, proposal to PL | Fixed-size buffers; code/stack/hot data in TCM where feasible; no allocator, logging, RPMsg wait or blocking Linux call in admitted path; bounded interrupt/preemption and memory access |
| PL encoder | Existing numerically specified computation | Exclusive request ownership; physical closure; successful-completion bound needs declared memory service |
| PL publication gate | Own deadline and authoritative result; reject stale/late/malformed proposals; publish non-actionable timeout independently | Local register/BRAM endpoint, running clock, proven reset/CDC behavior; never blocked by external DDR or ARM |
| Consumer | Use only stable valid record matching request and contract identity; act only on ACCEPTED | Bounded delivery is a separate contract; a label is not automatically an authorized action |

R5 lock-step can improve fault detection; it is not two-core throughput and does not independently prove WCET. A dedicated bare-metal A53 is another option if a head exceeds R5 resources, but caches, coherent interconnect and DDR then need explicit treatment. PREEMPT_RT/core affinity may improve measured Linux latency without establishing this hard claim.

OpenAMP/RPMsg is useful for startup and configuration. The Kria reference flow uses Linux remoteproc/RPMsg to load and communicate with the RPU; that path should stay outside the initial hard endpoint. An R5 timer alone is insufficient if the R5 can stall on a blocking DDR/MMIO access. Keeping code in TCM does not bound every data/interconnect access. Independent PL publication is the fallback even when ARM firmware stops progressing.

The implementation artifacts were also inspected, pinned to AMD/Xilinx `embeddedsw` commit `c3b3132f6e1e202e275b8dd77b3804f3b449528c` (2025.2 release ref). Its [R5 echo linker script](https://github.com/Xilinx/embeddedsw/blob/c3b3132f6e1e202e275b8dd77b3804f3b449528c/lib/sw_apps/openamp_echo_test/src/system/generic/machine/zynqmp_r5/lscript.ld) places `.text` in DDR while other sections use TCM and declares a heap. Its [platform implementation](https://github.com/Xilinx/embeddedsw/blob/c3b3132f6e1e202e275b8dd77b3804f3b449528c/lib/sw_apps/openamp_echo_test/src/machine/zynqmp_r5/platform_info.c) allocates an RPMsg device and contains polling loops; its [echo application](https://github.com/Xilinx/embeddedsw/blob/c3b3132f6e1e202e275b8dd77b3804f3b449528c/lib/sw_apps/openamp_echo_test/src/system/generic/rpmsg-echo.c) returns data through `rpmsg_send`. This is a useful communication/startup reference, not an all-TCM bounded-execution implementation to copy unchanged. Four artifact hashes and originals are preserved under `build/v2/r5-primary-artifacts/`; no firmware was built or installed.

## First tractable typed task

Start with **one intent head and one finite label enumeration**, not every head/BIO output and arbitrary JSON at once. Existing `host_heads.py` runs integer logits through NumPy scaling, floating softmax and threshold selection. Moving it to R5 is not a mechanical Python translation: pooling, accumulator width, scaling, tie-breaking, confidence calculation and threshold decisions need a pinned numerical specification and differential fixtures.

A fixed-point confidence score can have a bounded structural encoding, but cannot inherit the current calibrated probability thresholds without a quality/numerical study. The new publication prototype's 16-bit score and threshold demonstrate the protocol only. It does not implement or replace the production head. Compile/link the actual selected head and inspect its map against the configured TCM capacity before claiming residency. Head weights, code, stack, result buffers and interrupt state must all fit; do not assume all current heads fit together.

The repository already offers another useful partition: `ddr_image.head_program` emits POOL and raw-INT32 LINEAR instructions for FPGA heads. Its documented output overwrites A for each head, requiring a defined single-head read/run protocol. Assess that existing path before writing a complete R5 head: PL could produce numerically specified integer logits, leaving R5 only bounded per-class scaling, selection, confidence/abstention and structural checks. Per-class scales differ, so argmax of raw logits is not generally equivalent to the current scaled decision. This helper is not an integrated typed-deadline service today; program/buffer ownership, output transfer and the head's extra DDR requests still need evidence. Compare these two partitions at the one-head level, rather than moving all arithmetic to ARM by default.

## Prototype publication contract

`rtl/contracts/typed_publication_gate.sv` accepts synchronous, atomically staged inputs. It has no AXI master and cannot wait for DDR. It is deliberately a narrow single-label prototype:

- Admission captures a 64-bit request ID, a nonzero 256-bit contract identity and a 32-bit positive cycle budget at elapsed=0. Positive-budget request IDs must strictly increase within a boot session; exhaustion requires a safely reset service with a new boot identity.
- The trusted provisioning layer binds the contract hash to model, output schema, numerical head specification, bitstream, R5 firmware, clock and environment. A hash field by itself does not verify any of those bytes. Boot/session identity and live ownership are required to prevent replay across resets.
- Proposal identity must match the active request and contract. Wrong identities are ignored and cannot extend the timer. Correct proposals at the budget edge win; otherwise deadline is published exactly at D. Later changes to budget or identities cannot extend the captured request.
- Outcome codes are **1 accepted, 2 clarify, 3 abstain, 4 hardware fault, 5 deadline exceeded, 6 invalid input**. This ABI is distinct from the older core-only supervisor's codes.
- An accepted label must be in `[0, LABEL_COUNT)`. Score below `MIN_CONFIDENCE` yields abstention. Other declared variants always publish label=0 and score=0, with interpretation determined by the outcome tag. Invalid proposal variants/labels yield a quarantining hardware fault.
- `core_quiescent` is required for admission and nonfault proposal acceptance. It must mean no outstanding AXI/DMA/buffer ownership, **not merely encoder busy=0**. Timeout, fault or unsafe quiescence quarantines until coordinated safe recovery. The gate never aborts AXI.
- Publication is held until acknowledged. Quarantine cannot be cleared by acknowledgement; late proposals cannot rewrite the record. Ready describes this endpoint plus the quiescence input, not a permission to bypass the encoder's other admission guards.

The prototype's ready/admitted handshake defines its start boundary. Invalid zero-budget or replayed admissions produce immediate invalid-input records. Reset terminates the contract; it must be coordinated and cannot be used to hide missed deadlines. Inputs crossing clock domains require a reviewed request/response handshake and stable payload storage; wiring a multibit proposal directly across clocks would invalidate the argument. MMIO integration must stage a whole proposal, commit it atomically, and provide stable read/ack ownership so readers cannot observe a torn result. Restrict proposal writes to the trusted service with a reviewed privilege/protection policy.

Do not derive safety-critical quiescence from counter300's delayed diagnostic `read_due`/`write_due` or its snapshot flag. Those counters intentionally lag and are not control signals. Derive quiescence from reviewed live AXI/FIFO/streamer ownership, including write responses and pending requests. The current Python typed adapter also lacks this new authoritative request-ID/publication protocol; an explicit admission/bridge implementation must assign the boot-bound monotonic IDs and stage proposals. The prototype is not a drop-in replacement for the current adapter or driver.

Quiescence does not attest successful computation. The integration/verified ARM bridge must also require matching model/core/head success status before proposing ACCEPTED, with hardware fault/deadline state taking precedence. The standalone gate checks proposal identity and structural fields; it does not read the encoder status or independently recompute its prediction.

Counter argument: while active, elapsed begins at zero and is less than D before the next terminal edge. Each edge publishes a matching proposal, reaches the captured deadline, or advances elapsed toward it. At D, a matching valid proposal or deadline terminates. No ARM/DDR response is required for this transition. This argument is conditional on synchronous inputs, a continuously running timing-correct clock, no interrupting reset, and correctly implemented integration. Simulation is not exhaustive formal proof.

## Evidence needed before making the claim

| Priority | Work and artifact | Pass condition |
|---|---|---|
| P0 | Freeze one task, response union, start/end boundaries, environment and admission manifest | No ambiguous “inference time”; input sizes, schemas, failure authority and queue capacity bounded |
| P0 | Formal publication-gate properties plus reset/CDC/MMIO integration review | Bounded terminal result, stable identity/payload, no stale acceptance, no actionable failure, exact tie rule, quarantine and safe recovery |
| P0 | R5 firmware skeleton and standalone head port at 200 MHz PL target | Fixed buffers, inspected linker/disassembly, bit-exact head/decision fixtures, measured/statically justified WCET under declared interrupts and accesses |
| P0 | Integrate authoritative local typed-result endpoint in a separately sealed candidate | Setup/hold closure, protected ownership, atomic proposal/read semantics; no change to qualified package until separately qualified |
| P1 | Fault injection: stall encoder, stop R5 proposals, stale IDs/hash, malformed labels, stalled DDR, late completion, reset/recovery | Endpoint terminal record by D; no late overwrite or unsafe buffer reuse; distinguish endpoint availability from host receipt |
| P1 | Successful-completion analysis | `D >= C_admit + C_encoder + C_result_transfer + C_head + C_validate + C_commit + C_CDC + margin`, each term justified in one time domain; use ceiling conversions and include queue/interrupt bounds |
| P1 | DDR/interconnect service study and enforcement | Declared refresh/arbitration/contention bound or an enforced service schedule; OS choice/QoS settings alone are insufficient |
| P1 | Quality and abstention calibration | Pinned dataset/model/head version; accuracy/F1/OOS and accepted coverage/risk measured separately from structural typing |
| P2 | External transport guarantee | Bound consumer/link service and include it in the advertised endpoint; otherwise keep network/Linux outside scope |

Recommendation: prioritize P0 at 200 MHz after the requested counter timing experiment. A predictable typed response is a stronger project contribution than another frequency figure. Successful inference under a declared memory-service contract can then strengthen the claim without conflating it with fail-closed deadline behavior.
