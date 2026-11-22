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

Modelled speedups vs v9h (from docs/research/2026-11-21-attention-reclaim.md):
- MODELLED_TOOL_SPEEDUP = 1.31
- MODELLED_OVERALL_SPEEDUP = 1.065

Supported RC1.3 / pilot board result formats:
1. `bench-<label>.json`: JSON list produced by `install_rc13.py bench` (21 tool queries).
2. `BENCH-JSON [...]`: stdout log containing a `BENCH-JSON ` line (`rc12_ship/compare.py`).
3. `pilot.json`: JSON object with `cases` list (`experiments/dual_port/v9h_pilot.py`).

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
MODELLED_TOOL_SPEEDUP = 1.31
MODELLED_OVERALL_SPEEDUP = 1.065


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
        "ok": bool(case.get("identical", True)),
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
        "rc13_decode_total_s": round(rc13_dec_tot, 4),
        "pilot_decode_total_s": round(pilot_dec_tot, 4),
        "decode_speedup": round(dec_speedup, 4) if dec_speedup is not None else None,
        "rc13_decode_median_s": round(rc13_dec_med, 4),
        "pilot_decode_median_s": round(pilot_dec_med, 4),
        "decode_median_speedup": round(dec_med_speedup, 4) if dec_med_speedup is not None else None,
        "rc13_e2e_total_s": round(rc13_e2e_tot, 4),
        "pilot_e2e_total_s": round(pilot_e2e_tot, 4),
        "e2e_speedup": round(e2e_speedup, 4) if e2e_speedup is not None else None,
        "rc13_e2e_median_s": round(rc13_e2e_med, 4),
        "pilot_e2e_median_s": round(pilot_e2e_med, 4),
        "e2e_median_speedup": round(e2e_med_speedup, 4) if e2e_med_speedup is not None else None,
    }


