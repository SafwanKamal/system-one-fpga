# Maintenance first milestone: software implementation and development pilot

Date: 2026-10-21. This implements the first software milestone of [MaintenanceBench-Edge](maintenance-benchmark-v1/README.md). No board session, programming, deployment change, or energy measurement is part of this work. Previous sealed experiments are not inputs to the new task or targets for prompt tuning.

## Implemented scope

Source package: `src/sysone/v2/maintenance/`.

- `schema.py`: strict descriptive AST, exactly one of plan/clarify/reject, eight tools, three nodes, one asset, one predicate, backward evidence references, explicit terminal reasons, fixed-point units and a reversible JSON-array wire codec. Unknown fields, duplicate JSON keys, bool-as-int arguments, forward references, noncanonical terminals, trailing output and fenced/embedded answer salvage are rejected.
- `simulator.py`: deterministic read-only plant and simulated report/inspection records. Observations carry status, epoch and sample identity. Explicit threshold comparisons account for fixed-point scale; missing/error reads stop execution and never become successful evidence. Counterfactual worlds test below/equal/above threshold and read error. Caller-owned worlds are not mutated.
- `dataset.py`: programmatic authored-template development corpus with six strata, separate public inputs and scorer-only gold, split-specific wording and disjoint asset-ID strings. It creates no official test set or human annotations. Semantic scoring checks both exact canonical plans and simulator traces/effects in counterfactual worlds.
- `baselines.py`: task-vocabulary rules and factorized structured outputs shared by TF-IDF and MiniLM. Encoder targets predict outcome/reason, catalog-index asset pointer, step tools/arguments, guard flags, predicate and evidence. Every generated gold target round-trips through both representations.

Runner: `scripts/v2/maintenance_pilot.py`. Each prepared run snapshots source and hashes input files; each baseline writes raw predictions and a separate summary. Existing output directories cannot be silently overwritten. The Qwen runner starts a local loopback-only CPU server, verifies tokenizer IDs against the pinned deployment tokenizer, and sends token IDs directly. It closes the child server afterward. This avoids relying on the historical CLI prompt-file trailing-newline behavior.

## Corpus and token audit

The pilot has720 training records,120 tuning records and120 development-audit records, balanced over direct, composition, conditional, correction, clarification and unsupported requests. These contain423/98/99 distinct public inputs respectively. Repeated template-derived requests are retained and counted openly; they are not independent reliability trials. Exact public-input overlap across the three splits is zero. Related templates and semantic primitives remain shared, so this is not a strong compositional-generalization benchmark.

The generator receives the full public tool/format instruction plus user request, catalog and prior-request context. Supervised structured encoders receive public request/catalog/context, with their output schema fixed by trained heads. These are different adaptation/representation costs and must be shown rather than equated.

| Split | Qwen input tokens | Maximum gold wire tokens | Maximum MiniLM input tokens |
|---|---:|---:|---:|
| Train |329–358|64|122|
| Tuning |329–362|64|123|
| Development audit |338–370|67|123|

**No Qwen request fits the deployed256-token context**, even with exact gold-output length instead of the proposed96-token reservation. All fit the declared software capability ceiling. All MiniLM inputs fit128 tokens, which is an input-feasibility observation only; it does not qualify a new trained model/head for FPGA execution.

Do not drop the tool description, hide a schema-selection oracle, reduce task scope silently or claim the software result is deployed. Options for a later separately developed variant are task adaptation that learns the fixed schema, a more concise reversible codec/instruction, a disclosed catalog-routing mechanism, or a separately qualified larger-context implementation. Any such change requires its own development qualification and fresh evaluation.

## Baseline comparison design

The finite comparison runs:

1. Hand-authored deterministic rules covering the pilot vocabulary, frozen before opening audit outputs.
2. Character2–5-gram TF-IDF with per-field logistic-regression heads, trained on the720 records; constant fields remain explicit constants.
3. Local MiniLM-L12-H384 structured heads, with final two Transformer blocks fine-tuned for three epochs, one seed. Select the epoch on tuning exact task correctness only, then evaluate audit once. Other Transformer blocks stay frozen. Batch16 timing is not a matched single-request speed benchmark.
4. Local Qwen3-0.6B Q8_0, no task fine-tuning or few-shot examples, frozen nonthinking prompt, greedy generation, one attempt, full vocabulary, output cap256, no grammar or parser repair. The2048-token server allocation accommodates the reference experiment; benchmark admission remains <=1024 input and256 output. It does not extend FPGA context.

These compare initial software approaches, not equally trained model families. BERT/ModernBERT, adapted Qwen, FunctionGemma and three-seed comparisons from the full plan remain later work. CPU activities can overlap during this capability-only pilot; collected wall times must not be interpreted as controlled speed comparisons. No power values are estimated from CPU load.

Per baseline report full audit correctness, valid output count, correct accepted/accepted, per-stratum errors, and distinct-public-input outcomes. Invalid output, wrong plan, wrong terminal reason and inability to decode structured heads remain failures. A correctly rejected unsupported task contributes to terminal-decision accuracy but not completed actionable work.

## Verification and execution

Focused tests: `tests/test_maintenance_pilot.py`. The initial45 tests passed. They cover branch boundary differences, fixed-point thresholds, status failures, immutable evidence/world state, schema rejection, strict output parsing, lucky-world scoring, codec/target round trips, deterministic dataset preparation and separation of public inputs from gold/IDs.

