"""Does pretrained word knowledge in the hashed table make the board model better?

    uv run python scripts/pretrained_study.py --vectors ../vec/glove300.gz
    uv run python scripts/pretrained_study.py --seeds 0 --configs baseline glove_ft   # quick

Same model, same hashing, same RTL as the board (V=16384, D=64, H=256, INT4 table
with QAT, 8-bit head, word 1-3 grams + char 3-5 grams, 256 features). The only
difference between configurations is what the embedding table starts from and how
freely CLINC150 training may move it (src/sysone/pretrain.py has the method).

Evaluated on the integer path, i.e. what the board computes, on:
  * full     CLINC150 as shipped (~100 training sentences per intent)
  * small    data_small.json (~50 per intent): a proxy for adding new intents
             from fewer examples, where pretrained knowledge should matter most
and, on the full-data models, on test utterances containing at least one word
that never occurs in the training set (the case pretraining is meant to fix).

Only the training split's vocabulary is used to choose which pretrained words to
load (besides the frequency-ordered head of the vector file); nothing about the
test set reaches pretraining.

Writes results/pretrained_study.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sysone.data import load_clinc150, majority_floor               # noqa: E402
from sysone.hashing import tokenize                                 # noqa: E402
from sysone.metrics import evaluate                                 # noqa: E402
from sysone.model import ModelConfig, encode, softmax               # noqa: E402
from sysone.pretrain import load_word2vec_text, pretrain_table, project  # noqa: E402
from sysone.quant import QuantConfig, calibrate_and_quantize        # noqa: E402
from sysone.train import fit_temperature, train                     # noqa: E402

CFG = dict(n_buckets=16384, dim=64, hidden=256, use_bigrams=True, use_trigrams=True,
           char_ngrams=(3, 5), max_tokens=256)

# name -> (table source, training knobs)
CONFIGS = {
    "baseline":      (None, dict()),
    "glove_ft":      ("glove", dict()),
    "glove_slow":    ("glove", dict(freeze_emb_epochs=3, emb_lr_scale=0.3)),
    "glove_anchor":  ("glove", dict(freeze_emb_epochs=3, emb_lr_scale=0.3, anchor_weight=1e-3)),
    "glove_frozen":  ("glove", dict(emb_lr_scale=0.0)),
}
KEYS = ["in_scope_accuracy", "oos_recall", "combined_accuracy", "ece_equal_width",
        "brier", "oos_auroc_by_maxprob"]
TABLES: dict[str, Path] = {}


def build_table(vectors: Path, n_words: int, scale: float, out: Path) -> dict:
    ds = load_clinc150()
    train_vocab = {w.decode() for t in ds.train.texts for w in tokenize(t)}
    words, V = load_word2vec_text(vectors, n_words, keep=train_vocab)
    Y, pinfo = project(V, CFG["dim"], scale)
    E, tinfo = pretrain_table(words, Y, CFG["n_buckets"], CFG["use_trigrams"],
                              CFG["char_ngrams"], CFG["max_tokens"])
    np.save(out, E)
    return {**pinfo, **tinfo, "vectors": str(vectors), "scale": scale}


def run_one(job: tuple) -> dict:
    name, variant, seed, table = job
    src, knobs = CONFIGS[name]
    ds = load_clinc150(variant=variant)
    floor, _ = majority_floor(ds.test, ds.n_classes)
    oos = ds.oos_id
    cfg = ModelConfig(n_classes=ds.n_classes, seed=seed, **CFG)
    cw = np.ones(ds.n_classes, np.float32)
    cw[oos] = 10.0
    init_E = None if src is None else np.load(table)
    t0 = time.time()
    model, info = train(cfg, ds.train.texts, ds.train.y, ds.val.texts, ds.val.y,
                        epochs=24, class_weight=cw, qat_bits=(4, 8, 8), verbose=False,
                        init_E=init_E, **knobs)

    va_f, va_o = encode(ds.val.texts, cfg)
    te_f, te_o = encode(ds.test.texts, cfg)
    T = fit_temperature(model.logits(va_f, va_o), ds.val.y)
    qm = calibrate_and_quantize(model, va_f, va_o, QuantConfig(
        emb_bits=4, w1_bits=8, w2_bits=8, temperature=T))
    lv = qm.forward_int(va_f, va_o).astype(np.float64) * qm.s_out
    lt = qm.forward_int(te_f, te_o).astype(np.float64) * qm.s_out
    pv, pt = softmax(lv), softmax(lt)

    out = {"config": name, "variant": variant, "seed": seed,
           "best_epoch": info["best_epoch"], "train_seconds": time.time() - t0}
    r = evaluate(pt, ds.test.y, ds.test.is_oos, oos, floor)
    out["argmax"] = {k: r[k] for k in KEYS}

    # the deployed decision rule: oos below a top-probability threshold, tuned on
    # validation to give up at most 1 point of in-scope accuracy
    ins_v = ~ds.val.is_oos
    base = float((pv.argmax(1)[ins_v] == ds.val.y[ins_v]).mean())
    best = (-1.0, 0.0)
    for tau in np.linspace(0, 0.95, 191):
        pred = np.where(pv.max(1) < tau, oos, pv.argmax(1))
        vin = float((pred[ins_v] == ds.val.y[ins_v]).mean())
        vrec = float((pred[ds.val.is_oos] == oos).mean())
        if base - vin <= 0.01 and vrec > best[0]:
            best = (vrec, float(tau))
    tau = best[1]
    pred = np.where(pt.max(1) < tau, oos, pt.argmax(1))
    ins = ~ds.test.is_oos
    out["tau_rule"] = {"threshold": tau,
                       "in_scope_accuracy": float((pred[ins] == ds.test.y[ins]).mean()),
                       "oos_recall": float((pred[ds.test.is_oos] == oos).mean()),
                       "combined_accuracy": float((pred == ds.test.y).mean())}

    # in-scope test utterances with a word the training split never contains
    train_vocab = {w for t in ds.train.texts for w in tokenize(t)}
    has_new = np.array([any(w not in train_vocab for w in tokenize(t)) for t in ds.test.texts])
    sel = ins & has_new
    out["unseen_word_subset"] = {"n": int(sel.sum()),
                                 "accuracy": float((pt.argmax(1)[sel] == ds.test.y[sel]).mean())}
    print(f"done: {name:13s} {variant:5s} seed {seed}  in-scope "
          f"{out['argmax']['in_scope_accuracy']:.4f}  unseen-word "
          f"{out['unseen_word_subset']['accuracy']:.4f}", flush=True)
    return out


def summarise(rows: list[dict]) -> list[dict]:
    table = []
    for variant in ("full", "small"):
        for name in CONFIGS:
            rs = [r for r in rows if r["config"] == name and r["variant"] == variant]
            if not rs:
                continue
            e = {"config": name, "variant": variant, "seeds": len(rs)}
            for path in [("argmax", k) for k in KEYS] + [
                    ("tau_rule", "in_scope_accuracy"), ("tau_rule", "oos_recall"),
                    ("tau_rule", "combined_accuracy"), ("unseen_word_subset", "accuracy")]:
                v = np.array([r[path[0]][path[1]] for r in rs])
                key = ".".join(path)
                e[key] = float(v.mean())
                e[key + "_sd"] = float(v.std(ddof=1)) if len(v) > 1 else 0.0
            table.append(e)
    return table


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vectors", default=str(ROOT.parent / "vec" / "glove300.gz"))
    ap.add_argument("--n-words", type=int, default=100000)
    ap.add_argument("--scale", type=float, default=0.1, help="RMS of the 64-d targets")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--variants", nargs="+", default=["full", "small"])
    ap.add_argument("--configs", nargs="+", default=list(CONFIGS))
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--out", default=str(ROOT / "results" / "pretrained_study.json"))
    args = ap.parse_args()

    table = ROOT / "export" / "pretrained_table.npy"
    table.parent.mkdir(exist_ok=True)
    table_info = build_table(Path(args.vectors), args.n_words, args.scale, table)
    print(f"pretrained table: {table_info}")

    jobs = [(c, v, s, str(table)) for v in args.variants for c in args.configs
            for s in args.seeds]
    with Pool(args.workers) as pool:
        rows = pool.map(run_one, jobs)

    summary = summarise(rows)
    print(f"\n{'config':14s} {'data':5s} {'in-scope':>15s} {'unseen-word':>15s} "
          f"{'OOS(tau)':>9s} {'ECE':>7s}")
    for e in summary:
        print(f"{e['config']:14s} {e['variant']:5s} "
              f"{e['argmax.in_scope_accuracy']:.4f}±{e['argmax.in_scope_accuracy_sd']:.4f} "
              f"{e['unseen_word_subset.accuracy']:.4f}±{e['unseen_word_subset.accuracy_sd']:.4f} "
              f"{e['tau_rule.oos_recall']:9.4f} {e['argmax.ece_equal_width']:7.4f}")
    Path(args.out).write_text(json.dumps(
        {"table": table_info, "args": vars(args), "summary": summary, "runs": rows}, indent=2))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
