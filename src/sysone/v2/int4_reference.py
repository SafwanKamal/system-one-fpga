"""Signed symmetric INT4 primitive reference; not GGUF Q4_K block decoding.

Consecutive values use low nibble then high nibble, two's-complement [-8,7].
Scale/zero-point/calibration contracts remain model-specific and separate.
"""
import numpy as np

def pack(values):
    values=np.asarray(values)
    if values.dtype.kind not in 'iu' or np.any(values < -8) or np.any(values > 7):
        raise ValueError('Signed INT4 weights must be in [-8,7]')
    flat=values.astype(np.int8).reshape(-1)
    nibbles=np.zeros((len(flat)+1)//2*2,dtype=np.uint8)
    nibbles[:len(flat)]=flat.astype(np.uint8)&15
    return (nibbles[0::2]|(nibbles[1::2]<<4)).tobytes()

def unpack(data, count):
    if count<0 or len(data)!=(count+1)//2:
        raise ValueError('Packed weight size mismatch')
    raw=np.frombuffer(data,dtype=np.uint8)
    nibbles=np.empty(len(raw)*2,dtype=np.int8)
    nibbles[0::2]=(raw&15).astype(np.int8)
    nibbles[1::2]=(raw>>4).astype(np.int8)
    if count%2 and nibbles[-1]!=0:
        raise ValueError('Nonzero unused padding nibble')
    return np.where(nibbles[:count]>=8,nibbles[:count]-16,nibbles[:count]).astype(np.int8)

def matvec(activation, packed, rows, cols):
    if rows<=0 or cols<=0: raise ValueError('Positive matrix shape required')
    x=np.asarray(activation)
    if x.shape!=(cols,) or x.dtype.kind not in 'iu' or np.any(x < -127) or np.any(x > 127):
        raise ValueError('Expected symmetric INT8 activation vector')
    weights=unpack(packed,rows*cols).reshape(rows,cols).astype(np.int64)
    return weights @ x.astype(np.int64)
