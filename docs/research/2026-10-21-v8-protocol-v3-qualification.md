# v8 protocol v3: development and fresh qualification

This benchmark leaves deployed v8 unchanged. The full v1 sweep remains stopped;
qualification never launches it, regardless of admission scores. V1 and v2
evidence is preserved. Results live separately in `build/v2/v8-protocol-v3`.

## Failure diagnosis and changes

V2 failures include genuine semantic errors on both CPU and FPGA. Examples from
the FPGA traces: copying B=61 into A returned A's previous count 27; the enum
version returned the right count with the wrong target (`0 B 61`). A conditional
update expected 26 but retained 23. Compact add expected B=70 but returned 8 or
10. Missing/error sometimes borrowed the other counter's count or the example.
Strict parsing distinguishes these valid-but-wrong records from framing errors.

V3 compares three candidates on development cases:

| Candidate | Compact input example | Numeric output example |
|---|---|---|
| named-line | `A:31,ok;B:66,ok` | `0 A 31` followed by newline/EOS |
| named-array | `A:31,ok;B:66,ok` | `[0,"A",31]` |
| tuple-array | `[31,"ok",66,"ok"]` | `[0,"A",31]` |

All retain a string-status JSON output arm, e.g. `["ok","A",31]`.
The named representation replaces the ambiguous slash/count-status-digit input
with named counts and status words. The tuple representation has a fixed order
explicitly declared in the prompt. Both have strict lossless state decoders.
Numeric JSON retains delimiters that make completion unambiguous; removing
punctuation is not assumed to save tokens or improve reliability.

Examples are selected only by operation family, use fixed unrelated values and
match the actual context/output encoding. Prompts repeat the requested target,
distinguish it from the source, and tell missing/error cases to retain the
target's count. Conditional prompts state both branches and unrelated branch
examples. The event's defined status is explicitly supplied (ok/missing/error,
or its numeric code); this reduces status inference and is a protocol change.
No computed count, evaluated predicate or expected result is supplied. This is
a task-conditioned protocol, not unrestricted status discovery.

An initial 98-response CPU development pilot exposed status/entity confusion
(B sometimes elicited status 1). It was stopped before qualification and retained
with its original source under `cpu-development-pilot`. Revised prompts make the
operation's status explicit. No qualification responses inform candidate tuning.

## Experimental controls

Development contains 12 cases (both targets for set/add/copy/conditional/missing/
error), six context/output arms, three candidates: 216 CPU generations. Rank by
worst-arm semantic count, worst-arm format count, total semantic, total format,
then fewer mean input tokens. Ties keep the first candidate. Freeze the winner,
source hashes and qualification manifest before evaluating any fresh case.

Fresh qualification uses 12 distinct cases, six arms: 72 CPU and 72 FPGA
requests. Exact state/operation signatures are disjoint across development,
qualification and the previous v2 qualification. Values are small two-digit
counts with positive operations; both conditional branches are covered, but
negative values and non-ok prior statuses are not qualified by this sample.
In this small fixture A starts below the branch threshold and B above it;
entity and branch are therefore correlated, a limitation for generalization.

The unchanged per-arm gate is at least 11/12 valid records and 9/12 exact
semantic matches. All prompts plus 32 output tokens must fit 256 tokens.
Expected results exist only in scorer/manifest data. No output repair, grammar
constraint, vocabulary mask, CPU model correction or real tool execution occurs.

CPU uses the pinned Qwen3-0.6B Q8_0 GGUF and greedy llama.cpp decoding, not the
FPGA's INT8 activation arithmetic. Compare semantic outcomes without claiming
numerical parity. H and J coincide at initial state; these single-step controls
do not establish sustainable chain depth or a full-history compression benefit.

FPGA reads the original v8 package and runs a private hash-checked snapshot under
`/var/lib/sysone/benchmarks/v8-protocol-v3`. It holds the inference lock, disables
prefix reuse, and prefills each request from position zero. Deployment identity,
pre/post causal fixtures, exact CPU/FPGA input token IDs and repeated H/J inputs
are checked. A separate original-MVP generation control executes no tool.

## Results

The completed `qualification-summary.json`, paired comparisons and raw request
traces are authoritative. CPU development selection is in `cpu/selection.json`;
fresh CPU qualification is in `cpu-qualification/`; FPGA traces are in `fpga/`.
The qualification seal records the evidence files. Full sweep remains stopped.

CPU fresh qualification completed with 72/72 valid records and 47/72 exact
answers. String-status H/J/C arms each scored 9/12 correct; numeric-status H/J/C
scored 8/12, 8/12, 4/12. All twelve conditional responses were wrong. Examples
include outputting the demonstration result 3 instead of 35, emitting status 1
for a successful update of B, and retaining example count 2 for missing/error.
The CPU gate failed. These raw valid records establish semantic failures rather
than parser rejection. FPGA results are recorded separately in the summary.

On the frozen fresh cases, bare compact state averages 17 bytes/11 tokens versus
63 bytes/23 tokens for JSON state. Complete prompts average 168.67 versus 180.67
tokens, a 6.64% reduction; instructions and demonstrations dominate this small
state. See `state-size-analysis.json`. This does not measure savings after many
dependent steps. V2 and v3 use different qualification values, so their aggregate
scores are descriptive cross-version results, not a paired accuracy improvement.

## Completed FPGA result and disposition

| Arm | CPU valid | CPU correct | FPGA valid | FPGA correct |
|---|---:|---:|---:|---:|
| History / string status | 12/12 | 9/12 | 12/12 | 9/12 |
| History / numeric status | 12/12 | 8/12 | 12/12 | 7/12 |
| JSON state / string status | 12/12 | 9/12 | 12/12 | 9/12 |
| JSON state / numeric status | 12/12 | 8/12 | 12/12 | 7/12 |
| Compact state / string status | 12/12 | 9/12 | 12/12 | 10/12 |
| Compact state / numeric status | 12/12 | 4/12 | 9/12 | 3/12 |
| Total | 72/72 | 47/72 | 69/72 | 45/72 |

Both overall admission gates failed. FPGA conditional accuracy was also 0/12;
three numeric compact records included Markdown fences and failed strict format
checks. Among valid records, CPU had 23 wrong-count and two wrong-status answers;
FPGA had 20 wrong-count and four wrong-status answers. Neither backend produced
a wrong target in a valid record in this sample. No repairs were applied.

The string-status compact arm meets this small per-arm gate; the six-arm protocol
does not. Numeric status IDs are not justified by these results. The next
development effort should address count retrieval and conditional arithmetic,
rather than assume delimiter removal or a grammar can fix semantic errors.
Qualification cases must remain excluded from subsequent prompt tuning.

All 72 CPU/FPGA input token sequences matched. There were 63 matching parsed
outputs among 69 valid on both backends; 24 repeated H/J inputs had identical
FPGA output IDs. This supports reproducible execution, not CPU/FPGA arithmetic
equivalence. Both causal fixtures passed; board package/launcher identities and
Linux boot were unchanged. All 269 sealed local v8 artifacts and all 487 sealed
v2 evidence files verified unchanged. The original MVP generation reproduced
the previous 62 prompt/16 output token IDs and executed no tool.

The final board audit reports the baseline unit inactive/dead and no benchmark
processes. The authenticated session is closed. The evidence seal includes the
completed session receipts and all retained development/qualification traces.
Full sweep remains stopped; no dependent-chain sustainability claim is made.
