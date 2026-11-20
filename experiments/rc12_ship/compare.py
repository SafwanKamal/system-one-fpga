"""Compare the RC1.1 and RC1.2 tool-query benches from the board queue stdout.
usage: python compare.py RC11_STDOUT RC12_STDOUT OUT.json"""
import json, statistics, sys


def load(p):
    for line in open(p, encoding='utf-8'):
        if line.startswith('BENCH-JSON '):
            return json.loads(line[len('BENCH-JSON '):])
    raise SystemExit('no bench in ' + p)


a, b = load(sys.argv[1]), load(sys.argv[2])
assert [x['query'] for x in a] == [x['query'] for x in b]
same = [x['generated_ids'] == y['generated_ids'] and x['path'] == y['path'] for x, y in zip(a, b)]
tot = lambda r, k: sum(x[k] for x in r)
med = lambda r, k: statistics.median(x[k] for x in r)
out = dict(n=len(a), identical=sum(same), complete_rc11=sum(bool(x['complete']) for x in a), complete_rc12=sum(bool(x['complete']) for x in b),
           speculate=[a[0]['speculate'], b[0]['speculate']])
for k in ('prefill_seconds', 'decode_seconds', 'elapsed_seconds'):
    out[k] = dict(rc11_total=round(tot(a, k), 3), rc12_total=round(tot(b, k), 3), total_speedup=round(tot(a, k) / tot(b, k), 3),
                  rc11_median=round(med(a, k), 3), rc12_median=round(med(b, k), 3), median_speedup=round(med(a, k) / med(b, k), 3))
open(sys.argv[3], 'w').write(json.dumps(out, indent=1) + '\n')
print(json.dumps(out, indent=1))
