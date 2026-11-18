"""Offline proposed FGT1 request boundary; incompatible with current firmware.

This transports uint32 text-model IDs without truncating the 18-bit vocabulary.
It validates a request only: no cache ownership, dispatch or publication protocol.
"""
import struct
import zlib
from .functiongemma_profile import validate_prompt_ids

HEADER=struct.Struct('<4sHH6I32s')
MAGIC=b'FGT1'
VOCAB=262144
CONTEXT=2048
MAX_OUTPUT=256


def encode_prompt(ids,model_sha256,output_reserve=256):
    if not isinstance(model_sha256,bytes) or len(model_sha256)!=32:raise ValueError('32-byte model SHA required')
    if type(output_reserve) is not int or not 1<=output_reserve<=MAX_OUTPUT:raise ValueError('output reserve')
    validate_prompt_ids(ids,VOCAB,CONTEXT,output_reserve)
    payload=struct.pack('<'+'I'*len(ids),*map(int,ids))
    return HEADER.pack(MAGIC,1,HEADER.size,len(ids),output_reserve,CONTEXT,VOCAB,
        len(payload),zlib.crc32(payload),model_sha256)+payload


def decode_prompt(data,expected_model_sha256):
    if not isinstance(expected_model_sha256,bytes) or len(expected_model_sha256)!=32:raise ValueError('32-byte model SHA required')
    if len(data)<HEADER.size:raise ValueError('short header')
    magic,version,hlen,count,reserve,context,vocab,length,crc,model_sha=HEADER.unpack_from(data)
    if (magic,version,hlen,context,vocab)!=(MAGIC,1,HEADER.size,CONTEXT,VOCAB):raise ValueError('header profile')
    if model_sha!=expected_model_sha256:raise ValueError('model identity')
    if not 1<=reserve<=MAX_OUTPUT or not 1<=count<=CONTEXT-reserve:raise ValueError('prompt/output bounds')
    if length!=4*count or len(data)!=HEADER.size+length:raise ValueError('payload extent')
    payload=data[HEADER.size:]
    if zlib.crc32(payload)!=crc:raise ValueError('payload CRC')
    ids=list(struct.unpack('<'+'I'*count,payload))
    validate_prompt_ids(ids,VOCAB,CONTEXT,reserve)
    return ids,reserve
