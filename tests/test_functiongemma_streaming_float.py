import json
import numpy as np
import pytest
torch=pytest.importorskip('torch')
pytest.importorskip('transformers')
from transformers.models.gemma3.configuration_gemma3 import Gemma3TextConfig
from transformers.models.gemma3.modeling_gemma3 import Gemma3ForCausalLM
from sysone.v2.functiongemma_streaming_float import StreamingFloatGemma


def test_complete_decoder_matches_official_model_across_sliding_cache_eviction(tmp_path):
    # Deliberately Q width16 != hidden width8, with a 3-token local window.
    config=dict(model_type='gemma3_text',hidden_size=8,head_dim=4,num_attention_heads=4,
        num_key_value_heads=1,intermediate_size=12,num_hidden_layers=2,vocab_size=32,
        rms_norm_eps=1e-6,hidden_activation='gelu_pytorch_tanh',attention_bias=False,
        attention_dropout=0.,layer_types=['sliding_attention','full_attention'],
        sliding_window=3,rope_local_base_freq=10000.,rope_theta=1000000.,
        query_pre_attn_scalar=4,max_position_embeddings=32768,
        use_bidirectional_attention=False,attn_logit_softcapping=None,final_logit_softcapping=None,
        pad_token_id=0,eos_token_id=1,bos_token_id=2)
    torch.manual_seed(2026101808)
    cfg=Gemma3TextConfig(**config);cfg._attn_implementation='eager'
    oracle=Gemma3ForCausalLM(cfg).float().eval().requires_grad_(False)
    oracle.save_pretrained(tmp_path,safe_serialization=True)
    # The supported official checkpoint uses these legacy RoPE config fields.
    (tmp_path/'config.json').write_text(json.dumps(config),encoding='utf-8')
    model=StreamingFloatGemma(tmp_path);states=None;cache=None
    for ids in ([2,10,11,12],[7],[9],[4]):
        logits,states,hidden=model.step(ids,states)
        with torch.inference_mode():
            actual=oracle.model(input_ids=torch.tensor([ids]),past_key_values=cache,use_cache=True)
            cache=actual.past_key_values
            expected_logits=oracle.lm_head(actual.last_hidden_state[:,-1,:])[0].numpy()
        np.testing.assert_allclose(hidden,actual.last_hidden_state[0,-1].numpy(),atol=1e-5,rtol=1e-5)
        np.testing.assert_allclose(logits,expected_logits,atol=1e-5,rtol=1e-5)
    assert len(states[0].keys)==2 and len(states[1].keys)==7
    with pytest.raises(ValueError,match='token ID'):model.step([32])
    with pytest.raises(ValueError,match='cache layer extent'):model.step([2],states[:1])
