"""Development-split exploration of drafters and draft policies (replay + v9g cost model).

Policies run over the whole workload in order (persistent drafter state, as on the board);
metrics are reported on the development split (even case index). The odd split is held out
for the pre-registered evaluation (PROTOCOL.md) and is not printed here.
usage: python explore.py [variant ...]
"""
import json, sys
import replay, cost, spec_decode

cases, THR = replay.load_cases()
_spec = replay.run(cases, gate_factory=lambda: spec_decode.Gate(threshold=THR))
_ar = replay.run(cases, drafter_factory=None)
COEF, REPORT = cost.fit([(s['log'], c['record']['batched']['decode_seconds']) for c, s in zip(cases, _spec)] +
                        [(a['log'], c['record']['ar']['decode_seconds']) for c, a in zip(cases, _ar)])
AR_T = [cost.predict(COEF, a['log']) for a in _ar]


def metrics(res, split=0):
    idx = [i for i, c in enumerate(cases) if c['index'] % 2 == split]
    t = sum(cost.predict(COEF, res[i]['log']) for i in idx)
    ar = sum(AR_T[i] for i in idx)
    tok = sum(len(cases[i]['target']) for i in idx)
    work = sum(res[i]['passes'] + res[i]['ar_steps'] for i in idx)
    by = {}
    for d in ('general', 'maintenance', 'long', 'tool'):
        j = [i for i in idx if cases[i]['domain'] == d]
        by[d] = round(sum(AR_T[i] for i in j) / sum(cost.predict(COEF, res[i]['log']) for i in j), 3)
    return dict(speedup=round(ar / t, 4), tokens_per_weight_pass=round(tok / work, 3),
                accepted=sum(res[i]['accepted'] for i in idx), drafted=sum(res[i]['drafted'] for i in idx),
                passes=sum(res[i]['passes'] for i in idx), by_domain=by)


VARIANTS = {}


def variant(f):
    VARIANTS[f.__name__] = f
    return f


@variant
def rc11():
    return replay.run(cases, gate_factory=lambda: spec_decode.Gate(threshold=THR))


@variant
def no_gate():
    return replay.run(cases)


class Oracle:
    """Upper bound: drafts the true continuation (not causal; reference only)."""
    target = None

    def add(self, seq):
        pass

    def draft(self, ctx):
        n = len(Oracle.ids)
        c = Oracle.target[len(ctx) - n:len(ctx) - n + spec_decode.K]
        return list(c), 6


@variant
def oracle():
    def dec(e, ids, first, max_new, stop, **kw):
        Oracle.ids, Oracle.target = ids, e.target
        return spec_decode.decode(e, ids, first, max_new, stop, **kw)
    return replay.run(cases, drafter_factory=Oracle, decode=dec)


if __name__ == '__main__':
    names = sys.argv[1:] or list(VARIANTS)
    print('cost model', json.dumps({k: round(v, 6) for k, v in REPORT.items() if k != 'coef'}))
    for n in names:
        print(n, json.dumps(metrics(VARIANTS[n]())))
