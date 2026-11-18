"""Offline Gemma3 block reference for port development, not FPGA arithmetic.

Independent NumPy dense operations, one unpadded stream, bounded work and KV
storage. Uses explicit head_dim, GQA, local/global RoPE and Gemma's 1+weight RMS.
No image export, RTL, device I/O, generation or deadline claim.
"""
from dataclasses import dataclass
import numpy as np


def rms_norm(x, weight, epsilon):
    return x / np.sqrt(np.mean(x*x, axis=-1, keepdims=True)+epsilon) * (1+weight)


def gelu_tanh(x):
    return .5*x*(1+np.tanh(np.sqrt(2/np.pi)*(x+.044715*x*x*x)))


def rotary(x, positions, theta):
    width=x.shape[-1]
    if width%2:
        raise ValueError('rotary width must be even')
    # Official implementation explicitly computes phases in float32, including
    # at large positions. Other reference arithmetic uses float64.
    inv=(1/np.power(np.float32(theta),np.arange(0,width,2,dtype=np.float32)/width)).astype(np.float32)
    phase=(np.asarray(positions,dtype=np.float32)[:,None]*inv[None,:]).astype(np.float32)
    phase=np.concatenate((phase,phase),axis=-1)
    cosine=np.cos(phase).astype(np.float64)[:,None,:]
    sine=np.sin(phase).astype(np.float64)[:,None,:]
    half=width//2
    rotated=np.concatenate((-x[...,half:],x[...,:half]),axis=-1)
    return x*cosine+rotated*sine


def attention_allowed(query_positions, key_positions, window=None):
    distance=np.asarray(query_positions)[:,None]-np.asarray(key_positions)[None,:]
    return (distance>=0) if window is None else ((distance>=0)&(distance<window))


@dataclass(frozen=True)
class KVState:
    layer: int
    keys: np.ndarray
    values: np.ndarray
    positions: np.ndarray
    next_position: int
    seen_tokens: int


class FloatGemmaBlock:
    def __init__(self, weights, config, layer, max_context=2048):
        self.w={k:np.asarray(v,dtype=np.float64) for k,v in weights.items()}
        self.config=dict(config);self.layer=layer;self.max_context=max_context
        self.hidden=config['hidden_size'];self.head=config['head_dim']
        self.qheads=config['num_attention_heads'];self.kvheads=config['num_key_value_heads']
        self.middle=config['intermediate_size'];self.epsilon=config['rms_norm_eps']
        if min(self.hidden,self.head,self.qheads,self.kvheads,self.middle,max_context)<=0 or self.head%2 or self.qheads%self.kvheads:
            raise ValueError('invalid dimensions')
        if config.get('attention_bias',False) or config.get('hidden_activation')!='gelu_pytorch_tanh':
            raise ValueError('unsupported bias or activation')
        if config.get('attn_logit_softcapping') is not None or config.get('use_bidirectional_attention',False):
            raise ValueError('unsupported attention variant')
        kind=config['layer_types'][layer]
        if kind not in ('sliding_attention','full_attention'):
            raise ValueError('unsupported layer type')
        self.window=config['sliding_window'] if kind=='sliding_attention' else None
        if self.window is not None and self.window<2:
            raise ValueError('sliding window must be at least two')
        self.theta=config['rope_local_base_freq'] if self.window else config['rope_theta']
        self.scaling=config['query_pre_attn_scalar']**-.5
        shapes={
            'self_attn.q_proj.weight':(self.qheads*self.head,self.hidden),
            'self_attn.k_proj.weight':(self.kvheads*self.head,self.hidden),
            'self_attn.v_proj.weight':(self.kvheads*self.head,self.hidden),
            'self_attn.o_proj.weight':(self.hidden,self.qheads*self.head),
            'self_attn.q_norm.weight':(self.head,), 'self_attn.k_norm.weight':(self.head,),
            'mlp.gate_proj.weight':(self.middle,self.hidden),
            'mlp.up_proj.weight':(self.middle,self.hidden),
            'mlp.down_proj.weight':(self.hidden,self.middle)}
        shapes.update({n+'.weight':(self.hidden,) for n in
            ['input_layernorm','post_attention_layernorm','pre_feedforward_layernorm','post_feedforward_layernorm']})
        if set(self.w)!=set(shapes) or any(self.w[k].shape!=v for k,v in shapes.items()):
            raise ValueError('weight ABI mismatch')
        if any(not np.isfinite(v).all() for v in self.w.values()):
            raise ValueError('nonfinite weights')

    def __call__(self, hidden, state=None, position_start=0):
        x=np.asarray(hidden,dtype=np.float64)
        if x.ndim!=2 or x.shape[1]!=self.hidden or not len(x) or not np.isfinite(x).all():
            raise ValueError('expected finite nonempty unpadded hidden stream')
        seen=0 if state is None else state.seen_tokens
        start=position_start if state is None else state.next_position
        if state is not None and (state.layer!=self.layer or position_start!=0):
            raise ValueError('cache layer or position mismatch')
        if start<0 or start+len(x)>self.config['max_position_embeddings'] or seen+len(x)>self.max_context:
            raise ValueError('position or work budget exceeded')
        positions=np.arange(start,start+len(x),dtype=np.int64)
        norm=lambda value,name:rms_norm(value,self.w[name+'.weight'],self.epsilon)
        linear=lambda value,name:value@self.w[name+'.weight'].T
        normalized=norm(x,'input_layernorm')
        q=linear(normalized,'self_attn.q_proj').reshape(len(x),self.qheads,self.head)
        k=linear(normalized,'self_attn.k_proj').reshape(len(x),self.kvheads,self.head)
        v=linear(normalized,'self_attn.v_proj').reshape(len(x),self.kvheads,self.head)
        q=rotary(norm(q,'self_attn.q_norm'),positions,self.theta)
        k=rotary(norm(k,'self_attn.k_norm'),positions,self.theta)
        if state is not None:
            k=np.concatenate((state.keys,k));v=np.concatenate((state.values,v))
            key_positions=np.concatenate((state.positions,positions))
        else:key_positions=positions
        repeat=self.qheads//self.kvheads
        keys=np.repeat(k,repeat,axis=1).transpose(1,2,0)
        values=np.repeat(v,repeat,axis=1).transpose(1,0,2)
        scores=(q.transpose(1,0,2)@keys)*self.scaling
        allowed=attention_allowed(positions,key_positions,self.window)
        scores=np.where(allowed[None,:,:],scores,-np.inf)
        probabilities=np.exp(scores-np.max(scores,axis=-1,keepdims=True))
        probabilities/=np.sum(probabilities,axis=-1,keepdims=True)
        context=(probabilities@values).transpose(1,0,2).reshape(len(x),self.qheads*self.head)
        attention=linear(context,'self_attn.o_proj')
        post_attention=x+norm(attention,'post_attention_layernorm')
        ff_input=norm(post_attention,'pre_feedforward_layernorm')
        gated=gelu_tanh(linear(ff_input,'mlp.gate_proj'))*linear(ff_input,'mlp.up_proj')
        feedforward=linear(gated,'mlp.down_proj')
        output=post_attention+norm(feedforward,'post_feedforward_layernorm')
        keep=len(k) if self.window is None else min(len(k),self.window-1)
        updated=KVState(self.layer,k[-keep:].copy(),v[-keep:].copy(),key_positions[-keep:].copy(),
                        int(positions[-1])+1,seen+len(x))
        return output,updated,dict(input_norm=normalized,rotated_queries=q,keys=k,
            attention=attention,post_attention=post_attention,ff_input=ff_input,
            feedforward=feedforward,output=output)
