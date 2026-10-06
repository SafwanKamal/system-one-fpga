"""Integer-only inference path, and the float model -> integer model conversion.

This module is the specification the RTL implements. Everything downstream of the
index stream is integer arithmetic with explicitly defined rounding, so a NumPy
run and a hardware run must agree exactly, not approximately. Where a choice was
available, the one that is cheap on an Artix-7 was taken.

Scale placement
---------------
A per-dimension scale on the embedding table would normally break the integer MAC,
because the scale sits inside the sum over dimensions. It is made free by folding
it into the first weight matrix before that matrix is quantised:

    W1' = diag(s_E) @ W1

After the fold, ``acc1 = pooled_q @ W1q`` is a pure int32 dot product and the
per-dimension embedding scale has been absorbed. The same trick puts per-output
scales on both weight matrices at no hardware cost, since each output lane already
needs its own requantiser.

Rounding
--------
One rule everywhere: round-half-up via ``(x * m + (1 << (shift - 1))) >> shift``
with an arithmetic shift. It is one adder and one shifter in RTL, it is exactly
reproducible, and it is the same rule used for the mean-pool division. Round-to-
nearest-even would be defensible statistically and costs an extra comparator per
lane; it was not worth it.

Mean pooling
------------
Dividing by the token count is done with a 65-entry Q16 reciprocal table rather
than a divider, since ``max_tokens`` bounds the count. The table is generated with
the same rounding rule and is part of the exported manifest.

The mean is then scaled back up by ``pool_gain`` bits. This matters more than it
looks. A mean of n quantised values concentrates as n grows -- averaging 96
character n-gram rows whose codes live in [-7, 7] leaves a pooled value spanning
about 3 bits, so the first MAC consumes an input with eight distinguishable levels
and calibration suffers well before accuracy does. Scaling the mean up to fill the
activation width restores that resolution at the cost of one shift, and the factor
is folded into the first requantisation multiplier so it costs nothing downstream.
``pool_gain`` is chosen at calibration time from the observed pooled range, not
fixed, because it depends on how many features an input produces.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .model import HashedBagClassifier, softmax

RECIP_SHIFT = 16
MULT_SHIFT = 20          # fixed-point width for requantisation multipliers


# --------------------------------------------------------------------- helpers

def round_half_up_shift(x: np.ndarray, shift: int) -> np.ndarray:
    """(x + 2^(shift-1)) >> shift with an arithmetic shift, in int64."""
    if shift == 0:
        return x
    return (x.astype(np.int64) + (np.int64(1) << (shift - 1))) >> shift


def make_reciprocal_table(max_tokens: int) -> np.ndarray:
    """Q16 reciprocals: table[n] ~ 2^16 / n, with table[0] unused."""
    t = np.zeros(max_tokens + 1, dtype=np.int64)
    for n in range(1, max_tokens + 1):
        t[n] = (( 1 << RECIP_SHIFT) + n // 2) // n
    return t


def qmax_for(bits: int) -> int:
    """Symmetric signed range. int4 uses [-7, 7], not [-8, 7].

    Giving up the extra negative code keeps the range symmetric, which means one
    scale reproduces the quantiser exactly and negation is free. The lost code
    costs a fraction of a percent of representable range.
    """
    if bits == 1:
        return 1          # ternary {-1, 0, +1}
    return (1 << (bits - 1)) - 1


def quantize_symmetric(
    W: np.ndarray, bits: int, axis: int | None = None, percentile: float = 100.0
) -> tuple[np.ndarray, np.ndarray]:
    """Symmetric linear quantisation. Returns (integer codes, float scales).

    ``percentile`` below 100 clips outliers before choosing the scale. A single
    freak weight can otherwise set the scale for a whole tensor and push every
    ordinary weight into a couple of codes -- the dominant failure mode at 4 bits.
    Clipped values saturate rather than wrap.
    """
    q = qmax_for(bits)
    absW = np.abs(W)
    if axis is None:
        amax = np.percentile(absW, percentile) if percentile < 100 else absW.max()
        amax = np.array(max(float(amax), 1e-12), dtype=np.float64)
    else:
        amax = (np.percentile(absW, percentile, axis=axis, keepdims=True)
                if percentile < 100 else absW.max(axis=axis, keepdims=True))
        amax = np.maximum(amax.astype(np.float64), 1e-12)
    scale = amax / q
    codes = np.clip(np.round(W / scale), -q, q).astype(np.int32)
    return codes, np.squeeze(scale)


def quantize_ternary(W: np.ndarray, axis: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Ternary weights {-1, 0, +1} with a per-group scale (Li & Liu, TWN).

    Threshold 0.7 * mean|W| and scale = mean|W| over the surviving entries. This is
    the published heuristic; it is near-optimal for roughly Gaussian weights, which
    is what an Adam-trained table looks like.
    """
    absW = np.abs(W)
    mean_abs = absW.mean(axis=axis, keepdims=True) if axis is not None else absW.mean()
    delta = 0.7 * mean_abs
    codes = (np.sign(W) * (absW > delta)).astype(np.int32)
    mask = codes != 0
    if axis is None:
        scale = np.array(absW[mask].mean() if mask.any() else 1e-12, dtype=np.float64)
    else:
        num = (absW * mask).sum(axis=axis, keepdims=True)
        den = np.maximum(mask.sum(axis=axis, keepdims=True), 1)
        scale = np.maximum(num / den, 1e-12)
    return codes, np.squeeze(np.asarray(scale, dtype=np.float64))


