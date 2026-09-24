"""The question the size and bit-width sweeps together pose.

Both sweeps vary one thing at a time, which hides the interaction that matters.
Accuracy rises with table size, and it falls with narrower weights -- but a
narrower table is a *bigger* table at the same storage cost. So for the one budget
that is actually fixed by the hardware, 607.5 KiB of block RAM, which side of that
trade wins?

Every configuration below is sized to land just under the BRAM ceiling. If INT4
wins, the DDR2 path in the project plan becomes optional rather than central, and
the latency story changes: an on-chip table is a one-cycle read instead of a
scattered burst.

    uv run python scripts/bram_budget.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sysone.data import load_clinc150, majority_floor            # noqa: E402
from sysone.metrics import evaluate                              # noqa: E402
from sysone.model import ModelConfig, encode, softmax            # noqa: E402
from sysone.quant import QuantConfig, calibrate_and_quantize     # noqa: E402
from sysone.train import fit_temperature, train                  # noqa: E402

BRAM_KIB = 607.5

# (n_buckets, dim, hidden, embedding bits) -- each sized to sit under the ceiling.
CANDIDATES = [
    (8192,  64,  96, 8),
    (16384, 32,  64, 8),
    (16384, 64,  96, 4),
    (32768, 32,  64, 4),
    (32768, 64,  96, 2),
    (65536, 32,  64, 2),
    (16384, 96, 128, 4),
]


def main() -> None:
    ds = load_clinc150()
    floor, _ = majority_floor(ds.test, ds.n_classes)
    cw = np.ones(ds.n_classes, np.float32)
    cw[ds.oos_id] = 10.0

    print(f"BRAM ceiling: {BRAM_KIB} KiB. Head is always INT8 (it is ~1% of storage).")
    print(f"Test majority floor: {floor:.4f}\n")
    print(f"{'V':>6} {'D':>4} {'H':>4} {'emb':>4} {'KiB':>7} {'fits':>5} "
          f"{'in-scope':>9} {'oosR':>6} {'ECE':>7} {'Brier':>7} {'f32':>7}")

    rows = []
    enc_cache: dict = {}
    for V, D, H, bits in CANDIDATES:
        cfg = ModelConfig(n_buckets=V, dim=D, hidden=H, n_classes=ds.n_classes, seed=0)
        model, _ = train(cfg, ds.train.texts, ds.train.y, ds.val.texts, ds.val.y,
                         epochs=20, class_weight=cw, verbose=False,
                         qat_bits=(bits, 8, 8), qat_warmup_epochs=5)
        if V not in enc_cache:
            enc_cache[V] = (encode(ds.val.texts, cfg), encode(ds.test.texts, cfg))
        (va_f, va_o), (te_f, te_o) = enc_cache[V]

        T = fit_temperature(model.logits(va_f, va_o), ds.val.y)
        qm = calibrate_and_quantize(model, va_f, va_o, QuantConfig(
            emb_bits=bits, w1_bits=8, w2_bits=8, temperature=T))
        r = evaluate(qm.predict_proba(te_f, te_o), ds.test.y, ds.test.is_oos,
                     ds.oos_id, floor)
        r32 = evaluate(softmax(model.logits(te_f, te_o) / T), ds.test.y,
                       ds.test.is_oos, ds.oos_id, floor)
        kib = qm.storage_bits()["total_KiB"]
        fits = kib <= BRAM_KIB
        print(f"{V:6d} {D:4d} {H:4d} {bits:3d}b {kib:7.1f} {'yes' if fits else 'NO':>5} "
              f"{r['in_scope_accuracy']:9.4f} {r['oos_recall']:6.3f} "
              f"{r['ece_equal_width']:7.4f} {r['brier']:7.4f} "
              f"{r32['in_scope_accuracy']:7.4f}", flush=True)
        rows.append({"n_buckets": V, "dim": D, "hidden": H, "emb_bits": bits,
                     "storage_KiB": kib, "fits_bram": bool(fits),
                     "params": cfg.n_params, "temperature": T,
                     "int": {k: r[k] for k in
                             ("in_scope_accuracy", "oos_recall", "ece_equal_width",
                              "ece_equal_mass", "brier", "combined_accuracy",
                              "oos_auroc_by_maxprob")},
                     "float32_in_scope": r32["in_scope_accuracy"],
                     "selective": r["selective"]})

    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "bram_budget.json").write_text(json.dumps(rows, indent=2))
    best = max([r for r in rows if r["fits_bram"]],
               key=lambda r: r["int"]["in_scope_accuracy"])
    print(f"\nbest that fits on chip: V={best['n_buckets']} D={best['dim']} "
          f"emb={best['emb_bits']}b -> {best['int']['in_scope_accuracy']:.4f} in-scope "
          f"at {best['storage_KiB']:.1f} KiB")


if __name__ == "__main__":
    main()
