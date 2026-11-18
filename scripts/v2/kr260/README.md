# Working with both boards

As of 2026-10-09 the KR260 revB boots Ubuntu 24.04.2, kernel 6.8.0-1036-xilinx,
Python 3.12.3, with NumPy 2.4.4 in `~/sysone-venv`. SSH is at 192.168.0.239
(DHCP; may change). The 128 GB card provides 114G root storage. The transferred
baseline bundle is extracted under `~/system-one-fpga`. `sysone-v2` is loaded in
slot 0. Deployment checks passed: SYS2 ID 0x53595332, BUILD 0x20801804, clock
71,428,571 Hz for the 75 MHz request, and 64 MiB reserved. Clock and AFI drivers
bound and FPGA manager is operating. The bert-mini-slots4-kr260 image load passed:
11,256,832 bytes at 0x60000000, identical CPU readback in 5 seconds (host path).
PL DDR traffic and encoder checks also passed on 2026-10-09: hidden states are
bit-exact against ImageMachine at 1, 12, 64 and 128 tokens. Encoder clock counts
are 212,682 / 258,357 / 681,140 / 1,386,238 respectively; at the live clock these
are 2.98 / 3.62 / 9.54 / 19.41 ms. Full request times are 2.98 / 3.63 / 9.61 /
19.56 ms; host round trips 4 / 4 / 10 / 20 ms. The matched 300-request subset also passed; results follow below.
A dedicated 64 MiB no-map region at
0x60000000 is verified after FIT regeneration and reboot, with early hooks
installed to preserve it during kernel/initramfs updates. Nexys 4 DDR remains
the verified hardware baseline. Share trained checkpoints, tokenizers, calibration
and integer references; compile a separate DDR image for each board. Images contain
absolute addresses and board-specific tile layouts, so they are not interchangeable.

First real-text request passed on 2026-10-09: "show me flights from boston to
denver tomorrow morning" routes to ATIS, predicts book_flight / atis_flight, and
tags the two cities plus departure date/time. At 11 tokens, encoder 3.56 ms and
request 3.57 ms come from board counters; host round trip 4 ms and CPU heads
16.8 ms are separate host measurements. This is a smoke test, not corpus accuracy.

Out-of-scope smoke test also passed: "how should I build a h-bridge circuit?",
12 tokens, rejected by the CLINC threshold with no specialist head used (oos
p=0.286). Encoder 3.62 ms, request 3.63 ms, host round trip 5 ms, CPU heads 5.1 ms.
Initial bring-up is complete. Matched corpus evaluation completed on both boards; see below.
Keep accuracy and timing measurements separate.

## Matched hardware evaluation (2026-10-09)

The first KR260 evaluation attempt stalled with kernel RCU CPU warnings. Its
cause is not yet confirmed. The runtime bundle has been rebuilt with pre-MMIO
Linux app/driver/clock/reservation checks and full DDR image verification before
RUN. It prints flushed startup stages and rejects stale/absent app or model
state. All 46 relevant tests pass; guarded board execution completed successfully. Reboot
recovery clears volatile FPGA/model state: reload the app with deploy_app.py and
reload the model with the client before evaluating. Do not unload the FPGA while
the stalled client remains active. See rtl/v2/README.md problem 26.

`prepare_eval_suite.py` freezes 50 test requests from each of ATIS, CLINC, MSRP,
multi-segment CLINC, SGD dialogue and SICK (300 total, sampling seed 0). It verifies
both board-image integer encoders and task heads agree on every selected request,
then stores token IDs and cached INT8 goldens. Suite SHA256:
`4f557315887fdc140bc7028ee329038c8ecbf6c207f97a3d5ca57a42fca7c75b`.
The subset scores supervised task heads; automatic routing is not scored here.
These are subset results, not full-test-set accuracy. Multi-segment accuracy counts
segments; some SGD requests have no scored intent, so denominators differ from 50.

Preparation on the laptop, with pinned corpora already present:

```powershell
uv run python scripts/v2/prepare_eval_suite.py
uv run python scripts/v2/package_eval.py
```