Run from the repository root with the local virtual environment, changing `--out` for a new independent version:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_maintenance_pilot.py -q
.venv/Scripts/python.exe scripts/v2/maintenance_pilot.py prepare --out build/v2/maintenance-pilot-v1
.venv/Scripts/python.exe scripts/v2/maintenance_pilot.py classical --out build/v2/maintenance-pilot-v1
.venv/Scripts/python.exe scripts/v2/maintenance_pilot.py encoder --out build/v2/maintenance-pilot-v1 --epochs 3 --threads 4
.venv/Scripts/python.exe scripts/v2/maintenance_pilot.py qwen --out build/v2/maintenance-pilot-v1 --threads 4
.venv/Scripts/python.exe scripts/v2/maintenance_pilot.py report --out build/v2/maintenance-pilot-v1
```

Preparation is local and offline, using existing model/tokenizer files. It does not download weights. Raw Qwen responses, actual prompt IDs, per-case generated counts/stop reasons, trained encoder checkpoint, tuning history, source snapshots and audit manifests stay under the new run folder.

## Results and interpretation

Completed comparison: [REPORT.md](../../build/v2/maintenance-pilot-v1/REPORT.md), [machine-readable comparison](../../build/v2/maintenance-pilot-v1/comparison.json), [independent rescore](../../build/v2/maintenance-pilot-v1/independent-analysis.json), [token audit](../../build/v2/maintenance-pilot-v1/token-audit-summary.json).

| Baseline | Exact correct /120 | Schema-valid /120 | Correct actionable / accepted actionable | Distinct inputs correct /99 |
|---|---:|---:|---:|---:|
| Scoped rules |120|120|80/80|99|
| TF-IDF structured |93|116|53/76|72|
| MiniLM structured, epoch3 |32|102|0/62|18|
| Qwen, task-unadapted |0|0|0/0|0|

The comparison contains80 actionable tasks and40 clarification/unsupported decisions. Zero accepted Qwen proposals is zero useful coverage, not a low-error deployment result. MiniLM's32 correct decisions are all terminal outcomes; it does not complete an actionable plan correctly. Its tuning correctness was7,30,35 over three epochs, selecting epoch3 without inspecting audit for selection. All ten repeated-input groups produced identical raw outputs within each backend; duplicates still do not establish independent reliability.

Independent analysis reconstructed all480 recorded verdicts from raw outputs and gold plans, including counterfactual simulator runs. All baseline file seals and source/input hashes matched after execution. The local Qwen server exited after the finite run. Its actual prompt token IDs matched the pinned host tokenizer on all120 requests and were submitted directly; no CLI newline assumptions were used.

### What failed

- The rules baseline solves this authored vocabulary. This is evidence that the current pilot task distribution does not justify neural inference; it is not evidence of general rule coverage on operator language.
- TF-IDF has4 invalid structured decodes and23 wrong accepted plans. Active-target mismatches include13 asset pointers and10 predicate operators. Report overall correctness and accepted errors together.
- MiniLM has18 invalid decodes,8 wrong terminal outcomes and62 wrong plans. Its asset pointer is wrong on76 of80 actionable cases. This shared-pooling categorical head design and small, one-seed adaptation are inadequate; a token/candidate pointer head and stronger training require a separate development revision. These scores cannot support an encoder-versus-LLM family conclusion.
- Qwen has120 invalid wire records. Sixty-five outputs start with Markdown fences;47 are independently well-formed JSON values but do not satisfy the wire schema. No fence stripping, alternate-format salvage, few-shot revision or audit-dependent prompt adaptation was applied. Output compliance, task adaptation and task semantics remain separate questions; this run does not show that a trained Qwen cannot perform maintenance tasks.

### What the context audit implies

Full audit inputs require338–370 tokens. Public input plus empty-system framing alone requires74–106. A hypothetical short trained-schema instruction yields87–119 input tokens and all120 would fit256 with a96-token output reservation. This is **token-count feasibility only**: no model was trained on, or evaluated with, that hypothetical prompt. It does not authorize omitting the schema from an untrained model and claiming equivalent information or capability.

The full explicit contract is not deployable on the current context. A fixed-schema adapted model might amortize that contract into its weights; that is a concrete software hypothesis to test before any FPGA change. The maximum gold wire length of67 audit tokens shows the record itself is not the dominant context cost in this pilot.

### Next admission gate

Keep FPGA work deferred. First collect a separately versioned independently authored operator-language development set and review the labels/domain vocabulary. Do not manufacture difficult phrasing solely to defeat the rules baseline. Improve the structured encoder's entity/evidence binding, and adapt the generator to the same fixed schema using training data. Freeze selection on development, then use fresh audit cases. A short-instruction generator must demonstrate semantic performance, not only token savings. Preserve this pilot's prompts, scores and failures rather than overwriting them.

The120-workflow full study, human-reviewed1,800-request test, confidence calibration, multiple seeds, adapted Qwen/stronger encoder comparisons, and energy campaign remain outside this first pilot. Template-level success cannot establish industrial reliability, rare-error assurance, arbitrary planning capability, edge latency or energy efficiency. The implemented pipeline now makes those later experiments concrete and exposes the reasons to defer deployment.
