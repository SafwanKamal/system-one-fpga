"""Guard split lineage, target framing and native-wrapper semantics."""
import importlib.util
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/v2'))
spec = importlib.util.spec_from_file_location('maintenance_sft', ROOT/'scripts/v2/maintenance_sft.py')
sft = importlib.util.module_from_spec(spec); spec.loader.exec_module(sft)


def test_native_adapter_is_exact_and_does_not_repair():
    payload='["plan",[["read_metric","P61",{"metric":"temperature"},false]],null]'
    assert sft.unwrap('functiongemma',sft.PREFIX+payload+sft.SUFFIX)==payload
    for raw in (payload,'text '+sft.PREFIX+payload+sft.SUFFIX,
                sft.PREFIX+payload+sft.SUFFIX+' extra',sft.PREFIX+payload):
        with pytest.raises(ValueError): sft.unwrap('functiongemma',raw)


def test_conditional_stress_fully_crosses_factors():
    rows=sft.conditional_cases()
    combinations=set()
    for case in rows:
        ast=sft.parse(sft.encode(case['gold']),case['catalog'])
        combinations.add((ast['predicate']['op'],str(ast['predicate']['rhs']),
            ast['steps'][-1]['tool'],len(ast['steps']),ast['steps'][-1]['priority']))
        assert ast['steps'][0]['guard'] is False
        assert all(n['guard'] for n in ast['steps'][1:])
    assert len(rows)==len(combinations)==64


def test_official_functiongemma_template_round_trip():
    from transformers import AutoTokenizer
    from sysone.v2.maintenance.revision2 import corpus
    tok=AutoTokenizer.from_pretrained(str(sft.FG),local_files_only=True)
    case=next(c for c in corpus()['train'] if c['stratum']=='conditional')
    job=sft.serialize(tok,'functiongemma',case,training=True)
    assert len(job['prompt_ids'])+256<=1024
    assert job['input_ids'][:job['prompt_tokens']]==job['prompt_ids']
    assert sft.unwrap('functiongemma',job['target'].removesuffix('<start_function_response>'))==sft.encode(case['gold'])
    public=dict(sft.public_input(case),id=case['id'])
    inference=sft.serialize(tok,'functiongemma',public)
    assert inference['id']==case['id'] and inference['prompt_ids']==job['prompt_ids']
    assert 'target_ids' not in inference and 'gold' not in public


def test_cached_tail_matches_unmodified_tiny_qwen_and_gradient_shift():
    import torch
    from transformers import Qwen3Config,Qwen3ForCausalLM
    torch.set_num_threads(1); torch.manual_seed(1)
    model=Qwen3ForCausalLM(Qwen3Config(vocab_size=40,hidden_size=16,intermediate_size=32,
        num_hidden_layers=3,num_attention_heads=2,num_key_value_heads=1,head_dim=8,
        layer_types=['full_attention']*3,attention_dropout=0.0))
    model.eval(); model.requires_grad_(False); model.model.layers[-1].requires_grad_(True)
    ids=torch.tensor([[2,3,4,5,6]])
    with torch.no_grad():
        expected=model.model(ids,use_cache=False).last_hidden_state
        hidden=model.model.embed_tokens(ids)
        positions=torch.arange(5).unsqueeze(0)
        rotary=model.model.rotary_emb(hidden,positions)
        for layer in model.model.layers[:2]:
            hidden=layer(hidden,attention_mask=None,position_ids=positions,position_embeddings=rotary)
    # Capture with the actual mask machinery rather than a manually unmasked prefix.
    captured={}
    def capture(module,args,kwargs): captured['hidden']=args[0].detach()
    hook=model.model.layers[2].register_forward_pre_hook(capture,with_kwargs=True)
    with torch.no_grad(): model.model(ids,use_cache=False)
    hook.remove()
    actual=sft.cached_tail(model,captured['hidden'],2)
    torch.testing.assert_close(actual,expected)
    job=dict(prompt_tokens=3,target_ids=[5,6,7])
    loss=sft.token_loss(model,captured['hidden'],job,2)
    reference=torch.nn.functional.cross_entropy(model.lm_head(actual[:,2:,:])[0],torch.tensor([5,6,7]))
    torch.testing.assert_close(loss,reference)
    loss.backward()
    assert any(p.grad is not None for p in model.model.layers[-1].parameters())
    assert all(p.grad is None for p in model.model.layers[0].parameters())


