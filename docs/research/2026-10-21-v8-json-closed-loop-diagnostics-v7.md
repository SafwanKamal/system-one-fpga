# JSON closed-loop diagnosis and development fixes

The sealed v6-r2 pilot is preserved. V7 is a separate, CPU-only development
experiment at `build/v2/v8-json-diagnostics-v7`. It does not change the v8
deployment, access the board, update BOARD_STATUS.json, or restart the full sweep.

## What failed in v6-r2

The audit replays each closed-loop request against an independently written
explicit operation oracle, checks the global ideal trajectory from initial
state, and checks the committed state against the raw parsed proposal. No
oracle or reducer mismatch was found. This validates these checks, rather than
proving the entire harness cannot contain a bug.

Across both development and heldout sequences, the JSON arm had 16 requests:

| Outcome | Requests |
|---|---:|
| Globally correct | 4 |
| Parsed, wrong even for supplied state | 8 |
| Correct for supplied state, inherited wrong count | 1 |
| Unparseable at the output budget | 3 |

Of the eight new local errors, four were copies that echoed the target's old
count, one was an ignored addition, two were conditionals that kept the old
count, and one conditional used the opposite branch. These output patterns
support an operation-following / source-selection / branch-selection diagnosis;
they do not isolate an internal arithmetic failure. Three unparseable outputs
started emitting multiple records and reached the 48-token output budget. A
correct-looking prefix is not a complete accepted response and is not salvaged.

State drift was present before 13/16 JSON requests, but changed the target
answer on only 7/16. Four parsed local errors also encountered an already-wrong
target input. Thus drift and new errors overlap: assigning every later wrong
answer to drift would conceal persistent local failures. Only one wrong answer
was solely inherited under the local/global comparison. Extraction failures can
hide additional semantic errors, so the counts are not causal percentages.

For context, full-history had 3 correct and 1 local error in its four observed
requests before capacity stopped both chains. Compact had 1 correct, 8 new local
errors and 7 extraction failures. Different observation lengths prevent a fair
whole-chain accuracy ranking against history.

## Implemented changes

The original v6 files, prompts and results are unchanged. V7 adds:

- A generic instruction to emit one target result, rather than either a target
  record or the whole state. The successful status and resulting count are
  explicit. Copy identifies the source and destination; the condition explicitly
  compares the count, including the equality case. There are no examples, answer
  prefill, per-case prompt selection or model-specific codes.
- Separate `parsed` and `committed` fields. The application rejects wrong-target
  proposals and count changes on requested missing/error operations. Rejection
  preserves state. This uses the request and actual state, not gold arithmetic;
  wrong numeric answers still commit and propagate. Raw accuracy is scored
  independently of admission, so rejection cannot turn an error into a success.
- Explicit failure attribution, local and global answers, input-state drift and
  target-answer drift. Full-state agreement is separate from a correct reply.
- Matched ideal-state snapshot controls, plus isolated add, subtract, copy and
  conditional probes at 49, 50 and 51. These separate basic computation from
  conditional selection without executing arithmetic on behalf of the model.

The primitive subtraction probe is new; it is not retroactively treated as a
v6 capability measurement. V7's commit contract applies to both prompt policies,
so fresh paired comparisons isolate the prompt under that contract. V7 scores
are not paired with old v6 scores, whose cases and commit policy differ.

## Development validation

The frozen manifest uses seed 20261021701, two fresh eight-step chains with
opposite target order, and twelve independent primitive probes. Original and
clarified prompts each receive 16 dependent, 16 snapshot and 12 primitive
requests: 88 CPU inferences maximum. There is no new heldout run and no reuse
of v6 heldout as development inputs. Prior heldout results are diagnostic
evidence only; improvements require future fresh qualification.

Context remains 256 with 48 reserved output tokens, the pinned Qwen3-0.6B Q8_0
model and greedy CPU settings. The model interface receives only prompt text,
token IDs and output budget, never expected values or state objects. Frozen
sources and executable are hashed, and v6/v8 seals are checked before and after.
CPU process time includes model loading and is not an FPGA performance result.

61 focused tests passed before the first execution, including conditional boundaries,
unknown-operation rejection, wrong-target and preserve-count admission, lack of
arithmetic repair, separate oracle controls, and actual bad-count propagation.

The subsequent audit regression checks and copy-probe regression bring the
focused suite to 66 passing tests. Audit tests deliberately corrupt gold answers,
local expectations and state commits and confirm that each mismatch is detected.

## Development results and probe correction

The first v7 run completed all 88 inferences and sealed its evidence. Four groups
of repeated identical inputs had zero output-text mismatches. Both original and
clarified prompts use the same v7 admission contract.

| Fresh development measurement | Original | Clarified |
|---|---:|---:|
| Globally correct dependent answers | 2/16 | 2/16 |
| Locally correct dependent answers | 3/16 | 8/16 |
| Correct ideal-state snapshot answers | 3/16 | 9/16 |
| Parsed dependent answers | 13/16 | 14/16 |
| Committed dependent proposals | 13/16 | 12/16 |

The clarified prompt's ideal-state controls scored copy 3/4, missing 2/2,
error 2/2 and set 2/2, but add 0/2 and conditional 0/4. Its dependent failures
comprised six new local errors, six inherited-only errors and two extraction
failures. The original had ten new local errors, one inherited-only error and
three extraction failures. Thus better local handling did not produce a
successful chain, and the snapshot/trajectory difference must remain visible.

Review found one confounded **new development primitive probe**: when B was the
target, initialization accidentally gave both entities the same count. Copying
was then indistinguishable numerically from retaining the target. Its status
could still differ, but it is unsuitable evidence of count copying. This does
not affect any of the dependent chains, their snapshots, or the v6 audit.

The entire first run and its frozen source snapshot remain sealed unchanged.
V7-r2 fixes the generator by assigning target and source counts separately with
a fixed nonzero separation. A regression asserts unequal counts and a non-noop
copy result for every primitive case. A separate primitive-only run uses fresh
source counts and deltas: 24 CPU inferences, original and clarified policies,
at the same 49/50/51 comparison boundary. No chain rerun or new prompt search is
performed. Its results live in `build/v2/v8-json-diagnostics-v7-r2`.

The corrected primitive check completed all 24 inferences. Original scored
1/12 and clarified 10/12. Under the clarified prompt, add, subtract and copy
each scored 3/3; conditional scored 1/3. This shows that these small primitive
calculations can succeed while combining comparison and arithmetic remains
fragile; it does not establish arithmetic reliability at other magnitudes.

Across both runs, 112 CPU inferences were saved separately. V7 sealed 279 files,
v7-r2 sealed 88; final hash checks found no mismatches or unsealed files. Both
runs verified all 432 v6-r2 and 269 v8 sealed files unchanged. No heldout
qualification, FPGA request, board-status write or full-sweep restart occurred.
The clarified prompt is a development candidate, not a qualified replacement
for all benchmark families. No expanded closed-loop benchmark was launched.

## Expansion policy

Keep retention and closed-loop reasoning as separate experiments. Expand JSON
retention first with fresh sequences if evaluating bounded memory. Closed-loop
claims require fresh qualification after development and both local correctness
and end-to-end survival reporting. Freeze the generic prompt and admission
contract before that run; do not chase each arithmetic error with Qwen-specific
examples or claim that parser acceptance measures reasoning reliability.
