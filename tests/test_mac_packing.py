"""The arithmetic behind mac_array PACK = 1: two products per DSP48E1 (rtl/v2/encoder/mac_array.sv)."""

import numpy as np


def packed(a_high, a_low, b):
    p = ((a_high << 16) + a_low) * b                 # pre-adder then 25 x 18 multiply
    p = ((p + (1 << 42)) % (1 << 43)) - (1 << 42)    # the 43-bit P register
    low = ((p + (1 << 15)) % (1 << 16)) - (1 << 15)  # P[15:0], signed
    high = (p >> 16) + ((p >> 15) & 1)               # P[42:16] + P[15]
    return high, low


def test_every_operand_in_range():
    a = np.arange(-128, 256, dtype=np.int64)         # INT8 weights / queries, probabilities 0..255
    b = np.arange(-128, 128, dtype=np.int64)
    for a_high in a:
        hi, lo = packed(a_high, a[:, None], b[None, :])
        assert np.array_equal(lo, a[:, None] * b[None, :])
        assert np.array_equal(hi, np.broadcast_to(a_high * b[None, :], hi.shape))