def _quant(W: np.ndarray, bits: int, axis: int | None, percentile: float):
    # Anything whose code range collapses to {-1, 0, +1} is ternary, and ternary
    # needs the TWN scale rule, not the linear one. Routing bits=2 through
    # quantize_symmetric is a trap: with qmax=1 the scale becomes a high
    # percentile of |W|, so almost every weight rounds to zero and the model
    # reads as catastrophically broken when the quantiser, not the width, is at
    # fault. This branch is the fix, and it is why 2-bit and ternary agree.
    if qmax_for(bits) <= 1:
        return quantize_ternary(W, axis=axis)
    return quantize_symmetric(W, bits, axis=axis, percentile=percentile)


def to_fixed_multiplier(m: np.ndarray, shift: int = MULT_SHIFT) -> np.ndarray:
    """Real multiplier -> integer multiplier at a fixed shift."""
    return np.round(np.asarray(m, dtype=np.float64) * (1 << shift)).astype(np.int64)


# ----------------------------------------------------------------- the int model

@dataclass
class QuantConfig:
    emb_bits: int = 8
    w1_bits: int = 8
    w2_bits: int = 8
    act_bits: int = 8            # hidden activation width after ReLU
    logit_bits: int = 16         # output logit width
    max_multiplier: int = 1 << 17   # channel_requantizer: multiplier must be below this
    emb_percentile: float = 99.9
    w_percentile: float = 100.0
    act_percentile: float = 99.9
    temperature: float = 1.0


@dataclass
class QuantModel:
    """An integer model. Every field here maps to something on the board."""
    cfg: QuantConfig
    Eq: np.ndarray            # (V, D)   int codes  -> DDR2 or BRAM
    W1q: np.ndarray           # (D, H)   int codes  -> BRAM
    W2q: np.ndarray           # (H, K)   int codes  -> BRAM
    M1: np.ndarray            # (H,)     int multiplier, requantise acc1 -> act
    B1: np.ndarray            # (H,)     int bias in accumulator units
    M2: np.ndarray            # (K,)     int multiplier, requantise acc2 -> logit
    B2: np.ndarray            # (K,)     int bias in accumulator units
    recip: np.ndarray         # (max_tokens+1,) Q16 reciprocal LUT
    pool_gain: int            # left-shift applied to the pooled mean, folded into M1
    s_out: float              # real value of one output logit LSB
    act_qmax: int
    logit_qmax: int
    max_tokens: int

    # ---- the integer forward pass; this is the RTL contract ----

    def forward_int(self, flat: np.ndarray, offsets: np.ndarray,
                    batch: int = 4096) -> np.ndarray:
        n = len(offsets) - 1
        out = np.empty((n, self.W2q.shape[1]), dtype=np.int64)
        for s in range(0, n, batch):
            e = min(s + batch, n)
            sub = offsets[s:e + 1]
            out[s:e] = self._forward_int_block(flat[sub[0]:sub[-1]], sub - sub[0])
        return out

    def _forward_int_block(self, flat: np.ndarray, offsets: np.ndarray) -> np.ndarray:
        counts = np.diff(offsets).astype(np.int64)
        counts = np.minimum(counts, self.max_tokens)

        # 1. gather + accumulate int codes  (int32 is ample: 64 * 127 = 8128)
        summed = np.add.reduceat(self.Eq[flat].astype(np.int64), offsets[:-1], axis=0)

        # 2. mean pool via Q16 reciprocal, round-half-up, then rescale to fill
        #    the activation width (see "Mean pooling" above). One shift in RTL.
        pooled = round_half_up_shift(summed * self.recip[counts][:, None],
                                     RECIP_SHIFT - self.pool_gain)

        # 3. first MAC: int32 accumulation
        acc1 = pooled @ self.W1q.astype(np.int64)

        # 4. requantise + ReLU + clamp to the activation width
        h = round_half_up_shift(acc1 * self.M1[None, :] + self.B1[None, :], MULT_SHIFT)
        h = np.clip(h, 0, self.act_qmax)

        # 5. second MAC
        acc2 = h @ self.W2q.astype(np.int64)

        # 6. requantise to logits with temperature already folded into M2/B2
        logits = round_half_up_shift(acc2 * self.M2[None, :] + self.B2[None, :], MULT_SHIFT)
        return np.clip(logits, -self.logit_qmax, self.logit_qmax)

    def predict_proba(self, flat: np.ndarray, offsets: np.ndarray) -> np.ndarray:
        """Host-side softmax over dequantised logits.

        Temperature is already inside the integer logits, so this is a plain
        softmax -- no second calibration knob, which is the point: the board emits
        a calibrated decision, not raw scores that a host has to fix up.
        """
        return softmax(self.forward_int(flat, offsets).astype(np.float64) * self.s_out)

    # ---- size accounting ----

    def storage_bits(self) -> dict:
        c = self.cfg
        emb = self.Eq.size * (2 if c.emb_bits == 1 else c.emb_bits)
        w1 = self.W1q.size * (2 if c.w1_bits == 1 else c.w1_bits)
        w2 = self.W2q.size * (2 if c.w2_bits == 1 else c.w2_bits)
        aux = (self.M1.size + self.B1.size + self.M2.size + self.B2.size) * 32
        return {
            "embedding_bits": int(emb), "embedding_KiB": emb / 8 / 1024,
            "head_bits": int(w1 + w2), "head_KiB": (w1 + w2) / 8 / 1024,
            "aux_bits": int(aux), "aux_KiB": aux / 8 / 1024,
            "total_KiB": (emb + w1 + w2 + aux) / 8 / 1024,
        }


