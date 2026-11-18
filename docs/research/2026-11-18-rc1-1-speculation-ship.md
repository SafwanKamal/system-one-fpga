# RC1.1 release check: speculative decoding in the default service (2026-11-18)

Pre-registered in `experiments/rc1_spec_ship/PROTOCOL.md`, written before any board step.
Raw results are in `build/v2/rc1-spec-ship/board/{baseline,spec,rollback,boot}/svc.json`
and `analysis.json`. Deployment details are in `firmware/rc1_spec/README.md`.

## Result: PASS, RC1.1 stays enabled as the default

Each run sent 66 requests: 21 tool queries in three passes (warm prefix reuse, cold, warm
again), plus 3 through `sysone-qwen-fpga --query`.

| Run | Service | Complete | Equal to plain-RC1 baseline | `speculate` | Median latency, run / baseline |
|---|---|---|---|---|---|
| baseline | plain RC1 | 66/66 | n/a | none | 3.29 s |
| spec | RC1.1 just installed | 66/66 | **66/66** | adaptive | 2.33 s (**1.50x**) |
| rollback | `disable`, plain RC1 | 66/66 | **66/66** | none | 3.29 s (1.00x) |
| boot | RC1.1 after a normal reboot, not started by hand | 66/66 | **66/66** | adaptive | 2.08 s (**1.56x**) |

"Equal" covers `generated_ids`, generated text, parsed call, executed tool path and prefix
tokens reused. Latency by pass (baseline → after reboot):
- warm: 2.61 → 1.64 s (1.60x);
- cold prefill: 3.47 → 2.50 s (1.39x).

The cold gain is smaller because prefill is unchanged. The latency ratio covers the whole
request, not only decode.

Rule 4 (boot): new boot `32747938…`. After a normal reboot, `sysone-rc1-init` and then
`sysone-rc1` started on their own with the drop-in active and NRestarts 0. Health was READY
with all 639,446,688 model bytes verified at startup.

The installer was used as it will be in operation: `install`, then `disable` (rollback
drill), then `enable`. The enable and disable restarts each took about 10 s, through the
normal drain path, and every step's probe passed.

## Scope

- Tool queries only (RC1's request type), greedy decoding, one board, one request at a time.
- Fault and refusal paths were not exercised on the board. They leave the session FAULTED
  in both versions, and that logic is shared and covered by the offline wiring tests.
- Not yet in `restore_rc1.py`: after a reflash, run `install_rc1_spec.py install` and
  re-add the update-policy files.
