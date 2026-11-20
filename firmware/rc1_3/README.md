# RC1.3: v9h image + cost-aware lossless speculation in the default RC1 service

RC1.3 layers on RC1.1. It is a second systemd drop-in, `20-rc13.conf`, on `sysone-rc1.service`:

- `ExecStartPre`: `rc13_image.py up` switches the FPGA from v9e to v9h. The switch takes
  about 2 s. It is idempotent, leaves the DMA residency table unchanged, and reloads v9e if
  the load fails.
- `ExecStart`: `spec_service_rc13.py`. This is the RC1 service on v9h. Each verify pass is
  scored by one batched head scan, and draft lengths come from the cost-aware drafter
  (`drafters.py`, 7-coefficient v9h cost model `coef_v9h` in `config.json`).
- `ExecStopPost`: `rc13_image.py down` switches back to v9e. v9e stays the resting image, so
  the boot initializer and every other tool are unchanged.

Every emitted token is the engine's greedy token, so outputs are bit-identical to RC1
(v9h board pilot 37/37 in plain and speculative modes, `docs/research/2026-11-19-dual-weight-port-study.md`).
The package copy's `registers.json` is the v9h map (`model_b` at 0x70, scratch at 0x7c).

Enabling RC1.3 moves RC1.2's drop-in `20-rc12.conf` aside (to
`/var/lib/sysone/qualifications/rc1-3/rc12-dropin`); disabling RC1.3 restores it, so disable
returns to RC1.2 if it was enabled, else to RC1.1.

## Operations (root on the board)

```sh
python3 /var/lib/sysone/rc1-3-v1/install_rc13.py status
python3 /var/lib/sysone/rc1-3-v1/install_rc13.py disable   # back to RC1.2 (or RC1.1)
python3 /var/lib/sysone/rc1-3-v1/install_rc13.py enable
```

- `/var/lib/sysone/rc1-3-v1/package` is a copy of the sealed RC1 package plus the v9h app
  directory. The sealed package itself is not changed.
- Events are logged to `/var/lib/sysone/qualifications/rc1-3/`.
- Build the tar with `python scripts/v2/package_rc13.py`.
