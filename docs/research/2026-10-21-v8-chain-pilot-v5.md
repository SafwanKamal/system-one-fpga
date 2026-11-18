# Dependent-chain pilot v5: context management separate from exact formatting

This pilot freezes one compact representation and one generic prompt rather
than tuning a serializer for Qwen. It tests only deployed Qwen3-0.6B on the v8
system. Representation effectiveness and prompt sensitivity remain model-specific
empirical questions. The harness separates context management, record extraction,
task competence and error propagation; it does not claim universally optimal
compaction or cross-model scalability.

V8 deployment is unchanged and the full sweep remains stopped. All results are
separate under `build/v2/v8-chain-pilot-v5`. No previous benchmark evidence is
rewritten. Sources, parser policy, sequences and manifest were frozen before
the first CPU/FPGA inference; no prompt selection, demonstrations or retries.

## Plan and scoring

Two eight-step chains run independently with H=full raw conversation history
and C=named compact state (`A:count,status;B:count,status`). The simple chain uses
set/copy/missing/error to test retrieval and status handling without arithmetic.
The other uses add/conditional/copy/set/missing, including both conditional
branches. Initial states and operation sequences match across arms and backends.
One chain per family is a harness pilot, not a statistical accuracy estimate.

Each backend owns its observed trajectories. A valid parsed proposal is committed
verbatim, including incorrect counts, statuses or targets. Rejected answers leave
state unchanged. The next request reports only accepted/rejected feedback. C
receives the current observed state; H retains every raw request/reply, its
initial state and acknowledgement feedback, without truncation or summarization.
H never receives a current-state snapshot that would bypass reconstructing history.

Gold state is maintained separately for scoring. Exact answer versus the ideal
trajectory measures end-to-end success; local correctness versus the actual
observed state distinguishes new mistakes from inherited ones. Full-state
equality and transitions back to equality measure recovery. First semantic
failure includes unparseable output, with first parse failure separately recorded.

Sixteen standalone one-step controls use the ideal state before each request.
These are explicitly labeled oracle-input diagnostics, not measured chains.
Their outputs never repair rolling state. They separate base task competence
from accumulated context/state errors. Expected outputs are not passed to either
backend's inference method.

## Predeclared parser

The parser consumes the complete response to actual EOS or a fixed 48-token
budget; it never stops at a parseable prefix and ignores contradictory suffixes.
It accepts one closed JSON array of three fields or one object with exactly
status, entity/target and count/value/new_count. It also accepts a complete
Markdown JSON fence and two EOS-delimited text forms: `ok A 35` or
`status=ok;entity=A;count=35`. Field aliases, status/entity case folding and
canonical integer strings are deterministic lexical normalization.

It rejects duplicate/ambiguous/extra fields, multiple records, embedded answers
in prose, incomplete fences, booleans, floats, unknown statuses/entities and
out-of-range counts. It never searches for a gold match, supplies missing fields,
chooses between competing counts, infers a status or corrects arithmetic.
Closed JSON can terminate at the budget boundary; an unterminated plain numeric
record needs actual EOS to avoid accepting a partial number.

`native_format` is explicitly the **previous strict JSON-array parser's** result.
It is a preferred-array conformance metric, not compliance with this pilot's
more permissive prompt (which permits objects). Accepted/normalized records and
semantic correctness are reported separately.

## Capacity and measurement controls

The deployment context is 256 with a fixed output reservation of 48, leaving
208 input tokens. A prompt that exceeds that allowance is recorded as a capacity
stop without issuing an NN request. No sliding window or silent history trimming.
This is the deployment's configured budget, not Qwen's general context limit.
A shorter output reservation could change the full-history stopping point.

Successful-prefix survival after a known semantic failure is false even when
later steps hit capacity. A chain with no observed failure before capacity is
censored at its last generated step; its longer-horizon survival remains unknown.

FPGA per-request timing includes resident inference/prefill/decode, with full
prefill from position zero and no KV prefix reuse. CPU uses pinned greedy
llama.cpp Q8_0 and includes process/model-load time, so it is a quality control,
not a speed baseline. Host normalization/reducer overhead and energy are not
measured in this pilot. No sustained-throughput or energy claim.

