"""Decision rules 1-4 of BOARD_PROTOCOL.md on pilot.json (rule 5 is the restore job).
usage: python analyze_pilot.py pilot.json bootb-full-qual.json out.json"""
import json, statistics as S, sys

p = json.load(open(sys.argv[1])); bootb = {c['key'] for c in json.load(open(sys.argv[2]))['cases']}
cases = p['cases']
r1 = dict(n=len(cases), identical=sum(c['identical'] for c in cases))
r1['pass'] = r1['n'] == 181 and r1['identical'] == 181 and p['passed']
inb = [c for c in cases if c['key'] in bootb]
r2 = dict(n=len(inb), equal=sum(c['draft_stats_equal_v9e'] for c in inb)); r2['pass'] = r2['n'] == 170 and r2['equal'] == 170
ratios = [c['ar']['decode_seconds'] / c['v9e_ar_seconds'] for c in cases]
r3 = dict(median_ar_ratio=S.median(ratios)); r3['pass'] = 0.97 <= r3['median_ar_ratio'] <= 1.03
agg = sum(c['v9e_ar_seconds'] for c in cases) / sum(c['batched']['decode_seconds'] for c in cases)
r4 = dict(aggregate_speedup=agg, threshold=1.75); r4['pass'] = agg >= 1.75
dom = {}
for c in cases:
    d = dom.setdefault(c['domain'], dict(n=0, v9e_ar=0.0, v9e_spec=0.0, v9f_batched=0.0, v9f_ar=0.0, scans_v9e=0, scans_v9f=0))
    d['n'] += 1; d['v9e_ar'] += c['v9e_ar_seconds']; d['v9e_spec'] += c['v9e_adaptive_seconds']
    d['v9f_batched'] += c['batched']['decode_seconds']; d['v9f_ar'] += c['ar']['decode_seconds']
allv = dict(n=0, v9e_ar=0.0, v9e_spec=0.0, v9f_batched=0.0, v9f_ar=0.0)
for d in dom.values():
    for k in allv: allv[k] += d[k] if k in d else 0
dom['all'] = allv
summary = {k: dict(n=d['n'], v9e_spec_speedup=round(d['v9e_ar'] / d['v9e_spec'], 3), v9f_batched_speedup=round(d['v9e_ar'] / d['v9f_batched'], 3),
                   v9f_over_v9e_spec=round(d['v9e_spec'] / d['v9f_batched'], 3)) for k, d in dom.items()}
case_speedups = [c['v9e_ar_seconds'] / c['batched']['decode_seconds'] for c in cases]
head = dict(v9f_head_scans=sum(c['batched']['head_scans'] for c in cases), v9f_passes_plus_ar=sum(c['batched']['passes'] + c['batched']['ar_steps'] for c in cases))
out = dict(rule1_exact=r1, rule2_same_speculation=r2, rule3_no_regression=r3, rule4_gain=r4, by_domain=summary,
           min_case_speedup=round(min(case_speedups), 3), median_case_speedup=round(S.median(case_speedups), 3), head=head,
           boot_id=p.get('boot_id'), firmware=p.get('firmware'), runtime=p.get('runtime'))
out['rules_1_4_pass'] = all(r['pass'] for r in (r1, r2, r3, r4))
json.dump(out, open(sys.argv[3], 'w'), indent=1)
print(json.dumps(out, indent=1))
