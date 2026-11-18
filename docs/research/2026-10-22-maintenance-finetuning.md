# Maintenance fine-tuning: Qwen and FunctionGemma

Designed: 2026-10-22; completed: 2026-10-23. CPU software study; no FPGA access or energy measurement.

## Question and controlled comparison

Does supervised task adaptation improve complete maintenance-plan correctness, especially guarded actions and comparison operators, enough to beat the cheap text classifier and the adapted encoder?

The campaign is in `build/v2/maintenance-sft-v3`. Its protocol fixes 720 training records, 120 tuning records, six epochs, seed 0, AdamW at 5e-5, four-record gradient accumulation, and training of the final two decoder blocks only. Earlier blocks, embeddings, normalization outside those blocks, and the vocabulary head remain frozen. Select the checkpoint with minimum tuning completion-token cross entropy, with earlier epochs winning exact ties. Neither evaluation split contributes weight updates or checkpoint selection.

The older 120-record audit has already been inspected, so it is explicitly a regression set. Another 120 requests use new seeds and asset IDs, but retain the authored template families. This fresh replication is not independent human-authored evidence or a structural generalization test. Rules, TF-IDF and MiniLM use their sealed, unchanged revision2 checkpoints on the fresh requests; their old audit results are independently rescored. No claim of equivalent training compute or optimal model-family adaptation follows from equal record counts.

A separate 64-request conditional stress extension was frozen before generator evaluation. It crosses four operators, two threshold types (70 C/configured limit), two actions (report/inspection), history/no-history, and two priorities. It breaks operator/action/threshold correlations in the original templates, uses another new asset catalog, and tests correct branching at below/equal/above thresholds plus read failure. Its labels are programmatically authored, not independently reviewed. No stress cases enter training or checkpoint selection. Its own data hash and protocol are in `conditional-protocol.json`.

Both models retain a 1024-token total context with 256 output tokens reserved. Prompts include the full maintenance contract. Qwen uses the existing nonthinking maintenance-array format without demonstrations. FunctionGemma uses its official tokenizer chat template, native function-call delimiters, and one `submit_maintenance_plan(plan_json: string)` function that carries exactly the same maintenance-array payload. The wrapper adapter performs exact delimiter matching and string extraction only; it does not infer, repair or replace any semantic field. This tests a native function interface around a custom plan language, rather than direct calls to eight individual maintenance tools; other interfaces remain possible future ablations.

Fine-tuning and the main capability reference both use float32 on the local CPU, with greedy full-vocabulary decoding and no grammar restriction, output repair or fallback. The original protocol proposed PyTorch dynamic-int8 Linear layers, but that path failed tuning-only numerical qualification and was superseded by `precision-amendment.json`. Previously decoded dynamic-int8 attempts are archived separately and excluded from main capability scores. A difference from the older llama.cpp Qwen Q8 score combines task adaptation and backend/precision differences; this is not an FPGA numerical qualification.

For the first tuning request, Qwen's completion-token loss is 0.0000162 in float32 versus 2.095 under the dynamic-int8 path; FunctionGemma's is 0.000233 versus 2.270. Normal and cached float32 losses agree, and float32 predicts the expected first token and output prefix. These measurements isolate an unqualified numerical inference configuration rather than a failure of the trained float32 weights. Both checkpoints remain unchanged. No trained fresh or conditional-stress outputs had been decoded before the precision amendment. The generic int8 API smoke tests established that generation could run, not numerical fidelity. A weight-only or hardware-specific quantization requires its own qualification before deployment claims.

Local CPU jobs may overlap. Recorded inference durations are diagnostic observations, not a controlled latency comparison. Energy remains unmeasured. The existing ML and encoder baselines use factorized categorical fields; this run does not establish the limit of stronger span-based or structured encoder designs.

Matched-backend pretrained references use a predeclared balanced subset of 24 fresh requests: the first four distinct public inputs per stratum, selected without prediction results. Their before/after scores use exactly those same 24 requests and the same inference backend. Adapted-model main comparisons still use all 120 fresh requests, all 120 regression requests, and all 64 conditional stress requests. The reference subset is frozen in `pretrained-reference-ids.json` before generator evaluation; its scores must retain their 24-request denominator.

