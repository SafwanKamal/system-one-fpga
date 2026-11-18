# Maintenance probability-output models

Designed October 25, 2026. Local software experiment; no board access or energy measurement.

## Question

Does replacing autoregressive plan generation with explicit choice probabilities improve complete maintenance decisions, conditional reliability, and useful uncertainty? The existing stress set has already been inspected, so it remains development evidence. This campaign does not create an independent publication test.

## Implementations

The Qwen variant starts from the original official Qwen3-0.6B weights, not the maintenance-generating checkpoint. The entire backbone is frozen. Public input is encoded once into token features. A learned question projection attends to these features; a shared scorer compares that context with candidate-description embeddings from the same frozen backbone. Each question produces a softmax over its supplied candidates. There is no vocabulary projection or output-token decode loop.

This borrows the decision-head idea from [NanoJev](https://github.com/TianyuCodings/NanoJev), whose public [model card](https://huggingface.co/C-Tianyu/NanoJev) describes a Qwen3-0.6B backbone and candidate scoring. It is not a NanoJev reproduction: that implementation conditions backbone representations on each state/question/candidate path and has a set-attention choice head. Its released game checkpoint is not used here. Our head-only, shared-state design is a bounded first experiment; a poor result would not establish a limit of NanoJev or broader backbone adaptation.

Laya uses the released [typed-decisions checkpoint](https://huggingface.co/convaiinnovations/laya-typed-decisions), revision `e929ae5cf69bc34259cd2f95c9e91145b818b1f0`. Its [runtime source](https://github.com/NandhaKishorM/laya) is pinned to `a478221bcad24d1a9c47b361c79328ebd2b100c6`, installed without changing existing dependencies. The advertised package version was unavailable through PyPI. The adapter uses its native choice sequence builder, sequential option layout, and raw float32 decision logits. It performs no maintenance weight updates. Task calibration is fitted separately, and the published vendor temperature map is also evaluated as a probability reference. Temperatures change probability sharpness, not argmax decisions.

Both adapters use training-derived domains for the same factorized maintenance fields as the existing controls. Constants are fixed from training. Variable choices include an absent/not-applicable value. The shared unflatten function and strict validator assemble decisions without repair. No gold-dependent option pruning, fallback parser, sensor access, or external tool execution is present. Candidate domains are closed to the values in the original training set; arbitrary new thresholds and general long chains are outside this pilot.

## Data and selection

`build/v2/maintenance-decisions-v4` contains byte-identical copies of the sealed v3 training720, tuning120, fresh120 and crossed-conditional64 files. A separate calibration120 set uses new seeds and asset IDs81–84, with20 records per stratum. Exact public-input overlap with other splits is checked. The same authored template families remain, so distinct IDs and inputs do not establish independent language generalization.

The explicit overlap audit finds99 distinct raw public calibration inputs and59 distinct normalized model-visible inputs in those120 records. Calibration has zero normalized-input overlap with training or conditional stress, but33 normalized inputs also occur in tuning and5 in fresh. These counts reflect entity-index normalization and repeated templates. The calibrators therefore fit a template-distribution pilot, not independent operator language. Record-count binomial bounds are descriptive under an independence assumption; related templates and repeated normalized inputs limit their evidential strength.

The shared Qwen head trains for80 epochs, seed0, AdamW1e-3, batch16. Active gold fields receive weight1 and inactive fields0.05. Checkpoint selection maximizes tuning complete-plan correctness, with active-field NLL breaking ties. Gold-active masks are used for training and scoring only; prediction assembly and confidence use predicted structural dependencies. Frozen float32 features can be reused without changing backbone weights.

The completed frozen-head ablation selects epoch78 by the declared tuning rule and is weak on the existing development sets (fresh73/120; stress8/64). `adaptation-amendment.json` therefore declares a second variant that trains the final two Qwen decoder blocks and the same shared head. It initializes from the tuning-selected frozen head and the original pretrained decoder blocks, then trains six epochs with decoder LR1e-5, head LR1e-4 and batch8. Earlier blocks, final normalization and question/candidate embeddings stay frozen. Selection still uses tuning complete-plan correctness, then active-field NLL. This architecture decision was made after inspecting frozen-model development results; it is not a prospectively blinded comparison. The initial variant and all its outputs remain preserved. The adapted run selects epoch6 and updates31,828,225 parameters, including366,337 in the head. It reaches fresh81/120 and stress6/64: adaptation improves the fresh result but does not improve conditional recombination. These are single-seed development results, not a search over candidate-conditioned architectures.

TF-IDF and MiniLM retain their original sealed checkpoints. Fresh/stress raw decisions must exactly reproduce the archived predictions before calibration results are accepted. The original Qwen and FunctionGemma generators retain their selected weights and fresh/stress outputs. New calibration requests are decoded with their original full-contract, greedy float32 setup. Teacher-forced selected-token probabilities supply a minimum-token-confidence surrogate for separate plan-level calibration. This is not a typed choice distribution, so operator-choice NLL is unavailable for generators. The confidence policy is recorded before collecting generator calibration outputs in `generator-confidence-amendment.json`.

## Complete-decision results

| Model | Fresh correct /120 | Familiar conditional /20 | Crossed conditional correct /64 | Wrong accepted stress plans |
|---|---:|---:|---:|---:|
| Rules |120|20|64|0|
| TF-IDF |108|9|28|34|
| MiniLM encoder |82|5|3|61|
| Qwen generative SFT |111|15|22|23|
| FunctionGemma generative SFT |99|9|27|30|
| Qwen shared decision head, frozen backbone |73|7|8|56|
| Qwen shared decision head, final-two-block adaptation |81|7|6|58|
| Released Laya, current field adapter |0|0|0|0|

Laya produces only4 structurally valid fresh decisions, including2 accepted plans, and no valid stress decision. Its zero wrong accepted stress plans comes with zero useful stress coverage. The released checkpoint and this field-question adapter do not transfer to the maintenance schema in this test. Native-API and CPU/GPU numerical parity checks qualify the integration, not its semantic performance. This does not evaluate a maintenance-fine-tuned Laya model.

The probability-output Qwen prototypes do not improve complete-plan or conditional accuracy over the existing generative Qwen or TF-IDF controls. Candidate probabilities and typed field domains alone do not enforce a coherent plan or robust condition semantics. The implementation differs materially from NanoJev, so these results assess this bounded shared-state prototype. Calibration can change confidence and abstention while leaving those decisions unchanged. The full calibration and coverage results are saved separately in `build/v2/maintenance-decisions-v4/REPORT.md` and `comparison.json` after every required confidence run finishes.

## Calibration and reliability

After checkpoint selection, fit one positive scalar temperature per model by minimizing gold-active field NLL on calibration120. This changes probabilities without changing argmaxes. Fit a separate regularized one-dimensional logistic map from minimum predicted-active-field confidence to complete-plan correctness. This avoids treating field probabilities as independent. Structurally invalid plans receive correctness probability0. The temperature and logistic map share calibration records; all calibration quality claims come from evaluation, not fit-set scores.

For generators, fit the same regularized one-dimensional logistic map to minimum selected-token probability over the emitted tokens, excluding EOS. Vocabulary softmax probabilities are measured from model logits, not inferred from token strings. A shifted-token parity test compares this computation with cached generation scores for both Qwen and Gemma, including sliding attention and logit softcapping. Whole-plan Brier/ECE/coverage can then be compared across systems, with the different confidence surrogates stated explicitly.

Report raw and scaled field NLL, multiclass Brier (sum of squared class errors), ten-bin equal-width ECE, and conditional-operator metrics. Report complete-decision Brier/NLL/ECE separately. Coverage thresholds are calibration confidence quantiles for nominal25%,50%,75% decision coverage; ties and distribution shift can change actual evaluation coverage. Also report wrong selected plans and correct actionable completion, with one-sided95% binomial error upper bounds. These small authored datasets cannot establish a low production error guarantee.

The finished stress comparison shows that confidence calibration does not rescue capability. TF-IDF conditional-operator NLL worsens from0.941 to1.356 after fitting temperature on the calibration distribution, even though its aggregate active-field NLL improves. The frozen and adapted Qwen heads reduce operator NLL from4.865 to2.535 and6.314 to2.470, respectively, while retaining their original wrong argmax decisions.

At the predeclared nominal75% calibration-coverage threshold, the generative Qwen selects12/64 stress requests with0 observed errors; actual stress coverage is18.75%. TF-IDF selects24/64 with4 errors, and the adapted Qwen decision head selects16/64 with12 errors. These are different actual coverage levels, not a matched-coverage ranking. Even12 zero-error selections yield a22.1% one-sided95% binomial error upper bound under independence, before accounting for template dependence. This is pilot abstention evidence, not a reliable low-error guarantee.

Laya's stress full-pipeline Brier is0 because all64 outputs are invalid and receive known correctness probability0; accepted-plan Brier is correctly N/A. This illustrates why capability, structural validity, coverage and calibration must remain visible together. Detailed metrics and all three fixed operating points are retained in the final comparison.

## Cost and numerical scope

The selected Laya sweep runs float32 through ONNX Runtime DirectML on the Radeon780M. All other primary models run float32 CPU. Maximum logical input per sequence is1024 tokens, with no output reservation for choice models. The GPU graph has a fixed batch1/sequence288/marker10 envelope covering the audited maximum270 actual input tokens; this is not a test of1024-token requests. Laya scores24 variable field questions per request. Runtime observations include repeated question-row work and are not controlled FPGA latency comparisons. Qwen reuses state features and static question/candidate embeddings. Its cached head evaluation timings omit backbone cost and must not be compared directly with end-to-end Laya timings.

Initial CPU float32 and bfloat16 Laya attempts remain archived. The bfloat16 numerical probe preserved all120 sampled field argmaxes on five calibration requests, with maximum probability change0.00915. No partial CPU outputs enter the selected GPU calibration fit. GPU selection uses calibration-only numerical and runtime checks, not evaluation accuracy. A static specialization of124 ONNX Reshape inputs works around the DirectML/dynamo view-shape initialization failure while preserving fixed-envelope tensor shapes and weights. Five calibration requests match CPU float32 choice argmaxes throughout, with maximum probability difference0.00000692. The profile records121 DmlExecutionProvider events and no CPU node events for the qualified runs.

For the same first calibration request, observed complete-request times are19.18s CPU float32,9.61s CPU bfloat16 and6.38s GPU float32. CPU batches24 question rows; the fixed GPU graph runs one question row per call. These are diagnostic observations with different batching, not a controlled hardware comparison. The local AMD NPU is present and healthy with driver32.0.203.297, but no NPU model run was performed. AMD's [current support table](https://ryzenai.docs.amd.com/en/latest/relnotes.html) does not list floating-point NLP for this Hawk Point generation. The GPU uses the [DirectML execution provider](https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html); it does not require a supported ROCm device or changes to the installed GPU/NPU drivers.

## Implication for the FPGA study

Keep TF-IDF, the existing generative Qwen checkpoint, and the exact rule solver as capability controls. This pilot provides no accuracy reason to replace them with the shared Qwen decision head or released Laya. A more faithful candidate-conditioned Qwen experiment or maintenance-specific Laya adaptation would be a new training experiment with a declared budget; the current negative results should remain visible. For the ML path, explicit comparison, numeric-threshold and plan-dependency representations are a more targeted next experiment than a larger bag-of-words model.

Before making a deployment reliability claim, lock a test set with unseen language/template families and numerical boundary cases, using calibration inputs disjoint at the normalized model-visible level. Include genuinely long requests near the1024-token limit and clearly distinguish the current maximum-three-step task from general long-chain planning. Predeclare a tolerated error rate and report coverage and correct actionable completion at that operating point.

Measure FPGA energy on models that offer useful capability at the chosen reliability target. Report energy per attempted request alongside energy per correct accepted task, errors, and abstention coverage. Include the complete deployed pipeline and account for host, memory, preprocessing and output assembly. The present CPU/GPU latency probes establish a practical software runtime, not FPGA power, device energy efficiency, or production reliability.

## Reproduction

```powershell
.venv/Scripts/python.exe scripts/v2/maintenance_decisions.py prepare
.venv/Scripts/python.exe scripts/v2/maintenance_decisions.py features --threads 4
.venv/Scripts/python.exe scripts/v2/maintenance_decisions.py train --threads 4
.venv/Scripts/python.exe scripts/v2/maintenance_decisions.py prefix --threads 4
.venv/Scripts/python.exe scripts/v2/maintenance_decisions.py train-adapted --threads 4
.venv/Scripts/python.exe scripts/v2/maintenance_decisions.py laya --threads 4
.venv/Scripts/python.exe scripts/v2/maintenance_decisions.py controls --threads 2
.venv/Scripts/python.exe scripts/v2/maintenance_decisions.py generators --generator qwen --threads 4
.venv/Scripts/python.exe scripts/v2/maintenance_decisions.py generators --generator functiongemma --threads 4
.venv/Scripts/python.exe scripts/v2/maintenance_decisions.py report
.venv-maintenance-accel/Scripts/python.exe scripts/v2/verify_maintenance_decisions.py
```

The command block above is the CPU route for a fresh work directory. The selected GPU route instead uses `probe_maintenance_directml.py ready`, `export`, `static`, `probe`, and `evaluate` in the isolated accelerator environment. Its qualification step expects CPU FP32 calibration references through index80 under `laya-float32-qualification/calibration-predictions.jsonl`; these references were archived before the BF16 attempt in this campaign. For a new GPU campaign, copy the completed CPU FP32 calibration reference there before running `probe`. Pass the same `--work` argument to every command when using a new directory. `laya-runtime-selection.json` fixes the qualified `laya-directml` folder as the primary Laya result. CPU `laya` runs above are fallback/qualification attempts, not additional primary evaluation records. The accelerator environment uses the original benchmark packages through a local `.pth` file, adding ONNX Runtime DirectML1.24.4, ONNX1.23.2 and ONNXScript0.7.2 without replacing the working PyTorch installation.

Use a new `--work` directory for an independent campaign. Laya resumes completed requests by ID, allowing runtime-only changes to batch/thread settings; inputs, model weights and raw output mappings remain fixed. Source snapshots are journaled per invocation. For the two Qwen training runs, model metadata now points to the executed invocation snapshot; an earlier end-of-run hash observed later edits to the script. The originally observed hash is preserved as `source_hash_at_metadata_write`, and verification checks the corrected hash against the training invocation ledger. Weights and predictions are unchanged. The final comparison, verification and artifact seal establish completion; a launched job alone does not.