The existing 75 MHz Nexys encoder bitstream was programmed through JTAG, and its
11,309,056-byte model image read back exactly. Its frozen run completed: 300/300
bit-exact; mean encoder 10.07 ms over 300 requests averaging 33 tokens, maximum
37.22 ms (longest input 121 tokens). Reports: `build/v2/eval/nexys.json` and
`build/v2/eval/local-kr260.json` (the latter is a CPU reference, not KR260 hardware).
Matched hardware evaluation completed and compared (2026-10-09): both boards
passed 300/300 integer-reference checks. Case-by-case token IDs, hidden-state
hashes, task predictions/logit hashes and accuracy counts match. KR260 runtime
preflight and DDR verification passed after recovery, app reload and model reload.
Mean encoder time: Nexys 10.072 ms at 75 MHz, KR260 5.755 ms at 71,428,571 Hz,
about 1.75x faster overall. KR260 maximum was 18.36 ms (121 tokens); mean input
length was 33 tokens. These are board counter timings, with CPU heads and host
round trips recorded separately. The 16x12 Nexys and 16x32 KR260 variants use the
same trained model and frozen seed-0 subset, not the same hardware configuration.
Reports: build/v2/eval/nexys.json, kr260.json, comparison.json and comparison.md.
Suite SHA256: 4f557315887fdc140bc7028ee329038c8ecbf6c207f97a3d5ca57a42fca7c75b.
Accuracy covers supervised task heads on 50 requests per dataset; automatic
routing and full-corpus accuracy are not scored here.

Matched 300 requests; hidden states, predictions and accuracy counts identical.

| Dataset | Accuracy | Slot F1 | Nexys encoder mean ms | KR260 encoder mean ms | Speedup |
|---|---:|---:|---:|---:|---:|
| atis | 0.980 | 0.963 | 4.295 | 3.646 | 1.18x |
| clinc | 0.920 | — | 3.960 | 3.551 | 1.12x |
| msrp | 0.620 | — | 15.839 | 7.945 | 1.99x |
| multi_clinc | 0.875 | — | 9.744 | 5.223 | 1.87x |
| sgd | 0.909 | 0.622 | 19.293 | 9.720 | 1.98x |
| sick | 0.880 | — | 7.304 | 4.445 | 1.64x |

The adapter connections are independent: KR260 stays on the router, reached by
SSH over laptop Wi-Fi; Nexys RJ45 connects directly to the laptop's Realtek USB
Ethernet adapter (no Nexys IP configuration). KR260 computes through local AXI;
Nexys uses raw Ethernet. Host round-trip and heads timings are recorded separately.

Transfer `build/v2/kr260-eval.tar.gz` to `ubuntu@192.168.0.239:~/`, then run on KR260:

```sh
tar -xzf ~/kr260-eval.tar.gz -C ~/system-one-fpga && cd ~/system-one-fpga && sudo ~/sysone-venv/bin/python scripts/v2/sysone_v2_client.py --kr260 --clock-mhz 71.428571 --image bert-mini-slots4-kr260 eval --suite build/v2/eval/bert-mini-matched.json --verify --report ~/kr260-eval.json
```

The bundle updates the NumPy runtime and client and includes the selected examples,
goldens and corpus provenance. It does not change the FPGA app or model image.
No dataset download or training packages are needed on the board. If the board
rebooted, reload the app and image before evaluating and recheck the live clock.
Retrieve `~/kr260-eval.json` to `build/v2/eval/kr260.json` on the laptop, then:

```powershell
uv run python scripts/v2/compare_eval.py build/v2/eval/nexys.json build/v2/eval/kr260.json
```

Comparison refuses partial/unverified runs, changed suites, different token IDs,
hidden states, task predictions or accuracy counts. It reports accuracy/slot F1
and per-dataset encoder mean, median, p95 and full-request timing. Speedup uses
board counters and operating clocks, with host and CPU heads timing separate.
Comparison JSON and Markdown are written to `build/v2/eval/comparison.*`.

MiniLM KR260 automatic-routing smoke tests passed (owner output, 2026-10-09):

