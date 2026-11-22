# V9J decoder HLS synthesis

V9J keeps D3's dual weight ports and four-token attention pass (`P=4`). It uses the FTZ policy from Gemini's published `xmul_hls.hpp` for query × key and softmax mass × value. The generator checked every one of the 14 AXI-Lite control pragmas against v9h, including `model_b@0x70` and the return port. A changed CSR offset and duplicate or missing patch points were rejected before writing sources.

V9J met the score and value II=1 requirement. It increased decoder HLS area by **49,614 LUT and 128 DSP**. The projected routed decoder alone uses **133.3k LUT**, above the K26's 117,120-LUT capacity.

## HLS area

| Hierarchy | D3 LUT | V9J LUT | D3 FF | V9J FF | D3 DSP | V9J DSP | D3 BRAM18K | V9J BRAM18K |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Decoder total | 157,308 | 206,922 | 266,946 | 283,099 | 826 | 954 | 246 | 246 |
| Attention | 46,586 | 96,200 | 48,797 | 64,950 | 295 | 423 | 24 | 24 |
| Matvec | 63,069 | 63,069 | 187,217 | 187,217 | 396 | 396 | 0 | 0 |

Both attention RTL hierarchies have **56 instantiated FP32 `fmul` cores**, counted from the emitted Verilog and cross-checked against the instance tables. D3 places the bank in `attention`. V9J places it in the carried-accumulator rescale pipeline. At each replaced site the RTL-generation log records 64 FP32 multipliers for D3 and 64 unsigned 24 × 8 integer multipliers for V9J. These are per-loop generation counts.

## Routed LUT estimate

The D3 decoder estimate is `0.63 × 157,308 = 99,104` LUT. The entire HLS LUT increase is in attention, so applying the 0.69 attention ratio to the 49,614-LUT increase gives a projected **34,234 routed LUT increase**, for **133,338 LUT** in the V9J decoder. Estimated routed attention is 32,144 LUT for D3 and 66,378 LUT for V9J. Both ratios come from the v9i hierarchy. This is an extrapolation from HLS, with no V9J implementation run. [v9i route](../v9i/route.md)

## Run

Both designs use Vitis HLS 2025.2, top `qwen_decoder`, part `xck26-sfvc784-2LV-c`, an 8 ns clock, Vivado flow target and `config_compile -pipeline_loops 0`. The worker stages independent source snapshots and runs the two syntheses serially in a detached process. Both exited 0. D3 took 234.27 s and V9J took 299.54 s. Both runs reported an estimated Fmax of 95.45 MHz for the decoder. The successful launch uses absolute Tcl paths through a temporary drive alias. An earlier launch stopped at `open_project` in both arms because Vitis resolved the relative project path outside the workspace.

```powershell
python experiments/v9j/make_v9j.py $original
python experiments/v9j/csynth.py $original
python experiments/v9j/csynth.py --inspect build/v2/v9j/csynth/20261122T194358279077Z
```

Set `$original` to the checkout containing the generated study sources. Pass `--gemini-worktree` to the generator if the peer checkout is outside the coordinator's standard directory layout. The paired run's `results.json`, console logs, XML and RTL are under `build/v2/v9j/csynth/20261122T194358279077Z/`. Its source snapshots have these SHA-256 hashes.

| Source | SHA-256 |
|---|---|
| D3 `qwen_decoder.cpp` | `14331cd624593542403bf0c856257b43a24ed5c89e5f1db8165a502454f270c6` |
| V9J `qwen_decoder.cpp` | `8d36fcb54c3fb382eda6fb7edfee9eb2f9315b6d63db900bc5fe608e1c7b60bf` |
| V9J `xmul_hls.hpp` | `c7cea7557d056a87ffbdd0a356de81b1db44d0b2756349e898f690a5f3794ee5` |

The copied header is byte-identical to the blob in Gemini's published commit `ecc56d22ecd56104e06e2036cb28040152358e91`.

## Attention schedule

| Pipelined loop | Vitis loop name or source line | D3 II | V9J II |
|---|---|---:|---:|
| Load key tile | `VITIS_LOOP_329_3` | 1 | 1 |
| Load value tile | `VITIS_LOOP_333_4` | 1 | 1 |
| Pack query | line 374, flattened | 1 | 1 |
| **Query × key score** | `VITIS_LOOP_388_14` | **1** | **1** |
| Scale scores and find max | `VITIS_LOOP_406_18` | 1 | 1 |
| Compute and sum softmax masses | `VITIS_LOOP_425_23` | 4 | 4 |
| Rescale carried accumulator | `VITIS_LOOP_434_26` | 1 | 1 |
| **Softmax mass × value** | line 446, flattened | **1** | **1** |
| Normalize and write output | line 475, flattened | 1 | 1 |
| Save accumulator for next tile | `VITIS_LOOP_484_40` | 1 | 1 |

In the synthesis log, the score loop's scheduled depth went from 27 to 25 cycles and the value loop's from 10 to 8. Both loops achieved the required II of 1.
