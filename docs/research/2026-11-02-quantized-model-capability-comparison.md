# Quantized model capability comparison — November 2, 2026

**Recommendation: keep FPGA implementation on hold for this combined objective. Use Qwen3-1.7B Q4 as the next software baseline for targeted adaptation and an interactive tool interface. The current comparison does not justify a larger-model hardware port or establish bounded reliable maintenance planning.**

Qwen3-1.7B Q4 won the registered equal-weight screen among the eight primary Q4 profiles across maintenance, conditional planning, general function calls, and simulated two-turn decisions. The separate 8B Q2_K boundary profile scored slightly higher on that pilot balance, but its shared-DDR fit is particularly uncertain. Neither is a global most-capable model or a proven physical fit. The models still make substantive task errors; increasing parameter count alone did not resolve the complete-plan contract.

## What was measured

Eight pretrained Q4 release profiles were screened, plus a Qwen3-8B Q2_K memory-boundary profile. Each screen has 104 task records: 24 fresh maintenance cases, 24 conditional maintenance cases, 50 public BFCL Python function-call cases balanced across five categories, and six simulated two-turn decisions. Two fixed maintenance training examples were supplied uniformly. Direct JSON and each checkpoint’s embedded native tool format were compared on 22 separate development cases; the better route was frozen separately for maintenance and general use.

The primary finalist rule selected the equal-weight four-axis winner plus the highest-ranked remaining conventional Qwen/Qwen2-family candidate, preserving a closer hardware implementation path. The 8B boundary profile advanced when no smaller screened profile matched or exceeded all four axes. These registered choices were evaluated on 396 records: 120 fresh maintenance, 64 conditional, 200 BFCL, and 12 simulated two-turn decisions. Screen cases are a subset of this larger set, so confirmation is not an independent test. The conditional sample crosses gt/ge/lt/le. Maintenance correctness requires the exact canonical plan and agreement with the existing simulator on counterfactual states; this measures our complete structured-plan contract, not open-ended prose quality.

This common-profile comparison does not replace family-specific sampling or prompt optimization; those searches were not performed. Primary decoding used 2,048 total context tokens and at most 256 generated tokens, greedy unconstrained vocabulary, no JSON grammar or semantic repair, and thinking disabled. Admission reserves the full output-token allowance within the context limit. Context rejection and truncated output count as failures. Native assistant messages without tool calls count as no calls; malformed call frames remain failures. Model-native special tokens are restored from saved token IDs before parsing. Completed reasoning blocks and whole Markdown fences are removed as transport formatting; argument values, operators and plan steps are not repaired. JSON, documented XML-style arguments, and literal native function-call frames are normalized without changing their meaning.

All primary inference used the pinned llama.cpp b11540 Vulkan runtime on the local Radeon 780M, four requests concurrently. A small CPU/GPU qualification matched prompt IDs on 11/11 probes and raw outputs on 10/11; one decision differed, so CPU attempts were retained separately and the entire primary comparison used GPU. This is quantized-weight software capability, not FPGA arithmetic, timing, power or physical-design qualification. No board access, paid compute, new training, or real external tool actions occurred. The two-turn experiment feeds a simulated sensor result as a user message; it is not a live tool-role integration or broad multi-turn benchmark.

## Initial screen

| Profile | Weight file GiB | Fresh maintenance | Conditional plans | General calls | Simulated two-turn |
|---|---:|---:|---:|---:|---:|
| qwen06-q4 | 0.356 | 2/24 | 0/24 | 33/50 | 4/6 |
| qwen17-q4 | 0.984 | 4/24 | 0/24 | 44/50 | 6/6 |
| qwen4-q4 | 2.213 | 6/24 | 1/24 | 42/50 | 4/6 |
| qwen35-2-q4 | 1.131 | 3/24 | 3/24 | 30/50 | 6/6 |
| qwen35-4-q4 | 2.406 | 7/24 | 0/24 | 31/50 | 6/6 |
| xlam3-q4 | 1.698 | 3/24 | 2/24 | 43/50 | 4/6 |
| lfm12-q4 | 0.648 | 0/24 | 0/24 | 34/50 | 6/6 |
| smol3-q4 | 1.687 | 3/24 | 4/24 | 19/50 | 1/6 |
| qwen8-q2 | 3.056 | 6/24 | 2/24 | 38/50 | 6/6 |

