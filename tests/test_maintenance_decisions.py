"""Decision probabilities, structural dependencies and candidate-head contracts."""
import importlib.util
from pathlib import Path
import sys
import numpy as np
import pytest
import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/v2'))
spec=importlib.util.spec_from_file_location('decisions',ROOT/'scripts/v2/maintenance_decisions.py')
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)


def test_candidate_permutation_equivariance_and_padding():
    torch.manual_seed(0)
    q=torch.randn(2,12);c=torch.randn(2,4,12)
    head=d.CandidateHead(12,q,c,dimension=8).eval()
    h=torch.randn(3,5,12);mask=torch.tensor([[1,1,1,0,0],[1,1,1,1,1],[1,1,0,0,0]],dtype=torch.bool)
    z=head(h,mask).detach()
    h[~mask]=1000
    assert torch.allclose(z,head(h,mask),atol=1e-6)
    order=torch.tensor([2,0,3,1]);head.candidates=c[:,order]
    assert torch.allclose(z[:,:,order],head(h,mask),atol=1e-6)


def test_structural_activity_does_not_require_gold():
    values={'outcome':'plan','length':'2','asset':'0','pred_source':'0','pred_op':'"gt"','pred_rhs':'70',
        '0.tool':'"read_metric"','1.tool':'"draft_report"'}
    keys=d.active_fields(values)
    assert 'pred_op' in keys and '1.evidence' in keys
    assert '0.priority' not in keys and '1.metric' not in keys and 'reason' not in keys
    assert d.active_fields({'outcome':'reject'})==['outcome','reason']


def test_probability_metrics_and_temperature():
    assert np.allclose(d.softmax([0,0]),[.5,.5])
    assert d.softmax([0,2],2)[1]<d.softmax([0,2],1)[1]
    assert d.ece([1,1],[1,1])==0
    assert d.ece([.9,.9],[0,0])==pytest.approx(.9)
    assert d.plan_score({'valid':False},1)==0


def test_question_descriptions_preserve_operator_boundaries():
    descriptions=[d.option_text('pred_op',x) for x in ('"gt"','"ge"','"lt"','"le"')]
    assert len(set(descriptions))==4
    assert '>=' in descriptions[1] and '<=' in descriptions[3]


def test_prediction_and_scoring_roundtrip():
    c=d.make_case('train','conditional',0)
    gold=d.flatten(c['gold'],c['catalog'])
    classes={k:[v] for k,v in gold.items()}
    z={k:[0.] for k in gold}
    r=d.decode(c,z,classes)
    assert r['correct'] and r['valid']
    assert d.plan_score(r,1)==1


def test_padding_logits_does_not_add_candidates():
    c={'a':['x','y'],'b':['z']}
    z=d.mask_logits(torch.zeros(2,2,3),c)
    assert torch.all(z[:,0,2]==-1e4)
    assert torch.all(z[:,1,1:]==-1e4)


def test_right_padded_tail_preserves_decision_gradients():
    from transformers import Qwen3Config,Qwen3Model
    from types import SimpleNamespace
    from maintenance_sft import cached_tail
    torch.set_num_threads(1);torch.manual_seed(12)
    cfg=Qwen3Config(vocab_size=32,hidden_size=16,intermediate_size=32,num_hidden_layers=3,
        num_attention_heads=2,num_key_value_heads=1,head_dim=8,max_position_embeddings=64,
        layer_types=['full_attention']*3)
    base=Qwen3Model(cfg).eval();base.requires_grad_(False)
    for layer in base.layers[1:]:layer.requires_grad_(True)
    head=d.CandidateHead(16,torch.randn(2,16),torch.randn(2,3,16),dimension=8)
    ids=torch.tensor([[1,2,3,4,5,6,7],[3,4,5,6,0,0,0]])
    mask=torch.tensor([[1]*7,[1]*4+[0]*3],dtype=torch.bool);holder={}
    handle=base.layers[1].register_forward_pre_hook(lambda module,args:holder.update(h=args[0].detach().clone()))
    direct=base(input_ids=ids,attention_mask=mask,use_cache=False).last_hidden_state
    handle.remove()
    z=head(direct,mask);loss=torch.nn.functional.cross_entropy(z[:,0],torch.tensor([0,1]));loss.backward()
    expected=base.layers[-1].self_attn.q_proj.weight.grad.clone()
    head_expected=head.state[1].weight.grad.clone()
    base.zero_grad();head.zero_grad()
    replay=cached_tail(SimpleNamespace(model=base,config=base.config),holder['h'],1)
    zr=head(replay,mask)
    torch.nn.functional.cross_entropy(zr[:,0],torch.tensor([0,1])).backward()
    assert torch.allclose(z,zr,atol=1e-6,rtol=1e-5)
    assert torch.allclose(expected,base.layers[-1].self_attn.q_proj.weight.grad,atol=1e-6,rtol=1e-4)
    assert torch.allclose(head_expected,head.state[1].weight.grad,atol=1e-6,rtol=1e-4)


@pytest.mark.parametrize('family',['qwen','gemma'])
def test_selected_token_probabilities_match_generation(family):
    from transformers import Qwen3Config,Qwen3ForCausalLM,Gemma3TextConfig,Gemma3ForCausalLM
    torch.set_num_threads(1);torch.manual_seed(5)
    kw=dict(vocab_size=40,hidden_size=16,intermediate_size=32,num_hidden_layers=2,
        num_attention_heads=2,num_key_value_heads=1,head_dim=8,pad_token_id=0,eos_token_id=None)
    if family=='qwen':model=Qwen3ForCausalLM(Qwen3Config(**kw,layer_types=['full_attention']*2))
    else:model=Gemma3ForCausalLM(Gemma3TextConfig(**kw,layer_types=['sliding_attention','full_attention'],sliding_window=4,final_logit_softcapping=5.))
    model.eval();prompt=list(range(2,13))
    with torch.inference_mode():
        result=model.generate(torch.tensor([prompt]),max_new_tokens=4,do_sample=False,
            return_dict_in_generate=True,output_scores=True,pad_token_id=0,eos_token_id=None)
    generated=result.sequences[0,len(prompt):].tolist()
    expected=[float(z[0].log_softmax(-1)[i]) for z,i in zip(result.scores,generated)]
    assert np.allclose(d.selected_token_logps(model,prompt,generated),expected,atol=1e-5,rtol=1e-5)
    prefix=prompt[:5]
    with torch.inference_mode():cache=model.model(input_ids=torch.tensor([prefix]),use_cache=True).past_key_values
    assert np.allclose(d.selected_token_logps(model,prompt,generated,prefix,cache),expected,atol=1e-5,rtol=1e-5)


def test_plan_calibration_remains_finite_without_correct_examples():
    params,apply=d.fit_plan_map([{'valid':True,'correct':False}]*8,np.linspace(.1,.9,8))
    assert params['plan_calibration_slope']==0
    assert apply(.001)==pytest.approx(.1)
    assert apply(.999)==pytest.approx(.1)
