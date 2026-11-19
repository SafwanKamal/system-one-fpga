"""Item 1 of PROTOCOL.md: compare the v9f and P=4 prefill8 dumps word by word.
usage: python compare_dumps.py v9f-dump.bin p4-dump.bin out.json"""
import json, struct, sys

NAMES = ('hidden', 'kv', 'norm', 'token', 'logit')


def load(path):
    out, data, at = {}, open(path, 'rb').read(), 0
    for name in NAMES:
        (n,) = struct.unpack_from('<Q', data, at); at += 8
        out[name] = data[at:at + 4 * n]; at += 4 * n
    assert at == len(data), 'trailing bytes'
    return out


a, b = load(sys.argv[1]), load(sys.argv[2])
res = {}
for name in NAMES:
    x, y = a[name], b[name]
    words = len(x) // 4
    diff = [i for i in range(words) if x[4 * i:4 * i + 4] != y[4 * i:4 * i + 4]] if len(x) == len(y) else None
    res[name] = dict(words=words, differing=None if diff is None else len(diff), first=diff[0] if diff else None)
res['result'] = 'PASS' if all(r['differing'] == 0 for r in res.values() if isinstance(r, dict)) else 'FAIL'
json.dump(res, open(sys.argv[3], 'w'), indent=1)
print(json.dumps(res, indent=1))
