# Consolidated hardware candidate RC1

Selected candidate: unchanged **v9e FPGA hardware**, Qwen3-0.6B Q8_0 weights,
INT8 block32 matrix activations, BF16 RNE K/V storage, FP32 attention arithmetic,
2,048 total context tokens, eight-token prefill. Decoder/memory clocks remain
125/250 MHz. Firmware identity remains `sysone-qwen-decoder-v9e` so the existing
bitstream, overlay and runtime identity checks agree.

The candidate runtime combines mandatory sealed ABI2 DMA ownership and full
startup weight verification from v16 with v9e candidate5's aligned 64-byte
scratch transfers. The persistent service retains v16's exact-prefix reuse,
batch boundaries, generation/boot/package/clock checks and fault invalidation.
`--verification per-request` and `--no-prefix-cache` provide diagnostic controls.
The combined service **passed bounded board qualification on 2026-11-08**.
See `BOARD_QUALIFICATION.md` and `board-qualification.json` for measured results,
current deployment identity and limitations. The archived package retains its
original pre-qualification README and candidate metadata; qualification is attested
separately without changing the deployed bytes.

## Build and verify offline

From the repository root, with Python 3.11–3.13:

```powershell
.venv/Scripts/python.exe scripts/v2/package_hardware_candidate.py
.venv/Scripts/python.exe scripts/v2/package_hardware_candidate.py --output build/v2/hardware-consolidated-rc1/deployment
```

The first command checks pinned source, historical package, HLS export, routed
bitstream/XSA and timing evidence. The second creates a fresh package and `.tar`
archive; it refuses existing output. No FPGA synthesis or programming occurs.
`candidate.json` pins every hardware source, host module and evidence input.
Large historical artifacts remain in the original `build/v2/` directories.

To regenerate hardware, use the pinned `hls/qwen_decoder_v9e/release.tcl` and
`create_kr260.tcl` with AMD 2025.2 and the historical `S:/` repository mapping.
These historical scripts use fixed build paths: reproduce them in an isolated
checkout, preserving the original build directory. Run export/import consistency,
matrix II, routed setup/hold and bus-skew gates before packaging. A different
bitstream requires a new candidate lock and new board qualification.

## Bounded board qualification

Reserve the **canonical original checkout's** `BOARD_STATUS.json` through
`scripts/v2/board_status.py`; reconcile live state, then mark it changing before
programming. Also hold `/run/lock/sysone-inference.lock` for actual operations.
Follow `HANDOFF.md` and `docs/handoffs/claude-hardware-ownership.md`. This package
contains no automatic deployment, driver replacement, boot or launcher changes.
Its ABI2 driver prerequisite is the existing v16 sealed DMA module. Model loading
and sealing must finish before inference; ABI1 is deliberately refused.

After separately installing the matching v9e overlay/bitstream and package,
use unique result paths on the board:

```sh
sudo python3 "$PACKAGE/scripts/v2/smoke_qwen_fpga_candidate.py" --package "$PACKAGE" --out "$RESULTS/causal"
sudo python3 "$PACKAGE/scripts/v2/qwen_arm_service_candidate.py" serve --package "$PACKAGE" --socket /run/sysone-rc1.sock --ready "$RESULTS/ready.json"
```

The smoke runner and persistent service each acquire the Linux lock themselves;
do not wrap either in a second acquisition. Run the service in a separate terminal,
then send bounded requests:

```sh
sudo python3 "$PACKAGE/scripts/v2/qwen_arm_service_candidate.py" request --socket /run/sysone-rc1.sock --query 'Read /proc/uptime' --out "$RESULTS/request1.json"
sudo python3 "$PACKAGE/scripts/v2/qwen_arm_service_candidate.py" request --socket /run/sysone-rc1.sock --query 'Read /proc/uptime' --out "$RESULTS/request2.json"
sudo python3 "$PACKAGE/scripts/v2/qwen_arm_service_candidate.py" request --socket /run/sysone-rc1.sock --op shutdown
```

Check exact token parity with the cold candidate CLI, cache-off and per-request
controls, cross-conversation resets, ownership changes, context rejection and
long-context fixtures before adopting. Keep full historical sweep STOPPED.
Record actual image, model, clocks and evidence before releasing board ownership.
The previously recorded v9d configuration is the recovery target; verify its live
identity rather than assuming historical state is current.

The original copied `build.json` is retained for provenance. Its
`optimizations.kv_cache_layout` incorrectly says FP32; `candidate.json` supplies
the correct BF16 layout. Do not interpret historical single-prompt timings as
reliability, sustained throughput or semantic long-context quality evidence.
