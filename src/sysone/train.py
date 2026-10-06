"""Training loop and temperature calibration."""

from __future__ import annotations

import time

import numpy as np

from .metrics import ece_equal_width, nll
from .model import Adam, HashedBagClassifier, ModelConfig, encode, softmax
from .quant import QATSpec


def _logits_qat(model: HashedBagClassifier, flat: np.ndarray, offsets: np.ndarray,
                qat: QATSpec, batch: int = 2048) -> np.ndarray:
    n = len(offsets) - 1
    out = np.empty((n, model.cfg.n_classes), dtype=np.float32)
    for s in range(0, n, batch):
        e = min(s + batch, n)
        sub = offsets[s:e + 1]
        out[s:e] = model.forward(flat[sub[0]:sub[-1]], sub - sub[0], qat=qat)["logits"]
    return out


def _batches(n: int, size: int, rng: np.random.Generator):
    order = rng.permutation(n)
    for s in range(0, n, size):
        yield order[s:s + size]


def _gather(flat: np.ndarray, offsets: np.ndarray, idx: np.ndarray):
    """Re-pack an arbitrary subset of inputs into a contiguous CSR batch."""
    lens = (offsets[idx + 1] - offsets[idx]).astype(np.int64)
    out_off = np.zeros(len(idx) + 1, dtype=np.int64)
    np.cumsum(lens, out=out_off[1:])
    take = np.concatenate([np.arange(offsets[i], offsets[i + 1]) for i in idx]) \
        if len(idx) else np.zeros(0, dtype=np.int64)
    return flat[take], out_off


def train(
    cfg: ModelConfig,
    train_texts: list[str], train_y: np.ndarray,
    val_texts: list[str], val_y: np.ndarray,
    epochs: int = 25,
    batch_size: int = 128,
    lr: float = 3e-3,
    dropout: float = 0.1,
    weight_decay: float = 1e-5,
    class_weight: np.ndarray | None = None,
    qat_bits: tuple[int, int, int] | None = None,
    qat_warmup_epochs: int = 3,
    qat_refresh_steps: int = 50,
    verbose: bool = True,
    init_E: np.ndarray | None = None,
    emb_lr_scale: float = 1.0,
    freeze_emb_epochs: int = 0,
    anchor_weight: float = 0.0,
    soft_targets: np.ndarray | None = None,
) -> tuple[HashedBagClassifier, dict]:
    """Train and keep the checkpoint with the best validation accuracy.

    Selection is on accuracy, not loss: loss keeps improving after accuracy
    plateaus because the model sharpens confidences it already has right, and a
    sharper model is a worse-calibrated one. Calibration is repaired afterwards by
    temperature scaling on the same validation split.

    ``qat_bits`` turns on quantisation-aware training as ``(emb, w1, w2)`` widths.
    Training starts in float for ``qat_warmup_epochs`` and only then switches the
    rounding on. Starting straight into ternary fails: the weights are still near
    their random init, almost all of them fall under the ternary threshold, the
    fake-quantised table is nearly all zeros, and no gradient signal survives.
    Warming up first puts the weights somewhere the quantiser can represent.

    ``init_E`` starts from a pretrained table instead of the random one. The
    table is then frozen for ``freeze_emb_epochs`` (so the head first learns to
    read the pretrained geometry), trained at ``emb_lr_scale`` times the head's
    learning rate, and pulled back towards ``init_E`` with ``anchor_weight``.

    ``soft_targets`` (one probability row per training input) switches the loss
    to cross-entropy against those distributions, i.e. distillation from a
    teacher; ``train_y`` is then only used for the class weights.

    During QAT the validation pass is run with the same fake quantisation as
    training, so checkpoint selection is made on what the exported model will
    actually do rather than on a float score the deployed model never achieves.
    """
    rng = np.random.default_rng(cfg.seed)
    model = HashedBagClassifier(cfg)
    if init_E is not None:
        assert init_E.shape == model.E.shape
        model.E = init_E.astype(np.float32).copy()
    opt = Adam(model, lr=lr, weight_decay=weight_decay)

    tr_flat, tr_off = encode(train_texts, cfg)
    va_flat, va_off = encode(val_texts, cfg)

    best = {"acc": -1.0, "epoch": -1}
    best_w = None
    history = []
    t0 = time.time()
    qat = None
    step = 0

    for ep in range(epochs):
        qat_on = qat_bits is not None and ep >= qat_warmup_epochs
        for idx in _batches(len(train_y), batch_size, rng):
            if qat_on and step % qat_refresh_steps == 0:
                qat = QATSpec.build(model, *qat_bits)
            bf, bo = _gather(tr_flat, tr_off, idx)
            fwd = model.forward(bf, bo, dropout=dropout, rng=rng,
                                qat=qat if qat_on else None)
            sw = None if class_weight is None else class_weight[train_y[idx]]
            grads = model.backward(fwd, bf, bo, train_y[idx], sample_weight=sw,
                                   soft_targets=None if soft_targets is None else soft_targets[idx])
            opt.step(grads, emb_lr_scale=0.0 if ep < freeze_emb_epochs else emb_lr_scale,
                     emb_anchor=init_E, anchor_weight=anchor_weight)
            step += 1

        if qat_on:
            qat = QATSpec.build(model, *qat_bits)
            va_logits = _logits_qat(model, va_flat, va_off, qat)
        else:
            va_logits = model.logits(va_flat, va_off)
        va_p = softmax(va_logits)
        acc = float((va_p.argmax(1) == val_y).mean())
        history.append({"epoch": ep, "val_acc": acc, "val_nll": nll(va_p, val_y),
                        "val_ece": ece_equal_width(va_p, val_y)})
        if acc > best["acc"]:
            best = {"acc": acc, "epoch": ep}
            best_w = (model.E.copy(), model.W1.copy(), model.b1.copy(),
                      model.W2.copy(), model.b2.copy())
        if verbose and (ep % 5 == 0 or ep == epochs - 1):
            print(f"  epoch {ep:3d}  val_acc={acc:.4f}  nll={history[-1]['val_nll']:.4f}"
                  f"  ece={history[-1]['val_ece']:.4f}", flush=True)

    if best_w is not None:
        model.E, model.W1, model.b1, model.W2, model.b2 = best_w

    return model, {
        "best_val_acc": best["acc"],
        "best_epoch": best["epoch"],
        "train_seconds": time.time() - t0,
        "history": history,
    }


def fit_temperature(logits: np.ndarray, y: np.ndarray,
                    lo: float = 0.25, hi: float = 10.0, iters: int = 60) -> float:
    """Temperature that minimises validation NLL, by golden-section search.

    NLL in T is unimodal for a fixed set of logits, so a derivative-free bracket
    search is enough and avoids another gradient implementation. The bound at 0.25
    is there to catch the pathological case of an under-confident model; in
    practice the optimum lands above 1.0 for this architecture.
    """
    phi = (np.sqrt(5.0) - 1.0) / 2.0
    a, b = lo, hi
    c, d = b - phi * (b - a), a + phi * (b - a)
    fc = nll(softmax(logits / c), y)
    fd = nll(softmax(logits / d), y)
    for _ in range(iters):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - phi * (b - a)
            fc = nll(softmax(logits / c), y)
        else:
            a, c, fc = c, d, fd
            d = a + phi * (b - a)
            fd = nll(softmax(logits / d), y)
        if abs(b - a) < 1e-4:
            break
    return float((a + b) / 2.0)
