# RC1.2: v9g image + cost-aware lossless speculation in the default RC1 service

RC1.2 layers on RC1.1. It is a second systemd drop-in, `20-rc12.conf`, on `sysone-rc1.service`:

- `ExecStartPre`: `rc12_image.py up` switches the FPGA from v9e to v9g. The switch takes
  about 2 s. It is idempotent, leaves the DMA residency table unchanged, and reloads v9e if
  the load fails.
- `ExecStart`: `spec_service_rc12.py`. This is the RC1 service on v9g. Each verify pass is
  scored by one batched head scan, and draft lengths come from the cost-aware drafter
  (`drafters.py`, `coef_dev` in `config.json`).
- `ExecStopPost`: `rc12_image.py down` switches back to v9e. v9e stays the resting image, so
  the boot initializer and every other tool are unchanged.

Every emitted token is the engine's greedy token, so outputs are bit-identical to RC1:
- v9g board pilot: 181/181;
- drafter board check: 181/181 (`docs/research/2026-11-19-cost-aware-drafting.md`).

## Operations (root on the board)

```sh
python3 /var/lib/sysone/rc1-2-v1/install_rc12.py status
python3 /var/lib/sysone/rc1-2-v1/install_rc12.py disable   # back to RC1.1 on v9e
python3 /var/lib/sysone/rc1-2-v1/install_rc12.py enable
```

- `/var/lib/sysone/rc1-2-v1/package` is a copy of the sealed RC1 package plus the v9g app
  directory. The sealed package itself is not changed.
- Events are logged to `/var/lib/sysone/qualifications/rc1-2/`.
- Build the tar with `python scripts/v2/package_rc12.py`.
