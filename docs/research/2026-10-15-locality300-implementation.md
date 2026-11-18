# Locality300: timing-directed encoder candidate and typed service

User scope, 2026-10-15 America/Chicago: implement the strongest architectural path toward 300 MHz while preserving the qualified 200 MHz system, and retain the project's timing-guarantee and typed-output objective. The earlier documentation-only restriction applied to the completed review; this new task authorizes isolated implementation and validation. No hardware deployment or baseline replacement is performed.

## Why published KV260 systems can run faster

The same K26 fabric can host very different wiring and pipeline organizations. The [300 MHz LLaMA2 accelerator](https://arxiv.org/html/2502.10659v1) specializes a comparatively narrow vector engine for decode and streams work through pipelined auxiliary operators. [TeLLMe v2](https://arxiv.org/html/2510.15926v2) specializes table-lookup linear processing and separates prefill/decode attention, reporting a 250 MHz bitstream. Their model parameter counts mostly affect external storage and execution work, not the length of a single register-to-register path. More AXI ports increase bandwidth; they do not independently prove a higher fabric clock.

Our routed evidence identifies a concrete physical limit: 4.850 ns from activation capture into query distribution, including 4.736 ns of routing. Placement also exposes opcode selection into the shared MAC inputs. The design uses 54.31% LUTs but 81.94% of CLBs, reflecting packing and distribution pressure. TeLLMe's higher reported LUT percentage does not imply lower Fmax: resource percentages alone cannot explain timing. A matched physical ablation is needed to quantify the causal gain of each change.

## Changes implemented

1. **Consumer-local activation words:** four preserved query-group copies of the existing activation-read mux output stage. Each copy has its own selector and data registers and feeds only its query-group capture. This replaces a global shared operand source on the critical query distribution path; it adds registers, not an arithmetic or pipeline cycle. Placement still has to establish locality.
2. **Local registered MAC selects:** a separate select per output-lane/four-element group and per B element. These settle during instruction setup, before operands issue. An RTL assertion checks that local selection agrees with the executing opcode whenever either engine issues. This targets the placed opcode-to-DSP mux path without changing MAC/tag latency.
3. **Capacity specialization:** H384 efficiency and H1024 capacity configurations use the same candidate sources and five-cycle activation-read contract. The H384 profile serves the actual L12 model; the H1024 profile preserves the independently tested capacity design point. A smaller configuration is not advertised as H1024-capable.
4. **Independent PL deadline outcome:** a counter/terminal-state supervisor operates beside the encoder and publishes an outcome without waiting for DDR. It never aborts AXI or resets an engine with outstanding transactions. Timeout is latched and quarantines the instance until safe system recovery. Late completion cannot change that outcome or permit a new request to reuse its buffers.
5. **Checked typed service:** an additive Python adapter validates model bytes, token/vocabulary bounds, admitted timing profile, finite head/label enums, segments, probabilities, bounded aligned slot words and BIO structure. Immutable typed records and deterministic serialization include model/schema identity. Application policy can accept, ask for clarification or abstain after checking output. Deadline/fault/invalid-input records contain no prediction payload. The adapter rejects late successes and quarantines after backend timeout/fault; it does not retry automatically.

The isolated [candidate sources](../../rtl/v2/candidates/locality300/candidate.json) were copied from the qualified snapshot, not edited into the public qualified RTL. The new feature family is `0x5387ffff`. The existing qualified app/runtime/package guards are unchanged; this candidate has no deployment package. Creation is one-shot, and verification checks both original and candidate hashes. Do not regenerate or edit a candidate while its evidence is in use.

## Priority and expected benefit

| Rank | Change | Evidence and expected benefit | Effort / risk | Required decision experiment |
|---|---|---|---|---|
| 1 | Consumer-local query registers (implemented) | Directly targets the routed critical path, whose delay is 97.6% wiring. Strongest evidence for reducing that path; no MHz gain claimed yet. | Medium / replication can move congestion upstream | Verify replicas survive, compare placed/routed path distribution and fanout against the frozen baseline. |
| 2 | Registered local MAC selectors (implemented) | Targets the placed opcode-to-DSP path, with 3.492 ns wiring out of 3.892 ns. Removes instruction decode from issue-time selection. | Medium / setup-phase alignment and extra control FFs | Assertion-enabled numerical/cycle equivalence, mapped selector inventory and new critical-path inspection. |
| 3 | H384 specialization (implemented alongside H1024) | Matches the actual model capacity and may reduce address/mux/placement pressure. Benefit is plausible, not established by source inspection. | Low–medium / loses larger-model capacity in this profile | Compare resource usage and timing at identical clock/lanes; retain H1024 as a separate capacity point. |
| 4 | Further BRAM/DSP output retiming (deferred) | Synthesis warnings identify optional RAM output registers, but warnings do not establish the limiting routed path. | High / changes latency, tags, backpressure and WCET | Select only if the measured next critical path warrants it; prove all new valid/tag/flush timing and numerical behavior. |
| 5 | Physical partitioning or narrower lanes (deferred) | Could reduce route span and CLB spread; no locality ablation yet. | High / floorplan brittleness or additional execution cycles | Compare total request latency and admission bounds, not Fmax alone; reject throughput regressions that erase clock gain. |

The supervisor and typed service are orthogonal contract work, not claimed Fmax improvements. Any added pipeline cycle must enter the admitted execution bound; a faster clock alone does not establish a tighter successful-inference guarantee.

## Deadline channel contract

The experimental AXI-Lite map adds:

| Address | Meaning |
|---|---|
| `0x60` | bit0 outcome valid, bit1 active, bit2 quarantined, bit3 ready; bits10:8 outcome |
| `0x64` | elapsed supervisor cycles, frozen at outcome |
| `0x68` | budget in cycles; writable only while idle/ready |
| `0x6c` | deadline ABI `0x53595431` |

Outcome codes: 0 none, 1 core completed, 2 deadline exceeded, 3 invalid input/budget, 4 core hardware fault. Code1 says the encoder core completed; **it does not certify semantic correctness or output typing**. The checked service supplies that separate validation stage. IRQ is raised for a terminal supervisor result as well as ordinary core DONE.

At the rising edge that samples `contract_start`, elapsed=0 and the budget is captured. At each following edge elapsed increases. If completion is sampled at the budget edge, completion wins; otherwise timeout is published exactly at that edge. A zero budget rejects immediately and never starts the core. The MMIO control write precedes the sampled internal start by one clock; report that boundary explicitly. Later budget writes cannot extend an active deadline.

For positive D, induction gives `0 <= elapsed < D` while active before a terminal edge; no counter overflow occurs before D, even at `0xffffffff`. Every active edge either completes, increments toward D, or terminates at D. This is an **RTL-level conditional bound on outcome-register availability**, assuming the clock continues, reset does not interrupt the request, and the physical implementation meets timing. It is not yet a 300 MHz hardware guarantee. A host/MMIO read can still stall, so it is not a guaranteed delivery bound to Linux or a network client.

Timeout does not prove the late engine is quiescent. Acknowledging timeout leaves quarantine and the result latched. Do not independently reset just the supervisor or force a new RUN. Recovery must establish safe AXI/system quiescence before a coordinated reset or reload. The existing board is not altered by this implementation.

## What remains necessary for guaranteed successful typed inference

Our distinguishing objective is **admitted, numerically specified inference with bounded typed results and explicit failure semantics**, not an unmatched tokens/s headline. The new supervisor supplies a useful bounded failure mechanism. It cannot make successful model completion inevitable under unbounded DDR service.

A successful-completion certificate still needs:

- A model/profile-bound worst-case core execution analysis, including every permitted instruction, token count, memory request, pipeline fill/drain and exceptional path.
- A verified DDR/interconnect service bound under declared CPU/DMA/refresh/contention conditions. Bare metal or QoS settings alone are not that proof.
- Bounded task-head, validation, serialization and transport service, or moving the required stages to a suitably bounded execution environment. Linux polling and uncached MMIO currently prevent a hard host-inclusive claim.
- A type/schema checked before publication, bounded payload dimensions and an explicit consumer rule that non-accepted variants carry no action authority. Typing is structural validity; model semantic error requires a separate quality/risk study.
- Physical setup/hold closure at the actual clock, plus complete source/package/certificate binding and live qualification before deploying any new claim.

`contract_service.py` deliberately reports successful-completion and host-delivery guarantees as false. Its deadline checks cover encode, heads, validation and serialization before an accepted result is returned; they are enforcement checks, not a proven host WCET. The original `TimingPolicy` remains unchanged and correctly does not certify shared-DDR timing. Neither measured maxima nor percentile latency will be promoted into a hard bound.

The adapter composes with the existing encoder and heads without editing their
baseline implementation. For example, construct `OutputSchema.from_manifest`
with `head_names=('intent.atis', 'slots.atis')`, bind `TypedEncoderService` to the
loaded image's SHA256 and actual clock, and pass a prediction callback using
`heads.intent(encoded_x, chain, 'atis', segment)` and `heads.slots(...)`. An
optional `decide(checked_payload)` callback returns the `Outcome` enum for
accept/clarify/abstain. Its output cannot add arbitrary labels or arguments.
Use a separately declared timing policy; this example supplies no invented WCET.
Construct the service only after verified model loading under exclusive ownership
of the encoder and model region. Model/clock changes invalidate the service and
its admission policy. The adapter checks the driver's recorded clock and refuses
CPU-reference execution as fabric cycle evidence; it does not protect against
another process reprogramming hardware or modifying DDR behind its owner.

## Reproduction and gates

- Candidate origin/verification: `scripts/v2/kr260/create_locality300_candidate.py --verify`.
- Numerical and deadline regression: `simulation/v2/run_locality300.sh`; preserves existing evidence and stages compilation in a separate WSL temporary directory.
- Host contract tests: `tests/test_contract_service.py`; candidate/build guards: `tests/test_locality300_candidate.py`.
- Gated synthesis/placement: `scripts/v2/kr260/build_locality300.py`. Synthesis requires completed random-stall regression, exact baseline output/cycle parity, staged-source hashes and deadline proofs. It snapshots candidate sources separately and checks mapped query/select/supervisor cuts. Placement additionally requires an explicit hash-bound synthesis review. The tool has no route, bitstream, export, package or deployment action.

The unchanged route admission remains at least +0.5 ns placed setup for any separately reviewed route candidate. A 300 MHz target or successful synthesis does not establish closure. No false/multicycle path exception is added. Seven older rejected snapshots remain rejected.

## Validation record

The [validation receipt](2026-10-15-locality300-validation.json) records source and evidence hashes. Completed checks:

- 50 random-stall AXI cases across H1024 and H384 match the frozen numerical words **and exact cycle counts**. Each dataset also exercises the independent deadline IRQ and quarantine at the wrapper.
- A separate H384 run with Verilator assertions enabled passes all 8 actual-model cases, including the local MAC-selection assertion, with the same output/cycle parity.
- The independent supervisor passes 288 completion/budget boundary combinations plus zero-budget, immutable-budget, fault and quarantine checks. This is simulation evidence plus the stated counter argument, not an exhaustive formal proof of the integrated system.
- 259 host/runtime/package tests pass, with no failures, errors or skipped tests in the sealed XML.
- All 602 protected baseline files retain their recorded hashes; all 24 candidate RTL source hashes verify. No baseline RTL, numerical fixture, deployment package or recovery artifact was rewritten.

Results are in `build/v2/locality300-regression/`, `build/v2/locality300-assertions/` and the profile-specific `build/v2/locality300-*` directories. Physical synthesis/placement status is recorded separately below and in HANDOFF.md. Simulation at an ideal clock cannot establish 300 MHz setup/hold closure; there is no new board qualification in this task.

## First physical-tool evidence

H384 synthesis completed with all intended cuts retained: 512 query-data FFs, 128 local MAC-select FFs and 70 supervisor FFs. Integrated synthesis reports 67,598 LUTs, 53,227 registers, 46 BRAM tiles, 18 URAM blocks and 579 DSPs. Counts from synthesis are not directly interchangeable with the frozen routed counts.

The 3.333 ns clock target **fails** synthesized setup by 0.591 ns; estimated hold is -0.087 ns. The worst synthesized path is layernorm `width_reg[10]` through combinational source-address DSP multiplication and shared activation-buffer address selection into `gen_buffer[1].read_address_reg[5]`: 3.719 ns data delay, including 2.508 ns logic and 1.211 ns estimated routing. This new path is a concrete candidate for incremental row-base address generation or a properly tagged address pipeline in a successor revision. It is not a routed critical-path measurement and does not establish that the earlier route problem is solved.

The hash-bound synthesis review admits one diagnostic placement to evaluate locality and the next limiting paths. It does not admit routing or certify the target frequency. The original +0.5 ns placed setup admission threshold remains unchanged. No RTL source is edited while its build is active.

### Updated experiment order after synthesis

All 30 reported worst synthesized paths involve layernorm address generation and shared read addressing. Subject to placement confirmation, promote **incremental row-base address generation** ahead of broad BRAM/DSP retiming in the next revision. The current expression is `token_reg * (width_reg >> 3) + word_index`; a registered row base advanced once per completed token could eliminate that request-time multiplication. The destination expression uses a separately delayed token and must be audited independently. Do not substitute a fixed H384 stride: the runtime instruction width can vary even in the H384 capacity profile.

The experiment must check start/restart, row transitions, both sum/squares passes, normalization drain, variable legal widths, maximum token count and reset. Compare every word and exact cycles with the frozen cases, then add directed address-transition checks. A row-base implementation that changes cycles must update admission evidence explicitly. Effort is medium and risk is medium: arithmetic is simple, but an off-by-one row or delayed write tag can silently corrupt a later token. None of this successor RTL has been substituted into the currently sealed candidate.

Placement revises this synthesis-led priority: its worst path is linear load-state decode into the 32-bit `gen_performance.read_due_reg` counter, with 4.216 ns data delay (1.450 ns logic, 2.766 ns estimated routing). The next revision should first **register/localize the performance-counter event enable and split or pipeline the counter carry path**, then examine AXI readiness propagation and attention arithmetic among the other worst paths. This is medium effort/risk: preserve exact event counts at DONE, restart, rollover and simultaneous event/completion; do not silently remove the measurements used by the timing contract. A delayed counter needs a defined snapshot/drain rule and directed boundary tests. Layernorm row-base generation remains a synthesis-motivated follow-on, not the final placed bottleneck. This distinction prevents optimizing an unplaced estimate while ignoring the measured physical path.

### Completed placement: 300 MHz rejected

| Diagnostic clock | Setup slack | Hold slack | Meaning |
|---|---:|---:|---|
| 200 MHz | +0.656 ns | -0.074 ns | Fixed-placement estimate; no new hardware qualification |
| 250 MHz | -0.344 ns | -0.074 ns | Fails setup and hold |
| 300 MHz | -1.011 ns | -0.074 ns | Fails target and +0.5 ns route-admission gate |

These are timing analyses of the **same 300 MHz-targeted placement**, not three independently optimized designs or routed results. Both named PS clock constraints are rescaled by the diagnostic script; the measured core paths belong to `clk_pl_0`. No software clock setting or board clock was changed. The placed checkpoint was saved before the diagnostic constraint sweep.

Placed utilization is 63,478 LUTs, 52,253 FFs, 76.93% occupied CLBs, 46 BRAM tiles, 18 URAM blocks and 579 DSPs. The older 300 MHz placement had -1.164 ns setup; this candidate's -1.011 ns is only a small numerical difference across different capacity/configuration points, **not an isolated causal improvement or 300 MHz closure**. The original critical query/opcode paths are absent from the reported 30 worst placed paths, but no matched path-delay ablation proves their improvement. New leading paths include performance counting, AXI readiness propagation and attention arithmetic/control.

`build/v2/locality300-encoder384/placement-review.json` binds the final reports and explicitly **rejects 300 MHz route admission**. No route, bitstream, package or deployment was run. The source/test implementation is complete, but the 300 MHz objective remains unachieved. Preserve the failed candidate as evidence; implement the newly ranked counter/handshake changes in a separately sealed successor, with full regression and physical checks. The qualified 200 MHz system remains the production baseline.
