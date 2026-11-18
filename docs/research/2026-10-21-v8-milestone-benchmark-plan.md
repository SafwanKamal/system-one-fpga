# v8 milestone baseline and dependent-workflow experiment

Status: proposed protocol, 2026-10-21. No benchmark runs or board changes are
performed by this document. Preserve the sealed v8 release and earlier seals.
New harnesses, prompts, fixtures and results belong in separate versioned packages.

## Baseline campaign

Freeze bitstream, model, tokenizer, runtime, runner and workload hashes. Record
Linux boot, kernel, clocks, memory allocation, temperature and background load.
Use one request at a time, greedy selection, thinking disabled, full vocabulary
and no prefix reuse. Run the existing causal board fixtures before and after.
Do not tune the implementation during measurement or discard slow observations.

Measure separately:

1. Cold application calls: fresh process/runtime/tokenizer; weights resident;
   complete resident-weight SHA verification inside the request timer.
2. Persistent sequential requests: initialize once, retain runtime/tokenizer and
   weights, but reset logical request KV and prefill every independent prompt.
   Verification-once is a declared alternative to cold-call verification.
3. Model provisioning: loading and initial verification outside request latency.

Fixed-work sweep: total input tokens 32/64/128/192, output tokens 16/32/64,
three frozen prompts per cell and five repetitions per prompt per operating mode:
180 requests per mode. Check complete templated token lengths, not user text alone.
All input-plus-output budgets must fit the deployed 256-token context. A new
benchmark adapter must support declared fixed output counts without executing
tools; the production runner stops on completed JSON and cannot serve unchanged.
Record EOS occurrence and distinguish forced-length work from natural completion.

Repeat the historical boot-ID command 30 times. Add 100 frozen application cases
for the current one-tool scope. The production executor permits only boot_id,
uptime and version under /proc; arbitrary fixture paths require a separate
benchmark executor. Keep unsupported and invalid outputs in scoring denominators.

Collect lock wait, startup, SHA, tokenization, submission-to-first-token, prefill,
per-token decode, parse, execute and complete-call times. Count the first generated
token under prefill, not subsequent decode throughput. Save generated IDs, actual
lengths, errors, finish reasons, layer passes, vocabulary projections, command
counts, CPU/memory/thermal data and all interrupted attempts. Separate lock wait
explicitly; the historical runner's outer timer begins before lock acquisition.

Declare warmups, randomize measurement order with a saved seed, and report raw
observations, mean, median and spread. Tail estimates need larger samples than
this initial cell design. Measure energy only with an identified instrument and
sampling boundary; report CPU utilization as an observation, not an energy proxy.

## Added experiment: compact state across dependent requests

### Questions and hypotheses

- Can bounded typed state sustain more correct dependent steps within a fixed
  context budget than retaining the full transcript?
- Does shortening the generated wire format reduce complete-workflow latency
  without unacceptable semantic or parsing failures?
- How much improvement comes from selecting relevant state versus its encoding?

These are hypotheses, not current v8 capability claims. Typed-output protocols
and state compression alone are not claimed as novel.

### Two independent factors

Context factor:

| Arm | Information passed into the next request |
|---|---|
| H: full history | Initial task plus every previous request, generated response and observed tool result |
| J: typed JSON state | Initial task, current request and canonical current state; no transcript |
| C: compact typed state | Exactly J's state fields and values in a shorter deterministic encoding |

Output factor:

| Arm | Model-generated action representation |
|---|---|
| A: current-style array | JSON array with explicit values and natural-language enum names |
| E: compact enum record | Fixed field order, small documented enum IDs, explicit record boundary and escaping rules |

Use the resulting 3x2 comparison where feasible. Compare H/J with the same output
format to isolate state selection, J/C to isolate state serialization, and A/E
within a context arm to isolate output serialization. Histories include the
actual output encoding for that arm. Prompt instructions may necessarily differ;
retain and count those differences. Use identical tasks, tools, semantic state,
decoding policy and token budget otherwise. No vocabulary masks or grammar
constraints in the primary study. Any constrained decoding is a separate arm.

### Protocol development before measurement

Use development-only tasks to choose and freeze the compact codec. Candidate
formats include positional JSON arrays, newline/space-delimited records and
fixed-order records with enums. Removing punctuation is not assumed beneficial:
measure actual token IDs using the pinned Qwen tokenizer, including the codebook,
schema instructions, escaping and record terminator. Bytes and tokens are
separate metrics. The current MVP already uses a positional JSON array.

Use versioned, collision-free enum IDs, e.g. status 0=ok, 1=missing, 2=error.
Do not use arbitrary hashes for a small categorical field. Never shorten free
text, paths, identifiers, units or numeric precision by a lossy substitution.
Opaque IDs may reference host records only when that lookup is explicit and
identical across arms. If a value is needed for reasoning, the model must receive
it or use an equally available explicit lookup tool; hidden host answers are not
free context compression.

