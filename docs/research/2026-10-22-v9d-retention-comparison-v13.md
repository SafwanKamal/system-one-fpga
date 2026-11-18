# JSON state versus full reference conversation on v9d

This finite experiment intentionally reuses the six sealed v12 primary workloads:
mixed and long-gap at 16, 32, and 64 steps, totaling 224 semantic tasks per arm.
It is a new representation comparison on known workloads, not a fresh holdout.
All evidence is separate under build/v2/v9d-retention-comparison-v13.
The full system sweep remains stopped. The sealed v8 baseline is preserved.

## Representation and control

The JSON arm retains the frozen v10-r3 instruction and current host-managed JSON
snapshot (129 input tokens). The host reducer consumes only trusted simulated
tool observations: ok replaces count/status; missing/error changes status while
preserving that entity's count; no observation leaves state unchanged.

The history arm receives initial state and every prior user observation/query
and canonical correct assistant JSON reply, followed by the current observation
and query. No prior turns are discarded. Canonical replies are fixed from the
reference trace, equal on both backends. Actual answers never rewrite a later
prompt. Thus this is teacher-forced retention, not closed-loop model feedback.
Only prior answers are present; the current reference answer is never inserted.
The supplied history instruction states the same reducer rules explicitly.

Both arms use Qwen3-0.6B Q8_0, greedy decoding, a 48-token generation reserve, a
1,024-token context, complete response generation to EOS/budget, unchanged
syntax-only tolerant normalization and semantic scoring. CPU actual verbose CLI
IDs are compared with frozen IDs on every executed request; the CPU prompt file
includes the corrected extra framing LF. FPGA independently tokenizes and checks
input IDs. No inter-request prefix/KV reuse is enabled in either arm.

Inputs exceeding context minus output reserve are recorded as context-overflow,
with zero model execution and no inference latency. Report separately delivered
accuracy (correct/all requested), conditional accuracy (correct/executed), and
capacity coverage. Do not label capacity rejection an arithmetic/status mistake.
Do not average zero-time rejections into latency. CPU-only supplemental context
4,096 executes precisely the overflowing full-history inputs; keep that evidence
separate from the matched 1,024-token comparison.

## Costs and audit

Report required and actually processed input tokens, output tokens, per-chain
survival/first answer failure/first capacity rejection, and per-length accuracy.
CPU reports process wall time plus llama.cpp internal prompt-eval and decode time
separately. FPGA reports warm-model request prefill/decode and startup separately.
Latency ratios between representations use only steps where both fit. CPU output
counts are output re-tokenization plus EOS, rather than a generated-ID trace;
FPGA counts actual generated IDs including EOS. Preserve raw timing logs.

CPU process/model-load wall and warm FPGA request latency do not establish a
cross-device speedup. Prefix reuse is disabled, so these costs measure complete
prompt prefill per request, not cached-history serving performance. The two
fixed sequences per length and correlated snapshots limit generalization.

## Board protocol

Initial BOARD_STATUS revision 24 reported v8 ready and unreserved after Claude's
v9d validation. User authorized changing to v9d for this experiment. Reserve the
canonical file before any SSH; verify live idle v8, kernel lock, candidate package
hashes and existing v9d deployment procedure before swapping. Preserve boot,
resident DMA layout, launcher and inactive services. The finite inference worker
holds the kernel lock. Verify resident weights and causal block/300-position
fixtures before and after, with block checks at chain boundaries. Record final
verified v9d identity after the kernel lock is free, release ownership, and close SSH.
The v8 launcher remains unchanged; disabled MVP/full-sweep services are not enabled.

## Development provenance

The first development attempt was interrupted by a source-integrity guard after
24/24 correct requests: a packaging helper was edited while frozen. It is sealed
separately. The second attempt completed 35/36, including one full-history
cross-entity count error. A general instruction to keep entity counts separate
was added and rerun on new development counts. These development observations
are separate from evaluation and do not justify changing evaluation answers.

The revised development run completed 35/36: JSON 18/18, history 17/18, all parsed
and actual CLI input IDs verified. The remaining history error reverted to an
initial count after a distractor update. Before evaluation, the qualification
criterion was fixed as protocol validity and a passing JSON control, not perfect
history semantic accuracy. This preserves history failures as measured outcomes.
12 focused protocol, framing and board-status tests passed.

