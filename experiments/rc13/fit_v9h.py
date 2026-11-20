"""Refit the cost-aware drafter's cost model on v9h board timings and choose RC1.3's coefficients.

1. Replay the v9h board pilot exactly: the 37 cases (index % 5 == 0) in order, plain decode
   and the RC1.2 drafter (coef_dev, v9g costs) with persistent history. The replay must
   reproduce the board's per-case draft statistics; its command logs give the cost features.
2. Fit the v9h cost model on those 74 board runs. v9h runs passes of <= 4 tokens on both
   weight ports, so the pass constant splits in two (FEATURES7; CostAwareDrafter accepts
   7 coefficients). The 6-feature v9g-form fit is kept for comparison.
3. Evaluate on all 181 cases (history fed in workload order, as in the RC1.2 study):
   the drafter with v9g costs and with v9h costs, both priced with the v9h model, against
   plain decode priced the same way.
Writes build/v2/rc1-3/fit.json. usage: python experiments/rc13/fit_v9h.py
"""
import json, math, sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/draft_research'))
import replay, cost, spec_decode  # noqa: E402
from drafters import VoteDrafter, CostAwareDrafter  # noqa: E402

KEYS = ('passes', 'ar_steps', 'drafted', 'accepted', 'zero_accept', 'head_scans')
OUT = ROOT / 'build/v2/rc1-3'
board = json.loads((ROOT / 'build/v2/v9h-board/pilot.json').read_text())
coef_v9g = json.loads((ROOT / 'build/v2/draft-board/expected.json').read_text())['coef_dev']


def dec(e, ids, first, max_new, stop, drafter=None, **kw):
    drafter.begin(ids)
    return spec_decode.decode(e, ids, first, max_new, stop, drafter=drafter, **kw)


def candidate(cases, coef):
    return replay.run(cases, drafter_factory=lambda: CostAwareDrafter(VoteDrafter(prompts=True, ns=(6, 4, 3, 2, 1)), coef,
                                                                     prior=0.5, prior_w=2.0, P=4),
                      decode=dec, feed=lambda d, c, o: d.feed(c, o))


cases, _ = replay.load_cases()
by_index = {c['index']: c for c in board['cases']}
sub = [c for c in cases if c['index'] in by_index]
assert [c['index'] for c in sub] == [c['index'] for c in board['cases']]
ar_sub, cand_sub = replay.run(sub, drafter_factory=None), candidate(sub, coef_v9g)
bad = [(c['index'], k) for c, r in zip(sub, cand_sub) for k in KEYS if r[k] != by_index[c['index']]['candidate'][k]]
assert not bad, bad
rows = [(r['log'], by_index[c['index']]['ar']['decode_seconds']) for c, r in zip(sub, ar_sub)] + \
       [(r['log'], by_index[c['index']]['candidate']['decode_seconds']) for c, r in zip(sub, cand_sub)]
FEATURES7 = ('steps', 'step_pos', 'passes_small', 'passes_large', 'pass_tokens', 'pass_pos', 'pass_pos_groups')


def features7(log, P=4):
    f = [0.0] * 7
    for kind, k, p in log:
        if kind == 's':
            f[0] += 1; f[1] += p
        else:
            f[2 if k <= P else 3] += 1; f[4] += k; f[5] += p; f[6] += p * math.ceil(k / P)
    return f


X = np.array([features7(l) for l, _ in rows]); y = np.array([s for _, s in rows])
coef_v9h = [float(x) for x in np.linalg.lstsq(X, y, rcond=None)[0]]
pred = X @ np.array(coef_v9h); rel = np.abs(pred - y) / y
report = dict(features=FEATURES7, max_rel_err=float(rel.max()), median_rel_err=float(np.median(rel)),
              total_pred=float(pred.sum()), total_meas=float(y.sum()))
coef6, report6 = cost.fit(rows)
cost.predict = lambda coef, log: float(np.dot(features7(log), coef))  # price everything with the v9h model

ar_all = replay.run(cases, drafter_factory=None)
T = lambda runs: sum(cost.predict(coef_v9h, r['log']) for r in runs)
plain = T(ar_all)
res = {}
for name, coef in (('v9g_costs', coef_v9g), ('v9h_costs', coef_v9h)):
    runs = candidate(cases, coef)
    doms = {}
    for c, r, a in zip(cases, runs, ar_all):
        d = doms.setdefault(c['domain'], [0.0, 0.0])
        d[0] += cost.predict(coef_v9h, a['log']); d[1] += cost.predict(coef_v9h, r['log'])
    res[name] = dict(modelled_seconds=T(runs), speedup_vs_plain_v9h=plain / T(runs),
                     by_domain={k: v[0] / v[1] for k, v in doms.items()})
plain_v9g = sum(c['record']['ar']['decode_seconds'] for c in cases)
out = dict(replay_matches_board=True, board_runs=len(rows), coef_v9h=coef_v9h, coef_v9g=coef_v9g, fit=report,
           fit_6feature=dict(report6, coef=[float(x) for x in coef6]),
           plain_v9h_modelled_seconds=plain, plain_v9g_measured_seconds=plain_v9g, candidates=res,
           rc13_vs_plain_v9g=plain_v9g / res['v9h_costs']['modelled_seconds'])
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'fit.json').write_text(json.dumps(out, indent=1) + '\n')
print(json.dumps({k: v for k, v in out.items() if k not in ('coef_v9g',)}, indent=1))
