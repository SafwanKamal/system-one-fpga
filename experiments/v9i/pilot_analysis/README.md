# v9i Pilot Analysis

Offline analysis tool for comparing a v9i (RC1.4) KR260 board pilot against the RC1.3 (v9h) reference using the board result formats recorded in `docs/research/2026-11-20-rc1-3-ship.md`.

## Supported input formats

1. `bench-<label>.json`: JSON list of 21 tool-query results written by `install_rc13.py bench` (`query`, `ok`, `complete`, `generated_ids`, `path`, `prefill_seconds`, `decode_seconds`, `elapsed_seconds`, `wall_seconds`, `prefix_tokens_reused`, `speculate`, `speculation`).
2. `BENCH-JSON [...]`: stdout log containing a `BENCH-JSON ` line (as parsed by `experiments/rc12_ship/compare.py`).
3. `pilot.json`: JSON object with a `cases` array (as written by `experiments/dual_port/v9h_pilot.py`).
4. Archived wrapper JSON objects from the RC1.3 ship record (`docs/research/2026-11-20-rc1-3-ship.md`):
   - `build/v2/rc1-3/board/bench-template-cache.json` (select arm `shared` via `--rc13-arm shared` / `--pilot-arm shared`).
   - `build/v2/rc1-3/board/bench-compare.json` (select arm `rc13` via `--rc13-arm rc13` / `--pilot-arm rc13`).

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

### Using archived RC1.3 wrappers directly (or extracting arrays)

Pass `--rc13-arm` (and `--pilot-arm` when comparing a wrapped pilot archive) to select the desired arm directly without manual extraction:

```sh
# Using bench-template-cache.json ("shared" arm) + 36-case v9h pilot.json:
python experiments/v9i/pilot_analysis/analyze_pilot.py \
  --rc13 build/v2/rc1-3/board/bench-template-cache.json path/to/v9h-ref-36.json \
  --rc13-arm shared \
  --pilot path/to/bench-v9i.json path/to/v9i-pilot.json \
  --out build/v2/v9i/pilot-analysis.json \
  --check

# Or using pre-template-cache bench-compare.json ("rc13" arm):
python experiments/v9i/pilot_analysis/analyze_pilot.py \
  --rc13 build/v2/rc1-3/board/bench-compare.json \
  --rc13-arm rc13 \
  --pilot path/to/bench-v9i.json \
  --check
```

If you prefer standalone array files, extract the exact baseline arms and trim the historical `v9h-board/pilot.json` (which has indices `0, 5, ..., 175` plus tail index `180`) to the 36 runbook cases (`index < 180`) as follows:

```sh
python -c "import json; from pathlib import Path; Path('rc13-shared.json').write_text(json.dumps(json.loads(Path('build/v2/rc1-3/board/bench-template-cache.json').read_text())['shared']))"
python -c "import json; from pathlib import Path; Path('rc13-compare.json').write_text(json.dumps(json.loads(Path('build/v2/rc1-3/board/bench-compare.json').read_text())['rc13']))"
python -c "import json; from pathlib import Path; d=json.loads(Path('build/v2/v9h-board/pilot.json').read_text()); d['cases']=[c for c in d['cases'] if c['index']<180]; Path('v9h-ref-36.json').write_text(json.dumps(d))"
```

## Thresholds (defined at top of `analyze_pilot.py`)

- `REQUIRE_EXACT_IDENTITY = True`: every query occurrence must match RC1.3 in `generated_ids`/`tokens` (and `path`, `logit_bits`, `kv_sha256` when present), with explicit boolean `ok=True` and `complete=True` (and `identical=True` / terminal `passed=True` on `pilot.json`). Raw `pilot.json` cases additionally require both `ar` and `candidate` arms on both sides to provide complete non-empty `tokens`, matching-length `logit_bits`, and non-empty `kv_sha256`, matching both their corresponding RC1.3 arms and each other (missing or mismatched AR/candidate fields report the affected case as `NO-GO`). Token IDs (`generated_ids`, `candidate.tokens`, `ar.tokens`) and `logit_bits` must be non-negative integers (booleans and floats are rejected). Successful canonical socket bench rows require explicit `elapsed_seconds` (never falling back to `wall_seconds` or `prefill+decode`), successful `pilot.json` cases require explicit `prefill_seconds` (where E2E is `prefill_seconds + candidate.decode_seconds`), and matched queries must share both the same timing boundary (`source_format`) and matching measured cache conditions (`prefix_tokens_reused`). Socket bench pairs require measured non-negative `prefix_tokens_reused` on both sides (missing/`null` `prefix_tokens_reused` on either or both socket rows marks timings unavailable and forces `NO-GO`, while raw `pilot.json` cases remain distinct because `v9h_pilot.py` explicitly runs full prefill). Successful matched rows require strictly positive E2E duration (`> 0`) and strictly positive decode duration (`> 0`) whenever generation requires decode work (`len(tokens) > 1`); successful socket (`bench`) rows additionally require `elapsed_seconds >= prefill_seconds + decode_seconds` (when stage timings are available) and `wall_seconds >= elapsed_seconds` (when `wall_seconds` is available), within a `1e-6 s` rounding tolerance. Invalid timings on matched rows are invalidated, excluded from timing summaries/denominators, and force `NO-GO`. Pairs with mismatched or unmeasured `prefix_tokens_reused` are reported per query, excluded from decode/E2E timing summaries, and force `NO-GO`. Completed board failures (`ok=False`/`complete=False` bench rows or `pilot.json` with `finished_utc`, `passed=False`, and no `error`) are retained for `NO-GO` reporting with unavailable timings excluded; empty input files (`[]` or `cases: []`), interrupted/error snapshots, and invalid/missing boolean or non-finite/negative timing fields are rejected. Any single token difference fails the pilot.
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
