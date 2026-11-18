"""Experimental integer decoder primitives with explicit calibration contracts.

These specify arithmetic for future kernels, not a calibrated model export.
Python integers are intentional: the reference must not hide hardware overflow.
"""
import math
import numpy as np

def _symmetric_int8(values):
    a=np.asarray(values)
    if a.dtype.kind not in 'iu' or np.any(a < -127) or np.any(a > 127):
        raise ValueError('Expected symmetric INT8 values')
    return a

def _quantizer(multiplier,shift):
    if not isinstance(multiplier,int) or not 0<=multiplier<=131071 or not isinstance(shift,int) or not 1<=shift<=63:
        raise ValueError('Expected UINT17 multiplier and 1..63 shift')

def rmsnorm(values,gamma,*,gamma_fraction,inverse_fraction,epsilon_numerator,
            epsilon_denominator,output_multiplier,output_shift):
    """Row-wise RMS normalization in code units with a rational epsilon.

    gamma is signed INT16 fixed-point. epsilon is eps/(input_scale**2),
    supplied as numerator/denominator. Output multiplier/shift includes the
    inverse output scale. Inverse RMS is floored at inverse_fraction precision.
    """
    x=_symmetric_int8(values);g=np.asarray(gamma)
    if x.ndim!=2 or not 1<=x.shape[1]<=8192 or g.shape!=(x.shape[1],):
        raise ValueError('Expected [tokens,hidden] values and one gamma per channel')
    if g.dtype.kind not in 'iu' or np.any(g < -32768) or np.any(g > 32767):
        raise ValueError('Expected signed INT16 gamma')
    if any(not isinstance(v,int) for v in (gamma_fraction,inverse_fraction,epsilon_numerator,epsilon_denominator)):
        raise ValueError('Integer normalization parameters required')
    if not 0<=gamma_fraction<=15 or not 1<=inverse_fraction<=24 or epsilon_numerator<=0 or epsilon_denominator<=0:
        raise ValueError('Invalid fixed-point fractions/epsilon')
    _quantizer(output_multiplier,output_shift)
    total_shift=gamma_fraction+inverse_fraction+output_shift
    n=x.shape[1];out=np.empty(x.shape,dtype=np.int8)
    for row in range(len(x)):
        denominator=sum(int(v)**2 for v in x[row])*epsilon_denominator+epsilon_numerator*n
        inverse=math.isqrt(((n*epsilon_denominator)<<(2*inverse_fraction))//denominator)
        for c in range(n):
            value=int(x[row,c])*int(g[c])*inverse*output_multiplier
            value=(value+(1<<(total_shift-1)))>>total_shift
            out[row,c]=max(-127,min(127,value))
    return out

def gated_multiply(gate,up,activation_table,*,multiplier,shift):
    """Lookup gate activation then multiply by up and requantize.

    Table index is gate code+128; entries are calibrated signed INT16 codes.
    A SiLU table plus this operation provides a SwiGLU primitive, but caller
    owns all gate/up/output scales and table provenance.
    """
    g=_symmetric_int8(gate);u=_symmetric_int8(up);table=np.asarray(activation_table)
    if g.shape!=u.shape or table.shape!=(256,) or table.dtype.kind not in 'iu' or np.any(table < -32768) or np.any(table > 32767):
        raise ValueError('Gate/up shapes and signed INT16 table required')
    _quantizer(multiplier,shift)
    product=table[g.astype(np.int64)+128].astype(np.int64)*u.astype(np.int64)
    return np.clip((product*multiplier+(1<<(shift-1)))>>shift,-127,127).astype(np.int8)
