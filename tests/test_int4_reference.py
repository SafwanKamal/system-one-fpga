import numpy as np
import pytest
from sysone.v2.int4_reference import pack,unpack,matvec

def test_signed_nibble_order_and_odd_padding():
    assert pack([-8,7,-1])==bytes([0x78,0x0f])
    np.testing.assert_array_equal(unpack(bytes([0x78,0x0f]),3),[-8,7,-1])
    with pytest.raises(ValueError):unpack(bytes([0x78,0xff]),3)
    with pytest.raises(ValueError):unpack(bytes([0x78]),3)

def test_int4_matvec_against_scalar_products():
    rng=np.random.default_rng(23)
    w=rng.integers(-8,8,(5,17),dtype=np.int64)
    x=rng.integers(-127,128,17,dtype=np.int64)
    expected=[sum(int(w[r,c])*int(x[c]) for c in range(17)) for r in range(5)]
    np.testing.assert_array_equal(matvec(x,pack(w),5,17),expected)

@pytest.mark.parametrize('values',[[-9],[8],[1.5]])
def test_invalid_weights(values):
    with pytest.raises(ValueError):pack(values)
