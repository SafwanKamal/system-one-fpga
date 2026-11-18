# Prefix-cached JSON state versus full reference history on v9d

Same224 semantic tasks/arm and frozen logical v13 inputs:two workloads each at
16/32/64 steps, context1024, output48, greedy Qwen3-0.6B Q8_0. Full history uses
canonical reference assistant replies; actual outputs never change later inputs.
No history truncation. Capacity rejections remain separate from answer failures.
New results are under build/v2/v9d-prefix-comparison-v14. Prior evidence and v8/v9d
packages remain immutable. Full system sweep stays stopped.

## Cache implementation and controls

FPGA uses an experiment-only in-memory tracker, wrapping unchanged runtime_v9d.
Reuse requires an exact token prefix, matching model/kernel/runtime/boot/RoPE
identity and matching physical scratch tag. Each begin rotates the tag through
the existing disabled-cache runtime operation, without reading/writing package
prefix-cache files. Metadata is committed only after complete inference, even
if its answer is semantically wrong: answer accuracy must not bias cache hits.
Exceptions invalidate pending state. At least the final prompt token is rerun
for fresh logits. Reuse rounds down to an eight-token boundary, preserving the
original prefill batching alignment. Physical prefill token/group counters must
prove skipped work. Decode always generates a fresh complete answer.

One active case+representation uses the single physical KV bank. Reset between
cases/arms and before/after causal fixtures. This evaluates uninterrupted
sequential chains, not multiple simultaneous cache-resident conversations.

CPU uses the pinned local llama-server binary and DLLs, CPU-only single slot,
context1024, no context shifting, no KV chunk shifting, cache-ram disabled and
no idle-slot cache. It binds only localhost and is terminated on completion.
Tokenization is checked through its tokenizer endpoint, then exact frozen token
IDs are submitted to the completion endpoint, avoiding CLI file framing.
Raw requests/responses, exact generated IDs, cache_n and prompt_n are saved.
Actual cache_n+prompt_n must equal total prompt tokens. Fresh same-server cold
and cached sequences run serially; the first cached request is forced cold.
These are warm-model request timings, with server startup reported separately.
They should not be confused with v13 CPU process/model-load wall timings.

FPGA uses sealed v13 same-v9d cold controls rather than repeating that full cold
campaign. All328 executed cached generated-ID sequences must match those controls.
New live cold/cached qualification also precedes the FPGA cached run. Comparing
FPGA latency to v13 is across runs with matching boot/image/clocks/package, not
an interleaved same-run cold control. Report this limitation explicitly.

Qualification covers identical and changed prefixes, growing and shortened
histories, near-capacity requests, physical tag invalidation and explicit reset.
CPU cold controls precede a12-request cached sequence. FPGA repeats this live.
16 focused prefix validity/framing/reducer/ownership tests passed. CPU qualification
passed all12 exact generated-ID comparisons and reused2865 tokens;1389 evaluated.
No prompt tuning occurs. Known v13 wrong answers are still errors, not repaired.

## Board and reporting

Canonical BOARD_STATUS revision28 was ready on v9d and unreserved. Codex reserves
before SSH and keeps the physical kernel inference lock for each worker session.
Live preflight, resident-weight verification, before/after causal block/long
fixtures and case/arm boundary fixtures, source hashes and deployment inventories
are required. No reprogramming, launcher change or persistent service enablement.
Verified final identity must be recorded before release; uncertainty retains claim.

Report accuracy/coverage, logical token demand, physically evaluated/reused tokens,
cache hit fractions, warm prefill/decode/wall latency, exact output parity and
per-length/common-fit results. Cached tokens still occupy context and KV memory.
Costs exclude offline prompt construction and host reducer time. Fixed traces,
reference replies and one pinned model limit generalization; no closed-loop claim.

Protocol reference: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
The actual pinned executable response fields were verified locally rather than
assuming current online documentation exactly matched this binary.

## CPU strict-gate finding

