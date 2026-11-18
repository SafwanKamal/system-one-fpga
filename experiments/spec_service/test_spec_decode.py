"""Offline tests: speculative decode equals plain decode on a deterministic fake engine,
and the service stop rule reproduces the RC1 Session.generate decode loop."""
import json, random, struct, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import spec_decode  # noqa: E402


class Fake:
    """Next token is a deterministic function of all K/V rows up to the lane's position."""
    prefill_batch_size, context = 8, 2048

    def __init__(self, vocab=12, seed=0):
        self.kv, self.lanes, self.v, self.seed = {}, [None] * 8, vocab, seed
        self.scratch = bytearray(8)

    def nxt(self, pos):
        seq = tuple(self.kv[p] for p in range(pos + 1))
        h = hash((self.seed,) + seq) % 1000
        return (seq[-1] + 1) % self.v if h < 650 else h % self.v

    def prefill_batch(self, ids, position, logits=False):
        assert 1 <= len(ids) <= 8 and position + len(ids) <= self.context
        for i, t in enumerate(ids):
            self.kv[position + i] = t
            self.lanes[i] = position + i
        if logits:
            self.command(9, layer=len(ids) - 1)
            return self.select_token()

    def step(self, token, position, logits=False):
        self.kv[position] = token
        self.lanes[0] = position
        return self.select_token() if logits else None

    def command(self, c, layer=0):
        if c == 9:
            self.lanes[0] = self.lanes[layer]

    def select_token(self):
        t = self.nxt(self.lanes[0])
        struct.pack_into('<II', self.scratch, 0, t, (t * 2654435761) & 0xffffffff)
        return t


def logit_of(e):
    return lambda: struct.unpack_from('<I', e.scratch, 4)[0]


def prefill(e, ids):
    for pos in range(0, len(ids), 8):
        g = ids[pos:pos + 8]
        first = e.prefill_batch(g, pos, logits=pos + len(g) == len(ids))
    return first


def test_equivalence(cases=400):
    rnd = random.Random(7)
    drafter, gate = spec_decode.Drafter(), spec_decode.Gate(threshold=0.25)
    stats = dict(passes=0, gated_off=0, ar_steps=0)
    for k in range(cases):
        ids = [rnd.randrange(12) for _ in range(rnd.randrange(3, 60))]
        mx = rnd.randrange(1, 70)
        eos = rnd.choice([{11}, set()])
        stop = lambda t: t[-1] in eos
        e = Fake(seed=k); f = prefill(e, ids); fb = logit_of(e)()
        a, ab, _ = spec_decode.decode(e, ids, f, mx, stop, logit=logit_of(e), first_bits=fb)
        ka = [e.kv[p] for p in range(len(ids) + len(a) - 1)]
        # shared-prefill: second mode decodes on the same engine without re-prefill
        s, sb, st = spec_decode.decode(e, ids, f, mx, stop, drafter=drafter, gate=gate, logit=logit_of(e), first_bits=fb)
        ks = [e.kv[p] for p in range(len(ids) + len(s) - 1)]
        assert a == s and ab == sb and ka == ks, (k, a, s)
        # independent engine, always-speculate
        e2 = Fake(seed=k); f2 = prefill(e2, ids)
        s2, _, _ = spec_decode.decode(e2, ids, f2, mx, stop, drafter=spec_decode.Drafter())
        assert s2 == a
        drafter.add(a)
        for x in stats:
            stats[x] += st[x]
    return stats


def rc1_loop(e, ids, token, n, piece, typed_value, eos_ids):
    """Decode section of RC1 Session.generate (qwen_arm_service_v16/candidate), verbatim logic."""
    raw, value, out = b'', None, []
    for index in range(n):
        out.append(token)
        raw += piece(token)
        value = typed_value(raw)
        if value is not None:
            return out, value, 'typed'
        if token in eos_ids:
            return out, None, 'eos'
        if index + 1 < n:
            token = e.step(token, len(ids) + index, logits=True)
    return out, None, 'truncated'


def test_service_stop_rule(cases=300):
    sys.path.insert(0, str(HERE.parents[1] / 'src'))
    from sysone.v2.qwen_arm_service_v16 import typed_value
    pieces = {0: b'["read', 1: b'_linux', 2: b'_file",', 3: b'"/proc', 4: b'/uptime', 5: b'"]', 6: b'\n',
              7: b'x', 8: b'```', 9: b'json\n', 10: b' ', 11: b'<eos>'}
    piece = lambda t: pieces[t]
    tv = lambda raw: (lambda: typed_value(raw))() if True else None
    rnd = random.Random(3); seen = dict(typed=0, eos=0, truncated=0)
    for k in range(cases):
        ids = [rnd.randrange(12) for _ in range(rnd.randrange(3, 40))]
        n = rnd.randrange(1, 40)
        e = Fake(seed=1000 + k); f = prefill(e, ids)

        def safe_tv(raw):
            try:
                return typed_value(raw)
            except ValueError:
                return None
        ref, rv, why = rc1_loop(e, ids, f, n, piece, safe_tv, {11})
        e2 = Fake(seed=1000 + k); f2 = prefill(e2, ids)
        st = dict(raw=b'', value=None, eos=False)

        def stop(tokens):
            st['raw'] += piece(tokens[-1]); st['value'] = safe_tv(st['raw'])
            if st['value'] is not None:
                return True
            if tokens[-1] == 11:
                st['eos'] = True
                return True
            return False
        out, _, _ = spec_decode.decode(e2, ids, f2, n, stop, drafter=spec_decode.Drafter(), gate=spec_decode.Gate())
        mine = 'typed' if st['value'] is not None else ('eos' if st['eos'] else 'truncated')
        assert out == ref and mine == why and st['value'] == rv, (k, out, ref, mine, why)
        seen[why] += 1
    return seen


if __name__ == '__main__':
    print('equivalence', test_equivalence())
    print('service stop rule', test_service_stop_rule())
    print('ALL TESTS PASSED')
