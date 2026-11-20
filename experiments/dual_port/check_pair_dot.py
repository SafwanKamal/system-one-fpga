"""Check the slot-pair packed dot product (matrix_dual.hpp pair_dot) against direct sums.
Emulates the ap_int widths: 27-bit packed operand, 48-bit accumulator, 19-bit signed low field."""
import random

def wrap(v, bits):
    v &= (1 << bits) - 1
    return v - (1 << bits) if v >> (bits - 1) else v

def pair_dot(w, xa, xb):
    ta = tb = 0
    for half in range(2):
        acc = 0
        for lane in range(16):
            l = half * 16 + lane
            pk = wrap((wrap(xa[l], 27) << 19), 27) + xb[l]
            assert pk == wrap(pk, 27), 'packed operand overflows 27 bits'
            acc = wrap(acc + pk * w[l], 48)
        lo = wrap(acc, 19)
        hi = (acc - lo) >> 19
        ta += hi; tb += lo
    return ta, tb

random.seed(1)
cases = 0
X = range(-127, 128); W = range(-128, 128)
extremes = [([127] * 32, [127] * 32, [127] * 32), ([-128] * 32, [127] * 32, [127] * 32), ([-128] * 32, [-127] * 32, [-127] * 32),
            ([127] * 32, [-127] * 32, [127] * 32), ([-128] * 32, [127] * 32, [-127] * 32)]
for w, xa, xb in extremes + [([random.choice(W) for _ in range(32)], [random.choice(X) for _ in range(32)], [random.choice(X) for _ in range(32)]) for _ in range(200000)]:
    ref = (sum(a * b for a, b in zip(w, xa)), sum(a * b for a, b in zip(w, xb)))
    assert pair_dot(w, xa, xb) == ref, (w, xa, xb)
    cases += 1
# per-lane exhaustive sign/magnitude corners for one lane with the other lanes at extremes
for wv in (-128, -1, 0, 1, 127):
    for a in (-127, -1, 0, 1, 127):
        for c in (-127, -1, 0, 1, 127):
            for fill in (-127, 127):
                w = [wv] + [-128] * 31; xa = [a] + [fill] * 31; xb = [c] + [fill] * 31
                assert pair_dot(w, xa, xb) == (sum(p * q for p, q in zip(w, xa)), sum(p * q for p, q in zip(w, xb)))
                cases += 1
print('pair_dot exact on', cases, 'cases')
