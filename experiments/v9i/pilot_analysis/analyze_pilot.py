"""Analyze v9i board pilot results against the RC1.3 (v9h) baseline.

GO / NO-GO thresholds (explicitly stated here; override via CLI flags if needed):
- REQUIRE_EXACT_IDENTITY = True
    100% output identity vs RC1.3 across every query/case (exact `generated_ids` /
    `tokens`, matching `path` / `logit_bits` / `kv_sha256` when present, and
    `ok=True`, `complete=True`). Any single token difference fails the pilot.
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
3. `pilot.json`: JSON object with `cases` list and terminal `passed=True` status (`experiments/dual_port/v9h_pilot.py`).

Usage:
    python analyze_pilot.py --rc13 RC13_BENCH --pilot PILOT_BENCH [--out OUT.json]
    python analyze_pilot.py RC13_BENCH PILOT_BENCH [OUT.json]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

# --- GO / NO-GO thresholds ---
REQUIRE_EXACT_IDENTITY = True
MIN_DECODE_SPEEDUP = 1.03
MIN_E2E_SPEEDUP = 1.00

# --- Modelled speedups vs v9h (docs/research/2026-11-21-attention-reclaim.md) ---
# 1.31x (tool) and 1.065x (overall, 181-case workload) are end-to-end (E2E) values;
# the research record separately models 0.884x overall speculative decode.
MODELLED_TOOL_E2E_SPEEDUP = 1.31
MODELLED_OVERALL_E2E_SPEEDUP = 1.065
MODELLED_OVERALL_DECODE_SPEEDUP = 0.884
MODELLED_WORKLOAD_CASES = 181
MODELLED_TOOL_SPEEDUP = MODELLED_TOOL_E2E_SPEEDUP
MODELLED_OVERALL_SPEEDUP = MODELLED_OVERALL_E2E_SPEEDUP


def _validate_pilot_file_status(raw: dict[str, Any], path: Path) -> None:
    if "passed" not in raw or not isinstance(raw["passed"], bool):
        raise ValueError(
            f"{path}: pilot.json missing boolean top-level 'passed' status "
            "(interrupted or incomplete snapshot)"
        )
    if "started_utc" in raw and not raw.get("finished_utc"):
        raise ValueError(
            f"{path}: pilot.json has 'started_utc' without terminal 'finished_utc' "
            "(interrupted snapshot)"
        )
    if raw.get("error"):
        raise ValueError(f"{path}: pilot.json failed with error: {raw['error']!r}")
    if raw["passed"] is not True:
        raise ValueError(f"{path}: pilot.json top-level status failed (passed={raw['passed']!r})")


def _load_single_file(path: Path) -> list[dict[str, Any]]:
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
        return [_normalize_bench_row(row, path) for row in raw]
    if isinstance(raw, dict) and isinstance(raw.get("cases"), list):
        _validate_pilot_file_status(raw, path)
        return [_normalize_pilot_case(case, path) for case in raw["cases"]]
    raise ValueError(f"{path}: unsupported JSON structure; expected list or dict with 'cases'")


def _normalize_bench_row(row: dict[str, Any], path: Path) -> dict[str, Any]:
    if "query" not in row:
        raise ValueError(f"{path}: bench row missing 'query'")
    tokens = row.get("generated_ids")
    if tokens is None:
        tokens = row.get("tokens")
    if tokens is None:
        raise ValueError(f"{path}: bench row for {row['query']!r} missing 'generated_ids'")
    prefill = float(row.get("prefill_seconds") or 0.0)
    decode = float(row["decode_seconds"])
    elapsed = row.get("elapsed_seconds")
    if elapsed is None:
        elapsed = row.get("wall_seconds")
    if elapsed is None:
        elapsed = prefill + decode
    category = row.get("domain") or row.get("category") or row.get("path") or "tool"
    return {
        "id": row["query"],
        "label": row["query"],
        "category": str(category),
        "is_tool": row.get("domain", "tool") == "tool",
        "source_format": "bench",
        "tokens": list(tokens),
        "ar_tokens": None,
        "path": row.get("path"),
        "logit_bits": None,
        "kv_sha256": None,
        "ok": bool(row.get("ok", True)),
        "complete": bool(row.get("complete", True)),
        "prefill_seconds": prefill,
        "decode_seconds": decode,
        "e2e_seconds": float(elapsed),
        "reused": row.get("prefix_tokens_reused"),
        "speculate": row.get("speculate"),
    }


def _normalize_pilot_case(case: dict[str, Any], path: Path) -> dict[str, Any]:
    if "key" not in case:
        raise ValueError(f"{path}: pilot.json case missing 'key'")
    cand = case.get("candidate") or case.get("spec") or case.get("ar")
    ar = case.get("ar")
    if not isinstance(cand, dict) or "tokens" not in cand:
        raise ValueError(f"{path}: pilot.json case {case['key']!r} missing candidate/ar tokens")
    prefill = float(case.get("prefill_seconds") or 0.0)
    decode = float(cand["decode_seconds"])
    domain = str(case.get("domain") or "workload")
    case_ok = (
        bool(case.get("identical", True))
        and bool(case.get("ar_equal_v9e", True))
        and bool(case.get("candidate_equal_v9e", True))
    )
    return {
        "id": str(case["key"]),
        "label": str(case.get("query") or case["key"]),
        "category": domain,
        "is_tool": domain == "tool",
        "source_format": "pilot_cases",
        "tokens": list(cand["tokens"]),
        "ar_tokens": list(ar["tokens"]) if isinstance(ar, dict) and "tokens" in ar else None,
        "path": None,
        "logit_bits": cand.get("logit_bits"),
        "kv_sha256": cand.get("kv_sha256"),
        "ok": case_ok,
        "complete": True,
        "prefill_seconds": prefill,
        "decode_seconds": decode,
        "e2e_seconds": prefill + decode,
        "reused": None,
        "speculate": None,
    }


def load_records(paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for p in paths:
        records.extend(_load_single_file(p))
    return records


def _first_diff_index(a: list[Any], b: list[Any]) -> int | None:
    for idx, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return idx
    if len(a) != len(b):
        return min(len(a), len(b))
    return None


def _safe_ratio(num: float, den: float) -> float | None:
    if den <= 0.0:
        return None
    return num / den


def _summarize_group(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {
            "n": 0,
            "identical": 0,
            "rc13_decode_total_s": 0.0,
            "pilot_decode_total_s": 0.0,
            "decode_speedup": None,
            "rc13_decode_median_s": None,
            "pilot_decode_median_s": None,
            "decode_median_speedup": None,
            "rc13_e2e_total_s": 0.0,
            "pilot_e2e_total_s": 0.0,
            "e2e_speedup": None,
            "rc13_e2e_median_s": None,
            "pilot_e2e_median_s": None,
            "e2e_median_speedup": None,
        }

    rc13_dec_list = [x["rc13_decode_seconds"] for x in items]
    pilot_dec_list = [x["pilot_decode_seconds"] for x in items]
    rc13_e2e_list = [x["rc13_e2e_seconds"] for x in items]
    pilot_e2e_list = [x["pilot_e2e_seconds"] for x in items]

    rc13_dec_tot = sum(rc13_dec_list)
    pilot_dec_tot = sum(pilot_dec_list)
    rc13_e2e_tot = sum(rc13_e2e_list)
    pilot_e2e_tot = sum(pilot_e2e_list)

    rc13_dec_med = statistics.median(rc13_dec_list)
    pilot_dec_med = statistics.median(pilot_dec_list)
    rc13_e2e_med = statistics.median(rc13_e2e_list)
    pilot_e2e_med = statistics.median(pilot_e2e_list)

    dec_speedup = _safe_ratio(rc13_dec_tot, pilot_dec_tot)
    e2e_speedup = _safe_ratio(rc13_e2e_tot, pilot_e2e_tot)
    dec_med_speedup = _safe_ratio(rc13_dec_med, pilot_dec_med)
    e2e_med_speedup = _safe_ratio(rc13_e2e_med, pilot_e2e_med)

    return {
        "n": len(items),
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


def analyze(
    rc13_records: list[dict[str, Any]],
    pilot_records: list[dict[str, Any]],
    *,
    min_decode_speedup: float = MIN_DECODE_SPEEDUP,
    min_e2e_speedup: float = MIN_E2E_SPEEDUP,
    require_exact_identity: bool = REQUIRE_EXACT_IDENTITY,
) -> dict[str, Any]:
    if not rc13_records or not pilot_records:
        raise ValueError("Both RC1.3 and pilot inputs must contain at least one record")

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
            missing_in_pilot.append(rid)
            per_query.append({
                "id": rid,
                "occurrence": occ,
                "category": r["category"],
                "is_tool": r["is_tool"],
                "missing_in_pilot": True,
                "identical": False,
                "tokens_identical": False,
                "path_identical": False,
                "logit_identical": False,
                "kv_identical": False,
                "status_ok": False,
                "first_diff_index": 0,
                "rc13_token_count": len(r["tokens"]),
                "pilot_token_count": 0,
                "rc13_prefill_seconds": r["prefill_seconds"],
                "pilot_prefill_seconds": 0.0,
                "rc13_decode_seconds": r["decode_seconds"],
                "pilot_decode_seconds": 0.0,
                "decode_speedup": None,
                "rc13_e2e_seconds": r["e2e_seconds"],
                "pilot_e2e_seconds": 0.0,
                "e2e_speedup": None,
            })
            continue

        tokens_identical = (r["tokens"] == p["tokens"])
        ar_self_identical = (p["ar_tokens"] == p["tokens"]) if p["ar_tokens"] is not None else True
        path_identical = (r["path"] == p["path"]) if (r["path"] is not None or p["path"] is not None) else True
        logit_identical = (
            (r["logit_bits"] == p["logit_bits"])
            if (r["logit_bits"] is not None and p["logit_bits"] is not None)
            else True
        )
        kv_identical = (
            (r["kv_sha256"] == p["kv_sha256"])
            if (r["kv_sha256"] is not None and p["kv_sha256"] is not None)
            else True
        )
        status_ok = bool(r["ok"] and r["complete"] and p["ok"] and p["complete"])
        identical = (
            tokens_identical
            and ar_self_identical
            and path_identical
            and logit_identical
            and kv_identical
            and status_ok
        )
        diff_idx = None if tokens_identical else _first_diff_index(r["tokens"], p["tokens"])
        dec_sp = _safe_ratio(r["decode_seconds"], p["decode_seconds"])
        e2e_sp = _safe_ratio(r["e2e_seconds"], p["e2e_seconds"])

        per_query.append({
            "id": rid,
            "occurrence": occ,
            "category": r["category"],
            "is_tool": r["is_tool"],
            "missing_in_pilot": False,
            "identical": identical,
            "tokens_identical": tokens_identical,
            "ar_self_identical": ar_self_identical,
            "path_identical": path_identical,
            "logit_identical": logit_identical,
            "kv_identical": kv_identical,
            "status_ok": status_ok,
            "first_diff_index": diff_idx,
            "rc13_token_count": len(r["tokens"]),
            "pilot_token_count": len(p["tokens"]),
            "rc13_prefill_seconds": r["prefill_seconds"],
            "pilot_prefill_seconds": p["prefill_seconds"],
            "rc13_decode_seconds": r["decode_seconds"],
            "pilot_decode_seconds": p["decode_seconds"],
            "decode_speedup": dec_sp,
            "rc13_e2e_seconds": r["e2e_seconds"],
            "pilot_e2e_seconds": p["e2e_seconds"],
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
    overall = _summarize_group(matched)
    tool_items = [q for q in matched if q["is_tool"]]
    tool_summary = _summarize_group(tool_items) if tool_items else None

    identical_count = sum(1 for q in per_query if q["identical"])
    failing_queries = [
        {
            "id": q["id"],
            "occurrence": q["occurrence"],
            "first_diff_index": q["first_diff_index"],
            "tokens_identical": q["tokens_identical"],
            "path_identical": q["path_identical"],
            "logit_identical": q["logit_identical"],
            "kv_identical": q["kv_identical"],
            "status_ok": q["status_ok"],
            "missing_in_pilot": q["missing_in_pilot"],
        }
        for q in per_query
        if not q["identical"]
    ]

    identity_ok = same_id_set and (identical_count == len(per_query))
    overall_dec_sp = overall["decode_speedup"]
    overall_e2e_sp = overall["e2e_speedup"]
    speed_ok = (
        overall_dec_sp is not None
        and overall_e2e_sp is not None
        and overall_dec_sp >= min_decode_speedup
        and overall_e2e_sp >= min_e2e_speedup
    )

    reasons: list[str] = []
    if require_exact_identity and not identity_ok:
        reasons.append(
            f"identity failed ({identical_count}/{len(per_query)} identical"
            + (f", missing={len(missing_in_pilot)}, extra={len(extra_in_pilot)}" if not same_id_set else "")
            + ")"
        )
    if not speed_ok:
        if overall_dec_sp is None or overall_e2e_sp is None:
            reasons.append("speedup unavailable (no matched queries or non-positive pilot duration)")
        else:
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
        "per_query": per_query,
        "by_category": by_category,
        "overall": overall,
        "measured_vs_modelled": {
            "scope": {
                "measured_cases": matched_n,
                "measured_tool_cases": tool_n,
                "measured_non_tool_cases": non_tool_n,
                "measured_categories": sorted(by_category.keys()),
                "modelled_workload_cases": MODELLED_WORKLOAD_CASES,
                "matches_model_scope": matches_model_scope,
                "modelled_overall_decode_speedup": MODELLED_OVERALL_DECODE_SPEEDUP,
                "note": coverage_note,
            },
            "tool": (
                _model_comparison(
                    tool_summary["e2e_speedup"],
                    MODELLED_TOOL_E2E_SPEEDUP,
                    measured_n=tool_n,
                    measured_scope=f"measured tool sample (n={tool_n})",
                    model_scope="tool E2E model vs v9h",
                )
                if tool_summary is not None
                else None
            ),
            "overall": _model_comparison(
                overall_e2e_sp,
                MODELLED_OVERALL_E2E_SPEEDUP,
                measured_n=matched_n,
                measured_scope=f"measured sample (n={matched_n}, tool={tool_n}, non_tool={non_tool_n})",
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


def format_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    ident = report["identity"]
    lines.append("=== (a) Output Identity vs RC1.3 ===")
    lines.append(f"Identical: {ident['identical_queries']}/{ident['total_queries']} (pass={ident['passed']})")
    for q in report["per_query"]:
        status = "MATCH" if q["identical"] else f"DIFF(idx={q['first_diff_index']})"
        lines.append(
            f"  [{status}] {q['id']} | cat={q['category']} | "
            f"tokens={q['rc13_token_count']}/{q['pilot_token_count']} | "
            f"dec={q['rc13_decode_seconds']:.3f}s->{q['pilot_decode_seconds']:.3f}s ({_fmt_opt(q['decode_speedup'], '.4f', 'x')}) | "
            f"e2e={q['rc13_e2e_seconds']:.3f}s->{q['pilot_e2e_seconds']:.3f}s ({_fmt_opt(q['e2e_speedup'], '.4f', 'x')})"
        )

    lines.append("")
    lines.append("=== (b) Decode & End-to-End Time per Category vs RC1.3 ===")
    for cat, stats in report["by_category"].items():
        lines.append(
            f"  {cat} (n={stats['n']}, id={stats['identical']}/{stats['n']}): "
            f"decode {stats['rc13_decode_total_s']:.3f}s -> {stats['pilot_decode_total_s']:.3f}s ({_fmt_opt(stats['decode_speedup'], '.4f', 'x')}), "
            f"e2e {stats['rc13_e2e_total_s']:.3f}s -> {stats['pilot_e2e_total_s']:.3f}s ({_fmt_opt(stats['e2e_speedup'], '.4f', 'x')})"
        )
    ov = report["overall"]
    if not ov or ov.get("n", 0) == 0:
        lines.append("  OVERALL (n=0): no matched queries")
    else:
        lines.append(
            f"  OVERALL (n={ov['n']}): "
            f"decode {ov['rc13_decode_total_s']:.3f}s -> {ov['pilot_decode_total_s']:.3f}s "
            f"({_fmt_opt(ov['decode_speedup'], '.4f', 'x')}, med {_fmt_opt(ov['decode_median_speedup'], '.4f', 'x')}), "
            f"e2e {ov['rc13_e2e_total_s']:.3f}s -> {ov['pilot_e2e_total_s']:.3f}s "
            f"({_fmt_opt(ov['e2e_speedup'], '.4f', 'x')}, med {_fmt_opt(ov['e2e_median_speedup'], '.4f', 'x')})"
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
        load_records(rc13_paths),
        load_records(pilot_paths),
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
