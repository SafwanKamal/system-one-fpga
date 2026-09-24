"""Train one student, quantise it, verify it, and export the Phase 2 artefact.

This is the script that produces the thing the RTL is built against. Running it
end to end gives: a trained float model, a calibrated temperature, an integer
model, a bit-exactness check against a scalar reference, measured accumulator
widths, latency budgets, and an export directory whose manifest hashes everything.

    uv run python scripts/train_student.py --buckets 8192 --dim 64 --hidden 96 --bits 8
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from sysone.data import load_clinc150, majority_floor            # noqa: E402
from sysone.hw_estimate import (HwAssumptions, budget_table,     # noqa: E402
                                corpus_payload_stats, resource_estimate)
from sysone.manifest import export, verify                       # noqa: E402
from sysone.metrics import evaluate                              # noqa: E402
from sysone.model import ModelConfig, encode, softmax            # noqa: E402
from sysone.quant import QuantConfig, calibrate_and_quantize     # noqa: E402
from sysone.train import fit_temperature, train                  # noqa: E402
from tests.test_bitexact import accumulator_widths, ref_forward_scalar  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--buckets", type=int, default=8192)
    ap.add_argument("--dim", type=int, default=64)
    ap.add_argument("--hidden", type=int, default=96)
    ap.add_argument("--bits", type=int, default=8, help="embedding table width")
    ap.add_argument("--head-bits", type=int, default=8)
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--qat", action="store_true")
    ap.add_argument("--oos-weight", type=float, default=10.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-bigrams", action="store_true")
    ap.add_argument("--trigrams", action="store_true")
    ap.add_argument("--char-ngrams", default=None,
                    help="e.g. 3-5 to add character n-grams of length 3 to 5")
    ap.add_argument("--max-tokens", type=int, default=64,
                    help="hardware budget: memory reads per inference")
    ap.add_argument("--out", default="export/student")
    args = ap.parse_args()

    ds = load_clinc150()
    floor, floor_cls = majority_floor(ds.test, ds.n_classes)
    char = None
    if args.char_ngrams:
        lo, hi = (int(x) for x in args.char_ngrams.split("-"))
        char = (lo, hi)
    cfg = ModelConfig(n_buckets=args.buckets, dim=args.dim, hidden=args.hidden,
                      n_classes=ds.n_classes, seed=args.seed,
                      use_bigrams=not args.no_bigrams, use_trigrams=args.trigrams,
                      char_ngrams=char, max_tokens=args.max_tokens)
    print(f"features: unigram"
          + ("" if args.no_bigrams else " + bigram")
          + (" + trigram" if args.trigrams else "")
          + (f" + char {char[0]}-{char[1]}" if char else "")
          + f", max {args.max_tokens} reads/inference")
    print(f"model: V={cfg.n_buckets} D={cfg.dim} H={cfg.hidden} K={cfg.n_classes}  "
          f"{cfg.n_params:,} params ({cfg.head_params:,} in the head)")
    print(f"test majority floor: {floor:.4f} (always predict '{ds.labels[floor_cls]}')")

    cw = np.ones(ds.n_classes, np.float32)
    cw[ds.oos_id] = args.oos_weight
    qbits = (args.bits, args.head_bits, args.head_bits)

    model, info = train(cfg, ds.train.texts, ds.train.y, ds.val.texts, ds.val.y,
                        epochs=args.epochs, class_weight=cw,
                        qat_bits=qbits if args.qat else None)
    print(f"best val acc {info['best_val_acc']:.4f} at epoch {info['best_epoch']} "
          f"({info['train_seconds']:.1f}s)")

    va_f, va_o = encode(ds.val.texts, cfg)
    te_f, te_o = encode(ds.test.texts, cfg)

    T = fit_temperature(model.logits(va_f, va_o), ds.val.y)
    print(f"temperature (val NLL optimum): {T:.4f}")

    r_f32 = evaluate(softmax(model.logits(te_f, te_o) / T), ds.test.y,
                     ds.test.is_oos, ds.oos_id, floor)
    qm = calibrate_and_quantize(model, va_f, va_o, QuantConfig(
        emb_bits=qbits[0], w1_bits=qbits[1], w2_bits=qbits[2], temperature=T))
    r_int = evaluate(qm.predict_proba(te_f, te_o), ds.test.y, ds.test.is_oos,
                     ds.oos_id, floor)

    print("\n                         float32    integer")
    for k in ("combined_accuracy", "in_scope_accuracy", "oos_recall", "brier",
              "nll", "ece_equal_width", "ece_equal_mass", "oos_auroc_by_maxprob"):
        print(f"  {k:24s} {r_f32[k]:.4f}     {r_int[k]:.4f}")

    # --- bit-exactness against the scalar reference -------------------------
    vec = qm.forward_int(te_f, te_o)
    mism = sum(1 for i in range(200)
               if ref_forward_scalar(qm, [int(x) for x in te_f[te_o[i]:te_o[i + 1]]])
               != [int(x) for x in vec[i]])
    print(f"\nbit-exact vs scalar reference: {200 - mism}/200 inputs identical")
    if mism:
        print("  REFUSING TO EXPORT: the golden model disagrees with itself.")
        return 1

    widths = accumulator_widths(qm, te_f, te_o)
    print(f"measured accumulator widths: pooled={widths['pooled_bits']}b "
          f"acc1={widths['acc1_bits']}b acc2={widths['acc2_bits']}b "
          f"requant_product={max(widths['requant1_product_bits'], widths['requant2_product_bits'])}b")

    # --- latency budget -----------------------------------------------------
    tok_counts = np.diff(te_o)
    stats = corpus_payload_stats(ds.test.texts, tok_counts)
    in_bram = qm.storage_bits()["total_KiB"] <= 607.5
    budgets = budget_table(stats, cfg.dim, cfg.hidden, cfg.n_classes,
                           qbits[0], in_bram)
    print(f"\nlatency budget (embedding in {'BRAM' if in_bram else 'DDR2'}, "
          f"mean {stats['tokens_mean']:.1f} features / {stats['chars_mean']:.1f} chars):")
    for b in budgets:
        print(f"  {b['framing']:28s} {b['link']:9s} compute {b['compute_us']:8.2f} us  "
              f"transport {b['transport_us']:9.2f} us  "
              f"transport is {b['transport_share'] * 100:5.1f}% of total")

    res = resource_estimate(cfg.dim, cfg.hidden, cfg.n_classes, qbits[0],
                            qbits[1], cfg.n_buckets)
    print(f"\nstorage: {qm.storage_bits()['total_KiB']:.1f} KiB "
          f"(BRAM available {res['bram_KiB_available']:.1f} KiB) -> "
          f"{'fits on chip' if in_bram else 'embedding must live in DDR2'}")

    # --- export -------------------------------------------------------------
    out = ROOT / args.out
    metrics = {"float32": {k: v for k, v in r_f32.items() if k != "reliability"},
               "integer": {k: v for k, v in r_int.items() if k != "reliability"},
               "temperature": T, "majority_floor": floor}
    export(qm, cfg, out, metrics=metrics, widths=widths,
           notes="CLINC150 (CC BY 3.0), 150 in-scope intents + oos as class 150.")
    ok, problems = verify(out)
    print(f"\nexported to {out.relative_to(ROOT)}/  manifest verify: "
          f"{'OK' if ok else problems}")

    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "student_report.json").write_text(json.dumps({
        "config": cfg.__dict__, "bits": list(qbits), "qat": args.qat,
        "temperature": T, "majority_floor": floor,
        "float32": {k: v for k, v in r_f32.items() if k != "reliability"},
        "integer": {k: v for k, v in r_int.items() if k != "reliability"},
        "reliability_int": r_int["reliability"],
        "accumulator_widths": widths, "payload_stats": stats,
        "latency_budgets": budgets, "resources": res,
        "storage": qm.storage_bits(),
    }, indent=2, default=float))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
