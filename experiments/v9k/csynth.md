# v9k B=16 synthesis

**Verdict: DOES NOT FIT.** The v9k decoder estimates use 388 of 288 BRAM18K equivalents and 68 of 64 URAM. Its projected routed decoder uses about 115.5k LUT before adding the shell.

## HLS area and fit

| Design | Hierarchy | LUT | FF | DSP | BRAM18K | URAM |
|---|---|---:|---:|---:|---:|---:|
| v9i B=8 | Total | 137,955 | 243,455 | 666 | 234 | 40 |
| | Attention | 27,267 | 25,306 | 135 | 12 | 8 |
| | Matvec | 63,069 | 187,217 | 396 | 0 | 0 |
| v9k B=16 | Total | 181,088 | 406,345 | 1,056 | 388 | 68 |
| | Attention | 28,319 | 25,320 | 135 | 12 | 8 |
| | Matvec | 102,881 | 349,526 | 786 | 0 | 0 |

| Memory | v9i HLS | v9i routed system | v9k HLS | K26 |
|---|---:|---:|---:|---:|
| BRAM18K | 234 | | 388 (134.7%) | 288 |
| BRAM36 tile equivalents | 117 | 103 | 194 (134.7%) | 144 |
| URAM | 40 | 40 | 68 (106.3%) | 64 |

The BRAM conversion counts two BRAM18Ks per BRAM36 tile and gives an optimistic packing equivalent. Even scaling the 194-tile equivalent by v9i's observed `103 / 117` HLS-to-routed factor gives about 171 tiles, 27 beyond capacity. The four v9k activation banks use 15 URAM each, up from eight per bank. The eight additional URAM in attention bring the decoder total to 68. The matvec hierarchy accounts for 39,812 of the 43,133 added HLS LUT and all 390 added DSP. The top-level dot-output and quantized-input banks are counted outside the matvec XML hierarchy. [v9i route](../v9i/route.md)

### Routed decoder LUT projection

The published v9i routed-to-HLS LUT ratios are `87,772 / 138,765 = 0.633` for the decoder, `19,070 / 27,499 = 0.693` for attention and `40,872 / 63,447 = 0.644` for matvec. The remainder of the decoder gives `27,830 / 47,819 = 0.582`. Applying the hierarchy ratios to the measured paired HLS increases gives `87,772 + 1,052 × 0.69348 + 39,812 × 0.64419 + 2,269 × 0.58199 ≈ 115,469` LUT. Applying the whole-decoder ratio directly gives about 114,542 LUT. The routed v9i shell adds 4,956 LUT, so carrying that shell cost forward puts the two estimates at 120,425 and 119,498 LUT against 117,120 on K26. This is a projection from HLS and the prior v9i route. [v9i route](../v9i/route.md)

### Achieved loop IIs

| Loop | v9i XML loop suffix | v9k XML loop suffix | v9i II | v9k II |
|---|---|---|---:|---:|
| Attention K/V tile loads | `329_3`, `333_4` | `331_3`, `335_4` | 1 | 1 |
| Attention QK score | `388_14` | `390_14` | 1 | 1 |
| Attention score scale / max | `406_18` | `408_18` | 1 | 1 |
| Attention exp / mass | `425_23` | `427_23` | 4 | 4 |
| Attention carried rescale / store | `434_26`, `484_40` | `436_26`, `486_40` | 1 | 1 |
| Attention weighted value | `446_30` / `446_31` | `448_30` / `448_31` | 1 | 1 |
| Matvec loads / unpack | `79_2` / `11_1` | `79_2` / `11_1` | 1 | 1 |
| Matvec packed accumulate | `354_1` | `354_1` | 1 | 1 |
| Matvec reduction | `409_2` | `410_2` | 16 | 16 |
| Quantize max / scales / pack | `103_1` / `117_4`–`117_5` / `129_6` | same | 1 / 1 / 1 | 1 / 1 / 1 |
| RMS sum / apply | `210_1` / `219_3` | `212_1` / `221_3` | 4 / 1 | 4 / 1 |
| RoPE | `244_1` / `245_2` | `246_1` / `247_2` | 2 | 2 |

Both HLS runs estimate a 10.477 ns decoder period (95.45 MHz). The clock and fit of v9k have no implementation or board measurement.

## Batch audit

`make_v9k.py` copies the three audited v9i source files from `build/v2/v9i/src` into this worktree's `build/v2/v9k/src` and sets `B=16`. It checks the source inventory, SHA-256 of each source with normalized line endings, and the exact occurrence count of each patch. It also checks the patched top-level signature and all 14 control ports, including the return port, against v9h `build/v2/dual-port-study/src-s2`.

