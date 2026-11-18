from dataclasses import replace
import struct
import pytest
from sysone.v2.typed200_capture import (
    CONTRACT, ExpectedCapture, assess_capture, decode_shared, decode_pl,
)


def fixture(outcome=1, label=7, age=91, origin=1):
    e = ExpectedCapture(0x12345678, 1, 1, 2, 0, 2, 500, True, outcome, label, (101, 102))
    shared = bytearray(384)
    struct.pack_into('<IIQIIII', shared, 0, 0x54594331, 1, e.session, 1, 1, 3, 1)
    struct.pack_into('<HHHHI', shared, 32, 2, 0, 2, 0, 500)
    struct.pack_into('<HH', shared, 44, 101, 102)
    struct.pack_into('<II', shared, 300, 1, origin)
    struct.pack_into('<QQ', shared, 312, e.session, e.request)
    shared[328:360] = bytes.fromhex(CONTRACT)
    struct.pack_into('<IHHB', shared, 360, age, label, 0, outcome)
    pl = [0]*64
    pl[1] = 28 if outcome in (4, 5) else 20
    pl[32] = e.session
    pl[34] = 1
    digest = int(CONTRACT, 16)
    for i in range(8):
        pl[36+i] = digest >> (32*i) & 0xffffffff
    pl[44] = outcome | label << 16
    pl[46] = age
    pl[48] = 0x54590201
    pl[49] = 2
    pl[50] = 2
    pl[51] = 30
    return bytes(shared), struct.pack('<64I', *pl), e


def mutate(data, offset, value, fmt='<I'):
    result = bytearray(data)
    struct.pack_into(fmt, result, offset, value)
    return bytes(result)


def test_independent_layout_and_full_digest_endianness():
    s, p, e = fixture()
    assert decode_shared(s)[0] == decode_pl(p)[0]
    report = assess_capture(s, e, p)
    assert report['label'] == 7 and report['observed_terminal_within_budget']
    for key in ('target_execution_verified', 'successful_inference_guaranteed',
                'wcet_certified', 'external_delivery_guaranteed'):
        assert report[key] is False
    with pytest.raises(ValueError):
        assess_capture(s, e)
    # Earlier transport used the reverse word order; never accept it here.
    wrong = p[:0x90]+b''.join(p[0x90+4*i:0x94+4*i] for i in reversed(range(8)))+p[0xb0:]
    with pytest.raises(ValueError):
        assess_capture(s, e, wrong)


@pytest.mark.parametrize('outcome,label,age', [(1, 0, 1), (1, 17, 500),
    (2, 0, 91), (3, 0, 91), (4, 0, 91), (5, 0, 500)])
def test_terminal_variants_and_inclusive_budget(outcome, label, age):
    s, p, e = fixture(outcome, label, age)
    r = assess_capture(s, e, p)
    assert r['label'] == (label if outcome == 1 else None)
    assert r['observed_terminal_within_budget'] is True


@pytest.mark.parametrize('offset,value,fmt', [
    (0, 0, '<I'), (4, 2, '<I'), (8, 99, '<Q'), (16, 0, '<I'),
    (20, 0, '<I'), (24, 2, '<I'), (28, 2, '<I'), (32, 3, '<H'),
    (34, 1, '<H'), (36, 1, '<H'), (38, 1, '<H'), (40, 499, '<I'),
    (300, 2, '<I'), (304, 2, '<I'), (308, 1, '<I'), (312, 99, '<Q'),
    (320, 99, '<Q'), (328, 0, '<B'), (360, 501, '<I'),
    (364, 18, '<H'), (366, 1, '<H'), (368, 0, '<B'),
    (369, 1, '<B'), (375, 1, '<B'), (376, 1, '<I'), (380, 1, '<I'),
])
def test_corrupt_shared_rejected(offset, value, fmt):
    s, p, e = fixture()
    with pytest.raises(ValueError):
        assess_capture(mutate(s, offset, value, fmt), e, p)


@pytest.mark.parametrize('offset,value', [
    (4, 0), (4, 22), (4, 21), (4, 52), (0xc0, 0),
    (0x80, 99), (0x88, 99), (0x90, 0), (0xb0, 0x70009),
    (0xb0, 0x70000), (0xb0, 0x120001), (0xb4, 0x10000),
    (0xb8, 92), (0xc4, 3), (0xc8, 1), (0xcc, 28),
])
def test_corrupt_pl_rejected(offset, value):
    s, p, e = fixture()
    with pytest.raises(ValueError):
        assess_capture(s, e, mutate(p, offset, value))


def test_cpu_fault_is_not_authoritative_deadline_evidence():
    s, _, e = fixture(4, 0, 0, 0)
    report = assess_capture(s, e)
    assert report['origin'] == 'cpu_rejection_or_fault'
    assert report['elapsed_pl_cycles'] is None
    assert report['observed_terminal_within_budget'] is None
    assert report['label'] is None
    s, _, e = fixture(1, 7, 0, 0)
    with pytest.raises(ValueError):
        assess_capture(s, e)


@pytest.mark.parametrize('age', [0, 499, 501])
def test_deadline_age_is_exactly_d(age):
    s, p, e = fixture(5, 0, age)
    with pytest.raises(ValueError):
        assess_capture(s, e, p)


@pytest.mark.parametrize('outcome', [4, 5])
def test_fault_and_deadline_require_quarantine(outcome):
    s, p, e = fixture(outcome, 0, 500)
    with pytest.raises(ValueError):
        assess_capture(s, e, mutate(p, 4, 20))


def test_immediate_unadmitted_invalid_has_no_budget_claim():
    s, p, _ = fixture(4, 0, 0)
    s = mutate(s, 368, 6, '<B')
    p = mutate(mutate(p, 0xb0, 6), 4, 20)
    e = ExpectedCapture(0x12345678, 1, 1, 2, 0, 2, 500, False, 6, 0, (101, 102))
    assert assess_capture(s, e, p)['observed_terminal_within_budget'] is None


@pytest.mark.parametrize('field,value', [('session', True), ('request', -1),
    ('sequence', 0), ('tokens', 129), ('first', 2), ('count', 3),
    ('budget', 0), ('admitted', 1), ('outcome', 6), ('label', 18),
    ('token_ids', (101,)), ('token_ids', (101, 30522)), ('token_ids', (True, 102)),
    ('contract_sha256', '0'*64)])
def test_expected_manifest_rejects_invalid_admission(field, value):
    _, _, e = fixture()
    with pytest.raises(ValueError):
        replace(e, **{field: value})


@pytest.mark.parametrize('size', [0, 255, 257, 383, 385])
def test_no_truncated_or_oversized_snapshot(size):
    with pytest.raises(ValueError):
        decode_shared(bytes(size))
    with pytest.raises(ValueError):
        decode_pl(bytes(size))


def test_input_binding_rejects_different_ids_even_if_label_matches():
    s, p, e = fixture()
    with pytest.raises(ValueError, match='token IDs mismatch'):
        assess_capture(mutate(s, 44, 999, '<H'), e, p)


@pytest.mark.parametrize('bit', range(256))
def test_all_digest_bits_are_checked(bit):
    s, p, e = fixture()
    damaged = bytearray(s)
    damaged[328+bit//8] ^= 1 << (bit % 8)
    with pytest.raises(ValueError):
        assess_capture(bytes(damaged), e, p)
