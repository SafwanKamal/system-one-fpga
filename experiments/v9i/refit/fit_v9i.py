"""Refit the cost-aware drafter's cost model on v9i board timings (RC1.4 coefficients).

1. Replay the 36-case v9i raw pilot (build/v2/rc1-4/evidence-*/board/raw/pilot.json) in board
   order: plain decode and the qualification drafter (coef_dev, P=4) with persistent history.
   The replay must reproduce the board's per-case draft statistics.
2. Fit the 7-feature model with P=2 attention groups on those 72 board runs. Two forms:
   free (7 coefficients) and shared pass constant (dual weight port: passes<=P and >P cost
   the same). Pick the form with lower leave-one-out error.
3. Evaluate on all 181 cases with history in workload order: the RC1.4 drafter (P=2) with the
   modelled coefficients and with the refit, priced by the refit, against plain decode.
Writes experiments/v9i/refit/fit.json. usage: python experiments/v9i/refit/fit_v9i.py [--pilot PATH]
"""
import argparse, json, math, sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments/draft_research'))
import replay, spec_decode  # noqa: E402
from drafters import VoteDrafter, CostAwareDrafter  # noqa: E402

KEYS = ('passes', 'ar_steps', 'drafted', 'accepted', 'zero_accept', 'head_scans')
FEATURES7 = ('steps', 'step_pos', 'passes_small', 'passes_large', 'pass_tokens', 'pass_pos', 'pass_pos_groups')
P = 2
ap = argparse.ArgumentParser()
ap.add_argument('--pilot', type=Path, default=ROOT / 'build/v2/rc1-4/evidence-20261122-144249/board/raw/pilot.json')
ap.add_argument('--coef-dev', type=Path, default=ROOT / 'experiments/v9i/refit/coef_dev.json')
ap.add_argument('--modelled', type=Path, default=ROOT / 'experiments/v9i/refit/coef_v9i_modelled.json')
a = ap.parse_args()
board = json.loads(a.pilot.read_text())
coef_dev = json.loads(a.coef_dev.read_text())
coef_model = json.loads(a.modelled.read_text())


def dec(e, ids, first, max_new, stop, drafter=None, **kw):
    drafter.begin(ids)
    return spec_decode.decode(e, ids, first, max_new, stop, drafter=drafter, **kw)


def drafted(cases, coef, p):
    return replay.run(cases, drafter_factory=lambda: CostAwareDrafter(VoteDrafter(prompts=True, ns=(6, 4, 3, 2, 1)), coef,
                                                                     prior=0.5, prior_w=2.0, P=p),
                      decode=dec, feed=lambda d, c, o: d.feed(c, o))


def features7(log, p=P):
    f = [0.0] * 7
    for kind, k, pos in log:
        if kind == 's':
            f[0] += 1; f[1] += pos
        else:
            f[2 if k <= p else 3] += 1; f[4] += k; f[5] += pos; f[6] += pos * math.ceil(k / p)
    return f


cases, _ = replay.load_cases()
by_index = {c['index']: c for c in board['cases']}
sub = [c for c in cases if c['index'] in by_index]
assert [c['index'] for c in sub] == [c['index'] for c in board['cases']], 'pilot order differs from workload order'
ar_sub, cand_sub = replay.run(sub, drafter_factory=None), drafted(sub, coef_dev, 4)
bad = [(c['index'], k) for c, r in zip(sub, cand_sub) for k in KEYS if r[k] != by_index[c['index']]['candidate'][k]]
assert not bad, bad
rows = [(r['log'], by_index[c['index']]['ar']['decode_seconds'], c['domain']) for c, r in zip(sub, ar_sub)] + \
       [(r['log'], by_index[c['index']]['candidate']['decode_seconds'], c['domain']) for c, r in zip(sub, cand_sub)]
X = np.array([features7(l) for l, _, _ in rows]); y = np.array([s for _, s, _ in rows])
SHARE = np.array([[1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0], [0, 0, 1, 0, 0, 0],
                  [0, 0, 0, 1, 0, 0], [0, 0, 0, 0, 1, 0], [0, 0, 0, 0, 0, 1]], float)  # 6 params -> 7 coefs


def solve(Xm, ym, shared):
    if shared:
        return SHARE @ np.linalg.lstsq(Xm @ SHARE, ym, rcond=None)[0]
    return np.linalg.lstsq(Xm, ym, rcond=None)[0]


def report(coef):
    pred = X @ coef; rel = np.abs(pred - y) / y
    loo = []
    for i in range(len(y)):
        m = np.arange(len(y)) != i
        loo.append(abs(X[i] @ solve(X[m], y[m], shared) - y[i]) / y[i])
    return dict(max_rel_err=float(rel.max()), median_rel_err=float(np.median(rel)), loo_median_rel_err=float(np.median(loo)),
                loo_max_rel_err=float(np.max(loo)), total_pred=float(pred.sum()), total_meas=float(y.sum()))


fits = {}
for shared in (False, True):
    coef = solve(X, y, shared)
    fits['shared' if shared else 'free'] = dict(coef=[float(c) for c in coef], **report(coef))
choice = min(fits, key=lambda k: fits[k]['loo_median_rel_err'])
coef_fit = fits[choice]['coef']
modelled_err = np.abs(X @ np.array(coef_model) - y) / y

price = lambda log: float(np.dot(features7(log), coef_fit))
ar_all = replay.run(cases, drafter_factory=None)
plain = sum(price(r['log']) for r in ar_all)
res = {}
for name, coef, p in (('qual_coef_dev_P4', coef_dev, 4), ('rc14_modelled_P2', coef_model, P), ('rc14_refit_P2', coef_fit, P)):
    runs = drafted(cases, coef, p)
    doms = {}
    for c, r, ar in zip(cases, runs, ar_all):
        d = doms.setdefault(c['domain'], [0.0, 0.0])
        d[0] += price(ar['log']); d[1] += price(r['log'])
    t = sum(price(r['log']) for r in runs)
    res[name] = dict(modelled_seconds=t, speedup_vs_plain=plain / t, by_domain={k: v[0] / v[1] for k, v in sorted(doms.items())},
                     accepted=sum(r['accepted'] for r in runs), passes=sum(r['passes'] for r in runs))
out = dict(replay_matches_board=True, board_runs=len(rows), pilot=str(a.pilot.relative_to(ROOT)).replace('\\', '/'),
           features=FEATURES7, P=P, choice=choice, coef_v9i_refit=coef_fit, fits=fits,
           modelled_on_board=dict(median_rel_err=float(np.median(modelled_err)), max_rel_err=float(modelled_err.max()),
                                  total_pred=float((X @ np.array(coef_model)).sum())),
           plain_modelled_seconds=plain, candidates=res)
(ROOT / 'experiments/v9i/refit/fit.json').write_text(json.dumps(out, indent=1) + '\n')
print(json.dumps(out, indent=1))