| Source path | B=16 handling |
|---|---|
| `model_profile.hpp` | `B` changes from 8 to 16. The separate 8 KV heads, dimensions, and eight rotating partial sums per Q8 dot keep their existing values. |
| `qwen_decoder.cpp` activation and results | `activation[B][ACT]`, `dotoutput[B][F]`, `quantized[B][F/32]`, `qscales[B][F/32]` and the two `best_*` arrays scale with B. The existing cyclic and complete partition directives act on the wider arrays. The vocabulary initialization loop covers all B slots. |
| `quantize_activation` | The flattened magnitude and inverse buffers each hold `B*(F/32)` entries. All three traversals use the runtime batch count. The multiplier 8 and terminal quad index 7 refer to the eight four-value quads in a 32-value Q8 block. |
| `matrix_q8.hpp` and `matvec` | The slot loop, packed dot pairs, lane accumulators, scales, results and argmax arrays derive from `TOKENS=B`. Slots 14 and 15 form the final packed dot pair. The eight FP32 partial sums per slot and their reduction tree retain the original summation order. The first B=16 attempt hit an 8,192-bit completion FIFO, above the HLS aggregation limit of 4,096 bits. The corrected source uses one 4,096-bit depth-4 SRL FIFO per weight half. It writes both partial vectors at the same row boundary and reads both before reducing the first row of the pair. The original interleaved row order and smaller-index argmax tie rule are preserved. |
| `attention` | `run_acc`, `run_max` and `run_total` grow from four to eight groups in `[B/P][P]`. The runtime pass loop advances by P=2, with an active-slot mask for a partial pass and a separate causal count per slot. Tile buffers, vector-width literals of eight, and per-pass scratch dimensions still describe the same BF16/FP32 layout. |
| RMS, RoPE, KV and residuals | Norm and RoPE operate on a slot passed by the existing `b<batch` loops. RoPE lookup and KV append use `position+b`. The eight-lane gamma/rotary/load or KV-word constants refer to the memory layout. Residual, projection copy and gate loops traverse the runtime batch. |
| Batch commands and bounds | Cmd 7, 8 and 11 get the count from 32-bit `rows@0x58`. Cmd 12 gets the count from 32-bit `layer@0x48` and retains `rows` as vocabulary rows. Cmd 9 and 10 take a slot through `layer`. The existing checks use B for the allowed count/slot and embedding-list span, actual batch for the result span and context, and unsigned arithmetic for the counters. **CSR fields widened: none.** |

## Run and checks

Vitis HLS 2025.2 used top `qwen_decoder`, part `xck26-sfvc784-2LV-c`, Vivado flow target, an 8 ns clock, default 2.16 ns uncertainty and `config_compile -pipeline_loops 0`. The routed v9i reference used 1 ns uncertainty, so its HLS counts differ slightly from the paired baseline below. The launcher stages each source snapshot with a separate Tcl project and console log, then runs its worker detached.

```powershell
python experiments/v9k/make_v9k.py $original
python experiments/v9k/csynth.py $original
python experiments/v9k/csynth.py --inspect $run
```

Set `$original` to the source checkout and `$run` to the printed run directory. Use `--drive` to select a free drive letter if Y: is occupied. The v9i run completed once in 228.47 s. The initial v9k single-FIFO attempt stopped in pre-synthesis with HLS 214-256 after 94.56 s. The corrected v9k was launched separately with `--design v9k --drive Z:` and completed once in 261.10 s. Both successful arms exited 0. To inspect the baseline directory while omitting the failed attempt, pass `--inspect $baselineRun --design v9i`.

| Evidence | Location under `build/v2/v9k/` |
|---|---|
| v9i and failed single-FIFO v9k | `csynth/20261122T204800797233Z/` |
| Corrected v9k | `csynth/20261122T205044734488Z/` |
| C-sim source and log | `local-check/check.cpp`, `local-check/check.tcl`, `local-check/console.log` |

Each synthesis directory retains `results.json`, per-design `console.log` and source hashes. Successful XML and RTL are in `hls/solution/syn/` below the design name. The two successful designs emitted byte-identical `qwen_decoder_control_s_axi.v` (SHA-256 `b6a91334f8b988ef0a8a563f0367bcca09001e6a123ae9bd6d433ddd66d8a95e`).

The targeted Vitis C-sim passed for batch 1, 9, 15 and 16 on synthetic Q8/attention inputs. It checked FIFO row order, argmax ties, inactive slots and attention across the 256-token tile boundary. Python smoke checks passed for repeat generation, duplicate patch counts, corrupted source and changed reference CSR offsets. The candidate runtime's host prefill method, with mocked hardware commands and B=16 configured, issued the correct embedding-list lengths, `rows` counts and final slot picks at the context boundary, and rejected count 17.
