# v8 baseline v1 protocol diagnosis

The initial campaign was interrupted after 44 completed development requests and
one further intent. No historical, fixed-work, application or held-out requests
were reached. Raw traces, prompts and original scores remain unchanged.

To stop without interrupting active FPGA work, the benchmark process group was
first suspended. The FPGA idle bit was then observed twice before terminating
only those suspended benchmark processes. The idle control register was 14;
Linux boot remained e9728928-307d-485b-b40b-63fa29d9296d. No bitstream, model,
overlay or launcher was replaced. See the local diagnostic quiesce receipt.

## Findings

1. **Framing bug in the evaluation protocol.** All 24 enum outputs in the stopped
   trace end with EOS and have a valid three-field record without a newline.
   v1 requires the newline, so every one is rejected. A candidate EOS-aware
   parser accepts them only at a real terminal boundary. It must not accept a
   streaming numeric prefix, e.g. `0 A 4` before the next digit arrives.
2. **Framing is not the whole problem.** Of those 24 records, only one matches the
   expected semantic result under a post-hoc per-step diagnostic. The prompt's
   example `0 A 12` is frequently echoed as `0 B 12` or `0 A 12` despite unrelated
   actual values. JSON arms often emit labeled text rather than JSON arrays.
3. **One exact semantic answer is rejected for format.** The first JSON-state
   request emits `status: ok\nentity: B\nvalue: 69`, while the required representation
   is `["ok","B",69]`. This is a format error, not evidence that the underlying
   arithmetic failed on that request.
4. **CPU controls reproduce these behaviors.** The same pinned Q8 model, exact
   original prompts, greedy decoding and disabled thinking reproduce all six
   first-step textual responses in llama.cpp on CPU. This strongly implicates
   prompt/model behavior rather than an FPGA-specific failure. CPU arithmetic
   differs from the FPGA's block32 activation arithmetic, so this is not a
   general proof of numerical equivalence or hardware correctness.
5. **The model can produce arrays.** A literal-output CPU control returns
   `["ok", "A", 4]`. A clearer arithmetic/JSON control produces valid JSON but an
   incorrect number (73 instead of 69). Format adherence and task correctness
   need separate qualification; merely relaxing the parser is insufficient.

The test harness should have gated the long campaign on successful protocol
qualification, rather than automatically advancing after development failures.
The v1 negatives are diagnostic artifacts, not a valid comparison of sustainable
context or compact-state benefit. Invalid outputs leave simulator state unchanged,
so later recorded steps cannot be turned into a repaired rolling chain by
post-hoc rescoring.

## Repairs prepared and next gate

`src/sysone/v2/v8_benchmark_protocol_v2.py` implements a candidate EOS-aware enum
parser with regression tests. It does not modify the frozen v1 parser, snapshots,
deployed software or recorded results. Together with the original harness tests,
17 focused tests pass.

A revised benchmark must use a new version and output directory. Before any long
run: freeze unambiguous state schemas and output rules; evaluate prompt examples
on development only; verify exact records across the task families on CPU; run a
small paired FPGA control; separately gate framing/semantic quality; and require
an explicit qualification artifact before historical/fixed/held-out phases.
No long campaign has been restarted.

Evidence: `build/v2/v8-diagnosis-v1/diagnosis.json`, CPU stdout/stderr/prompts,
copied 44-request JSONL, and `board/results/00-quiesce/`. An attempted additional
FPGA diagnostic upload failed on local file preparation before any new diagnostic
inference. Its queue and failure receipt are retained; it is not counted as a
hardware or model failure.