| Request | Route / result | Encoder ms | Request ms | Host round trip ms | CPU heads ms |
|---|---|---:|---:|---:|---:|
| show me flights from boston to denver tomorrow morning | ATIS: book_flight 0.894, atis_flight 0.999; both cities/date/time slots correct | 10.80 | 10.82 | 12 | 34.3 |
| how should I build a h-bridge circuit? | out of scope; CLINC oos 0.355, no specialist head | 10.90 | 10.92 | 12 | 26.2 |
| turn off the lights in the kitchen | HWU: smart_home 0.835, iot_hue_lightoff 0.988; kitchen B-house_place | 10.59 | 10.60 | 11 | 32.1 |
| book me a table for two at an italian restaurant tomorrow evening | SGD: restaurant_reservation 0.983, ReserveRestaurant 0.957; cuisine/date tagged, party size absent, orphan I-time | 11.11 | 11.13 | 12 | 35.9 |

Live clock 71,428,571 Hz; encoder/request times use FPGA counters. CPU heads
and host round trips are separate measurements. These four requests validate
specific routing branches, not corpus-level routing accuracy. SGD routing passed on the restaurant smoke test, but its slots are imperfect:
"two" is untagged and "evening" is I-time without a preceding B-time. Model
quality must be assessed separately from the bit-exact hardware checks.
Custom-intent/document paths have not yet been checked with MiniLM on the KR260.

## MiniLM-L6-v3b hardware evaluation (2026-10-09)

Matched MiniLM hardware comparison completed (2026-10-09): programmed the
existing 75 MHz Nexys encoder through JTAG; 23,035,904-byte MiniLM image
read back exactly in 34 s (host path). Both boards passed 350/350 frozen
integer-reference checks. Per-case token IDs, hidden-state hashes, task-head
predictions/logit hashes and score counts match exactly. Suite SHA256:
f89ce2428293503f0458e98e5f5aebe29e5be08f7f9b3c36012c7d2e5428109e.
Nexys encoder mean 26.441 ms at 75 MHz, maximum 112.36 ms;
KR260 mean 15.139 ms at 71,428,571 Hz, maximum 50.94 ms.
Overall encoder speedup 1.747x. Mean input 28.39 tokens, maximum 123.
Nexys tile 16x12, KR260 16x32; same trained checkpoint and calibration.
Host transport/CPU heads remain separate; this is a seeded 50-request-per-dataset
supervised subset, not full-corpus or automatic-router accuracy.
Reports: build/v2/eval/nexys-minilm.json, kr260-minilm.json and minilm-comparison.*.
Both boards currently have their respective MiniLM image loaded in volatile DDR.
To return to bert-mini, use that board variant's load command; files/reports remain.

Matched 350 requests; hidden states, predictions and accuracy counts identical.

| Dataset | Accuracy | Slot F1 | Nexys encoder mean ms | KR260 encoder mean ms | Speedup |
|---|---:|---:|---:|---:|---:|
| atis | 0.960 | 0.920 | 12.927 | 10.953 | 1.18x |
| clinc | 0.900 | — | 11.954 | 10.783 | 1.11x |
| hwu | 0.920 | 0.659 | 11.674 | 10.718 | 1.09x |
| msrp | 0.640 | — | 45.772 | 21.048 | 2.17x |
| multi_clinc | 0.892 | — | 25.786 | 13.650 | 1.89x |
| sgd | 0.933 | 0.449 | 55.728 | 26.236 | 2.12x |
| sick | 0.820 | — | 21.244 | 12.583 | 1.69x |

MiniLM-L6-v3b KR260 hardware evaluation verified (2026-10-09).

All 350 frozen requests match cached integer hidden states and CPU task-head predictions/logit hashes. Live clock: 71,428,571 Hz.

Encoder mean 15.139 ms; maximum 50.942 ms. Mean input 28.39 tokens; maximum input 123. Timings use FPGA counters.

