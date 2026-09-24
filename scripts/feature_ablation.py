"""Where does accuracy actually come from, and how much is left?

The DDR2 experiment showed capacity is not the constraint. This one asks the
follow-up: if not capacity, what? Two candidate answers, and they point at very
different hardware.

  * **Word order.** Bag-of-words with bigrams cannot tell "transfer from savings
    to checking" from "transfer from checking to savings". If order carries a lot
    of signal, the fix is an architecture with real sequence modelling -- a small
    transformer -- which is compute-hungry and parameter-light. That suits the
    board: 74% of the DSPs and 45x the compute budget are unused on Ethernet.
    Trigrams are the cheap probe for this. They add strictly more order
    information at no architectural cost, so if trigrams do nothing, order is
    probably not where the headroom is.

  * **Unseen words.** 39.8% of distinct test words never appear in training, and
    a word hash gives those a randomly-initialised row. If that is the constraint,
    the fix is character n-grams (compose unseen words from seen fragments) or
    pretrained embeddings (import outside knowledge) -- both cheap in compute,
    one cheap in memory.

A TF-IDF linear model is included as a reference point. It is a different model
family with a different failure profile, so it brackets how much of the remaining
gap is "this architecture" versus "this dataset with 100 examples per class".

    uv run python scripts/feature_ablation.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sysone.data import load_clinc150, majority_floor          # noqa: E402
from sysone.hashing import tokenize                            # noqa: E402
from sysone.metrics import evaluate                            # noqa: E402
from sysone.model import ModelConfig, encode, softmax          # noqa: E402
from sysone.quant import QuantConfig, calibrate_and_quantize   # noqa: E402
from sysone.train import fit_temperature, train                # noqa: E402

# max_tokens is a hardware budget: it bounds the memory reads per inference.
# Character n-grams multiply the feature count by ~6, so they need a larger
# budget, and that cost is reported rather than hidden.
VARIANTS = [
    ("unigram only",          dict(use_bigrams=False, max_tokens=64)),
    ("uni + bigram",          dict(use_bigrams=True,  max_tokens=64)),
    ("uni + bi + trigram",    dict(use_bigrams=True,  use_trigrams=True, max_tokens=96)),
    ("uni + char 3-5",        dict(use_bigrams=False, char_ngrams=(3, 5), max_tokens=256)),
    ("uni + bi + char 3-5",   dict(use_bigrams=True,  char_ngrams=(3, 5), max_tokens=256)),
    ("uni + bi + tri + char", dict(use_bigrams=True,  use_trigrams=True,
                                   char_ngrams=(3, 5), max_tokens=256)),
]


def oov_split(ds) -> np.ndarray:
    """Mask of test inputs containing at least one word unseen in training.

    Accuracy on this subset is the number that says whether unseen words are
    actually hurting, as opposed to merely being numerous.
    """
    vocab = set()
    for t in ds.train.texts:
        vocab.update(tokenize(t))
    return np.array([any(w not in vocab for w in tokenize(t)) for t in ds.test.texts])


def tfidf_reference(ds, floor) -> dict | None:
    """A different model family, as a bracket on what this dataset supports."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline, make_union
    except ImportError:
        return None
    feats = make_union(
        TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1),
        TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=2),
    )
    clf = make_pipeline(feats, LogisticRegression(C=10.0, max_iter=2000, n_jobs=-1))
    t0 = time.time()
    clf.fit(ds.train.texts, ds.train.y)
    p = clf.predict_proba(ds.test.texts)
    # LogisticRegression drops classes absent from training; re-expand to K columns.
    full = np.zeros((len(ds.test.y), ds.n_classes))
    full[:, clf.classes_] = p
    r = evaluate(full, ds.test.y, ds.test.is_oos, ds.oos_id, floor)
    r["seconds"] = time.time() - t0
    r["n_features"] = int(clf[:-1].transform(ds.train.texts[:1]).shape[1])
    return r


def main() -> None:
    ds = load_clinc150()
    floor, _ = majority_floor(ds.test, ds.n_classes)
    cw = np.ones(ds.n_classes, np.float32)
    cw[ds.oos_id] = 10.0
    has_oov = oov_split(ds)
    ins = ~ds.test.is_oos

    print(f"test inputs containing >=1 unseen word: {has_oov.mean():.1%} "
          f"({has_oov.sum()} of {len(has_oov)})")
    print(f"majority floor {floor:.4f}\n")
    print(f"{'features':24} {'feats/input':>11} {'MiB':>7} {'in-scope':>9} "
          f"{'seen':>7} {'has-OOV':>8} {'oosR':>6} {'ECE':>7}")

    rows = []
    for name, kw in VARIANTS:
        cfg = ModelConfig(n_buckets=2**17, dim=64, hidden=96,
                          n_classes=ds.n_classes, seed=0, **kw)
        model, _ = train(cfg, ds.train.texts, ds.train.y, ds.val.texts, ds.val.y,
                         epochs=16, class_weight=cw, verbose=False)
        va_f, va_o = encode(ds.val.texts, cfg)
        te_f, te_o = encode(ds.test.texts, cfg)
        T = fit_temperature(model.logits(va_f, va_o), ds.val.y)
        qm = calibrate_and_quantize(model, va_f, va_o, QuantConfig(
            emb_bits=8, w1_bits=8, w2_bits=8, temperature=T))
        probs = qm.predict_proba(te_f, te_o)
        r = evaluate(probs, ds.test.y, ds.test.is_oos, ds.oos_id, floor)

        pred = probs.argmax(1)
        acc_seen = float((pred[ins & ~has_oov] == ds.test.y[ins & ~has_oov]).mean())
        acc_oov = float((pred[ins & has_oov] == ds.test.y[ins & has_oov]).mean())
        fpi = float(np.diff(te_o).mean())
        mib = qm.storage_bits()["total_KiB"] / 1024

        rows.append({"features": name, "config": kw, "feats_per_input": fpi,
                     "storage_MiB": mib, "in_scope": r["in_scope_accuracy"],
                     "acc_no_oov": acc_seen, "acc_has_oov": acc_oov,
                     "oos_recall": r["oos_recall"], "ece": r["ece_equal_width"],
                     "brier": r["brier"], "temperature": T})
        print(f"{name:24} {fpi:>11.1f} {mib:>7.2f} {r['in_scope_accuracy']:>9.4f} "
              f"{acc_seen:>7.4f} {acc_oov:>8.4f} {r['oos_recall']:>6.3f} "
              f"{r['ece_equal_width']:>7.4f}", flush=True)

    print("\n=== reference: TF-IDF word(1,2) + char_wb(3,5) -> logistic regression ===")
    ref = tfidf_reference(ds, floor)
    if ref is None:
        print("  sklearn unavailable, skipped")
    else:
        print(f"  in-scope {ref['in_scope_accuracy']:.4f}  oosR {ref['oos_recall']:.3f}  "
              f"ECE {ref['ece_equal_width']:.4f}  Brier {ref['brier']:.4f}  "
              f"({ref['n_features']:,} features, {ref['seconds']:.0f}s)")

    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "feature_ablation.json").write_text(json.dumps(
        {"variants": rows, "tfidf_reference": ref, "oov_input_rate": float(has_oov.mean())},
        indent=2, default=float))
    print("\nwrote results/feature_ablation.json")


if __name__ == "__main__":
    main()
