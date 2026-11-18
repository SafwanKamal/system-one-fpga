# v8 protocol v4: compact state and string statuses

V4 focuses only on compact state with a string-status JSON record, such as
`["ok","A",35]`. V8 deployment, model, runtime, tokenizer, FPGA and launcher
remain unchanged. The full sweep stays stopped regardless of qualification
scores. V2/v3 qualification cases are excluded from new prompt development.

## Development

New development contains 28 cases: four each for set/add/copy/missing/error and
eight conditionals. Both targets occur on both threshold sides. Conditional
counts include exactly 50 and 51 for each target. Prior statuses include ok,
missing and error, unlike the earlier all-ok qualification states. These make
the sample more representative of rolling typed state, but prevent direct
accuracy comparisons with the easier v3 cases. All amounts are positive small
integers and counts remain small; this is not a general arithmetic benchmark.

Every candidate uses the same development inputs. Rank by worst-operation
semantic fraction, then valid-record count, total exact answers, and fewer mean
prompt tokens. Ties keep the first candidate. No candidate selection depends
on the actual request's count, branch decision or gold answer.

Preserved exploratory development pilots:

- `cpu-pilot1`: 84 responses. Removing examples caused a format regression.
  Two opposite-branch examples improved conditional accuracy to 4/8, while
  operations with no examples often returned malformed records.
- `cpu-pilot2`: 43 responses before stopping. A formatting-only echo example
  restored arrays but caused copies of its target/count. No qualification ran.
- `cpu-pilot3`: 84 responses. A host-prefilled status/target header without
  numeric examples did not resolve count retrieval or conditional errors.

Original source snapshots and dispositions accompany every pilot. Pilot manifests
are development artifacts and were never submitted for qualification.

Final development comparison includes:

- `v3-control`: unchanged v3 compact/string prompt, on the new development cases.
- `two-tuple`: two operation-specific examples with different targets and prior
  statuses; conditional examples cover both branches. Positional compact state.
- `two-named`: the same two examples with `A:count,status;B:count,status`, retaining
  entity labels to reduce positional count confusion.
- `prefilled-contrastive`: known status and target prefilled in the assistant
  record, model generates the numeric suffix; two conditional examples only.
  This is explicitly a scaffolded output protocol, not free generation of all
  three fields. No count, predicate result or arithmetic answer is prefilled.

Demonstrations use fixed unrelated states A=64/B=17 and A=72/B=19, with amounts
7 and 4. They do not select a branch for the evaluated request. Both targets and
prior non-ok statuses are represented, and demonstrations use the same compact
encoding as the actual input. No grammar mask, output repair, host arithmetic,
CPU model correction or tool execution is used.

## Frozen qualification

After development selection, freeze sources, all prompts, input token IDs,
expected records and gate thresholds before any qualification inference.
Use 28 fresh cases with the same coverage plus four exact-input repetitions
for conditional/missing/error checks: 32 requests per backend. Repeats are
excluded from accuracy. Development, qualification and prior v2/v3 exact
state/step signatures are checked for overlap by tests.

The compact/string gate requires at least 26/28 valid records and 21/28 exact
answers. Additionally, conditionals require at least 6/8 correct, and each other
operation requires at least 3/4. These retain the previous 75% semantic threshold
and approximately 92% format threshold while adding operation-family checks.
No claim of production reliability or sustainable dependent-chain depth follows
from passing such a small sample.

Inputs plus 32 output tokens must fit context 256. CPU uses pinned Qwen3-0.6B Q8_0
in greedy llama.cpp; FPGA uses unchanged v8 INT8 activation arithmetic. They are
quality controls, not mathematically identical backends or a fair CPU-speed test.

The board reads its original package and runs a hash-checked snapshot only under
`/var/lib/sysone/benchmarks/v8-protocol-v4`. Each prompt is prefilled from zero
with prefix-cache reuse disabled. The assistant record-header experiment, when
used, is input text and is unrelated to KV prefix-cache reuse.

Collect raw results, causal fixtures before/after, package/launcher/boot identity,
paired input IDs, four repeated output-ID checks and an unchanged-MVP generation
control. Verify sealed v8 and prior v2/v3 evidence. Audit the baseline unit and
benchmark processes, close the RAM-only authenticated session, then seal the new
evidence. The full sweep is never launched by this workflow.

## Results and disposition

The completed `build/v2/v8-protocol-v4/qualification-summary.json` is authoritative.
Development selection is in `cpu/selection.json`; fresh CPU traces are in
`cpu-qualification/`; FPGA traces are in `fpga/`. `semantic-failures.json` retains
every failed fresh case. Qualification cases must not be recycled for tuning.

Final development selected `two-named`: 28/28 valid, 21/28 correct, compared with
28/28 valid and 16/28 correct for the v3 prompt on exactly the same new cases.
Eight cases improved and three regressed. Set/add/copy/conditional/missing/error
correct counts changed from 4/1/3/0/4/4 to 4/4/2/4/4/3. This is a real paired
development improvement with tradeoffs; it does not prove fresh-case accuracy.
The selected protocol generates the entire output freely; no response header is
prefilled. The prefilled candidate was tested and not selected.

Selected state averages 12.46 tokens (20.36 bytes), versus 11 tokens for tuple
state and 23 for nested JSON on these fresh states. Complete selected prompts
average 187.89 tokens, range 176–201; plus 32 output tokens they fit context 256.
Two demonstrations add prompt overhead relative to v3. State compression should
not be described as a measured whole-workflow speedup or sustainable-chain gain.

CPU qualification completed with 28/28 valid records and 19/28 exact answers,
excluding four repeats. Set/add/copy/conditional/missing/error scored
4/4, 4/4, 2/4, 4/8, 2/4, 3/4. Its gate failed. Remaining failures include copying
the target's old count instead of the source, wrong branch/arithmetic at 51,
an example count 19 instead of current count 18, and status ok instead of the
requested missing/error. The changes partly address the failures; they do not
fix conditional arithmetic or example copying reliably.

## Completed paired result

CPU and FPGA each scored 28/28 valid records and 19/28 exact answers. Their
operation-level scores were identical:

| Operation | CPU correct | FPGA correct |
|---|---:|---:|
| Set | 4/4 | 4/4 |
| Add | 4/4 | 4/4 |
| Copy | 2/4 | 2/4 |
| Conditional | 4/8 | 4/8 |
| Missing | 2/4 | 2/4 |
| Error | 3/4 | 3/4 |

Both semantic gates failed, including conditional, copy and missing family
thresholds. All nine failed cases on each backend had valid records: seven
wrong counts and two wrong statuses, with no wrong-target records. These failures
are retained in raw traces and the failure ledger. A copied example count 19,
source/target count confusion, and incorrect arithmetic at 51 remain unresolved.

All 32 paired inputs matched token-for-token, including the four repeat jobs.
Four exact FPGA input repetitions produced identical generated token IDs.
Pre/post causal fixtures passed; package/launcher/boot identity matched both
within this run and the previous qualification. The original MVP generation
reproduced its prior token IDs without tool execution. All 269 sealed v8 files,
487 sealed v2 evidence files and 1233 sealed v3 evidence files verified unchanged.
The final audit reports the full-sweep unit inactive/dead and no benchmark
processes; the authenticated session is closed. All 42 focused tests passed.

The full sweep remains stopped. This protocol is an improvement on the paired
development cases, not a reliable conditional executor. Further work should
test explicit branch/arithmetic decomposition or model adaptation with new
development cases; JSON framing alone cannot address these observed semantic
errors. No sustainability or paper-level reliability claim is established here.
