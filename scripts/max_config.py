"""The largest useful model the board can actually hold.

The DDR2 experiment ruled out spending resources on table rows. The feature
ablation showed where accuracy does come from. This script puts both together and
asks the only question left: given the real constraints, what is the most capable
model that fits?

The binding constraint is block RAM, and at INT4 it is a single number:

    V * D <= 607.5 KiB * 1024 * 2 = 1,244,160

Everything else on the board is slack. The head costs D*H + H*K parameters, which
is under 1% of storage, and the DSPs and compute budget are 73% and 98% idle -- so
head width is very nearly free and is swept aggressively here. If a wider head
does nothing, a deeper one will not help either, and the ceiling is the
representation rather than the classifier on top of it.

    uv run python scripts/max_config.py
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
from sysone.hw_estimate import (HwAssumptions, compute_latency_us,  # noqa: E402
                                transport_latency_us)
from sysone.metrics import evaluate                            # noqa: E402
from sysone.model import ModelConfig, encode, softmax          # noqa: E402
from sysone.quant import QuantConfig, calibrate_and_quantize   # noqa: E402
from sysone.train import fit_temperature, train                # noqa: E402

BRAM_KIB = 607.5
BEST_FEATURES = dict(use_bigrams=True, use_trigrams=True,
                     char_ngrams=(3, 5), max_tokens=256)

# (V, D, H, emb_bits, label). The first group holds V*D at the block-RAM ceiling
# and varies how it is split; the second group grows the head at a fixed table;
# the last is the off-chip reference, included to show what is given up.
CANDIDATES = [
    (32768, 32,  64, 4, "BRAM ceiling, wide table"),
    (16384, 64,  64, 4, "BRAM ceiling, wide rows"),
    (32768, 32, 256, 4, "BRAM ceiling + 4x head"),
    (32768, 32, 512, 4, "BRAM ceiling + 8x head"),
    (16384, 64, 256, 4, "BRAM ceiling, wide rows + 4x head"),
    (16384, 64, 512, 4, "BRAM ceiling, wide rows + 8x head"),
    (131072, 64, 256, 8, "off-chip reference (8 MiB)"),
]


def main() -> None:
    ds = load_clinc150()
    floor, _ = majority_floor(ds.test, ds.n_classes)
    cw = np.ones(ds.n_classes, np.float32)
    cw[ds.oos_id] = 10.0
    hw = HwAssumptions()
    enc: dict = {}

    print(f"block RAM ceiling at INT4: V*D <= {int(BRAM_KIB * 1024 * 2):,}")
    print(f"features: unigram + bigram + trigram + char 3-5\n")
    print(f"{'configuration':34} {'V*D':>10} {'KiB':>7} {'fit':>4} {'in-scope':>9} "
          f"{'oosR':>6} {'ECE':>7} {'us':>7} {'DSP%':>6}")

    rows = []
    for V, D, H, bits, label in CANDIDATES:
        cfg = ModelConfig(n_buckets=V, dim=D, hidden=H, n_classes=ds.n_classes,
                          seed=0, **BEST_FEATURES)
        t0 = time.time()
        model, _ = train(cfg, ds.train.texts, ds.train.y, ds.val.texts, ds.val.y,
                         epochs=20, class_weight=cw, verbose=False,
                         qat_bits=(bits, 8, 8), qat_warmup_epochs=5)
        if V not in enc:
            enc[V] = (encode(ds.val.texts, cfg), encode(ds.test.texts, cfg))
        (va_f, va_o), (te_f, te_o) = enc[V]

        T = fit_temperature(model.logits(va_f, va_o), ds.val.y)
        qm = calibrate_and_quantize(model, va_f, va_o, QuantConfig(
            emb_bits=bits, w1_bits=8, w2_bits=8, temperature=T))
        r = evaluate(qm.predict_proba(te_f, te_o), ds.test.y, ds.test.is_oos,
                     ds.oos_id, floor)

        kib = qm.storage_bits()["total_KiB"]
        fits = kib <= BRAM_KIB
        n_feat = int(np.diff(te_o).mean())
        lat = compute_latency_us(n_feat, D, H, ds.n_classes, bits, fits, hw)
        # Head width sets the MAC lane count we could usefully deploy.
        lanes = min(hw.mac_lanes, 240)

        rows.append({"label": label, "V": V, "dim": D, "hidden": H, "emb_bits": bits,
                     "storage_KiB": kib, "fits_bram": bool(fits),
                     "params": cfg.n_params, "feats_per_input": n_feat,
                     "compute_us": lat.compute_us, "cycles": lat.detail["total_cycles"],
                     "in_scope": r["in_scope_accuracy"], "oos_recall": r["oos_recall"],
                     "ece": r["ece_equal_width"], "brier": r["brier"],
                     "combined": r["combined_accuracy"], "temperature": T,
                     "selective": r["selective"], "train_s": time.time() - t0})
        print(f"{label:34} {V * D:>10,} {kib:>7.1f} {'yes' if fits else 'NO':>4} "
              f"{r['in_scope_accuracy']:>9.4f} {r['oos_recall']:>6.3f} "
              f"{r['ece_equal_width']:>7.4f} {lat.compute_us:>7.2f} "
              f"{lanes / 240:>5.0%}", flush=True)

    best = max((r for r in rows if r["fits_bram"]), key=lambda r: r["in_scope"])
    tx_eth = transport_latency_us(int(best["feats_per_input"] * 2 + 6), "ethernet", hw)
    print(f"\nbest on-chip: {best['label']} -> {best['in_scope']:.4f} in-scope, "
          f"{best['storage_KiB']:.1f} KiB ({best['storage_KiB'] / BRAM_KIB:.0%} of BRAM)")
    print(f"  compute {best['compute_us']:.2f} us vs Ethernet transport {tx_eth:.1f} us "
          f"-> compute is {best['compute_us'] / (best['compute_us'] + tx_eth):.1%} of latency")
    print(f"  headroom before compute ties transport: {tx_eth / best['compute_us']:.0f}x")

    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "max_config.json").write_text(json.dumps(rows, indent=2, default=float))
    print("\nwrote results/max_config.json")


if __name__ == "__main__":
    main()
