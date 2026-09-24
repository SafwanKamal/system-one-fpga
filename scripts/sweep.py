"""Phase 1 sweeps: model size, bit width, and where each lands on the board.

Writes results/sweep_size.json and results/sweep_bits.json.

Every configuration is trained, calibrated on validation, quantised, and scored
on the integer path -- never on the float model. The numbers reported are what the
hardware would produce, because the integer path is bit-exact against a scalar
reference (tests/test_bitexact.py).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sysone.data import load_clinc150, majority_floor          # noqa: E402
from sysone.hashing import collision_stats                     # noqa: E402
from sysone.metrics import evaluate                            # noqa: E402
from sysone.model import ModelConfig, encode                   # noqa: E402
from sysone.quant import QuantConfig, calibrate_and_quantize   # noqa: E402
from sysone.train import fit_temperature, train                # noqa: E402

# Nexys 4 DDR / Artix-7 XC7A100T
BRAM_KIB = 4860 * 1024 / 8 / 1024     # 135 x 36Kb block RAMs = 607.5 KiB
DSP48 = 240
SLICES = 15850


def board_fit(storage: dict) -> dict:
    """Where each tensor has to live, given 607.5 KiB of BRAM.

    The head is tiny and always fits. The question is only ever the embedding
    table: in BRAM it is a one-cycle random read, in DDR2 it is a scattered burst
    of a few dozen rows and the latency story changes completely.
    """
    emb, head = storage["embedding_KiB"], storage["head_KiB"] + storage["aux_KiB"]
    return {
        "bram_KiB": BRAM_KIB,
        "embedding_fits_bram": emb + head <= BRAM_KIB,
        "bram_utilisation_if_onchip": (emb + head) / BRAM_KIB,
        "embedding_location": "BRAM" if emb + head <= BRAM_KIB else "DDR2",
        "head_KiB": head,
    }


def run_one(ds, cfg: ModelConfig, qcfg_bits, epochs, cw, qat: bool, seed: int,
            cache: dict) -> dict:
    cfg = ModelConfig(**{**cfg.__dict__, "seed": seed})
    key = (cfg.n_buckets, cfg.use_bigrams, cfg.max_tokens)
    if key not in cache:
        cache[key] = {
            "tr": encode(ds.train.texts, cfg),
            "va": encode(ds.val.texts, cfg),
            "te": encode(ds.test.texts, cfg),
        }
    enc = cache[key]
    va_f, va_o = enc["va"]
    te_f, te_o = enc["te"]

    t0 = time.time()
    model, info = train(
        cfg, ds.train.texts, ds.train.y, ds.val.texts, ds.val.y,
        epochs=epochs, class_weight=cw, verbose=False,
        qat_bits=qcfg_bits if qat else None, qat_warmup_epochs=max(2, epochs // 4),
    )
    train_s = time.time() - t0

    floor, _ = majority_floor(ds.test, ds.n_classes)
    T = fit_temperature(model.logits(va_f, va_o), ds.val.y)

    emb_b, w1_b, w2_b = qcfg_bits
    qm = calibrate_and_quantize(model, va_f, va_o, QuantConfig(
        emb_bits=emb_b, w1_bits=w1_b, w2_bits=w2_b, temperature=T))
    r_int = evaluate(qm.predict_proba(te_f, te_o), ds.test.y, ds.test.is_oos,
                     ds.oos_id, floor)

    from sysone.model import softmax
    r_f32 = evaluate(softmax(model.logits(te_f, te_o) / T), ds.test.y,
                     ds.test.is_oos, ds.oos_id, floor)

    storage = qm.storage_bits()
    keep = ("combined_accuracy", "in_scope_accuracy", "oos_recall", "brier",
            "ece_equal_width", "ece_equal_mass", "nll", "oos_auroc_by_maxprob",
            "in_scope_false_oos_rate", "mean_confidence")
    return {
        "n_buckets": cfg.n_buckets, "dim": cfg.dim, "hidden": cfg.hidden,
        "bits": list(qcfg_bits), "qat": qat, "seed": seed,
        "params": cfg.n_params, "head_params": cfg.head_params,
        "temperature": T, "train_seconds": round(train_s, 1),
        "best_val_acc": info["best_val_acc"],
        "float32": {k: r_f32[k] for k in keep},
        "int": {k: r_int[k] for k in keep},
        "int_minus_float_in_scope": r_int["in_scope_accuracy"] - r_f32["in_scope_accuracy"],
        "storage": storage,
        "board": board_fit(storage),
        "selective_int": r_int["selective"],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=16)
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--which", choices=["size", "bits", "both"], default="both")
    args = ap.parse_args()

    ds = load_clinc150()
    cw = np.ones(ds.n_classes, np.float32)
    cw[ds.oos_id] = 10.0
    cache: dict = {}
    (ROOT / "results").mkdir(exist_ok=True)

    if args.which in ("size", "both"):
        print("=== hash table load factors (train split, unigrams) ===")
        loads = {v: collision_stats(ds.train.texts, v) for v in
                 (1024, 2048, 4096, 8192, 16384, 32768, 65536)}
        for v, s in loads.items():
            print(f"  V={v:6d}  types={s['distinct_word_types']:5d}  "
                  f"load={s['load_factor']:.3f}  collision_rate={s['collision_rate']:.3f}")
        (ROOT / "results" / "hash_load.json").write_text(json.dumps(loads, indent=2))

        print("\n=== size sweep (INT8, post-training quantisation) ===")
        rows = []
        for V in (2048, 4096, 8192, 16384, 32768, 65536):
            for D in (32, 64, 128):
                H = max(64, D)
                for seed in range(args.seeds):
                    cfg = ModelConfig(n_buckets=V, dim=D, hidden=H,
                                      n_classes=ds.n_classes, seed=seed)
                    r = run_one(ds, cfg, (8, 8, 8), args.epochs, cw, False, seed, cache)
                    rows.append(r)
                    print(f"  V={V:6d} D={D:3d} H={H:3d} params={r['params']:>9,} "
                          f"int8={r['storage']['total_KiB']:8.1f}KiB "
                          f"{'BRAM' if r['board']['embedding_fits_bram'] else 'DDR2'}  "
                          f"in={r['int']['in_scope_accuracy']:.4f} "
                          f"oosR={r['int']['oos_recall']:.4f} "
                          f"ECE={r['int']['ece_equal_width']:.4f}", flush=True)
        (ROOT / "results" / "sweep_size.json").write_text(json.dumps(rows, indent=2))

    if args.which in ("bits", "both"):
        print("\n=== bit-width sweep (V=8192, D=64, H=96) ===")
        print("     emb/head bits are swept separately: the table is ~99% of the")
        print("     storage, so crushing it and crushing the head are not the same bet.")
        rows = []
        base = dict(n_buckets=8192, dim=64, hidden=96, n_classes=ds.n_classes)
        combos = [(8, 8), (8, 4), (4, 8), (4, 4), (1, 8), (8, 1), (1, 1), (4, 1), (1, 4)]
        for emb_b, head_b in combos:
            for qat in (False, True):
                for seed in range(args.seeds):
                    cfg = ModelConfig(**base, seed=seed)
                    r = run_one(ds, cfg, (emb_b, head_b, head_b), args.epochs,
                                cw, qat, seed, cache)
                    rows.append(r)
                    print(f"  emb={emb_b}b head={head_b}b qat={int(qat)} "
                          f"{r['storage']['total_KiB']:7.1f}KiB "
                          f"{'BRAM' if r['board']['embedding_fits_bram'] else 'DDR2'}  "
                          f"in={r['int']['in_scope_accuracy']:.4f} "
                          f"(f32 {r['float32']['in_scope_accuracy']:.4f}, "
                          f"d={r['int_minus_float_in_scope']:+.4f}) "
                          f"oosR={r['int']['oos_recall']:.4f} "
                          f"ECE={r['int']['ece_equal_width']:.4f} "
                          f"brier={r['int']['brier']:.4f}", flush=True)
        (ROOT / "results" / "sweep_bits.json").write_text(json.dumps(rows, indent=2))

    print("\nwrote results/*.json")


if __name__ == "__main__":
    main()