def calibrate_and_quantize(
    model: HashedBagClassifier,
    flat: np.ndarray,
    offsets: np.ndarray,
    qcfg: QuantConfig,
) -> QuantModel:
    """Post-training quantisation, calibrated on a held-out split.

    Only two things need data: the hidden-activation scale and the output logit
    scale. Both are taken from a percentile of the float model's activations on
    the calibration split rather than the max, because one outlier input would
    otherwise set the scale for every input.
    """
    cfgm = model.cfg

    # --- embedding table, per-dimension scale
    Eq, s_E = _quant(model.E, qcfg.emb_bits, axis=0, percentile=qcfg.emb_percentile)
    s_E = np.atleast_1d(np.asarray(s_E, dtype=np.float64))
    if s_E.size == 1:
        s_E = np.full(cfgm.dim, float(s_E))

    # --- fold the per-dimension embedding scale into W1, then quantise per hidden unit
    W1_folded = model.W1.astype(np.float64) * s_E[:, None]
    W1q, s_W1 = _quant(W1_folded, qcfg.w1_bits, axis=0, percentile=qcfg.w_percentile)
    s_W1 = np.atleast_1d(np.asarray(s_W1, dtype=np.float64))
    if s_W1.size == 1:
        s_W1 = np.full(cfgm.hidden, float(s_W1))

    # --- activation scale from float-model statistics on the calibration split
    fwd = model.forward(flat, offsets)
    h_float = np.maximum(fwd["h_pre"], 0.0)
    act_qmax = qmax_for(qcfg.act_bits)
    a_max = float(np.percentile(h_float, qcfg.act_percentile))
    s_h = max(a_max, 1e-9) / act_qmax

    # Choose pool_gain so the rescaled mean uses most of the activation width.
    # Measured on the calibration split rather than assumed, because it depends on
    # the feature count per input, which the feature set controls.
    counts_cal = np.minimum(np.diff(offsets).astype(np.int64), cfgm.max_tokens)
    summed_cal = np.add.reduceat(Eq[flat].astype(np.int64), offsets[:-1], axis=0)
    base = round_half_up_shift(summed_cal * make_reciprocal_table(cfgm.max_tokens)[counts_cal][:, None],
                               RECIP_SHIFT)
    observed = float(np.percentile(np.abs(base), 99.9))
    pool_gain = 0
    if observed > 0:
        while pool_gain < 8 and observed * (1 << (pool_gain + 1)) <= act_qmax:
            pool_gain += 1

    # The gain multiplies pooled, so the first requantiser must divide it back out.
    M1 = to_fixed_multiplier(s_W1 / s_h / (1 << pool_gain))
    B1 = to_fixed_multiplier(model.b1.astype(np.float64) / s_h)

    # --- second layer, per-class scale
    W2q, s_W2 = _quant(model.W2.astype(np.float64), qcfg.w2_bits, axis=0,
                       percentile=qcfg.w_percentile)
    s_W2 = np.atleast_1d(np.asarray(s_W2, dtype=np.float64))
    if s_W2.size == 1:
        s_W2 = np.full(cfgm.n_classes, float(s_W2))

    # --- output scale, with temperature folded in
    logit_qmax = qmax_for(qcfg.logit_bits)
    l_max = float(np.percentile(np.abs(fwd["logits"]), 99.99))
    s_out = max(l_max / qcfg.temperature, 1e-9) / logit_qmax

    # The RTL multiplier input is 17 bits unsigned. A model with small logits
    # (a distilled one, say) wants a fine output step and hence a large M2; when
    # that overflows, coarsen the output step instead. The logits then use less
    # of their 16-bit range, which costs nothing measurable at this resolution.
    m2_float = (s_h * s_W2) / (qcfg.temperature * s_out) * (1 << MULT_SHIFT)
    if m2_float.max() >= qcfg.max_multiplier - 1:
        s_out *= float(m2_float.max()) / (qcfg.max_multiplier - 2)
    M2 = to_fixed_multiplier((s_h * s_W2) / (qcfg.temperature * s_out))
    B2 = to_fixed_multiplier(model.b2.astype(np.float64) / (qcfg.temperature * s_out))

    return QuantModel(
        cfg=qcfg, Eq=Eq.astype(np.int32), W1q=W1q.astype(np.int32), W2q=W2q.astype(np.int32),
        M1=M1, B1=B1, M2=M2, B2=B2,
        recip=make_reciprocal_table(cfgm.max_tokens),
        pool_gain=pool_gain,
        s_out=s_out, act_qmax=act_qmax, logit_qmax=logit_qmax,
        max_tokens=cfgm.max_tokens,
    )


