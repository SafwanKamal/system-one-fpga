# RC1.1: ship lossless speculative decoding in the default RC1 service

Written 2026-11-18, before any board step. This follows the speculative decoding
qualification (`docs/research/2026-11-18-speculative-decoding-qualification.md`): all
rules passed, with 181/181 bit-identical cases.

## Change

- **New bundle `/var/lib/sysone/rc1-spec-v1`:** `firmware/rc1_spec/` contains
  `spec_service.py` and `spec_decode.py`, byte-identical to the qualified
  `experiments/spec_service` copies, plus `10-speculation.conf`, `config.json` and a
  SHA manifest.
- **Drop-in:** `/etc/systemd/system/sysone-rc1.service.d/10-speculation.conf`
  replaces only `ExecStart`, with `spec_service.py serve --speculate adaptive
  --gate-threshold 0.25`. It keeps the same socket and ready file.
- **Unchanged:** the sealed package, init unit, base unit file, `ExecStartPost` readiness
  gate, launcher, firmware, driver and model.
- **Installer:** `scripts/v2/install_rc1_spec.py` (install, enable, disable, status).
  - Enabling requires the READY gate, then a probe generation that reports
    `speculate=adaptive`.
  - Any failure removes the drop-in and requires plain RC1 to come up READY with a
    plain probe.

## Board sequence (one board, RC1 running throughout except restarts)

1. **baseline:** `svc_check.py` against the installed plain RC1.
2. **install:** install and enable, then `svc_check.py` (**spec**).
3. **rollback drill:** disable, then `svc_check.py` (**rollback**), then enable again.
4. **reboot** through the normal boot path. Then `svc_check.py` (**boot**), with no manual
   start.

`svc_check.py` runs 21 tool queries (the qualification's set) × 3 passes:
- warm1, with prefix reuse;
- cold, with `reset_cache` on every request;
- warm2.

It then runs 3 queries through `sysone-qwen-fpga --query`, for 66 requests in total.
Only queries already proven to complete are used, because an error leaves the RC1
service FAULTED until it restarts.

## Decision rules (`analyze_ship.py`)

1. All 66 requests complete in each of the four runs.
2. For spec, rollback and boot, every request equals the baseline in `generated_ids`,
   generated text, parsed call, executed tool path and prefix tokens reused.
3. Every request in baseline and rollback reports no `speculate` field. Every request in
   spec and boot reports `adaptive`.
4. **Boot:** new boot ID, ExecStart is the bundle's `spec_service.py`, NRestarts=0 before
   and after, and health READY with 639,446,688 verified bytes.
5. **Latency:** median per-request client-time ratio (baseline / run) is at least 1.10 for
   spec and for boot.

PASS on all five: RC1.1 stays enabled as the default. Any FAIL: disable it (plain RC1)
and record why.

## Limits

One board. Tool queries only, the RC1 service's only request type. No concurrency
(RC1 serves one request at a time). Refusal or fault paths are not exercised, because
they leave the session FAULTED in both versions, and their logic is shared code that
the offline wiring tests cover.
