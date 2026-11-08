# RC1 default launcher and boot startup

The KR260 default command is `sudo sysone-qwen-fpga --query 'Read /proc/uptime'`.
It uses the boot-managed RC1 persistent service, with sealed ABI2 weights,
startup verification and exact-prefix reuse. Existing `--query`, `--out` and
`--max-tokens` options remain supported. Output remains a flat generation record.
Without `--out`, the result goes to
`/var/lib/sysone/rc1-results/last-command-result.json`, outside immutable packages.

`--health` checks service readiness. `--no-prefix-cache` forces cold prefill for
that request. `--conversation-id` and `--reset-cache` control the single cache bank.
The launcher never falls back to a CPU model or an older FPGA runtime.

## Startup sequence

`sysone-rc1.service` is enabled for `multi-user.target`. Its required
`sysone-rc1-init.service` runs after the DFX manager is ready. Initialization:

1. Takes `/run/lock/sysone-inference.lock` nonblocking.
2. Checks pinned startup files, package files, firmware, kernel/module and the
   existing 256 MiB `no-map` scratch reservation.
3. Loads v9e from the stock starter image; an unexpected active image or DMA
   owner causes a refusal rather than replacement.
4. Checks clock/AXI bindings and the routed 125/250 MHz profile.
5. Loads the qualified ABI2 driver, then loads/seals/SHA-verifies every model
   byte. An already sealed model is fully verified before reuse.
6. Writes a boot-specific result at `/run/sysone-rc1-init/state.json`.

The persistent service then acquires the same Linux lock for its lifetime,
claims its sealed inference lease and performs its own full startup SHA.
`ExecStartPost` requires a READY health response with complete verification
coverage before systemd marks startup successful. Prefix state starts empty
after boot or service restart. Stop requests drain inference; systemd does not
escalate them to SIGKILL or automatically reset/restart uncertain hardware.

The boot bundle is `/var/lib/sysone/rc1-default-v1`. It contains the startup code,
configuration and units here, the qualified `.ko` copied from the preserved v16
bundle and a checksum manifest.
RC1's deployed package remains `/var/lib/sysone/hardware-consolidated-rc1-20261108`.
Model source: `/home/ubuntu/sysone-generation/Qwen3-0.6B-Q8_0.gguf`.
The module is qualified for kernel `6.8.0-1036-xilinx`; a kernel change requires
reviewing/rebuilding the driver and updating the versioned pins before startup.

## Operations and recovery

Follow the canonical `BOARD_STATUS.json` reservation protocol for board sessions.
The running service intentionally owns the Linux inference lock and DMA lease.
Drain it with `sudo systemctl stop sysone-rc1.service` before raw hardware tests,
model transitions or programming. `sudo systemctl start sysone-rc1.service`
restores it after a successful check. Initialization leaves the programmed image
and sealed weights resident when the inference service stops.

Useful checks:

```sh
sudo sysone-qwen-fpga --health
systemctl status sysone-rc1-init.service sysone-rc1.service
sudo journalctl -b -u sysone-rc1-init.service -u sysone-rc1.service
```

The migration preserves the original launcher at
`/var/lib/sysone/qualifications/rc1-default-20261108/rollback/sysone-qwen-fpga.original`.
To disable automatic RC1 startup, stop and disable `sysone-rc1.service`, then
stop `sysone-rc1-init.service`. Restore the saved launcher only as part of a
deliberate runtime/image rollback: the old v8 launcher is incompatible with the
currently loaded v9e image and sealed ABI2 driver. Preserved historical packages,
v9d and stock starter recovery images are unchanged. The old CPU MVP service
remains disabled. The full historical benchmark sweep remains stopped.

Reboot validation and the final live identity are recorded separately in
`hardware/candidates/consolidated-rc1/BOOT_STARTUP.md` and its JSON receipt.