def _model_comparison(measured_decode: float | None, measured_e2e: float | None, modelled: float) -> dict[str, Any]:
    return {
        "modelled_speedup": modelled,
        "measured_decode_speedup": round(measured_decode, 4) if measured_decode is not None else None,
        "decode_measured_over_modelled": round(measured_decode / modelled, 4) if measured_decode is not None else None,
        "decode_delta_vs_modelled": round(measured_decode - modelled, 4) if measured_decode is not None else None,
        "measured_e2e_speedup": round(measured_e2e, 4) if measured_e2e is not None else None,
        "e2e_measured_over_modelled": round(measured_e2e / modelled, 4) if measured_e2e is not None else None,
        "e2e_delta_vs_modelled": round(measured_e2e - modelled, 4) if measured_e2e is not None else None,
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

    rc13_by_id = {r["id"]: r for r in rc13_records}
    pilot_by_id = {p["id"]: p for p in pilot_records}
    missing_in_pilot = [r["id"] for r in rc13_records if r["id"] not in pilot_by_id]
    extra_in_pilot = [p["id"] for p in pilot_records if p["id"] not in rc13_by_id]
    same_id_set = (not missing_in_pilot) and (not extra_in_pilot) and (len(rc13_records) == len(pilot_records))

    per_query: list[dict[str, Any]] = []
    for r in rc13_records:
        p = pilot_by_id.get(r["id"])
        if p is None:
            per_query.append({
                "id": r["id"],
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
                "rc13_prefill_seconds": round(r["prefill_seconds"], 4),
                "pilot_prefill_seconds": 0.0,
                "rc13_decode_seconds": round(r["decode_seconds"], 4),
                "pilot_decode_seconds": 0.0,
                "decode_speedup": None,
                "rc13_e2e_seconds": round(r["e2e_seconds"], 4),
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
            "id": r["id"],
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
            "rc13_prefill_seconds": round(r["prefill_seconds"], 4),
            "pilot_prefill_seconds": round(p["prefill_seconds"], 4),
            "rc13_decode_seconds": round(r["decode_seconds"], 4),
            "pilot_decode_seconds": round(p["decode_seconds"], 4),
            "decode_speedup": round(dec_sp, 4) if dec_sp is not None else None,
            "rc13_e2e_seconds": round(r["e2e_seconds"], 4),
            "pilot_e2e_seconds": round(p["e2e_seconds"], 4),
            "e2e_speedup": round(e2e_sp, 4) if e2e_sp is not None else None,
        })

    matched = [q for q in per_query if not q["missing_in_pilot"]]
    categories: dict[str, list[dict[str, Any]]] = {}
    for q in matched:
        categories.setdefault(q["category"], []).append(q)

    by_category = {cat: _summarize_group(items) for cat, items in categories.items()}
    overall = _summarize_group(matched) if matched else {}
    tool_items = [q for q in matched if q["is_tool"]]
    tool_summary = _summarize_group(tool_items) if tool_items else None

    identical_count = sum(1 for q in per_query if q["identical"])
    failing_queries = [
        {
            "id": q["id"],
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
    overall_dec_sp = overall.get("decode_speedup")
    overall_e2e_sp = overall.get("e2e_speedup")
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
        reasons.append(
            f"slower than threshold (decode={overall_dec_sp}x < {min_decode_speedup:.2f}x "
            f"or e2e={overall_e2e_sp}x < {min_e2e_speedup:.2f}x)"
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

    return {
        "thresholds": {
            "require_exact_identity": require_exact_identity,
            "min_decode_speedup": min_decode_speedup,
            "min_e2e_speedup": min_e2e_speedup,
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
            "tool": (
                _model_comparison(
                    tool_summary["decode_speedup"],
                    tool_summary["e2e_speedup"],
                    MODELLED_TOOL_SPEEDUP,
                )
                if tool_summary is not None
                else None
            ),
            "overall": _model_comparison(overall_dec_sp, overall_e2e_sp, MODELLED_OVERALL_SPEEDUP),
        },
        "verdict": verdict,
        "go": go,
        "reasons": reasons,
        "go_line": go_line,
    }


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
            f"dec={q['rc13_decode_seconds']:.3f}s->{q['pilot_decode_seconds']:.3f}s ({q['decode_speedup']}x) | "
            f"e2e={q['rc13_e2e_seconds']:.3f}s->{q['pilot_e2e_seconds']:.3f}s ({q['e2e_speedup']}x)"
        )

    lines.append("")
    lines.append("=== (b) Decode & End-to-End Time per Category vs RC1.3 ===")
    for cat, stats in report["by_category"].items():
        lines.append(
            f"  {cat} (n={stats['n']}, id={stats['identical']}/{stats['n']}): "
            f"decode {stats['rc13_decode_total_s']:.3f}s -> {stats['pilot_decode_total_s']:.3f}s ({stats['decode_speedup']}x), "
            f"e2e {stats['rc13_e2e_total_s']:.3f}s -> {stats['pilot_e2e_total_s']:.3f}s ({stats['e2e_speedup']}x)"
        )
    ov = report["overall"]
    lines.append(
        f"  OVERALL (n={ov['n']}): "
        f"decode {ov['rc13_decode_total_s']:.3f}s -> {ov['pilot_decode_total_s']:.3f}s ({ov['decode_speedup']}x, med {ov['decode_median_speedup']}x), "
        f"e2e {ov['rc13_e2e_total_s']:.3f}s -> {ov['pilot_e2e_total_s']:.3f}s ({ov['e2e_speedup']}x, med {ov['e2e_median_speedup']}x)"
    )

    lines.append("")
    lines.append("=== (c) Measured vs Modelled Speedup (vs v9h) ===")
    mvm = report["measured_vs_modelled"]
    if mvm["tool"] is not None:
        t = mvm["tool"]
        lines.append(
            f"  Tool:    decode={t['measured_decode_speedup']}x, e2e={t['measured_e2e_speedup']}x "
            f"vs modelled {t['modelled_speedup']}x (decode/model={t['decode_measured_over_modelled']}x)"
        )
    o = mvm["overall"]
    lines.append(
        f"  Overall: decode={o['measured_decode_speedup']}x, e2e={o['measured_e2e_speedup']}x "
        f"vs modelled {o['modelled_speedup']}x (decode/model={o['decode_measured_over_modelled']}x, "
        f"e2e/model={o['e2e_measured_over_modelled']}x)"
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
