import numpy as np
import pytest
from sysone.v2.decoder_math import rmsnorm,gated_multiply

def norm(x,g):
    return rmsnorm(x,g,gamma_fraction=12,inverse_fraction=24,
                   epsilon_numerator=1,epsilon_denominator=1024,
                   output_multiplier=64,output_shift=1)

def test_rmsnorm_against_float_oracle_zero_negative_gamma_and_saturation():
    x=np.array([[3,4],[-3,4],[0,0],[127,1]],dtype=np.int64)
    g=np.array([4096,-8192],dtype=np.int64)
    want=x*(g/4096)/np.sqrt((x.astype(float)**2).mean(axis=1,keepdims=True)+1/1024)*32
    want=np.clip(np.floor(want+.5),-127,127).astype(np.int8)
    np.testing.assert_array_equal(norm(x,g),want)
    assert np.all(norm(x,g)[2]==0)
    np.testing.assert_array_equal(norm(x,np.full(2,32767))[3],np.array([127,3],dtype=np.int8))

def test_rmsnorm_wide_extremes_have_no_hidden_integer_overflow():
    x=np.full((1,8192),127,dtype=np.int64)
    out=norm(x,np.full(8192,4096,dtype=np.int64))
    np.testing.assert_array_equal(out,np.full((1,8192),32,dtype=np.int8))
    with pytest.raises(ValueError):norm(x.astype(float),np.full(8192,4096))

def test_gated_multiply_against_scalar_lookup_and_clip():
    gate=np.array([-127,-5,0,3,127],dtype=np.int64)
    up=np.array([127,-127,7,9,127],dtype=np.int64)
    table=np.arange(-128,128,dtype=np.int64)*128
    want=[max(-127,min(127,(int(table[int(g)+128])*int(u)*3+128)>>8)) for g,u in zip(gate,up)]
    np.testing.assert_array_equal(gated_multiply(gate,up,table,multiplier=3,shift=8),want)
    with pytest.raises(ValueError):gated_multiply(gate,up,table[:255],multiplier=3,shift=8)
