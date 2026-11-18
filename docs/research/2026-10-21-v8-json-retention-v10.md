# Status-copy development and fresh JSON retention evaluation

This benchmark changes only retention prompting. Closed-loop reasoning remains
separate. Model, CPU settings, parser, scorer and observation reducer are
unchanged. No board access, BOARD_STATUS.json update, deployment change or
full-sweep restart is part of this work. Earlier sealed evidence is preserved.

## Development protocol

The v9 evaluation showed six substitutions of ok for a stored non-ok status and
eight complete JSON replies with the invalid status latest. Those completed
evaluation inputs are not used for tuning. Development instead generates 36
fresh state/query cases with seed202610211001, crossing all nine A/B status
pairs, both target entities and two independent sets of counts. Each requested
status occurs twelve times. All task identities (state plus queried entity)
are checked against earlier inference records, independently of prompt wording.

The first development run pairs the unchanged original prompt with a generic
instruction to copy the stored status/count, and explicitly distinguishes the
stored observation's status from successful production of an answer. No examples,
model-specific status mappings, grammar constraints, gold prefill or repairs
are introduced. Status latest is still invalid; no missing field is supplied
by the evaluator.

Before inference, the development gate requires 36/36 correct full records for
the candidate. Fresh evaluation cannot start unless a sealed development summary
passes the gate. All prompts, token IDs, cases, sources and executable hashes are
frozen before each phase. Development may guide generic prompt revisions, but
evaluation responses must not inform further changes in the same evaluation.

## First development finding

The initial candidate's user query asked for status and count while the system
requested status, entity and count. The model emitted status/count objects but
omitted the entity field. The gate detects this extraction failure. The parser
is deliberately not changed to infer the absent entity from the query. A prompt
revision must request all three fields consistently in the user query too.
The initial development run is preserved separately; no evaluation was started
from its failed gate.

The first prompt scored0/36 complete records (all omitted entity); the unchanged
original baseline scored29/36. Its 72-call paired run is sealed under
`build/v2/v8-json-retention-v10/development`. A second revision explicitly
requested the entity in the user query and scored35/36, with one remaining
missing-to-ok substitution. Its 36-call development run is separately sealed
under `v8-json-retention-v10-r2/development`; evaluation remained stopped.

The final development candidate states the generic domain rule that missing
and error must not be replaced with ok, and names the requested JSON field
paths in the query. The same 36 development cases are reused for these prompt
revisions, which is development tuning, not fresh qualification. Original
baseline outputs are reused only for analysis, not counted as new inferences.
The strict36/36 gate is unchanged. No evaluation response has informed a revision.

The final r3 candidate passed36/36, including12/12 each for ok, missing and
error, versus the original baseline's12/12,10/12,7/12 respectively. The revised
record selector explicitly references State.<entity>.status and
State.<entity>.count; it includes the queried entity name. These are paths to
the supplied data, not answer prefill. No field value is computed by the host
for the model. Development's original-versus-selected comparison is adaptive
prompt development, not an unbiased statistical test of improvement.

The final revision's development and evaluation sources were frozen unchanged
under `build/v2/v8-json-retention-v10-r3/{development,evaluation}`. The first
two attempts remain separately sealed. The focused test suite passed54 tests
before the final freeze.

## Fresh evaluation design

The selected prompt is evaluated on six fresh sequences at lengths16,32,64 with
mixed and long-gap workloads:224 primary requests plus12 exact-repeat checks.
Counts are resampled with independently fixed seeds202610211100–105 and entity
orientation is varied. The 32-step long-gap sequence preserves an error status
rather than missing, broadening non-ok coverage. State/query identities must
not overlap previous experiments or development. Evaluation is not a paired
comparison with v9; the original-versus-candidate development comparison is paired.

The trusted host reducer alone updates state from simulated observations.
Missing/error observations preserve count, successful observations replace it;
model replies remain read-only. Current JSON state is supplied each request.
Long chains therefore test repeated extraction from bounded host state, not
the model's context window or model-driven error propagation.

Pinned Qwen3-0.6B Q8_0, greedy CPU llama.cpp, ngl0, context256 and output reserve48
are retained. Timing includes model loading and is not an FPGA performance result.
Unparseable replies, wrong semantic fields, first error, longest correct run,
distinct-input accuracy, per-status accuracy and exact-repeat agreement remain
separate metrics. A parsed success is not treated as semantic success.

## Evidence and validation

53 focused tests passed before the first development freeze. They check paired
status/entity coverage, unchanged rejection of invalid status latest, absence of
gold objects from inference calls, fresh evaluation identities, independent replay
of all generated observation states, and repeat inputs. Earlier v8/v6/v7/v9
seals are checked before and after each phase. Source snapshots, prompt files,
raw stdout/stderr, durable JSONL and separate phase seals preserve provenance.

## Completed fresh evaluation

The selected r3 prompt scored **224/224 correct primary records**, with
224/224 parsed and no missing-field, invalid-status or semantic failures.
All six chains completed without an error:

| Chain length | Mixed workload | Long-gap workload |
|---|---:|---:|
| 16 | 16/16 | 16/16 |
| 32 | 32/32 | 32/32 |
| 64 | 64/64 | 64/64 |

Per-status correctness was ok87/87, missing75/75 and error62/62. The selected
prompt therefore preserved both non-ok statuses in this fresh evaluation.
Distinct-input accuracy was179/179; all12 explicit repeats matched. Across all
57 groups of repeated inputs, raw output text was identical. Queries at
observation age8+ scored57/57, including gaps up to62 steps; these remain
correlated host-state queries rather than independent long-memory trials.

Input size stayed129 tokens through64 steps, versus102 in the v9 prompt. The
27-token instruction overhead fits the unchanged256 context and48 output
reservation. Neither parser acceptance nor count/status values were repaired.
The reporting audit independently replayed every observation and checked all
224 primary expected answers and stored states. It also verified identical
source hashes between selected development and evaluation, and exact state/
query pairing with the original development baseline.

There were144 development inferences across the original paired run and two
revisions, then236 evaluation inferences including repeats:380 total, kept in
separate phases. The first development seal covers235 files, r2 development127,
r3 development127 and r3 evaluation728. The separate report at
`build/v2/v8-json-retention-v10-report` contains analysis.json, requests.csv,
README.md and reporting source, with its own seal. All earlier v8/v6/v7/v9
seals verified unchanged. No board access, board-status write, closed-loop
experiment or full-sweep restart occurred.

These results support the selected prompt as the CPU JSON-state retention
baseline for this two-entity workload. They do not establish universal status
reliability, FPGA equivalence, cross-model generalization, arbitrary conversation
retention or closed-loop reasoning. V9 scored210/224 on different evaluation
cases; that numerical difference is not a paired causal estimate. The matched
development comparison29/36 to36/36 is development-selected evidence, followed
by this independent fresh evaluation. Preserve the completed evaluation as
evidence rather than using its outputs for further prompt tuning.

## Later input-parity correction (v11 qualification)

Actual CLI token logging in the v11 qualification found that llama.cpp removes
one trailing LF from prompt files. V10 recorded nominal token IDs from the
frozen string, not independently logged actual CLI IDs. Its quality scores
remain observed results for the CLI's actual prefix, but do not prove exact
CPU/FPGA input parity. V11 preserves this evidence, compensates file framing
without changing the logical prompt, and reruns paired CPU/FPGA qualification
with actual input IDs checked on both backends. See
`2026-10-21-v8-json-retention-v11-fpga.md` for the diagnostic evidence and limits.
