"""Build the long-prompt board bundle and the model's per-case predictions.

Cases: all 20 'long' workload cases plus the non-long cases of the every-fifth pilot sample
(index % 5 == 0, index <= 175), in workload order, with prompt ids and the recorded greedy
tokens. Drafters: RC1.3 on v9h (coef_v9h, P=4) and RC1.4 on v9i (refit, P=2), each replayed
on exactly this case sequence with persistent history; plain and drafted decode priced by the
v9h fit (build/v2/rc1-3/fit.json) and the v9i refit (fit.json) respectively.
Writes build/v2/rc1-4/long/{long.tar, predicted.json, replay-stats.json}.
usage: python experiments/v9i/refit/make_long.py
"""
import hashlib, io, json, math, sys, tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'experiments/draft_research'))
import replay, spec_decode  # noqa: E402
from drafters import VoteDrafter, CostAwareDrafter  # noqa: E402

OUT = ROOT / 'build/v2/rc1-4/long'
coef_v9h = json.loads((ROOT / 'build/v2/rc1-3/fit.json').read_text())['coef_v9h']
coef_v9i = json.loads((HERE / 'fit.json').read_text())['coef_v9i_refit']


def features7(log, P):
    f = [0.0] * 7
    for kind, k, p in log:
        if kind == 's':
            f[0] += 1; f[1] += p
        else:
            f[2 if k <= P else 3] += 1; f[4] += k; f[5] += p; f[6] += p * math.ceil(k / P)
    return f


def dec(e, ids, first, max_new, stop, drafter=None, **kw):
    drafter.begin(ids)
    return spec_decode.decode(e, ids, first, max_new, stop, drafter=drafter, **kw)


cases, _ = replay.load_cases()
sel = [c for c in cases if c['domain'] == 'long' or (c['index'] % 5 == 0 and c['index'] <= 175)]
assert sum(c['domain'] == 'long' for c in sel) == 20 and len(sel) == 52, len(sel)
assert max(len(c['ids']) + c['max_new'] for c in sel) <= 2048
work = dict(cases=[dict(key=c['key'], index=c['index'], domain=c['domain'], prompt_ids=c['ids'], max_new=c['max_new'],
                        target=c['target']) for c in sel])
pred, stats = {}, {}
ar = replay.run(sel, drafter_factory=None)
for img, coef, P in (('v9h', coef_v9h, 4), ('v9i', coef_v9i, 2)):
    runs = replay.run(sel, drafter_factory=lambda: CostAwareDrafter(VoteDrafter(prompts=True, ns=(6, 4, 3, 2, 1)), coef,
                                                                   prior=0.5, prior_w=2.0, P=P),
                      decode=dec, feed=lambda d, c, o: d.feed(c, o))
    price = lambda log: sum(a * b for a, b in zip(features7(log, P), coef))
    pred[img] = {str(c['index']): dict(ar=price(x['log']), drafted=price(r['log'])) for c, x, r in zip(sel, ar, runs)}
    stats[img] = {str(c['index']): {k: r[k] for k in ('passes', 'ar_steps', 'drafted', 'accepted', 'zero_accept', 'head_scans')}
                  for c, r in zip(sel, runs)}
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'predicted.json').write_text(json.dumps(pred, indent=1, sort_keys=True) + '\n')
(OUT / 'replay-stats.json').write_text(json.dumps(stats, indent=1, sort_keys=True) + '\n')
files = {'long/workload.json': json.dumps(work).encode(), 'long/coef_v9h.json': json.dumps(coef_v9h).encode(),
         'long/coef_v9i_refit.json': json.dumps(coef_v9i).encode(),
         'long/long_check.py': (HERE / 'long_check.py').read_bytes(),
         'long/spec_decode.py': (ROOT / 'experiments/spec_service/spec_decode.py').read_bytes(),
         'long/drafters.py': (ROOT / 'experiments/draft_research/drafters.py').read_bytes()}
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode='w', format=tarfile.USTAR_FORMAT) as t:
    for name, data in sorted(files.items()):
        info = tarfile.TarInfo(name); info.size = len(data); info.mtime = 0; info.mode = 0o644
        t.addfile(info, io.BytesIO(data))
(OUT / 'long.tar').write_bytes(buf.getvalue())
tot = {img: (sum(v['ar'] for v in p.values()), sum(v['drafted'] for v in p.values())) for img, p in pred.items()}
print(json.dumps(dict(cases=len(sel), tar_sha256=hashlib.sha256(buf.getvalue()).hexdigest(), modelled_decode=tot), indent=1))