## Training implementation and verification

The trainable Qwen source is `models/Qwen3-0.6B-HF`, downloaded from the official [Qwen model repository](https://huggingface.co/Qwen/Qwen3-0.6B); file hashes are retained with each model run. FunctionGemma uses the existing official cached snapshot `39eccb091651513a5dfb56892d3714c1b5b8276c`. Earlier task checkpoints are not used to initialize either generator.

Qwen has 596,049,920 total parameters and 31,461,888 trainable parameters. FunctionGemma has 268,098,176 total parameters and 11,147,264 trainable parameters. Equal final-block counts are a bounded adaptation policy, not equal parameter or compute budgets and not full-model fine-tuning.

Frozen-prefix activations are cached without quantization. Shared instruction-prefix KV reuse accelerates their preparation. Within each four-record update, trainable blocks also share their common prefix computation, preserving its gradient graph; their prefix states are recomputed with current weights for every update. Tests compare both loss and parameter gradients against independent full-sequence passes, including sliding attention. Completion tokens alone incur loss. Every Qwen training token sequence matches the previously verified 720-record export exactly. The runtime source is journaled per invocation. Preliminary preparation/training attempts were stopped while implementing these optimizations; their partial in-memory updates were discarded, no checkpoint was evaluated, and the final six-epoch campaign restarts from the original pretrained weights.

Final real-model spot checks use training indices 120, 240 and 360. One FunctionGemma hidden coordinate differed by 0.00726 between cached and full passes, exceeding the verifier's initial per-coordinate tolerance; mean hidden error was 0.00000509. The recorded `cache-verification-amendment.json` adds selected-checkpoint completion-loss, top-token and logit checks alongside absolute and relative hidden-state bounds. All six sampled completions have identical teacher-forced top tokens and zero float32 completion-loss difference; maximum completion-logit difference is 0.000718. This is a documented numerical verification amendment after observing the discrepancy, not evidence of bitwise equivalence. It changes neither training nor evaluation outputs; full measurements are retained in `verification.json`.

## Why FunctionGemma belongs in this test

Google describes [FunctionGemma](https://ai.google.dev/gemma/docs/functiongemma/model_card) as a Gemma 3 270M derivative specialized for function calling and intended for additional task-specific fine-tuning. Its [fine-tuning guide](https://ai.google.dev/gemma/docs/functiongemma/finetuning-with-functiongemma) specifically discusses nonstandard schemas and domain policies. Those properties make it a credible candidate for this task, without establishing superiority on conditional maintenance requests.

Its parameter count does not establish that it will run faster or use less energy on our FPGA. The cached configuration uses 640-wide hidden states, 256-wide attention heads, a 262,144-token vocabulary and alternating sliding/full attention; Qwen uses a different architecture and vocabulary. Existing FunctionGemma reference/profile work in this repository does not establish current-board deployment qualification. Any model-quality win must be followed by numerical, operator, memory and latency qualification before an energy comparison.

## Result artifacts

Training and adapted-model evaluation completed on October 23, 2026. Qwen selected epoch 5 (tuning token loss 0.0080035); FunctionGemma selected epoch 3 (0.0164127), from six completed epochs each. The machine-readable comparison and human-readable table are in `build/v2/maintenance-sft-v3/comparison.json` and `REPORT.md`, accompanied by raw generated IDs/text, complete prompts, tuning histories, selected checkpoints, source snapshots and a separate seal. Existing revision2 artifacts remain sealed.

| Model | Fresh correct /120 | Fresh conditional /20 | Crossed conditional stress /64 | Fresh valid /120 | Fresh valid but wrong plans |
|---|---:|---:|---:|---:|---:|
| Authored rules | 120 | 20 | 64 | 120 | 0 |
| TF-IDF | 108 | 9 | 28 | 119 | 11 |
| MiniLM encoder | 82 | 5 | 3 | 111 | 29 |
| Fine-tuned Qwen | 111 | 15 | 22 | 119 | 8 |
| Fine-tuned FunctionGemma | 99 | 9 | 27 | 110 | 7 |

Qwen has the strongest learned-model result on the fresh template replication, including 15/20 familiar conditional requests. Its three-request overall lead over TF-IDF is small and is not evidence of a statistically established advantage. FunctionGemma does not improve on Qwen overall in this bounded adaptation recipe. Its five-request advantage over Qwen on crossed conditionals still leaves it below TF-IDF there. The two generators produce respectively 23 and 30 valid but incorrect plans on the 64-request conditional stress set; schema validity alone would let these semantic errors through.

The operator breakdown also matters: on the 16 strict-greater-than stress cases, FunctionGemma gets 8 correct, Qwen 2, and TF-IDF 0. FunctionGemma therefore has a useful local strength despite its weaker overall fresh score. These small, authored subgroups do not establish a general model ranking.

On the matched, predeclared 24-request float32 reference subset, Qwen improves from 0/24 pretrained to 21/24 adapted, and FunctionGemma improves from 0/24 to 18/24. Both pretrained models produce zero valid maintenance plans under this exact no-demonstration interface. This measures adaptation to the declared schema and prompt, rather than proving pretrained models cannot solve maintenance tasks with other prompting or interfaces. The same-backend result isolates adaptation more cleanly than comparing against the older Q8 few-shot run.

The result supports learning the familiar task interface, but does not support reliable recombination of conditions, a need for an LLM over rules, or an FPGA deployment claim. Stress failures are a reason to improve the data and model comparison before spending effort measuring accelerator energy. A future experiment should use independently authored operator requests, broader conditional combinations in training, and a stronger structured/span encoder baseline. Any changes informed by this stress set need a new held-out evaluation. No energy measurements, long-chain reasoning results, or hardware precision qualification follow from this run.

## Reproduction

The local environment is recorded in `environment.json`. Maintenance tests pass 58/58, including full/shared-prefix gradient parity for both decoder families and dynamic-int8 generation with left padding. Existing pilot seals are checked during preparation and final verification. Run in a new output folder; completed training is never silently overwritten.

```powershell
.venv/Scripts/python.exe scripts/v2/maintenance_sft.py prepare
.venv/Scripts/python.exe scripts/v2/maintenance_sft.py prepare-conditional
.venv/Scripts/python.exe scripts/v2/maintenance_sft.py prepare-references
.venv/Scripts/python.exe scripts/v2/maintenance_sft.py controls --threads 2
.venv/Scripts/python.exe scripts/v2/maintenance_sft.py controls-conditional --threads 1
.venv/Scripts/python.exe scripts/v2/maintenance_sft.py train --model qwen --threads 4
.venv/Scripts/python.exe scripts/v2/maintenance_sft.py train --model functiongemma --threads 4
.venv/Scripts/python.exe scripts/v2/diagnose_maintenance_precision.py --model qwen
.venv/Scripts/python.exe scripts/v2/diagnose_maintenance_precision.py --model functiongemma
.venv/Scripts/python.exe scripts/v2/maintenance_sft.py evaluate --model qwen --pretrained --threads 4
.venv/Scripts/python.exe scripts/v2/maintenance_sft.py evaluate --model qwen --threads 4
.venv/Scripts/python.exe scripts/v2/maintenance_sft.py evaluate --model functiongemma --pretrained --threads 4
.venv/Scripts/python.exe scripts/v2/maintenance_sft.py evaluate --model functiongemma --threads 4
.venv/Scripts/python.exe scripts/v2/verify_maintenance_sft.py
.venv/Scripts/python.exe scripts/v2/maintenance_sft.py report
```

Use `--work` consistently with a different directory to run an independent campaign. The trainable Qwen weights must be available at the declared local model path; the FunctionGemma path identifies the existing official snapshot. Commands perform local training and simulated evaluation, never external tool execution or FPGA access.
