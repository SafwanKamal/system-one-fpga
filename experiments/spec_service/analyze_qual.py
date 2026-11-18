"""Apply experiments/spec_service/PROTOCOL.md rules.

usage: python analyze_qual.py --boota A/qual.json [A2/qual.json ...] --e2e e2e.json [--bootb B/qual.json] --out analysis.json

Several --boota files are merged by case key (Amendment 2). Cross-boot (rule 2) is judged
on the cases carrying cross_boot_equal: 55 under Amendment 1, or 46 with --bootb.
"""
import argparse, json, statistics
from pathlib import Path

HEAD = ('3', '4', '9')
LAYER = ('1', '2', '7', '8')


def share(cases, mode):
    t = {}
    for c in cases:
        for k, v in c[mode]['decode_work']['timing'].items():
            t[k] = t.get(k, 0.0) + v['seconds']
    tot = sum(t.values()) or 1.0
    return dict(head=round(sum(t.get(k, 0) for k in HEAD) / tot, 3), layers=round(sum(t.get(k, 0) for k in LAYER) / tot, 3),
                fpga_seconds=round(tot, 1), wall_seconds=round(sum(c[mode]['decode_seconds'] for c in cases), 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--boota', type=Path, nargs='+', required=True)
    ap.add_argument('--e2e', type=Path, required=True)
    ap.add_argument('--bootb', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    parts = [json.loads(f.read_text()) for f in a.boota]
    A = parts[0]
    merged = {}
    for P in parts:
        for c in P['cases']:
            assert c['key'] not in merged, 'duplicate case ' + c['key']
            merged[c['key']] = c
    cases = sorted(merged.values(), key=lambda c: c['index'])
    out = dict(boota=dict(boot=A.get('boot_id'), n=len(cases), parts=[dict(file=str(f), boot=P.get('boot_id'), n=len(P['cases']), passed_flag=P.get('passed'),
               error=P.get('error'), resumed_from=P.get('resumed_from')) for f, P in zip(a.boota, parts)]))
    xc = [c for c in cases if 'cross_boot_equal' in c]
    if xc:
        xf = [c['index'] for c in xc if not (c['identical'] and c['cross_boot_equal'])]
        out['rule2_cross_boot'] = dict(pass_=not xf and len(xc) == 55, basis='Amendment 1: cases from the first boot', n=len(xc), failing=xf[:10])
    bad = [c['index'] for c in cases if not c['identical']]
    out['rule1_exactness'] = dict(pass_=not bad and len(cases) == 181, identical=len(cases) - len(bad), differing=bad[:10])
    if a.bootb:
        B = json.loads(a.bootb.read_text()); bc = B['cases']
        xb = [c['index'] for c in bc if not (c['identical'] and c.get('cross_boot_equal'))]
        out['rule2_cross_boot'] = dict(pass_=not xb and len(bc) == 46 and B.get('boot_id') != A.get('boot_id'),
                                       boot=B.get('boot_id'), n=len(bc), failing=xb[:10], error=B.get('error'))
    E = json.loads(a.e2e.read_text())
    out['rule3_service'] = dict(pass_=bool(E.get('passed')), compare=E.get('compare_vs_rc1'), error=E.get('error'))
    if E.get('phases', {}).get('rc1') and E['phases'].get('adaptive'):
        rc1 = [r['client_seconds'] for r in E['phases']['rc1']]; ad = [r['client_seconds'] for r in E['phases']['adaptive']]
        off = [r['client_seconds'] for r in E['phases'].get('off', [])]
        out['rule6_service_latency'] = dict(rc1_median_s=round(statistics.median(rc1), 3), off_median_s=round(statistics.median(off), 3) if off else None,
                                            adaptive_median_s=round(statistics.median(ad), 3),
                                            median_ratio_rc1_over_adaptive=round(statistics.median(x / y for x, y in zip(rc1, ad)), 3))
    speed = {}
    for dom in ('general', 'maintenance', 'tool', 'long'):
        cs = [c for c in cases if c['domain'] == dom]
        if not cs:
            continue
        ar = sum(c['ar']['decode_seconds'] for c in cs); sp = sum(c['adaptive']['decode_seconds'] for c in cs)
        tok = sum(c['generated'] - 1 for c in cs)
        st = {k: sum(c['adaptive'][k] for c in cs) for k in ('passes', 'ar_steps', 'accepted', 'drafted', 'gated_off')}
        speed[dom] = dict(cases=len(cs), tokens=tok, ar_s=round(ar, 1), adaptive_s=round(sp, 1), speedup=round(ar / sp, 3),
                          median_case=round(statistics.median(c['decode_speedup'] for c in cs), 3),
                          min_case=round(min(c['decode_speedup'] for c in cs), 3),
                          ar_ms_per_token=round(1000 * ar / max(1, tok), 1),
                          tokens_per_weight_pass=round(tok / max(1, st['passes'] + st['ar_steps']), 2),
                          acceptance=round(st['accepted'] / max(1, st['drafted']), 3), gated_off=st['gated_off'],
                          head_share=share(cs, 'adaptive'), ar_head_share=share(cs, 'ar'))
    nonlong = [c for c in cases if c['domain'] != 'long']
    slow = [c['index'] for c in nonlong if c['decode_speedup'] < 0.95]
    ar_all = sum(c['ar']['decode_seconds'] for c in cases); sp_all = sum(c['adaptive']['decode_seconds'] for c in cases)
    speed['ALL'] = dict(speedup=round(ar_all / sp_all, 3), ar_s=round(ar_all, 1), adaptive_s=round(sp_all, 1))
    out['speed'] = speed
    rule4 = all(speed[d]['speedup'] >= 1.0 for d in ('general', 'maintenance', 'tool')) and speed['maintenance']['speedup'] >= 1.10 \
        and len(slow) <= 0.05 * len(nonlong)
    out['rule4_speed'] = dict(pass_=rule4, slow_cases_below_0_95=len(slow), allowed=round(0.05 * len(nonlong), 1), slow=slow[:20])
    hs = speed['maintenance']['head_share']['head']
    out['rule5_next_step'] = dict(maintenance_head_share=hs, batched_head_next=hs >= 0.30)
    Path(a.out).write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
