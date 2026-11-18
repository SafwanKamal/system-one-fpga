"""Integer causal-attention/KV-cache reference, not a complete model decoder.

Uses the encoder's exp-table/probability/context arithmetic, with a causal prefix.
Grouped-query attention shares KV heads; RMSNorm, gated FFN and model calibration
remain absent. Integer RoPE below consumes externally supplied calibrated tables.
"""
import numpy as np

class CausalAttention:
    def __init__(self, heads, head_dim, max_context, exp, sm_multiplier,
                 sm_shift, context_multiplier, context_shift, *, kv_heads=None):
        if any(not isinstance(v,(int,np.integer)) for v in (heads,head_dim,max_context)):
            raise ValueError('Integer reference dimensions required')
        if not 1 <= heads <= 64 or not 1 <= head_dim <= 256 or not 1 <= max_context <= 4096:
            raise ValueError('Unsupported reference dimensions')
        exp = np.asarray(exp)
        if exp.shape != (256,) or exp.dtype.kind not in 'iu' or np.any(exp < 0) or np.any(exp > 65535) or exp[0] != 65535:
            raise ValueError('Expected 256 UINT16 exponents with exp[0]=65535')
        if any(not isinstance(v,(int,np.integer)) for v in (sm_multiplier,context_multiplier,sm_shift,context_shift)):
            raise ValueError('Integer quantization parameters required')
        if not 0 <= sm_multiplier <= 131071 or not 0 <= context_multiplier <= 131071:
            raise ValueError('Multiplier outside UINT17')
        if not 1 <= sm_shift <= 38 or not 1 <= context_shift <= 39:
            raise ValueError('Unsupported requantization shifts')
        self.heads, self.head_dim, self.max_context = heads, head_dim, max_context
        self.kv_heads = heads if kv_heads is None else kv_heads
        if not isinstance(self.kv_heads,int) or not 1 <= self.kv_heads <= heads or heads % self.kv_heads:
            raise ValueError('KV heads must evenly divide query heads')
        self.exp = exp.astype(np.int64, copy=True)
        self.sm_multiplier, self.sm_shift = sm_multiplier, sm_shift
        self.context_multiplier, self.context_shift = context_multiplier, context_shift
        self.keys = np.zeros((max_context, self.kv_heads * head_dim), dtype=np.int64)
        self.values = np.zeros_like(self.keys)
        self.length = 0

    def reset(self):
        self.length = 0

    def _inputs(self, q, k, v):
        arrays = [np.asarray(a) for a in (q,k,v)]
        shape = arrays[0].shape
        if len(shape) != 2 or shape[1] != self.heads * self.head_dim or any(
                a.shape != (shape[0],self.kv_heads*self.head_dim) for a in arrays[1:]):
            raise ValueError('Q and KV shapes must match token count and their head dimensions')
        if any(a.dtype.kind not in 'iu' or np.any(a < -127) or np.any(a > 127) for a in arrays):
            raise ValueError('Expected symmetric INT8 Q/K/V')
        if self.length + shape[0] > self.max_context:
            raise ValueError('KV-cache capacity exceeded')
        return [a.astype(np.int64, copy=False) for a in arrays]

    @staticmethod
    def _rq(x, multiplier, shift):
        return (x * multiplier + (1 << (shift-1))) >> shift

    def prefill(self, q, k, v):
        q,k,v = self._inputs(q,k,v)  # Validate the whole append before mutating cache.
        out = np.empty(q.shape, dtype=np.int8)
        for row in range(len(q)):
            self.keys[self.length] = k[row]
            self.values[self.length] = v[row]
            self.length += 1
            for head in range(self.heads):
                sl = slice(head*self.head_dim, (head+1)*self.head_dim)
                kv = head // (self.heads // self.kv_heads)
                kv_slice = slice(kv*self.head_dim,(kv+1)*self.head_dim)
                scores = self.keys[:self.length,kv_slice] @ q[row,sl]
                indices = np.minimum(self._rq(scores.max()-scores,self.sm_multiplier,self.sm_shift),255)
                exponent = np.where(indices == 255,0,self.exp[indices])
                reciprocal = (1 << 24) // int(exponent.sum())
                probability = np.minimum((exponent*reciprocal+(1 << 15)) >> 16,255)
                context = probability @ self.values[:self.length,kv_slice]
                out[row,sl] = np.clip(self._rq(context,self.context_multiplier,self.context_shift),-127,127)
        return out

    def decode(self, q, k, v):
        if np.asarray(q).ndim != 1 or np.asarray(k).ndim != 1 or np.asarray(v).ndim != 1:
            raise ValueError('decode accepts one token per Q/K/V vector')
        return self.prefill(np.asarray(q)[None,:],np.asarray(k)[None,:],np.asarray(v)[None,:])[0]


def rope_int8(vectors, cosine, sine, *, fraction=14):
    """Half-split rotation per head with fixed-point tables; clamp to symmetric INT8.

    vectors is [tokens,heads,head_dim], cosine/sine [tokens,head_dim/2].
    Caller owns positions, frequencies and model-specific scaling/calibration.
    """
    x,c,s = [np.asarray(a) for a in (vectors,cosine,sine)]
    if not isinstance(fraction,int) or not 1<=fraction<=15:
        raise ValueError('RoPE table fraction must be 1..15')
    if x.ndim!=3 or x.shape[2]%2 or x.shape[2]==0 or c.shape!=(x.shape[0],x.shape[2]//2) or s.shape!=c.shape:
        raise ValueError('Invalid RoPE vector/table shape')
    if x.dtype.kind not in 'iu' or np.any(x < -127) or np.any(x > 127):
        raise ValueError('Expected symmetric INT8 vectors')
    if any(a.dtype.kind not in 'iu' or np.any(a < -(1<<fraction)) or np.any(a > 1<<fraction) for a in (c,s)):
        raise ValueError('Invalid fixed-point sine/cosine table')
    x=x.astype(np.int64);c=c.astype(np.int64)[:,None,:];s=s.astype(np.int64)[:,None,:]
    half=x.shape[-1]//2;lo=x[:,:,:half];hi=x[:,:,half:]
    rotated=np.concatenate((lo*c-hi*s,hi*c+lo*s),axis=-1)
    return np.clip((rotated+(1<<(fraction-1)))>>fraction,-127,127).astype(np.int8)
