"""Apply experiments/rc1_spec_ship/PROTOCOL.md rules.

usage: python analyze_ship.py --baseline B/svc.json --spec S/svc.json --rollback R/svc.json --boot T/svc.json --out analysis.json
"""
import argparse, json, statistics
from pathlib import Path

KEYS = ('generated_ids', 'text', 'call', 'tool', 'reused')


def load(p):
    return json.loads(Path(p).read_text())


def compare(ref, run):
    a = {(r['phase'], r['i']): r for r in ref['rows']}
    b = {(r['phase'], r['i']): r for r in run['rows']}
    diff = [dict(row=k, fields=[f for f in KEYS if a[k].get(f) != b.get(k, {}).get(f)]) for k in a
            if k not in b or any(a[k].get(f) != b[k].get(f) for f in KEYS)]
    return dict(rows=len(a), matching_rows=len(a) - len(diff), differing=diff[:10], same_keys=set(a) == set(b))


def latency(ref, run):
    a = {(r['phase'], r['i']): r['client_seconds'] for r in ref['rows'] if r['phase'] != 'cli'}
    b = {(r['phase'], r['i']): r['client_seconds'] for r in run['rows'] if r['phase'] != 'cli'}
    out = {}
    for ph in ('warm1', 'cold', 'warm2', 'all'):
        ks = [k for k in a if (ph == 'all' or k[0] == ph) and k in b]
        out[ph] = dict(base_median_s=round(statistics.median(a[k] for k in ks), 3), run_median_s=round(statistics.median(b[k] for k in ks), 3),
                       median_ratio=round(statistics.median(a[k] / b[k] for k in ks), 3))
    return out


def main():
    ap = argparse.ArgumentParser()
    for n in ('baseline', 'spec', 'rollback', 'boot'):
        ap.add_argument('--' + n, type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    R = {n: load(getattr(a, n)) for n in ('baseline', 'spec', 'rollback', 'boot')}
    out = {}
    out['rule1_all_requests_complete'] = {n: dict(passed=r['passed'], rows=len(r['rows']), error=r.get('error')) for n, r in R.items()}
    out['rule1_pass'] = all(r['passed'] and len(r['rows']) == 66 for r in R.values())
    out['rule2_equal_to_baseline'] = {n: compare(R['baseline'], R[n]) for n in ('spec', 'rollback', 'boot')}
    out['rule2_pass'] = all(c['same_keys'] and c['matching_rows'] == c['rows'] for c in out['rule2_equal_to_baseline'].values())
    modes = {n: sorted({str(r.get('speculate')) for r in R[n]['rows']}) for n in R}
    out['rule3_modes'] = modes
    out['rule3_pass'] = modes['baseline'] == modes['rollback'] == ['None'] and modes['spec'] == modes['boot'] == ['adaptive']
    b = R['boot']
    boot_ok = (b['boot_id'] != R['spec']['boot_id'] and 'rc1-spec-v1/spec_service.py' in b['service_before']
               and 'NRestarts=0' in b['service_before'] and 'NRestarts=0' in b['service_after']
               and b['health'].get('state') == 'READY' and b['health'].get('startup_proof', {}).get('verified_bytes') == 639446688)
    out['rule4_boot'] = dict(pass_=boot_ok, boot_id=b['boot_id'], spec_boot_id=R['spec']['boot_id'], health_state=b['health'].get('state'))
    out['rule5_latency'] = {n: latency(R['baseline'], R[n]) for n in ('spec', 'rollback', 'boot')}
    out['rule5_pass'] = all(out['rule5_latency'][n]['all']['median_ratio'] >= 1.10 for n in ('spec', 'boot'))
    out['passed'] = all(out[k] for k in ('rule1_pass', 'rule2_pass', 'rule3_pass', 'rule5_pass')) and boot_ok
    Path(a.out).write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))
    print('SHIP RESULT: ' + ('PASS' if out['passed'] else 'FAIL'))


if __name__ == '__main__':
    main()