Keep field boundaries unambiguous. Variable-length strings require a defined
delimiter/escape or length convention. Unknown IDs, missing fields, extra fields,
trailing data and overflow must fail validation rather than be repaired. Test
codec round trips and malformed input rejection before measuring model behavior.
Stable tokenization does not imply the model understands an ID. Evaluate that.

### Workloads and state ownership

Use a deterministic simulated tool environment, not arbitrary Linux execution.
Proposed chain families: state updates/corrections, arithmetic with units,
references to earlier entities, conditional action selection, and missing/error
results requiring clarification. Include delayed dependencies, distractors and
superseded facts. Fresh realistic result values prevent memorizing outputs.

For each task family, define a shared state schema sufficient for its dependencies.
The initial specification and current request remain available to every arm.
State updates use only actual emitted actions and actual simulated results;
never ground-truth answers or future task steps. A deterministic reducer is
audited separately. Compression must retain unresolved goals, entity identity,
units, result provenance and error states where required. Host normalization
does not silently fix an incorrect model action. Count reducer time and failures.

The current production runner has one file-read tool and no conversation loop.
This experiment needs a new runner, simulator, parser and explicit state reducer.
It does not imply that the sealed application already supports these workflows.

### Finite execution stages

1. Development: 12 chains, disjoint from evaluation, for codec/prompt selection
   and reducer checks. Inspect token counts and context feasibility first.
2. Qualification: exercise the new harness on short chains and verify identical
   semantic parsing/scoring across encodings. Confirm timestamp boundaries and
   that no old KV leaks between reprefilled requests. Use saved fixtures to check
   instrumentation where possible. Fix bugs before freezing evaluation artifacts.
3. Held-out milestone: 24 fresh chains, each up to 16 steps, paired across six
   arms. Maximum 2,304 model requests, fewer when an arm reaches its context limit.
   Choose the balanced task mix and seed before seeing results. Record prefix
   outcomes at steps 1/2/4/8/16. A later 32-step extension is a separately declared
   extension, not an outcome-selected continuation of favorable chains.

Run the board milestone with its actual 256-token total context. Fix an output
reservation per task across arms. If full history cannot fit, record context
exhaustion and stop that arm; do not silently truncate it. A sliding-history
baseline can be added explicitly, with a fixed truncation policy. Distinguish
capacity failures from semantic errors. Evaluate larger contexts first in software
if desired; those results do not imply an enlarged FPGA context or v8 arithmetic
equivalence unless independently established.

Start each step with fresh logical KV and reprefill the chosen representation.
Keep runtime/model resident for throughput measurements. Prefix/KV reuse is a
different optimization and must not confound the primary context comparison.
Pair arms by task; randomize arm execution order. After a semantic error,
continue the simulated workflow where defined to measure propagation, but retain
the first error and do not substitute the gold result. Infrastructure aborts and
context exhaustion are distinct terminal events, with all attempts preserved.

### Metrics

- Exact action/argument accuracy, format validity, enum confusion, refusals and
  incorrect accepted actions. Keep parse and semantic failures distinct.
- Fraction of chains correct through step k; first-error step; task completion;
  context-exhaustion step and cumulative correct useful steps.
- End-to-end rolling state versus an oracle-state diagnostic at selected steps:
  oracle supplies correct prior state only and is labeled separately; its output
  is never fed back into the measured rolling chain.
- Input/output tokens, codebook overhead, total tokens per completed workflow,
  token-growth slope and bytes. Report generated thinking/formatting overhead.
- Per-step prefill/TTFT/decode and complete-workflow latency, including parsing,
  reduction and simulated tool work. Report cold startup separately and amortized.
- Correct completed workflows per second; energy per correct workflow only if
  measured. Never reward a fast invalid response as useful throughput.

Use paired differences and uncertainty resampled by chain, not by dependent step.
Twenty-four chains are an initial milestone sample, not evidence of rare failure
rates. Report censored chains and capacity failures rather than assigning an
invented successful horizon. Freeze any acceptable quality-loss margin before
evaluation; report the full quality/latency tradeoff regardless of promotion.

## Potential paper outcome

A defensible result would quantify sustained task correctness, context growth,
and FPGA latency under identical dependent workflows. The useful contribution
would be an evaluated typed-state protocol and execution method for bounded-context
embedded inference, with explicit failure and state-provenance handling. It needs
measured benefits and comparison with simple JSON/state baselines. Smaller wire
syntax, enum IDs, or a long sequence of successful calls alone do not establish
novelty, semantic safety, arbitrary workflow support or a real-time guarantee.

## Deliverables

New benchmark source snapshot, protocol/codebook, workload manifests and hashes;
per-step/per-request JSONL; semantic state traces; summaries and plots for accuracy
survival versus step, input-token growth, and complete-workflow quality/latency;
qualification fixtures; immutable evidence manifest. No model, bitstream, launcher
or previously sealed deployment evidence is changed by this plan.
