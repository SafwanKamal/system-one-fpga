# RC1.4 (v9i) Pilot Bundle vs. Analyzer Cross-Check

- **Target bundle:** Codex commit `792510f6ad5c72ab2b43e4fa408ceeef3392701a` (job `6467c25ae23c`, reviewed pass), inspected via staged read-only copies (`firmware/rc1_4/**`, `scripts/v2/package_rc14.py`, `experiments/v9i/pilot/PILOT.md`, `experiments/v9i/pilot/dry_run.py`).
- **Analyzer checked:** `experiments/v9i/pilot_analysis/analyze_pilot.py` (with regression suite `test_analyze_pilot.py`).
- **Overall result:** **PASS** — every structured result file `PILOT.md` instructs the operator to record is parsed by `analyze_pilot.py` with matching filenames, field names, types, and units; rollback to RC1.3 is complete across install, active service, raw-check stopped-service state, failed-probe recovery, and reboot; and the `v9i` drafter coefficients are consistently labelled modelled across packaging, config, service, drop-in, dry-run, and runbook artifacts.

---

## 1. Result Files, Schemas, Fields, and Units (`PILOT.md` vs. `analyze_pilot.py`)

### Structured comparison inputs & outputs

| File in `PILOT.md` | Producer / Source | Format & Key Fields | Units & Labels | Parsed by `analyze_pilot.py` |
|---|---|---|---|---|
| `bench-rc13-shared.json` (`$evidence/bench-rc13-shared.json`) | Extracted `shared` list (21 rows) from `build/v2/rc1-3/board/bench-template-cache.json` (`PILOT.md` L36–38) | JSON list (`source_format="bench"`): `query`, `ok`, `complete`, `speculate`, `prefix_tokens_reused`, `generated_ids`, `path`, `prefill_seconds`, `decode_seconds`, `elapsed_seconds`, `wall_seconds`, `speculation` | Seconds (`float`), token IDs (`int`), `prefix_tokens_reused` (`int`, expected `32`), `speculate="rc1.3-costaware"` | **Yes** (`_load_single_file` list branch -> `_normalize_bench_row`); validates `speculate == "rc1.3-costaware"`, `prefix_tokens_reused`, `ok=True`, `complete=True`, `generated_ids`, `path`, nested socket timings (`elapsed >= prefill + decode`, `wall >= elapsed`). |
| `bench-v9i.json` (`$E/bench-v9i.json`, copied from `/var/lib/sysone/qualifications/rc1-4/bench-$label.json`) | `install_rc14.py bench --label "$label" --keep-cache` (`install_rc14.py` L147–174, `PILOT.md` L109–110) | JSON list (21 rows, `source_format="bench"`): exact RC1.3 row keys (`query`, `ok`, `complete`, `speculate`, `prefix_tokens_reused`, `generated_ids`, `path`, `prefill_seconds`, `decode_seconds`, `elapsed_seconds`, `wall_seconds`, `speculation`) | Seconds (`float`), token IDs (`int`), `prefix_tokens_reused` (`int`, expected `32`), `speculate="rc1.4-costaware"` | **Yes** (`_load_single_file` list branch -> `_normalize_bench_row`); validates `speculate == "rc1.4-costaware"`, `prefix_tokens_reused` parity with RC1.3, `generated_ids`, `path`, and nested socket timings. |
| `bench-v9i.log` (`$E/bench-v9i.log`) | `tee` of `install_rc14.py bench` stdout (`install_rc14.py` L171, `PILOT.md` L109, L116) | Text log containing `BENCH-JSON <json-array>` | Identical JSON list payload to `bench-v9i.json` | **Yes** (`_load_single_file` `BENCH-JSON ` parser produces the exact same normalized `bench` records). |
| `rc14/check/reference-pilot.json` (`$evidence/rc14/check/reference-pilot.json`) | `package_rc14.py` L115–122 (filtered 36 cases `index in range(0, 180, 5)` from `build/v2/v9h-board/pilot.json`, extracted from `rc14.tar` at `PILOT.md` L39) | JSON dict (`source_format="pilot_cases"`): `passed`, `started_utc`, `finished_utc`, `cases[]` (`key`, `index`, `domain`, `prefill_seconds`, `ar.{tokens,logit_bits,kv_sha256,decode_seconds}`, `candidate.{tokens,logit_bits,kv_sha256,decode_seconds}`, `ar_equal_v9e`, `candidate_equal_v9e`, `identical`) | Seconds (`float`), non-negative integer token IDs & FP32 `logit_bits`, hex SHA-256 `kv_sha256` | **Yes** (`_normalize_pilot_doc` -> `_normalize_pilot_case`); validates top-level terminal `passed=True` + `finished_utc`, both `ar` and `candidate` arm completeness/equality, and computes E2E as `prefill_seconds + candidate.decode_seconds` (matching `PILOT.md` L203–204). |
| `raw/pilot.json` (`$E/raw/pilot.json`) | `check_v9i.py` (`package_rc14.py` L124–138 patching `experiments/dual_port/v9h_pilot.py`, `PILOT.md` L131–140) | JSON dict (`source_format="pilot_cases"`): `passed`, `started_utc`, `finished_utc`, optional `error`, `cases[]` (36 cases, same schema as `reference-pilot.json`) | Seconds (`float`), non-negative integer token IDs & FP32 `logit_bits`, hex SHA-256 `kv_sha256` | **Yes** (`_normalize_pilot_doc` -> `_normalize_pilot_case`); retains completed `passed=False` (no `error`) failures for per-case `NO-GO` reporting and rejects interrupted/error snapshots. |

