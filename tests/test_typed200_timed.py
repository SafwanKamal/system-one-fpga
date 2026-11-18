import struct
import pytest
from sysone.v2.typed200_timed import assess_timed_trace
from test_typed200_trace import trace,change


def fixture():
    b,e=trace()
    b=change(change(change(b,20,0x52355031),24,500000000),28,1)
    for i in range(17):b=change(b,724+24*i,300+100*i)
    pmu=struct.pack('<4IQ12I',0x504d4531,1,1,0,e.session,500000000,19,
        0x41151801,0x80000000,0,0,0x41151801,0x80000000,0,0,100,1900)
    return b,pmu,e


def test_nominal_phases_include_logging_overhead_and_never_claim_guarantee():
    b,p,e=fixture();r=assess_timed_trace(b,p,e)
    assert r['phase_observations']['hidden_copy']=={
        'observed_counter_ticks':100,'nominal_ns_at_declared_hz_ceil':200}
    for k in ('frequency_verified','pmu_ownership_verified','wcet_certified',
              'successful_inference_guaranteed','timestamp_provenance_verified'):
        assert r[k] is False


@pytest.mark.parametrize('offset,value',[(0,0),(4,2),(8,0),(12,1),(12,2),(16,99),
    (24,0),(28,18),(32,0x41151809),(32,0x41151800),(32,0x41151821),
    (36,0),(40,0x80000000),(44,0x80000000),(48,0x41151809),
    (52,0),(56,0x80000000),(60,0x80000000),(64,400),(68,1901)])
def test_bad_pmu_state_is_not_a_timing_measurement(offset,value):
    b,p,e=fixture()
    with pytest.raises(ValueError):assess_timed_trace(b,change(p,offset,value),e)


@pytest.mark.parametrize('tick',[0,799,800,0xffffffff])
def test_no_modular_duration_when_counter_rewinds_stalls_or_wraps(tick):
    b,p,e=fixture()
    with pytest.raises(ValueError):assess_timed_trace(change(b,724+24*6,tick),p,e)


@pytest.mark.parametrize('n',[0,71,73])
def test_exact_evidence_abi(n):
    b,p,e=fixture()
    with pytest.raises(ValueError):assess_timed_trace(b,bytes(n),e)


def test_nominal_conversion_rounds_up_without_float_math():
    b,p,e=fixture();b=change(b,24,3);p=change(p,24,3)
    r=assess_timed_trace(b,p,e)
    assert r['phase_observations']['hidden_copy']['nominal_ns_at_declared_hz_ceil']==33333333334


@pytest.mark.parametrize('offset,value',[(20,0xffff),(24,12345),(28,0)])
def test_trace_clock_must_match_pmu_evidence(offset,value):
    b,p,e=fixture()
    with pytest.raises(ValueError):assess_timed_trace(change(b,offset,value),p,e)