| Dataset | Accuracy | Scored intents/pairs | Slot F1 | Encoder mean ms |
|---|---:|---:|---:|---:|
| atis | 0.960 | 50 | 0.920 | 10.953 |
| clinc | 0.900 | 50 | — | 10.783 |
| hwu | 0.920 | 50 | 0.659 | 10.718 |
| msrp | 0.640 | 50 | — | 21.048 |
| multi_clinc | 0.892 | 139 | — | 13.650 |
| sgd | 0.933 | 45 | 0.449 | 26.236 |
| sick | 0.820 | 50 | — | 12.583 |

50 requests per dataset, seed 0; supervised task heads. Automatic routing and full-corpus accuracy are not scored.
The 350-case MiniLM suite includes HWU and differs from the 300-case bert-mini suite; their mean times are not a matched model comparison.
Nexys MiniLM hardware evaluation passed on the same suite; see matched comparison above.

Suite SHA256: `f89ce2428293503f0458e98e5f5aebe29e5be08f7f9b3c36012c7d2e5428109e`.

Hardware image load/readback and 1/12/64/128-token checks now pass. Encoder
times are 9.75 / 10.90 / 26.07 / 52.99 ms at 71,428,571 Hz. Evaluation stopped
after ATIS/CLINC due to a missing HWU slot-label lookup; corrected client uses
the active head labels. CPU scoring replay passed all 350 cases. Transfer and
extract `build/v2/kr260-client-fix.tar.gz` to update only the client, then rerun
the frozen evaluation. That rerun completed 350/350 bit-exact and was independently
verified after importing its report. Full bundle is also updated.

Preparation completed: both image variants match on all 350 frozen test requests
(50 each: ATIS, CLINC, HWU, MSRP, multi-CLINC, SGD, SICK; seed 0), including
integer hidden states and task-head integer/float logits and labels. The embedding
head also passed a separate exact smoke comparison. Suite SHA256:
`f89ce2428293503f0458e98e5f5aebe29e5be08f7f9b3c36012c7d2e5428109e`.
Ready archive: `build/v2/kr260-minilm.tar.gz` (23,967,804 bytes). Every archived
file was read back and matched to its workspace source by SHA256; no training
checkpoint is included. Hardware MiniLM load/check/evaluation subsequently passed; see results above.

The existing `sysone-v2` bitstream supports hidden width 384, head dimension 32,
six layers and a 128-token window. Compile the trained `minilm-l6-v3b` checkpoint
with its existing calibration; no RTL rebuild is needed:

```powershell
uv run --group train python scripts/v2/oos_threshold.py --name minilm-l6-v3b --extra hwu
uv run --group train python scripts/v2/compile_image.py build --name minilm-l6-v3b --board kr260 --base 0x60000000 --suffix=-kr260 --reuse-calibration
uv run --group train python scripts/v2/prepare_eval_suite.py --image minilm-l6-v3b --peer-image minilm-l6-v3b-kr260 --per-dataset 50 --seed 0 --out build/v2/eval/minilm-l6-v3b-matched.json
uv run python scripts/v2/package_eval.py --image minilm-l6-v3b-kr260 --suite build/v2/eval/minilm-l6-v3b-matched.json --include-model --out build/v2/kr260-minilm.tar.gz
```

Refresh/copy `decision.json` to the KR260 image directory if retuning after the
image build. CLINC and HWU thresholds are both 0.480 after the corrected router
statistics run. The full CLINC+HWU router rejects 29.2% of CLINC OOS test queries;
supervised task-head scores do not measure this automatic routing behavior.

Image: 23,087,104 bytes, SHA256
`0cf8d009e9fc55367a3fa53e853a9b498227daf91aa669206e4389ec5931eea1`,
base `0x60000000`, tile 16x32. Token IDs are at `0x61700000`; maximum result
ends at `0x6170d000`, within the reservation ending at `0x64000000`. Image CRCs
and reused calibration were verified. The source 16x12 image previously passed
1,400 chains against IntEncoder with zero hidden/head mismatches.