# ------------------------------------------------------- quantisation-aware training

@dataclass
class FakeQuantSpec:
    """Scale (and ternary threshold) for one tensor, held fixed between refreshes.

    Recomputing the embedding table's scale every step would cost more arithmetic
    than the model update itself -- it is a reduction over millions of rows to set
    a number that barely moves. Scales are therefore refreshed on a schedule and
    treated as constants in between, which is also what the deployed model does,
    since its scales are frozen at export.
    """
    bits: int
    scale: np.ndarray            # broadcastable against the tensor's last axis
    threshold: np.ndarray | None = None   # ternary only

    def apply(self, W: np.ndarray) -> np.ndarray:
        if self.bits >= 32:
            return W
        if self.bits == 1:   # ternary
            codes = np.sign(W) * (np.abs(W) > self.threshold)
        else:
            q = qmax_for(self.bits)
            codes = np.clip(np.round(W / self.scale), -q, q)
        return (codes * self.scale).astype(np.float32)


def make_fq_spec(W: np.ndarray, bits: int, axis: int | None = 0,
                 percentile: float = 100.0) -> FakeQuantSpec:
    if bits >= 32:
        return FakeQuantSpec(bits=bits, scale=np.array(1.0))
    if qmax_for(bits) <= 1:      # see _quant: ternary needs the TWN scale rule
        bits = 1
        absW = np.abs(W)
        mean_abs = absW.mean(axis=axis, keepdims=True) if axis is not None else absW.mean()
        thr = 0.7 * mean_abs
        mask = absW > thr
        if axis is None:
            scale = np.array(absW[mask].mean() if mask.any() else 1e-12)
        else:
            num = (absW * mask).sum(axis=axis, keepdims=True)
            den = np.maximum(mask.sum(axis=axis, keepdims=True), 1)
            scale = np.maximum(num / den, 1e-12)
        return FakeQuantSpec(bits=1, scale=np.squeeze(scale).astype(np.float32),
                             threshold=np.squeeze(np.asarray(thr)).astype(np.float32))
    _, s = quantize_symmetric(W, bits, axis=axis, percentile=percentile)
    return FakeQuantSpec(bits=bits, scale=np.atleast_1d(np.asarray(s, dtype=np.float32)))


@dataclass
class QATSpec:
    """The three tensor specs used during a QAT step, refreshed together."""
    emb: FakeQuantSpec
    w1: FakeQuantSpec
    w2: FakeQuantSpec

    @staticmethod
    def build(model, emb_bits: int, w1_bits: int, w2_bits: int,
              emb_percentile: float = 99.9) -> "QATSpec":
        return QATSpec(
            emb=make_fq_spec(model.E, emb_bits, axis=0, percentile=emb_percentile),
            w1=make_fq_spec(model.W1, w1_bits, axis=0),
            w2=make_fq_spec(model.W2, w2_bits, axis=0),
        )
