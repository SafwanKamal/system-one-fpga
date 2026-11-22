"""Model what the attention-reclaim trade buys end to end: P=2 attention (frees LUT) plus the full
dual weight port (needs the LUT), against v9h (P=4, port split only for passes of <= 4 tokens).

Cost model: the 7-coefficient v9h board fit (build/v2/rc1-3/fit.json, median error 0.2%), split
into its two hardware meanings:
  pass(k, p) = (c_small if k <= SPLIT else c_large) + c_tok*k + c_pos*p + c_grp*p*ceil(k/P)
  step(p)    = c_step + c_steppos*p
SPLIT=4 on v9h; the full dual port splits every pass, so c_large -> c_small (the measured cost of a
pass on both ports). P is the attention token lanes (4 on v9h, 2 for the 'p2' variant); c_grp is the
compute-bound attention term (37 cycles x 8 heads per row per pass, core-feasibility study).

Decode: the RC1.3 drafter is replayed on all 181 cases (exact fake engine, persistent history) with
each hardware's own costs, so drafts re-tune to the hardware. Prefill: each case's prompt after the
cached 32-token template prefix, in groups of 8, priced with the same pass model.
usage: python experiments/attn_reclaim/model_p2.py  -> build/v2/attn-reclaim/claude/model_p2.json
"""
import json, math, os, sys
from pathlib import Path

ROOT = Path(os.environ.get('SYS_ROOT', 'S:/'))
sys.path.insert(0, str(ROOT / 'experiments/draft_research'))
import replay, spec_decode  # noqa: E402
from drafters import VoteDrafter, CostAwareDrafter  # noqa: E402

fit = json.loads((ROOT / 'build/v2/rc1-3/fit.json').read_text())
c_step, c_steppos, c_small, c_large, c_tok, c_pos, c_grp = fit['coef_v9h']
PREFIX = 32
HW = {  # name: (split threshold, attention P)
    'v9h': (4, 4),
    'v9h+p2': (4, 2),
    'dual+p4 (does not fit)': (8, 4),
    'dual+p2': (8, 2),
}


def pass_cost(k, p, split, P):
    return (c_small if k <= split else c_large) + c_tok * k + c_pos * p + c_grp * p * math.ceil(k / P)


def step_cost(p):
    return c_step + c_steppos * p


class HwDrafter(CostAwareDrafter):
    def __init__(self, base, split, P, **kw):
        super().__init__(base, [0.0] * 7, P=P, **kw)
        self.split = split

    def cost(self, k, p):
        return step_cost(p) if k == 1 else pass_cost(k, p, self.split, self.P)


def dec(e, ids, first, max_new, stop, drafter=None, **kw):
    drafter.begin(ids)
    return spec_decode.decode(e, ids, first, max_new, stop, drafter=drafter, **kw)


def price(log, split, P):
    return sum(step_cost(p) if kind == 's' else pass_cost(k, p, split, P) for kind, k, p in log)


def prefill(ids, split, P):
    t, p = 0.0, PREFIX
    while p < len(ids):
        k = min(8, len(ids) - p)
        t += step_cost(p) if k == 1 else pass_cost(k, p, split, P)
        p += k
    return t


cases, _ = replay.load_cases()
plain = replay.run(cases, drafter_factory=None)
out = {}
for name, (split, P) in HW.items():
    spec = replay.run(cases, drafter_factory=lambda: HwDrafter(VoteDrafter(prompts=True, ns=(6, 4, 3, 2, 1)), split, P,
                                                               prior=0.5, prior_w=2.0),
                      decode=dec, feed=lambda d, c, o: d.feed(c, o))
    row = dict(split=split, P=P,
               plain_decode_s=sum(price(r['log'], split, P) for r in plain),
               spec_decode_s=sum(price(r['log'], split, P) for r in spec),
               prefill_s=sum(prefill(c['ids'], split, P) for c in cases))
    dom = {}
    for c, r in zip(cases, spec):
        d = dom.setdefault(c['domain'], [0.0, 0.0])
        d[0] += price(r['log'], split, P); d[1] += prefill(c['ids'], split, P)
    row['by_domain_spec_plus_prefill_s'] = {k: v[0] + v[1] for k, v in dom.items()}
    row['end_to_end_s'] = row['spec_decode_s'] + row['prefill_s']
    out[name] = row
base = out['v9h']
for row in out.values():
    row['vs_v9h'] = {k: base[k] / row[k] for k in ('plain_decode_s', 'spec_decode_s', 'prefill_s', 'end_to_end_s')}
    row['vs_v9h_by_domain'] = {d: base['by_domain_spec_plus_prefill_s'][d] / v
                               for d, v in row['by_domain_spec_plus_prefill_s'].items()}
dst = ROOT / 'build/v2/attn-reclaim/claude/model_p2.json'
dst.write_text(json.dumps(out, indent=1))
for name, row in out.items():
    print('%-24s plain %7.1fs  spec %7.1fs  prefill %7.1fs  e2e %7.1fs  | e2e vs v9h %.3fx  spec %.3fx  prefill %.3fx'
          % (name, row['plain_decode_s'], row['spec_decode_s'], row['prefill_s'], row['end_to_end_s'],
             row['vs_v9h']['end_to_end_s'], row['vs_v9h']['spec_decode_s'], row['vs_v9h']['prefill_s']))
