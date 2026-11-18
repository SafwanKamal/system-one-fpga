import numpy as np
import pytest
from sysone.v2.decoder_reference import CausalAttention
from sysone.v2.decoder_reference import rope_int8

def reference(capacity=8):
    exp=np.maximum(1,np.rint(65535*np.exp(-np.arange(256)/16))).astype(np.int64)
    return CausalAttention(2,4,capacity,exp,1,4,1,8)

def test_prefill_matches_tokenwise_decode_and_future_is_invisible():
    rng=np.random.default_rng(42)
    q,k,v=[rng.integers(-127,128,(6,8),dtype=np.int64) for _ in range(3)]
    want=reference().prefill(q,k,v)
    cached=reference()
    actual=np.stack([cached.decode(q[i],k[i],v[i]) for i in range(6)])
    np.testing.assert_array_equal(actual,want)
    k[3:]=0;v[3:]=127
    np.testing.assert_array_equal(reference().prefill(q,k,v)[:3],want[:3])
    cached.reset()
    np.testing.assert_array_equal(cached.prefill(q,k,v),reference().prefill(q,k,v))

def test_one_token_and_independent_scalar_attention():
    r=reference()
    q=np.arange(16).reshape(2,8)-5;k=q[::-1].copy();v=q*3
    actual=r.prefill(q,k,v)
    expected=[]
    for row in range(2):
        result=[]
        for head in range(2):
            cols=range(head*4,head*4+4)
            scores=[sum(int(q[row,c])*int(k[j,c]) for c in cols) for j in range(row+1)]
            indices=[min(((max(scores)-s)+8)>>4,255) for s in scores]
            e=[0 if i==255 else int(r.exp[i]) for i in indices]
            reciprocal=(1<<24)//sum(e)
            p=[min((x*reciprocal+(1<<15))>>16,255) for x in e]
            result += [max(-127,min(127,(sum(p[j]*int(v[j,c]) for j in range(row+1))+128)>>8)) for c in cols]
        expected.append(result)
    np.testing.assert_array_equal(actual,expected)
    np.testing.assert_array_equal(actual[0],v[0])

def test_capacity_and_validation_do_not_mutate_cache():
    r=reference(2);row=np.ones(8,dtype=np.int64)
    r.decode(row,row,row)
    with pytest.raises(ValueError): r.prefill(np.ones((2,8),dtype=int),np.ones((2,8),dtype=int),np.ones((2,8),dtype=int))
    assert r.length==1
    with pytest.raises(ValueError): r.decode(row*128,row,row)
    assert r.length==1
    with pytest.raises(ValueError): r.decode(row.astype(float),row,row)

def test_grouped_query_attention_matches_expanded_kv_and_incremental_decode():
    r=reference();exp=r.exp
    rng=np.random.default_rng(72)
    q=rng.integers(-127,128,(5,32),dtype=np.int64)
    k,v=[rng.integers(-127,128,(5,8),dtype=np.int64) for _ in range(2)]
    def grouped(): return CausalAttention(8,4,8,exp,1,4,1,8,kv_heads=2)
    g=grouped();actual=g.prefill(q,k,v)
    expanded=[np.repeat(a.reshape(5,2,4),4,axis=1).reshape(5,32) for a in (k,v)]
    want=CausalAttention(8,4,8,exp,1,4,1,8).prefill(q,*expanded)
    np.testing.assert_array_equal(actual,want)
    stream=grouped()
    np.testing.assert_array_equal(np.stack([stream.decode(q[i],k[i],v[i]) for i in range(5)]),want)
    assert g.keys.shape==(8,8)  # Cache holds two KV heads, not eight repeated copies.
    with pytest.raises(ValueError):CausalAttention(8,4,8,exp,1,4,1,8,kv_heads=3)

def test_rope_identity_quarter_turn_and_saturation():
    x=np.array([[[1,-2,3,-4],[127,-127,127,-127]]],dtype=np.int64)
    np.testing.assert_array_equal(rope_int8(x,np.full((1,2),16384),np.zeros((1,2),dtype=int)),x)
    turned=rope_int8(x,np.zeros((1,2),dtype=int),np.full((1,2),16384))
    np.testing.assert_array_equal(turned,np.concatenate((-x[:,:,2:],x[:,:,:2]),axis=-1))
    sat=rope_int8(x,np.full((1,2),16384),np.full((1,2),16384))
    assert sat[0,1,2]==127 and sat[0,1,3]==-127
    with pytest.raises(ValueError):rope_int8(x,np.ones((2,2),dtype=int),np.zeros((2,2),dtype=int))

@pytest.mark.parametrize('kwargs',[{'heads':2.5},{'sm_shift':1.5},{'context_multiplier':1.5},
                                  {'sm_multiplier':131072},{'context_shift':0}])
def test_invalid_configuration_rejected_before_cache_use(kwargs):
    args=dict(heads=2,head_dim=4,max_context=8,exp=reference().exp,sm_multiplier=1,
              sm_shift=4,context_multiplier=1,context_shift=8)
    args.update(kwargs)
    with pytest.raises(ValueError):CausalAttention(**args)
