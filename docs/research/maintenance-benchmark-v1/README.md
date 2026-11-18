# MaintenanceBench-Edge v1: proposed benchmark protocol

Date: 2026-10-21. Status: design specification, not an executed benchmark. Companion [protocol.json](protocol.json) records campaign sizes and gates; [design-examples.jsonl](design-examples.jsonl) contains illustrative seed cases, not a dataset or held-out test. No model training, board session, equipment purchase, or historical benchmark restart is performed by this plan.

First software milestone is now implemented in a separate development pilot; see [implementation, token audit and baseline results](../2026-10-21-maintenance-pilot.md). The full study and human-reviewed test specified below have not been executed.

The2026-10-22 continuation uses the verified1024-token candidate context; see [updated budget, fresh comparison and training export](../2026-10-22-maintenance-context1024.md). The256-token values below describe the original design, not the new candidate limit.

## 1. Questions and intended claim

The benchmark asks two separate questions:

1. **Capability choice:** when does a small generative language model improve useful maintenance-task coverage relative to rules, conventional ML and structured encoders?
2. **Deployment choice:** for the same selected model, task and numerical contract, does FPGA execution reduce latency and measured energy relative to resident CPU execution?

Target claim, conditional on results: a bounded local language interface produces correct typed maintenance workflows at useful coverage and low energy on KR260. Do not presuppose an LLM winner, claim universally best model capability, or equate valid JSON with correct behavior. Report the supported task envelope and limitations.

One paper can answer both questions using the same task, scorer and platform. Primary deployment is one model, one frozen bitstream/runtime, one representation. A second FPGA model port, new power predictor, hard-real-time proof and model-router architecture are extensions, not prerequisites.

## 2. Task and tool boundary

Application: an offline diagnostic assistant for pumps, motors and fans. An operator describes a bounded diagnostic or maintenance-documentation task. The model outputs a typed plan, clarification or rejection. A deterministic interpreter executes plans against a versioned simulated plant; it does not interpret the user's language or repair plans. There is no live actuator control, raw-sensor diagnosis, remaining-life prediction, arbitrary code generation, or free-form report generation in v1.

Model inputs: user request, public tool/codec description, asset catalog, and the same bounded observed state/prior request for all baselines. Hidden world values are available only through simulated tools. Gold plans, future observations and correctness labels are scorer-only.

| Tool | Arguments | Result / semantics |
|---|---|---|
| `read_metric` | asset, metric | Current value, unit, configured limit, sample ID, status and epoch |
| `read_history` | asset, metric, count | Last 1–5 ordered samples; no invented time-series provenance |
| `list_alarms` | asset | Bounded alarm IDs and statuses |
| `read_status` | asset | Operating-state record |
| `read_metadata` | asset, field | Manufacturer or inspection-date field |
| `draft_report` | asset, priority, evidence step references | Deterministic report draft assembled from cited results |
| `request_inspection` | asset, priority, evidence step references | Simulated pending inspection record |
| `lookup_procedure` | asset, topic | Fixed versioned procedure identifier/text; no generated engineering advice |

Freeze domains before data creation: three asset types; twelve public asset IDs in any one episode; metrics temperature/vibration/current; canonical units C/mm_per_s/A; priority normal/high; history count1–5; metadata manufacturer/inspection_date; procedure topics inspection/lubrication. IDs and values vary by episode. Public catalog size is bounded even when held-out IDs are new. The model chooses the relevant asset; no gold-dependent tool or entity shortlist.

Numeric readings are fixed-point integers with declared scale, not binary floats. Numeric conversion, when requested, uses the same disclosed conversion function for all models. v1 inputs use canonical units; unfamiliar units require clarification or rejection according to the frozen reason policy. No implicit learned threshold: `read_metric` returns the configured limit when the instruction requests it.

### Plan language

Maximum three tool nodes, one predicate and one asset per independent plan; no loops. A predicate compares an earlier result value against its returned configured limit, or an explicit user threshold. Operators: gt/ge/lt/le. It can gate one or two later nodes; predicate evaluation is conventional code. References must point backward. A skipped or missing reference cannot support a report. Read failure produces a typed `tool_error`, stops that execution path, and never becomes an `ok` observation.