Key names: qwen35 denotes Qwen3.5; xlam3 is xLAM-2-3b-fc-r; lfm12 is LFM2.5-1.2B-Instruct; smol3 is SmolLM3-3B. Exact release filenames identify all profiles in models.json. File labels are release names, not uniform arithmetic precision: actual GGUF tensor mixtures include higher-precision embeddings/output and other tensors. Models, revisions, exact file hashes, tensor audits and runtime hashes are in the accompanying receipts. Qwen3.5 and LFM require different operators from the existing Qwen3 engine.

## Larger-set results

| Profile | Fresh maintenance | Conditional plans | General calls | Simulated two-turn | Wrong accepted maintenance plans | Context rejections |
|---|---:|---:|---:|---:|---:|---:|
| qwen17-q4 | 15/120 | 0/64 | 172/200 | 9/12 | 67 | 0 |
| qwen4-q4 | 32/120 | 4/64 | 170/200 | 4/12 | 36 | 0 |
| qwen8-q2 | 28/120 | 6/64 | 171/200 | 12/12 | 22 | 0 |

Among the three confirmed profiles, **qwen8-q2** has the highest descriptive four-axis mean (0.546); that mean is not a reliability probability. **qwen17-q4** has the most correct general calls (172/200); **qwen4-q4** has the most correct complete maintenance outcomes (36/184). This ranking applies only to these tested profiles and budgets, and does not establish FPGA fit.

Parsed outcomes equivalent to gold under the project simulator’s counterfactual checks: qwen17-q4 15/184, qwen4-q4 36/184, qwen8-q2 34/184. Invalid plan syntax is counted as a failure here as well. These simulator checks are not physical-domain validation.

The 292 confirmation records outside the screening subset are shown separately below. They were newly run after selection in this comparison, but come from the same public/template-derived distributions and are not a blind independent validation set.

| Profile | Additional fresh /96 | Additional conditional /40 | Additional general /150 | Additional two-turn /6 |
|---|---:|---:|---:|---:|
| qwen17-q4 | 11 | 0 | 128 | 3 |
| qwen4-q4 | 26 | 2 | 128 | 1 |
| qwen8-q2 | 22 | 4 | 133 | 6 |

Repeated screen cases had identical first-turn prompt IDs in screening and confirmation. Greedy decoding still did not guarantee identical generated text under different batches. Observed repeated-case agreement:

- qwen17-q4: 104/104 same correctness decisions; 94/104 identical first outputs.
- qwen4-q4: 102/104 same correctness decisions; 98/104 identical first outputs.
- qwen8-q2: 104/104 same correctness decisions; 99/104 identical first outputs.

“Wrong accepted” means the parser accepted a plan-shaped output whose full decision was wrong. It does not mean a hardware gate executed it. Examples include dropping the requested conditional action, replacing a contradiction/clarification outcome with a metric read, or adding an unrequested threshold guard. These errors survive syntax validation. In a simulated strict-above-70 request, Qwen3-4B proposed both read_sensor and open_inspection before the sensor result was available. That is a dependency error in ordinary function calls, separate from the maintenance wire format. No proposed actions were executed.

Observed larger-set software wall times below include formatting/tokenization/completion and four-way request contention; a two-turn record combines both turns. They exclude model startup, warmup, final control-token detokenization and scoring. Context rejections return quickly and remain in the distribution. These are host observations, not comparable FPGA latency or worst-case deadlines.

| Profile | Median wall s | p95 wall s | Maximum wall s | Truncated records | Median generated tokens | Maximum prompt tokens |
|---|---:|---:|---:|---:|---:|---:|
| qwen17-q4 | 4.14 | 7.69 | 10.04 | 2 | 45.0 | 848 |
| qwen4-q4 | 9.60 | 15.67 | 20.71 | 0 | 33.0 | 666 |
| qwen8-q2 | 24.91 | 41.37 | 53.11 | 1 | 51.5 | 888 |

## Precision and budget sensitivity