All896 records/656 inferences completed and server closed. The original frozen
CPU bit-exact gate failed at final comparison; its attention status is preserved.
16/328 cached token sequences differed from fresh same-server cold controls,
all JSON arm. All16 differences were Markdown fences/whitespace only; parsed
values, parse success and correctness matched in every executed pair. Do not
claim CPU bit-exact validation. Supplemental cold/cold/cache/cache/cold
single-token probes reproduce the output-template switch and retain top-token
log probabilities. The official server README cache_prompt documentation warns
that different prompt-processing/token-generation batch sizes need not produce
bit-identical logits. This is consistent with the observed shape-dependent
change; no semantic repair or rewriting of original evidence occurs.
The offline report records strict CPU failure separately from semantic and
actual-cache-work validation. FPGA retains its strict generated-ID gate.

## Completed results

Both cached backends completed448 records:328 model executions and120 explicit
history overflows. CPU also completed fresh same-server cold controls (896 total
records/656 executions across both modes). All parsed outcomes and accuracy
matched cold controls:JSON224/224, history84/104 fitting requests correct and120
rejected. Per length:16-step histories26/32;32-step histories29/36 plus28 rejects;
64-step histories29/36 plus92 rejects. History still exceeds context at step19
in32/64-step workloads. Cached tokens still occupy positions in the1024 context.

FPGA all328 generated-ID sequences matched sealed v13 cold controls exactly.
CPU312/328 sequences matched exactly;16 JSON-format differences had no changes
in parsed values, parse success or correctness. Its original strict gate remains
failed/attention. comparison-summary.json therefore records passed=false for
all-original-gates, while semantic_and_cache_validity_passed=true. Do not erase
that distinction. No parser repair or data rewriting was used.

Mean request wall latency on precisely104 common fitting steps:

| Backend / mode | JSON seconds | History seconds | History/JSON |
|---|---:|---:|---:|
|CPU same-server cold|0.963|2.327|2.42x|
|CPU cached|0.696|0.711|1.02x|
|FPGA sealed v13 cold|7.921|22.107|2.79x|
|FPGA cached|5.889|6.275|1.07x|

CPU startup/loading is excluded from these new same-server warm request times.
FPGA cold comparison is across matched-identity runs, not interleaved controls;
boot, image/package, clocks, launcher and services matched v13. Decode mean on
FPGA stayed essentially unchanged:JSON4.726s cold versus4.726s cached;
history3.777s versus3.778s. Prefill fell from3.195 to1.163s for JSON and18.329
to2.497s for history. This localizes the improvement to skipped prompt work.

Actually evaluated prompt tokens across all executed cached requests:

| Backend / arm | Logical tokens | Reused | Newly evaluated | Reuse fraction |
|---|---:|---:|---:|---:|
|CPU JSON|28896|21075|7821|72.93%|
|CPU history|56290|50452|5838|89.63%|
|FPGA JSON|28896|20432|8464|70.71%|
|FPGA history|56290|50088|6202|88.98%|

The history row covers104 fitting requests, versus224 JSON requests, so these
all-executed totals are not equal-coverage comparisons. On104 common fitting
steps, FPGA evaluated4144 JSON tokens versus6202 history tokens; logical counts
were13416 versus56290. Required logical traffic across all224 requested tasks
is unchanged from v13:28896 JSON versus275251 history. Rejected inputs do not
contribute fake zero-latency samples or evaluated tokens. KV allocation is fixed
by the hardware profile; lower occupancy is not a measured RAM allocation saving.

All16 causal checkpoints passed (2656 fixture vectors), worst absolute error
2.384185791015625e-7. New live cold/cached qualification12/12 passed on both
backends. Source checks, pinned CPU binaries/DLLs, old seals, before/after v9d
identity/package and v13 baseline identity all verified. No package-cache files,
launcher changes, service enablement or programming occurred. Final v9d verified
ready; reservation released and SSH closed. Full sweep remains stopped.

Data, qualification, CPU formatting diagnostic, original attention status, raw
requests/responses, generated IDs, counters and source snapshots are sealed in
seal.json. CPU also has an independent phase seal. Summaries, CSV and saved
report source are retained. Future work should use these cached results as the
latency baseline, rather than presenting uncached history replay as the only
comparison. The main surviving JSON advantages are bounded context and measured
answer accuracy on these controlled, teacher-forced workloads.