### Non-analyzer operational & audit records in `PILOT.md`

The remaining files in `PILOT.md` (`before.log`, `install.log`, `v9i-service.log`, `raw.log`, `rollback.log`, `after.log`, `service-journal.log`, `observation.json`) are board-state snapshots, systemd/installer/progress logs, and the `board_status.py` observation record. They are not offline inference result inputs to `analyze_pilot.py`.

### Notes on combined `PILOT.md` invocation & order check

- `PILOT.md` L199 invokes `analyze_pilot.py` with both pairs together (`--rc13 bench-rc13-shared.json reference-pilot.json --pilot bench-v9i.json raw/pilot.json --check`).
  - IDs do not collide between the 21 socket rows (`query`, e.g. `"Read /proc/uptime"`) and the 36 raw cases (`key`, where tool cases are prefixed `"tool:..."`).
  - `bench` rows and `pilot_cases` rows are paired within their own `source_format`, so `timing_boundary_comparable` holds for all 57 pairs.
  - Because `select_workload.py` interleaves `general`, `maintenance`, `long`, and `tool`, the 36-case raw check (`index = 0, 5, ..., 175`) contains ~9 raw `domain="tool"` cases alongside the 21 socket `bench` tool rows. See **Section 4** for the analyzer adjustment added to keep socket and raw aggregates identifiable even at the summary level.
- **Minor non-blocking note on ordering (`PILOT.md` L190):** `PILOT.md` states `"with exactly the RC1.3 generated token IDs and tool paths in the same order"`. `install_rc14.py` and `check_v9i.py` execute sequentially in fixed `queries.json` / `workload.json` order, and `analyze_pilot.py` enforces exact 1-to-1 ID + occurrence pairing (`same_id_set`) rather than rejecting an identically keyed file whose list order was permuted.

---

## 2. Rollback to RC1.3 Completeness Audit

Verified across `firmware/rc1_4/install_rc14.py`, `firmware/rc1_4/rc14_image.py`, `firmware/rc1_4/30-rc14-pilot.conf`, `firmware/rc1_4/README.md`, and `experiments/v9i/pilot/PILOT.md`:

1. **Non-destructive staging (`install_rc14.py` L69–104):**
   - Staging writes only to new dedicated paths `/var/lib/sysone/rc1-4-pilot` (`BUNDLE`) and `/lib/firmware/xilinx/sysone-qwen-decoder-v9i` (`FIRMWARE / APP`) via temporary staging directories and atomic rename/rollback on `OSError`.
   - Persistent RC1/RC1.3 directories (`/var/lib/sysone/hardware-consolidated-rc1-20261108`, `/var/lib/sysone/rc1-default-v1`, `/var/lib/sysone/rc1-3-v1`, `/lib/firmware/xilinx/sysone-qwen-decoder-v9h`) and persistent drop-ins (`/etc/systemd/system/sysone-rc1.service.d/10-speculation.conf`, `20-rc13.conf`) are never overwritten or removed.
2. **Volatile systemd override & reboot safety (`30-rc14-pilot.conf`, `install_rc14.py` L18, L127–144):**
   - Activation places `/run/systemd/system/sysone-rc1.service.d/30-rc14-pilot.conf` (under volatile `/run/`). Any reboot automatically drops the override and boots persistent RC1.3 (`20-rc13.conf` on `v9h`).
   - Before replacing `DROPIN`, `enable()` verifies `20-rc13.conf` exists, checks bundle SHA-256s, probes `rc1.3-costaware`, and stops `sysone-rc1.service` so RC1.3's `ExecStopPost` transitions `v9h -> v9e`.
   - Any exception during `enable()` (including a failed `rc1.4-costaware` READY probe) triggers `rollback()` automatically.
