# RC1 defaults and reboot verification — 2026-11-08

**RC1 is the default launcher and automatic boot startup. An actual reboot
passed, and the default inference service is running and READY.**

Use the board's normal command:

```sh
sudo sysone-qwen-fpga --query 'Read /proc/uptime'
sudo sysone-qwen-fpga --health
```

`--out` and `--max-tokens` remain supported. Without `--out`, the flat JSON result
is written to `/var/lib/sysone/rc1-results/last-command-result.json`. The default
uses the persistent RC1 service with startup SHA verification and prefix reuse.
`--no-prefix-cache` forces cold prefill for that request.

## Changes

The original v8 shell launcher was saved byte-for-byte before installing the
RC1 service client at `/usr/local/bin/sysone-qwen-fpga`. The new
`sysone-rc1.service` is enabled for boot and requires `sysone-rc1-init.service`.
The initializer runs after `dfx-mgr.service`, validates pinned files and scratch
reservation, programs the qualified v9e image, loads the pinned ABI2 module,
then loads, seals and verifies all 639,446,688 model bytes. The inference service
then independently verifies the resident model before its readiness gate passes.

Startup source/configuration and both units are in `firmware/rc1_default/`.
The reviewed installer is `scripts/v2/install_rc1_default.py`. Its positional
input is the staged JSON mapping of startup filenames to base64 file bytes;
the exact executed payload and installer are retained with the evidence.
The installed versioned bundle is `/var/lib/sysone/rc1-default-v1`.
The qualified RC1 package remains unchanged at
`/var/lib/sysone/hardware-consolidated-rc1-20261108`.

The old CPU MVP service remains disabled. Historical model, firmware and
qualification packages are preserved. The full benchmark sweep remains stopped.

## Actual reboot evidence

| Check | Result |
|---|---|
| Boot ID before | `43277fd8-b0f4-479c-9b50-c73df5ab2027` |
| Boot ID after | `e887c9d8-df37-494c-b1e5-7b45eac4be0d` |
| Automatic initializer | Passed; started from stock starter firmware and loaded/sealed/verified the pinned model |
| Fresh driver instance | Changed across reboot; new sealed ABI2 generation 2 |
| Default launcher | Five checked generations before reboot, five after; exact prompt/generated-ID/text/call parity across boot |
| Correct live result | Boot-ID requests returned the actual new boot ID |
| Prefix behavior | First request after boot reused zero; identical repeat reused 48 tokens; `--no-prefix-cache` forced zero |
| Post-reboot causal fixtures | **4,112 checks, worst absolute error 0** |
| Final default service | Enabled, active/running, READY; two further launcher requests passed after fixture testing |
| Integrity | All 2,113 package files and eight startup bundle files verified; installed units and launcher match their pinned sources |

The initial post-reboot checks made **no manual initializer or service start**.
They waited for automatic readiness and used the public launcher. After those
checks passed, the service was briefly drained to run the causal fixture suite,
then restored and checked through the same launcher. It remains running.

Automatic initialization took 72.274 s and inference-service startup 3.008 s.
Those are component timings, excluding earlier OS/network boot time. One reboot
was tested; this is not power-loss or repeated-reboot stress qualification.

Four host/Linux tests passed for pinned-file rejection, output/argument
compatibility, failure exit behavior and health-output handling. An independent
local validator rechecked all 12 default-launcher generations, the changed boot
and driver identities, source hashes, model-verification proofs, final service
ownership and all 4,112 causal records. All 75 target evidence files passed
their checksum seal.

## Operation and recovery

The running service intentionally holds `/run/lock/sysone-inference.lock` and
the exclusive DMA inference lease. Reserve the canonical `BOARD_STATUS.json`
for board sessions, then drain with:

```sh
sudo systemctl stop sysone-rc1.service
```

Perform hardware/model work only after it has stopped and released ownership.
Restore the default using `sudo systemctl start sysone-rc1.service` after successful
verification. The initializer preserves an already sealed model only after full
SHA verification and refuses unexpected firmware, active DMA owners or an
unreviewed kernel/module change. Its current module is qualified for
`6.8.0-1036-xilinx`; kernel updates require a reviewed module/pin update.

The original launcher is saved at
`/var/lib/sysone/qualifications/rc1-default-20261108/rollback/sysone-qwen-fpga.original`.
The installer includes a rollback procedure that drains/disables RC1 startup,
restores that launcher and removes only the newly installed units. Restoring the
legacy launcher also requires a deliberate compatible image/runtime rollback;
the old writable-mapping v8 runtime cannot use the current v9e/ABI2 deployment.
No automatic destructive reset or force-kill recovery is installed.

Machine-readable receipt: `boot-startup.json`.
Raw target logs, executed installer/payload, source snapshots, independent
validator and seal: `build/v2/rc1-default-boot-20261108/` in the original checkout.
Remote evidence: `/var/lib/sysone/qualifications/rc1-default-20261108/`.
