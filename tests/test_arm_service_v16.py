import json
from types import SimpleNamespace
import pytest
from sysone.v2.qwen_arm_service_v16 import Session, COUNTERS, validate_request


class Engine:
    context=1024
    prefill_batch_size=8
    manifest={'eos_ids':[99]}
    clock_hz=125000000
    memory_clock_hz=250000000
    def __init__(self,events):
        self.events=events
        self.scratch=bytearray(256)
        self.prefix_identity={'generation':2}
        self.seq=0
        self.command_timing={}
        for k in COUNTERS:setattr(self,k,0)
    def begin_prefix(self,ids,enabled):
        assert not enabled
        self.seq+=1;self.scratch[128:160]=self.seq.to_bytes(32,'little')
        self.pending_prefix=dict(identity=dict(self.prefix_identity),tag=bytes(self.scratch[128:160]).hex(),prompt_ids=list(ids))
    def prefill_batch(self,ids,pos,logits):
        self.events.append('NN')
        self.tokens+=len(ids);self.prefill_tokens+=len(ids);self.prefill_groups+=1
        return 1
    def close(self):pass


def make(mode='startup',cache=True):
    events=[];e=Engine(events)
    v=SimpleNamespace(encode_text=lambda text:list(range(25)),
        piece=lambda t:b'["read_linux_file","/proc/uptime"]',close=lambda:None)
    def verify():
        events.append('hash');return dict(resident_weights_verified=True,verified_bytes=123,model_verify_ms=10)
    s=Session(e,v,verify,lambda:events.append('identity'),lambda raw:(json.loads(raw),{'executed':True}),
        verification=mode,prefix_cache=cache,startup_proof=dict(resident_weights_verified=True,verified_bytes=123,model_verify_ms=10))
    return s,events


def test_startup_mode_requires_proof_and_does_not_hash_requests():
    s,events=make()
    for _ in range(2):
        r=s.generate(dict(op='generate',query='x'))
        assert not r['request_weights_hashed'] and r['verified_bytes']==0 and r['startup_verified_bytes']==123
    assert 'hash' not in events
    assert r['prefix_tokens_reused']==24 and r['work']['prefill_tokens']==1
    with pytest.raises(RuntimeError,match='startup verification'):
        Session(s.engine,s.vocab,s.verify,s.identity,s.execute)


def test_diagnostic_hashes_every_time_and_cache_can_be_disabled():
    s,events=make('per-request',False)
    for _ in range(2):
        r=s.generate(dict(op='generate',query='x'))
        assert r['request_weights_hashed'] and r['verified_bytes']==123
        assert r['prefix_tokens_reused']==0 and r['work']['prefill_tokens']==25
    assert events.count('hash')==2


def test_conversation_reset_tag_and_identity_changes_invalidate_cache():
    s,events=make()
    request=dict(op='generate',query='x')
    s.generate(request)
    assert s.generate(dict(request,conversation_id='other'))['prefix_tokens_reused']==0
    assert s.generate(dict(request,conversation_id='other',reset_cache=True))['prefix_tokens_reused']==0
    s.engine.scratch[128]^=1
    assert s.generate(dict(request,conversation_id='other'))['prefix_tokens_reused']==0
    s.engine.prefix_identity['generation']=3
    assert s.generate(dict(request,conversation_id='other'))['prefix_tokens_reused']==0


def test_generation_transition_faults_before_any_neural_command():
    s,events=make()
    s.generate(dict(op='generate',query='x'));events.clear()
    def changed():raise RuntimeError('generation changed')
    s.identity=changed
    with pytest.raises(RuntimeError,match='generation changed'):
        s.generate(dict(op='generate',query='x'))
    assert not events and s.state=='FAULTED' and s.cache.ids==[]


def test_invalid_input_does_not_fault_and_metadata_is_bounded():
    s,events=make();s.engine.context=1
    with pytest.raises(ValueError):s.generate(dict(op='generate',query='x'))
    assert s.state=='READY' and not events
    for r in [dict(op='generate',query='x',conversation_id=''),dict(op='generate',query='x',reset_cache=1)]:
        with pytest.raises(ValueError):validate_request(r)
