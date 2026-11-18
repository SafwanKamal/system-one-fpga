import struct
import pytest
from sysone.v2.typed200_mvp import assess_mvp, R5_NOMINAL_HZ
from test_typed200_timed import fixture
from test_typed200_trace import change


def capture():
    trace, pmu, expected = fixture()
    trace = change(trace, 24, R5_NOMINAL_HZ)
    pmu = change(pmu, 24, R5_NOMINAL_HZ)
    final = change(trace[336:720], 20, 2)
    boot = struct.pack('<IIQ12I', 0x4d565031, 1, expected.session, R5_NOMINAL_HZ, *([0]*11))
    return [trace, pmu, final, boot, struct.pack('<3I', 0, 20, 1), bytes(4), expected]


def test_parked_candidate_gate_preserves_existing_typed_checks():
    r = assess_mvp(*capture())
    assert r['mvp_parked_consistency_passed']
    for key in ('continuous_hardware_ownership_verified', 'target_execution_verified',
                'frequency_verified', 'wcet_certified', 'successful_inference_guaranteed'):
        assert r[key] is False


@pytest.mark.parametrize('index,offset,value', [
    (2, 20, 1), (2, 376, 1), (2, 360, 99), (2, 16, 0),
    (3, 0, 0), (3, 4, 2), (3, 8, 99), (3, 16, 500000000),
    *[(3, p, 1) for p in range(20, 64, 4)],
    (4, 0, 1), (4, 4, 0), (4, 4, 1), (4, 4, 0xffffffff), (4, 8, 0), (4, 8, 2),
    (5, 0, 1), (1, 12, 1), (1, 24, 500000000),
])
def test_fault_unparked_foreign_config_and_changed_results_are_rejected(index, offset, value):
    args = capture();args[index] = change(args[index], offset, value)
    with pytest.raises(ValueError):
        assess_mvp(*args)


@pytest.mark.parametrize('index', range(6))
def test_truncated_snapshot_rejected(index):
    args = capture();args[index] = args[index][:-1]
    with pytest.raises(ValueError):
        assess_mvp(*args)
