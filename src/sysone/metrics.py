"""Evaluation metrics: accuracy against a floor, calibration, selective risk.

Pure NumPy, no sklearn, so the same code runs in the cloud container, on the
device VM, and inside the hardware-in-the-loop harness later.

Two deliberate choices worth stating up front:

1. **ECE is reported two ways.** Equal-width binning is the convention (Guo et al.
   2017) and is what other papers will be compared against, but it is unstable
   when confidences pile up near 1.0 -- most of the mass lands in one bin and the
   estimate is dominated by it. Equal-mass binning fixes that and usually reads
   higher. Reporting only the flattering one would be cherry-picking, so both are
   always computed, and the write-up should quote equal-width for comparability
   and equal-mass as the honest number.

2. **Brier is the full multiclass score**, sum over all K classes, range [0, 2].
   A "top-label only" Brier looks better and is not comparable to the literature.
"""

from __future__ import annotations

import numpy as np


def accuracy(probs: np.ndarray, y: np.ndarray) -> float:
    return float((probs.argmax(1) == y).mean())


def brier(probs: np.ndarray, y: np.ndarray) -> float:
    """Multiclass Brier score: mean_i sum_k (p_ik - 1[y_i = k])^2. Lower is better."""
    onehot = np.zeros_like(probs)
    onehot[np.arange(len(y)), y] = 1.0
    return float(((probs - onehot) ** 2).sum(1).mean())


def nll(probs: np.ndarray, y: np.ndarray, eps: float = 1e-12) -> float:
    return float(-np.log(np.clip(probs[np.arange(len(y)), y], eps, 1.0)).mean())


def _ece_from_bins(conf: np.ndarray, correct: np.ndarray, edges: np.ndarray) -> float:
    n = len(conf)
    total = 0.0
    for lo, hi, last in zip(edges[:-1], edges[1:], [False] * (len(edges) - 2) + [True]):
        m = (conf > lo) & (conf <= hi) if not last else (conf > lo) & (conf <= hi + 1e-12)
        if lo == edges[0]:
            m |= conf == lo
        k = int(m.sum())
        if k == 0:
            continue
        total += (k / n) * abs(correct[m].mean() - conf[m].mean())
    return float(total)


def ece_equal_width(probs: np.ndarray, y: np.ndarray, n_bins: int = 10) -> float:
    """Top-label ECE with equal-width bins on [0, 1]. The conventional number."""
    conf = probs.max(1)
    correct = (probs.argmax(1) == y).astype(float)
    return _ece_from_bins(conf, correct, np.linspace(0.0, 1.0, n_bins + 1))


def ece_equal_mass(probs: np.ndarray, y: np.ndarray, n_bins: int = 10) -> float:
    """Top-label ECE with equal-count bins. More stable when confidence is peaked."""
    conf = probs.max(1)
    correct = (probs.argmax(1) == y).astype(float)
    qs = np.quantile(conf, np.linspace(0.0, 1.0, n_bins + 1))
    edges = np.unique(qs)
    if len(edges) < 2:
        return 0.0
    edges[0], edges[-1] = 0.0, 1.0
    return _ece_from_bins(conf, correct, edges)


def reliability_table(probs: np.ndarray, y: np.ndarray, n_bins: int = 10) -> list[dict]:
    """Per-bin counts, mean confidence and mean accuracy -- the raw material for a
    reliability diagram, and what lets a reader recompute ECE themselves."""
    conf = probs.max(1)
    correct = (probs.argmax(1) == y).astype(float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    rows = []
    for i, (lo, hi) in enumerate(zip(edges[:-1], edges[1:])):
        m = (conf > lo) & (conf <= hi)
        if i == 0:
            m |= conf == 0.0
        k = int(m.sum())
        rows.append({
            "bin": f"({lo:.1f}, {hi:.1f}]",
            "n": k,
            "mean_conf": float(conf[m].mean()) if k else None,
            "accuracy": float(correct[m].mean()) if k else None,
            "gap": float(correct[m].mean() - conf[m].mean()) if k else None,
        })
    return rows


def selective_curve(
    probs: np.ndarray, y: np.ndarray, coverages: np.ndarray | None = None
) -> list[dict]:
    """Accuracy on the most-confident fraction of inputs, for a grid of coverages.

    This is the curve the cascade argument rests on: if the FPGA answers only the
    top c fraction by confidence and escalates the rest, this is the accuracy it
    delivers on the part it keeps.
    """
    if coverages is None:
        coverages = np.arange(0.1, 1.01, 0.1)
    conf = probs.max(1)
    correct = (probs.argmax(1) == y).astype(float)
    order = np.argsort(-conf)
    correct_sorted = correct[order]
    n = len(y)
    out = []
    for c in coverages:
        k = max(1, int(round(c * n)))
        out.append({
            "coverage": float(k / n),
            "accuracy": float(correct_sorted[:k].mean()),
            "threshold": float(conf[order][k - 1]),
            "n_kept": k,
        })
    return out


def auroc(scores: np.ndarray, positive: np.ndarray) -> float:
    """Rank-based AUROC (Mann-Whitney U), ties handled by average ranks."""
    pos, neg = int(positive.sum()), int((~positive).sum())
    if pos == 0 or neg == 0:
        return float("nan")
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=float)
    ranks[order] = np.arange(1, len(scores) + 1, dtype=float)
    s_sorted = scores[order]
    i = 0
    while i < len(s_sorted):  # average ranks within tie groups
        j = i
        while j + 1 < len(s_sorted) and s_sorted[j + 1] == s_sorted[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = ranks[order[i:j + 1]].mean()
        i = j + 1
    return float((ranks[positive].sum() - pos * (pos + 1) / 2) / (pos * neg))


def evaluate(
    probs: np.ndarray,
    y: np.ndarray,
    is_oos: np.ndarray,
    oos_id: int,
    floor: float,
    n_bins: int = 10,
) -> dict:
    """The full report for one model on one split.

    In-scope accuracy and OOS recall are kept apart on purpose. Pooling them
    rewards a model that simply learns to say "oos" often, because OOS is 18% of
    the combined test set -- the exact failure mode a 150:1 class imbalance in the
    training data invites.
    """
    pred = probs.argmax(1)
    ins = ~is_oos
    combined_acc = float((pred == y).mean())
    return {
        "n": int(len(y)),
        "combined_accuracy": combined_acc,
        "majority_floor": float(floor),
        "lift_over_floor": combined_acc - float(floor),
        "in_scope_accuracy": float((pred[ins] == y[ins]).mean()) if ins.any() else None,
        "in_scope_n": int(ins.sum()),
        "oos_recall": float((pred[is_oos] == oos_id).mean()) if is_oos.any() else None,
        "oos_n": int(is_oos.sum()),
        "in_scope_false_oos_rate": float((pred[ins] == oos_id).mean()) if ins.any() else None,
        "brier": brier(probs, y),
        "nll": nll(probs, y),
        "ece_equal_width": ece_equal_width(probs, y, n_bins),
        "ece_equal_mass": ece_equal_mass(probs, y, n_bins),
        "mean_confidence": float(probs.max(1).mean()),
        "oos_auroc_by_maxprob": auroc(-probs.max(1), is_oos),
        "oos_auroc_by_oos_prob": auroc(probs[:, oos_id], is_oos),
        "selective": selective_curve(probs, y),
        "reliability": reliability_table(probs, y, n_bins),
    }
