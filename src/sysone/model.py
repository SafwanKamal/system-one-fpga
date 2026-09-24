"""Hashed embedding-bag classifier, forward and backward in NumPy.

    indices --> embedding table lookup --> mean pool --> Linear --> ReLU --> Linear --> softmax

Why this shape and not something better: every stage has to survive the trip to an
Artix-7 with no hard CPU. Lookup and mean-pool are DDR2-friendly because an input
touches only a few dozen scattered rows, which is random access, the one thing
DDR2 on this board does acceptably. The head is two dense layers small enough to
live in BRAM and reuse the existing packed-weight MAC lanes. There is no attention
and no recurrence, so there is no sequence state to buffer.

Training is plain NumPy on CPU. The embedding table dominates the parameter count
but is touched sparsely -- about 30 rows per input -- so the optimiser updates
only the rows a batch actually used. Dense Adam over a 4M-element table would
spend roughly 200x more arithmetic on untouched rows than on the model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .hashing import encode_corpus


@dataclass
class ModelConfig:
    n_buckets: int = 32768      # embedding table rows; power of two (index = mask)
    dim: int = 128              # embedding width
    hidden: int = 128           # MLP hidden width
    n_classes: int = 151
    use_bigrams: bool = True
    max_tokens: int = 64
    use_trigrams: bool = False
    char_ngrams: tuple[int, int] | None = None
    seed: int = 0

    @property
    def n_params(self) -> int:
        return (
            self.n_buckets * self.dim
            + self.dim * self.hidden + self.hidden
            + self.hidden * self.n_classes + self.n_classes
        )

    @property
    def head_params(self) -> int:
        return (
            self.dim * self.hidden + self.hidden
            + self.hidden * self.n_classes + self.n_classes
        )


def pool(E: np.ndarray, flat: np.ndarray, offsets: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Mean-pool embedding rows per input.

    ``reduceat`` sums each contiguous segment in one pass. Counts come back too
    because the backward pass needs the 1/n factor and the integer path needs n
    to reproduce the same division.
    """
    counts = np.diff(offsets).astype(np.float32)
    summed = np.add.reduceat(E[flat], offsets[:-1], axis=0)
    return summed / counts[:, None], counts


def softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


@dataclass
class HashedBagClassifier:
    cfg: ModelConfig
    E: np.ndarray = field(init=False)
    W1: np.ndarray = field(init=False)
    b1: np.ndarray = field(init=False)
    W2: np.ndarray = field(init=False)
    b2: np.ndarray = field(init=False)

    def __post_init__(self) -> None:
        rng = np.random.default_rng(self.cfg.seed)
        c = self.cfg
        # Small embedding init: pooled activations are a mean of ~30 rows, so the
        # scale that reaches the head is already close to the per-row scale.
        self.E = (rng.standard_normal((c.n_buckets, c.dim)) * 0.05).astype(np.float32)
        self.W1 = (rng.standard_normal((c.dim, c.hidden)) * np.sqrt(2.0 / c.dim)).astype(np.float32)
        self.b1 = np.zeros(c.hidden, dtype=np.float32)
        self.W2 = (rng.standard_normal((c.hidden, c.n_classes)) * np.sqrt(1.0 / c.hidden)).astype(np.float32)
        self.b2 = np.zeros(c.n_classes, dtype=np.float32)

    # ---------------------------------------------------------------- forward

    def forward(self, flat: np.ndarray, offsets: np.ndarray, dropout: float = 0.0,
                rng: np.random.Generator | None = None, qat=None) -> dict:
        """``qat`` is a ``QATSpec``; when given, weights are fake-quantised on the
        way through and gradients flow straight past the rounding (STE).

        Only the embedding rows this batch touches are quantised, not the whole
        table. That is what makes QAT affordable on a 4M-row table on CPU, and it
        is exact: a row's fake-quantised value depends only on that row and the
        frozen per-dimension scale.
        """
        if qat is None:
            x, counts = pool(self.E, flat, offsets)
            W1, W2 = self.W1, self.W2
        else:
            rows = qat.emb.apply(self.E[flat])
            counts = np.diff(offsets).astype(np.float32)
            x = np.add.reduceat(rows, offsets[:-1], axis=0) / counts[:, None]
            W1, W2 = qat.w1.apply(self.W1), qat.w2.apply(self.W2)

        if dropout > 0.0:
            assert rng is not None
            mask = (rng.random(x.shape) >= dropout).astype(np.float32) / (1.0 - dropout)
            x = x * mask
        else:
            mask = None
        h_pre = x @ W1 + self.b1
        h = np.maximum(h_pre, 0.0)
        logits = h @ W2 + self.b2
        return {"x": x, "counts": counts, "h_pre": h_pre, "h": h, "logits": logits,
                "mask": mask, "W1": W1, "W2": W2}

    def logits(self, flat: np.ndarray, offsets: np.ndarray, batch: int = 2048) -> np.ndarray:
        n = len(offsets) - 1
        out = np.empty((n, self.cfg.n_classes), dtype=np.float32)
        for s in range(0, n, batch):
            e = min(s + batch, n)
            sub = offsets[s:e + 1]
            out[s:e] = self.forward(flat[sub[0]:sub[-1]], sub - sub[0])["logits"]
        return out

    def predict_proba(self, flat: np.ndarray, offsets: np.ndarray,
                      temperature: float = 1.0) -> np.ndarray:
        return softmax(self.logits(flat, offsets) / temperature)

    # --------------------------------------------------------------- backward

    def backward(self, fwd: dict, flat: np.ndarray, offsets: np.ndarray,
                 y: np.ndarray, soft_targets: np.ndarray | None = None,
                 sample_weight: np.ndarray | None = None) -> dict:
        """Gradients for cross-entropy, or for KL against a teacher if given.

        ``soft_targets`` is the distillation hook the plan calls for. dL/dlogits
        has the same form either way -- (p - target)/B -- so the teacher can be
        swapped in later without touching this code.

        ``sample_weight`` exists because of the 150:1 in-scope/out-of-scope
        imbalance: without it the OOS class contributes so little gradient that
        the model learns to never predict it, which would silently destroy the
        abstention behaviour the whole calibration story depends on. Weights
        normalise to mean 1 so the effective learning rate does not move when
        weighting is switched on.
        """
        n = len(y)
        p = softmax(fwd["logits"])
        target = np.zeros_like(p) if soft_targets is None else soft_targets.astype(np.float32)
        if soft_targets is None:
            target[np.arange(n), y] = 1.0
        dlogits = (p - target) / n
        if sample_weight is not None:
            w = sample_weight.astype(np.float32)
            dlogits = dlogits * (w / w.mean())[:, None]

        # Straight-through estimator: the backward pass uses whatever weights the
        # forward pass actually used (fake-quantised under QAT, float otherwise),
        # and the resulting gradient is applied to the float master copy as if the
        # rounding step were the identity.
        W1_used, W2_used = fwd["W1"], fwd["W2"]
        gW2 = fwd["h"].T @ dlogits
        gb2 = dlogits.sum(0)
        dh = dlogits @ W2_used.T
        dh_pre = dh * (fwd["h_pre"] > 0)
        gW1 = fwd["x"].T @ dh_pre
        gb1 = dh_pre.sum(0)
        dx = dh_pre @ W1_used.T
        if fwd["mask"] is not None:
            dx = dx * fwd["mask"]

        # Mean pool: each row that input i touched receives dx[i] / counts[i].
        # repeat() expands per-input gradient back onto the flat index stream.
        per_token = np.repeat(dx / fwd["counts"][:, None],
                              np.diff(offsets).astype(np.int64), axis=0)
        return {"gW1": gW1, "gb1": gb1, "gW2": gW2, "gb2": gb2,
                "g_emb_flat": per_token.astype(np.float32), "emb_rows": flat}


