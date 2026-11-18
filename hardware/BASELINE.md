# RC1 hardware and runtime baseline — adopted 2026-11-08

**RC1 is the supported KR260 hardware/runtime baseline.** Use it as the reference
for future hardware, runtime and performance changes. Its deployed bytes retain
their versioned `consolidated-rc1`, `v9e` and `candidate` filenames so the existing
qualification and checksums remain valid. [baseline.json](baseline.json) pins the
selection; [BOARD_STATUS.json](../BOARD_STATUS.json) in the original checkout is
the sole live board identity and ownership record.

| Baseline item | Selection |
|---|---|
| FPGA | `sysone-qwen-decoder-v9e`; `hls/qwen_decoder_v9e/` |
| Model | Qwen3-0.6B Q8_0, 639,446,688 bytes |
| Arithmetic | INT8 block32 matrix activations, INT32 dots, FP32 scaling/norm/attention/residuals; BF16 RNE K/V storage |
| Capacity | 2,048 total context tokens, eight-token prefill |
| Clocks | 125 MHz decoder, 250 MHz memory |
| Runtime | Sealed ABI2 ownership, full startup SHA, persistent exact-prefix reuse |
| Installed package | `/var/lib/sysone/hardware-consolidated-rc1-20261108` |
| Boot bundle | `/var/lib/sysone/rc1-default-v1` |
| Default command | `/usr/local/bin/sysone-qwen-fpga` |
| Boot units | `sysone-rc1-init.service` required by enabled `sysone-rc1.service` |
| Kernel/module | Qualified ABI2 module for `6.8.0-1036-xilinx` |

v8 is retained as an immutable historical control, and v9d/v16 is retained as a
recovery path. Existing measurements keep their original version labels. Earlier
Nexys classifier/encoder results and the software capability research remain
separate workstreams.

## Normal use

On the board, after reserving and reconciling the canonical board state:

```sh
sudo sysone-qwen-fpga --health
sudo sysone-qwen-fpga --query 'Read /proc/uptime'
sudo sysone-qwen-fpga --query 'Read /proc/sys/kernel/random/boot_id' \
  --out /var/lib/sysone/rc1-results/boot-id.json --max-tokens 64
```

Without `--out`, the flat JSON result is saved outside immutable packages at
`/var/lib/sysone/rc1-results/last-command-result.json`. `--no-prefix-cache` forces
cold prefill for one request; `--conversation-id` and `--reset-cache` control the
single cache bank. All neural arithmetic runs on the FPGA.

At boot, the initializer waits for the DFX manager, verifies source/firmware and
the 256 MiB `no-map` scratch reservation, programs v9e, loads the qualified ABI2
module, then loads, seals and hashes the pinned model. The service performs its
own full startup verification and must report READY before its systemd readiness
gate passes. An unexpected kernel, image, owner or checksum causes refusal.

```sh
systemctl status sysone-rc1-init.service sysone-rc1.service
sudo journalctl -b -u sysone-rc1-init.service -u sysone-rc1.service
sudo cat /run/sysone-rc1-init/state.json
```

Reserve the canonical board status before board sessions. The running service
intentionally holds the Linux inference lock and DMA lease. Drain it before raw
hardware/model work. Stop requests drain inference without forced SIGKILL; there
is no automatic reset or restart of uncertain hardware. Full historical sweep
remains **STOPPED**.

## Verified baseline evidence

| Qualification stage | Verified result |
|---|---|
| Consolidated hardware/runtime | 8,224 causal checks across bracketing passes, worst absolute error 0; 28 full generations checked, including 18 timed service calls and a 1,454-token prompt |
| Ownership/cache/bounds | Ten driver negative checks, competing-owner rejection, same-model generation 4 → 6, conversation/reset checks and capacity/boundary rejection passed |
| Actual reboot/default launcher | Changed boot and driver identities; automatic model load/seal/full SHA; 12 default-launcher generations checked with exact generated-output parity across reboot |
| Post-reboot hardware | 4,112 causal checks, worst absolute error 0; default service restored, enabled and READY |
| Integrity | 2,113 package files and eight startup bundle files verified |

The causal fixtures cover layer 0 through all 2,048 positions and tile boundaries;
full-model tool generations exercise all decoder layers. These are bounded
development checks on one board and one actual reboot.

In the pre-reboot qualification's six short requests per arm, mean client time
was 5.564 s with per-request SHA/no cache, 3.856 s with startup SHA/no cache, and
3.105 s with startup SHA/prefix reuse. The cached arm includes its first cold
request. For the 1,454-token prompt, persistent client time was 73.827 s initially
and 5.397 s on the identical repeat. Automatic reboot initialization took 72.274 s
plus 3.008 s service startup, excluding earlier OS/network boot time. Preserve
these timing boundaries and do not combine component speedups or relabel older
results as RC1 measurements.

