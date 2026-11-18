# Faster Qwen3-0.6B FPGA tool-command deployment — 2026-10-18

Deployed `sysone-qwen-decoder-fast` at 99,999,999 Hz, keeping Linux on the same
boot `6c80ec1a-e7ae-473f-b169-d54f129615d1`. Every model operation remains on the FPGA with pinned Q8_0
weights and FPGA FP32 arithmetic. No ARM/host model forward pass, hidden-state
correction or output-token replay is used. Linux validates and executes the tool.

## Measured result

Same request/model/prompt/full vocabulary and real tool read:
`Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'.`

| Execution | Seconds | Speedup vs original cold |
|---|---:|---:|
| Original 50 MHz, instrumented baseline | 232.991 | 1.00x |
| New 100 MHz, cold prefix cache | 92.031 | 2.53x |
| New 100 MHz, cached identical prompt | 44.580 | 5.23x |

Cold latency fell 60.5%. Cold and cached runs generated
identical 35-token outputs (including EOS), matching the baseline. Both executed
`read_linux_file(path="/proc/sys/kernel/random/boot_id")` and returned the actual,
unchanged Linux boot ID. Both projected all 151936 vocabulary rows per output
step. This is one fixed-command engineering comparison, not a benchmark sweep,
general quality result or worst-case deadline bound. Latency remains too high for
an interactive target; batching prefill/weight reuse is the next substantial lever.

The baseline spent 205.774s in decoder blocks and 17.554s in vocabulary projection.
The new cold run spent 74.054s and
8.201s respectively. Combined changes were
measured together; no ablation/frequency sweep was run.

## What changed

- Retimed the decoder for one 100 MHz target (previously 50 MHz).
- Reduced the Q8 matrix loop initiation interval from four cycles to three.
- Loaded each KV head through explicit 32-word AXI bursts into UltraRAM, then
  reused it for both grouped query heads. HLS reports eight URAMs for buffering.
- Added guarded persistent KV prefix reuse and per-command timing counters.

Routed setup slack is +1.927ns; hold slack +0.010ns. The final bitstream and XSA
passed routed timing. The two-token real-weight hardware fixture retained max
absolute errors 2.145767e-6 and 6.854534e-7; norm/argmax C simulation also passed.
The Linux FPGA manager loaded this image while Linux/networking stayed live.
No JTAG, reboot, paid compute, commit/push or benchmark sweeps were used.

## Prefix reuse

The cached run reused 66 of 67 prompt-token KV entries. It recomputed the final
prompt token and generated every output token anew on the FPGA, processing
35 input tokens/980 layer calls.
Cold processing used 101 input tokens/2828 layer calls.

Cache identity includes Linux boot, overlay/DMA instance inodes, model weight
hash, kernel bitstream hash, runtime source hash, RoPE hash and model-manifest
hash. A 32-byte ownership tag at reserved scratch offset 0x80 changes before each
request, invalidating old metadata on failures. Metadata commits atomically only
after successful model/tool completion. Ordinary non-cached runtime construction
(e.g. the fixture) clears the tag. Causal common-prefix matching can reuse shared
instructions across different requests; the measured warm result is specifically
an identical-prompt repeat. No partial-prefix quality/performance claim is made.
The final prompt token is always recomputed to reconstruct its hidden activation.
The full resident model hash is still verified each invocation.

## Using this deployment

On the KR260, for the current Linux boot:

```sh
sudo sysone-qwen-fpga --query "Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'."
```

Add `--no-prefix-cache` to force fresh prompt processing. The launcher now points
to `/var/lib/sysone/qwen-fpga-decoder-v3/scripts/v2/run_qwen_fpga_command_v2.py`.
Next output: `/var/lib/sysone/qwen-fpga-decoder-v3/last-command-result.json`.
The old launcher bytes are preserved as `sysone-qwen-fpga.previous` in that
package, and the original 50 MHz app/package remains installed for rollback.

The fast image remains loaded and idle after both commands. R5 is unloaded; the
ARM model service remains stopped/disabled. The same 39 DMA segments hold the
639446688-byte pinned Q8 model. No second model allocation was needed. Context
remains 256 tokens; registry remains the three allowed read-only procfs paths.
Files/launcher persist on disk, but FPGA/model residency and prefix state are
current-boot state; no boot autostart/reboot workflow was installed or tested.

## Model size and capability before lock

A larger model is plausible but not yet supported or proven better in this system.
The separate model-envelope note assesses 1.7B Q4 and recommends treating tool ABI
and model/timing profile as separate versioned contracts:
`docs/research/2026-10-18-qwen-model-envelope-before-lock.md`.
Targeted fine-tuning/distillation of 0.6B can be considered before paying the
latency cost of a larger model. That training was not performed in this speed task.

## Evidence and reproduction

`build/v2/qwen-fpga-decoder-v3/deployment-proof.json` contains baseline, cold,
cached, hardware-smoke, deployment, installed-file hashes, idle state and boot ID.
See `baseline-profile.json`, `real-command-result.json`, `warm-command-result.json`,
`board/results/00*` through `07*`, routed reports, bitstream/XSA and `seal.json`.
HLS source is `hls/qwen_decoder_v3/qwen_decoder.cpp`; software runtime is
`src/sysone/v2/qwen_fpga_runtime_v2.py`. New build/package/deployment helpers end
in `_v2.py`; previous sealed artifacts remain unchanged. Package archive SHA256:
`91264d139f1abb2855889f0a07fa8f98fe83aa3d968d139a2d9f7703e6441ae0`.
The board login was closed after promotion; credentials were retained in RAM only.