Semantic output variants: `plan`, `clarify(reason, field)`, `reject(reason)`. Runtime failures, deadlines and capacity failures are recorded by the harness, not fabricated by the model. Distinguish unsupported capability from a missing parameter and from contradictory requests.

Example request:

> Read P3's temperature. If it exceeds its configured limit, fetch three recent temperature readings and draft a high-priority report. Do not change settings.

Expected semantic steps: read_metric(P3,temperature); when step0.value > step0.limit, read_history(P3,temperature,3); under the same predicate, draft_report(P3,high,evidence=[0,1]). Three tool nodes. The earlier two-metric-plus-history-plus-report example needs four nodes and is explicitly outside v1; do not silently simplify it.

All systems must be able to express the complete plan grammar. Use a descriptive JSON AST as the reference representation. Develop one reversible compact JSON-array wire codec if needed for token budget; publish its codebook, count its instructions, and train/evaluate every learned baseline with equivalent semantics. Do not assign a favorable short representation to only one model. Codec development uses development cases only. The examples companion file specifies semantic requirements rather than freezing that as-yet unimplemented codec.

Validation rejects unknown tools, extra fields, invalid enums/units, duplicate keys, forward references, cycles, conflicting records and trailing text. No searching a response for a correct subsequence. Greedy generation runs to EOS or a frozen cap; invalid/truncated suffixes remain failures. Common deterministic formatting conversions are permitted only when they preserve all decoded semantics and are frozen before testing.

## 3. Datasets: purpose and provenance

There is no assumed public dataset that directly supplies our exact maintenance plans, simulated environment, and hardware budget. **The primary dataset must be newly constructed and human reviewed.** Public datasets provide external controls and patterns, not automatic industrial validity.

