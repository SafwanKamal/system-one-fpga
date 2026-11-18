"""Candidate host-only 6/7/8-bit signed weight format, not an FPGA ABI.

Tiles keep one tied embedding/projection copy. Packing is lossless for supplied
integer codes; quantization quality is outside this codec's claims.
"""
from dataclasses import dataclass
import numpy as np


def pack_codes(values,bits):
    values=np.asarray(values)
    if bits not in (6,7,8):raise ValueError('unsupported code width')
    if values.dtype.kind!='i':raise TypeError('signed integer codes required')
    if np.any(values<-(1<<(bits-1))) or np.any(values>=(1<<(bits-1))):
        raise ValueError('code outside signed range')
    unsigned=(values.reshape(-1).astype(np.int16)&((1<<bits)-1)).astype(np.uint16)
    bit_matrix=((unsigned[:,None]>>np.arange(bits,dtype=np.uint16))&1).astype(np.uint8)
    return np.packbits(bit_matrix.reshape(-1),bitorder='little').tobytes()


def unpack_codes(data,bits,count):
    if bits not in (6,7,8) or count<0 or len(data)!=(count*bits+7)//8:
        raise ValueError('invalid packed extent')
    binary=np.unpackbits(np.frombuffer(data,dtype=np.uint8),bitorder='little')[:count*bits]
    if count*bits<len(data)*8 and np.any(np.unpackbits(np.frombuffer(data,dtype=np.uint8),bitorder='little')[count*bits:]):
        raise ValueError('nonzero padding bits')
    unsigned=(binary.reshape(count,bits).astype(np.int16)*(1<<np.arange(bits,dtype=np.int16))).sum(axis=1)
    return np.where(unsigned>=(1<<(bits-1)),unsigned-(1<<bits),unsigned).astype(np.int8)


@dataclass(frozen=True)
class PackedWeights:
    data: bytes
    rows: int
    columns: int
    bits: int

    def __post_init__(self):
        if self.bits not in (6,7,8) or self.rows<=0 or self.columns<=0:
            raise ValueError('invalid packed matrix')
        if len(self.data)!=self.output_tiles*self.input_tiles*self.tile_bytes:
            raise ValueError('packed length mismatch')

    @property
    def output_tiles(self):return (self.rows+31)//32
    @property
    def input_tiles(self):return (self.columns+15)//16
    @property
    def tile_bytes(self):return 32*16*self.bits//8

    @classmethod
    def from_codes(cls,codes,bits):
        codes=np.asarray(codes)
        if codes.ndim!=2 or min(codes.shape)<=0:raise ValueError('matrix required')
        if codes.dtype.kind!='i':raise TypeError('signed integer codes required')
        rows,columns=codes.shape
        # Bound temporary bit expansion to one output tile, including for the
        # 262k-row vocabulary. Do not materialize N*D*bits temporary bits.
        blocks=[]
        for start in range(0,rows,32):
            block=codes[start:start+32]
            padded=np.zeros((32,((columns+15)//16)*16),dtype=codes.dtype)
            padded[:len(block),:columns]=block
            tiled=padded.reshape(32,-1,16).transpose(1,0,2)
            blocks.append(pack_codes(tiled,bits))
        return cls(b''.join(blocks),rows,columns,bits)

    def tile(self,out_tile,in_tile):
        if not 0<=out_tile<self.output_tiles or not 0<=in_tile<self.input_tiles:
            raise ValueError('tile index')
        start=(out_tile*self.input_tiles+in_tile)*self.tile_bytes
        return unpack_codes(self.data[start:start+self.tile_bytes],self.bits,512).reshape(32,16)

    def gather(self,row):
        if isinstance(row,(bool,np.bool_)) or not isinstance(row,(int,np.integer)) or not 0<=row<self.rows:
            raise ValueError('embedding ID outside vocabulary')
        group_bytes=16*self.bits//8
        out_tile,within=divmod(row,32)
        pieces=[]
        for k in range(self.input_tiles):
            start=(out_tile*self.input_tiles+k)*self.tile_bytes+within*group_bytes
            pieces.append(unpack_codes(self.data[start:start+group_bytes],self.bits,16))
        return np.concatenate(pieces)[:self.columns]

    def matmul(self,inputs):
        inputs=np.asarray(inputs)
        if inputs.ndim!=2 or inputs.shape[1]!=self.columns or inputs.dtype!=np.int8:
            raise ValueError('INT8 matrix with matching input width required')
        result=np.zeros((len(inputs),self.output_tiles*32),dtype=np.int64)
        for n in range(self.output_tiles):
            for k in range(self.input_tiles):
                start=k*16;end=min(start+16,self.columns)
                result[:,n*32:(n+1)*32]+=inputs[:,start:end].astype(np.int64)@self.tile(n,k)[:,:end-start].astype(np.int64).T
        return result[:,:self.rows]
