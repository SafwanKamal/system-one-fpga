"""Analyze v9i board pilot results against the RC1.3 (v9h) baseline.

GO / NO-GO thresholds (explicitly stated here; override via CLI flags if needed):
- REQUIRE_EXACT_IDENTITY = True
    100% output identity vs RC1.3 across every query/case (exact `generated_ids` /
    `tokens`, matching `path` / `logit_bits` / `kv_sha256` when present, and
    `ok=True`, `complete=True`; socket bench rows additionally require the expected
    per-side `speculate` mode labels). Any single token difference fails the pilot.
- EXPECTED_RC13_SPECULATE = "rc1.3-costaware"
    Expected `speculate` label on RC1.3 socket (`bench`) rows.
- EXPECTED_PILOT_SPECULATE = "rc1.4-costaware"
    Expected `speculate` label on candidate pilot socket (`bench`) rows.
- MIN_DECODE_SPEEDUP = 1.03
    Minimum aggregate decode speedup vs RC1.3 (v9h) across the evaluated run.
- MIN_E2E_SPEEDUP = 1.00
    Minimum aggregate end-to-end speedup vs RC1.3 (v9h) (no end-to-end regression).

Modelled E2E speedups vs v9h (from docs/research/2026-11-21-attention-reclaim.md):
- MODELLED_TOOL_E2E_SPEEDUP = 1.31       (E2E tool speedup vs v9h)
- MODELLED_OVERALL_E2E_SPEEDUP = 1.065   (E2E overall speedup across 181-case workload)
- MODELLED_OVERALL_DECODE_SPEEDUP = 0.884 (separately modelled overall speculative decode)

Supported RC1.3 / pilot board result formats:
1. `bench-<label>.json`: JSON list produced by `install_rc13.py bench` (21 tool queries).
2. `BENCH-JSON [...]`: stdout log containing a `BENCH-JSON ` line (`rc12_ship/compare.py`).
3. `pilot.json`: JSON object with `cases` list and terminal status (`finished_utc` without `error`; `passed=False` completed failures are retained for `NO-GO` reporting, while interrupted/error snapshots are rejected) (`experiments/dual_port/v9h_pilot.py`).
4. Archived wrapper JSON objects (e.g., `bench-template-cache.json` with `shared` or pre-template-cache `bench-compare.json` with `rc13`), selected explicitly via `--rc13-arm` / `--pilot-arm`. When `--rc13-arm rc13` is used and every row omits `prefix_tokens_reused` (the documented `0cc305b` `install_rc13.py` `reset_cache=True` provenance), RC1.3 rows are treated as cold (`prefix_tokens_reused=0`). Pass `--rc13-cold-baseline` when supplying a standalone extracted `rc13-compare.json` or `0cc305b` `BENCH-JSON` stdout log.

Usage:
    python analyze_pilot.py --rc13 RC13_BENCH --pilot PILOT_BENCH [--out OUT.json]
    python analyze_pilot.py RC13_BENCH PILOT_BENCH [OUT.json]
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

# --- GO / NO-GO thresholds ---
REQUIRE_EXACT_IDENTITY = True
MIN_DECODE_SPEEDUP = 1.03
MIN_E2E_SPEEDUP = 1.00
EXPECTED_RC13_SPECULATE = "rc1.3-costaware"
EXPECTED_PILOT_SPECULATE = "rc1.4-costaware"

# --- Modelled speedups vs v9h (docs/research/2026-11-21-attention-reclaim.md) ---
# 1.31x (tool) and 1.065x (overall, 181-case workload) are end-to-end (E2E) values;
# the research record separately models 0.884x overall speculative decode.
MODELLED_TOOL_E2E_SPEEDUP = 1.31
MODELLED_OVERALL_E2E_SPEEDUP = 1.065
MODELLED_OVERALL_DECODE_SPEEDUP = 0.884
MODELLED_WORKLOAD_CASES = 181
MODELLED_TOOL_SPEEDUP = MODELLED_TOOL_E2E_SPEEDUP
MODELLED_OVERALL_SPEEDUP = MODELLED_OVERALL_E2E_SPEEDUP


# --- Timing consistency tolerance ---
# Allow tiny floating-point / serialization rounding tolerance when checking
# nested socket timing intervals (elapsed >= prefill + decode, wall >= elapsed).
TIMING_ROUNDING_TOLERANCE = 1e-6


def _is_nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _parse_nonneg_int(
    value: Any, field: str, path: Path, *, required: bool = False
) -> int | None:
    if value is None:
        if required:
            raise ValueError(f"{path}: missing or null required integer {field!r}")
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(
            f"{path}: {field!r} must be an integer, got {type(value).__name__} ({value!r})"
        )
    if value < 0:
        raise ValueError(f"{path}: {field!r} must be non-negative, got {value!r}")
    return value


def _parse_nonneg_int_list(
    value: Any, field: str, path: Path, *, context: str, elem_label: str
) -> list[int]:
    if not isinstance(value, list):
        raise ValueError(f"{path}: {context} {field!r} must be a list")
    out: list[int] = []
    for idx, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, int):
            raise ValueError(
                f"{path}: {context} {field!r}[{idx}] must be an {elem_label}, "
                f"got {type(item).__name__} ({item!r})"
            )
        if item < 0:
            raise ValueError(
                f"{path}: {context} {field!r}[{idx}] must be non-negative, got {item!r}"
            )
        out.append(item)
    return out


def _parse_token_ids(
    value: Any, field: str, path: Path, *, context: str
) -> list[int]:
    return _parse_nonneg_int_list(
        value, field, path, context=context, elem_label="integer token ID"
    )


def _parse_logit_bits(
    value: Any, field: str, path: Path, *, context: str
) -> list[int]:
    return _parse_nonneg_int_list(
        value, field, path, context=context, elem_label="integer logit bit pattern"
    )


def _parse_kv_sha256(
    value: Any, field: str, path: Path, *, context: str
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(
            f"{path}: {context} {field!r} must be a string, "
            f"got {type(value).__name__} ({value!r})"
        )
    return value if value.strip() != "" else None


def _validate_token_list_direct(value: Any, field: str, record_id: str) -> list[int]:
    if not isinstance(value, list):
        raise ValueError(f"record {record_id!r} {field!r} must be a list")
    for idx, tok in enumerate(value):
        if isinstance(tok, bool) or not isinstance(tok, int):
            raise ValueError(
                f"record {record_id!r} {field!r}[{idx}] must be an integer, "
                f"got {type(tok).__name__} ({tok!r})"
            )
        if tok < 0:
            raise ValueError(
                f"record {record_id!r} {field!r}[{idx}] must be non-negative, got {tok!r}"
            )
    return list(value)


def _parse_timing(value: Any, field: str, path: Path, *, required: bool) -> float | None:
    if value is None:
        if required:
            raise ValueError(f"{path}: missing or null required timing {field!r}")
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path}: timing {field!r} must be a number, got {value!r}")
    fval = float(value)
    if not math.isfinite(fval) or fval < 0.0:
        raise ValueError(f"{path}: timing {field!r} must be finite and nonnegative, got {value!r}")
    return fval


def _validate_pilot_file_status(raw: dict[str, Any], path: Path) -> None:
    if "passed" not in raw or not isinstance(raw["passed"], bool):
        raise ValueError(
            f"{path}: pilot.json missing boolean top-level 'passed' status "
            "(interrupted or incomplete snapshot)"
        )
    if "started_utc" in raw and not _is_nonempty_str(raw.get("finished_utc")):
        raise ValueError(
            f"{path}: pilot.json has 'started_utc' without terminal 'finished_utc' "
            "(interrupted snapshot)"
        )
    if raw.get("error") is not None and raw.get("error") != "":
        raise ValueError(f"{path}: pilot.json failed with error: {raw['error']!r}")
    if raw["passed"] is False and not _is_nonempty_str(raw.get("finished_utc")):
        raise ValueError(
            f"{path}: pilot.json has passed=False without terminal 'finished_utc' "
            "(incomplete snapshot)"
        )


def _is_pilot_doc(obj: Any) -> bool:
    return isinstance(obj, dict) and isinstance(obj.get("cases"), list)


def _normalize_pilot_doc(raw: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    _validate_pilot_file_status(raw, path)
    if not raw["cases"]:
        raise ValueError(f"{path}: pilot.json contains zero cases")
    file_passed = raw["passed"]
    return [_normalize_pilot_case(case, path, file_passed=file_passed) for case in raw["cases"]]


def _all_omit_reused(rows: list[Any]) -> bool:
    """Return True when every row is a dict omitting the 'prefix_tokens_reused' key."""
    return bool(rows) and all(
        isinstance(row, dict) and "prefix_tokens_reused" not in row
        for row in rows
    )


def _load_single_file(
    path: Path,
    *,
    arm: str | None = None,
    allow_legacy_cold_arm: bool = False,
    cold_baseline: bool = False,
) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    raw: Any = None
    stripped = text.lstrip()
    if stripped.startswith("[") or stripped.startswith("{"):
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            raw = None
    if raw is None:
        bench_rows: list[dict[str, Any]] = []
        for line in text.splitlines():
            if line.startswith("BENCH-JSON "):
                payload = json.loads(line[len("BENCH-JSON "):])
                if not isinstance(payload, list):
                    raise ValueError(f"{path}: BENCH-JSON payload must be a list")
                bench_rows.extend(payload)
        if not bench_rows:
            raise ValueError(f"{path}: unrecognized board result format (expected JSON list, pilot.json dict, or BENCH-JSON line)")
        raw = bench_rows

    if isinstance(raw, list):
        if not raw:
            raise ValueError(f"{path}: bench result list is empty")
        default_omitted_reused = 0 if (cold_baseline and _all_omit_reused(raw)) else None
        return [
            _normalize_bench_row(row, path, default_omitted_reused=default_omitted_reused)
            for row in raw
        ]
    if isinstance(raw, dict):
        if _is_pilot_doc(raw) and (arm is None or arm == "cases" or arm not in raw):
            return _normalize_pilot_doc(raw, path)
        avail = [
            str(k) for k, v in raw.items()
            if isinstance(v, list) or _is_pilot_doc(v)
        ]
        if arm is None:
            if avail:
                raise ValueError(
                    f"{path}: wrapper JSON object requires explicit arm selection "
                    f"(--rc13-arm / --pilot-arm); available arm keys: {', '.join(avail)}"
                )
            raise ValueError(f"{path}: unsupported JSON structure; expected list or dict with 'cases'")
        if arm not in raw:
            avail_msg = ", ".join(avail) if avail else "<none>"
            raise ValueError(
                f"{path}: wrapper JSON object has no arm {arm!r}; available arm keys: {avail_msg}"
            )
        selected = raw[arm]
        if isinstance(selected, list):
            if not selected:
                raise ValueError(f"{path}: wrapper arm {arm!r} bench result list is empty")
            # Pre-template-cache RC1.3 bench-compare.json ('rc13' arm from 0cc305b install_rc13.py)
            # always used reset_cache=True without emitting prefix_tokens_reused.
            is_legacy_cold_rc13 = (allow_legacy_cold_arm and arm == "rc13") or cold_baseline
            default_omitted_reused = (
                0 if (is_legacy_cold_rc13 and _all_omit_reused(selected)) else None
            )
            return [
                _normalize_bench_row(row, path, default_omitted_reused=default_omitted_reused)
                for row in selected
            ]
        if _is_pilot_doc(selected):
            return _normalize_pilot_doc(selected, path)
        raise ValueError(
            f"{path}: wrapper arm {arm!r} must be a list or pilot.json object, "
            f"got {type(selected).__name__}"
        )
    raise ValueError(f"{path}: unsupported JSON structure; expected list or dict with 'cases'")


def _normalize_bench_row(
    row: dict[str, Any],
    path: Path,
    *,
    default_omitted_reused: int | None = None,
) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError(f"{path}: bench row must be an object")
    if "query" not in row or not _is_nonempty_str(row["query"]):
        raise ValueError(f"{path}: bench row missing non-empty 'query'")
    if "ok" not in row or not isinstance(row["ok"], bool):
        raise ValueError(f"{path}: bench row for {row['query']!r} missing boolean 'ok'")
    if "complete" not in row:
        raise ValueError(f"{path}: bench row for {row['query']!r} missing 'complete'")
    ok_val = row["ok"]
    comp_val = row["complete"]
    if ok_val is True:
        if not isinstance(comp_val, bool):
            raise ValueError(f"{path}: bench row for {row['query']!r} requires boolean 'complete' when ok=True")
    else:
        if comp_val is not None and not isinstance(comp_val, bool):
            raise ValueError(f"{path}: bench row for {row['query']!r} has invalid 'complete': {comp_val!r}")
    complete_bool = comp_val is True
    row_ok = ok_val and complete_bool

    if "generated_ids" in row:
        token_field = "generated_ids"
        raw_tokens = row["generated_ids"]
    elif "tokens" in row:
        token_field = "tokens"
        raw_tokens = row["tokens"]
    elif row_ok:
        raise ValueError(f"{path}: bench row for {row['query']!r} missing 'generated_ids'")
    else:
        token_field = "generated_ids"
        raw_tokens = None

    if raw_tokens is None:
        if row_ok:
            raise ValueError(f"{path}: bench row for {row['query']!r} has null 'generated_ids' with ok=True, complete=True")
        tokens: list[int] | None = None
    else:
        tokens = _parse_token_ids(
            raw_tokens, token_field, path, context=f"bench row for {row['query']!r}"
        )

    if "prefix_tokens_reused" in row:
        reused = _parse_nonneg_int(
            row["prefix_tokens_reused"], "prefix_tokens_reused", path, required=False
        )
    else:
        reused = default_omitted_reused

    decode = _parse_timing(row.get("decode_seconds"), "decode_seconds", path, required=row_ok)
    if "prefill_seconds" in row:
        prefill = _parse_timing(row["prefill_seconds"], "prefill_seconds", path, required=row_ok)
    else:
        prefill = None
    wall = _parse_timing(row.get("wall_seconds"), "wall_seconds", path, required=False)
    e2e = _parse_timing(row.get("elapsed_seconds"), "elapsed_seconds", path, required=row_ok)

    category = row.get("domain") or row.get("category") or row.get("path") or "tool"
    return {
        "id": row["query"],
        "label": row["query"],
        "category": str(category),
        "is_tool": row.get("domain", "tool") == "tool",
        "source_format": "bench",
        "tokens": tokens,
        "ar_tokens": None,
        "path": row.get("path"),
        "logit_bits": None,
        "ar_logit_bits": None,
        "kv_sha256": None,
        "ar_kv_sha256": None,
        "ok": ok_val,
        "complete": complete_bool,
        "file_passed": True,
        "prefill_seconds": prefill,
        "decode_seconds": decode,
        "e2e_seconds": e2e,
        "wall_seconds": wall,
        "reused": reused,
        "speculate": row.get("speculate"),
    }


def _normalize_pilot_case(case: dict[str, Any], path: Path, *, file_passed: bool = True) -> dict[str, Any]:
    if not isinstance(case, dict):
        raise ValueError(f"{path}: pilot.json case must be an object")
    if "key" not in case or case["key"] is None or str(case["key"]).strip() == "":
        raise ValueError(f"{path}: pilot.json case missing 'key'")
    if "identical" not in case or not isinstance(case["identical"], bool):
        raise ValueError(f"{path}: pilot.json case {case['key']!r} missing boolean 'identical'")
    for flag in ("ar_equal_v9e", "candidate_equal_v9e"):
        if flag in case and not isinstance(case[flag], bool):
            raise ValueError(f"{path}: pilot.json case {case['key']!r} field {flag!r} must be boolean")

    case_ok = (
        case["identical"]
        and case.get("ar_equal_v9e", True)
        and case.get("candidate_equal_v9e", True)
    )
    strict_case = case_ok and file_passed

    if "candidate" in case:
        cand = case["candidate"]
    elif "spec" in case:
        cand = case["spec"]
    else:
        cand = None

    if cand is not None and not isinstance(cand, dict):
        raise ValueError(f"{path}: pilot.json case {case['key']!r} candidate must be an object")
    if strict_case and cand is None:
        raise ValueError(f"{path}: pilot.json case {case['key']!r} missing 'candidate'")

    if isinstance(cand, dict):
        if strict_case and "tokens" not in cand:
            raise ValueError(f"{path}: pilot.json case {case['key']!r} missing candidate 'tokens'")
        raw_cand_tokens = cand.get("tokens")
        if raw_cand_tokens is None:
            if strict_case:
                raise ValueError(f"{path}: pilot.json case {case['key']!r} has null candidate 'tokens'")
            cand_tokens: list[int] | None = None
        else:
            cand_tokens = _parse_token_ids(
                raw_cand_tokens,
                "tokens",
                path,
                context=f"pilot.json case {case['key']!r} candidate",
            )
        cand_logit_bits = (
            _parse_logit_bits(
                cand["logit_bits"],
                "logit_bits",
                path,
                context=f"pilot.json case {case['key']!r} candidate",
            )
            if cand.get("logit_bits") is not None
            else None
        )
        cand_kv_sha256 = _parse_kv_sha256(
            cand.get("kv_sha256"),
            "kv_sha256",
            path,
            context=f"pilot.json case {case['key']!r} candidate",
        )
        decode = _parse_timing(cand.get("decode_seconds"), "candidate.decode_seconds", path, required=strict_case)
    else:
        cand_tokens = None
        cand_logit_bits = None
        cand_kv_sha256 = None
        decode = None

    prefill = _parse_timing(case.get("prefill_seconds"), "prefill_seconds", path, required=strict_case)
    e2e = (prefill + decode) if (prefill is not None and decode is not None) else None

    ar = case.get("ar")
    if ar is not None and not isinstance(ar, dict):
        raise ValueError(f"{path}: pilot.json case {case['key']!r} 'ar' must be an object")
    ar_tokens: list[int] | None = None
    ar_logit_bits: list[int] | None = None
    ar_kv_sha256: str | None = None
    if isinstance(ar, dict):
        if "decode_seconds" in ar and ar["decode_seconds"] is not None:
            _parse_timing(ar["decode_seconds"], "ar.decode_seconds", path, required=False)
        if "tokens" in ar and ar["tokens"] is not None:
            ar_tokens = _parse_token_ids(
                ar["tokens"],
                "tokens",
                path,
                context=f"pilot.json case {case['key']!r} ar",
            )
        if "logit_bits" in ar and ar["logit_bits"] is not None:
            ar_logit_bits = _parse_logit_bits(
                ar["logit_bits"],
                "logit_bits",
                path,
                context=f"pilot.json case {case['key']!r} ar",
            )
        ar_kv_sha256 = _parse_kv_sha256(
            ar.get("kv_sha256"),
            "kv_sha256",
            path,
            context=f"pilot.json case {case['key']!r} ar",
        )

    cand_complete = (
        cand is not None
        and cand_tokens is not None
        and len(cand_tokens) > 0
        and cand_logit_bits is not None
        and len(cand_logit_bits) == len(cand_tokens)
        and _is_nonempty_str(cand_kv_sha256)
    )
    ar_complete = (
        ar is not None
        and ar_tokens is not None
        and len(ar_tokens) > 0
        and ar_logit_bits is not None
        and len(ar_logit_bits) == len(ar_tokens)
        and _is_nonempty_str(ar_kv_sha256)
    )

    domain = str(case.get("domain") or "workload")
    return {
        "id": str(case["key"]),
        "label": str(case.get("query") or case["key"]),
        "category": domain,
        "is_tool": domain == "tool",
        "source_format": "pilot_cases",
        "tokens": cand_tokens,
        "ar_tokens": ar_tokens,
        "path": None,
        "logit_bits": cand_logit_bits,
        "ar_logit_bits": ar_logit_bits,
        "kv_sha256": cand_kv_sha256,
        "ar_kv_sha256": ar_kv_sha256,
        "ok": case_ok,
        "complete": bool(cand_complete and ar_complete),
        "file_passed": file_passed,
        "prefill_seconds": prefill,
        "decode_seconds": decode,
        "e2e_seconds": e2e,
        "wall_seconds": None,
        "reused": None,
        "speculate": None,
    }


def load_records(
    paths: list[Path],
    *,
    arm: str | None = None,
    allow_legacy_cold_arm: bool = True,
    cold_baseline: bool = False,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for p in paths:
        records.extend(
            _load_single_file(
                p,
                arm=arm,
                allow_legacy_cold_arm=allow_legacy_cold_arm,
                cold_baseline=cold_baseline,
            )
        )
    return records


def _first_diff_index(a: list[Any], b: list[Any]) -> int | None:
    for idx, (x, y) in enumerate(zip(a, b)):
        if type(x) is not type(y) or x != y:
            return idx
    if len(a) != len(b):
        return min(len(a), len(b))
    return None


def _strict_list_eq(a: list[Any], b: list[Any]) -> bool:
    return len(a) == len(b) and all(type(x) is type(y) and x == y for x, y in zip(a, b))


def _safe_ratio(num: float, den: float) -> float | None:
    if den <= 0.0:
        return None
    return num / den


def _summarize_timings(
    pairs: list[dict[str, Any]], rc13_key: str, pilot_key: str
) -> tuple[float, float, float | None, float | None, float | None, float | None]:
    if not pairs:
        return 0.0, 0.0, None, None, None, None
    rc13_vals = [x[rc13_key] for x in pairs]
    pilot_vals = [x[pilot_key] for x in pairs]
    rc13_tot = sum(rc13_vals)
    pilot_tot = sum(pilot_vals)
    rc13_med = statistics.median(rc13_vals)
    pilot_med = statistics.median(pilot_vals)
    return (
        rc13_tot,
        pilot_tot,
        _safe_ratio(rc13_tot, pilot_tot),
        rc13_med,
        pilot_med,
        _safe_ratio(rc13_med, pilot_med),
    )


def _summarize_group(items: list[dict[str, Any]]) -> dict[str, Any]:
    dec_pairs = [
        x for x in items
        if x.get("decode_comparable", True)
        and x["rc13_decode_seconds"] is not None
        and x["pilot_decode_seconds"] is not None
        and x["rc13_decode_seconds"] > 0.0
        and x["pilot_decode_seconds"] > 0.0
    ]
    e2e_pairs = [
        x for x in items
        if x.get("e2e_comparable", True)
        and x["rc13_e2e_seconds"] is not None
        and x["pilot_e2e_seconds"] is not None
        and x["rc13_e2e_seconds"] > 0.0
        and x["pilot_e2e_seconds"] > 0.0
    ]
    rc13_dec_tot, pilot_dec_tot, dec_speedup, rc13_dec_med, pilot_dec_med, dec_med_speedup = _summarize_timings(
        dec_pairs, "rc13_decode_seconds", "pilot_decode_seconds"
    )
    rc13_e2e_tot, pilot_e2e_tot, e2e_speedup, rc13_e2e_med, pilot_e2e_med, e2e_med_speedup = _summarize_timings(
        e2e_pairs, "rc13_e2e_seconds", "pilot_e2e_seconds"
    )

    return {
        "n": len(items),
        "decode_n": len(dec_pairs),
        "e2e_n": len(e2e_pairs),
        "identical": sum(1 for x in items if x["identical"]),
        "rc13_decode_total_s": rc13_dec_tot,
        "pilot_decode_total_s": pilot_dec_tot,
        "decode_speedup": dec_speedup,
        "rc13_decode_median_s": rc13_dec_med,
        "pilot_decode_median_s": pilot_dec_med,
        "decode_median_speedup": dec_med_speedup,
        "rc13_e2e_total_s": rc13_e2e_tot,
        "pilot_e2e_total_s": pilot_e2e_tot,
        "e2e_speedup": e2e_speedup,
        "rc13_e2e_median_s": rc13_e2e_med,
        "pilot_e2e_median_s": pilot_e2e_med,
        "e2e_median_speedup": e2e_med_speedup,
    }


def _model_comparison(
    measured_e2e: float | None,
    modelled_e2e: float,
    *,
    measured_n: int,
    measured_scope: str,
    model_scope: str,
) -> dict[str, Any]:
    return {
        "metric": "e2e",
        "modelled_speedup": modelled_e2e,
        "measured_e2e_speedup": measured_e2e,
        "e2e_measured_over_modelled": (measured_e2e / modelled_e2e) if measured_e2e is not None else None,
        "e2e_delta_vs_modelled": (measured_e2e - modelled_e2e) if measured_e2e is not None else None,
        "measured_n": measured_n,
        "measured_scope": measured_scope,
        "model_scope": model_scope,
    }


def _validate_records(records: list[dict[str, Any]]) -> None:
    for rec in records:
        rid = str(rec.get("id", "<unknown>"))
        for lfield in ("tokens", "ar_tokens", "logit_bits", "ar_logit_bits"):
            if rec.get(lfield) is not None:
                _validate_token_list_direct(rec[lfield], lfield, rid)
        for sfield in ("kv_sha256", "ar_kv_sha256"):
            sval = rec.get(sfield)
            if sval is not None and not isinstance(sval, str):
                raise ValueError(
                    f"record {rid!r} {sfield!r} must be a string, "
                    f"got {type(sval).__name__} ({sval!r})"
                )
        reused = rec.get("reused")
        if reused is not None:
            if isinstance(reused, bool) or not isinstance(reused, int) or reused < 0:
                raise ValueError(
                    f"record {rid!r} 'reused' must be a non-negative integer, "
                    f"got {type(reused).__name__} ({reused!r})"
                )
        for tfield in ("prefill_seconds", "decode_seconds", "e2e_seconds", "wall_seconds"):
            tval = rec.get(tfield)
            if tval is not None:
                if isinstance(tval, bool) or not isinstance(tval, (int, float)):
                    raise ValueError(
                        f"record {rid!r} {tfield!r} must be a number, "
                        f"got {type(tval).__name__} ({tval!r})"
                    )
                ftval = float(tval)
                if not math.isfinite(ftval) or ftval < 0.0:
                    raise ValueError(
                        f"record {rid!r} {tfield!r} must be finite and non-negative, got {tval!r}"
                    )


def _socket_timing_issues(
    rec: dict[str, Any], tol: float = TIMING_ROUNDING_TOLERANCE
) -> list[str]:
    """Return nested-interval consistency errors for a successful socket ('bench') record."""
    if rec.get("source_format") != "bench":
        return []
    if not (rec.get("ok") and rec.get("complete")):
        return []
    issues: list[str] = []
    elapsed = rec.get("e2e_seconds")
    prefill = rec.get("prefill_seconds")
    decode = rec.get("decode_seconds")
    wall = rec.get("wall_seconds")
    if elapsed is not None:
        if prefill is not None or decode is not None:
            stage_sum = (prefill if prefill is not None else 0.0) + (
                decode if decode is not None else 0.0
            )
            if elapsed + tol < stage_sum:
                issues.append("elapsed_lt_stage_sum")
        if wall is not None and wall + tol < elapsed:
            issues.append("wall_lt_elapsed")
    return issues


def analyze(
    rc13_records: list[dict[str, Any]],
    pilot_records: list[dict[str, Any]],
    *,
    min_decode_speedup: float = MIN_DECODE_SPEEDUP,
    min_e2e_speedup: float = MIN_E2E_SPEEDUP,
    require_exact_identity: bool = REQUIRE_EXACT_IDENTITY,
    expected_rc13_speculate: str = EXPECTED_RC13_SPECULATE,
    expected_pilot_speculate: str = EXPECTED_PILOT_SPECULATE,
) -> dict[str, Any]:
    if not rc13_records or not pilot_records:
        raise ValueError("Both RC1.3 and pilot inputs must contain at least one record")
    _validate_records(rc13_records)
    _validate_records(pilot_records)

    rc13_groups: dict[str, list[dict[str, Any]]] = {}
    for r in rc13_records:
        rc13_groups.setdefault(r["id"], []).append(r)
    pilot_groups: dict[str, list[dict[str, Any]]] = {}
    for p in pilot_records:
        pilot_groups.setdefault(p["id"], []).append(p)

    missing_in_pilot: list[str] = []
    seen_rc13: dict[str, int] = {}
    per_query: list[dict[str, Any]] = []
    for r in rc13_records:
        rid = r["id"]
        occ = seen_rc13.get(rid, 0)
        seen_rc13[rid] = occ + 1
        p_list = pilot_groups.get(rid, [])
        p = p_list[occ] if occ < len(p_list) else None
        if p is None:
            rc13_speculate_ok = (
                r.get("source_format") != "bench"
                or (
                    isinstance(r.get("speculate"), str)
                    and r.get("speculate") == expected_rc13_speculate
                )
            )
            missing_in_pilot.append(rid)
            per_query.append({
                "id": rid,
                "occurrence": occ,
                "category": r["category"],
                "is_tool": r["is_tool"],
                "missing_in_pilot": True,
                "identical": False,
                "tokens_identical": False,
                "cand_tokens_identical": False,
                "ar_tokens_identical": False,
                "ar_self_identical": False,
                "path_identical": False,
                "logit_identical": False,
                "cand_logit_identical": False,
                "ar_logit_identical": False,
                "kv_identical": False,
                "cand_kv_identical": False,
                "ar_kv_identical": False,
                "status_ok": False,
                "rc13_source_format": r.get("source_format"),
                "pilot_source_format": None,
                "rc13_speculate": r.get("speculate"),
                "pilot_speculate": None,
                "speculate_ok": rc13_speculate_ok,
                "first_diff_index": 0,
                "rc13_token_count": len(r["tokens"]) if r["tokens"] is not None else None,
                "pilot_token_count": 0,
                "rc13_prefix_tokens_reused": r.get("reused"),
                "pilot_prefix_tokens_reused": None,
                "cache_comparable": True,
                "timing_boundary_comparable": True,
                "timing_valid": True,
                "timing_issues": [],
                "decode_comparable": True,
                "rc13_prefill_seconds": r["prefill_seconds"],
                "pilot_prefill_seconds": None,
                "rc13_decode_seconds": r["decode_seconds"],
                "pilot_decode_seconds": None,
                "decode_speedup": None,
                "rc13_e2e_seconds": r["e2e_seconds"],
                "pilot_e2e_seconds": None,
                "rc13_wall_seconds": r.get("wall_seconds"),
                "pilot_wall_seconds": None,
                "e2e_comparable": True,
                "e2e_speedup": None,
            })
            continue

        is_raw = (
            r.get("source_format") == "pilot_cases"
            or p.get("source_format") == "pilot_cases"
        )
        both_have_cand_tokens = (r["tokens"] is not None and p["tokens"] is not None)
        both_have_ar_tokens = (
            r.get("ar_tokens") is not None and p.get("ar_tokens") is not None
        )
        ar_tokens_identical = (
            both_have_ar_tokens
            and len(r["ar_tokens"]) > 0
            and _strict_list_eq(r["ar_tokens"], p["ar_tokens"])
        )
        path_identical = (r["path"] == p["path"]) if (r["path"] is not None or p["path"] is not None) else True

        def _raw_arm_complete(toks: Any, bits: Any, kv: Any) -> bool:
            return (
                isinstance(toks, list)
                and len(toks) > 0
                and isinstance(bits, list)
                and len(bits) == len(toks)
                and _is_nonempty_str(kv)
            )

        if is_raw:
            r_cand_ok = _raw_arm_complete(r.get("tokens"), r.get("logit_bits"), r.get("kv_sha256"))
            p_cand_ok = _raw_arm_complete(p.get("tokens"), p.get("logit_bits"), p.get("kv_sha256"))
            r_ar_ok = _raw_arm_complete(r.get("ar_tokens"), r.get("ar_logit_bits"), r.get("ar_kv_sha256"))
            p_ar_ok = _raw_arm_complete(p.get("ar_tokens"), p.get("ar_logit_bits"), p.get("ar_kv_sha256"))

            cand_tokens_identical = (
                both_have_cand_tokens
                and len(r["tokens"]) > 0
                and _strict_list_eq(r["tokens"], p["tokens"])
            )
            tokens_identical = cand_tokens_identical and ar_tokens_identical
            cand_logit_identical = (
                r_cand_ok
                and p_cand_ok
                and _strict_list_eq(r["logit_bits"], p["logit_bits"])
            )
            ar_logit_identical = (
                r_ar_ok
                and p_ar_ok
                and _strict_list_eq(r["ar_logit_bits"], p["ar_logit_bits"])
            )
            cand_kv_identical = (
                r_cand_ok and p_cand_ok and r["kv_sha256"] == p["kv_sha256"]
            )
            ar_kv_identical = (
                r_ar_ok and p_ar_ok and r["ar_kv_sha256"] == p["ar_kv_sha256"]
            )
            logit_identical = cand_logit_identical and ar_logit_identical
            kv_identical = cand_kv_identical and ar_kv_identical
            ar_self_identical = (
                r_cand_ok
                and r_ar_ok
                and p_cand_ok
                and p_ar_ok
                and _strict_list_eq(r["ar_tokens"], r["tokens"])
                and _strict_list_eq(r["ar_logit_bits"], r["logit_bits"])
                and r["ar_kv_sha256"] == r["kv_sha256"]
                and _strict_list_eq(p["ar_tokens"], p["tokens"])
                and _strict_list_eq(p["ar_logit_bits"], p["logit_bits"])
                and p["ar_kv_sha256"] == p["kv_sha256"]
            )
            arms_complete = r_cand_ok and r_ar_ok and p_cand_ok and p_ar_ok
        else:
            cand_tokens_identical = both_have_cand_tokens and _strict_list_eq(r["tokens"], p["tokens"])
            tokens_identical = cand_tokens_identical
            if r.get("ar_tokens") is not None or p.get("ar_tokens") is not None:
                tokens_identical = cand_tokens_identical and ar_tokens_identical
            else:
                ar_tokens_identical = True
            if r.get("logit_bits") is not None or p.get("logit_bits") is not None:
                cand_logit_identical = (
                    _strict_list_eq(r["logit_bits"], p["logit_bits"])
                    if (isinstance(r.get("logit_bits"), list) and isinstance(p.get("logit_bits"), list))
                    else False
                )
            else:
                cand_logit_identical = True
            if r.get("ar_logit_bits") is not None or p.get("ar_logit_bits") is not None:
                ar_logit_identical = (
                    _strict_list_eq(r["ar_logit_bits"], p["ar_logit_bits"])
                    if (isinstance(r.get("ar_logit_bits"), list) and isinstance(p.get("ar_logit_bits"), list))
                    else False
                )
            else:
                ar_logit_identical = True
            if r.get("kv_sha256") is not None or p.get("kv_sha256") is not None:
                cand_kv_identical = (
                    _is_nonempty_str(r.get("kv_sha256"))
                    and _is_nonempty_str(p.get("kv_sha256"))
                    and r["kv_sha256"] == p["kv_sha256"]
                )
            else:
                cand_kv_identical = True
            if r.get("ar_kv_sha256") is not None or p.get("ar_kv_sha256") is not None:
                ar_kv_identical = (
                    _is_nonempty_str(r.get("ar_kv_sha256"))
                    and _is_nonempty_str(p.get("ar_kv_sha256"))
                    and r["ar_kv_sha256"] == p["ar_kv_sha256"]
                )
            else:
                ar_kv_identical = True
            logit_identical = cand_logit_identical and ar_logit_identical
            kv_identical = cand_kv_identical and ar_kv_identical
            ar_self_identical = (
                _strict_list_eq(p["ar_tokens"], p["tokens"])
                if (p.get("ar_tokens") is not None and p["tokens"] is not None)
                else (p.get("ar_tokens") is None)
            )
            arms_complete = True

        rc13_speculate_ok = (
            r.get("source_format") != "bench"
            or (
                isinstance(r.get("speculate"), str)
                and r.get("speculate") == expected_rc13_speculate
            )
        )
        pilot_speculate_ok = (
            p.get("source_format") != "bench"
            or (
                isinstance(p.get("speculate"), str)
                and p.get("speculate") == expected_pilot_speculate
            )
        )
        speculate_ok = rc13_speculate_ok and pilot_speculate_ok

        row_status_ok = bool(r["ok"] and r["complete"] and p["ok"] and p["complete"] and arms_complete)
        status_ok = bool(row_status_ok and speculate_ok)
        identical = (
            tokens_identical
            and ar_self_identical
            and path_identical
            and logit_identical
            and kv_identical
            and status_ok
        )
        if both_have_cand_tokens and not cand_tokens_identical:
            diff_idx = _first_diff_index(r["tokens"], p["tokens"])
        elif both_have_ar_tokens and not ar_tokens_identical:
            diff_idx = _first_diff_index(r["ar_tokens"], p["ar_tokens"])
        elif p["tokens"] is not None and p.get("ar_tokens") is not None and not _strict_list_eq(p["ar_tokens"], p["tokens"]):
            diff_idx = _first_diff_index(p["ar_tokens"], p["tokens"])
        else:
            diff_idx = None

        rc13_reused = r.get("reused")
        pilot_reused = p.get("reused")
        has_any_timings = (
            (r["decode_seconds"] is not None and p["decode_seconds"] is not None)
            or (r["e2e_seconds"] is not None and p["e2e_seconds"] is not None)
        )
        # Raw pilot.json cases explicitly run full prefill with no prefix cache; socket bench rows
        # must have measured non-negative prefix_tokens_reused on both sides to be comparable.
        requires_measured_cache = (
            r.get("source_format") != "pilot_cases"
            or p.get("source_format") != "pilot_cases"
        )
        reused_differs = (rc13_reused != pilot_reused)
        missing_measured_reused = requires_measured_cache and (
            rc13_reused is None or pilot_reused is None
        )
        cache_comparable = not (
            (reused_differs or missing_measured_reused)
            and (row_status_ok or has_any_timings or (rc13_reused is not None and pilot_reused is not None))
        )
        timing_boundary_comparable = (r.get("source_format") == p.get("source_format"))

        requires_decode = (
            (r["tokens"] is not None and len(r["tokens"]) > 1)
            or (p["tokens"] is not None and len(p["tokens"]) > 1)
        )
        nonpositive_e2e = (
            (r["e2e_seconds"] is not None and r["e2e_seconds"] <= 0.0)
            or (p["e2e_seconds"] is not None and p["e2e_seconds"] <= 0.0)
        )
        nonpositive_decode_required = requires_decode and (
            (r["decode_seconds"] is not None and r["decode_seconds"] <= 0.0)
            or (p["decode_seconds"] is not None and p["decode_seconds"] <= 0.0)
        )
        nonpositive_decode_any = (
            (r["decode_seconds"] is not None and r["decode_seconds"] <= 0.0)
            or (p["decode_seconds"] is not None and p["decode_seconds"] <= 0.0)
        )
        nonpositive_timing = row_status_ok and (nonpositive_e2e or nonpositive_decode_required)
        socket_timing_inconsistent = bool(_socket_timing_issues(r) or _socket_timing_issues(p))
        timing_issues: list[str] = []
        if nonpositive_timing:
            timing_issues.append("nonpositive")
        if socket_timing_inconsistent:
            timing_issues.append("inconsistent_socket")
        timing_valid = not timing_issues

        decode_comparable = (
            speculate_ok
            and cache_comparable
            and timing_valid
            and not nonpositive_e2e
            and not nonpositive_decode_any
        )
        e2e_comparable = (
            speculate_ok
            and timing_boundary_comparable
            and cache_comparable
            and timing_valid
            and not nonpositive_e2e
        )

        dec_sp = (
            _safe_ratio(r["decode_seconds"], p["decode_seconds"])
            if (decode_comparable and r["decode_seconds"] is not None and p["decode_seconds"] is not None)
            else None
        )
        e2e_sp = (
            _safe_ratio(r["e2e_seconds"], p["e2e_seconds"])
            if (e2e_comparable and r["e2e_seconds"] is not None and p["e2e_seconds"] is not None)
            else None
        )

        per_query.append({
            "id": rid,
            "occurrence": occ,
            "category": r["category"],
            "is_tool": r["is_tool"],
            "missing_in_pilot": False,
            "identical": identical,
            "tokens_identical": tokens_identical,
            "cand_tokens_identical": cand_tokens_identical,
            "ar_tokens_identical": ar_tokens_identical,
            "ar_self_identical": ar_self_identical,
            "path_identical": path_identical,
            "logit_identical": logit_identical,
            "cand_logit_identical": cand_logit_identical,
            "ar_logit_identical": ar_logit_identical,
            "kv_identical": kv_identical,
            "cand_kv_identical": cand_kv_identical,
            "ar_kv_identical": ar_kv_identical,
            "status_ok": status_ok,
            "rc13_source_format": r.get("source_format"),
            "pilot_source_format": p.get("source_format"),
            "rc13_speculate": r.get("speculate"),
            "pilot_speculate": p.get("speculate"),
            "speculate_ok": speculate_ok,
            "first_diff_index": diff_idx,
            "rc13_token_count": len(r["tokens"]) if r["tokens"] is not None else None,
            "pilot_token_count": len(p["tokens"]) if p["tokens"] is not None else None,
            "rc13_prefix_tokens_reused": rc13_reused,
            "pilot_prefix_tokens_reused": pilot_reused,
            "cache_comparable": cache_comparable,
            "timing_boundary_comparable": timing_boundary_comparable,
            "timing_valid": timing_valid,
            "timing_issues": timing_issues,
            "decode_comparable": decode_comparable,
            "rc13_prefill_seconds": r["prefill_seconds"],
            "pilot_prefill_seconds": p["prefill_seconds"],
            "rc13_decode_seconds": r["decode_seconds"],
            "pilot_decode_seconds": p["decode_seconds"],
            "decode_speedup": dec_sp,
            "rc13_e2e_seconds": r["e2e_seconds"],
            "pilot_e2e_seconds": p["e2e_seconds"],
            "rc13_wall_seconds": r.get("wall_seconds"),
            "pilot_wall_seconds": p.get("wall_seconds"),
            "e2e_comparable": e2e_comparable,
            "e2e_speedup": e2e_sp,
        })

    extra_in_pilot: list[str] = []
    seen_pilot: dict[str, int] = {}
    for p in pilot_records:
        pid = p["id"]
        occ = seen_pilot.get(pid, 0)
        seen_pilot[pid] = occ + 1
        if occ >= len(rc13_groups.get(pid, [])):
            extra_in_pilot.append(pid)

    same_id_set = (not missing_in_pilot) and (not extra_in_pilot) and (len(rc13_records) == len(pilot_records))

    matched = [q for q in per_query if not q["missing_in_pilot"]]
    categories: dict[str, list[dict[str, Any]]] = {}
    for q in matched:
        categories.setdefault(q["category"], []).append(q)

    by_category = {cat: _summarize_group(items) for cat, items in categories.items()}
    source_formats: dict[str, list[dict[str, Any]]] = {}
    for q in matched:
        sf = (
            q["rc13_source_format"]
            if q["rc13_source_format"] == q["pilot_source_format"] and q["rc13_source_format"] is not None
            else f"{q['rc13_source_format']}->{q['pilot_source_format']}"
        )
        source_formats.setdefault(str(sf), []).append(q)
    by_source_format = {sf: _summarize_group(items) for sf, items in source_formats.items()}
    overall = _summarize_group(matched)
    tool_items = [q for q in matched if q["is_tool"]]
    tool_summary = _summarize_group(tool_items) if tool_items else None
    socket_tool_items = [
        q for q in tool_items
        if q.get("rc13_source_format") == "bench" and q.get("pilot_source_format") == "bench"
    ]
    raw_tool_items = [
        q for q in tool_items
        if q.get("rc13_source_format") == "pilot_cases" and q.get("pilot_source_format") == "pilot_cases"
    ]
    socket_tool_summary = (
        _summarize_group(socket_tool_items)
        if (socket_tool_items and raw_tool_items)
        else None
    )

    identical_count = sum(1 for q in per_query if q["identical"])
    failing_queries = [
        {
            "id": q["id"],
            "occurrence": q["occurrence"],
            "first_diff_index": q["first_diff_index"],
            "tokens_identical": q["tokens_identical"],
            "cand_tokens_identical": q["cand_tokens_identical"],
            "ar_tokens_identical": q["ar_tokens_identical"],
            "ar_self_identical": q["ar_self_identical"],
            "path_identical": q["path_identical"],
            "logit_identical": q["logit_identical"],
            "cand_logit_identical": q["cand_logit_identical"],
            "ar_logit_identical": q["ar_logit_identical"],
            "kv_identical": q["kv_identical"],
            "cand_kv_identical": q["cand_kv_identical"],
            "ar_kv_identical": q["ar_kv_identical"],
            "status_ok": q["status_ok"],
            "speculate_ok": q["speculate_ok"],
            "rc13_speculate": q["rc13_speculate"],
            "pilot_speculate": q["pilot_speculate"],
            "missing_in_pilot": q["missing_in_pilot"],
        }
        for q in per_query
        if not q["identical"]
    ]

    files_passed = all(r.get("file_passed", True) for r in rc13_records) and all(
        p.get("file_passed", True) for p in pilot_records
    )
    identity_ok = same_id_set and (identical_count == len(per_query)) and files_passed
    missing_decode_on_ok = any(
        q["status_ok"] and (q["rc13_decode_seconds"] is None or q["pilot_decode_seconds"] is None)
        for q in matched
    )
    missing_e2e_on_ok = any(
        q["status_ok"] and (q["rc13_e2e_seconds"] is None or q["pilot_e2e_seconds"] is None)
        for q in matched
    )
    mixed_timing_boundaries = any(
        not q.get("timing_boundary_comparable", True) for q in matched
    )
    cache_condition_mismatches = [
        {
            "id": q["id"],
            "occurrence": q["occurrence"],
            "rc13_prefix_tokens_reused": q["rc13_prefix_tokens_reused"],
            "pilot_prefix_tokens_reused": q["pilot_prefix_tokens_reused"],
        }
        for q in matched
        if not q.get("cache_comparable", True)
    ]
    invalid_timing_queries = [
        {
            "id": q["id"],
            "occurrence": q["occurrence"],
            "rc13_prefill_seconds": q["rc13_prefill_seconds"],
            "pilot_prefill_seconds": q["pilot_prefill_seconds"],
            "rc13_decode_seconds": q["rc13_decode_seconds"],
            "pilot_decode_seconds": q["pilot_decode_seconds"],
            "rc13_e2e_seconds": q["rc13_e2e_seconds"],
            "pilot_e2e_seconds": q["pilot_e2e_seconds"],
            "rc13_wall_seconds": q.get("rc13_wall_seconds"),
            "pilot_wall_seconds": q.get("pilot_wall_seconds"),
            "timing_issues": q.get("timing_issues", []),
        }
        for q in matched
        if not q.get("timing_valid", True)
    ]

    speculate_mismatches = [
        {
            "id": q["id"],
            "occurrence": q["occurrence"],
            "rc13_speculate": q["rc13_speculate"],
            "pilot_speculate": q["pilot_speculate"],
            "expected_rc13_speculate": (
                expected_rc13_speculate if q.get("rc13_source_format") == "bench" else None
            ),
            "expected_pilot_speculate": (
                expected_pilot_speculate if q.get("pilot_source_format") == "bench" else None
            ),
        }
        for q in matched
        if not q.get("speculate_ok", True)
    ]

    overall_dec_sp = overall["decode_speedup"]
    overall_e2e_sp = overall["e2e_speedup"]
    speed_ok = (
        not missing_decode_on_ok
        and not missing_e2e_on_ok
        and not mixed_timing_boundaries
        and not cache_condition_mismatches
        and not invalid_timing_queries
        and not speculate_mismatches
        and overall_dec_sp is not None
        and overall_e2e_sp is not None
        and overall_dec_sp >= min_decode_speedup
        and overall_e2e_sp >= min_e2e_speedup
    )

    reasons: list[str] = []
    if require_exact_identity and not identity_ok:
        detail_parts: list[str] = []
        if not same_id_set:
            detail_parts.append(f"missing={len(missing_in_pilot)}, extra={len(extra_in_pilot)}")
        if not files_passed:
            detail_parts.append("top-level passed=False")
        suffix = f", {', '.join(detail_parts)}" if detail_parts else ""
        reasons.append(f"identity failed ({identical_count}/{len(per_query)} identical{suffix})")
    if not speed_ok:
        if speculate_mismatches:
            affected = ", ".join(
                f"{m['id']} (rc13={m['rc13_speculate']!r}, pilot={m['pilot_speculate']!r})"
                for m in speculate_mismatches[:3]
            )
            if len(speculate_mismatches) > 3:
                affected += f", +{len(speculate_mismatches) - 3} more"
            reasons.append(
                f"unexpected socket speculate mode on {len(speculate_mismatches)}/{len(matched)} "
                f"matched queries: {affected}"
            )
        if mixed_timing_boundaries:
            reasons.append("mixed timing boundaries (matched RC1.3 and pilot records use different source formats)")
        if cache_condition_mismatches:
            mismatched_cache_items = [
                m for m in cache_condition_mismatches
                if m["rc13_prefix_tokens_reused"] != m["pilot_prefix_tokens_reused"]
            ]
            unmeasured_cache_items = [
                m for m in cache_condition_mismatches
                if m["rc13_prefix_tokens_reused"] is None and m["pilot_prefix_tokens_reused"] is None
            ]
            if mismatched_cache_items:
                reasons.append(
                    f"mismatched measured cache conditions (prefix_tokens_reused mismatch on "
                    f"{len(mismatched_cache_items)}/{len(matched)} matched queries)"
                )
            if unmeasured_cache_items:
                reasons.append(
                    f"unmeasured cache conditions (missing prefix_tokens_reused on "
                    f"{len(unmeasured_cache_items)}/{len(matched)} matched queries)"
                )
        if invalid_timing_queries:
            nonpositive_items = [
                m for m in invalid_timing_queries
                if "nonpositive" in (m.get("timing_issues") or [])
            ]
            inconsistent_items = [
                m for m in invalid_timing_queries
                if "inconsistent_socket" in (m.get("timing_issues") or [])
            ]
            if nonpositive_items:
                reasons.append(
                    f"invalid non-positive timing on {len(nonpositive_items)}/{len(matched)} successful matched queries"
                )
            if inconsistent_items:
                reasons.append(
                    f"inconsistent socket timing on {len(inconsistent_items)}/{len(matched)} matched queries"
                )
        if missing_decode_on_ok or missing_e2e_on_ok:
            reasons.append("speedup unavailable (missing required timing on successful matched query)")
        elif overall_dec_sp is None or overall_e2e_sp is None:
            if (
                not mixed_timing_boundaries
                and not cache_condition_mismatches
                and not invalid_timing_queries
                and not speculate_mismatches
            ):
                reasons.append("speedup unavailable (no matched queries or non-positive pilot duration)")
        elif overall_dec_sp < min_decode_speedup or overall_e2e_sp < min_e2e_speedup:
            reasons.append(
                f"slower than threshold (decode={overall_dec_sp:.6g}x < {min_decode_speedup:.2f}x "
                f"or e2e={overall_e2e_sp:.6g}x < {min_e2e_speedup:.2f}x)"
            )

    go = (identity_ok or not require_exact_identity) and speed_ok
    verdict = "GO" if go else "NO-GO"
    if go:
        go_line = (
            f"GO: {identical_count}/{len(per_query)} identical; "
            f"decode speedup {overall_dec_sp:.3f}x (>= {min_decode_speedup:.2f}x), "
            f"e2e speedup {overall_e2e_sp:.3f}x (>= {min_e2e_speedup:.2f}x)"
        )
    else:
        go_line = f"NO-GO: {'; '.join(reasons)}"

    matched_n = overall["n"]
    tool_n = tool_summary["n"] if tool_summary is not None else 0
    tool_e2e_n = tool_summary["e2e_n"] if tool_summary is not None else 0
    overall_e2e_n = overall["e2e_n"]
    non_tool_n = matched_n - tool_n
    matches_model_scope = (matched_n == MODELLED_WORKLOAD_CASES)
    coverage_note = (
        f"measured sample covers n={matched_n} matched queries (tool={tool_n}, non_tool={non_tool_n}) vs "
        f"{MODELLED_WORKLOAD_CASES}-case full-workload E2E model; 1.31x (tool) and 1.065x (overall) are E2E "
        f"values vs v9h (0.884x separately modelled overall speculative decode)"
    )

    return {
        "thresholds": {
            "require_exact_identity": require_exact_identity,
            "min_decode_speedup": min_decode_speedup,
            "min_e2e_speedup": min_e2e_speedup,
            "expected_rc13_speculate": expected_rc13_speculate,
            "expected_pilot_speculate": expected_pilot_speculate,
            "modelled_tool_e2e_speedup": MODELLED_TOOL_E2E_SPEEDUP,
            "modelled_overall_e2e_speedup": MODELLED_OVERALL_E2E_SPEEDUP,
            "modelled_overall_decode_speedup": MODELLED_OVERALL_DECODE_SPEEDUP,
            "modelled_workload_cases": MODELLED_WORKLOAD_CASES,
            "modelled_tool_speedup": MODELLED_TOOL_SPEEDUP,
            "modelled_overall_speedup": MODELLED_OVERALL_SPEEDUP,
        },
        "identity": {
            "total_queries": len(per_query),
            "identical_queries": identical_count,
            "same_id_set": same_id_set,
            "missing_in_pilot": missing_in_pilot,
            "extra_in_pilot": extra_in_pilot,
            "passed": identity_ok,
            "failing_queries": failing_queries,
        },
        "speculate_mismatches": speculate_mismatches,
        "cache_condition_mismatches": cache_condition_mismatches,
        "invalid_timings": invalid_timing_queries,
        "per_query": per_query,
        "by_category": by_category,
        "by_source_format": by_source_format,
        "overall": overall,
        "measured_vs_modelled": {
            "scope": {
                "measured_cases": matched_n,
                "measured_tool_cases": tool_n,
                "measured_socket_tool_cases": len(socket_tool_items),
                "measured_raw_tool_cases": len(raw_tool_items),
                "measured_non_tool_cases": non_tool_n,
                "measured_categories": sorted(by_category.keys()),
                "measured_source_formats": sorted(by_source_format.keys()),
                "modelled_workload_cases": MODELLED_WORKLOAD_CASES,
                "matches_model_scope": matches_model_scope,
                "modelled_overall_decode_speedup": MODELLED_OVERALL_DECODE_SPEEDUP,
                "note": coverage_note,
            },
            "tool": (
                _model_comparison(
                    tool_summary["e2e_speedup"],
                    MODELLED_TOOL_E2E_SPEEDUP,
                    measured_n=tool_e2e_n,
                    measured_scope=f"measured tool sample (n={tool_e2e_n})",
                    model_scope="tool E2E model vs v9h",
                )
                if tool_summary is not None
                else None
            ),
            **(
                {
                    "socket_tool": _model_comparison(
                        socket_tool_summary["e2e_speedup"],
                        MODELLED_TOOL_E2E_SPEEDUP,
                        measured_n=socket_tool_summary["e2e_n"],
                        measured_scope=f"measured socket tool sample (n={socket_tool_summary['e2e_n']})",
                        model_scope="tool E2E model vs v9h",
                    )
                }
                if socket_tool_summary is not None
                else {}
            ),
            "overall": _model_comparison(
                overall_e2e_sp,
                MODELLED_OVERALL_E2E_SPEEDUP,
                measured_n=overall_e2e_n,
                measured_scope=f"measured sample (n={overall_e2e_n}, tool={tool_e2e_n}, non_tool={non_tool_n})",
                model_scope=f"{MODELLED_WORKLOAD_CASES}-case workload E2E model vs v9h (decode modelled separately at {MODELLED_OVERALL_DECODE_SPEEDUP}x)",
            ),
        },
        "verdict": verdict,
        "go": go,
        "reasons": reasons,
        "go_line": go_line,
    }


def _fmt_opt(val: float | None, fmt: str = ".4f", suffix: str = "") -> str:
    if val is None:
        return "N/A"
    return f"{val:{fmt}}{suffix}"


def _fmt_tok(val: int | None) -> str:
    if val is None:
        return "N/A"
    return str(val)


def _fmt_group_timing(stats: dict[str, Any], kind: str) -> str:
    n_avail = stats.get(f"{kind}_n", stats["n"])
    if n_avail == 0:
        return f"{kind} N/A"
    rc13_tot = stats[f"rc13_{kind}_total_s"]
    pilot_tot = stats[f"pilot_{kind}_total_s"]
    sp = stats[f"{kind}_speedup"]
    suffix = f" [n={n_avail}/{stats['n']}]" if n_avail < stats["n"] else ""
    return f"{kind} {rc13_tot:.3f}s -> {pilot_tot:.3f}s ({_fmt_opt(sp, '.4f', 'x')}){suffix}"


def format_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    ident = report["identity"]
    lines.append("=== (a) Output Identity vs RC1.3 ===")
    lines.append(f"Identical: {ident['identical_queries']}/{ident['total_queries']} (pass={ident['passed']})")
    for q in report["per_query"]:
        if q["identical"]:
            status = "MATCH"
        elif q["missing_in_pilot"]:
            status = "MISSING"
        elif q["first_diff_index"] is not None:
            status = f"DIFF(idx={q['first_diff_index']})"
        elif not q["status_ok"]:
            status = "FAIL(status)"
        else:
            status = "DIFF"
        cache_suffix = ""
        rc13_reused = q.get("rc13_prefix_tokens_reused")
        pilot_reused = q.get("pilot_prefix_tokens_reused")
        if rc13_reused is not None or pilot_reused is not None or not q.get("cache_comparable", True):
            if not q.get("cache_comparable", True):
                cache_flag = (
                    " [CACHE-UNMEASURED]"
                    if (rc13_reused is None and pilot_reused is None)
                    else " [CACHE-MISMATCH]"
                )
            else:
                cache_flag = ""
            cache_suffix = f" | reused={_fmt_tok(rc13_reused)}/{_fmt_tok(pilot_reused)}{cache_flag}"
        timing_suffix = " [INVALID-TIMING]" if not q.get("timing_valid", True) else ""
        speculate_suffix = ""
        if not q.get("speculate_ok", True):
            speculate_suffix = (
                f" | speculate={q.get('rc13_speculate')!r}/{q.get('pilot_speculate')!r} "
                "[SPECULATE-MISMATCH]"
            )
        lines.append(
            f"  [{status}] {q['id']} | cat={q['category']} | "
            f"tokens={_fmt_tok(q['rc13_token_count'])}/{_fmt_tok(q['pilot_token_count'])} | "
            f"dec={_fmt_opt(q['rc13_decode_seconds'], '.3f', 's')}->{_fmt_opt(q['pilot_decode_seconds'], '.3f', 's')} ({_fmt_opt(q['decode_speedup'], '.4f', 'x')}) | "
            f"e2e={_fmt_opt(q['rc13_e2e_seconds'], '.3f', 's')}->{_fmt_opt(q['pilot_e2e_seconds'], '.3f', 's')} ({_fmt_opt(q['e2e_speedup'], '.4f', 'x')}){cache_suffix}{timing_suffix}{speculate_suffix}"
        )

    lines.append("")
    lines.append("=== (b) Decode & End-to-End Time per Category vs RC1.3 ===")
    for cat, stats in report["by_category"].items():
        lines.append(
            f"  {cat} (n={stats['n']}, id={stats['identical']}/{stats['n']}): "
            f"{_fmt_group_timing(stats, 'decode')}, "
            f"{_fmt_group_timing(stats, 'e2e')}"
        )
    by_sf = report.get("by_source_format") or {}
    if len(by_sf) > 1:
        for sf, stats in by_sf.items():
            lines.append(
                f"  SOURCE[{sf}] (n={stats['n']}, id={stats['identical']}/{stats['n']}): "
                f"{_fmt_group_timing(stats, 'decode')}, "
                f"{_fmt_group_timing(stats, 'e2e')}"
            )
    ov = report["overall"]
    if not ov or ov.get("n", 0) == 0:
        lines.append("  OVERALL (n=0): no matched queries")
    else:
        dec_part = (
            "decode N/A"
            if ov.get("decode_n", ov["n"]) == 0
            else (
                f"decode {ov['rc13_decode_total_s']:.3f}s -> {ov['pilot_decode_total_s']:.3f}s "
                f"({_fmt_opt(ov['decode_speedup'], '.4f', 'x')}, med {_fmt_opt(ov['decode_median_speedup'], '.4f', 'x')})"
                + (f" [n={ov['decode_n']}/{ov['n']}]" if ov.get("decode_n", ov["n"]) < ov["n"] else "")
            )
        )
        e2e_part = (
            "e2e N/A"
            if ov.get("e2e_n", ov["n"]) == 0
            else (
                f"e2e {ov['rc13_e2e_total_s']:.3f}s -> {ov['pilot_e2e_total_s']:.3f}s "
                f"({_fmt_opt(ov['e2e_speedup'], '.4f', 'x')}, med {_fmt_opt(ov['e2e_median_speedup'], '.4f', 'x')})"
                + (f" [n={ov['e2e_n']}/{ov['n']}]" if ov.get("e2e_n", ov["n"]) < ov["n"] else "")
            )
        )
        lines.append(f"  OVERALL (n={ov['n']}): {dec_part}, {e2e_part}")
    cache_mismatches = report.get("cache_condition_mismatches") or []
    if cache_mismatches:
        mismatched = [
            m for m in cache_mismatches
            if m["rc13_prefix_tokens_reused"] != m["pilot_prefix_tokens_reused"]
        ]
        unmeasured = [
            m for m in cache_mismatches
            if m["rc13_prefix_tokens_reused"] is None and m["pilot_prefix_tokens_reused"] is None
        ]
        if mismatched:
            summary_items = ", ".join(
                f"{m['id']} ({_fmt_tok(m['rc13_prefix_tokens_reused'])} vs {_fmt_tok(m['pilot_prefix_tokens_reused'])})"
                for m in mismatched
            )
            lines.append(
                f"  EXCLUDED (mismatched prefix_tokens_reused): {summary_items}"
            )
        if unmeasured:
            summary_items = ", ".join(m["id"] for m in unmeasured)
            lines.append(
                f"  EXCLUDED (missing prefix_tokens_reused): {summary_items}"
            )
    invalid_timings = report.get("invalid_timings") or []
    if invalid_timings:
        nonpositive_timings = [
            m for m in invalid_timings
            if "nonpositive" in (m.get("timing_issues") or []) or not m.get("timing_issues")
        ]
        inconsistent_timings = [
            m for m in invalid_timings
            if "inconsistent_socket" in (m.get("timing_issues") or [])
        ]
        if nonpositive_timings:
            summary_items = ", ".join(
                f"{m['id']} (dec={_fmt_opt(m['rc13_decode_seconds'], '.3f', 's')}/{_fmt_opt(m['pilot_decode_seconds'], '.3f', 's')}, "
                f"e2e={_fmt_opt(m['rc13_e2e_seconds'], '.3f', 's')}/{_fmt_opt(m['pilot_e2e_seconds'], '.3f', 's')})"
                for m in nonpositive_timings
            )
            lines.append(
                f"  EXCLUDED (non-positive timing): {summary_items}"
            )
        if inconsistent_timings:
            summary_items = ", ".join(
                f"{m['id']} (pre={_fmt_opt(m.get('rc13_prefill_seconds'), '.3f', 's')}/{_fmt_opt(m.get('pilot_prefill_seconds'), '.3f', 's')}, "
                f"dec={_fmt_opt(m['rc13_decode_seconds'], '.3f', 's')}/{_fmt_opt(m['pilot_decode_seconds'], '.3f', 's')}, "
                f"e2e={_fmt_opt(m['rc13_e2e_seconds'], '.3f', 's')}/{_fmt_opt(m['pilot_e2e_seconds'], '.3f', 's')}, "
                f"wall={_fmt_opt(m.get('rc13_wall_seconds'), '.3f', 's')}/{_fmt_opt(m.get('pilot_wall_seconds'), '.3f', 's')})"
                for m in inconsistent_timings
            )
            lines.append(
                f"  EXCLUDED (inconsistent socket timing): {summary_items}"
            )
    spec_mismatches = report.get("speculate_mismatches") or []
    if spec_mismatches:
        summary_items = ", ".join(
            f"{m['id']} (rc13={m['rc13_speculate']!r} vs pilot={m['pilot_speculate']!r})"
            for m in spec_mismatches
        )
        lines.append(
            f"  EXCLUDED (unexpected speculate mode): {summary_items}"
        )

    lines.append("")
    lines.append("=== (c) Measured vs Modelled E2E Speedup (vs v9h) ===")
    mvm = report["measured_vs_modelled"]
    scope = mvm["scope"]
    lines.append(f"  Scope:       {scope['note']}")
    if mvm["tool"] is not None:
        t = mvm["tool"]
        lines.append(
            f"  Tool E2E:    e2e={_fmt_opt(t['measured_e2e_speedup'], '.4f', 'x')} "
            f"vs modelled {t['modelled_speedup']}x "
            f"(e2e/model={_fmt_opt(t['e2e_measured_over_modelled'], '.4f', 'x')}, "
            f"delta={_fmt_opt(t['e2e_delta_vs_modelled'], '+.4f', 'x')})"
        )
    if mvm.get("socket_tool") is not None:
        st = mvm["socket_tool"]
        lines.append(
            f"  Socket Tool E2E: e2e={_fmt_opt(st['measured_e2e_speedup'], '.4f', 'x')} "
            f"vs modelled {st['modelled_speedup']}x "
            f"(e2e/model={_fmt_opt(st['e2e_measured_over_modelled'], '.4f', 'x')}, "
            f"delta={_fmt_opt(st['e2e_delta_vs_modelled'], '+.4f', 'x')})"
        )
    o = mvm["overall"]
    lines.append(
        f"  Overall E2E: e2e={_fmt_opt(o['measured_e2e_speedup'], '.4f', 'x')} "
        f"vs modelled {o['modelled_speedup']}x "
        f"(e2e/model={_fmt_opt(o['e2e_measured_over_modelled'], '.4f', 'x')}, "
        f"delta={_fmt_opt(o['e2e_delta_vs_modelled'], '+.4f', 'x')})"
    )

    lines.append("")
    lines.append("=== (d) Decision ===")
    lines.append(report["go_line"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("positional", nargs="*", help="Optional positional: RC13_PATH PILOT_PATH [OUT_JSON]")
    ap.add_argument("--rc13", type=Path, nargs="+", help="RC1.3 reference board result file(s)")
    ap.add_argument("--pilot", type=Path, nargs="+", help="Candidate pilot board result file(s)")
    ap.add_argument(
        "--rc13-arm",
        type=str,
        default=None,
        help="Wrapper key to select from wrapped RC1.3 archive JSON (e.g. 'shared' or 'rc13')",
    )
    ap.add_argument(
        "--pilot-arm",
        type=str,
        default=None,
        help="Wrapper key to select from wrapped pilot archive JSON",
    )
    ap.add_argument(
        "--rc13-cold-baseline",
        action="store_true",
        help=(
            "Treat uniformly omitted prefix_tokens_reused on --rc13 bench rows as cold (0 reused) "
            "for extracted pre-template-cache RC1.3 archives/logs (never overrides explicit null or --pilot)"
        ),
    )
    ap.add_argument("--out", type=Path, help="Optional JSON output path")
    ap.add_argument("--min-decode-speedup", type=float, default=MIN_DECODE_SPEEDUP)
    ap.add_argument("--min-e2e-speedup", type=float, default=MIN_E2E_SPEEDUP)
    ap.add_argument("--check", action="store_true", help="Exit with code 1 when verdict is NO-GO")
    args = ap.parse_args(argv)

    rc13_paths = args.rc13
    pilot_paths = args.pilot
    out_path = args.out
    if args.positional:
        if rc13_paths or pilot_paths:
            ap.error("Do not mix positional paths with --rc13/--pilot")
        if len(args.positional) not in (2, 3):
            ap.error("Positional usage: RC13_PATH PILOT_PATH [OUT_JSON]")
        rc13_paths = [Path(args.positional[0])]
        pilot_paths = [Path(args.positional[1])]
        if len(args.positional) == 3 and out_path is None:
            out_path = Path(args.positional[2])
    if not rc13_paths or not pilot_paths:
        ap.error("Provide --rc13 and --pilot (or two positional paths)")

    report = analyze(
        load_records(
            rc13_paths,
            arm=args.rc13_arm,
            allow_legacy_cold_arm=True,
            cold_baseline=args.rc13_cold_baseline,
        ),
        load_records(
            pilot_paths,
            arm=args.pilot_arm,
            allow_legacy_cold_arm=False,
            cold_baseline=False,
        ),
        min_decode_speedup=args.min_decode_speedup,
        min_e2e_speedup=args.min_e2e_speedup,
    )
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(format_report(report))
    if args.check and not report["go"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
