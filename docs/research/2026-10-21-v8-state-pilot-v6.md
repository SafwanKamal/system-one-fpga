# CPU pilot v6-r2: history, JSON state and compact state

This is an isolated CPU-only evaluation workstream. It performs no SSH, board
inference, programming, deployment/service changes or board-status writes. The
sealed v8 baseline and previous benchmark evidence remain preserved. The full
sweep remains stopped. Final results are under `build/v2/v8-state-pilot-v6-r2`.

## Fixed experimental question

Compare H=full raw history, J=readable JSON current state and C=named compact
current state. J and C use the same deterministic task-state reducer, so their
comparison separates encoding from the main effect of bounding state. H retains
all raw user/assistant messages and required tool observations/acceptance feedback,
without trimming or summarization. J/C receive self-contained current-state
snapshots and no references to absent prior replies.

There is one fixed prompt per experiment mode, shared by all arms, with no numeric
examples, prompt selection, model-specific status codes, fine-tuning or semantic
output correction. This is a one-model pilot, not proof of scalable compaction.

## Cases and distinct state semantics

Four fresh eight-step sequences: one retention and one closed-loop sequence in
each of development and heldout splits. Seeded independently at 20261021601 and
20261021602, with shared sequence templates. Arm order rotates across cases.
Triple-digit initial counts distinguish these cases from previous v2-v5 tasks;
tests also check exact state/request signatures for overlap. The task remains a
synthetic deterministic tool-state workload, not a real application deployment.

Retention consists of actual simulated tool observations, followed by latest-state
queries. Observations refresh one entity, preserve the last count on missing/error,
and test delayed references after intervening updates to the other entity. Model
answers are read-only: a wrong answer never changes tool/world state. H sees the
raw event stream; J/C see the reducer's state after the actual observation.
This is ordinary ingestion of input facts, not correction using expected answers.
The reducer preserves task-sufficient latest state; it is not lossless compression
of all historical observations. Queries for old revisions are outside this pilot.

Closed loop uses add, conditional, copy, missing and set operations, covering both
conditional branches. An accepted model proposal updates the observed state
verbatim, including errors; rejection leaves it unchanged. Gold state is maintained
separately only for scoring and snapshot controls. Expected values are never
passed to the CPU inference interface. Local correctness measures consistency
with the actual committed state; global correctness compares the ideal trajectory.
Locally correct but globally wrong outputs identify inherited-only errors.

## Aligned controls

Each sequence has 16 snapshot controls: eight J and eight C, for 64 controls total.
Retention control state comes from the actual tool-observation stream; closed-loop
controls use the ideal state before each request. Neither control's model output
is used to repair a measured trajectory. J/C controls and dependent requests use
exactly the same prompt construction and omit prior-reply acknowledgement.
When the measured state matches its control state, input token IDs must match.
Retention J/C prompts should therefore match their controls throughout; these
repeated executions are reproducibility checks, not independent accuracy samples.

H refers to J's snapshot as a base-competence diagnostic, not an identical-history
control. H closed-loop feedback still records whether the previous proposal was
accepted; H retention replies never update world state. This removes the v5
state-arm acknowledgement mismatch without treating H versus snapshot as a
causal ablation of history length alone.

The maximum is 160 NN calls: 64 controls plus 96 dependent requests. Full-history
capacity stops can reduce that count. Development runs before heldout, and final
prompts/parser/source/manifest are frozen before either split's final execution.

## Generic parsing correction discovered in development

The original v5 parser was initially reused. Development produced unambiguous
records such as `[{"name":"A","count":127,"status":"ok"}]`, rejected because
the parser did not support the singleton object container or `name` field alias.
This is an extraction-coverage gap, not proof of a wrong count.

That preliminary run was stopped with 51 durable development records and zero
heldout responses. Its prompts, stdout/stderr, source snapshot, disposition and
167-file seal are preserved at `build/v2/v8-state-pilot-v6`. The final run is a
separate revision and output folder; no preliminary evidence was overwritten.

Before heldout inference, r2 declared singleton-object-list unwrapping and the
name-to-entity field alias as structural normalization. Existing v5 rules for
closed arrays/objects, field aliases, case/integer strings, complete JSON fences
and actual-EOS text records remain. Conflicting fields, duplicate JSON keys,
multiple records, booleans/floats, embedded prose and unevaluated expressions are
rejected. No field/value defaults, expected-value search or arithmetic evaluation.
Prompts and case values were not changed in response to model answers.

