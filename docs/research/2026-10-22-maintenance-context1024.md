# Maintenance development revision: 1024-token context

Date: 2026-10-22. Separate software development campaign at `build/v2/maintenance-pilot-v2-context1024`. The [v1 implementation/results](2026-10-21-maintenance-pilot.md) and its164-file seal are preserved. This revision does not access/program the board or measure energy.

## Context evidence and budget

The saved v9d model manifest declares `max_context=1024`; saved hardware qualification includes attention/decode checks at position1023 and616 causal cases. The saved canonical board status inspected at revision24 says v8 was restored after v9d testing. This study uses1024 as the candidate's total input-plus-output budget; it does not claim that v9d is currently loaded or qualified for maintenance tasks.

Evidence files and their hashes are recorded in the new manifest:

- `build/v2/qwen-fpga-decoder-v9d/deployment/model-manifest.json`
- `build/v2/qwen-fpga-decoder-v9d/board-evidence-1/validation-summary.json`

Every request reserves256 generated tokens before inference. No context sliding, input truncation, hidden tool filtering, grammar constraint or prefix reuse is permitted. The CPU server itself uses a1024-token context, unlike v1's larger software-reference allocation.

| Prompt mode | Fresh audit input tokens | Maximum input + output reservation | Eligible audit cases |
|---|---:|---:|---:|
| Full contract, zero-shot |377–409|665|120/120|
| Full contract, four training examples |576–608|864|120/120|

All720 training/120 tuning/120 audit records fit both modes. The encoder's maximum audit input remains123 tokens. Fitting is a capacity result, not a correctness or FPGA timing result. The original explicit-contract capacity blocker is removed for this candidate; its v1 measurements remain correct for the earlier256-token budget.

The v1 CPU reference already accommodated the full prompt. Increasing candidate FPGA capacity does not itself improve CPU model reasoning or explain a quality-score change. This revision uses newly available deployment capacity for training-only demonstrations and evaluates that prompt adaptation separately.

## Revised software comparison

Schema, simulator, exact canonical scoring, strict parsing and counterfactual branch tests are unchanged. New records use new seeded values and asset IDs:21–24 for training,31–34 for tuning,41–44 for audit within pump/motor/fan categories. They remain programmatic authored templates, not independent human-reviewed data or a publication test. No claim of strong structural disjointness or rare-error reliability follows from different IDs/seeds.

The public catalog is ordered by explicit current-request mentions, then prior-request mentions, then remaining catalog entries. All candidates remain present. This deterministic, gold-independent binding aid is exposed to every model; learned heads must still predict the asset index and every semantic field. It is not evidence of a general learned pointer mechanism. Negation/multiple-mention cases outside these templates need further evaluation.

Baselines:

1. Unchanged scoped rules.
2. TF-IDF structured heads retrained on the fresh720 records.
3. MiniLM structured heads and final two Transformer blocks trained for a predeclared six epochs, one seed, with epoch chosen on tuning exact correctness only. This changes both preprocessing and training effort from v1; a score difference is not an isolated causal effect.
4. The same pinned Qwen3-0.6B Q8_0 weights, without weight fine-tuning. Two prompt modes are compared on24 unique, balanced tuning inputs. Four demonstrations are deterministically selected from training only and illustrate output shape and conditional/terminal variants. Demonstration requests omit repeated catalogs, while every actual query includes its complete public catalog. Choose greatest tuning exact correctness, then valid records, with zero-shot winning an exact tie. Seal selection before evaluating the120 audit records once.

Qwen's examples are prompt adaptation, not task weight training. Encoder/TF-IDF train on720 examples; Qwen sees four demonstration outputs and uses pretraining. These differences must accompany any comparison. Local CPU jobs can overlap; timing observations are not matched edge-speed evidence. All useful/invalid/accepted-error counts remain explicit.

## Validation and artifacts

Tests: `tests/test_maintenance_pilot.py` plus `tests/test_maintenance_revision2.py`,48 passing before preparation. They retain v1 simulator/schema checks and add public-input-only candidate ordering, fresh data/target round trips, training-only examples and query/gold separation.

Implementation: `src/sysone/v2/maintenance/revision2.py`; runner: `scripts/v2/maintenance_revision2.py`.

