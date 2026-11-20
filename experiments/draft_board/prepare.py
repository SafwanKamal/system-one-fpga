"""Freeze the board check's inputs from the exact offline replay (host only, needs numpy).

Writes build/v2/draft-board/expected.json:
- coef_dev: the candidate drafter's cost coefficients (cost model fitted on the even split),
  exactly as in experiments/draft_research/evaluate.py;
- coef_all: the evaluation cost model (all 362 v9g board runs);
- per case: the replayed draft statistics of the RC1.1 policy and of the candidate, and the
  modelled decode seconds of both.
The board pilot loads coef_dev from this file (JSON floats round-trip exactly) and checks
that the candidate's draft statistics on the board equal the replay's.
usage: python prepare.py
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/draft_research'))
import replay, cost, spec_decode  # noqa: E402
from drafters import VoteDrafter, CostAwareDrafter  # noqa: E402

KEYS = ('passes', 'ar_steps', 'drafted', 'accepted', 'zero_accept', 'gated_off', 'head_scans')

cases, THR = replay.load_cases()
spec = replay.run(cases, gate_factory=lambda: spec_decode.Gate(threshold=THR))
ar = replay.run(cases, drafter_factory=None)
rows = [(s['log'], c['record']['batched']['decode_seconds']) for c, s in zip(cases, spec)] + \
       [(a['log'], c['record']['ar']['decode_seconds']) for c, a in zip(cases, ar)]
coef_all, report = cost.fit(rows)
dev = [i for i, c in enumerate(cases) if c['index'] % 2 == 0]
coef_dev, _ = cost.fit([rows[i] for i in dev] + [rows[181 + i] for i in dev])
coef_dev = [float(x) for x in coef_dev]


def dec(e, ids, first, max_new, stop, drafter=None, **kw):
    drafter.begin(ids)
    return spec_decode.decode(e, ids, first, max_new, stop, drafter=drafter, **kw)


cand = replay.run(cases, drafter_factory=lambda: CostAwareDrafter(VoteDrafter(prompts=True, ns=(6, 4, 3, 2, 1)), coef_dev,
                                                                 prior=0.5, prior_w=2.0, P=4),
                  decode=dec, feed=lambda d, c, o: d.feed(c, o))
T = lambda r: cost.predict(coef_all, r['log'])
out = dict(coef_dev=coef_dev, coef_all=[float(x) for x in coef_all], features=list(cost.FEATURES), cost_report=report,
           gate_threshold=THR, cases=[])
for c, s, d, a in zip(cases, spec, cand, ar):
    out['cases'].append(dict(key=c['key'], index=c['index'], domain=c['domain'],
                             rc11={k: s[k] for k in KEYS}, candidate={k: d[k] for k in KEYS},
                             model_ar_seconds=T(a), model_rc11_seconds=T(s), model_candidate_seconds=T(d)))
r = sum(x['model_rc11_seconds'] for x in out['cases']); q = sum(x['model_candidate_seconds'] for x in out['cases'])
odd = [x for x in out['cases'] if x['index'] % 2 == 1]
out['model_ratio_all'] = r / q
out['model_ratio_odd'] = sum(x['model_rc11_seconds'] for x in odd) / sum(x['model_candidate_seconds'] for x in odd)
dst = ROOT / 'build/v2/draft-board'
dst.mkdir(parents=True, exist_ok=True)
(dst / 'expected.json').write_text(json.dumps(out, indent=1) + '\n')
print('model candidate/rc11: all %.4f odd %.4f' % (out['model_ratio_all'], out['model_ratio_odd']))
print('modelled seconds: rc11 %.1f candidate %.1f' % (r, q))