@pytest.mark.parametrize('family',['qwen','gemma'])
def test_shared_frozen_prefix_matches_full_forward(tmp_path,family):
    import torch
    from transformers import Qwen3Config,Qwen3ForCausalLM,Gemma3TextConfig,Gemma3ForCausalLM
    torch.set_num_threads(1); torch.manual_seed(2)
    kwargs=dict(vocab_size=40,hidden_size=16,intermediate_size=32,num_hidden_layers=3,
        num_attention_heads=2,num_key_value_heads=1,head_dim=8,attention_dropout=0.0)
    if family=='qwen':
        model=Qwen3ForCausalLM(Qwen3Config(**kwargs,layer_types=['full_attention']*3))
    else:
        model=Gemma3ForCausalLM(Gemma3TextConfig(**kwargs,
            layer_types=['sliding_attention','sliding_attention','full_attention'],sliding_window=8))
    model.eval(); model.requires_grad_(False)
    rows=[dict(id='a',input_ids=list(range(2,18))),dict(id='b',input_ids=list(range(2,9))+[20,21,22,23,24])]
    paths=sft.cache_prefix(model,rows,tmp_path/'cache',2)
    for row,path in zip(rows,paths):
        with torch.no_grad():
            direct=model.model(torch.tensor([row['input_ids'][:-1]]),use_cache=False).last_hidden_state
            replay=sft.cached_tail(model,torch.load(path,weights_only=True),2)
        torch.testing.assert_close(direct,replay,atol=0.0001,rtol=0.0001)


@pytest.mark.parametrize('family',['qwen','gemma'])
def test_shared_trainable_prefix_preserves_loss_and_gradients(family):
    import torch
    from transformers import Qwen3Config,Qwen3ForCausalLM,Gemma3TextConfig,Gemma3ForCausalLM
    torch.set_num_threads(1); torch.manual_seed(3)
    kwargs=dict(vocab_size=40,hidden_size=16,intermediate_size=32,num_hidden_layers=2,
        num_attention_heads=2,num_key_value_heads=1,head_dim=8,attention_dropout=0.0)
    if family=='qwen':
        model=Qwen3ForCausalLM(Qwen3Config(**kwargs,layer_types=['full_attention']*2))
    else:
        model=Gemma3ForCausalLM(Gemma3TextConfig(**kwargs,
            layer_types=['sliding_attention','full_attention'],sliding_window=4))
    model.eval(); model.requires_grad_(False)
    for layer in model.model.layers: layer.requires_grad_(True)
    prefix=torch.randn(1,3,16)
    hidden=[torch.cat([prefix,torch.randn(1,5,16)],dim=1),torch.cat([prefix,torch.randn(1,7,16)],dim=1)]
    records=[dict(prompt_tokens=5,target_ids=[7,8,9,10]),dict(prompt_tokens=6,target_ids=[11,12,13,14,15])]
    reference=sum(sft.token_loss(model,h,r,0) for h,r in zip(hidden,records))/2
    reference.backward()
    gradients=[p.grad.clone() for p in model.parameters() if p.requires_grad]
    model.zero_grad()
    shared=sft.shared_batch_loss(model,hidden,records,0,3)
    torch.testing.assert_close(reference,shared,atol=0.00001,rtol=0.00001)
    shared.backward()
    for parameter,expected in zip([p for p in model.parameters() if p.requires_grad],gradients):
        torch.testing.assert_close(parameter.grad,expected,atol=0.00001,rtol=0.0001)


@pytest.mark.parametrize('family',['qwen','gemma'])
def test_quantized_decoder_can_generate_with_left_padding(family):
    import torch
    from transformers import Qwen3Config,Qwen3ForCausalLM,Gemma3TextConfig,Gemma3ForCausalLM
    torch.set_num_threads(1)
    kwargs=dict(vocab_size=40,hidden_size=16,intermediate_size=32,num_hidden_layers=2,
        num_attention_heads=2,num_key_value_heads=1,head_dim=8,pad_token_id=0,eos_token_id=1)
    if family=='qwen':
        model=Qwen3ForCausalLM(Qwen3Config(**kwargs,layer_types=['full_attention']*2))
    else:
        model=Gemma3ForCausalLM(Gemma3TextConfig(**kwargs,
            layer_types=['sliding_attention','full_attention'],sliding_window=4))
    model.eval()
    model=torch.ao.quantization.quantize_dynamic(model,{torch.nn.Linear},dtype=torch.qint8,inplace=True)
    with torch.inference_mode():
        result=model.generate(torch.tensor([[0,2,3],[2,3,4]]),attention_mask=torch.tensor([[0,1,1],[1,1,1]]),
            max_new_tokens=3,do_sample=False,pad_token_id=0,eos_token_id=1)
    assert result.shape[0]==2 and 3<result.shape[1]<=6
