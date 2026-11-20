"""v9g decode-time model fitted to the v9g board pilot, applied to replay command logs.

Features follow the hardware (docs/research/2026-11-19-core-feasibility.md):
- single step at position p: a + b*p (28 layers of cmd 2, one head scan, host);
- verify pass of k tokens at position p: c + d*k + p*(e + f*ceil(k/4)) (28 layers of cmd 8;
  K/V tile load and the P=4 attention passes; one cmd 11 + cmd 12 head scan).
Fitted by least squares on per-case decode seconds of both modes (362 runs).
"""
import math
import numpy as np

FEATURES = ('steps', 'step_pos', 'passes', 'pass_tokens', 'pass_pos', 'pass_pos_groups')


def features(log, P=4):
    f = dict.fromkeys(FEATURES, 0.0)
    for kind, k, p in log:
        if kind == 's':
            f['steps'] += 1; f['step_pos'] += p
        else:
            f['passes'] += 1; f['pass_tokens'] += k; f['pass_pos'] += p; f['pass_pos_groups'] += p * math.ceil(k / P)
    return [f[n] for n in FEATURES]


def fit(rows):
    """rows: list of (log, seconds). Returns coefficients and fit report."""
    X = np.array([features(l) for l, _ in rows]); y = np.array([s for _, s in rows])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ coef
    rel = np.abs(pred - y) / y
    r2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return coef, dict(r2=float(r2), max_rel_err=float(rel.max()), median_rel_err=float(np.median(rel)),
                      total_pred=float(pred.sum()), total_meas=float(y.sum()),
                      coef={n: float(c) for n, c in zip(FEATURES, coef)})


def predict(coef, log):
    return float(np.dot(features(log), coef))
