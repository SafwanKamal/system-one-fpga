# Batched cold prefill deployed - 2026-10-19

Qwen3-0.6B now completes the same real cold tool command in **66.183s**, down
from **92.031s**: 1.39x faster, 28.1% less elapsed time. Four prompt-token lanes
share each Q8 weight stream. Prefix reuse was explicitly disabled. Model size,
weights, arithmetic and vocabulary did not change.

## Measured command

`Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'.`

The model generated the exact same 35 output tokens (including EOS) as the
baseline. Linux executed `read_linux_file(path="/proc/sys/kernel/random/boot_id")`
and returned `6c80ec1a-e7ae-473f-b169-d54f129615d1`, the unchanged Linux boot ID.
All neural-network arithmetic ran on the FPGA, including FP32 activations and
full 151936-row vocabulary projection. No ARM/host model inference or correction.
Linux tokenizes, schedules hardware commands, validates JSON and executes the tool.

| Measurement | Result |
|---|---:|
| Previous cold command | 92.031s |
| Batched cold command, including initialization and tool execution | 66.183s |
| Batched prefill, including first output projection | 21.119s |
| Subsequent decode | 35.655s |
| Resident full-model SHA256 verification, included in total | 4.732s |
| Prompt / output tokens | 67 / 35 |
| Reused prefix tokens | 0 |
| Prefill groups | 17 (16 groups of 4, one group of 3) |
| Semantic decoder-layer evaluations | 2828, unchanged |
| Matrix-layer weight passes, prefill plus decode | 2828 to 1428 |
| Prefill matrix-layer weight passes | 1876 to 476 |
| Kernel commands | 3630 to 2181 |

Remaining elapsed time includes helper startup, preflight, descriptor writes and
tool/result handling. This is one fixed-command comparison, not a benchmark
sweep, general quality evaluation or worst-case timing guarantee. Latency remains
high for an interactive MVP. Model size was not increased.

## Implementation and checks

`hls/qwen_decoder_v4/qwen_decoder.cpp` holds four activation slots in URAM and
broadcasts one dequantized Q8 weight stream to four parallel matrix products.
Each group completes all 28 layers. Within each layer, tokens append KV and run
attention in increasing position, retaining causality. The last prompt slot feeds
final norm/full-vocabulary argmax. Decode uses the same core with batch size one.

Commands 7/8 handle batched embeddings/layers, 9 selects the final hidden slot,
and 10 dumps a lane for the fixture. Existing CSR addresses and single-token
commands remain unchanged. Runtime: `src/sysone/v2/qwen_fpga_runtime_v3.py`.
CLI: `scripts/v2/run_qwen_fpga_command_v3.py`.

HLS achieved matrix II=3 at 100 MHz: 75104 LUT, 63986 FF, 202 BRAM18K, 343 DSP,
24 URAM. Final routed setup slack +0.833ns, hold +0.010ns. Bitstream and matching
XSA passed. C simulation checked full four-token and partial 1+3 groups, final
norm and argmax. One real-weight board fixture checked all lanes in both
groupings: max absolute error 5.72205e-6 versus an independent offline reference.
That reference is only a fixture; runtime has no host correction. Then ONE cold
real tool command passed. No warm repeat, extra baseline or sweep was run.

## Active deployment

Linux FPGA manager loaded `sysone-qwen-decoder-batch` at 99,999,999 Hz without
reboot/JTAG. The promoted launcher `/usr/local/bin/sysone-qwen-fpga` now points to
`/var/lib/sysone/qwen-fpga-decoder-v4/scripts/v2/run_qwen_fpga_command_v3.py`.

```sh
sudo sysone-qwen-fpga --no-prefix-cache --query "Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'."
```

Next result: `/var/lib/sysone/qwen-fpga-decoder-v4/last-command-result.json`.
Old launcher: package `sysone-qwen-fpga.previous`. Previous fast app/package
remain installed. Batch decoder left active and idle; ARM model service remains
stopped/disabled, R5 unloaded. Same 639446688-byte Q8 model in 39 Linux-owned DMA
segments; no second allocation or reserved-memory increase. Context remains
256 tokens and tool registry permits three read-only procfs paths.

Files/launcher persist on disk; FPGA/model residency is current-boot state. Boot
autostart was not installed/tested. SSH closed after promotion; secret held only
in RAM. No paid compute or commit/push.

## Evidence

`build/v2/qwen-fpga-decoder-v4/deployment-proof.json` records real command,
exact baseline output match, board fixture, installed file hashes, live clock,
idle state, unchanged boot and promotion. Adjacent result JSONs, board queue
receipts, CSim/HLS logs, routed reports, bitstream/XSA and `seal.json` preserve
the implementation and evidence. Prior v2 (100 files) and v3 (80 files) seals
rechecked unchanged. `batch-plan.json` traffic values are estimates, not measured
AXI traffic; measured latency is in the deployment proof.
