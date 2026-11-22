# Attention Reclaim C-Sim Exactness Audit Harness

Word-for-word Vitis HLS C-simulation exactness harness for comparing Qwen3-0.6B decoder variants against the `v9h` baseline (`build/v2/dual-port-study/src-s2`).

## Files

- `audit.py`: Driver that hashes sources, caches the baseline dump, serializes Vitis HLS `csim_design` runs on `S:\`, compares dumps word-for-word, and emits a JSON verdict on stdout.
- `testbench.cpp`: Shared C-sim testbench derived from `experiments/dual_port/testbench_s1.cpp`. Supports both `prefill` (batch-8 groups) and `decode` (single-token steps) across all 28 layers, including a deterministic-KV-seeded crossing of the 256-row attention `TILE` boundary.
- `run_csim.tcl`: Reference Vitis HLS Tcl script (per-run Tcl scripts are generated dynamically under `<source checkout>/build/v2/attn-reclaim/gemini/runs/`).

## Usage

```sh
python experiments/attn_reclaim/audit/audit.py \
  --baseline build/v2/dual-port-study/src-s2 \
  --variant build/v2/attn-reclaim/claude/src-<variant> \
  --mode prefill
```

Options:
- `--mode decode|prefill` (default: `prefill`)
- `--drive LETTER` (or `SYSONE_SUBST_DRIVE`; default: `S`): subst drive letter mapped to `--source-checkout`
- `--source-checkout PATH` (or `SYSONE_SOURCE_CHECKOUT`): source checkout root holding `models/` and `build/`
- `--no-cache`: force re-running baseline C-sim instead of reusing `<source checkout>/build/v2/attn-reclaim/gemini/cache/`
- `--no-tile-cross`: run only the 24-position cold prefix without crossing `TILE=256`
- `--out PATH`: also write the JSON verdict to `PATH`
- `--strict-exit`: exit with code `1` when `verdict` is `FAIL`
- `--self-test`: run offline unit tests (dump parsing, comparison, localization, hashing, Tcl rendering)

## Coverage and Limits

- **Cold prefix (`0..23`)**: Starts with the entire KV cache poisoned with BF16 quiet NaNs (`0x7fc0`) and runs the 24 prompt positions from `build/v2/schedule-invariance-audit/meta.bin` (`3` batch-8 groups in `prefill`; `24` single-token calls in `decode`).
- **256-row `TILE` boundary crossing**: Rather than running 250+ full 28-layer Q8 matvec passes in C-sim, `testbench.cpp` deterministically seeds KV rows `24..251` (`prefill`) or `24..254` (`decode`) with finite, non-uniform BF16 values while leaving tail rows `>= 260` (`prefill`) or `>= 258` (`decode`) poisoned with `0x7fc0` NaN. It then runs:
  - `prefill`: one batch-8 group at `position=252..259`, straddling `TILE=256` within a single `cmd=8` call and across both `P=4` passes (`252..255` finish in tile 0; `256..259` carry `run_acc`, `run_max`, `run_total` across tile 0 to tile 1).
  - `decode`: three single-token steps at `255`, `256`, `257`.
- **Compared fields (raw 32-bit patterns)**:
  - `hidden`: `[28, M, 1024]` after every layer
  - `kv`: `[28, 2, 8, M, 64]` packed BF16 cache rows for kept positions
  - `norm`: `[M, 1024]` final RMSNorm output
  - `token`: `[M]` greedy winner over the first `8,192` vocabulary rows
  - `logit`: `[M]` raw IEEE-754 float32 bits of the winning logit
- **Vitis execution**: Runs through `S:\` (or `--drive`, auto-mapped with `subst`) to avoid OneDrive path spaces breaking Vitis C-sim makefiles, and holds both a lockfile and a Vitis process check so only one Vitis job runs at a time.
- **Verification limit (2026-11-21 run)**: Full-decoder 28-layer `csim_design` was not completed in this run (Gemini sandbox blocked direct `S:\`/Vitis access, and the operator full-decoder C-sim was stopped after ~50 min on the first baseline and descoped to a follow-up run); current verified evidence covers `audit.py --self-test` and the operator-executed compiled `attention()` probe (`75,776` FP32 outputs covering decode and batch-8 prefill across `TILE=256`).