The fixed precision subset has 32 records (12 fresh, eight conditional, ten BFCL, two simulated episodes). Q4 and Q8 releases use the same first-turn prompt IDs, one request slot, 2,048 context and 256 output. Q8 is a higher-weight-precision software comparison; neither profile is a float32 reference or an FPGA bit-accurate simulation. Second-turn histories can differ when first-turn generated text differs.

| Profile | Q4 correct /32 | Q8 correct /32 | Q8 file GiB | Correctness disagreements |
|---|---:|---:|---:|---:|
| qwen17-q4 | 12 | 12 | 1.708 | 2 |
| qwen4-q4 | 12 | 13 | 3.986 | 3 |

The 4B Q8 reference already exceeds 4 GiB when its 2,048-token BF16 KV cache is added, before OS/workspace costs; it is not a fully resident candidate at that setting. The 1.7B Q8 reference plus that cache is about 1.93 GiB before other costs. It follows the existing Q8 arithmetic family more closely than Q4, but still needs wider workspaces, a larger model address extent, allocation changes and FPGA arithmetic qualification. The software Q4 baseline is therefore not an automatic decision about the cheapest hardware port.

Only primary-finalist context-overflow cases were separately retried at 4,096 context, keeping the 256-token output budget. Those retries are diagnostic and do not replace failures in the 2,048-token scores.

- qwen17-q4: no primary context overflows to retry.
- qwen4-q4: no primary context overflows to retry.

A separately registered paired ablation used the same fixed 32 IDs with 4,096 context and 1,024 total generated tokens, including reasoning. Routes were reused from the primary development comparison. This is exploratory evidence collected after the short-profile results, not matched-budget evidence against the 256-token screen.

| Profile | Thinking off correct /32 | Thinking on correct /32 | On-mode truncated records | On-mode median generated tokens | On-mode median wall s |
|---|---:|---:|---:|---:|---:|
| qwen06-q4 | 11 | 8 | 9 | 602.5 | 20.94 |
| qwen17-q4 | 12 | 11 | 2 | 112.0 | 6.90 |
| qwen35-2-q4 | 13 | 9 | 20 | 1024.0 | 61.25 |
| qwen35-4-q4 | 14 | 6 | 20 | 1024.0 | 147.74 |

