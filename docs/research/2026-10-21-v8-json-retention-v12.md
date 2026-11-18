# Fresh paired16/32/64-step CPU/FPGA retention evaluation

This bounded experiment evaluates the frozen v10-r3 status-copy instruction on
fresh JSON-state retention sequences, using v11-r2 corrected CPU file framing.
It is separate from closed-loop reasoning and the full system sweep. All new
results live at `build/v2/v8-json-retention-v12`; previous evidence is immutable.

## Cases and inference contract

The six sequences cover mixed and long-gap workloads at16,32,64 steps. Seeds
202610211300–305 resample all initial and successful-observation counts and
vary entity orientation. The32-step long-gap case retains an error status;
the other long-gap cases retain missing. Successful refreshes, no observations,
distractor updates, missing/error preservation and final recovery are covered.
There are224 primary requests plus12 exact first/last-input repeat controls per
backend. State/query identities are checked against earlier evaluations and
development, independently of prompt wording. Repeated snapshots within this
experiment remain intentional and are reported separately from distinct inputs.

The host reducer advances state from trusted simulated observations. Model
answers never change the world state. Both entities' current count and status
are supplied in JSON each request. The instruction, tolerant parser and scorer
are unchanged. No defaults, value repair, host answer prefill or arithmetic
evaluation substitutes for a generated answer. Closed-loop is excluded.

CPU and FPGA receive identical frozen129-token inputs and48-token output budgets
within the unchanged256-token context. CPU writes one extra file-framing LF to
compensate for llama.cpp removing one LF, and logs/verifies every actual CLI
input token. FPGA independently tokenizes the same logical prompt and verifies
the full list before prefill. Both run to EOS or output budget, without accepting
an early parseable prefix. Inter-request prefix reuse remains disabled.

Pinned Qwen3-0.6B Q8_0 and greedy CPU settings match earlier qualifications.
FPGA uses the original runtime copied from the sealed v8 package, including its
INT8 block32 activation arithmetic. Cross-backend normalized semantic agreement
is distinct from raw text or generated-token identity. Exact generated-ID
reproducibility is checked within FPGA repeat pairs.

## Shared board protocol

The first canonical status read showed Claude holding a reservation for v9c
hardware testing. CPU preparation/execution proceeded offline; no board access
occurred under that reservation. After Claude recorded v8 restored and released
ownership at revision16, Codex reserved the board for this finite experiment.

Live preflight under `/run/lock/sysone-inference.lock` verified the restored v8
image/package, launcher, boot,125/250MHz clocks, DMA layout, idle services and
absence of competing inference/R5 activity. Only a separate benchmark bundle
was uploaded. The transient finite unit is `sysone-v8-json-retention-v12`, with
remote evidence at `/var/lib/sysone/benchmarks/v8-json-retention-v12`. The MVP and
full-sweep units remain inactive. No reprogramming or deployment writes occur.

The process holds the kernel lock throughout, verifies resident weights during
startup, and checks causal single/batch fixtures before inference, after each
sequence (including repeats), and after the complete run. Source/input hashes
are rechecked at sequence boundaries. Deployment and live identity must match
before/after; a verified observation must be recorded before releasing the
canonical reservation. Unknown failures retain ownership for reconciliation.

## Reporting and limits

Report primary and repeat denominators separately, per-chain first failure,
longest uninterrupted correct run, survival at8/16/32/64, per-status correctness,
distinct-input accuracy, actual token-ID alignment, semantic and text agreement,
FPGA repeat IDs, causal fixtures and before/after identity. The CPU cold process
time includes model loading and cannot support a direct FPGA speedup claim.

The same snapshot can recur because a queried field did not change. Neither
duplicate snapshots nor exact-repeat controls are independent reliability trials.
There are only two fixed workload sequences per length. Because the host carries
the sufficient current state,64 steps do not establish a64-turn model context
window, lossless conversation retention, or model-driven error propagation.

37 focused tests passed before freezing. Tests independently replay every
observation and expected snapshot, check freshness against v10/v11, verify
unchanged prompt identity and exact repeats, inject wrong replies to prove they
cannot rewrite later state, and retain the CPU file-framing and board-ownership
regressions. Actual CPU tokens are verified from verbose CLI logs on every
request; earlier nominal-only CPU token records are not reused as parity proof.

## Completed results

All gates passed on 2026-10-21. Each backend completed 224/224 primary requests
and 12/12 repeat controls correctly, with no parse failures. Both mixed and
long-gap sequences survived their full length without a first failure.

| Chain length | Workloads | CPU primary correct | FPGA primary correct |
|---|---|---:|---:|
| 16 | Mixed and long-gap | 32/32 | 32/32 |
| 32 | Mixed and long-gap | 64/64 | 64/64 |
| 64 | Mixed and long-gap | 128/128 | 128/128 |

Each backend passed all 177 distinct primary inputs. Primary status results were
ok 87/87, missing 75/75 and error 62/62. All 57 queries whose target had not been
updated for at least eight steps passed. These counts include correlated
snapshots and must not be interpreted as independent reliability trials.

All 236 actual CPU prompt-ID sequences matched their frozen inputs and the FPGA
input IDs. Every logical input was 129 tokens. All 236 normalized CPU/FPGA answers
agreed. Raw generated text matched on 205/236 pairs; independently parsing all
31 differing pairs after removing Markdown fences showed identical JSON values.
The differences were whitespace and optional fences, not status/count changes.
All 12 FPGA repeat pairs reproduced exact generated token IDs; CPU repeat text
also matched in all 12 pairs.

All eight causal checkpoints passed (128 fixture vectors), with worst absolute
error 7.152557373046875e-7. Source integrity passed throughout. The local 269-file
v8 baseline seal and earlier benchmark seals verified unchanged. Before/after
live identity and deployment inventory matched, including package, image, boot,
launcher, clocks, DMA and inactive services. SSH closed and the reservation was
released at canonical status revision 20, after recording verified ready status.
The full sweep remains stopped; there was no reprogramming.

Evidence is sealed under `build/v2/v8-json-retention-v12/seal.json`, with an
additional independent CPU-phase seal. `paired-summary.json` contains gates and
per-chain/status/age metrics; `paired-comparisons.json` and CSV retain every pair;
`repeat-checks.json`, raw CPU/FPGA outputs, frozen inputs, causal fixtures and
board evidence preserve the audit trail.

This establishes a matched CPU/FPGA baseline for supplying compact, host-managed
JSON state through 64 workflow steps under a fixed input budget. It does not
establish arbitrary conversation retention, closed-loop error recovery, a
64-turn model context, superiority over full history, or general task accuracy.
