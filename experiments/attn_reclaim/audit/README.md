# Attention Reclaim C-Sim Exactness Audit Harness

Word-for-word Vitis HLS C-simulation exactness harness for comparing Qwen3-0.6B decoder variants against a baseline (`v9h` `build/v2/dual-port-study/src-s2` or `v9i` `build/v2/v9i/src`).

## Files

- `audit.py`: Driver that hashes sources, snapshots and hashes `meta.bin` once per audit into an immutable subst-relative fixture, caches the baseline dump, serializes Vitis HLS `csim_design` runs on `S:\`, compares dumps word-for-word per position, derives optional `groups` metadata, and emits a JSON verdict on stdout.
- `testbench.cpp`: Shared C-sim testbench derived from `experiments/dual_port/testbench_s1.cpp`. Supports both `prefill` (batch-`N` groups, `N in {8, 16}`, default `8`) and `decode` (single-token steps) across all 28 layers, including a deterministic-KV-seeded crossing of the 256-row attention `TILE` boundary. Preserves the original `results.json` schema (`mode`, `tile_boundary_crossed`, `tile_boundary_method`, `positions`, `tokens`, `kv_nan_values`, `elapsed_seconds`).
- `run_csim.tcl`: Reference Vitis HLS Tcl script (per-run Tcl scripts are generated dynamically under `<source checkout>/build/v2/attn-reclaim/gemini/runs/`).

## Usage

Matched batch size (default `--batch 8`):

```sh
python experiments/attn_reclaim/audit/audit.py \
  --baseline build/v2/dual-port-study/src-s2 \
  --variant build/v2/attn-reclaim/claude/src-<variant> \
  --mode prefill \
  --batch 8
```

Cross-batch comparison (`v9i` at `--batch 8` vs `v9k` at `--batch 16` over the same cold prefix positions):

```sh
python experiments/attn_reclaim/audit/audit.py \
  --baseline build/v2/v9i/src \
  --variant build/v2/v9k/src \
  --mode prefill \
  --baseline-batch 8 \
  --batch 16 \
  --no-tile-cross
```

Options:
- `--mode decode|prefill` (default: `prefill`)
- `--batch 8|16` (default: `8`): prefill group size `N` (default `8` preserves byte-identical testbench behaviour and dumps to the original batch-8 harness)
- `--baseline-batch 8|16` (optional, defaults to `--batch`): override the baseline run's batch size so a batch-8 baseline (`v9i`) and a batch-16 variant (`v9k`) can be compared in one invocation
- `--drive LETTER` (or `SYSONE_SUBST_DRIVE`; default: `S`): subst drive letter mapped to `--source-checkout`
- `--source-checkout PATH` (or `SYSONE_SOURCE_CHECKOUT`): source checkout root holding `models/` and `build/`
- `--no-cache`: force re-running baseline C-sim instead of reusing `<source checkout>/build/v2/attn-reclaim/gemini/cache/`
- `--no-tile-cross`: run only the cold prefix positions (`0..n-1`) without crossing `TILE=256`
- `--out PATH`: also write the JSON verdict to `PATH`
- `--strict-exit`: exit with code `1` when `verdict` is `FAIL`
- `--self-test`: run offline unit tests (dump parsing, per-position comparison, localization, hashing, `N=16` argument handling, position grouping, Tcl rendering, and subst-drive `cwd`)

## Comparing When Group Boundaries Differ (Per-Position, Not Per-Group)

`testbench.cpp` groups the `n` prompt positions from `meta.bin` (`n=24` in `build/v2/schedule-invariance-audit/meta.bin`, or any `n` such as `32`) into `prefill` chunks of size `min(N, remaining)`:
- At `--batch 8` (`n=24`): 3 groups `[0..7]`, `[8..15]`, `[16..23]` (or 4 groups `[0..7]..[24..31]` when `n=32`).
- At `--batch 16` (`n=24`): 2 groups `[0..15]`, `[16..23]` (or 2 groups `[0..15]`, `[16..31]` when `n=32`).

Even though group boundaries differ, `testbench.cpp` indexes every output buffer (`hidden`, `kv`, `norm`, `token`, `logit`) by the global kept position index `pidx = pos_to_idx[position]` (`0..M-1`), not by group or lane index. `audit.py`'s `compare_dumps()` therefore compares every field **per prompt position** (token by token) across the two runs and reports any mismatch by `(layer, position_index, position, element/word_in_row)`.

When comparing `--baseline-batch 8` against `--batch 16` in `prefill`, pass `--no-tile-cross` (`audit.py` rejects mixed-size `prefill` with tile crossing enabled before cache lookup or simulation): with tile crossing enabled, batch-8 runs `252..259` (`M = n + 8`) while batch-16 runs `248..263` (`M = n + 16`), so the two runs would not cover the same position set.

## Coverage and Limits

- **Cold prefix (`0..n-1`, `n=24` in `meta.bin`)**: Starts with the entire KV cache poisoned with BF16 quiet NaNs (`0x7fc0`) and runs the `n` prompt positions from `meta.bin` grouped by `--batch N` in `prefill`, or `n` single-token calls in `decode`.
- **256-row `TILE` boundary crossing**: Rather than running 250+ full 28-layer Q8 matvec passes in C-sim, `testbench.cpp` deterministically seeds KV rows `n..(tile_start-1)` (`prefill`) or `n..254` (`decode`) with finite, non-uniform BF16 values while leaving tail rows `>= tile_start + N` (`prefill`) or `>= 258` (`decode`) poisoned with `0x7fc0` NaN. It then runs:
  - `prefill`: one batch-`N` group at `tile_start = 256 - N/2` (`252..259` for `N=8`; `248..263` for `N=16`), straddling `TILE=256` within a single `cmd=8` call (`N/2` tokens in tile 0 and `N/2` tokens carrying `run_acc`, `run_max`, `run_total` across tile 0 to tile 1).
  - `decode`: three single-token steps at `255`, `256`, `257`.
- **Compared fields (raw 32-bit patterns, indexed per kept position `M`)**:
  - `hidden`: `[28, M, 1024]` after every layer
  - `kv`: `[28, 2, 8, M, 64]` packed BF16 cache rows for kept positions
  - `norm`: `[M, 1024]` final RMSNorm output
  - `token`: `[M]` greedy winner over the first `8,192` vocabulary rows
  - `logit`: `[M]` raw IEEE-754 float32 bits of the winning logit
- **Vitis execution**: Runs through `S:\` (or `--drive`, auto-mapped with `subst`) to avoid OneDrive path spaces breaking Vitis C-sim makefiles, and holds both a lockfile and a Vitis process check so only one Vitis job runs at a time.
- **Verification limit (2026-11-21 run)**: Full-decoder 28-layer `csim_design` was not completed in that initial run (Gemini sandbox blocked direct `S:\`/Vitis access, and the operator full-decoder C-sim was stopped after ~50 min on the first baseline and descoped to a follow-up run); current verified evidence in this directory covers `audit.py --self-test` and the operator-executed compiled `attention()` probe (`75,776` FP32 outputs covering decode and batch-8 prefill across `TILE=256`). Note: `experiments/v9i/exactness.md` separately records the later 2026-11-22 batch-8 prefill `--no-tile-cross` exactness pass between `v9h` and `v9i`.