3. **Explicit rollback after service or raw check (`install_rc14.py` L115–124, `rc14_image.py` L49–89, `PILOT.md` L145–185):**
   - `rollback()` requires `20-rc13.conf` present, stops `sysone-rc1.service` (if active, triggering `ExecStopPost` `rc14_image.py down`), explicitly runs `rc14_image.py down` (needed when `sysone-rc1.service` is already stopped after `check_v9i.py`, and idempotent if `v9e` is already active), unlinks only `30-rc14-pilot.conf`, runs `systemctl daemon-reload`, starts `sysone-rc1.service` (running `20-rc13.conf` -> `rc13_image.py up` `v9e -> v9h`), and probes `rc1.3-costaware`.
   - `rc14_image.py` checks `/run/lock/sysone-inference.lock`, `sealed=1 loading=0 owner_tgid=0 vmas=0`, decoder idle bit, reloads source on load failure, and verifies the DMA `buffers` residency table is unchanged.
   - `PILOT.md` L150–185 records `rollback.log`, `after.log`, `service-journal.log`, checks `boot_id` / `v9h` / `READY` / DMA lease PID / `rc1.3-costaware`, and handles failed restoration via `state = 'unknown'` before releasing `BOARD_STATUS.json`.
   - **Operational note (non-blocking, by design):** `/var/lib/sysone/rc1-4-pilot`, `/lib/firmware/xilinx/sysone-qwen-decoder-v9i`, and `/var/lib/sysone/qualifications/rc1-4/` remain on disk after rollback for post-pilot audit (`firmware/rc1_4/README.md` L18). They do not affect RC1.3, though a future re-stage would require removing the prior stage directories first (`install_rc14.py` L75–77).

---

## 3. Modelled Drafter Coefficients Audit

Every reference to the `v9i` drafter cost coefficients explicitly labels them **modelled** (not board-fitted):

- `scripts/v2/package_rc14.py` L41–48 & L139–141: `model(fit)` sets `coef[3] = coef[2]` (full dual weight port on all passes, `P=2` attention groups per `experiments/attn_reclaim/model_p2.py dual+p2`), and writes `config.json` with `"cost_model": "modelled from v9h board fit"` and `"cost_model_source": "experiments/attn_reclaim/model_p2.py dual+p2"`.
- `firmware/rc1_4/README.md` L7–11: `"The seven drafter coefficients are **modelled from the v9h board fit** ... The v9i coefficients have no v9i board calibration."`
- `firmware/rc1_4/30-rc14-pilot.conf` L3: `Description=RC1.4 pilot (v9i, modelled dual-port P=2 drafter costs)`.
- `firmware/rc1_4/spec_service_rc14.py` L1 & L159: docstring states `"modelled dual-port P=2 costs"` and instantiates `CostAwareDrafter(..., coef, prior=0.5, prior_w=2.0, P=2)`.
- `experiments/v9i/pilot/dry_run.py` L99–102: asserts `c[2] == c[3]`, `cfg["split_all_passes"]`, `cfg["cost_model"].startswith("modelled")`, and tests `CostAwareDrafter(..., P=2)` cost equation for `k=1..8`.
- `experiments/v9i/pilot/PILOT.md` L121–123 & L204–205: states `"The 21-query service bench exercises the modelled v9i drafter"`, clarifies that the 36-case raw checker (`check_v9i.py`) retains `v9h`'s original qualification drafter (`coef_dev`, `P=4`), and states `"The expected speedups of 1.31x on tools and 1.065x overall are model projections."`

---

## 4. Analyzer Adjustments & Verification

### Adjustment made (`experiments/v9i/pilot_analysis/analyze_pilot.py`)

When running the combined `PILOT.md` L199 command (`21` socket `bench` rows + `36` raw `pilot_cases` rows), both the 21 socket rows and the ~9 raw `domain="tool"` cases had `is_tool=True`, so `measured_vs_modelled["tool"]` aggregated both `elapsed_seconds` (template-cached `rc1.4-costaware` service) and `prefill_seconds + candidate.decode_seconds` (cold `v9h` `coef_dev`/`P=4` raw check), and section `(b)` had no aggregate split by `source_format`.

To honor `PILOT.md` L204 (`"Keep the raw and socket timings identifiable"`) at the summary level without breaking any existing API/JSON field:
1. Added `"by_source_format"` to `analyze()` output (`bench` vs `pilot_cases`), and printed `SOURCE[<format>]` lines in `format_report()` section `(b)` whenever multiple source formats are present.
2. When `tool_items` spans both `"bench"` and `"pilot_cases"`, added `"socket_tool"` inside `measured_vs_modelled` (and `Socket Tool E2E:` in `format_report()`) plus `"measured_socket_tool_cases"`, `"measured_raw_tool_cases"`, and `"measured_source_formats"` in `measured_vs_modelled["scope"]`, while preserving `"tool"` unchanged for backward compatibility.
3. Added regression test `test_rc14_pilot_md_combined_21_plus_36_schemas_and_source_format_split` in `experiments/v9i/pilot_analysis/test_analyze_pilot.py` exercising exact `PILOT.md` schemas (`bench-rc13-shared.json`, `reference-pilot.json`, `bench-v9i.json`, `bench-v9i.log`, and `raw/pilot.json`).

### Verification

- `python -m unittest discover -s experiments/v9i/pilot_analysis -p "test_*.py" -v`: **23/23 tests PASS**.
