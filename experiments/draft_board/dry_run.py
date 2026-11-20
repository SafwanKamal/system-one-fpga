"""Host dry run of draft_pilot.py's decode loop on the replay engine (no board).

Checks, before packaging:
- the pilot's loop, with coef_dev loaded from expected.json, reproduces the replayed draft
  statistics of both modes on all cases;
- in the v9e records, `ar` and `adaptive` agree on tokens, logit bits and K/V hash, so
  comparing both board modes with `ar` is the same test the v9g pilot used.
usage: python dry_run.py
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/draft_research'))
import replay, spec_decode  # noqa: E402
from drafters import VoteDrafter, CostAwareDrafter  # noqa: E402

KEYS = ('passes', 'ar_steps', 'drafted', 'accepted', 'zero_accept', 'gated_off', 'head_scans')
exp = json.loads((ROOT / 'build/v2/draft-board/expected.json').read_text())
cases, thr = replay.load_cases()
assert [c['key'] for c in cases] == [c['key'] for c in exp['cases']]
rc_drafter, rc_gate = spec_decode.Drafter(), spec_decode.Gate(threshold=thr)
cand = CostAwareDrafter(VoteDrafter(prompts=True, ns=(6, 4, 3, 2, 1)), exp['coef_dev'], prior=0.5, prior_w=2.0, P=4)
stop = lambda t: t[-1] in replay.EOS
bad = []
for i, (c, x) in enumerate(zip(cases, exp['cases'])):
    runs = {}
    for mode in (['rc11', 'candidate'] if i % 2 == 0 else ['candidate', 'rc11']):
        e = replay.FakeEngine(c['ids'], c['target'])
        if mode == 'candidate':
            cand.begin(c['ids'])
        out, _, st = spec_decode.decode(e, c['ids'], c['target'][0], c['max_new'], stop,
                                        drafter=rc_drafter if mode == 'rc11' else cand,
                                        gate=rc_gate if mode == 'rc11' else None, batched=e.batched)
        assert out == c['target'], (c['index'], mode)
        runs[mode] = (out, st)
    rc_drafter.add(runs['rc11'][0])
    cand.feed(dict(ids=c['ids']), runs['candidate'][0])
    for mode in ('rc11', 'candidate'):
        bad += [(c['index'], mode, k) for k in KEYS if runs[mode][1][k] != x[mode][k]]
print('stat mismatches vs expected.json:', len(bad), bad[:5])

ref = {}
for p in ('build/v2/spec-qual/board/bootb-full/qual.json', 'build/v2/spec-qual/board/bootc-resume/qual.json'):
    for r in json.loads((ROOT / p).read_text())['cases']:
        ref.setdefault(r['key'], r)
diff = [k for k in (c['key'] for c in cases)
        if any(ref[k]['ar'][f] != ref[k]['adaptive'][f] for f in ('tokens', 'logit_bits', 'kv_sha256'))]
print('v9e records where ar != adaptive:', len(diff), 'of', len(cases))
sys.exit(1 if bad or diff else 0)
