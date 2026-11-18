import pytest
torch=pytest.importorskip('torch')
pytest.importorskip('transformers')
from transformers.models.gemma3.configuration_gemma3 import Gemma3TextConfig
from transformers.models.gemma3.modeling_gemma3 import Gemma3ForCausalLM
from sysone.v2.functiongemma_batch import generate_ids


def test_variable_length_left_padding_and_cache_eviction_match_single_greedy():
    torch.manual_seed(2026101809)
    cfg=Gemma3TextConfig(hidden_size=8,intermediate_size=12,head_dim=4,
        num_attention_heads=4,num_key_value_heads=1,num_hidden_layers=2,vocab_size=32,
        layer_types=['sliding_attention','full_attention'],sliding_window=3,
        max_position_embeddings=64,query_pre_attn_scalar=4,pad_token_id=0,eos_token_id=1)
    cfg._attn_implementation='eager'
    model=Gemma3ForCausalLM(cfg).float().eval().requires_grad_(False)
    prompts=[[2,10,11,12],[2,7],[2]]
    expected=[]
    with torch.inference_mode():
        for prompt in prompts:
            cache=None;ids=prompt;emitted=[]
            for _ in range(8):
                out=model.model(input_ids=torch.tensor([ids]),past_key_values=cache,use_cache=True)
                cache=out.past_key_values
                token=int(model.lm_head(out.last_hidden_state[:,-1,:]).argmax(-1)[0])
                emitted.append(token)
                if token==1:break
                ids=[token]
            expected.append(emitted)
    actual,_=generate_ids(model,prompts,[1],output_cap=8)
    assert actual==expected