Manifest provenance note: the copied v12 source manifest retains legacy
maximum_inferences, repeats, and prompt_policy descriptions. The authoritative
v13 schedule is frozen-jobs.json and maximum_records=448: all primary records,
328 executions and120 capacity rejections per matched backend, with no explicit
repeat-control jobs. New history_policy/history_system fields and each frozen
prompt describe the history arm. Do not interpret the legacy236-inference or
12-repeat source descriptions as the v13 execution plan.

## Completed comparison

Both matched backends completed448 records:328 model executions and120 explicit
history-capacity rejections. All protocol/audit gates passed. CPU and FPGA had
identical correctness counts on every length:

| Length (two workloads) | JSON correct/requested | History correct/executed | History rejected |
|---|---:|---:|---:|
|16|32/32|26/32|0|
|32|64/64|29/36|28|
|64|128/128|29/36|92|
|Total|224/224|84/104|120|

JSON delivered accuracy was100%; history conditional accuracy was80.77% on
fitting requests and delivered accuracy37.5% across all224 requested steps.
History fit through step18 in both32/64-step workloads, rejecting step19 onward.
The16-step histories all fit. The history failures comprised19 parsed wrong
answers and one output-budget/extraction failure per backend. Wrong-field
counts were15 status and7 count (three answers wrong in both); entity had zero
errors. JSON had no answer or extraction failures. Full per-chain first failures
and capacity boundaries are retained in comparison-summary.json.

All328 executed input sequences matched frozen IDs and actual CPU CLI IDs.
All327 pairs that both parsed agreed semantically, including shared wrong answers;
this agreement must not be interpreted as accuracy. Raw text matched311/328.
One pair failed extraction on both backends. No values/defaults were repaired.

Complete histories required275,251 input tokens across all requested tasks,
versus28,896 for JSON:9.53x as many, or89.5% fewer with JSON. This is required
input traffic, not an assertion that rejected prompts were processed by FPGA.
The104 common fitting steps used56,290 history tokens versus13,416 JSON tokens
(4.20x). JSON remained129 tokens/request. Prefix reuse was disabled.

Mean latencies on precisely those104 common fitting steps:

| Backend / component | JSON seconds | History seconds | History/JSON |
|---|---:|---:|---:|
|CPU process wall, including loading|3.551|5.028|1.42x|
|CPU internal prompt evaluation|0.834|2.779|3.33x|
|CPU internal prompt+decode|2.038|3.536|1.74x|
|FPGA warm request|7.921|22.107|2.79x|
|FPGA prefill|3.195|18.329|5.74x|

CPU load/startup differs from FPGA warm request setup; these rows do not justify
a cross-device speedup claim. Offline prompt construction/host reducer time is
excluded. Output lengths differ and per-record decode/output counts are saved.
Latency medians/p95, per-length metrics and CSV are included in the sealed data.

The separate CPU4096 diagnostic executed precisely the120 rejected histories:
114/120 correct (27/28 at32 steps,87/92 at64 steps). All six errors changed a
stored missing/error status to ok; counts/entities were correct. This is not a
uniform4096-context rerun of all history tasks. More capacity allowed execution
but did not eliminate answer errors, and accuracy did not decline monotonically
with step count in these fixed reference-history workloads.

All8 causal checkpoints passed, totaling1,328 vectors; worst absolute error was
2.384185791015625e-7. Before/after v9d live/package identity matched. The authorized
swap preserved boot, DMA, launcher, clocks and inactive services. The sealed269-file
v8 package and earlier evidence verified unchanged. Final v9d identity was
recorded ready and ownership released; SSH closed. v9d is left active under its
explicit candidate package, with the original launcher unchanged and MVP/full-sweep services inactive.

comparison-summary.json, paired-comparisons.json and requests-comparison.csv,
frozen inputs/sources and raw CPU/FPGA/board evidence are sealed under the v13
root seal, including independent1554-file CPU and482-file extended-CPU phase
seals. The interrupted development and both completed development variants are
preserved separately. The full system sweep remains stopped.

This supports a bounded systems result: host-managed JSON state keeps prompt
size constant and reduces prefill while improving answer accuracy on these
controlled retention tasks. It does not establish arbitrary-history compression,
closed-loop reasoning reliability, or performance against a prefix-cached history
server. Known v12 workloads and fixed reference replies limit generalization.
