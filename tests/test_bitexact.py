"""Bit-exactness and accumulator-width tests.

The NumPy integer path in ``quant.py`` is the specification for the RTL, but NumPy
is not a neutral witness: it has its own overflow behaviour, its own shift
semantics, and vectorised reductions whose association order is not the one a
hardware accumulator uses. So the path is checked against a second implementation
written in scalar Python with arbitrary-precision ints, which cannot silently
overflow and which walks the accumulation in the same order a serial MAC would.

If these two agree on every probe input, the NumPy path is trustworthy as the
golden model, and any later disagreement with hardware is the hardware's.

The tests also record the widest accumulator value actually reached, because that
number is what sizes the registers in RTL. Guessing it from the theoretical bound
(64 tokens x 127 x 128 lanes) over-provisions by a wide margin.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sysone.data import load_clinc150                      # noqa: E402
from sysone.model import ModelConfig, encode                # noqa: E402
from sysone.quant import (MULT_SHIFT, RECIP_SHIFT, QuantConfig,  # noqa: E402
                          calibrate_and_quantize)
from sysone.train import train                              # noqa: E402


def ref_forward_scalar(qm, idx: list[int]) -> list[int]:
    """Scalar reference: Python ints, explicit loops, serial accumulation order.

    Deliberately slow and deliberately naive. Its only job is to be obviously
    correct by inspection, so that agreement with the vectorised path means
    something.
    """
    D = qm.W1q.shape[0]
    H = qm.W1q.shape[1]
    K = qm.W2q.shape[1]
    n = min(len(idx), qm.max_tokens)
    idx = idx[:n]

    def rshift_round(x: int, shift: int) -> int:
        # Arithmetic shift of a Python int is already floor-division by 2^shift.
        return (x + (1 << (shift - 1))) >> shift

    pooled = []
    for d in range(D):
        acc = 0
        for t in idx:
            acc += int(qm.Eq[t, d])
        pooled.append(rshift_round(acc * int(qm.recip[n]), RECIP_SHIFT - qm.pool_gain))

    h = []
    for j in range(H):
        acc = 0
        for d in range(D):
            acc += pooled[d] * int(qm.W1q[d, j])
        v = rshift_round(acc * int(qm.M1[j]) + int(qm.B1[j]), MULT_SHIFT)
        h.append(min(max(v, 0), qm.act_qmax))

    out = []
    for k in range(K):
        acc = 0
        for j in range(H):
            acc += h[j] * int(qm.W2q[j, k])
        v = rshift_round(acc * int(qm.M2[k]) + int(qm.B2[k]), MULT_SHIFT)
        out.append(min(max(v, -qm.logit_qmax), qm.logit_qmax))
    return out


def accumulator_widths(qm, flat, offsets, n_probe=512) -> dict:
    """Largest magnitude seen at each accumulation point, as signed bit widths."""
    sub = offsets[:n_probe + 1]
    f = flat[:sub[-1]]
    counts = np.minimum(np.diff(sub).astype(np.int64), qm.max_tokens)
    summed = np.add.reduceat(qm.Eq[f].astype(np.int64), sub[:-1], axis=0)
    from sysone.quant import round_half_up_shift
    pooled = round_half_up_shift(summed * qm.recip[counts][:, None],
                                 RECIP_SHIFT - qm.pool_gain)
    acc1 = pooled @ qm.W1q.astype(np.int64)
    h = np.clip(round_half_up_shift(acc1 * qm.M1[None, :] + qm.B1[None, :], MULT_SHIFT),
                0, qm.act_qmax)
    acc2 = h @ qm.W2q.astype(np.int64)
    prod1 = acc1 * qm.M1[None, :] + qm.B1[None, :]
    prod2 = acc2 * qm.M2[None, :] + qm.B2[None, :]

    def width(a) -> int:
        return int(np.abs(a).max()).bit_length() + 1  # +1 for the sign bit

    return {
        "emb_sum_max": int(np.abs(summed).max()), "emb_sum_bits": width(summed),
        "pooled_max": int(np.abs(pooled).max()), "pooled_bits": width(pooled),
        "acc1_max": int(np.abs(acc1).max()), "acc1_bits": width(acc1),
        "requant1_product_bits": width(prod1),
        "acc2_max": int(np.abs(acc2).max()), "acc2_bits": width(acc2),
        "requant2_product_bits": width(prod2),
    }


def main() -> int:
    ds = load_clinc150()
    cfg = ModelConfig(n_buckets=8192, dim=64, hidden=96, n_classes=ds.n_classes, seed=0)
    cw = np.ones(ds.n_classes, np.float32)
    cw[ds.oos_id] = 10.0
    model, _ = train(cfg, ds.train.texts, ds.train.y, ds.val.texts, ds.val.y,
                     epochs=8, class_weight=cw, verbose=False)
    va_f, va_o = encode(ds.val.texts, cfg)
    te_f, te_o = encode(ds.test.texts, cfg)

    failures = 0
    for bits in (8, 4, 1):
        qm = calibrate_and_quantize(model, va_f, va_o,
                                    QuantConfig(emb_bits=bits, w1_bits=bits, w2_bits=bits))
        vec = qm.forward_int(te_f, te_o)

        n_probe = 200
        mism = 0
        for i in range(n_probe):
            idx = [int(x) for x in te_f[te_o[i]:te_o[i + 1]]]
            ref = ref_forward_scalar(qm, idx)
            if ref != [int(x) for x in vec[i]]:
                mism += 1
                if mism <= 2:
                    got = [int(x) for x in vec[i]]
                    bad = [(k, r, g) for k, (r, g) in enumerate(zip(ref, got)) if r != g][:5]
                    print(f"    MISMATCH bits={bits} sample={i} (class, ref, numpy): {bad}")
        status = "OK " if mism == 0 else "FAIL"
        print(f"[{status}] {bits}-bit: scalar reference vs NumPy on {n_probe} inputs "
              f"-> {n_probe - mism}/{n_probe} identical")
        failures += mism

        # Batching must not change results: a boundary-straddling split is the
        # classic place for a reduceat off-by-one to hide.
        bad_batches = [bs for bs in (1, 7, 64, 4096)
                       if not np.array_equal(qm.forward_int(te_f, te_o, batch=bs), vec)]
        failures += len(bad_batches)
        print(f"       batch-size invariance (1, 7, 64, 4096): "
              f"{'OK' if not bad_batches else 'FAIL at ' + str(bad_batches)}")

        w = accumulator_widths(qm, te_f, te_o)
        print(f"       widths: emb_sum={w['emb_sum_bits']}b pooled={w['pooled_bits']}b "
              f"acc1={w['acc1_bits']}b acc2={w['acc2_bits']}b "
              f"requant={max(w['requant1_product_bits'], w['requant2_product_bits'])}b")

    print("\nRESULT:", "all bit-exact" if failures == 0 else f"{failures} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
