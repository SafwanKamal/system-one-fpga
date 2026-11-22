# v9i Pilot Analysis

Offline analysis tool for comparing a v9i (RC1.4) KR260 board pilot against the RC1.3 (v9h) reference using the board result formats recorded in `docs/research/2026-11-20-rc1-3-ship.md`.

## Supported input formats

1. `bench-<label>.json`: JSON list of 21 tool-query results written by `install_rc13.py bench` (`query`, `ok`, `complete`, `generated_ids`, `path`, `prefill_seconds`, `decode_seconds`, `elapsed_seconds`, `wall_seconds`, `prefix_tokens_reused`, `speculate`, `speculation`).
2. `BENCH-JSON [...]`: stdout log containing a `BENCH-JSON ` line (as parsed by `experiments/rc12_ship/compare.py`).
3. `pilot.json`: JSON object with a `cases` array (as written by `experiments/dual_port/v9h_pilot.py`).

Multiple files can be passed to `--rc13` and `--pilot` (for example, a 21-query tool bench file plus a 36-case workload `pilot.json`).

## Usage

```sh
python experiments/v9i/pilot_analysis/analyze_pilot.py \
  --rc13 path/to/bench-rc13.json \
  --pilot path/to/bench-v9i.json \
  --out build/v2/v9i/pilot-analysis.json \
  --check
```

Or with positional arguments:

```sh
python experiments/v9i/pilot_analysis/analyze_pilot.py \
  path/to/bench-rc13.json path/to/bench-v9i.json build/v2/v9i/pilot-analysis.json
```

## Thresholds (defined at top of `analyze_pilot.py`)

- `REQUIRE_EXACT_IDENTITY = True`: every query occurrence must match RC1.3 in `generated_ids`/`tokens` (and `path`, `logit_bits`, `kv_sha256` when present), with explicit boolean `ok=True` and `complete=True` (and `identical=True` / terminal `passed=True` on `pilot.json`). Completed board failures (`ok=False`/`complete=False` bench rows or `pilot.json` with `finished_utc`, `passed=False`, and no `error`) are retained for `NO-GO` reporting with unavailable timings excluded; interrupted/error snapshots and invalid/missing boolean or non-finite/negative timing fields are rejected. Any single token difference fails the pilot.
- `MIN_DECODE_SPEEDUP = 1.03`: minimum aggregate decode speedup vs RC1.3 (v9h), computed and gated at full precision.
- `MIN_E2E_SPEEDUP = 1.00`: minimum aggregate end-to-end speedup vs RC1.3 (v9h), computed and gated at full precision.
- Modelled E2E reference speedups vs v9h (`docs/research/2026-11-21-attention-reclaim.md`): `1.31x` E2E tool, `1.065x` E2E overall across the 181-case workload (`0.884x` is separately modelled for overall speculative decode). Measured-vs-modelled comparisons are restricted to E2E and report the scope difference between the measured sample and the 181-case model.

## Synthetic fixtures & tests

Fixtures in `experiments/v9i/pilot_analysis/fixtures/`:
- `rc13_bench.json`: 21-query RC1.3 reference fixture.
- `pilot_go_bench.json`: 21/21 identical, ~1.31x decode speedup (`GO`).
- `pilot_nogo_identity_bench.json`: 1 token mismatch (`NO-GO` identity).
- `pilot_nogo_slower_bench.json`: 21/21 identical, slower decode (`NO-GO` slower).

Run tests:

```sh
python -m unittest discover -s experiments/v9i/pilot_analysis -p "test_*.py" -v
```
