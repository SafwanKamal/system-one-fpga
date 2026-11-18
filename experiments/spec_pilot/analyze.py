"""Apply PROTOCOL.md decision rules to the board pilot result.

usage: python analyze.py <pilot.json> <out.json>
Speedup = sum(ar decode seconds) / sum(spec decode seconds) per domain (time-weighted).
Model prediction uses constants fixed before the run (T_AR=170, T_PASS8=181, T_HEAD=44 ms),
replaying the drafter over the board's own AR outputs.
"""
import json, sys, statistics
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import types
sys.modules.setdefault('fcntl', types.ModuleType('fcntl'))
import pilot

T_AR, T_PASS8, T_HEAD = 170.0, 181.0, 44.0


def modeled(cases):
    d = pilot.Drafter(); per = {}
    for c in cases:
        ids, out = c['prompt_ids'], c['ar']['tokens']
        i, ms = 1, 0.0                                   # token 0 comes from prefill
        while i < len(out):
            if out[i - 1] in (151645, 151643):
                break
            dr = d.draft(ids + out[:i])[:min(pilot.K, len(out) - i - 1)]
            if not dr:
                ms += T_AR; i += 1; continue
            a = 0
            while a < len(dr) and dr[a] == out[i + a]:
                a += 1
            e = min(a + 1, len(out) - i)
            ms += T_PASS8 + T_HEAD * e; i += e
        d.add(out)
        per[c['index']] = (len(out) - 1) * T_AR / ms if ms else None
    return per


def main():
    res = json.loads(Path(sys.argv[1]).read_text())
    cases = res['cases']
    workload = json.loads(Path(sys.argv[3]).read_text()) if len(sys.argv) > 3 else None
    if workload:  # attach prompt ids (pilot.json already holds them only via workload)
        ids = {x['index']: x['prompt_ids'] for x in workload['prompts']}
    out = dict(passed_flag=res.get('passed'), error=res.get('error'), n=len(cases))
    bad = [c for c in cases if not c['identical']]
    out['correctness'] = dict(identical=len(cases) - len(bad), differing=len(bad),
                              first_failure=None if not bad else dict(index=bad[0]['index'], tokens_equal=bad[0]['tokens_equal'],
                                                                     logits_equal=bad[0]['logits_equal'], kv_equal=bad[0]['kv_equal']))
    doms = {}
    for c in cases:
        g = doms.setdefault(c['domain'], dict(ar=0.0, spec=0.0, tokens=0, passes=0, ar_steps=0, accepted=0, drafted=0, cases=0, per=[]))
        g['ar'] += c['ar']['decode_seconds']; g['spec'] += c['spec']['decode_seconds']; g['tokens'] += c['generated']
        for k in ('passes', 'ar_steps', 'accepted', 'drafted'):
            g[k] += c['spec'][k]
        g['cases'] += 1; g['per'].append(c['decode_speedup'])
    tot = dict(ar=sum(g['ar'] for g in doms.values()), spec=sum(g['spec'] for g in doms.values()))
    out['speed'] = {k: dict(cases=g['cases'], tokens=g['tokens'], ar_s=round(g['ar'], 2), spec_s=round(g['spec'], 2),
                            speedup=round(g['ar'] / g['spec'], 3), median_case_speedup=round(statistics.median(g['per']), 3),
                            ar_ms_per_token=round(1000 * g['ar'] / max(1, g['tokens'] - g['cases']), 1),
                            tokens_per_weight_pass=round((g['tokens'] - g['cases']) / max(1, g['passes'] + g['ar_steps']), 2),
                            acceptance=round(g['accepted'] / max(1, g['drafted']), 3)) for k, g in doms.items()}
    out['speed']['ALL'] = dict(speedup=round(tot['ar'] / tot['spec'], 3), ar_s=round(tot['ar'], 2), spec_s=round(tot['spec'], 2))
    if workload:
        for c in cases:
            if c['domain'] != 'tool':
                c['prompt_ids'] = ids[c['index']]
        model_cases = [c for c in cases if c['domain'] != 'tool']
        per = modeled(model_cases)
        for dom in ('general', 'maintenance'):
            xs = [c for c in model_cases if c['domain'] == dom]
            out['speed'][dom]['modeled_median_case_speedup'] = round(statistics.median(per[c['index']] for c in xs), 3)
    m = out['speed'].get('maintenance', {}).get('speedup')
    out['kill_rule'] = None if bad else ('host-only route continues' if m and m >= 1.10 else 'host-only route killed (maintenance < 1.10x)')
    Path(sys.argv[2]).write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