class Adam:
    """Dense Adam for the head, sparse Adam for the embedding table.

    The sparse branch uses the global step count for bias correction, matching
    PyTorch's SparseAdam. It is not the same as dense Adam -- a row's moments go
    stale between the batches that touch it -- but it is the standard trade and
    it is what makes CPU training of a 4M-row table practical.
    """

    def __init__(self, model: HashedBagClassifier, lr: float = 2e-3,
                 betas: tuple[float, float] = (0.9, 0.999), eps: float = 1e-8,
                 weight_decay: float = 0.0):
        self.m = model
        self.lr, (self.b1, self.b2), self.eps = lr, betas, eps
        self.wd = weight_decay
        self.t = 0
        self.state = {k: [np.zeros_like(getattr(model, k)), np.zeros_like(getattr(model, k))]
                      for k in ("W1", "b1", "W2", "b2")}
        self.mE = np.zeros_like(model.E)
        self.vE = np.zeros_like(model.E)

    def step(self, grads: dict) -> None:
        self.t += 1
        bc1 = 1.0 - self.b1 ** self.t
        bc2 = 1.0 - self.b2 ** self.t

        for k in ("W1", "b1", "W2", "b2"):
            g = grads["g" + k]
            p = getattr(self.m, k)
            if self.wd and k.startswith("W"):
                g = g + self.wd * p
            m, v = self.state[k]
            m *= self.b1; m += (1 - self.b1) * g
            v *= self.b2; v += (1 - self.b2) * (g * g)
            p -= self.lr * (m / bc1) / (np.sqrt(v / bc2) + self.eps)

        rows = grads["emb_rows"]
        g = grads["g_emb_flat"]
        # A row can appear several times in one batch; accumulate before updating
        # so a repeated word does not get several partial Adam steps.
        uniq, inv = np.unique(rows, return_inverse=True)
        acc = np.zeros((len(uniq), g.shape[1]), dtype=np.float32)
        np.add.at(acc, inv, g)

        m, v = self.mE[uniq], self.vE[uniq]
        m = self.b1 * m + (1 - self.b1) * acc
        v = self.b2 * v + (1 - self.b2) * (acc * acc)
        self.mE[uniq], self.vE[uniq] = m, v
        self.m.E[uniq] -= self.lr * (m / bc1) / (np.sqrt(v / bc2) + self.eps)


def encode(texts: list[str], cfg: ModelConfig) -> tuple[np.ndarray, np.ndarray]:
    return encode_corpus(texts, cfg.n_buckets, cfg.use_bigrams, cfg.max_tokens,
                         cfg.use_trigrams, cfg.char_ngrams)
