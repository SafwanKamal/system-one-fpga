# Bounded maintenance decisions: implementation and experiment plan

Prepared October 25, 2026. Proposed work, not implemented or authorized deployment by this document. This turn adds a plan only. No board session, bitstream change, model training or benchmark restart occurred. Preserve existing sealed results and the stopped full sweep.

## Decision

Build a model-independent bounded maintenance service with a small trusted executive and a versioned FPGA release gate. Reuse the existing three-step maintenance language, trusted simulator branch execution, typed publication/epoch machinery, and sealed DMA lifecycle. First establish the semantics and experimental value in software; then implement only the enforcement functions that benefit from hardware. Retain rules and compact learned models as equal candidates. Do not make a new choice-head architecture or general grammar accelerator the main project.

Central question: under explicit memory, response and execution budgets, can a small enforcement boundary provide bounded terminal results and prevent invalid action releases without forfeiting too much correct task completion? Evaluate request interpretation separately from execution-policy compliance.

## Existing pieces and actual gaps

| Existing piece | Reuse | Remaining work |
|---|---|---|
| `src/sysone/v2/maintenance/schema.py` | Eight named tools, four comparison operators, one asset, at most three steps, strict structure and bounded numeric values | New envelope/identity ABI, explicit grounding references and capacity semantics |
| `src/sysone/v2/maintenance/simulator.py` | Trusted guard arithmetic, evidence checking, read-failure stopping, below/equal/above counterfactuals | Time progression, concurrent state changes, release/ACK failure and retry semantics |
| `rtl/contracts/typed_publication_gate.sv` and `rtl/contracts/typed_intent_v1/` | Failure variants, request IDs, complete-frame publication and deadlines | Maintenance records, policy/state binding, authoritative action release |
| `rtl/v2/candidates/typed200/contracts/` | Encoder epoch/drain integration patterns and fault/quarantine evidence | A decoder-specific ownership/drain observation path; encoder proofs do not transfer automatically |
| `src/sysone/v2/qwen_arm_service_v16.py` and firmware v16 | Sealed-model startup verification, identity changes, serialized inference lifecycle | Existing prompt/parser is specifically a two-string Linux-file call; a new maintenance adapter is required |
| Current classifiers, generators and probability-output experiments | Frozen proposal controls and development error analysis | Independent new language data; no current decision head is presumed superior |

The simulator already evaluates conditions in trusted code. The proposal is not to rediscover that mechanism, but to connect it to a bounded, versioned target boundary and measure the consequences.

## Closest prior art and restricted novelty claim

The earlier review is background, not a novelty clearance. Additional targeted search found particularly close work:

- [LIR+LVM: Bounded execution of LLM-generated code on microcontrollers](https://www.sciencedirect.com/science/article/abs/pii/S1383762126003310): publisher excerpts describe compact representations, capability gating and step-bounded execution across MCU boards. Full-text access returned 403. A bounded VM or compact action language is not an adequate novelty claim by itself.
- [VIGIL, ACL 2026](https://aclanthology.org/2026.acl-long.443/): verify-before-commit for tool-stream injection. Publisher abstract screened; not reproduced.
- [Stale Does Not Mean Unsafe](https://arxiv.org/abs/2609.29522): preprint compares epoch/read-set/predicate guards and benign-race blocking. Author abstract screened. Guard precision and freshness tradeoffs already have direct prior art.
- [FPGA-resident guardrail fabric, October 15, 2026](https://www.tdcommons.org/dpubs_series/12215/): defensive disclosure proposes hardware-interlocked release with identity and state binding. This is a proposal, not inspected implementation evidence or a patent/legal conclusion. Nonetheless, broad hardware-release-interlock claims overlap.

Potential contribution to investigate: a small, implemented and formally specified publication-and-release protocol for an FPGA language-model system, preserving a bounded terminal response when inference/ARM stalls while preventing late, stale or partially committed action release; plus a controlled evaluation separating semantic mistakes, policy violations and completion/availability loss.

Distinctive evidence would be: actual decoder drain/ownership integration, assumptions explicit through AXI and sink handshakes, bounded timeout independent of software progress, fixed resource accounting, paired proposal replay, end-to-end numerical/acceptance qualification, and a measured comparison against an optimized ARM checker. This remains a candidate contribution. Full reading of the closest work and an updated citation search precede a publication novelty assertion.

## Phase 1: Freeze a narrow service contract

Initial supported maintenance profile: one asset; up to three steps; one predicate; temperature with integer-C thresholds or configured limit; `read_metric`, optional `read_history` (at most five samples), `draft_report`, and `request_inspection`. No physical actuation. Remaining existing tools and metrics stay available as legacy baselines but are outside the initial hardware action profile. Add them only in a new profile. Unsupported inputs return a typed outcome; they are not silently rounded, truncated or repaired.

Keep numerical thresholds within the existing signed domain [-1,000,000, 1,000,000]. Explicitly freeze scale/overflow semantics and how a configured limit is sampled. Extending to fractional vibration/current thresholds later requires a new fixed-point contract rather than silently changing legacy labels.

New profile limits, proposed engineering choices rather than measured facts:

- Up to 16 catalog entries; at most 1,024 total model tokens, with 256 output tokens reserved for generators. The exact tokenizer/template decides fit; do not use a character-count proxy.
- At most 8 KiB input text; fixed maximum provenance-span count; no recursive AST or executable free text.
- Exactly one active request and one pending terminal record. Backpressure rejects new admission explicitly.
- No automatic model retry or action retry in the primary experiment. Later repair is a separate budgeted arm.
- Proposal deadline of 10 seconds for the primary research profile; report 1/3/5/10-second sensitivity from a frozen policy. These are service-study budgets, not industrial process deadlines.
- Per-read/action-adapter timeout and total execution budget fixed in protocol after development measurements. Timeouts produce failure without claiming the remote action did not occur.

Record identity: boot/session ID, monotone request ID, model/runtime ID, policy/catalog versions and observation generation. A trusted wrapper sets identities; an untrusted proposal cannot vouch for its own provenance. Treat IDs as trusted table references, not cryptographic attestation.

Output variants: `PROPOSAL_READY`, `CLARIFY`, `REJECT`, `DEADLINE`, `HARDWARE_FAULT`; execution separately reports `COMPLETED`, `TOOL_ERROR`, `CANCELLED`, or `OUTCOME_UNKNOWN`. `PROPOSAL_READY` is not task completion. Invalid or failure records carry no actionable payload. Specify expiry-edge tie behavior before tests; use expiry-wins and preserve historical gates unchanged.

Deliverables: `docs/contracts/maintenance_v1.md`, `firmware/maintenance_guard_v1/contract.json`, and generated C/Python/SystemVerilog enums and layouts from one fixed description.

Exit gate: every field, capacity rejection, time origin, state transition and failure outcome has an unambiguous definition and independent reference examples.

## Phase 2: Software reference and proposal adapters

Create additive modules under `src/sysone/v2/maintenance_guard_v1/`:

- `contract.py`: typed envelope, profile capacity and version validation.
- `grounding.py`: catalog references, exact numeric/unit spans, bounded explicit-operator lexicon and ambiguity detection. Unsupported paraphrases cause clarification; source spans alone do not certify their interpretation.
- `admission.py`: dependencies, permitted effects, policy, identity and acceptance checks. Reject contradictory evidence; do not fill semantic fields from hidden labels.
- `executive.py`: explicit read, evaluate, stage, dispatch, wait/ACK and terminal states.
- `event_world.py`: separate visible and authoritative state, time, mutations, failures and action sink.
- `proposers.py`: normalize frozen rules, TF-IDF, encoder and generator proposals to the same contract. Preserve raw outputs and rejected proposals.
- `scoring.py`: independent complete-plan, execution-policy and outcome scoring.

Request interpretation remains learned/empirical outside the explicitly recognized language subset. A structurally valid wrong plan must remain a semantic error even if it causes no forbidden side effect. Grounding aids can reduce coverage; measure both errors caught and correct proposals blocked.

Implement a portable C reference in `firmware/maintenance_guard_v1/` with fixed arrays and no heap. Compare against the Python oracle on valid, invalid and boundary records. Build optimized C for the ARM baseline; Python is not the main software performance comparator.

Observation record: asset/metric/unit, signed value, status, timestamp, observation ID and relevant state generation. Adapter supplies it on a trusted path; model text is never accepted as sensor evidence. Configured-limit changes, permissions and catalog changes are applied as events in the authoritative world.

Release is at-most-once per session/request/action ID. A lost ACK after dispatch produces `OUTCOME_UNKNOWN`, not an automatic retry or an exactly-once physical-effect claim. Recovery requires reconciliation through the trusted adapter.

Exit gate: differential behavior agrees; named invariants pass exhaustive reduced-domain exploration plus mutation/property tests; original maintenance tests and sealed artifacts remain intact.

## Phase 3: Isolated FPGA gate, then decoder integration

Create `rtl/contracts/maintenance_guard_v1/`, leaving all historical sources untouched:

- `plan_store.sv`: staged fixed-capacity plan and complete-frame commit; immutable while active.
- `observation_store.sv`: fixed observation slots, monotone versions, explicit trusted writes.
- `policy_check.sv`: supported opcode/type/range/dependency checks and fixed-point comparisons.
- `release_gate.sv`: final check and single release handshake with a bounded sink.
- `request_lifecycle.sv`: IDs, timeout, terminal holding, late-message rejection and quarantine.
- `axil_endpoint.sv`: WSTRB-aware complete-frame staging, independent response backpressure.

Use the existing typed modules as reviewed design references, not drop-in proof certificates. Initially test with a hardware sink that records action IDs/counters. This makes release authoritative and observable without actual maintenance actions. An ARM tool adapter obeying a PL decision is a trusted cooperative boundary; it is not isolation against malicious root, raw MMIO or arbitrary DMA.

On the same release edge check that the complete plan is active, all relevant versions are current, prerequisite reads succeeded, required predicate holds, budget is valid, and the action ID has not been consumed. Observation/policy update collision wins over release. Block stale relevant state conservatively in v1; record needless rejection from unrelated state updates. A read-set refinement is an optional comparison, not a novel invention.

Timeout publishes a terminal record even when ARM or the decoder stops progressing. Separately retain ownership/quarantine until physical traffic is known drained. A deadline does not authorize resetting a decoder with outstanding AXI transactions. A stalled bus may prevent reading the record even though the PL record exists; the proof concerns internal publication, while external delivery needs interface fairness/bounds.

Decoder integration is a separate gate: build a new wrapper/candidate from the frozen v9d sources, exposing actual completion, faults and transaction drain from the owning interfaces. `AP_DONE` alone and software's claimed quiescence are insufficient. Analyze internal HLS outstanding traffic and interconnect/CDC behavior. If reliable drain cannot be exposed, report software/standalone-sink results and defer the integrated ownership claim.

Proposed feasibility targets, to be accepted/revised on development synthesis before evaluation: <=2,000 LUTs, <=4 BRAM36-equivalent blocks, zero DSPs for the gate; <=1,000 local cycles from a complete resident frame to a decision, excluding external stalls. Actual closure must preserve the candidate's declared decoder/memory timing. These are design targets, not projections or existing measurements. Report resource delta both standalone and integrated.

Use a PL control clock kept running while inference stalls. Any cycle-bound theorem assumes that clock and reset behave as specified. Protect configuration/observation paths within the stated trusted environment; shared clocks, fabric or memory can still be common failure points.

Exit gate: induction/model-checking for lifecycle and release properties; RTL/C differential tests; routed timing and CDC review; standalone target qualification before any integrated inference.

## Properties and adversarial cases

Prove or explicitly leave unproved:

1. No action before complete successful admission and prerequisite observations.
2. Predicate evaluation uses the declared signed scale and current relevant data.
3. No action after deadline/fault, stale identity, invalidation or previous consumption.
4. At most one release per action ID; terminal records stable until legal ACK.
5. Timeout publication within the declared local-cycle bound, regardless of proposal arrival.
6. No new epoch while old accelerator transactions remain owned/outstanding.
7. Failure/timeout never becomes a late success; stale ACKs cannot clear quarantine.

Inject partial writes, missing COMMIT, duplicate IDs, replay after reset, field/range errors, wrong model/catalog/policy, relevant and unrelated mutations, missing/error/stale samples, opposite/equality-boundary predicates, ARM kill, decoder stall, delayed B/R responses, AXI errors, backpressure, expiry-edge completion, dropped ACK and duplicated delivery. Distinguish reduced-state exhaustive proof, randomized simulation and actual target injection.

## Experiment A: Semantic quality and acceptance

New protocol/output root: `build/v2/bounded-maintenance-v1/`. Existing pilot/stress sets are development/regression only. Design a new training set of approximately 1,200 reviewed/generated development requests, 300 tuning requests, 400 calibration requests, and 600 independently authored evaluation requests. Use balanced predefined strata: direct, multi-read composition, crossed conditions, corrections/context references, ambiguity/negation, unsupported operations. Evaluation authors must not copy development templates; hold out phrasing families and asset names. Labels reviewed and disagreements resolved before predictions; record author grouping and duplicates. These counts are planning budgets, not proof of sufficient power.

Select at most two learned proposers on tuning, retain authored rules and TF-IDF controls. Include frozen fine-tuned Qwen; promote a decision-head alternative only if development evidence justifies it. Newly trained weights require export/numerical qualification before FPGA claims. Keep original float32 capability results distinct from deployed Q8/INT8 outcomes.

Factor the experiment rather than run a huge Cartesian sweep:

- Frozen proposals through (a) schema-only, (b) domain checks, (c) domain plus grounding checks.
- For the selected pipeline, compare no abstention with one calibrated complete-plan acceptance policy.
- Use identical public observations and tool policy for every proposer.

Freeze finite threshold candidates before independent risk calibration. For an accepted-set risk claim, use a suitable high-probability risk-control method with threshold-search correction and an independent test. If calibration supports no useful setting, return that result; a logistic confidence fit is descriptive, not a theorem. Calibrate episodes rather than treating dependent turns as independent. Report threshold-tuning and risk-certification samples separately if split further.

Primary measures: wrong accepted complete plans / accepted plans; correct actionable completions / actionable requests; clarification/refusal burden; total requested-task accuracy; error types. Paired tests/intervals must respect request/author/episode clustering. No 0.1% reliability assertion from 600 evaluation requests: accepted count is smaller and dependence matters.

Preliminary development decision target: reduce wrong accepted plans by at least half while retaining at least 80% of the original correct actionable completions. This is a predeclared engineering usefulness criterion, not a production safety requirement. Report held-out estimates and uncertainty without selecting a new threshold afterward.

## Experiment B: Enforcement, utility and fault behavior

Replay a fixed 100-proposal set, including valid, invalid and semantically wrong-but-policy-valid proposals, through 20 frozen event schedules: 2,000 traces per enforcement arm. These are paired fault cases, not 2,000 independent language examples.

Arms: optimized ARM C checker/executive; same contract with PL release gate; selected guard ablations only in simulation/safe sink. Maintain identical snapshot, predicate, retry and deadline semantics. Include relevant and benign mutations to measure false blocks. Broader generic RTA tools are conceptual baselines unless a runnable feature-equivalent port is feasible; do not compare unlike policies by raw speed.

Primary result: forbidden releases, duplicates, late success, bounded terminal publication, useful releases unnecessarily blocked, and recovery/unknown-outcome behavior. Any forbidden release blocks promotion. Zero observed violations is not a proof; formal results specify exactly which invariants and assumptions were checked.

## Experiment C: Target cost and end-to-end utility

After software/RTL gates pass, use a separately versioned board candidate and canonical `BOARD_STATUS.json` reservation/preflight. No automatic full-sweep restart or boot-service migration. Keep sealed baselines and failure evidence. Preserve the DMA ABI2 ownership rules.

First replay the same 100 fixed proposals with ten repetitions under three load conditions (idle, controlled CPU load, controlled memory contention): 3,000 requests per implementation. Randomize/interleave ARM/PL comparisons where hardware permits, or bracket separate image runs with identity checks. Repetitions quantify timing variability, not language reliability. Distinguish internal gate cycles, transport latency and terminal record delivery.

Then run a bounded 60-request balanced end-to-end subset on the numerically qualified selected FPGA proposer. Freeze IDs before board execution. If no maintenance checkpoint is deployable, use replayed proposals to qualify enforcement and explicitly leave end-to-end maintenance inference outstanding. Do not substitute the existing Linux-file-call prompt and call it maintenance validation.

Measure p50/p95/p99/max latency, deadline misses, startup separately, peak RAM, LUT/BRAM/DSP, routed timing, power/energy with a declared measurement boundary and sensor bandwidth. Report total energy per attempted request and per correct on-time completion. Use long enough repeated windows if power sampling cannot resolve short gate operations. Never infer an FPGA energy gain from cycles alone.

If PL enforcement has no meaningful latency-tail, isolation or CPU-load advantage over C, keep C as the preferred deployment and treat the hardware result as a no-go. A standalone monitor with no actual bypass-resistant sink supports a narrower claim than an integrated interlock.

## Order, effort and stopping rules

Planning estimate for one researcher, with existing tooling available: roughly four to six weeks; independent labeling, numerical export issues, physical design or unavailable power instrumentation can extend this. Milestones, not elapsed time, control progression.

1. Week 1: closest-prior-art full reads, frozen contract, event oracle, C/Python reference.
2. Week 2: proposal/grounding/acceptance comparison; dataset authoring and independent label review in progress.
3. Week 3: standalone RTL, lifecycle proofs, differential and fault tests; preliminary synthesis.
4. Week 4: standalone target sink and optimized ARM comparison; decoder drain integration only if justified.
5. Weeks 5–6: numerical qualification, finite end-to-end target run, power windows, independent rescoring and seals.

Stop or narrow scope if semantic checks merely reproduce the answer with rules, learned models add no useful language coverage, abstention suppresses most correct work, hardware does not fit/close timing, or authoritative drain/sink access cannot be established. Preserve negative outcomes.

Minimum useful deliverable: an independently evaluated bounded maintenance service with honest semantic and execution guarantees, plus an optimized software implementation. Hardware contribution requires actual proof/target/cost evidence beyond this minimum. A new universal safety claim, certified industrial controller, general FPGA grammar engine, and model-family leaderboard are outside this plan.
