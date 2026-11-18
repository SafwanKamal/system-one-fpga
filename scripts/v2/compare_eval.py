"""Compare completed Nexys/KR260 reports from the same frozen suite."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def compare(a: dict, b: dict) -> dict:
    if {a["backend"], b["backend"]} != {"nexys4ddr", "kr260"}:
        raise ValueError("Need one hardware report from each board")
    if not a.get("complete") or not b.get("complete"):
        raise ValueError("Partial runs cannot be compared")
    if not a.get("suite_sha256") or a["suite_sha256"] != b.get("suite_sha256"):
        raise ValueError("Reports use different or unfrozen suites")
    for report in (a, b):
        rows = report["cases"]
        if not rows or len({r["id"] for r in rows}) != len(rows):
            raise ValueError("Missing or duplicate cases")
        if report["verification"] != {"exact": len(rows), "total": len(rows)} or any(
                row["bit_exact"] is not True for row in rows):
            raise ValueError("Every case must pass the integer reference")
        if not report["clock_hz"] or report["clock_hz"] <= 0:
            raise ValueError("Positive measured board clock required")
    left, right = ({row["id"]: row for row in r["cases"]} for r in (a, b))
    if left.keys() != right.keys():
        raise ValueError("Reports contain different cases")
    for identifier, row in left.items():
        other = right[identifier]
        for field in ("dataset", "tokens", "ids_sha256", "hidden_sha256", "predictions"):
            if row[field] != other[field]:
                raise ValueError(f"Board disagreement at {identifier}: {field}")
    if a["stats"] != b["stats"]:
        raise ValueError("Accuracy/slot counts differ")
    nexys, kr = (a, b) if a["backend"] == "nexys4ddr" else (b, a)
    datasets = {}
    for dataset, stats in sorted(a["stats"].items()):
        entry = {"counts": stats,
                 "accuracy": stats["ok"] / stats["n"] if stats["n"] else None,
                 "slot_f1": 2 * stats["tp"] / (2 * stats["tp"] + stats["fp"] + stats["fn"])
                    if stats["tp"] + stats["fp"] + stats["fn"] else None}
        for report in (nexys, kr):
            rows = [r for r in report["cases"] if r["dataset"] == dataset]
            encoder = np.array([r["encoder_clocks"] for r in rows]) / report["clock_hz"] * 1000
            request = np.array([r["request_clocks"] for r in rows]) / report["clock_hz"] * 1000
            if not len(rows) or np.any(encoder <= 0) or np.any(request < encoder):
                raise ValueError("Invalid board timing counters")
            entry[report["backend"]] = {"requests": len(rows),
                "mean_tokens": float(np.mean([r["tokens"] for r in rows])),
                "encoder_mean_ms": float(encoder.mean()), "encoder_median_ms": float(np.median(encoder)),
                "encoder_p95_ms": float(np.percentile(encoder, 95)),
                "request_mean_ms": float(request.mean()),
                "host_round_trip_mean_ms": float(np.mean([r["host_round_trip_ms"] for r in rows])),
                "heads_mean_ms": float(np.mean([r["heads_ms"] for r in rows]))}
        entry["encoder_speedup"] = (entry["nexys4ddr"]["encoder_mean_ms"] /
                                    entry["kr260"]["encoder_mean_ms"])
        datasets[dataset] = entry
    return {"suite_sha256": a["suite_sha256"], "cases": len(left),
            "outputs_and_predictions_identical": True, "datasets": datasets,
            "clocks_hz": {r["backend"]: r["clock_hz"] for r in (nexys, kr)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs=2, type=Path)
    parser.add_argument("--out", type=Path, default=Path("build/v2/eval/comparison.json"))
    args = parser.parse_args()
    result = compare(*(json.loads(p.read_text(encoding="utf-8")) for p in args.reports))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines = [f"Matched {result['cases']} requests; hidden states, predictions and accuracy counts identical.",
        "", "| Dataset | Accuracy | Slot F1 | Nexys encoder mean ms | KR260 encoder mean ms | Speedup |",
        "|---|---:|---:|---:|---:|---:|"]
    for ds, row in result["datasets"].items():
        acc = "—" if row["accuracy"] is None else f"{row['accuracy']:.3f}"
        f1 = "—" if row["slot_f1"] is None else f"{row['slot_f1']:.3f}"
        lines.append(f"| {ds} | {acc} | {f1} | {row['nexys4ddr']['encoder_mean_ms']:.3f} | "
                     f"{row['kr260']['encoder_mean_ms']:.3f} | {row['encoder_speedup']:.2f}x |")
    lines += ["", "Speedup uses board counters and operating clocks. Host/heads timings are separate in JSON.",
              "Accuracy covers the frozen supervised test subset; automatic routing is not scored here."]
    text = "\n".join(lines) + "\n"
    args.out.with_suffix(".md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