The transfer bundle includes the NumPy runtime, model image/manifest/program,
decision rule, original model tokenizer, provenance and cached evaluation suite.
It contains no checkpoint or training dependencies. Extracting it updates files;
loading the model into DDR is a separate command. MiniLM FPGA measurements passed; these commands reproduce the run after transfer:

```sh
tar -xzf ~/kr260-minilm.tar.gz -C ~/system-one-fpga
cd ~/system-one-fpga
sudo ~/sysone-venv/bin/python scripts/v2/sysone_v2_client.py --kr260 --image minilm-l6-v3b-kr260 load
sudo ~/sysone-venv/bin/python scripts/v2/sysone_v2_client.py --kr260 --image minilm-l6-v3b-kr260 check --tokens 1 12 64 128
sudo ~/sysone-venv/bin/python scripts/v2/sysone_v2_client.py --kr260 --image minilm-l6-v3b-kr260 run --dataset auto "show me flights from boston to denver tomorrow morning"
sudo ~/sysone-venv/bin/python scripts/v2/sysone_v2_client.py --kr260 --image minilm-l6-v3b-kr260 eval --suite build/v2/eval/minilm-l6-v3b-matched.json --verify --report ~/kr260-minilm-eval-fixed.json
```

The client uses the live clock automatically. If the board rebooted, reload the
FPGA app before loading the model. The bert-mini files and reports are retained;
switching back requires its `load` command because the two images share the DDR base.
Nexys uses the original `minilm-l6-v3b` image; its MiniLM hardware run passed
on this same frozen suite, enabling the verified comparison above.

| Target | Client location / transport | Image tile | Initial encoder clock | Hardware status |
|---|---|---|---|---|
| Nexys 4 DDR | Windows laptop / raw Ethernet | 16 x 12 | 75 MHz | bert-mini verified |
| KR260 | ARM Linux / AXI via `/dev/mem` | 16 x 32 | 71.428571 MHz observed | bert-mini bit-exact at 1/12/64/128 tokens |

Use Nexys for regression and resource-constrained experiments; use KR260 for wider
compute and later longer-window studies. Start KR260 with the existing 128-token
bert-mini model. Change clock, parallelism or buffers only after a bit-exact baseline.
The updated KR260 client reads the live PL0 clock during preflight. An explicit
`--clock-mhz` must agree with it; use deployment's `clock_hz` divided by 1,000,000.
Report encoder/request clock counters separately from host wall time.

## First boot (owner at the board)

