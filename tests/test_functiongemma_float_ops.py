import numpy as np
import pytest
from sysone.v2.functiongemma_float_ops import FloatGemmaBlock,attention_allowed,rms_norm


def fixture(layer=0,max_context=32):
    config=dict(hidden_size=8,head_dim=4,num_attention_heads=4,num_key_value_heads=1,
        intermediate_size=12,rms_norm_eps=1e-6,hidden_activation='gelu_pytorch_tanh',
        layer_types=['sliding_attention','full_attention'],sliding_window=3,
        rope_local_base_freq=10000.,rope_theta=1000000.,query_pre_attn_scalar=4,
        max_position_embeddings=32768)
    rng=np.random.default_rng(9827)
    shapes={'self_attn.q_proj':(16,8),'self_attn.k_proj':(4,8),'self_attn.v_proj':(4,8),
        'self_attn.o_proj':(8,16),'self_attn.q_norm':(4,),'self_attn.k_norm':(4,),
        'mlp.gate_proj':(12,8),'mlp.up_proj':(12,8),'mlp.down_proj':(8,12)}
    shapes.update({n:(8,) for n in ['input_layernorm','post_attention_layernorm',
        'pre_feedforward_layernorm','post_feedforward_layernorm']})
    weights={k+'.weight':rng.normal(0,.1,size=v) for k,v in shapes.items()}
    return FloatGemmaBlock(weights,config,layer,max_context),rng.normal(size=(7,8))


@pytest.mark.parametrize('layer',[0,1])
def test_incremental_cache_matches_full_prefix_and_is_causal(layer):
    model,x=fixture(layer)
    full,_,_=model(x)
    state=None;pieces=[]
    for chunk in (x[:2],x[2:6],x[6:]):
        y,state,_=model(chunk,state);pieces.append(y)
    np.testing.assert_allclose(np.concatenate(pieces),full,rtol=1e-12,atol=1e-12)
    assert len(state.keys)==(2 if layer==0 else len(x))
    changed=x.copy();changed[-1]*=100
    alternative,_,_=model(changed)
    np.testing.assert_allclose(alternative[:-1],full[:-1],rtol=0,atol=0)


def test_window_boundary_and_gemma_offset_weight():
    assert attention_allowed([512],[0,1,511,512,513],512).tolist()==[[False,True,True,True,False]]
    x=np.array([[1.,2.]])
    np.testing.assert_allclose(rms_norm(x,np.zeros(2),1e-6),x/np.sqrt(2.5+1e-6))


def test_bounded_work_survives_sliding_eviction_and_cache_is_layer_specific():
    model,x=fixture(max_context=7)
    _,state,_=model(x)
    with pytest.raises(ValueError,match='budget'):model(x[:1],state)
    other,_=fixture(layer=1)
    with pytest.raises(ValueError,match='cache layer'):other(x[:1],state)
    with pytest.raises(ValueError,match='budget'):model(x[:2],position_start=32767)
