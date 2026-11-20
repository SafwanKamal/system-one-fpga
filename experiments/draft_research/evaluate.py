"""Held-out evaluation in PROTOCOL.md (odd split). usage: python evaluate.py out.json"""
import json, sys
import replay, cost, spec_decode
from drafters import VoteDrafter, CostAwareDrafter

cases, THR = replay.load_cases()
spec = replay.run(cases, gate_factory=lambda: spec_decode.Gate(threshold=THR))
ar = replay.run(cases, drafter_factory=None)
rows = [(s['log'], c['record']['batched']['decode_seconds']) for c, s in zip(cases, spec)] + \
       [(a['log'], c['record']['ar']['decode_seconds']) for c, a in zip(cases, ar)]
coef_all, report = cost.fit(rows)
dev = [i for i, c in enumerate(cases) if c['index'] % 2 == 0]
coef_dev, _ = cost.fit([rows[i] for i in dev] + [rows[181 + i] for i in dev])


def dec(e, ids, first, max_new, stop, drafter=None, **kw):
    drafter.begin(ids)
    return spec_decode.decode(e, ids, first, max_new, stop, drafter=drafter, **kw)


cand = replay.run(cases, drafter_factory=lambda: CostAwareDrafter(VoteDrafter(prompts=True, ns=(6, 4, 3, 2, 1)), coef_dev,
                                                                 prior=0.5, prior_w=2.0, P=4),
                  decode=dec, feed=lambda d, c, o: d.feed(c, o))
T = lambda r: cost.predict(coef_all, r['log'])


def summary(split):
    idx = [i for i, c in enumerate(cases) if c['index'] % 2 == split]
    out = {}
    for d in ('general', 'maintenance', 'long', 'tool', 'all'):
        j = [i for i in idx if d == 'all' or cases[i]['domain'] == d]
        if not j:
            continue
        a = sum(T(ar[i]) for i in j); r = sum(T(spec[i]) for i in j); c = sum(T(cand[i]) for i in j)
        out[d] = dict(n=len(j), rc11_speedup=round(a / r, 4), candidate_speedup=round(a / c, 4), candidate_over_rc11=round(r / c, 4),
                      rc11_tokens_per_pass=round(sum(len(cases[i]['target']) for i in j) / sum(spec[i]['passes'] + spec[i]['ar_steps'] for i in j), 3),
                      candidate_tokens_per_pass=round(sum(len(cases[i]['target']) for i in j) / sum(cand[i]['passes'] + cand[i]['ar_steps'] for i in j), 3))
    return out


res = dict(cost_model=report, heldout_odd=summary(1), development_even=summary(0))
res['ratio'] = res['heldout_odd']['all']['candidate_over_rc11']
res['result'] = 'PASS' if res['ratio'] >= 1.05 else 'FAIL'
json.dump(res, open(sys.argv[1], 'w'), indent=1)
print(json.dumps({k: res[k] for k in ('heldout_odd', 'ratio', 'result')}, indent=1))
