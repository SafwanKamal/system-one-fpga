"""Integer-only reference of the v2 chain encoder (BERT family), the RTL's target.

v1 was made bit-exact by having one Python integer model that both the RTL and the
accuracy numbers come from. v2 needs the same, with the parts a transformer adds:
attention, softmax, GELU and LayerNorm. Everything below is integer arithmetic that
maps onto simple hardware:

  matmul        INT8 x INT8 -> INT32 accumulate (DSP48), bias added in INT32
  requantise    (acc * M + 2^(S-1)) >> S, then clamp      (channel_requantizer)
  GELU          256-entry table, INT8 in -> INT8 out
  softmax       row max, exp of the (max - score) distance from a 256-entry table
                (UINT16), row sum, ONE reciprocal per row, multiply, -> UINT8 / 256
  LayerNorm     row sum and sum of squares in INT32/INT64, mean by a constant
                multiply, integer square root, ONE reciprocal per row, multiply,
                then gamma / beta in fixed point -> INT8
  pooling       segment sum, reciprocal of the count from a table (as v1)

Scales: weights symmetric per output channel; every activation tensor symmetric per
tensor with a scale calibrated as a high percentile of |x| on calibration chains.
The residual stream is kept at a wider INT16 scale so the skip connection does not
lose precision.

Matrix products are computed with float64 BLAS on integer-valued arrays, which is
exact while every partial sum stays below 2^53 (INT8 x INT8 x 1536 terms is far
below), and fast.

`FloatEncoder` mirrors Hugging Face's BertModel in NumPy (checked against PyTorch
in `check_float`), and is what calibration runs on.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

EXP_STEPS = 256          # softmax table length
EXP_STEP = 1.0 / 16      # natural-log units per table step: covers e^0 .. e^-16
LN_FRACTION = 12         # fixed-point bits of the normalised LayerNorm value
RESIDUAL_BITS = 16


# ------------------------------------------------------------------- helpers

def gelu(x):
    from math import erf  # noqa: F401
    return 0.5 * x * (1.0 + _erf(x / np.sqrt(2.0)))


def _erf(x):
    # Abramowitz-Stegun 7.1.26 is not exact enough for checking against PyTorch;
    # use scipy if present, otherwise numpy's vectorised math.erf
    try:
        from scipy.special import erf
        return erf(x)
    except ImportError:
        from math import erf
        return np.vectorize(erf)(x)


def layer_norm(x, g, b, eps):
    m = x.mean(-1, keepdims=True)
    v = ((x - m) ** 2).mean(-1, keepdims=True)
    return (x - m) / np.sqrt(v + eps) * g + b


def to_multiplier(scale: np.ndarray | float, bits: int = 17) -> tuple[np.ndarray, int]:
    """Real scale -> (integer M < 2^bits, shift S) with M / 2^S ~= scale (one S per tensor)."""
    s = np.atleast_1d(np.asarray(scale, dtype=np.float64))
    top = float(s.max())
    shift = 0
    while top * (1 << (shift + 1)) < (1 << bits) - 1 and shift < 62:
        shift += 1
    M = np.round(s * (1 << shift)).astype(np.int64)
    return M, shift


def requant(acc: np.ndarray, M: np.ndarray, shift: int, lo: int, hi: int) -> np.ndarray:
    """(acc * M + 2^(S-1)) >> S, clamped. acc and M are integer-valued."""
    v = np.floor((acc * M + float(1 << (shift - 1))) / float(1 << shift)) if shift > 0 else acc * M
    return np.clip(v, lo, hi)


def quant_weight(W: np.ndarray, bits: int = 8) -> tuple[np.ndarray, np.ndarray]:
    """W is (in, out); symmetric per output column."""
    q = (1 << (bits - 1)) - 1
    s = np.abs(W).max(0) / q
    s = np.where(s == 0, 1e-12, s)
    return np.clip(np.round(W / s), -q, q), s


def isqrt(v: np.ndarray) -> np.ndarray:
    """floor(sqrt(v)) for non-negative integer-valued arrays (exact)."""
    r = np.floor(np.sqrt(v))
    r = np.where(r * r > v, r - 1, r)
    r = np.where((r + 1) * (r + 1) <= v, r + 1, r)
    return r


# --------------------------------------------------------------------- weights

@dataclass
class Layer:
    Wq: np.ndarray; bq: np.ndarray; Wk: np.ndarray; bk: np.ndarray
    Wv: np.ndarray; bv: np.ndarray; Wo: np.ndarray; bo: np.ndarray
    g1: np.ndarray; b1: np.ndarray
    Wi: np.ndarray; bi: np.ndarray; Wf: np.ndarray; bf: np.ndarray
    g2: np.ndarray; b2: np.ndarray


class FloatEncoder:
    """NumPy BertModel (post-LayerNorm, GELU) + the chain heads."""

    def __init__(self, state: dict, config, heads: dict):
        t = lambda k: state[k].detach().cpu().numpy().astype(np.float64)  # noqa: E731
        p = "encoder."
        self.H = config.hidden_size
        self.A = config.num_attention_heads
        self.eps = config.layer_norm_eps
        self.word = t(p + "embeddings.word_embeddings.weight")
        self.pos = t(p + "embeddings.position_embeddings.weight")
        self.type0 = t(p + "embeddings.token_type_embeddings.weight")[0]
        self.eg = t(p + "embeddings.LayerNorm.weight")
        self.eb = t(p + "embeddings.LayerNorm.bias")
        self.layers = []
        for i in range(config.num_hidden_layers):
            q = f"{p}encoder.layer.{i}."
            self.layers.append(Layer(
                t(q + "attention.self.query.weight").T, t(q + "attention.self.query.bias"),
                t(q + "attention.self.key.weight").T, t(q + "attention.self.key.bias"),
                t(q + "attention.self.value.weight").T, t(q + "attention.self.value.bias"),
                t(q + "attention.output.dense.weight").T, t(q + "attention.output.dense.bias"),
                t(q + "attention.output.LayerNorm.weight"), t(q + "attention.output.LayerNorm.bias"),
                t(q + "intermediate.dense.weight").T, t(q + "intermediate.dense.bias"),
                t(q + "output.dense.weight").T, t(q + "output.dense.bias"),
                t(q + "output.LayerNorm.weight"), t(q + "output.LayerNorm.bias")))
        self.heads = {}
        for kind in ("intent", "slots", "pair"):
            for name in heads[kind]:
                self.heads[(kind, name)] = (t(f"{kind}.{name}.weight").T, t(f"{kind}.{name}.bias"))
        self.trace: dict[str, list] | None = None

    def _rec(self, key: str, x: np.ndarray) -> None:
        if self.trace is not None:
            a = np.abs(x).ravel()
            if a.size > 100_000:
                a = a[np.random.default_rng(0).integers(0, a.size, 100_000)]
            self.trace.setdefault(key, []).append(float(np.percentile(a, 99.99)))

    def hidden(self, ids: np.ndarray) -> np.ndarray:
        """One chain (no padding): ids (n,) -> final hidden (n, H)."""
        n = len(ids)
        x = self.word[ids] + self.pos[:n] + self.type0
        self._rec("emb_sum", x)
        x = layer_norm(x, self.eg, self.eb, self.eps)
        self._rec("x0", x)
        d = self.H // self.A
        for i, L in enumerate(self.layers):
            q, k, v = x @ L.Wq + L.bq, x @ L.Wk + L.bk, x @ L.Wv + L.bv
            for nm, t in (("q", q), ("k", k), ("v", v)):
                self._rec(f"{i}.{nm}", t)
            ctx = np.empty_like(q)
            for h in range(self.A):
                sl = slice(h * d, (h + 1) * d)
                s = q[:, sl] @ k[:, sl].T / np.sqrt(d)
                self._rec(f"{i}.scores", s)
                p = np.exp(s - s.max(-1, keepdims=True))
                p /= p.sum(-1, keepdims=True)
                ctx[:, sl] = p @ v[:, sl]
            self._rec(f"{i}.ctx", ctx)
            a = ctx @ L.Wo + L.bo
            self._rec(f"{i}.attn_out", a)
            r = a + x
            self._rec(f"{i}.res1", r)
            x = layer_norm(r, L.g1, L.b1, self.eps)
            self._rec(f"{i}.x1", x)
            u = x @ L.Wi + L.bi
            self._rec(f"{i}.ffn_in", u)
            g = gelu(u)
            self._rec(f"{i}.gelu", g)
            f = g @ L.Wf + L.bf
            self._rec(f"{i}.ffn_out", f)
            r = f + x
            self._rec(f"{i}.res2", r)
            x = layer_norm(r, L.g2, L.b2, self.eps)
            self._rec(f"{i}.x2", x)
        return x


# ---------------------------------------------------------------- integer model

class IntEncoder:
    """Integer-only forward with scales calibrated from a FloatEncoder trace."""

    def __init__(self, fe: FloatEncoder, trace: dict[str, list], seg_counts_max: int = 256,
                 range_stat: str = "max"):
        """`trace` holds, per tensor, the 99.99th percentile of |x| of every calibration
        chain; `range_stat` reduces them to the clamp range: "max" (the most cautious,
        the default so far) or "median" (clamps the rare extreme chain, finer steps)."""
        self.fe = fe
        self.H, self.A = fe.H, fe.A
        self.d = self.H // self.A
        reduce = {"max": np.max, "median": np.median}[range_stat]
        st = {k: max(float(reduce(v)), 1e-6) for k, v in trace.items()}
        q8 = 127.0
        q16 = float((1 << (RESIDUAL_BITS - 1)) - 1)
        self.s = {k: v / q8 for k, v in st.items()}                  # INT8 activations
        for k in st:                                                  # residual sums: INT16
            if k.endswith("res1") or k.endswith("res2") or k == "emb_sum":
                self.s[k] = st[k] / q16
        self.word_q, self.s_word = quant_weight(fe.word, 8)           # per dimension
        self.pos_q, self.s_pos = quant_weight(fe.pos, 8)
        se = self.s["emb_sum"]                                        # INT16 embedding sum
        self.emb_word_m = to_multiplier(self.s_word / se)
        self.emb_pos_m = to_multiplier(self.s_pos / se)
        self.emb_type = np.round(fe.type0 / se)
        self.layers = []
        for i, L in enumerate(fe.layers):
            self.layers.append(self._layer(i, L))
        self.e_ln = self._ln(fe.eg, fe.eb, "x0")
        self.exp_table = np.round(np.exp(-np.arange(EXP_STEPS) * EXP_STEP) * 65535)
        # GELU tables per layer: INT8 code of ffn_in -> INT8 code of gelu output
        for i, Lq in enumerate(self.layers):
            codes = np.arange(-127, 128)
            g = gelu(codes * self.s[f"{i}.ffn_in"]) / self.s[f"{i}.gelu"]
            Lq["gelu_table"] = np.clip(np.round(g), -127, 127)
        self.recip = np.array([0] + [round((1 << 16) / c) for c in range(1, seg_counts_max + 1)])
        self.heads = {}
        for key, (W, b) in fe.heads.items():
            Wq, sw = quant_weight(W)
            self.heads[key] = (Wq, sw, b)

    # -- parameter preparation
    def _linear(self, W, b, s_in, s_out, lo=-127, hi=127):
        Wq, sw = quant_weight(W)
        bq = np.round(b / (s_in * sw))                                # INT32 bias
        M, S = to_multiplier(s_in * sw / s_out)
        return {"W": Wq, "b": bq, "M": M, "S": S, "lo": lo, "hi": hi}

    def _ln(self, g, b, out_key):
        # y = n * g + b with n in Q(LN_FRACTION); output INT8 at s[out_key]
        s_out = self.s[out_key]
        gq = np.round(g / s_out * (1 << 8))                           # gamma / s_out, Q8
        bq = np.round(b / s_out * (1 << (LN_FRACTION + 8)))
        return {"g": gq, "b": bq}

    def _layer(self, i, L):
        s, p = self.s, f"{i}."
        q16 = (1 << (RESIDUAL_BITS - 1)) - 1
        out = {
            "q": self._linear(L.Wq, L.bq, s[f"{i - 1}.x2"] if i else s["x0"], s[p + "q"]),
            "k": self._linear(L.Wk, L.bk, s[f"{i - 1}.x2"] if i else s["x0"], s[p + "k"]),
            "v": self._linear(L.Wv, L.bv, s[f"{i - 1}.x2"] if i else s["x0"], s[p + "v"]),
            # attention output straight into the INT16 residual domain
            "o": self._linear(L.Wo, L.bo, s[p + "ctx"], s[p + "res1"], -q16, q16),
            "i": self._linear(L.Wi, L.bi, s[p + "x1"], s[p + "ffn_in"]),
            "f": self._linear(L.Wf, L.bf, s[p + "gelu"], s[p + "res2"], -q16, q16),
            "ln1": self._ln(L.g1, L.b1, p + "x1"),
            "ln2": self._ln(L.g2, L.b2, p + "x2"),
        }
        x_in = s[f"{i - 1}.x2"] if i else s["x0"]
        out["skip1"] = to_multiplier(x_in / s[p + "res1"])            # INT8 x -> INT16 residual
        out["skip2"] = to_multiplier(s[p + "x1"] / s[p + "res2"])
        # softmax: index = (max - score) * s_q * s_k / sqrt(d) / EXP_STEP
        out["sm"] = to_multiplier(s[p + "q"] * s[p + "k"] / np.sqrt(self.d) / EXP_STEP)
        # context = P(UINT8/256) @ V(INT8) -> INT8 at s[ctx]
        out["ctx"] = to_multiplier(s[p + "v"] / 256.0 / s[p + "ctx"])
        return out

    # -- integer operators
    @staticmethod
    def _apply(x, P):
        acc = x @ P["W"] + P["b"]
        return requant(acc, P["M"], P["S"], P["lo"], P["hi"])

    def _layernorm(self, r, P):
        """r: INT16 residual rows. Returns INT8 codes."""
        n = r.shape[-1]
        total = r.sum(-1, keepdims=True)
        mean = np.floor(total / n + 0.5)                              # constant multiply in HW
        c = r - mean
        var = np.floor((c * c).sum(-1, keepdims=True) / n)
        std = np.maximum(isqrt(var), 1)
        inv = np.floor(float(1 << (LN_FRACTION + 16)) / std)          # one reciprocal per row
        nrm = np.floor((c * inv + float(1 << 15)) / float(1 << 16))   # Q(LN_FRACTION)
        y = nrm * P["g"] + P["b"]                                     # Q(LN_FRACTION + 8)
        y = np.floor((y + float(1 << (LN_FRACTION + 7))) / float(1 << (LN_FRACTION + 8)))
        return np.clip(y, -127, 127)

    def _softmax(self, scores, M, S):
        """scores INT32 (rows, cols) -> UINT8 probabilities / 256 (rows sum to ~256)."""
        dist = scores.max(-1, keepdims=True) - scores
        idx = np.clip(requant(dist, M, S, 0, 1 << 30), 0, EXP_STEPS - 1).astype(np.int64)
        e = self.exp_table[idx]
        e = np.where(idx >= EXP_STEPS - 1, 0, e)
        tot = e.sum(-1, keepdims=True)
        r = np.floor(float(1 << 24) / tot)                            # one reciprocal per row
        return np.clip(np.floor((e * r + float(1 << 15)) / float(1 << 16)), 0, 255)

    def hidden(self, ids: np.ndarray) -> np.ndarray:
        """INT8 final hidden codes (n, H) at scale s['{last}.x2']."""
        n = len(ids)
        s = self.s
        # embeddings: word + position + type-0 rows, each rescaled per dimension into
        # one INT16 domain, then LayerNorm
        Mw, Sw = self.emb_word_m
        Mp, Sp = self.emb_pos_m
        r = (requant(self.word_q[ids], Mw, Sw, -32767, 32767)
             + requant(self.pos_q[:n], Mp, Sp, -32767, 32767) + self.emb_type)
        r = np.clip(r, -32767, 32767)
        x = self._layernorm(r, self.e_ln)
        d = self.d
        for i, Lq in enumerate(self.layers):
            q, k, v = self._apply(x, Lq["q"]), self._apply(x, Lq["k"]), self._apply(x, Lq["v"])
            ctx = np.empty_like(q)
            Msm, Ssm = Lq["sm"]
            Mc, Sc = Lq["ctx"]
            for h in range(self.A):
                sl = slice(h * d, (h + 1) * d)
                p = self._softmax(q[:, sl] @ k[:, sl].T, Msm, Ssm)
                ctx[:, sl] = requant(p @ v[:, sl], Mc, Sc, -127, 127)
            a = self._apply(ctx, Lq["o"])
            M1, S1 = Lq["skip1"]
            r = np.clip(a + requant(x, M1, S1, -32767, 32767), -32767, 32767)
            x = self._layernorm(r, Lq["ln1"])
            u = self._apply(x, Lq["i"])
            g = Lq["gelu_table"][(u + 127).astype(np.int64)]
            f = self._apply(g, Lq["f"])
            M2, S2 = Lq["skip2"]
            r = np.clip(f + requant(x, M2, S2, -32767, 32767), -32767, 32767)
            x = self._layernorm(r, Lq["ln2"])
        return x

    def head_logits(self, x: np.ndarray, kind: str, name: str, rows: np.ndarray | None = None):
        """Integer head: mean pool (pair/intent) or per-token (slots); logits as INT32."""
        W, sw, b = self.heads[(kind, name)]
        s_x = self.s[f"{len(self.layers) - 1}.x2"]
        if kind == "slots":
            v = x[rows]
            return v @ W + np.round(b / (s_x * sw)), s_x * sw
        cnt = len(rows)
        tot = x[rows].sum(0)
        pooled = np.floor((tot * self.recip[cnt] + float(1 << 15)) / float(1 << 16))
        return pooled @ W + np.round(b / (s_x * sw)), s_x * sw
