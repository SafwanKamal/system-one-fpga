import numpy as np
import pytest
from sysone.v2.functiongemma_integer_ops import RMSPlan,SoftmaxPlan,attention_context


def nearest(x):return np.sign(x)*np.floor(np.abs(x)+.5)


def test_rms_integer_rows_agree_with_quantized_float_at_int16_extremes():
    rng=np.random.default_rng(683)
    x=rng.integers(-32768,32768,size=(17,640),dtype=np.int16)
    x[0]=0;x[1]=32767;x[2]=0;x[2,0]=-32768
    weight=rng.normal(0,.02,size=640)
    plan=RMSPlan.compile(weight,.0004,.03)
    real=x.astype(np.float64)*.0004
    expected=np.clip(nearest(real/np.sqrt(np.mean(real*real,axis=-1,keepdims=True)+1e-6)*(1+weight)/.03),-127,127)
    actual=plan.run(x)
    assert np.max(np.abs(actual.astype(np.int16)-expected))<=1
    assert not actual[0].any()
    with pytest.raises(ValueError):RMSPlan.compile(weight,0,.03)
    with pytest.raises(ValueError):RMSPlan.compile(np.full(640,1e10),.1,.01)


def test_long_uniform_attention_has_nonzero_q16_weights_and_correct_context():
    plan=SoftmaxPlan.compile(.01)
    p=plan.run(np.zeros(2048,dtype=np.int32),np.ones(2048,dtype=bool))
    assert p.dtype==np.uint16 and np.all(p==32) and int(p.astype(np.int64).sum())==65536
    v=np.full((2048,256),100,dtype=np.int8)
    np.testing.assert_array_equal(attention_context(p,v),np.full(256,100,dtype=np.int8))


def test_masked_attention_ignores_sentinels_and_has_float_probability_accuracy():
    plan=SoftmaxPlan.compile(1/4096)
    scores=np.array([-(1<<31),0,1024,2048],dtype=np.int32)
    mask=np.array([False,True,True,True])
    p=plan.run(scores,mask)
    real=scores[mask]/4096;expected=np.exp(real-real.max());expected/=expected.sum()
    assert p[0]==0
    assert np.max(np.abs(p[mask]/65536-expected))<.002
    with pytest.raises(ValueError,match='empty'):plan.run(scores,np.zeros(4,dtype=bool))
    with pytest.raises(ValueError):plan.run(np.zeros(2049,dtype=np.int32),np.ones(2049,dtype=bool))


def test_single_key_and_bad_probability_rows_are_bounded():
    p=SoftmaxPlan.compile(.01).run(np.array([123],dtype=np.int32),np.array([True]))
    assert p.tolist()==[65535]
    with pytest.raises(ValueError,match='sum invariant'):
        attention_context(np.full(2048,65535,dtype=np.uint16),np.ones((2048,256),dtype=np.int8))
