"""Bounded host integer primitives for a future Gemma path; no RTL or image.

Plans use floating point once at compilation. Runtime kernels use integer sums,
integer square root, one reciprocal division per row, tables and fixed shifts.
All rounding is nearest with ties away from zero. No whole-model quality claim.
"""
from dataclasses import dataclass
import math
import numpy as np


def round_shift(values,bits):
    values=np.asarray(values,dtype=np.int64)
    if not 1<=bits<=62:raise ValueError('invalid fixed-point shift')
    half=1<<(bits-1)
    return np.where(values>=0,(values+half)>>bits,-((-values+half)>>bits))


@dataclass(frozen=True)
class RMSPlan:
    channels: int
    epsilon_units: int
    root_constant: int
    multipliers: np.ndarray

    @classmethod
    def compile(cls,weight,input_scale,output_scale,epsilon=1e-6):
        weight=np.asarray(weight,dtype=np.float64)
        if weight.ndim!=1 or not 1<=len(weight)<=2048 or not np.isfinite(weight).all():
            raise ValueError('invalid norm weights')
        if not all(np.isfinite(v) and v>0 for v in (input_scale,output_scale,epsilon)):
            raise ValueError('invalid norm scales')
        with np.errstate(over='ignore',divide='ignore',invalid='ignore'):
            units=np.float64(epsilon)*len(weight)/np.float64(input_scale)**2*(1<<16)
            multipliers=(1+weight)/output_scale*(1<<12)
        if not np.isfinite(units) or not 0<=units<=(1<<60):raise ValueError('epsilon extent')
        if not np.isfinite(multipliers).all() or np.any(np.abs(multipliers)>(1<<31)-1):
            raise ValueError('norm multiplier extent')
        return cls(len(weight),max(1,int(np.floor(units+.5))),
            int(np.floor(math.sqrt(len(weight))*256*4096+.5)),
            (np.sign(multipliers)*np.floor(np.abs(multipliers)+.5)).astype(np.int32))

    def run(self,values):
        values=np.asarray(values)
        if values.ndim!=2 or values.shape[1]!=self.channels or values.dtype not in (np.int8,np.int16):
            raise ValueError('expected INT8/INT16 norm rows')
        x=values.astype(np.int64)
        sums=np.sum(x*x,axis=-1,dtype=np.int64)
        # N<=2048 and |x|<=32768 imply sumsq<<16 <=2^57;
        # epsilon<=2^60 keeps the radicand below 2^61.
        radicands=(sums<<16)+self.epsilon_units
        roots=np.asarray([math.isqrt(int(v)) for v in radicands],dtype=np.int64)
        reciprocal=((1<<40)+roots//2)//roots
        normalized=round_shift(x*reciprocal[:,None]*self.root_constant,40)
        # |x*reciprocal| is bounded by 2^32 plus reciprocal rounding;
        # root_constant<2^26, so the product remains below 2^59.
        if np.any(np.abs(normalized)>(1<<19)):raise ValueError('norm invariant')
        result=round_shift(normalized*self.multipliers[None,:].astype(np.int64),24)
        return np.clip(result,-127,127).astype(np.int8)


@dataclass(frozen=True)
class SoftmaxPlan:
    distance_multiplier: int
    exponent_table: np.ndarray
    max_length: int=2048
    dot_bound: int=256*128*128

    @classmethod
    def compile(cls,score_scale,max_length=2048,head_dim=256):
        if not np.isfinite(score_scale) or score_scale<=0 or not 1<=max_length<=2048 or not 1<=head_dim<=2048:
            raise ValueError('invalid softmax profile')
        multiplier=score_scale*128*(1<<20)
        if not np.isfinite(multiplier) or multiplier>(1<<31)-1:raise ValueError('softmax scale extent')
        table=np.floor(np.exp(-np.arange(2048)/128)*((1<<24)-1)+.5).astype(np.int64)
        return cls(int(np.floor(multiplier+.5)),table,max_length,head_dim*128*128)

    def run(self,scores,allowed):
        scores=np.asarray(scores);allowed=np.asarray(allowed)
        if scores.ndim!=1 or scores.dtype!=np.int32 or allowed.dtype!=np.bool_ or allowed.shape!=scores.shape or not 1<=len(scores)<=self.max_length:
            raise ValueError('invalid score row or mask')
        if not np.any(allowed):raise ValueError('empty attention row')
        valid=scores[allowed].astype(np.int64)
        if np.any(np.abs(valid)>self.dot_bound):raise ValueError('dot-product bound')
        distances=int(valid.max())-valid
        indices=round_shift(distances*self.distance_multiplier,20)
        exponent=np.where(indices<2048,self.exponent_table[np.minimum(indices,2047)],0)
        total=int(np.sum(exponent,dtype=np.int64))
        # Exponents are 24-bit; at most2048 terms -> total<2^35.
        reciprocal=((1<<56)+total//2)//total
        probabilities=np.clip(round_shift(exponent*reciprocal,40),0,65535).astype(np.uint16)
        # A Q8 probability row would become all-zero for uniform length2048.
        # Q16 preserves that row. Integer normalization rounding permits <=N/2
        # total code excess, which also bounds the subsequent value accumulator.
        if int(probabilities.astype(np.int64).sum())>65536+(len(valid)+1)//2+1:
            raise ValueError('probability sum invariant')
        result=np.zeros(len(scores),dtype=np.uint16);result[allowed]=probabilities
        return result


def attention_context(probabilities,values):
    p=np.asarray(probabilities);v=np.asarray(values)
    if p.ndim!=1 or p.dtype!=np.uint16 or v.ndim!=2 or v.dtype!=np.int8 or len(v)!=len(p) or not 1<=len(p)<=2048:
        raise ValueError('invalid attention context inputs')
    if int(p.astype(np.int64).sum())>65536+(len(p)+1)//2+1:
        raise ValueError('probability sum invariant')
    sums=p.astype(np.int64)@v.astype(np.int64)
    # The normalized row sum limits |sum| to about8.6 million, despite
    # UINT16 probabilities; a 32-bit value accumulator is sufficient.
    if np.any(np.abs(sums)>=(1<<31)):raise ValueError('context accumulator bound')
    return np.clip(round_shift(sums,16),-127,127).astype(np.int8)