1. Follow the [official KR260 Ubuntu boot guide](https://xilinx.github.io/kria-apps-docs/kr260/linux_boot/ubuntu_24_04/build/html/docs/intro.html)
   and obtain the matching Kria image through [Ubuntu's AMD downloads](https://ubuntu.com/download/amd).
   Use the Kria image rather than a generic ARM installer. Flash a microSD card with
   an SD reader, checking the selected card because flashing replaces its contents.
2. Connect the USB UART/JTAG cable for console access and connect the primary PS
   Ethernet port, Ethernet 1 on J10C, to a network with DHCP. See the
   [KR260 interface map](https://docs.amd.com/r/en-US/ug1092-kr260-starter-kit/Interfaces).
3. Insert the prepared card and use the kit's 12 V, 3 A power supply. Complete the
   image's first-login steps. Follow the boot guide's firmware compatibility checks
   if it does not boot; record the installed firmware before changing it.
4. Record `cat /etc/os-release`, `uname -a` and `ip -br address`. Enable SSH if needed
   using the image's supported setup. From Windows, verify `ssh <user>@<board-ip>`.
5. Copy this repository (or `src/`, `scripts/v2/`, and the required exports) to the
   board. Run `python3 scripts/v2/kr260/doctor.py`; save the JSON with experiment logs.
   This only reads Linux information; it does not map registers or write DDR.

No training environment is needed on the ARM. Use a Python virtual environment with
NumPy for inference. Python must be >=3.11 for this project; check the image's Python
version first. When root is needed for `/dev/mem`, run the venv's Python explicitly.

## Vivado on the laptop

**Project creation now passes (2026-10-08):** after installing Kria device support,
Vivado 2025.2 applied the PS preset, validated the block design and generated the
wrapper and `build/v2/kr260/sysone_v2_kr260.xpr`. The full 32-lane design now routes.
100 MHz fails setup WNS -0.497 ns; hold WNS is +0.002 ns. The same routed design
passes an 80 MHz timing ceiling (setup +2.003 ns, hold +0.002 ns, no failing or
unconstrained endpoints), with 99,783 LUTs, 49,624 registers, 606 DSPs, 59 BRAM
tiles and 18 UltraRAMs. `validate_runtime_clock.tcl` produces the checked export
and clock profile for a Linux runtime request of 75 MHz. It does not change RTL,
placement, routing or timing exceptions. The XSA PS preset remains 100 MHz;
this export requires Linux's lower runtime clock, verified before MMIO.
See `build/v2/kr260-runtime-clock.log` and `timing-100mhz.rpt` for the failed target.
Hardware app deployment, DDR readback and encoder verification passed on
2026-10-09. Review local-board shadowing,
initial clock FREQ_HZ metadata and HP0 AWUSER/ARUSER width warnings before building.

The local Vivado 2025.2 probes on 2026-10-08 found no installed xck26 device parts.
Modify the Vivado installation to include Kria SOMs and Starter Kits device support
(K26, Zynq UltraScale+ MPSoC) first.
KR260 board files were initially absent too; an official Board Store checkout is
now available under `build/v2/board-store` and is picked up by the script. To recreate
that checkout on another machine (or install Kria KR260 through Vivado Store):

```powershell
git clone --depth 1 --filter=blob:none --sparse https://github.com/Xilinx/XilinxBoardStore.git build/v2/board-store
git -C build/v2/board-store sparse-checkout set boards/Xilinx/kr260_som boards/Xilinx/kr260_carrier
```

Then:

```powershell
vivado -mode batch -source scripts/v2/kr260/create_project_kr260.tcl
# After the block design validates:
vivado -mode batch -source scripts/v2/kr260/create_project_kr260.tcl -tclargs build
```

The script recreates its generated project under `build/v2/kr260/`. It produces a
bitstream and XSA when built. Validate PS preset, AXI interfaces, reset, interrupts,
address map and timing on this installed tool version. The design registers are at
0xA0000000; the memory master uses HP0, so its CPU memory mapping must be uncached.
Simulation targets live in `simulation/v2/Makefile`: `encoder-kr260`, `kr260-vectors`,
and `kr260` (Verilator is not installed in the current Windows PATH).

## Linux integration before the first encoder access

The actual Ubuntu boot partition uses `image.fit` and `boot.scr.uimg`, with no
extlinux configuration. The boot command line includes `cma=800M`. Inspect the
FIT components and `/usr/share/flash-kernel/its/image-kria.its` before preparing
a boot reservation; account for CMA placement. Existing `.bak` files were
generated by the OS and are not yet verified as project recovery artifacts.

Once `~/sysone-boot/kr260-reserved.dtb` is prepared from the revB image with only
the 64 MiB no-map reservation, run `python3 scripts/v2/kr260/prepare_reserved_fit.py`.
This writes `~/sysone-boot/image-sysone.fit`, `image-sysone.original.fit` and a JSON
report. It verifies every source/candidate image hash, preserves other payloads,
FIT configuration choices and metadata, and refuses unrelated DTB changes or
signed FITs. It does not install or reboot. Keep the source snapshot and report
for recovery; verify the source hash still matches the live FIT before installation.
Boot validation and a persistent kernel-update hook are separate remaining steps.

**Reservation boot verified (2026-10-08):** the candidate was installed and the
board rebooted successfully. The live DT has `sysone@60000000` with `reg` and
`no-map`; `/proc/iomem` reports `60000000-63ffffff : reserved`. Recovery copy:
`/boot/firmware/image.fit.sysone-original`. Kernel-update persistence remains
pending; the one-time FIT patch may be replaced by flash-kernel regeneration.

Persistent setup is prepared in `install_memory_hooks.sh`: it installs an early
`00-sysone-reserved-memory` hook into kernel postinst and initramfs post-update
directories. `patch_kernel_dtb.py` modifies the installed kernel's revB DTB before
FIT generation, saving original DTBs under `/var/lib/sysone/dtb-backups/<version>/`
by SHA256. Package-delivered DTBs are intentionally patched; kernel and initrd
contents, flash-kernel functions and ITS templates remain managed by Ubuntu.
The helper is idempotent, rejects wrong-board/overlapping reservations, and fails
when a new kernel has no expected DTB. Install with sudo, inspect printed hook
order, then test a FIT regeneration and reboot before declaring persistence
verified. Removing the hooks alone does not restore already patched source DTBs;
restore their matching backup and rebuild the FIT to undo the reservation.

**Normal regeneration verified (2026-10-08):** `update-initramfs -u -k
6.8.0-1036-xilinx` ran the hook before flash-kernel; the newly installed FIT's
revB DTB retains the exact reservation and no-map. A reboot of this regenerated
image also passed: live DT and iomem retain the reservation on kernel
6.8.0-1036-xilinx. A future new-kernel installation has not yet been exercised.
Missing tuner-firmware and blank standalone-DTB
lookup warnings did not prevent successful ITS-based image construction.

The existing driver expects a dedicated 64 MiB region at 0x60000000. The board above
has this reservation verified; stock Linux does not provide it. Confirm a boot-time
reserved-memory node with `no-map` for that range, or implement a DMA-buffer-backed
driver and use its physical allocation instead. A runtime PL overlay alone does not
reserve ordinary RAM already allocated by Linux. Do not run `load` against stock RAM.
The current RUN descriptor holds 32-bit addresses despite the 40-bit AXI bus; all
image and scratch addresses must stay below 4 GiB.

Package the generated bitstream with a device-tree overlay derived from the XSA and
the metadata appropriate for the installed OS. AMD's
[Vivado accelerator example](https://xilinx.github.io/kria-apps-docs/creating_applications/2022.1/build/html/docs/vivado_accel_example.html)
describes `.bit.bin`, `.dtbo` and `shell.json`; use the installed OS/tool versions'
flow rather than copying an unrelated app's device tree. Once packaged, use the
OS's `xmutil`/FPGA-manager flow. Record `sudo xmutil listapps` before switching apps.
The installed Ubuntu package was inspected on 2026-10-08:
`/lib/firmware/xilinx/k26-starter-kits/` contains `k26_starter_kits.bit.bin`,
`k26_starter_kits.dtbo` and `shell.json` with `shell_type: XRT_FLAT` and
`num_slots: "1"`. The live base DT exports `fpga_full`, `amba` and `zynqmp_clk`.
The custom application's overlay and clock configuration passed board checks
on 2026-10-09. The implementation, packaging and boot memory reservation are complete.

`sysone-v2.dts` is prepared from the Vivado 2025.2 SDTGen output for the current
block design (hardware-only preview XSA under build/v2). It includes the PL0/PL1
fabric clock nodes and the generated AFI port configuration, plus the register
mapping. Ubuntu has `xilinx_fclk` and `afi-fpga` drivers; its PL0/PL1 clocks were
reported at 99,999,999 Hz before deployment. The overlay requests the design's
nominal 100 MHz in the source template. Packaging substitutes the runtime profile's
75 MHz request for the checked lower-clock build. SDTGen's PS preset estimate
remains 99,999,001 Hz; the Linux clock uses
its own oscillator description and rounding. Recheck the live clock after
loading and use that rate for elapsed-time calculations. The current host polls
DONE, so the generated interrupt property is omitted. `shell.json` matches the
installed application's metadata. Devices are added directly under the existing
amba bus, following AMD's KR260 overlay layout; a new nested bus can prevent
dynamic device creation. The DTS compiles with dtc without warnings. Overlay application,
AFI driver binding, clock activation and the SYS2/BUILD register reads passed
hardware verification on 2026-10-09 at 71,428,571 Hz. Subsequent encoder checks
verified PL DDR traffic and bit-exact output for 1/12/64/128-token seeded chains.
Recheck this overlay against the final XSA if the block design changes.

After a passing final hardware export, run
`uv run python scripts/v2/kr260/package_app.py` on the laptop. This requires the
implemented bitstream, timing/utilization reports and a final XSA containing the
same bitstream. It converts the bitstream with bootgen, compiles the overlay,
records SHA256 hashes and creates `build/v2/kr260-app.tar.gz`. It never installs
or loads the app. Package creation passed on 2026-10-08 after lower-clock validation;
the final XSA's bitstream matches, bootgen conversion succeeds, and final SDT
clock IDs, AFI configuration and register mapping match the prepared overlay.
The final SDT's 100 MHz PS preset is explicitly overridden by the runtime overlay.

The archive includes `deploy_app.py`, intended for `sudo python3` on the board.
It verifies payload hashes, the live boot reservation and iomem before installing
the app and calling xmutil. Existing differing app files are preserved by refusing
replacement. After load it requires the FPGA manager to be operating, the clock
and AFI drivers bound, and enabled PL0 within the requested/validated clock range
before reading SYS2 and BUILD. This bundle requests 75 MHz and refuses above 80 MHz.
It performs no encoder or DDR writes. Direct workspace SSH currently lacks key
authentication, so the owner must transfer/run the bundle in their authenticated
terminal. If app loading fails, the original starter package remains available:
`sudo xmutil unloadapp; sudo xmutil loadapp k26-starter-kits`.

Transfer `build/v2/kr260-app.tar.gz` to the board, then run this single line:

```sh
mkdir -p ~/sysone-kr260-app && tar -xzf ~/kr260-app.tar.gz -C ~/sysone-kr260-app && sudo python3 ~/sysone-kr260-app/deploy_app.py ~/sysone-kr260-app/sysone-v2
```

Require ID `0x53595332`, BUILD `0x20801804`, and a valid reported live clock before
the image load below. Archive contains no model image and the helper writes no DDR.

## Compile and transfer the baseline

On the laptop, reuse the original calibration and preserve its Nexys image:

```powershell
uv run --group train python scripts/v2/compile_image.py build --name bert-mini-slots4 --board kr260 --base 0x60000000 --suffix=-kr260 --reuse-calibration
uv run python scripts/v2/compile_image.py show --name bert-mini-slots4-kr260
```

Transfer `export/v2/image/bert-mini-slots4-kr260/` and
`export/v2/chain/bert-mini-slots4/tokenizer.json` with `src/` and `scripts/v2/`.
New manifests record `model_name`; board variants copy `decision.json` when present.
Retain the manifest, image SHA-256, bitstream, tool version and clock with each run.
If thresholds are retuned, rebuild/copy the decision file for each variant too.

After Linux memory and the PL application are configured, on the ARM:

```sh
CLOCK_MHZ=$(sudo awk '$1 == "pl0_ref" {print $5 / 1000000}' /sys/kernel/debug/clk/clk_summary)
sudo ~/sysone-venv/bin/python scripts/v2/sysone_v2_client.py --kr260 --clock-mhz "$CLOCK_MHZ" --image bert-mini-slots4-kr260 load
sudo ~/sysone-venv/bin/python scripts/v2/sysone_v2_client.py --kr260 --clock-mhz "$CLOCK_MHZ" --image bert-mini-slots4-kr260 check --tokens 1 12 64 128
sudo ~/sysone-venv/bin/python scripts/v2/sysone_v2_client.py --kr260 --clock-mhz "$CLOCK_MHZ" --image bert-mini-slots4-kr260 run --dataset auto "show me flights from boston to denver"
```

Require exact image readback and exact hidden states before evaluating real corpora.
The host checks tile shape, dimensions and scratch-region capacity against the BUILD
register before writes. Then run `eval --verify` with the same dataset subset/seed on
both boards. Only after that build `minilm-l6-v3b-kr260` with the same command pattern.
Keep accuracy, bit-exactness, board clocks, host path, resource use and timing slack
as separate experiment fields. Never substitute an estimated clock for a measured build.
