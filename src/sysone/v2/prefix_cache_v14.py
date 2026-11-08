"""Single-owner, in-memory prefix validity; no deployment package writes."""
class PrefixCache:
 def __init__(self):self.reset()
 def reset(self):self.ids=[];self.identity=None;self.tag=None;self.pending=None
 def begin(self,engine,ids,enabled=True):
  if not ids:raise ValueError('Empty prompt')
  identity=dict(engine.prefix_identity);tag=bytes(engine.scratch[0x80:0xa0]).hex();matched=0
  if enabled and self.identity==identity and self.tag==tag:
   for a,b in zip(self.ids,ids):
    if a!=b:break
    matched+=1
  # Retain original eight-token batch boundaries; recompute the final token/logits.
  matched=(min(matched,len(ids)-1)//engine.prefill_batch_size)*engine.prefill_batch_size
  self.reset() # Exceptions/interruptions can never commit stale state.
  engine.begin_prefix(ids,enabled=False) # rotate physical tag, never reads/writes package cache files
  self.pending=dict(engine.pending_prefix,prompt_ids=list(ids))
  return matched
 def commit(self,engine,ids):
  p=self.pending
  if not p or p['prompt_ids']!=list(ids) or p['identity']!=engine.prefix_identity or p['tag']!=bytes(engine.scratch[0x80:0xa0]).hex():
   self.reset();raise RuntimeError('Prefix invalidated before commit')
  self.ids=list(ids);self.identity=dict(p['identity']);self.tag=p['tag'];self.pending=None
