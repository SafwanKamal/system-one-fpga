"""Decision rules 1-4 of BOARD_PROTOCOL.md (v9g) on the v9g pilot.json; rule 5 is the restore job.
usage: python analyze_pilot.py v9g-pilot.json v9f-pilot.json bootb-full-qual.json out.json"""
import json, statistics as S, sys

g = json.load(open(sys.argv[1])); f = json.load(open(sys.argv[2]))
bootb = {c['key'] for c in json.load(open(sys.argv[3]))['cases']}
cases = g['cases']; base = {c['key']: c for c in f['cases']}
r1 = dict(n=len(cases), identical=sum(c['identical'] for c in cases))
r1['pass'] = r1['n'] == 181 and r1['identical'] == 181 and g['passed']
inb = [c for c in cases if c['key'] in bootb]
r2 = dict(n=len(inb), equal=sum(c['draft_stats_equal_v9e'] for c in inb)); r2['pass'] = r2['n'] == 170 and r2['equal'] == 170
r3 = dict(median_ar_ratio_vs_v9f=S.median(c['ar']['decode_seconds'] / base[c['key']]['ar']['decode_seconds'] for c in cases))
r3['pass'] = 0.97 <= r3['median_ar_ratio_vs_v9f'] <= 1.03
sf = lambda k, cs: sum(k(base[c['key']]) for c in cs) / sum(k(c) for c in cs)
pf = lambda c: c['prefill_seconds']; bd = lambda c: c['batched']['decode_seconds']; e2e = lambda c: pf(c) + bd(c)
r4 = dict(prefill_speedup=sf(pf, cases), end_to_end_speedup=sf(e2e, cases), batched_decode_speedup=sf(bd, cases),
          thresholds=dict(prefill=1.15, end_to_end=1.12, batched_decode=1.00),
          predicted=dict(prefill=1.231, end_to_end=1.224, batched_decode=1.197))
r4['pass'] = r4['prefill_speedup'] >= 1.15 and r4['end_to_end_speedup'] >= 1.12 and r4['batched_decode_speedup'] >= 1.00
dom = {}
for c in cases:
    dom.setdefault(c['domain'], []).append(c)
dom['all'] = cases
by_domain = {d: dict(n=len(cs), prefill=round(sf(pf, cs), 3), batched_decode=round(sf(bd, cs), 3), end_to_end=round(sf(e2e, cs), 3),
                     decode_vs_v9e_ar=round(sum(c['v9e_ar_seconds'] for c in cs) / sum(bd(c) for c in cs), 3)) for d, cs in dom.items()}
out = dict(rule1_exact=r1, rule2_same_speculation=r2, rule3_no_single_step_regression=r3, rule4_gain=r4, by_domain=by_domain,
           seconds=dict(v9f_prefill=sum(pf(base[c['key']]) for c in cases), v9g_prefill=sum(pf(c) for c in cases),
                        v9f_batched=sum(bd(base[c['key']]) for c in cases), v9g_batched=sum(bd(c) for c in cases)),
           boot_id=g.get('boot_id'), firmware=g.get('firmware'), runtime=g.get('runtime'), baseline_boot=f.get('boot_id'))
out['rules_1_4_pass'] = all(r['pass'] for r in (r1, r2, r3, r4))
json.dump(out, open(sys.argv[4], 'w'), indent=1)
print(json.dumps(out, indent=1))