Detailed receipts: [hardware qualification](candidates/consolidated-rc1/BOARD_QUALIFICATION.md),
[reboot/default startup](candidates/consolidated-rc1/BOOT_STARTUP.md),
[qualification JSON](candidates/consolidated-rc1/board-qualification.json),
[startup JSON](candidates/consolidated-rc1/boot-startup.json).
Raw evidence is preserved under `build/v2/hardware-consolidated-rc1-board-20261108/`
and `build/v2/rc1-default-boot-20261108/` in the original checkout.

## Rollback: disable automatic defaults and use RC1 manually

These are operator recovery instructions, not actions performed by adopting this
baseline. Reserve the canonical status, reconcile live identity and mark the
operation before changing the board. Save new results in a fresh evidence path.

```sh
sudo systemctl disable --now sysone-rc1.service
sudo systemctl stop sysone-rc1-init.service
sudo cat /sys/class/misc/sysone_qwen_dma/ownership
```

Require `sealed=1`, `loading=0`, `owner_tgid=0`, `vmas=0` before manual inference.
Stopping the units leaves the current v9e image and model resident. The default
socket client will be unavailable while the service is stopped; use the verified
cold CLI explicitly on this boot:

```sh
P=/var/lib/sysone/hardware-consolidated-rc1-20261108
R=$(sudo mktemp -d /var/lib/sysone/qualifications/rc1-manual-XXXXXXXX)
sudo python3 "$P/scripts/v2/run_qwen_fpga_command_candidate.py" \
  --package "$P" --query 'Read /proc/uptime' \
  --out "$R/request.json"
```

The cold CLI acquires the Linux lock itself. After successful recovery, restore
automatic defaults with `sudo systemctl enable --now sysone-rc1.service` and
check `sudo sysone-qwen-fpga --health`. Record the observed result before releasing
canonical ownership. If automatic startup stays disabled, a later reboot requires
explicit initialization; do not assume model residency survives a reboot.

## Rollback: preserved v9d/v16 hardware/runtime recovery

The following uses previously qualified components; this rollback sequence was
not executed during baseline adoption. First drain/disable RC1 as above, verify
idle/quiescent hardware and preserve the sealed model. The versioned swap helper
checks package integrity, active image, MMIO clients, clocks and DMA-table
continuity and takes the Linux lock itself.

```sh
P=/var/lib/sysone/hardware-consolidated-rc1-20261108
T=/var/lib/sysone/qualifications/rc1-20261108/tools
R=$(sudo mktemp -d /var/lib/sysone/qualifications/rc1-rollback-XXXXXXXX)
echo "$R"
sudo python3 "$T/deploy_hardware_candidate.py" --package "$P" \
  --direction restore --baseline v9d --out "$R/image.json"
V=/var/lib/sysone/benchmarks/persistent-arm-service-v16/bundle-r2
sudo python3 "$V/scripts/v2/qwen_arm_service_v16.py" serve \
  --package /var/lib/sysone/qwen-fpga-decoder-v9d-candidate1 \
  --socket "$R/v9d.sock" --ready "$R/ready.json"
```

Keep that server terminal open. In a second terminal, set `R` to the printed path
and `V` to the same bundle, then verify an explicit v16 request:

```sh
sudo python3 "$V/scripts/v2/qwen_arm_service_v16.py" request \
  --socket "$R/v9d.sock" --query 'Read /proc/sys/kernel/random/boot_id' \
  --out "$R/request.json"
```

Validate the returned live boot ID and save evidence. Use the explicit v16 client
during recovery; the RC1 default service stays disabled. To return to RC1, shut
down the v16 server through its `request --op shutdown` CLI, verify owner/VMAs are
released, swap with the same helper using `--direction candidate --baseline v9d`
and a new `--out` path, then enable/start RC1 and verify health/inference. Record
the actual image, model, clocks and services before releasing ownership; record
unknown if recovery cannot establish them.

The original global v8 launcher remains backed up at
`/var/lib/sysone/qualifications/rc1-default-20261108/rollback/sysone-qwen-fpga.original`.
The installer in `scripts/v2/install_rc1_default.py` contains the exact default
configuration rollback. **Do not restore or invoke the old v8 launcher alone:**
its writable-mapping runtime requires a compatible v8 image/driver/model setup,
whereas RC1 and the v9d/v16 recovery above use sealed ABI2. All old packages,
module copies, boot configuration backups and unsuccessful evidence remain
preserved.
