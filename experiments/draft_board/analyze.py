"""Apply BOARD_PROTOCOL.md's decision rule to the fetched pilot record.
usage: python analyze.py PILOT.json OUT.json
"""
import json, sys

res = json.loads(open(sys.argv[1]).read())
cases = res['cases']
n = len(cases)


def ratio(cs):
    r = sum(c['rc11']['decode_seconds'] for c in cs); q = sum(c['candidate']['decode_seconds'] for c in cs)
    mr = sum(c['model_rc11_seconds'] for c in cs); mq = sum(c['model_candidate_seconds'] for c in cs)
    return dict(n=len(cs), rc11_seconds=round(r, 2), candidate_seconds=round(q, 2), R=round(r / q, 4),
                model_R=round(mr / mq, 4), rc11_measured_over_model=round(r / mr, 4), candidate_measured_over_model=round(q / mq, 4),
                rc11_tokens_per_pass=round(sum(len(c['rc11']['tokens']) for c in cs) / sum(c['rc11']['passes'] + c['rc11']['ar_steps'] for c in cs), 3),
                candidate_tokens_per_pass=round(sum(len(c['candidate']['tokens']) for c in cs) / sum(c['candidate']['passes'] + c['candidate']['ar_steps'] for c in cs), 3))


out = dict(cases=n, boot_id=res.get('boot_id'), firmware=res.get('firmware'), pilot_passed=res['passed'],
           exact_rc11=sum(c['rc11_equal_v9e'] for c in cases), exact_candidate=sum(c['candidate_equal_v9e'] for c in cases),
           replay_rc11=sum(c['rc11_stats_equal_replay'] for c in cases), replay_candidate=sum(c['candidate_stats_equal_replay'] for c in cases),
           all=ratio(cases), odd=ratio([c for c in cases if c['index'] % 2 == 1]),
           by_domain={d: ratio([c for c in cases if c['domain'] == d]) for d in sorted({c['domain'] for c in cases})})
exact = n == 181 and out['exact_rc11'] == out['exact_candidate'] == 181
replay = out['replay_rc11'] == out['replay_candidate'] == 181
out['decision'] = 'FAIL' if not exact else ('PASS' if replay and out['all']['R'] >= 1.10 else 'EXACT, NOT FASTER')
open(sys.argv[2], 'w').write(json.dumps(out, indent=1) + '\n')
print(json.dumps(out, indent=1))