The publisher supports both modes but recommends nonzero-temperature sampling and much larger maximum output allowances (32,768 for most queries). Our greedy 256/1,024-token profiles do not reproduce those quality-oriented settings. Budget-exhausted answers therefore do not establish intrinsic inability or a capability ceiling. Larger-budget sampled profiles remain untested. Sources: [Qwen3.5-2B guidance](https://huggingface.co/Qwen/Qwen3.5-2B#best-practices), [Qwen3.5-4B guidance](https://huggingface.co/Qwen/Qwen3.5-4B#best-practices).

The registered promotion rule selected **no profile** for a 104-record thinking-enabled screen.

## Existing adapted-model control

The existing sealed maintenance-SFT-v3 Qwen3-0.6B checkpoint was exported without retraining, then quantized to Q4_0 and Q8_0 and evaluated under the same primary screen and route-selection procedure. This is a task-adapted control with an unequal training budget, not part of the pretrained model ranking.

| Adapted profile | Fresh maintenance | Conditional plans | General calls | Simulated two-turn |
|---|---:|---:|---:|---:|
| qwen06-sft-q4 | 8/24 | 0/24 | 23/50 | 4/6 |
| qwen06-sft-q8 | 11/24 | 0/24 | 27/50 | 4/6 |

Historical float32 task-adapted results (111/120 fresh, 22/64 conditional) used a different prompt/framing/backend and are not a paired quantization comparison. Their difference from these controls cannot be attributed solely to quantization. The deterministic authored-template rule baseline scores 120/120 fresh and 64/64 conditional; it verifies the evaluator on those templates, not broad language capability.

## FPGA implication

The KR260 has 4 GiB shared DDR. Actual Qwen3-1.7B Q4 release weights occupy 0.984 GiB; estimated BF16 KV at 2,048 total tokens adds 224 MiB, giving about 1.203 GiB before Linux, activations, scratch, alignment and allocation overhead. Qwen3-4B Q4 occupies 2.213 GiB plus 288 MiB KV, about 2.494 GiB before those costs. Qwen3-8B Q2_K occupies 3.056 GiB plus 288 MiB KV, about 3.338 GiB before those costs, leaving a particularly narrow unproven shared-memory margin. These are analytic budgets, not allocation or routed-fit results.

The current driver and HLS decoder each impose a separate 1 GiB model extent. The current Q8 matrix path does not execute the tested mixed Q4/Q2 releases directly. Supporting only Q4_0 would not cover every tensor type in these files; repacking or requantizing them would create a new profile requiring capability re-evaluation. Wider workspaces, packing/dequantization, head-group limits and physical routing must be implemented and tested. Historical v9e routing already occupied 96.07% of CLBs and 84.72% of BRAM, so fitting weights in DDR is insufficient evidence of FPGA fit.

The 128-bit, 250 MHz memory port has a nominal 4 GB/s ceiling. If every output token streams the whole weight file once, file-size/bandwidth gives rough full-file streaming scenarios of about 0.264 s/token for 1.7B Q4, 0.594 s/token for 4B Q4, and 0.820 s/token for 8B Q2_K. Actual traffic excludes some stored metadata/embeddings but includes other state, and achieved bandwidth is lower; these are rough scenarios, not rigorous latency bounds. Hundreds of reasoning/output tokens therefore have a serious latency cost on this architecture. Existing hardware measurements and operator/resource details are in the [preceding feasibility report](2026-11-02-model-capability-feasibility.md).

## Decision and what remains feasible

For the combined maintenance-planning and general-tool objective, the tested configurations do not establish useful bounded reliability for the current complete-plan contract, so this evidence does not justify a new FPGA implementation. The useful candidate to carry forward in software is Qwen3-1.7B Q4: it won the registered balanced screen among the eight primary Q4 profiles, uses much less DDR than the larger dense candidates, and is closest to the existing architecture family. This recommendation is for further capability work, not authorization to call it deployable or reliable.

Two software directions remain open before any port decision: evaluate explicit read-then-decide tool interactions and a simpler plan interface with matched targeted adaptation; or test a larger-budget, publisher-sampled reasoning profile if its latency could be useful. The small simulated two-turn successes support investigating the interface direction; they do not prove robustness or substitute for complete maintenance plans. If that revised software task cannot reach useful accuracy on an independent, domain-reviewed set, the hardware port should remain deferred.

The hybrid Qwen3.5-2B remains relevant to the second direction: extrapolating the pinned BF16-KV/FP32-state formula to a hypothetical 65,536 total-token context gives about 1.90 GiB of weights plus state before OS/workspace costs. That is an analytic memory scenario, not a tested profile, latency result or FPGA fit. It leaves a plausible memory route to much longer reasoning than the ablation, with new-kernel and completion-time costs still unresolved. We have not established the globally strongest deployable model.

We can currently bound input/output capacity and enforce a generation cap in software; we cannot infer a production error bound or FPGA deadline from this study. Acceptance thresholds should be chosen after specifying the allowed maintenance decisions, cost of a wrong action/clarification, context envelope, and independent evaluation distribution. Avoid deriving a 99%/99.9% reliability claim from this public, template-related sample.

## Evidence and limitations

Re-executed the same pinned scorers on 2,716 saved task records with zero discrepancies, verified stage IDs/cardinalities, all evaluated weight hashes, frozen data hashes, matched precision prompts, and 23 focused tests. The 210 positive BFCL fixtures pass the pinned checker. Separate re-scoring is not independent ground-truth annotation.

Primary raw prompts, token IDs, responses, timings, source snapshots and earlier failed attempts remain under `build/v2/model-capability-20261102*`. Initial zero-shot codec failures, CPU attempts, native-token/parser corrections, superseded scores and amendments were preserved rather than selected away. There was no blind test, human maintenance-domain review, exhaustive candidate search, equal-budget adaptation of all models, real tool execution, FPGA arithmetic validation, or measured FPGA latency/energy. Public benchmark contamination and correlated template variants remain limitations.

Compact reports, pinned manifests, full score breakdowns, runtime inventory, precision/reasoning receipts, and verification are in [model-capability-2026-11-02](model-capability-2026-11-02/verification.json). The [evidence manifest](model-capability-2026-11-02/evidence-manifest.json) hashes the retained build artifacts; the [final seal](model-capability-2026-11-02/final-seal.json) hashes the compact evidence package.
