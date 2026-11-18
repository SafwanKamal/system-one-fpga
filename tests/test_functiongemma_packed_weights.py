import numpy as np
import pytest
from sysone.v2.functiongemma_packed_weights import PackedWeights,pack_codes,unpack_codes


@pytest.mark.parametrize('bits',[6,7,8])
def test_single_copy_serves_embedding_gather_and_projection_with_partial_tiles(bits):
    rng=np.random.default_rng(2941)
    codes=rng.integers(-(1<<(bits-1)),1<<(bits-1),size=(37,19),dtype=np.int16)
    packed=PackedWeights.from_codes(codes,bits)
    for row in [0,31,32,36]:np.testing.assert_array_equal(packed.gather(row),codes[row])
    x=rng.integers(-128,128,size=(3,19),dtype=np.int8)
    np.testing.assert_array_equal(packed.matmul(x),x.astype(np.int64)@codes.T.astype(np.int64))
    assert len(packed.data)==2*2*32*16*bits//8
    with pytest.raises(ValueError):packed.gather(37)


def test_seven_bit_layout_has_known_bit_pattern_and_strict_range():
    assert pack_codes(np.array([-64,-1,0,63],dtype=np.int16),7)==bytes([192,63,224,7])
    np.testing.assert_array_equal(unpack_codes(bytes([192,63,224,7]),7,4),[-64,-1,0,63])
    with pytest.raises(ValueError):pack_codes(np.array([64],dtype=np.int16),7)
    with pytest.raises(TypeError):pack_codes(np.array([1.5]),7)
    with pytest.raises(ValueError):unpack_codes(bytes([0,128]),7,2)