The private board snapshot is `/var/lib/sysone/benchmarks/v8-chain-pilot-v5`.
Exclusive inference lock, pre/post causal fixtures, package/launcher/boot
identity, original-MVP exact-token control and prior evidence seals are checked.
No real tool calls, model reload, FPGA reconfiguration or deployment writes.

Paired fixed control prompts must match CPU/FPGA token IDs. Dependent inputs may
legitimately diverge after different backend outputs; each backend rolls its own
state, rather than replaying CPU answers onto FPGA. Matching-input comparisons
and identical-input FPGA repetition checks are reported explicitly.

## Results

The completed `pilot-summary.json`, per-backend `summary.json`, full request
traces, comparisons and failure ledger are authoritative. Capacity, correctness
and accepted-format counts must remain separate. Even if C runs more requests
than H, that is not evidence of more correct dependent steps or general context
retention unless the semantic results also support it.

CPU completed 36 NN requests plus two capacity-stop records. The legacy strict
array metric was 0/36, but normalization accepted 35/36 responses. The remaining
response contained `"count": 79 - 6`, an unevaluated expression rather than an
integer; the harness did not calculate the answer for the model.

CPU standalone controls scored 6/8 on retrieval/status and 4/8 on arithmetic.
Both C chains ran eight steps, with inputs 113–132 tokens; both H chains stopped
before step three under the 208-token input allowance. Simple H/C first failed
at step two (copying B's existing 74 instead of A's 43). Arithmetic C first
failed at step two; arithmetic H was correct for both observed steps and then
capacity-censored. This does not show that C improves semantic retention.

Observed-state scoring exposes error propagation: after the wrong copy, reporting
missing with count 74 is locally correct for the committed state but globally
wrong versus the ideal count 43. It must not be counted as a new arithmetic or
memory error. The original wrong count remains present; no gold repair occurs.

## Completed CPU/FPGA pilot

Both backends completed 36 NN requests and recorded two capacity stops. Both
accepted 35/36 responses with 0/36 legacy-array conformance. The dependent-chain
outcomes below were identical across CPU and FPGA:

| Chain | Context | Generated steps | Exact answers | First semantic failure | Capacity stop |
|---|---|---:|---:|---:|---:|
| Retrieval/status | Full history | 2 | 1/2 | 2 | Before step 3 |
| Retrieval/status | Compact state | 8 | 4/8 | 2 | None within 8 |
| Arithmetic | Full history | 2 | 2/2 | Not observed | Before step 3 |
| Arithmetic | Compact state | 8 | 2/8 | 2 | None within 8 |

Each backend produced nine exact answers in 20 dependent inferences. The 16
one-step controls scored CPU10/16 and FPGA9/16 (retrieval/status6/8 on both,
arithmetic4/8 versus3/8). Controls and dependent steps must not be pooled to claim
a chain reliability rate. No compact chain recovered full ideal state after its
first error. Local/global correctness traces identify inherited errors separately.

Full-history input sizes were 114,168,224 for retrieval/status and 113,180,234 for
arithmetic, with the third request blocked by the 208-token allowance. Compact
inputs stayed 113–132 tokens. This demonstrates a capacity benefit under the
chosen budget, not eight correct dependent steps or a general Qwen context width.
Arithmetic full history remained correct through the two observed steps and is
right-censored afterward; its longer-horizon quality is unknown.

The one-step controls omit prior-reply acknowledgement. Therefore control versus
chain differences can include acknowledgement/prompt sensitivity, not only state
accumulation. Representation changes also alter model behavior. These controls
diagnose base competence; they are not an identical-prompt causal ablation.

All 38 recorded input sequences (36 inferences plus two stops) matched across
backends. Among 35 records valid on both, 34 parsed outputs matched; one additional
record was unparseable on both. Four repeated initial prompts produced identical
FPGA output IDs. Causal fixtures, unchanged package/launcher/boot identity and
original-MVP exact-token generation passed. Seals verified all269 v8 files and
all prior v2/v3/v4 evidence (487/1233/1156 files). All62 focused tests passed.

The final audit shows the full sweep inactive/dead with no benchmark processes;
the authenticated session is closed. Results are sealed separately. Further work
should evaluate fixed, portable state representations and application tasks
across models rather than optimize a Qwen-specific symbolic code. This pilot
supports separating capacity from semantic reliability; it does not establish
better retention, a scalable compaction method or a paper-ready reliability claim.
