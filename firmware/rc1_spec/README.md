# RC1.1: lossless speculative decoding in the default RC1 service

Deployed on the KR260 on 2026-11-18. The default command is still
`sudo sysone-qwen-fpga --query ...`. Its answers are bit-identical to plain RC1, and
median latency on the tool queries is about 1.5x lower.

## What is installed

| Path | Content |
|---|---|
| `/var/lib/sysone/rc1-spec-v1/` | `spec_service.py`, `spec_decode.py`, `10-speculation.conf`, `config.json`, `bundle-sha256.json` (this directory) |
| `/etc/systemd/system/sysone-rc1.service.d/10-speculation.conf` | Drop-in that replaces only `ExecStart` with `spec_service.py serve --speculate adaptive --gate-threshold 0.25` |
| `/var/lib/sysone/qualifications/rc1-spec-20261118/events.jsonl` | install, enable and disable events with probe results |

Unchanged: the sealed package `hardware-consolidated-rc1-20261108`, `sysone-rc1-init.service`,
the base `sysone-rc1.service` (including its `ExecStartPost` READY gate), the launcher,
firmware, driver and model. `spec_service.py` imports the sealed RC1 package and
replaces only the decode loop. Each generation result carries `"speculate": "adaptive"` and
a `speculation` block of draft statistics. Plain RC1 results have no `speculate` field.

## Operations (as root on the board)

```sh
python3 /home/ubuntu/rc1-spec-20261118/bundle/install_rc1_spec.py status
python3 /home/ubuntu/rc1-spec-20261118/bundle/install_rc1_spec.py disable   # back to plain RC1
python3 /home/ubuntu/rc1-spec-20261118/bundle/install_rc1_spec.py enable    # RC1.1 again
```

The source is `scripts/v2/install_rc1_spec.py`.
- **enable:** writes the drop-in, restarts the service through the normal drain path, and
  requires READY plus a probe generation that reports `speculate=adaptive`. Any failure
  disables it again automatically.
- **disable:** removes the drop-in, keeping a copy under the qualification directory, then
  restarts and requires a plain probe.

Drain with `systemctl stop sysone-rc1.service` before raw hardware work, as before.

## Evidence

- Kernel exactness: `experiments/schedule_invariance` (C simulation).
- Exactness and speed: `docs/research/2026-11-18-speculative-decoding-qualification.md`,
  181/181 bit-identical across boots.
- Release check: `docs/research/2026-11-18-rc1-1-speculation-ship.md` and
  `experiments/rc1_spec_ship/PROTOCOL.md`. The installed, rollback and after-reboot runs
  were each 66/66 equal to plain RC1.

## Not covered

- Recovery: `experiments/kria_recovery/restore_rc1.py` restores RC1 only. After a
  reflash, run `install_rc1_spec.py install`. Also add the update-policy files: see the
  qualification write-up's operational section.
