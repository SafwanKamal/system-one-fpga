"""Distil the transformer teacher into the board's own model (no RTL change).

    uv run python scripts/distill_board.py                    # needs export/v2/transformers/distill_roberta-base15.npz
    uv run python scripts/distill_board.py --seeds 0 --configs kd

The board model (hashed embedding bag, V=16384, D=64, H=256, INT4 table with QAT,
8-bit head) is trained on the teacher-labelled, MLM-augmented sentences from
augment_and_label.py instead of the 15k gold-labelled ones:

  * original sentences: target = alpha * one-hot(gold) + (1 - alpha) * teacher
  * augmented sentences: target = teacher

with the teacher's probabilities taken at ``--kd-temp`` times its calibrated
temperature. Optionally starts from the GloVe-pretrained table
(pretrained_study.py). Evaluated on the integer path like pretrained_study.py.

Writes results/distill_board.json.
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
sys.path.insert(0, str(ROOT / "scripts"))

from pretrained_study import CFG, KEYS, summarise                   # noqa: E402,F401
from sysone.data import load_clinc150, majority_floor               # noqa: E402
from sysone.hashing import tokenize                                 # noqa: E402
from sysone.metrics import evaluate                                 # noqa: E402
from sysone.model import ModelConfig, encode, softmax               # noqa: E402
from sysone.quant import QuantConfig, calibrate_and_quantize        # noqa: E402
from sysone.train import fit_temperature, train                     # noqa: E402

CONFIGS = {
    "baseline":  dict(kd=False, glove=False),
    "kd":        dict(kd=True, glove=False),
    "kd_glove":  dict(kd=True, glove=True),
}
ARGS = {}


def run_one(job: tuple) -> dict:
    name, seed = job
    c = CONFIGS[name]
    ds = load_clinc150()
    floor, _ = majority_floor(ds.test, ds.n_classes)
    oos = ds.oos_id
    cfg = ModelConfig(n_classes=ds.n_classes, seed=seed, **CFG)
    cw = np.ones(ds.n_classes, np.float32)
    cw[oos] = 10.0

    texts, y, soft = ds.train.texts, ds.train.y, None
    if c["kd"]:
        d = np.load(ROOT / "export" / "v2" / "transformers" / f"distill_{ARGS['teacher']}.npz",
                    allow_pickle=True)
        texts = list(d["texts"])
        p = softmax(d["logits"].astype(np.float64) / (float(d["temperature"]) * ARGS["kd_temp"]))
        hard = d["hard"]
        soft = p.astype(np.float32)
        orig = hard >= 0
        onehot = np.zeros_like(soft)
        onehot[np.where(orig)[0], hard[orig]] = 1.0
        a = ARGS["alpha"]
        soft[orig] = a * onehot[orig] + (1 - a) * soft[orig]
        y = np.where(orig, hard, p.argmax(1))
    init_E = np.load(ROOT / "export" / "pretrained_table.npy") if c["glove"] else None

    model, info = train(cfg, texts, y, ds.val.texts, ds.val.y, epochs=ARGS["epochs"],
                        class_weight=cw, qat_bits=(4, 8, 8), verbose=False,
                        init_E=init_E, soft_targets=soft)
    va_f, va_o = encode(ds.val.texts, cfg)
    te_f, te_o = encode(ds.test.texts, cfg)
    T = fit_temperature(model.logits(va_f, va_o), ds.val.y)
    qm = calibrate_and_quantize(model, va_f, va_o, QuantConfig(
        emb_bits=4, w1_bits=8, w2_bits=8, temperature=T))
    pv = softmax(qm.forward_int(va_f, va_o).astype(np.float64) * qm.s_out)
    pt = softmax(qm.forward_int(te_f, te_o).astype(np.float64) * qm.s_out)

    out = {"config": name, "variant": "full", "seed": seed, "best_epoch": info["best_epoch"]}
    r = evaluate(pt, ds.test.y, ds.test.is_oos, oos, floor)
    out["argmax"] = {k: r[k] for k in KEYS}
    ins_v = ~ds.val.is_oos
    base = float((pv.argmax(1)[ins_v] == ds.val.y[ins_v]).mean())
    best = (-1.0, 0.0)
    for tau in np.linspace(0, 0.95, 191):
        pred = np.where(pv.max(1) < tau, oos, pv.argmax(1))
        if base - float((pred[ins_v] == ds.val.y[ins_v]).mean()) <= 0.01:
            vrec = float((pred[ds.val.is_oos] == oos).mean())
            if vrec > best[0]:
                best = (vrec, float(tau))
    pred = np.where(pt.max(1) < best[1], oos, pt.argmax(1))
    ins = ~ds.test.is_oos
    out["tau_rule"] = {"threshold": best[1],
                       "in_scope_accuracy": float((pred[ins] == ds.test.y[ins]).mean()),
                       "oos_recall": float((pred[ds.test.is_oos] == oos).mean()),
                       "combined_accuracy": float((pred == ds.test.y).mean())}
    vocab = {w for t in ds.train.texts for w in tokenize(t)}
    sel = ins & np.array([any(w not in vocab for w in tokenize(t)) for t in ds.test.texts])
    out["unseen_word_subset"] = {"n": int(sel.sum()),
                                 "accuracy": float((pt.argmax(1)[sel] == ds.test.y[sel]).mean())}
    if ARGS.get("save") and seed == 0:
        np.save(ROOT / "export" / f"board_{name}_seed0_E.npy", model.E)
    print(f"done: {name:9s} seed {seed}  in-scope {out['argmax']['in_scope_accuracy']:.4f}  "
          f"tau combined {out['tau_rule']['combined_accuracy']:.4f}  unseen-word "
          f"{out['unseen_word_subset']['accuracy']:.4f}", flush=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", default="roberta-base")
    ap.add_argument("--kd-temp", type=float, default=1.0)
    ap.add_argument("--alpha", type=float, default=0.5)
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--configs", nargs="+", default=list(CONFIGS))
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--out", default=str(ROOT / "results" / "distill_board.json"))
    args = ap.parse_args()
    ARGS.update(vars(args))

    jobs = [(c, s) for c in args.configs for s in args.seeds]
    with Pool(args.workers, initializer=ARGS.update, initargs=(vars(args),)) as pool:
        rows = pool.map(run_one, jobs)
    import pretrained_study
    pretrained_study.CONFIGS = {k: (None, {}) for k in CONFIGS}
    summary = pretrained_study.summarise(rows)
    for e in summary:
        print(f"{e['config']:9s} in-scope {e['argmax.in_scope_accuracy']:.4f}±"
              f"{e['argmax.in_scope_accuracy_sd']:.4f}  tau: in-scope "
              f"{e['tau_rule.in_scope_accuracy']:.4f} OOS {e['tau_rule.oos_recall']:.4f} "
              f"combined {e['tau_rule.combined_accuracy']:.4f}  unseen-word "
              f"{e['unseen_word_subset.accuracy']:.4f}  ECE {e['argmax.ece_equal_width']:.4f}")
    Path(args.out).write_text(json.dumps({"args": vars(args), "summary": summary, "runs": rows},
                                         indent=2))


if __name__ == "__main__":
    main()
