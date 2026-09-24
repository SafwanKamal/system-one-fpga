"""Would a DDR2-scale model actually be better?

The board has 128 MiB of DDR2 and the recommended student uses 525 KiB of it --
0.4%. That looks like waste, so it deserves a real answer rather than an appeal to
the saturation curve, which only shows *that* accuracy flattens, not *why*.

Three things are measured here, because they distinguish three different
bottlenecks and the fix is different for each:

  1. **Feature inventory.** How many distinct hashed features does the corpus
     actually contain? A table with more rows than there are features cannot help:
     the extra rows are never addressed. If the inventory is small, the table is
     already big enough and DDR2 capacity is irrelevant.

  2. **Table size past the no-collision point.** Push V up to DDR2 scale and see
     whether accuracy moves once collisions are gone. This is the direct test.

  3. **Learning curve.** Train the same model on 10 / 25 / 50 / 100% of the data.
     If accuracy is still climbing at 100%, the binding constraint is training
     data, and more parameters would overfit rather than help.

    uv run python scripts/ddr2_headroom.py
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
from sysone.hashing import fnv1a32, hash_features, tokenize    # noqa: E402
from sysone.metrics import evaluate                            # noqa: E402
from sysone.model import ModelConfig, encode, softmax          # noqa: E402
from sysone.quant import QuantConfig, calibrate_and_quantize   # noqa: E402
from sysone.train import fit_temperature, train                # noqa: E402

DDR2_MIB = 128


def feature_inventory(ds) -> dict:
    """Count distinct features, before hashing, and how many are learnable.

    A feature seen once in training cannot have a useful embedding fitted to it,
    so the count that matters is not "distinct features" but "features with enough
    occurrences to train a row". Those are counted separately.
    """
    from collections import Counter

    uni, bi = Counter(), Counter()
    for t in ds.train.texts:
        words = tokenize(t)
        uni.update(words)
        bi.update(zip(words, words[1:]))

    test_uni = set()
    for t in ds.test.texts:
        test_uni.update(tokenize(t))
    oov = len(test_uni - set(uni)) / max(len(test_uni), 1)

    total = len(uni) + len(bi)
    out = {
        "unigram_types": len(uni), "bigram_types": len(bi),
        "total_feature_types": total,
        "unigrams_seen_once": sum(1 for v in uni.values() if v == 1),
        "bigrams_seen_once": sum(1 for v in bi.values() if v == 1),
        "features_seen_at_least_5x": sum(1 for v in uni.values() if v >= 5)
                                     + sum(1 for v in bi.values() if v >= 5),
        "test_unigram_oov_rate": oov,
        "table_rows_for_zero_collisions_approx": 1 << int(np.ceil(np.log2(total * 20))),
    }
    # Rows in a 128 MiB DDR2 table, for comparison.
    for D, bits in ((64, 8), (128, 8), (64, 4)):
        out[f"ddr2_rows_at_D{D}_{bits}b"] = int(DDR2_MIB * 1024 * 1024 * 8 / (D * bits))
    return out


def measured_collisions(ds, V: int, use_bigrams: bool = True) -> dict:
    """Actual occupancy of a table of V rows by the real feature stream."""
    used = np.zeros(V, dtype=np.int64)
    seen: dict[int, set] = {}
    for t in ds.train.texts:
        words = tokenize(t)
        feats = [fnv1a32(w) for w in words]
        if use_bigrams:
            for a, b in zip(feats, feats[1:]):
                m = ((a ^ 0x9E3779B9) * 0x01000193) & 0xFFFFFFFF
                feats.append(((m ^ b) * 0x01000193) & 0xFFFFFFFF)
        for h in feats:
            idx = h & (V - 1)
            used[idx] += 1
            seen.setdefault(idx, set()).add(h)
    n_types = sum(len(v) for v in seen.values())
    colliding = sum(len(v) for v in seen.values() if len(v) > 1)
    return {
        "V": V, "rows_ever_addressed": int((used > 0).sum()),
        "rows_never_addressed": int((used == 0).sum()),
        "fraction_of_table_wasted": float((used == 0).mean()),
        "distinct_features": n_types,
        "features_in_colliding_rows": colliding,
        "collision_rate": colliding / max(n_types, 1),
    }


def run(ds, cfg, cw, epochs, enc_cache, frac=1.0, seed=0):
    floor, _ = majority_floor(ds.test, ds.n_classes)
    tx, ty = ds.train.texts, ds.train.y
    if frac < 1.0:
        rng = np.random.default_rng(1234)
        keep = rng.permutation(len(ty))[:int(len(ty) * frac)]
        tx = [tx[i] for i in keep]
        ty = ty[keep]

    t0 = time.time()
    model, _ = train(cfg, tx, ty, ds.val.texts, ds.val.y, epochs=epochs,
                     class_weight=cw, verbose=False)
    if cfg.n_buckets not in enc_cache:
        enc_cache[cfg.n_buckets] = (encode(ds.val.texts, cfg), encode(ds.test.texts, cfg))
    (va_f, va_o), (te_f, te_o) = enc_cache[cfg.n_buckets]

    T = fit_temperature(model.logits(va_f, va_o), ds.val.y)
    qm = calibrate_and_quantize(model, va_f, va_o,
                                QuantConfig(emb_bits=8, w1_bits=8, w2_bits=8, temperature=T))
    r = evaluate(qm.predict_proba(te_f, te_o), ds.test.y, ds.test.is_oos, ds.oos_id, floor)
    r32 = evaluate(softmax(model.logits(te_f, te_o) / T), ds.test.y,
                   ds.test.is_oos, ds.oos_id, floor)
    train_acc = float((model.predict_proba(*encode(tx, cfg)).argmax(1) == ty).mean())
    return {"storage_MiB": qm.storage_bits()["total_KiB"] / 1024,
            "in_scope": r["in_scope_accuracy"], "f32_in_scope": r32["in_scope_accuracy"],
            "oos_recall": r["oos_recall"], "ece": r["ece_equal_width"],
            "brier": r["brier"], "train_acc": train_acc,
            "n_train": len(ty), "seconds": time.time() - t0}


def main() -> None:
    ds = load_clinc150()
    cw = np.ones(ds.n_classes, np.float32)
    cw[ds.oos_id] = 10.0
    enc_cache: dict = {}
    out: dict = {}

    print("=== 1. what features actually exist in the corpus ===")
    inv = feature_inventory(ds)
    out["inventory"] = inv
    for k, v in inv.items():
        print(f"  {k:42s} {v:,}" if isinstance(v, int) else f"  {k:42s} {v:.4f}")

    print("\n=== 2. how much of a large table is ever addressed ===")
    out["collisions"] = []
    for V in (2**15, 2**17, 2**19, 2**21):
        c = measured_collisions(ds, V)
        out["collisions"].append(c)
        print(f"  V={V:>9,}  addressed={c['rows_ever_addressed']:>8,}  "
              f"wasted={c['fraction_of_table_wasted']:6.2%}  "
              f"collision_rate={c['collision_rate']:.4f}")

    print("\n=== 3. does a DDR2-scale table help? (D=64, INT8) ===")
    print(f"{'V':>9} {'params':>12} {'MiB':>8} {'in-scope':>9} {'f32':>8} {'train':>8} {'ECE':>7}")
    out["big_tables"] = []
    for V in (2**15, 2**17, 2**19, 2**21):
        cfg = ModelConfig(n_buckets=V, dim=64, hidden=96, n_classes=ds.n_classes, seed=0)
        r = run(ds, cfg, cw, 16, enc_cache)
        r["V"] = V
        r["params"] = cfg.n_params
        out["big_tables"].append(r)
        print(f"{V:>9,} {cfg.n_params:>12,} {r['storage_MiB']:>8.2f} "
              f"{r['in_scope']:>9.4f} {r['f32_in_scope']:>8.4f} "
              f"{r['train_acc']:>8.4f} {r['ece']:>7.4f}", flush=True)

    print("\n=== 4. is the bottleneck training data? (V=131072, D=64) ===")
    print(f"{'train frac':>11} {'n':>7} {'in-scope':>9} {'train acc':>10} {'gap':>7}")
    out["learning_curve"] = []
    for frac in (0.1, 0.25, 0.5, 1.0):
        cfg = ModelConfig(n_buckets=2**17, dim=64, hidden=96, n_classes=ds.n_classes, seed=0)
        r = run(ds, cfg, cw, 16, enc_cache, frac=frac)
        r["frac"] = frac
        out["learning_curve"].append(r)
        print(f"{frac:>11.2f} {r['n_train']:>7,} {r['in_scope']:>9.4f} "
              f"{r['train_acc']:>10.4f} {r['train_acc'] - r['in_scope']:>7.4f}", flush=True)

    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "ddr2_headroom.json").write_text(json.dumps(out, indent=2, default=float))
    print("\nwrote results/ddr2_headroom.json")


if __name__ == "__main__":
    main()