Preferred-array conformance is the legacy strict-array metric; the new prompt
permits objects. Acceptance and exact semantic correctness are separate counts.
Unparseable output is an end-to-end failure, but not demonstrated semantic
incorrectness of its contents. Reports distinguish first extraction failure,
first parsed wrong answer, new local errors and inherited errors. Legacy summary
key `first_semantic_failure` includes extraction failures; use the report's
`first_end_to_end_failure` and `first_parsed_semantic_error` for clarity.

## Budget, reproducibility and limits

Pinned Qwen3-0.6B Q8_0 SHA256
`9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`.
Existing llama.cpp CPU executable, greedy temperature0/seed0, repeat penalty1,
GPU layers0, explicit nonthinking Qwen chat template, context256 and fixed
48-token output reservation. All responses run to actual EOS or budget; no
acceptance of an early JSON prefix while contradictory text could still follow.
All J/C oracle prompts fit (J102–123, C92–114 tokens in preflight).

Only 208 input tokens are available under this reservation. Capacity stops issue
no NN request and are reported separately from model failures. Correct-prefix
survival remains false after a known earlier failure; it is censored when history
hits capacity before an observed error. Common-prefix comparisons supplement
whole-trajectory results because H and state arms can run different step counts.

CPU timing includes per-request process/model loading. It is not an FPGA latency,
throughput, energy or host-reducer overhead measurement. There is only one sequence
per mode/split, shared templates and one model; no statistical reliability,
application-generalization or cross-model scaling claim. Raw v5/v6 scores are not
paired comparisons: tasks, prompts and control policy differ.

Frozen sources, executable and manifest are hashed before and after inference.
Static control prompts are saved before responses exist. Reports verify control
alignment, repeated identical inputs, all sealed v8 artifacts, previous v2-v5
evidence and the preserved parser-development run, then seal final results.

## Results

`pilot-summary.json` is authoritative; `cpu/requests.jsonl` retains every request,
state transition, raw output and score. `control-alignment.json`,
`common-prefix-comparisons.json`, `repeat-checks.json`, `semantic-failures.json`
and `requests.csv` provide separate views. Interpretation must retain the
distinction between acceptance, semantic correctness and capacity.

Final r2 completed 136 CPU inferences (72 dependent requests and 64 snapshot
controls), plus four capacity stops. Frozen source integrity passed before and
after execution. All 82 focused tests passed.

| Split / experiment | Full history correct | JSON state correct | Compact state correct |
|---|---:|---:|---:|
| Development retention | 2/2, capacity before 3 | 7/8 | 4/8 |
| Heldout retention | 2/2, capacity before 3 | 7/8 | 3/8 |
| Development closed-loop | 2/2, capacity before 3 | 2/8 | 1/8 |
| Heldout closed-loop | 1/2, capacity before 3 | 2/8 | 0/8 |

Full history is capacity-censored; its two observed answers cannot establish
eight-step reliability. Both state arms completed all eight steps. In retention,
JSON accepted 16/16 replies and answered 14/16 correctly across both splits;
compact accepted 11/16 and answered 7/16 correctly. The compact failures comprise
five unparseable replies and four parsed wrong answers. Heldout examples include
missing entity fields and incorrect statuses despite a correct count. JSON's
heldout error also selected the wrong status. These are distinct extraction and
retrieval failures, not evidence that punctuation alone causes the difference.

Retention JSON inputs were 102 tokens versus compact's mean 92.625, a saving of
about nine tokens (9.2%). This saved space did not enable additional observed
steps over JSON. Closed-loop outcomes remained weak, with no full-state recovery:
JSON scored 4/16 globally correct and compact 1/16. One JSON answer was locally
correct for its already-drifted state but globally wrong. State reduction does
not resolve arithmetic or error propagation.

All 64 frozen control prompts verified. There were 38 exact control-input
matches, including all 32 retention state-arm requests, and 40 repeated identical
prompt checks with zero raw-text mismatches. Earlier v8/v2/v3/v4/v5 seals and the
167-file parser-development seal verified unchanged. Final results are separately
sealed under `build/v2/v8-state-pilot-v6-r2`.

The next evaluation baseline should use readable JSON state, retaining compact
state as an ablation. The supported paper observation is that task-sufficient
state bounds context growth in this workload; neither universal compression nor
reliable long dependent execution is established by this small pilot. Additional
fresh sequences are needed before a statistical or cross-model claim. There was
no board access, no board-status update and no full-sweep restart. The sealed v8
baseline was unchanged; live board identity remains governed by BOARD_STATUS.json.
