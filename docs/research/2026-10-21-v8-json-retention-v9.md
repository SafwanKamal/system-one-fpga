# Expanded CPU JSON-state retention benchmark

This is a separate bounded retention evaluation, version `v8-json-retention-v9`.
Closed-loop reasoning is excluded. The sealed v8 baseline and earlier results
remain unchanged; no board session, board-status update or full-sweep restart is
part of this experiment.

## Frozen design

Six independently seeded fresh sequences: `mixed` and `long-gap` workloads at
16, 32 and 64 steps. There are 224 primary requests and 12 exact-repeat controls
(first and last request of every sequence). All 236 prompts and token IDs are
frozen before model inference. None matches a prior v6/v7 input prompt. This is
an exploratory expansion with two workload sequences per length, not a
statistically powered reliability claim.

Mixed sequences include successful observations, missing and error observations,
no new observation, updates to the other entity, and successful recovery. The
long-gap sequences preserve A's original count with status missing while B
changes; the final step refreshes A successfully. The maximum age of a queried
entity's last observation is 62 steps. The fixture includes 87 ok, 96 missing
and 41 error primary answers, so overall accuracy must be read with the
per-status breakdown. These are generated simulated observations, not live tool
failures or time-based staleness.

The trusted host reducer replaces count/status on successful observations;
missing/error changes status and preserves the previous count. Model responses
are read-only and never update world state. The prompt supplies both entities'
latest state as readable JSON. No arithmetic or model proposal is needed to
advance the state; gold is used only for scoring. Query age is diagnostic
metadata and is not inserted into prompts.

The system prompt, query template and tolerant parser are unchanged from the
v6-r2 retention arm. V7 closed-loop prompt changes are not imported into this
evaluation. There are no examples, prompt selection, missing-field completion,
value repair or parseable-prefix salvage. A rejected answer is an extraction
failure, distinct from a parsed wrong count, entity or status.

Pinned Qwen3-0.6B Q8_0 model, greedy CPU llama.cpp, temperature0/seed0,
repeat penalty1, ngl0, context256 and output reserve48. All primary prompts are
102 input tokens; host reduction prevents growth with sequence position. Raw
outputs run to EOS or output limit. CPU process time includes model loading and
is not an FPGA throughput or energy result.

## Interpretation and controls

There are 179 distinct primary prompt inputs among the 224 requests. Repeated
state snapshots are expected when no relevant value changes; accuracy over
requests and over distinct inputs are reported separately. Exact-repeat controls
are excluded from primary accuracy. Neither the repeated snapshots nor repeated
controls are independent evidence for statistical confidence intervals.

Each JSON request is self-contained. A long observation gap does not require
the model to remember old tokens: the reducer carries the sufficient current
state forward. Consequently a 64-step chain cannot establish a 64-turn model
context capacity or reliable closed-loop reasoning. The defensible experiment
measures extraction correctness and uninterrupted correct-output runs as host
observations continue. A later correct answer after an error is ordinary
read-only extraction recovery, not recovery from model-driven state drift.

Metrics include per-chain first failure, longest correct run, all-correct prefix
survival at 8/16/32/64, correctness by requested chain length, status, event
relation and queried-observation age, distinct-input accuracy, and repeat-text
agreement. Capacity is checked before inference; none of the frozen requests
requires trimming. No full-history or compact arm is run, so this experiment
does not establish a paired encoding advantage.

## Validation and provenance

49 focused tests passed before freezing. Tests independently replay every
observation into every expected snapshot, check missing/error preservation and
long-gap behavior, verify exact repeat inputs and separate unique-input
reporting, and inject wrong model answers to prove they cannot rewrite later
state. The inference interface receives only prompt, token IDs, output budget
and request ID, never expected values or reducer objects.

Raw evidence lives in `build/v2/v8-json-retention-v9`: manifest, frozen jobs,
source/executable hashes, source snapshot, validation, per-request prompts and
stdout/stderr, durable JSONL, summary, failures, status and final seal. The runner
can resume a verified completed prefix without overwriting prior requests; it
refuses to rerun sealed evidence. Sources and frozen jobs are checked before and
after inference. V8's 269 sealed files, v6-r2's 432, v7's 279 and v7-r2's 88
are checked before and after this run.

Reproduction entry points:

```powershell
.venv/Scripts/python.exe scripts/v2/run_v8_json_retention_v9.py --prepare-only
.venv/Scripts/python.exe scripts/v2/run_v8_json_retention_v9.py --run
```

Preparation refuses an existing result directory. A reproduction must use a
separate version/output location; preserve this run's frozen evidence.

## Completed results

All 236 CPU inferences completed: 224 primary requests and 12 repeat controls.
There were no context-capacity stops. Sources and frozen inputs verified
unchanged after inference. The separate report independently replayed all 224
primary observations and checked their expected answers, stored states and scores.

| Requested chain length | Mixed correct | Long-gap correct | Combined |
|---|---:|---:|---:|
| 16 | 15/16 | 16/16 | 31/32 |
| 32 | 29/32 | 31/32 | 60/64 |
| 64 | 58/64 | 61/64 | 119/128 |

Primary accuracy is **210/224 (93.75%)**; distinct-input accuracy is
**167/179 (93.30%)**. The 12 exact-repeat controls matched their original raw
outputs. Across every repeated-input group, including ordinary repeated
snapshots, all 57 groups had identical output text. This consistency supports
reproducibility; it does not turn correlated repeated cases into independent
evidence.

| Target status | Correct |
|---|---:|
| ok | 87/87 |
| missing | 93/96 |
| error | 30/41 |

All 14 failures concern status. Six accepted records returned ok instead of the
supplied missing/error status. Eight other records were syntactically complete
JSON at EOS but used the invalid status `latest`, so the fixed parser rejected
them. These are domain-value failures, not bracket/colon/comma errors or output
truncation. The eight rejected records' raw entity/count fields match the
requested values on inspection, but their status is not repaired or inferred.
All 216 accepted records have the correct entity and count.

| Chain | First failed step | Longest correct run |
|---|---:|---:|
| mixed-16 | 13 | 12 |
| long-gap-16 | none | 16 |
| mixed-32 | 10 | 12 |
| long-gap-32 | 16 | 16 |
| mixed-64 | 21 | 20 |
| long-gap-64 | 31 | 30 |

All six sequences were correct through step8. Only one full sequence was
error-free (long-gap-16); neither 64-step sequence was. The longest correct
prefix/run observed is 30 steps, which is a result for these fixed cases, not
a model-wide sustainable-chain limit. All 57 queries with observation age8+
were correct, but these share the long-gap A/missing workload and cannot
establish a causal age effect. Prefix and window metrics should not be read as
proof of monotonic degradation; inputs, statuses and workload composition vary.

The supported result is stable 102-token input size through 64 host-maintained
steps, with high but imperfect extraction accuracy and a clear non-ok-status
weakness. It does not establish reliable 64-step execution, a larger model
context window, or performance/energy advantages. Closed-loop remains separate.
Any future status-prompt change should be developed on new development cases
and assessed on fresh evaluation data; this completed set is not a tuning set.

Raw evidence is sealed with 725 files. The separate
`build/v2/v8-json-retention-v9-report` contains `analysis.json`, `requests.csv`,
`README.md`, reporting source and its own seal. Final hashes verified; all prior
v8/v6/v7 artifacts remain unchanged. No board access or board-status update
occurred, and the full sweep remains stopped.
