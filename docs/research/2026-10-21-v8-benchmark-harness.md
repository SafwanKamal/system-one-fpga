# v8 baseline harness implementation

The finite harness is separate from the sealed deployment. Source:
`scripts/v2/run_v8_benchmark.py`, protocol: `src/sysone/v2/v8_benchmark.py`,
packager: `scripts/v2/prepare_v8_benchmark.py`, SSH launcher:
`scripts/v2/v8_benchmark_ssh.py`. Focused tests: `tests/test_v8_benchmark.py`.

Snapshot and local board receipts are under `build/v2/v8-baseline-v1/`.
The board destination is `/var/lib/sysone/benchmarks/v8-baseline-v1`, with
`results/requests.jsonl`, individual intent/result files, `status.json`, and
pre/post fixture and deployment identity records. The systemd unit is a single
finite execution named `sysone-v8-baseline-v1`; it is not enabled at boot and
does not recur. It continues if SSH disconnects. Do not submit the sweep twice.

Order: pre-fixture, 12 development chains x six arms x up to four steps,
30 historical command generations, 360 fixed-work requests, 100 scoped application
cases, 24 held-out chains x six arms x up to 16 steps, post-fixture and summaries.
Maximum 3,082 model requests plus board fixtures. Context exhaustion shortens
individual chain arms. No hidden retries and no automatic prompt adaptation.

Read-only deployment means no source/package/model/bitstream/launcher replacement,
no reboot, no overlay reload, no real tool reads, and no persistent prefix-cache
writes. Normal inference necessarily writes scratch/KV memory. The benchmark
holds the shared inference lock for its campaign to exclude competing requests.

Operational commands after authentication:

```
systemctl status sysone-v8-baseline-v1
cat /var/lib/sysone/benchmarks/v8-baseline-v1/results/status.json
journalctl -u sysone-v8-baseline-v1
```

Do not abruptly stop/reset hardware after a timeout; inspect status and let any
in-flight operation finish. The runner stops the campaign on hardware/runtime
failure and preserves intent records. Incorrect model outputs continue through
the simulator without substituting gold values.

## Declared implementation scope

- Fixed input lengths use token-ID padding within the user message, with actual
  frozen token sequences and three padding variants; no semantic quality claim.
- History/state experiment uses a two-entity count simulator with set/add/copy,
  conditional updates, missing/error events and explicit status. No real tools.
- Model outputs are proposals committed verbatim to simulator state; the simulator
  does not verify semantic correctness. Gold state is a separate scorer only.
- Compact state uses `A=value/statusID B=value/statusID` with explicit units and
  codebook. Compact output is `statusID entity integer` plus newline. Fields have
  finite domains; variable-length strings are outside this initial protocol.
- Full history is never truncated. Capacity failures are distinct from semantic
  and format failures. Every independent step reprefills at position zero.
- Unsupported file prompts measure acceptance/nonacceptance; invalid or truncated
  output is never called a correct refusal. No tools execute in this benchmark.
- Cold-call time includes runtime/tokenizer setup and resident weight verification;
  outer harness wall time additionally includes process launch. Persistent setup
  is logged separately. CPU timings are process observations, not system-wide
  power measurements. Energy is unmeasured.
- The original boot-ID text is retained, but benchmark generation is scored rather
  than executing the read; this is not a repetition of complete tool-execution latency.
- Oracle-state diagnostics, paired confidence intervals, plots, CPU baselines and
  broader task coverage remain follow-up work. Raw traces permit later analysis.

Protocol, schema and development tasks freeze before execution. Poor development
performance is retained and does not trigger tuning on held-out chains. This is
an initial milestone study, not evidence of arbitrary workflow reliability.
