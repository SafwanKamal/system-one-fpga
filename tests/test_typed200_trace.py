import struct
import pytest
from sysone.v2.typed200_trace import assess_trace
from test_typed200_capture import fixture


def trace():
    shared, pl, expected = fixture()
    data = bytearray(1488)
    kinds = list(range(1, 18))
    struct.pack_into('<8IQQ5I', data, 0, 0x54524331, 1, 1, len(kinds), 0, 0, 0, 0,
                     expected.session, expected.request, expected.sequence, 1, 1, 1, 20)
    data[80:336] = pl
    data[336:720] = shared
    for i, kind in enumerate(kinds):
        struct.pack_into('<4IQ', data, 720+24*i, kind, 0,
                         0 if i < 2 else expected.sequence, 1,
                         0 if i < 2 else expected.request)
    return bytes(data), expected


def change(data, offset, value, fmt='<I'):
    b = bytearray(data)
    struct.pack_into(fmt, b, offset, value)
    return bytes(b)


def test_complete_trace_has_capture_before_done_and_ack():
    b, e = trace()
    r = assess_trace(b, e)
    assert len(r['trace_events']) == 17 and r['label'] == 7
    assert not r['timestamps_supplied']
    assert all(event['tick'] is None for event in r['trace_events'])
    for flag in ('timestamp_provenance_verified', 'instrumentation_overhead_bounded',
                 'wcet_certified', 'successful_inference_guaranteed', 'target_execution_verified'):
        assert r[flag] is False


@pytest.mark.parametrize('offset,value', [(0, 0), (4, 2), (8, 0), (12, 0), (12, 33),
    (16, 1), (20, 1), (24, 1), (28, 2), (32, 99), (40, 99), (48, 99),
    (52, 0), (56, 0), (60, 0), (64, 28), (68, 1), (80+0xb4, 1),
    (336+44, 999), (720, 17), (724, 1), (728, 99), (732, 6),
    (720+24*12, 17), (720+24*15, 15), (720+24*17, 1)])
def test_corrupt_or_incomplete_trace_rejected(offset, value):
    b, e = trace()
    with pytest.raises(ValueError):
        assess_trace(change(b, offset, value), e)


def test_clock_ticks_remain_unverified_and_no_wrap_inference():
    b, e = trace()
    b = change(change(change(b, 20, 0xffff), 24, 1000), 28, 1)
    for i in range(17):
        b = change(b, 724+24*i, (0xfffffff0+17*i) & 0xffffffff)
    r = assess_trace(b, e)
    assert r['timestamps_supplied'] and r['trace_events'][1]['tick'] == 1
    assert not r['timestamp_provenance_verified']
    assert 'phase_duration' not in r


@pytest.mark.parametrize('n', [0, 720, 1487, 1489])
def test_trace_size_is_exact(n):
    _, e = trace()
    with pytest.raises(ValueError):
        assess_trace(bytes(n), e)
