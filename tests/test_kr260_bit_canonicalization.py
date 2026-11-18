import pytest
from scripts.v2.kr260.canonicalize_xsa_bit import verify_same_payload

def bit(*,time=b'12:00:00\0',design=b'design\0',part=b'xck26\0',payload=b'FPGA DATA'):
    data=b'\x00\x09'+b'\x0f\xf0'*4+b'\x00\x00\x01'
    for tag,value in zip(b'abcd',[design,part,b'2026/10/13\0',time]):
        data+=bytes([tag])+len(value).to_bytes(2,'big')+value
    return data+b'e'+len(payload).to_bytes(4,'big')+payload

def test_only_timestamp_changes_are_safe_and_payload_hash_is_exact():
    result=verify_same_payload(bit(),bit(time=b'12:01:00\0'))
    assert result['original_sha256']!=result['canonical_sha256']
    assert result['original_time']=='12:00:00' and result['canonical_time']=='12:01:00'

@pytest.mark.parametrize('changed',[bit(payload=b'OTHER DATA'),bit(part=b'wrong\0'),bit(design=b'other\0'),bit()[:-1],b'bad'])
def test_cannot_adopt_different_payload_design_device_or_truncated_export(changed):
    with pytest.raises(ValueError):verify_same_payload(bit(),changed)
