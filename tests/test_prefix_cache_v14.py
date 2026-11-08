import pytest
from sysone.v2.prefix_cache_v14 import PrefixCache
class Engine:
 def __init__(self):self.prefix_identity={'model':'m','boot':'b'};self.scratch=bytearray(256);self.prefill_batch_size=8;self.seq=0
 def begin_prefix(self,ids,enabled):
  assert enabled is False
  self.seq+=1;self.scratch[128:160]=self.seq.to_bytes(32,'little')
  self.pending_prefix=dict(identity=dict(self.prefix_identity),tag=bytes(self.scratch[128:160]).hex(),prompt_ids=list(ids))
def test_exact_partial_and_shortened_prefix_recompute_final_aligned_batch():
 e=Engine();c=PrefixCache();a=list(range(129))
 assert c.begin(e,a)==0;c.commit(e,a)
 assert c.begin(e,a)==128;c.commit(e,a)
 b=a[:93]+[900]+a[94:];assert c.begin(e,b)==88;c.commit(e,b)
 assert c.begin(e,b[:80])==72
def test_tag_and_identity_invalidate_and_no_package_io():
 e=Engine();c=PrefixCache();a=list(range(40));c.begin(e,a);c.commit(e,a)
 e.scratch[128]=99;assert c.begin(e,a)==0;c.commit(e,a)
 e.prefix_identity['boot']='new';assert c.begin(e,a)==0
def test_failure_reset_and_boundary_are_safe():
 e=Engine();c=PrefixCache();a=list(range(40));c.begin(e,a);c.commit(e,a)
 assert c.begin(e,a)==32 # infer fails, so never commit
 assert c.begin(e,a)==0;c.commit(e,a);c.reset();assert c.begin(e,a)==0
 c.commit(e,a);assert c.begin(e,a,enabled=False)==0
def test_commit_refuses_changed_tags_and_wrong_prompt():
 e=Engine();c=PrefixCache();a=list(range(40));c.begin(e,a);e.scratch[128]=200
 with pytest.raises(RuntimeError):c.commit(e,a)
 c.begin(e,a)
 with pytest.raises(RuntimeError):c.commit(e,a+[9])
