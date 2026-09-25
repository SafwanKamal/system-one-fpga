"""Out-of-scope recall: which fixes work, measured over three seeds.

    uv run python scripts/oos_study.py                # all configurations, 3 seeds
    uv run python scripts/oos_study.py --seeds 0      # quick look

OOS recall is the model's known weak point (0.447 on seed 0, ~0.42 over three
seeds) while its OOS AUROC is 0.92, i.e. out-of-scope inputs are ranked low but
the argmax rarely lands on the oos class. That points at the decision rule rather
than the representation, so this compares two kinds of fix:

  training   the OOS class weight (10 today) and the 250-example OOS training set
             that ships with CLINC150 (data_oos_plus.json) instead of 100
  decision   rules applied to the board's integer logits, tuned on validation
             (max_prob also under a 1-point in-scope budget, max_prob_1pt):
             * oos_offset: add a constant to the oos logit before the argmax.
               On the board this is an exact edit of one number, B2[150] += d << 20,
               so it costs nothing and needs no RTL change.
             * max_prob: answer oos when the top probability is below a threshold.
               The host already computes probabilities from the logits it receives.

Decision rules are tuned on the validation split (3,000 in-scope + 100 OOS) to
maximise the mean of in-scope accuracy and OOS recall, then applied unchanged to
the test split. Only 100 validation OOS examples exist, so the tuned values are
noisy; that is part of what the seed spread shows.

Everything is evaluated on the integer path, i.e. what the RTL computes.
Writes results/oos_study.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sysone.data import load_clinc150, majority_floor               # noqa: E402
from sysone.metrics import evaluate                                 # noqa: E402
from sysone.model import ModelConfig, encode, softmax               # noqa: E402
from sysone.quant import QuantConfig, calibrate_and_quantize        # noqa: E402
from sysone.train import fit_temperature, train                     # noqa: E402

# name, OOS class weight, dataset variant
CONFIGS = [
    ("baseline (weight 10, 100 OOS)", 10.0, "full"),
    ("weight 30", 30.0, "full"),
    ("weight 100", 100.0, "full"),
    ("oos_plus (250 OOS), weight 10", 10.0, "oos_plus"),
    ("oos_plus, weight 30", 30.0, "oos_plus"),
]

KEYS = ["in_scope_accuracy", "oos_recall", "combined_accuracy", "ece_equal_width",
        "brier", "oos_auroc_by_maxprob"]


def balanced(pred: np.ndarray, y: np.ndarray, is_oos: np.ndarray, oos_id: int) -> float:
    ins = ~is_oos
    return 0.5 * (float((pred[ins] == y[ins]).mean()) + float((pred[is_oos] == oos_id).mean()))


def metrics_for(probs, pred, split, oos_id, floor) -> dict:
    r = evaluate(probs, split.y, split.is_oos, oos_id, floor)
    ins = ~split.is_oos
    # evaluate() scores the argmax of probs; override accuracy/recall for rules that
    # change the prediction without changing the probabilities
    r["in_scope_accuracy"] = float((pred[ins] == split.y[ins]).mean())
    r["oos_recall"] = float((pred[split.is_oos] == oos_id).mean())
    r["combined_accuracy"] = float((pred == split.y).mean())
    return {k: r[k] for k in KEYS}


def run_one(job: tuple) -> dict:
    name, oos_weight, variant, seed = job
    ds = load_clinc150(variant=variant)
    floor, _ = majority_floor(ds.test, ds.n_classes)
    oos = ds.oos_id

    cfg = ModelConfig(n_buckets=16384, dim=64, hidden=256, n_classes=ds.n_classes, seed=seed,
                      use_bigrams=True, use_trigrams=True, char_ngrams=(3, 5), max_tokens=256)
    cw = np.ones(ds.n_classes, np.float32)
    cw[oos] = oos_weight
    model, _ = train(cfg, ds.train.texts, ds.train.y, ds.val.texts, ds.val.y,
                     epochs=24, class_weight=cw, qat_bits=(4, 8, 8))

    va_f, va_o = encode(ds.val.texts, cfg)
    te_f, te_o = encode(ds.test.texts, cfg)
    T = fit_temperature(model.logits(va_f, va_o), ds.val.y)
    qm = calibrate_and_quantize(model, va_f, va_o, QuantConfig(
        emb_bits=4, w1_bits=8, w2_bits=8, temperature=T))

    lv = qm.forward_int(va_f, va_o)
    lt = qm.forward_int(te_f, te_o)
    pv = softmax(lv.astype(np.float64) * qm.s_out)
    pt = softmax(lt.astype(np.float64) * qm.s_out)

    out = {"config": name, "seed": seed, "oos_weight": oos_weight, "variant": variant}

    # argmax, as the board does today
    out["argmax"] = metrics_for(pt, pt.argmax(1), ds.test, oos, floor)

    # oos logit offset, in integer logit LSBs, tuned on validation
    best = (-1.0, 0)
    for d in range(0, 20001, 250):
        lv2 = lv.copy()
        lv2[:, oos] += d
        b = balanced(lv2.argmax(1), ds.val.y, ds.val.is_oos, oos)
        if b > best[0]:
            best = (b, d)
    d = best[1]
    lt2 = lt.copy()
    lt2[:, oos] += d
    pt2 = softmax(lt2.astype(np.float64) * qm.s_out)
    out["oos_offset"] = metrics_for(pt2, lt2.argmax(1), ds.test, oos, floor)
    out["oos_offset"]["offset_lsb"] = int(d)
    out["oos_offset"]["offset_logit"] = float(d * qm.s_out)

    # max-probability abstention, tuned on validation; probabilities unchanged
    best = (-1.0, 0.0)
    for tau in np.linspace(0.0, 0.95, 96):
        pred = np.where(pv.max(1) < tau, oos, pv.argmax(1))
        b = balanced(pred, ds.val.y, ds.val.is_oos, oos)
        if b > best[0]:
            best = (b, float(tau))
    tau = best[1]
    pred = np.where(pt.max(1) < tau, oos, pt.argmax(1))
    out["max_prob"] = metrics_for(pt, pred, ds.test, oos, floor)
    out["max_prob"]["threshold"] = tau

    # the same rule under a budget instead: the largest validation OOS recall that
    # gives up at most 1 point of validation in-scope accuracy
    val_in0 = float((pv.argmax(1)[~ds.val.is_oos] == ds.val.y[~ds.val.is_oos]).mean())
    best = (-1.0, 0.0)
    for tau in np.linspace(0.0, 0.95, 191):
        pred = np.where(pv.max(1) < tau, oos, pv.argmax(1))
        ins = ~ds.val.is_oos
        vin = float((pred[ins] == ds.val.y[ins]).mean())
        vrec = float((pred[ds.val.is_oos] == oos).mean())
        if val_in0 - vin <= 0.01 and vrec > best[0]:
            best = (vrec, float(tau))
    tau = best[1]
    pred = np.where(pt.max(1) < tau, oos, pt.argmax(1))
    out["max_prob_1pt"] = metrics_for(pt, pred, ds.test, oos, floor)
    out["max_prob_1pt"]["threshold"] = tau

    print(f"done: {name} seed {seed}", flush=True)
    return out


def summarise(rows: list[dict]) -> list[dict]:
    table = []
    for name, _, _ in CONFIGS:
        rs = [r for r in rows if r["config"] == name]
        if not rs:
            continue
        for rule in ("argmax", "oos_offset", "max_prob", "max_prob_1pt"):
            entry = {"config": name, "rule": rule, "seeds": len(rs)}
            for k in KEYS:
                v = np.array([r[rule][k] for r in rs])
                entry[k] = float(v.mean())
                entry[k + "_sd"] = float(v.std(ddof=1)) if len(v) > 1 else 0.0
            table.append(entry)
    return table


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    args = ap.parse_args()

    jobs = [(n, w, v, s) for n, w, v in CONFIGS for s in args.seeds]
    with Pool(args.workers) as pool:
        rows = pool.map(run_one, jobs)

    table = summarise(rows)
    print(f"\n{'configuration':32s} {'rule':11s} {'in-scope':>15s} {'OOS recall':>15s} "
          f"{'combined':>9s} {'ECE':>7s}")
    for e in table:
        print(f"{e['config']:32s} {e['rule']:11s} "
              f"{e['in_scope_accuracy']:.4f}±{e['in_scope_accuracy_sd']:.4f} "
              f"{e['oos_recall']:.4f}±{e['oos_recall_sd']:.4f} "
              f"{e['combined_accuracy']:9.4f} {e['ece_equal_width']:7.4f}")

    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "oos_study.json").write_text(json.dumps(
        {"seeds": args.seeds, "summary": table, "runs": rows}, indent=2))
    print("\nwrote results/oos_study.json")


if __name__ == "__main__":
    main()
