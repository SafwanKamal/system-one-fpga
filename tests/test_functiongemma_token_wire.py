import struct
import zlib
import pytest
from sysone.v2.functiongemma_token_wire import encode_prompt,decode_prompt,HEADER

SHA=bytes(range(32))


def test_uint32_ids_roundtrip_and_bounds():
    ids=[0,1,65535,65536,131071,262143]
    assert HEADER.size==64
    packet=encode_prompt(ids,SHA)
    assert decode_prompt(packet,SHA)==(ids,256)
    assert decode_prompt(encode_prompt([262143]*1792,SHA),SHA)[0]==[262143]*1792
    for bad in [[],[262144],[-1],[True],[1.5],[1]*1793]:
        with pytest.raises(ValueError):encode_prompt(bad,SHA)


def test_mutated_wire_rejected_including_recomputed_crc_invalid_id():
    packet=encode_prompt([65536,262143],SHA)
    for offset in [0,4,6,8,12,16,20,24,28,32,64]:
        corrupted=bytearray(packet);corrupted[offset]^=1
        with pytest.raises(ValueError):decode_prompt(corrupted,SHA)
    for bad in [packet[:63],packet[:-1],packet+b'\x00']:
        with pytest.raises(ValueError):decode_prompt(bad,SHA)
    corrupted=bytearray(packet);struct.pack_into('<I',corrupted,64,262144)
    struct.pack_into('<I',corrupted,28,zlib.crc32(corrupted[64:]))
    with pytest.raises(ValueError):decode_prompt(corrupted,SHA)
