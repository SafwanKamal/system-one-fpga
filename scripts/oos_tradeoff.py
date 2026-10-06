"""In-scope accuracy vs out-of-scope recall for the exported model's decision rules.

    uv run python scripts/oos_tradeoff.py

No training: this uses the deployed export (src/sysone/deployed.py) and its integer logits, which is
exactly what the board sends back. It sweeps three rules that answer "oos" more
often than the plain argmax:

  max_prob    host side: oos if the top probability is below tau
  margin      board side: oos if top_logit - second_logit is below m. The RTL
              already outputs both logits, so this is one subtractor and one
              comparator, no probabilities needed.
  oos_offset  board side: add d to the oos logit before the argmax, i.e. an exact
              edit of B2[150] (+ d << 20) in requant_output_biases.mem

For each rule it picks operating points on the validation split, under a budget
of in-scope accuracy given up (0.5, 1, 2 and 5 points), and reports what they do
on the test split. Writes results/oos_tradeoff.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from rtl_pack import load_qm                                     # noqa: E402
from sysone.deployed import DEPLOYED_EXPORT  # noqa: E402
from sysone.data import load_clinc150, majority_floor            # noqa: E402
from sysone.hashing import encode_corpus                         # noqa: E402
from sysone.metrics import evaluate                              # noqa: E402
from sysone.model import softmax                                 # noqa: E402

BUDGETS = [0.005, 0.01, 0.02, 0.05]


def logits_for(qm, man, texts):
    m = man["model"]
    flat, offs = encode_corpus(texts, m["n_buckets"], m["use_bigrams"], m["max_tokens"],
                               m["use_trigrams"], tuple(m["char_ngrams"]))
    return qm.forward_int(flat, offs)


def rule_predictions(rule: str, logits: np.ndarray, s_out: float, oos: int, value: float):
    if rule == "oos_offset":
        l2 = logits.copy()
        l2[:, oos] += int(value)
        return l2.argmax(1), l2
    pred = logits.argmax(1)
    if rule == "max_prob":
        p = softmax(logits.astype(np.float64) * s_out)
        return np.where(p.max(1) < value, oos, pred), logits
    top2 = np.sort(logits, axis=1)[:, -2:]
    return np.where(top2[:, 1] - top2[:, 0] < value, oos, pred), logits


def rates(pred, split, oos):
    ins = ~split.is_oos
    return float((pred[ins] == split.y[ins]).mean()), float((pred[split.is_oos] == oos).mean())


def main() -> None:
    qm, man = load_qm(DEPLOYED_EXPORT)
    ds = load_clinc150()
    oos = ds.oos_id
    floor, _ = majority_floor(ds.test, ds.n_classes)
    lv = logits_for(qm, man, ds.val.texts)
    lt = logits_for(qm, man, ds.test.texts)
    s_out = qm.s_out

    grids = {
        "max_prob": np.linspace(0.0, 0.95, 191),
        "margin": np.arange(0, 12001, 50),
        "oos_offset": np.arange(0, 20001, 100),
    }

    val_in0, _ = rates(lv.argmax(1), ds.val, oos)
    test_in0, test_rec0 = rates(lt.argmax(1), ds.test, oos)
    out = {"argmax": {"in_scope_accuracy": test_in0, "oos_recall": test_rec0},
           "curves": {}, "operating_points": []}

    print(f"argmax: in-scope {test_in0:.4f}  OOS recall {test_rec0:.4f}\n")
    print(f"{'rule':11s} {'budget':>7s} {'value':>8s}  {'in-scope':>9s} {'OOS recall':>10s} "
          f"{'combined':>9s} {'ECE':>7s}")

    for rule, grid in grids.items():
        curve = []
        for v in grid:
            pred, _ = rule_predictions(rule, lt, s_out, oos, v)
            curve.append((float(v), *rates(pred, ds.test, oos)))
        out["curves"][rule] = curve

        for budget in BUDGETS:
            # largest OOS recall on validation within the in-scope budget
            best = None
            for v in grid:
                pred, _ = rule_predictions(rule, lv, s_out, oos, v)
                vin, vrec = rates(pred, ds.val, oos)
                if val_in0 - vin <= budget and (best is None or vrec > best[1]):
                    best = (v, vrec)
            v = best[0]
            pred, l2 = rule_predictions(rule, lt, s_out, oos, v)
            tin, trec = rates(pred, ds.test, oos)
            r = evaluate(softmax(l2.astype(np.float64) * s_out), ds.test.y, ds.test.is_oos,
                         oos, floor)
            combined = float((pred == ds.test.y).mean())
            point = {"rule": rule, "budget": budget, "value": float(v), "in_scope_accuracy": tin,
                     "oos_recall": trec, "combined_accuracy": combined,
                     "ece_equal_width": r["ece_equal_width"]}
            out["operating_points"].append(point)
            print(f"{rule:11s} {budget * 100:6.1f}% {v:8.3g}  {tin:9.4f} {trec:10.4f} "
                  f"{combined:9.4f} {r['ece_equal_width']:7.4f}")
        print()

    (ROOT / "results" / "oos_tradeoff.json").write_text(json.dumps(out, indent=2))
    print("wrote results/oos_tradeoff.json")


if __name__ == "__main__":
    main()
