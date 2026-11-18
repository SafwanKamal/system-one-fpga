# Streaming Qwen3-0.6B FPGA decoder deployed - 2026-10-19

The same cold real tool call now completes in **27.430s**, down
from **42.209s**: 1.539x faster and 35.01% less
elapsed time. The complete SSH job took 28.047s, also below 30 seconds.
Linux stayed on boot `6c80ec1a-e7ae-473f-b169-d54f129615d1`.
All model arithmetic remains on the FPGA at 99,999,999 Hz; no ARM/host inference,
FP32 correction, restricted vocabulary or output replay.

## One measured cold command

`Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'.`

The model generated exactly the same 16 tokens as the previous deployment.
Linux executed `read_linux_file(path="/proc/sys/kernel/random/boot_id")` and
returned the actual unchanged boot ID. The prompt's 62 token IDs also match.
No prefix tokens were reused; the model, precision, prompt and wire format
were unchanged. This is an actual decoder-throughput improvement.

| Measurement | Previous compact baseline | Streaming decoder |
|---|---:|---:|
| Cold runtime including initialization and real tool | 42.209s | 27.430s |
| Prefill, including first full-vocabulary projection | 19.579s | 11.825s |
| Subsequent decode | 15.505s | 8.429s |
| Full resident-model SHA verification, included above | 4.699s | 4.747s |
| Vocabulary setup, included above | 1.917s | 1.919s |
| Prompt / output tokens | 62 / 16 | 62 / 16 |
| Reused prefix tokens | 0 | 0 |
| Semantic decoder-layer evaluations | 2156 | 2156 |
| Matrix-layer weight passes | 868 | 868 |
| Kernel commands | 1221 | 1221 |
| Vocabulary rows projected | 2430976 | 2430976 |

All 151936 vocabulary rows were projected for each generated token. Generation
uses the existing compact typed array [function_name,path] and stops at complete
JSON, as in the baseline; it does not wait for EOS. Host processing only parses,
validates and structurally binds the two generated strings to the tool API.
No argument is predicted or repaired on the host.

One complete cold command was run for this candidate. One directed hardware
fixture checked all four lanes plus partial causal groups; max absolute error
5.72205e-6 matches the prior decoder. No warm repeat or benchmark sweep. This is
one fixed-command observation, not a general quality or worst-case deadline claim.

## Decoder change

A backpressured stream now separates contiguous DMA reads, Q8 block unpacking,
flat matrix accumulation across rows, and final row reduction/argmax. The matrix
accumulator achieves II2; the reader supplies blocks every 2/3 cycles and can
stall the pipeline normally. Static eight-register rotation preserves the prior
FP32 accumulation order while eliminating repeated row pipeline drain/refill.
The independent row reducer keeps up at II16. Short, wide FIFOs use SRLs to
preserve block RAM capacity.

HLS: 82553 LUT, 74231 FF, 194 BRAM18K, 453 DSP and 24 URAM. Final routed timing
passed the single 100 MHz target: setup +0.896ns, hold +0.010ns. Final bitstream
and matching XSA passed. The release IP and archive match all 71 synthesized
RTL files (apart from the exporter's explicitly checked simulation-only top
hook), and the same files imported into Vivado also match. The packaging helper
rejects stale exports, changed hardware sources and mismatched compiled profiles.

Full model verification stays enabled. A directed smoke showed direct hashing
of uncached DMA memory took 9.621s on this ARM CPU, so that experiment was dropped
before the cold command. Final software retains the original bounded cached-copy
SHA path (4.747s); it checks every resident byte. No extra model command was run
to sweep hashing methods. Initial/final archive hashes and the guarded two-file
software update are retained in the board receipts.

## Transfer to a larger model

`hls/qwen_decoder_v6/matrix_q8.hpp` is a separate template parameterized by token
lanes and vector capacity, taking matrix dimensions per operation. The same core
passed directed simulation at capacity6144 with 2048, 6144 and 1056 columns,
including vocabulary argmax. These are functional portability checks, not a
larger-model deployment or performance sweep.

`model_profile.hpp` derives hidden/FFN sizes, activation offsets, query/KV widths,
GQA grouping, layers, vocabulary and context. The runtime validates the actual
compiled profile against the weights and derives embedding stride, KV reservation
size, RoPE length and optional untied Q8 output-head offset. The packager reads
expanded constants from the compiled source, so compile-time overrides cannot
silently disagree with its manifest. Unsupported alignment/scratch layouts fail
before hardware access. Manifest/RoPE/model-path inputs are configurable.

A larger model still needs its own weights, shape/memory profile, synthesis/fit
and directed numerical check. The current DMA driver/table limit is 64x16MiB
segments (1GiB); no capacity extension or larger model was deployed. Current
quantization is Q8_0 and head dimension128; other formats need their own verified
unpacker. See `docs/research/2026-10-19-streaming-qwen-decoder-design.md` for the
reusable architecture and explicit boundaries.

## Active deployment

FPGA app: `sysone-qwen-decoder-stream`, left operating and idle. The launcher
`/usr/local/bin/sysone-qwen-fpga` points to
`/var/lib/sysone/qwen-fpga-decoder-v6/scripts/v2/run_qwen_fpga_command_v5.py`.

```sh
sudo sysone-qwen-fpga --query "Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'."
```

This profile always uses cold prefill; `--no-prefix-cache` is accepted for
compatibility. Next result: package `last-command-result.json`. Previous launcher
bytes are retained in package `sysone-qwen-fpga.previous`; old apps/packages remain
installed. The ARM model service remains stopped/disabled and R5 unloaded.
The same 639446688-byte pinned model remains in 39 Linux-owned DMA segments.
No extra model allocation, reserved-memory increase, reboot, JTAG or paid compute.
Files/launcher persist; FPGA/model residency remains current-boot state, with no
boot-autostart workflow installed. SSH closes after promotion; no secret saved.
No commit/push.

## Evidence and reproduction

`build/v2/qwen-fpga-decoder-v6/deployment-proof.json` contains the passing real
command, exact baseline ID equivalence, numerical fixture, live clock/idle state,
unchanged boot, installed file hashes and promotion. Adjacent JSONs, board queue
receipts, `seal.json`, routed reports and bit/XSA retain the evidence.

The correct release flow is `hls/qwen_decoder_v6/release.tcl`: synthesize and
export together into a clean `hls-release` project. Run
`scripts/v2/check_qwen_hls_export_v1.py` before physical synthesis and again with
`--vivado build/v2/qwen-fpga-decoder-v6/vivado` after import. Then use
`create_kr260.tcl`, `package_qwen_fpga_v5.py`, deploy/smoke/run/finish v5.
Separate export of an old implementation directory reused stale RTL during
bring-up; that build was stopped before deployment. The audit rejects it.
Prior v2/v3/v4/v5 sealed artifacts remain unchanged.