| Dataset/source | Role | Limits and handling |
|---|---|---|
| MaintenanceBench-Edge authored requests and simulator | Primary capability/reliability/energy task | Publish schema, generation recipes, human review, semantic group IDs and split manifests |
| [BFCL V3](https://gorilla.cs.berkeley.edu/blogs/13_bfcl_v3_multi_turn.html) | Precedent for multi-step/multi-turn, missing parameters and execution-state scoring; optional frozen external diagnostic | Our previous BFCL cases have been inspected; they cannot become a new blind test. Adapted cases are labeled custom, not official BFCL scores |
| [Schema-Guided Dialogue](https://github.com/google-research-datasets/dstc8-schema-guided-dialogue) | Optional external dialogue/state generalization check | Different domains. Keep official splits; do not mix into primary training in the initial experiment |
| [CLINC150/OOS](https://github.com/clinc/oos-eval) | Optional intent/OOS regression for existing tooling | Prior local use makes this a regression, not independent maintenance evidence |
| [UCI AI4I2020](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset) | Optional realistic-range numeric fixtures | Synthetic tabular maintenance data, not language plans, real plant validation or a time series; do not invent temporal history from row order |

Use synthetic, deterministic world traces for the primary test: they provide exact controlled thresholds, missing/error readings and counterfactuals. Optional real-data replay is a robustness extension. NASA C-MAPSS would add turbofan-specific modeling and data interpretation without improving the primary language-interface question; omit it initially.

Record source revisions, licenses, authorship, generation model if any, prompts, annotation lineage and content hashes. Data generated by a larger LLM are proposals only; execute and review labels independently. Do not have the evaluated model judge its own outputs. Public pretraining contamination is unknown; new independent authoring reduces direct reuse but does not prove pretraining independence.

### Primary single-request corpus

| Stratum | Train | Development | Sealed test | Definition |
|---|---:|---:|---:|---|
| Direct | 1,000 | 150 | 300 | One read or documentation operation |
| Composition | 1,000 | 150 | 300 | Two/three ordered operations with correct evidence/dependencies |
| Conditional | 1,000 | 150 | 300 | Explicit threshold or configured limit; gt/ge/lt/le distinctions |
| Context/correction | 1,000 | 150 | 300 | Previous request/reference is supplied; correction preserves unchanged requirements |
| Clarification | 1,000 | 150 | 300 | Missing identity/value, ambiguous reference, contradiction |
| Unsupported | 1,000 | 150 | 300 | Unknown asset, unsupported operation/unit/value or plan exceeding bounds |
| **Total** | **6,000** | **900** | **1,800** | Balanced diagnostic distribution, not an asserted deployment prior |

Split development into 450 tuning and 450 calibration cases, 75 per stratum in each. Tune prompts/checkpoints on tuning; choose confidence thresholds on calibration. Never use either for headline test accuracy. Primary test includes at least 900 independently human-authored requests, 150 per stratum; remaining requests may use held-out reviewed generation recipes. Double-annotate the entire sealed test with adjudication; if two independent annotators are unavailable, disclose that and downgrade the external-validity claim. Seek maintenance-domain review of the API vocabulary and at least 100 cases before freezing.

Across each stratum's 300 test cases, allocate 100 to familiar structural families with new values, 100 to independently authored language/surface families, and 100 to held-out combinations of known primitives. In negative strata, the last category holds out combinations of ambiguity/unsupported reasons with familiar task context. Track these as separate slices rather than claiming every slice tests compositional planning.

Assign semantic skeleton, paraphrase family, author, seed, asset catalog and world scenario IDs before splitting. Keep all paraphrases and numerical variants of a base task in one split. Explicitly reserve combination signatures for compositional testing before generation. Hold out some asset-ID strings without withholding the public test catalog. Check normalized duplicates and near duplicates across train/dev/test; review nearest matches. Counterfactual pairs stay in the same split and resampling cluster.

At least 100 conditional test cases require a report/inspection if the predicate fires and no such action otherwise. Evaluate each predicted conditional plan against below/equal/above and read-error worlds. These are four executions of the same plan, not four independent language samples; equality distinguishes gt from ge and lt from le. Check requested reads, order and permissions, not only final report existence. An irrelevant no-op cannot pass a false-branch scenario just because nothing changed.

### Separate closed-loop workflow corpus

Create 120 fresh held-out workflows of four user turns each (480 maximum primary turns). Thirty workflows each: correction/reference, changing observations, missing/error recovery, and conditional composition. Provide 24 development workflows outside the 120 for harness/protocol qualification. Training single-request cases already cover the transition primitives; do not tune prompts against workflow-test results.

All models consume the same observed state and prior-request representation in the primary comparison. This is a bounded state interface, not a claim of autonomous long-term memory. Commit model proposals only as emitted and validated. Each system rolls its own trajectory; never substitute a gold action/result after error. Simulated exogenous observations use fixed scenario keys and event indices independent of model call count. Tool calls do not advance the world clock accidentally. Missing/rejected actions leave their actual consequences in subsequent state.

Only later add full/sliding history and compact state as a separate selected-model ablation. Longer 8/16-step chains are optional after four-turn usefulness is established. Keep read-only field-copy diagnostics separate from closed-loop results.

## 4. Baselines and adaptation

| ID | Baseline | Required role / hardware status |
|---|---|---|
| R0 | Deterministic grammar, synonym table and slot parser | Conventional-code baseline on K26 A53; same complete plan grammar, ambiguity/rejection options |
| R1 | Word/character TF-IDF plus calibrated linear heads and argument parser | Cheap conventional ML; predict tools/order/predicate/slots, same simulator |
| E1 | [MiniLM-L12-H384](https://huggingface.co/microsoft/MiniLM-L12-H384-uncased), fine-tuned structured heads | Compact encoder; plausible existing encoder-family reuse, but new checkpoint/heads require qualification |
| E2 | BERT-base structured encoder; [ModernBERT-base](https://huggingface.co/answerdotai/ModernBERT-base) optional stronger quality reference | Prevent a weak encoder strawman. CPU reference initially; neither is automatically supported by current FPGA decoder |
| L0 | Existing [Qwen3-0.6B](https://huggingface.co/Qwen/Qwen3-0.6B), frozen prompt, nonthinking | Current-deployment starting point; new task prompt still needs software and board qualification |
| L1 | Task-adapted Qwen3-0.6B | Primary generative candidate; quantized/exported weights require new image qualification |
| L2 | [FunctionGemma270M](https://ai.google.dev/gemma/docs/functiongemma/model_card), task-adapted | Optional focused challenger. CPU capability screen first; new FPGA implementation is not required for v1 |

E1/E2 use up to three ordered tool slots plus outcome/reason, entity, metric, history count, priority, evidence reference and predicate heads. Support enum prediction and source copying; unit/case normalization is common and explicit. Missing slots are not inferred from gold. Audit that every v1 gold AST is representable and round-trips through encoder targets before training. The old extractive general-tool prototype had unrepresentable values and is not the sole strong encoder baseline.

R0/R1 may use explicit parsing rules for language, but must not look up test request IDs, hidden worlds or gold plans. Freeze authored rule effort and manual development changes. A deterministic AST builder may serialize predicted fields; it must not invent unpredicted ordering, operands or actions that improve one model silently.

All adapted learned models see the same six thousand task records and information. Use three training seeds where feasible, at most six development-selected configurations per family, with budget/epochs/trainable parameters/compute reported. Different optimizers and full fine-tuning versus adapters are allowed; equal data is not equal pretraining or compute. Set size curves at 600/2,000/6,000 examples using nested train subsets. If resources are limited, complete the 6,000-record comparison first and mark curves optional. Select one deployment checkpoint using tuning only; calibration chooses thresholds; test each frozen seed for capability. Repeated inference from one checkpoint is not a new training seed.

Greedy, thinking disabled for generator comparisons. One attempt, no self-repair, no tool-result-dependent hidden retries in the primary plan-generation track. Constrained decoding is an optional common-policy variant with overhead included; publish unconstrained validity and constrained semantic correctness separately. Emitter guarantees do not count as semantic gains. Raw max probabilities across model families are not comparable confidence measures.

## 5. Context and numerical fairness

Two declared tracks are required:

* **Capability reference:** each model's supported software configuration, with 1,024-token input ceiling and 256-token generator output ceiling as benchmark limits, counting public schemas/catalog/state. Report native tokenizer lengths and failures. This explores capability but does not establish deployability on our 256-token FPGA context.
* **Deployable track:** actual platform bounds, including Qwen input plus reserved output <=256 and any deployed encoder limit. Proposed initial generator reservation96 leaves160 input tokens; this is a preflight candidate, not proof the catalog/plan fits or an instruction to change runtime. Determine sufficiency on development before freezing. Test gold outputs and generated length distributions; never truncate gold plans to pass.

Each model receives all semantically relevant information; token IDs need not match across different tokenizers. For CPU/FPGA runs of the same model, input IDs, chat template, stopping policy, tokenizer and wire format must match. Catalog/codec instructions count. No gold-based tool filtering. Shared explicit task-independent catalog partitions are an optional separate system, not an unreported shortcut.

Keep every sealed task in full deployment accuracy denominators, with capacity failures labeled. Also publish a pre-inference eligible subset to compare execution without capacity confounding. The energy panel is chosen from that subset with fixed stratum quotas before predictions. If a stratum cannot fit, report the missing support; do not replace it with easier tasks or enlarge context after seeing test outcomes. Retain an exclusion manifest and token-length distributions. A common encoder/decoder subset uses the intersection of actual limits, not an assumed 256 tokens for every bitstream.

Quantization has its own ladder: adapted float reference -> software reference for exported arithmetic -> FPGA. Compare intermediate fixtures, final IDs/ASTs and complete test task quality at each stage. CPU GGUF Q8_0 is not assumed bit-equivalent to FPGA integer weights. A same-model FPGA acceleration claim needs the same numerical contract; if only a different CPU quantization/runtime is available, label the result a system-configuration comparison and report output/quality differences.

## 6. Scoring and predeclared hypotheses

Primary capability score: exact semantic plan correctness, macro-averaged across six strata, with each stratum and generalization slice shown. Evaluate plans in the interpreter and also compare required calls, ordering, predicate strictness, evidence lineage, correct asset/units, clarification/rejection reason and prohibited extra actions. Permit explicitly enumerated semantically equivalent plans; freeze normalization and verifier before testing. Execution in one lucky world is insufficient.

Report separately:

| Dimension | Required metrics |
|---|---|
| Capability | Exact correct plans; correct actionable coverage; per-stratum and held-out-combination success; workflow completion |
| Reliability | Raw parse validity; schema validity; incorrect accepted plans / accepted plans; wrong execution attempts / all requests; clarification/rejection precision/recall; failure reason and status fidelity |
| Temporal behavior | Cold and resident complete-call latency; p50/p95 where supported; timeout fraction; whole-workflow time; throughput |
| Efficiency | Total and idle-subtracted J/attempt; correct actionable completions/J; complete correct workflows/J; measured memory footprint |

Unsupported/ambiguous requests remain in overall correctness and energy denominators but are not credited as completed maintenance work. Report them as correct terminal decisions separately. An always-reject policy has zero actionable coverage and zero useful maintenance completions/J. Distinguish model plan acceptance from the independent validator/executor admitting a proposal.

Hypotheses, not promised outcomes:

H1: an adapted generator improves held-out composition/context success relative to the strongest practical structured encoder at comparable accepted-error operating points.

H2: same-model FPGA execution improves resident total energy or latency without material task-quality loss relative to its CPU numerical reference.

H3, optional: explicit bounded state improves four-turn useful completion/energy relative to declared history baselines, after reducer costs and capacity failures are counted.

Calibration freezes one primary operating point per model: maximize actionable coverage subject to observed accepted-error <=1% on calibration. If no meaningful coverage meets this rule, report failure; this small calibration set does not prove a population1% bound. Show threshold curves for all models; do not claim matched risk when confidence intervals are broad. Grammar baseline may provide a discrete coverage point rather than a smooth curve. User-provided missing parameters can be clarified once in the workflow track, with all clarification time/energy counted; isolated-request scoring just scores the reason.

Suggested engineering promotion goals: >=95% exact actionable-plan accuracy on the deployable subset, >=90% macro terminal-decision correctness, >=80% actionable coverage, observed incorrect-accepted <=1%, and >=15% energy reduction versus the declared CPU system at comparable quality. These are proposed decision criteria, not established results or universal requirements. Report failures even if no candidate meets them. Freeze any revised margins on development before opening test.

## 7. Statistics and low-error claims

Use paired model comparisons by independent semantic family/request or workflow, clustering counterfactuals/paraphrases. Report95% uncertainty intervals for capability differences, accepted-error and energy ratios. Workflow steps are dependent; resample workflows, not individual steps. Quantization noninferiority requires a predeclared acceptable difference (proposed1 percentage point exact task accuracy) and a compatible confidence interval; failure to find significance is not equivalence.

Zero errors is not zero risk: with n independent accepted trials, one-sided95% upper error bound is 1 - 0.05^(1/n), about3/n. Even zero among1,000 gives about0.30%, not0.1%. The effective sample count may be smaller than request count because of template/author dependence. With actual errors use exact binomial intervals only where independence is defensible, alongside cluster-aware estimates.

If a below0.1% accepted-error claim is essential, run a separately frozen acceptance audit until at least3,000 unique independent accepted cases accrue, under a fixed threshold and a predeclared issued-case cap10,000. Stop based only on accepted count/cap, retain every issued case and error, and do not tune. About3,000 zero-error trials only support that bound under the specified distribution and assumptions; counterfactual repetitions do not qualify as new language trials. A diverse independently authored audit may dominate project effort. v1's1,800-case test supports a measured-rate statement, not arbitrary rare-error assurance.

## 8. FPGA/CPU experiment matrix

| Comparison | What it answers | Required boundary |
|---|---|---|
| R0/R1/E1/E2/L0/L1 software | Which model provides useful capability? | Same semantics, data and task budgets; record resource differences |
| Selected Qwen CPU vs FPGA | Does this deployment accelerate that model efficiently? | Same selected weights/arithmetic where qualified, input IDs, outputs/policy and complete host work |
| K26 CPU encoder/rules vs FPGA Qwen | Which local system gives the better capability/energy tradeoff? | Same board input or SOM boundary; quality differences shown; not a pure accelerator speedup |
| Selected encoder CPU vs its FPGA path | Optional extra hardware mechanism result | New heads/model binding, numerical/ABI/clock qualification first |
| v8 vs qualified successor | Optional hardware ablation | One fixed workload/model/state policy; configuration identity and repeats |

Only move forward with the FPGA paths that pass quality/context gates. Current Qwen v8 is a starting deployment, not evidence that adapted weights or a maintenance plan executor already work. FunctionGemma and ModernBERT remain software references unless separately ported. Current saved decoder status does not establish an active R5 terminal-control path. Record clock, memory, CPU governor/affinity, thermal/fan state, OS/runtime, model hashes and full build/package identity. Obey existing serial board reservation and inference locks; keep the stopped historical sweep stopped.

## 9. Energy campaign

Prefer a characterized DC-input meter for total board energy; use documented SOM_5V0 telemetry as a lower-effort primary boundary if no board meter exists, labeling every result SOM energy. Do not infer separate PS/PL/DDR power from the module monitor. Identify actual sensor/driver, units, averaging and fresh update cadence on the deployed image before testing. AMD documents the module monitor; access and time resolution remain to be verified. [AMD KR260 power guide](https://docs.amd.com/r/en-US/ug1092-kr260-starter-kit/Powering-the-Starter-Kit-and-Power-Budgets).

Qualify idle/load/idle response, timestamp alignment, stale samples, dropped reads and logger overhead against an external instrument where available. Keep voltage/current/power samples with instrument semantics. Calculate timestamp-weighted energy over the same marked work interval; do not multiply TDP or an unrelated average power by a request timer. Use multiple-request windows for very fast baselines when sensor response cannot resolve one request. Replay a varied frozen panel, not one cache-friendly repeated input, and call it repeated-work window energy. Never invent per-kernel energy from low-rate telemetry.

Two primary operating modes:

1. Resident sequential, batch1: weights/model/tokenizer resident, fresh logical request state/KV, no prefix reuse. Start at request reception on K26; stop when validated plan has completed its simulated execution. Count tokenization, model, parsing, state handling and tool simulation. Simulator steps are local deterministic operations with no artificial sleep; real network/device energy is outside this claim.
2. Cold application, weights resident: process/runtime/tokenizer setup and declared weight verification included; model provisioning/boot measured separately. Apply equivalent identity checks to CPU and FPGA or report their differing work explicitly. Do not compare cold CPU with resident FPGA.

For practical low-rate deployment add one optional fixed-arrival trace after sustained results, using1 request/30 s only if every selected system meets that service rate. If not, freeze a slower common rate on development. Include idle and queueing over the same observation horizon; report missed/deferred work. This prevents saturated energy/request from being mistaken for sparse-service battery savings.

Campaign sizes:

* Qualification:24 development requests spanning all six strata, at least three complete hardware blocks, before test; no energy ranking promoted here.
* Primary full deployment quality:1,800 isolated requests per selected deployment configuration once, including failures/capacity stops. Counterfactual interpreter replays need no extra inference. Run120 four-turn workflows once. This is quality evidence, not1,800 independent power repetitions.
* Energy panel:120 eligible isolated requests,20 per stratum, chosen by seeded stratification before any test predictions. Five independently ordered blocks on CPU and FPGA:600 requests per configuration. Include all120 even when they fail; do not choose only correct cases. Counterbalance CPU/FPGA block order and wait for a predeclared stable thermal criterion.
* Cold panel:24 preselected requests,4 per stratum, three blocks per configuration:72 calls/configuration. These are repeat timings/energy, not new semantic test cases.
* Workflow energy panel:24 workflows,6 per family, three blocks:288 maximum turns/configuration. Paired common scenarios, each backend's own actions/state. Failed early workflows are not assigned imaginary completion energy.

The isolated, cold and workflow energy panels imply960 generated calls/configuration before warmups, assuming every four-turn workflow completes. The full quality and energy campaigns imply up to3,240 generated calls/configuration (1,800+480+960); first quality runs may also have power traces but do not replace the repeated panels. At10 s/call this is9 core-hours/configuration before idle/transition overhead, purely planning arithmetic. Complete pilot timing before booking board hours; a minimum pilot is120 development cases and12 development workflows, with no paper-grade low-error claim.

For boundary B report:

    E_B = integral_window P_B(t) dt
    J_per_attempt = E_B / N_attempted
    incremental_J_per_attempt = (E_B - integral_window P_idle_hat(t) dt) / N_attempted
    useful_completions_per_J = N_correct_actionable_completions / E_B

Use total energy as primary; show idle subtraction as secondary, with same resident configuration. Include failures/retries/clarifications in energy even when useful count is zero. Never add SOM and board input energy: they overlap. For fast systems, include equivalent harness/dispatcher work or measure and disclose it separately. Measurements from another host that performs essential computation require that host's energy; a launch-only controller can remain outside the declared boundary. Respect sensor interval averaging rather than assuming arbitrarily fast point samples.

Analyze paired energy differences by independent block and task family, separating systematic instrument uncertainty from run variation. Five blocks provide an initial estimate, not rare-tail or multi-device generalization. Do not discard slow runs or clip negative idle-subtracted estimates. If intervals overlap zero/one for the declared energy contrast, report unresolved rather than claim a win.

## 10. Implementation sequence and release gates

| Stage | Deliverable | Gate |
|---|---|---|
| A: semantics, 2–4 days | AST/codec, tool simulator, reason policy, independent replay scorer,24 examples | Correct branch/reference/error behavior; encoder target representability; no hidden gold input |
| B: dataset and token audit, 1–2 weeks | Grouped6,000/900/1,800 corpus;120 workflows; provenance; context manifests | Human review, split/duplicate checks and realistic256-token eligibility; freeze protocol before test |
| C: software baselines, 1–2 weeks | Rules/ML/encoder/Qwen training, seed results and calibration | Generator has a useful capability tradeoff; select deployable checkpoint without test selection |
| D: deployment/energy qualification, 3–7 days | CPU arithmetic reference, versioned FPGA package, instrument collector | Numerical fixtures, model/task parity, measurement boundary/timing resolved |
| E: sealed campaign and analysis, 1–2 weeks | Raw traces, paired results, uncertainty and figures | Preserve failures; reproducible aggregates; claims limited to supported evidence |

Effort ranges are estimates with overlap and instrument/annotator access assumed. A new FPGA model port or a genuinely independent3,000-accepted-case audit adds substantial time. No guarantee of meeting promotion targets.

Stop or pivot if all realistic maintenance cases are solved equally well by cheap rules/encoder at lower cost; the outcome can support a simpler deployment. If generation helps capability but FPGA gives no energy benefit, report that distinction and optimize only after profiling. If compact state loses necessary facts, retain the failure as an information-loss result rather than repair inputs with gold.

## 11. Artifacts, logs and paper layout

Required future artifacts: versioned schema/codec; simulator and scorer; train/tune/calibration/test/workflow manifests and licenses; token-budget/exclusion ledger; exact model revisions and quantization manifests; training and deployment recipes; instrument configuration; timestamped raw readings; immutable attempt JSONL; aggregate recomputation; reliability/coverage curves; energy/latency Pareto plots; failure taxonomy.

Each attempt must include case/group/split/scenario IDs, backend and checkpoint hashes, numerical mode, prompt and input IDs/hash, actual input/output counts, EOS/finish reason, raw response, decoded AST, validation/execution verdict, state before/after, all tool results/epochs, phase timestamps, configuration/boot identity, and aligned power-window IDs. Gold labels live in a separate scoring file. Missing output, capacity failure, administrative abort and runtime error are distinct.

Paper structure: task and typed contract; dataset/generalization design; capability comparison; same-model FPGA qualification/performance/energy; reliability and failure behavior; optional bounded-state ablation. Use MLPerf's complete-system/quality-aware principles without labeling this custom task an MLPerf result. [MLPerf Power framework](https://mlcommons.org/2025/03/ml-commons-power-hpca/).

This plan is intentionally neutral about whether an LLM is the best model. The desired conclusion must be earned by capability at a declared error/coverage operating point and measured complete-system cost.
