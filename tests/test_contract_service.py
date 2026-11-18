import hashlib
import json
from types import SimpleNamespace as NS

import pytest

from sysone.v2.contract_service import (HeadType, Outcome, OutputSchema, PredictionValue,
                                        TypedEncoderService, TypedResult)
from sysone.v2.timing_policy import TimingPolicy

IMAGE = b'bound-model-fixture'
HASH = hashlib.sha256(IMAGE).hexdigest()


def prediction(head='intent.demo', labels=None, probability=None, segment=0, words=None):
    return NS(head=head, labels=labels or ['on'], probability=probability or [0.9],
              segment=segment, words=words)


def schema():
    return OutputSchema((HeadType('intent.demo', 'intent', ('on', 'off')),
                         HeadType('slots.demo', 'slots', ('O', 'B-device', 'I-device')),
                         HeadType('pair.demo', 'pair', ('same', 'different'))))


class Encoder:
    def __init__(self, cycles=100, error=None):
        self.machine = NS(mem=NS(buf=IMAGE), h={'vocab': 100, 'max_tokens': 128})
        self.cycles, self.error, self.calls = cycles, error, 0

    def encode(self, ids, timeout):
        self.calls += 1
        if self.error:
            raise self.error
        return NS(x='hidden', run=NS(total_clocks=self.cycles, status=0))


def service(encoder=None, now=lambda: 0):
    return TypedEncoderService(encoder or Encoder(), schema(),
        TimingPolicy(HASH, 200_000_000, 128, 100, 5),
        model_sha256=HASH, clock_hz=200_000_000, monotonic_ns=now)


def test_accepted_exact_boundary_is_typed_serialized_and_has_no_false_guarantee():
    s = service()
    r = s.run([1], lambda x: [prediction()])
    assert r.outcome is Outcome.ACCEPTED
    record = json.loads(r.to_json())
    assert record['payload'][0]['labels'] == ['on']
    assert not record['successful_completion_guaranteed']
    assert not record['host_delivery_guaranteed']
    assert record['schema_sha256'] == schema().sha256
    assert record['contract_sha256'] == s.contract_sha256
    assert not record['semantic_correctness_guaranteed']


@pytest.mark.parametrize('bad', [[], [True], [-1], [100], [65536], list(range(129)), '1'])
def test_admission_rejects_before_encoder(bad):
    e = Encoder(); r = service(e).run(bad, lambda x: [prediction()])
    assert r.outcome is Outcome.INVALID_INPUT and not r.payload and e.calls == 0


@pytest.mark.parametrize('p', [prediction(labels=['arbitrary-action']),
    prediction(probability=[float('nan')]), prediction(probability=[True]),
    prediction(segment=True), prediction(words=['extra']), prediction(head='intent.other'),
    prediction(head='slots.demo', labels=['I-device'], words=['lamp'])])
def test_schema_violation_never_publishes_raw_prediction(p):
    s = service(); r = s.run([1], lambda x: [p])
    assert r.outcome is Outcome.HARDWARE_FAULT and not r.payload
    assert s.quarantined


def test_slots_validate_bio_and_bound_words_without_silent_repair():
    p = prediction(head='slots.demo', labels=['B-device', 'I-device', 'O'],
                   probability=[0.9]*3, words=['desk', 'lamp', 'please'])
    assert schema().validate([p])[0].words == ('desk', 'lamp', 'please')
    with pytest.raises(ValueError):
        schema().validate([p, p])


@pytest.mark.parametrize('cycles,error', [(101, None), (100, TimeoutError()),
                                        (100, OSError('link failure'))])
def test_deadline_or_fault_quarantines_and_does_not_retry(cycles, error):
    e = Encoder(cycles, error); s = service(e)
    first = s.run([1], lambda x: [prediction()])
    assert first.outcome in (Outcome.DEADLINE_EXCEEDED, Outcome.HARDWARE_FAULT)
    assert not first.payload
    assert s.run([1], lambda x: [prediction()]).outcome is Outcome.HARDWARE_FAULT
    assert e.calls == 1


def test_late_head_cannot_publish_accepted_result():
    clock = [0]
    s = service(now=lambda: clock[0])
    def slow_head(x):
        clock[0] = 5_000_001
        return [prediction()]
    r = s.run([1], slow_head)
    assert r.outcome is Outcome.DEADLINE_EXCEEDED and not r.payload


def test_reentrant_request_is_rejected_without_corrupting_outer_result():
    s = service()
    def head(x):
        assert s.run([2], lambda x: [prediction()]).outcome is Outcome.HARDWARE_FAULT
        return [prediction()]
    assert s.run([1], head).outcome is Outcome.ACCEPTED


@pytest.mark.parametrize('outcome', [Outcome.CLARIFY, Outcome.ABSTAIN])
def test_application_rejection_has_no_actionable_payload(outcome):
    r = service().run([1], lambda x: pytest.fail('head not needed'), decision=outcome)
    assert r.outcome is outcome and not r.payload


def test_checked_constructor_cannot_bypass_label_schema():
    p = PredictionValue('intent.demo', 'intent', 0, ('launch-anything',), (1.0,), None)
    with pytest.raises(ValueError):
        TypedResult(Outcome.ACCEPTED, HASH, 200_000_000, 1, 1, (p,), schema=schema(), contract_sha256='a'*64)
    with pytest.raises(ValueError):
        TypedResult(Outcome.DEADLINE_EXCEEDED, HASH, 200_000_000, 1, 1, (p,))


def test_model_binding_checks_actual_encoder_bytes():
    e = Encoder(); e.machine.mem.buf = b'different model'
    with pytest.raises(ValueError, match='Encoder bytes'):
        service(e)


@pytest.mark.parametrize('bad', [True, -1, 1 << 32, '100'])
def test_invalid_backend_counter_maps_to_typed_fault(bad):
    r = service(Encoder(bad)).run([1], lambda x: [prediction()])
    assert r.outcome is Outcome.HARDWARE_FAULT and r.request_cycles is None


def test_unexpected_head_failure_maps_to_fault_and_no_partial_payload():
    def broken_head(x):
        raise KeyError('missing task head')
    r = service().run([1], broken_head)
    assert r.outcome is Outcome.HARDWARE_FAULT and not r.payload


def test_scope_or_risk_policy_can_abstain_after_checked_head_output():
    r = service().run([1], lambda x: [prediction()], decide=lambda checked: Outcome.ABSTAIN)
    assert r.outcome is Outcome.ABSTAIN and not r.payload


def test_untyped_policy_decision_cannot_publish_success():
    r = service().run([1], lambda x: [prediction()], decide=lambda checked: 'accepted')
    assert r.outcome is Outcome.HARDWARE_FAULT and not r.payload


def test_cpu_reference_cannot_be_reported_as_measured_fabric_execution():
    e = Encoder(); e.local = True
    with pytest.raises(ValueError, match='CPU reference'):
        service(e)


def test_recorded_driver_clock_must_match_timing_policy():
    e = Encoder(); e.link = NS(clock_hz=125_000_000)
    with pytest.raises(ValueError, match='Driver clock'):
        service(e)


def test_schema_head_count_has_an_explicit_execution_bound():
    with pytest.raises(ValueError):
        OutputSchema(tuple(HeadType(f'intent.head{i}', 'intent', ('on',)) for i in range(33)))


def test_service_rejects_noninteger_clock_at_construction():
    with pytest.raises(ValueError, match='Integer fabric clock'):
        TypedEncoderService(Encoder(), schema(), TimingPolicy(HASH, 200_000_000, 128, 100, 5),
                            model_sha256=HASH, clock_hz=200_000_000.0)