```powershell
.venv/Scripts/python.exe -m pytest tests/test_maintenance_pilot.py tests/test_maintenance_revision2.py -q
.venv/Scripts/python.exe scripts/v2/maintenance_revision2.py prepare
.venv/Scripts/python.exe scripts/v2/maintenance_revision2.py classical
.venv/Scripts/python.exe scripts/v2/maintenance_revision2.py encoder --threads 4
.venv/Scripts/python.exe scripts/v2/maintenance_revision2.py qwen --threads 4
.venv/Scripts/python.exe scripts/v2/export_maintenance_sft.py
.venv/Scripts/python.exe scripts/v2/verify_maintenance_revision2.py --work build/v2/maintenance-pilot-v2-context1024
.venv/Scripts/python.exe scripts/v2/maintenance_revision2.py report
```

Use a new `--out` for an independent run; no silent overwrites. Frozen jobs include the exact prompt text and input IDs for both modes before selection. Source snapshots, dataset hashes, training history/checkpoint, raw Qwen tuning/audit responses, actual tokenizer-ID checks, selection record, per-case predictions and final independent rescoring are retained. The local Qwen server is closed after the finite campaign; the old pilot seal is checked again at completion.

## Results

Completed results: [REPORT.md](../../build/v2/maintenance-pilot-v2-context1024/REPORT.md), [comparison.json](../../build/v2/maintenance-pilot-v2-context1024/comparison.json), [verification.json](../../build/v2/maintenance-pilot-v2-context1024/verification.json), [token audit](../../build/v2/maintenance-pilot-v2-context1024/token-audit-summary.json).

| Baseline | Exact correct /120 | Schema-valid /120 | Correct actionable / accepted plans | Wrong accepted plans | Distinct inputs correct /101 |
|---|---:|---:|---:|---:|---:|
| Scoped rules |120|120|80/80|0|101|
| TF-IDF structured |109|119|69/79|10|90|
| MiniLM structured, selected epoch5 |83|113|48/77|29|68|
| Qwen3-0.6B, four examples, unchanged weights |8|66|8/66|58|8|

There are80 actionable requests and40 clarification/unsupported requests. The audit contains101 distinct public inputs; repeated cases are not independent reliability observations. These authored-template scores do not establish general operator-language performance. Different adaptation budgets and new preprocessing prevent a model-family winner or a causal v1-to-v2 improvement claim.

MiniLM tuning exact scores across six predeclared epochs were20,56,68,81,86,78 out of120. Epoch5 was selected before the audit. Audit conditional accuracy is1/20, versus14/20 direct,15/20 composition,18/20 correction,15/20 clarification and20/20 unsupported. Binding is no longer the only obstacle; correct conditional structure/arguments need further development and fresh evaluation.

Qwen prompt selection used only24 balanced tuning requests: zero-shot0/24 correct and0/24 valid; four examples2/24 correct and16/24 valid. The examples mode was sealed before audit. On audit it succeeds on5 direct and3 correction cases, with0/20 in each other stratum. It emits66 schema-valid plans but58 are wrong; it earns no correct clarification/rejection outcomes. This is a direct demonstration that structural typing does not guarantee semantic reliability. Few-shot prompting is not supervised weight adaptation, and this result does not establish the limit of a task-trained generator.

### Completed verification and training export

The verifier recomputed all528 recorded verdicts from raw responses:480 audit decisions across four baselines plus48 Qwen tuning decisions. It checked168 actual Qwen input-ID sequences and1024-token budgets, reproduced the prompt-selection rule, verified training-only demonstration lineage, and rechecked all164 sealed parent-pilot files. The local inference server exited after completion. New results and source snapshots have a separate final seal. No FPGA access, programming, power readings or controlled edge-speed comparisons occurred.

The supervised-training export at `build/v2/maintenance-pilot-v2-context1024/sft-export/` contains720 training and120 tuning records, with explicit input IDs and completion-only labels. All prompt positions are masked with-100; the response EOS is151645. Maximum total lengths are475 training and479 tuning tokens, below1024. The verifier checked all840 masks and boundaries. Audit cases are not exported. `model_trained=false` is explicit: no Qwen weight fine-tuning has happened in this campaign. Export code and provenance are retained.

### Admission decision

The context-capacity blocker is resolved for the1024-token candidate. **The software-quality gate is not passed by either neural baseline.** More attention capacity alone has not produced the desired low-error deployment. Do not describe schema validity, zero accepted output or template-level rule success as industrial reliability.

The next meaningful experiment is supervised schema/task adaptation on training data, stronger conditional/argument binding for the encoder, and independently authored operator requests with reviewed labels. Keep the current audit frozen. A later model should be selected on development and tested on new cases before maintenance FPGA qualification or energy-efficiency claims. Rules and cheap ML remain mandatory controls; this pilot still supplies no task-driven reason to prefer the LLM. Energy remains unmeasured.
