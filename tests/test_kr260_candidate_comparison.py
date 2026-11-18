from copy import deepcopy

import pytest

from scripts.v2.kr260.compare_candidate import compare


def report():
    return {'complete': True, 'backend': 'kr260', 'clock_hz': 1000,
            'image_sha256': 'a'*64, 'suite_sha256': 'b'*64, 'stats': {'test': {'ok': 1, 'n': 1}},
            'verification': {'exact': 1, 'total': 1},
            'cases': [{'id': 'test:0', 'dataset': 'test', 'tokens': 1,
                       'ids_sha256': 'c'*64, 'hidden_sha256': 'd'*64,
                       'predictions': [], 'bit_exact': True,
                       'encoder_clocks': 100, 'request_clocks': 110}]}


def test_uses_each_live_clock_and_marks_observation_not_guarantee():
    a = report()
    b = deepcopy(a)
    b['clock_hz'] = 2000
    result = compare(a, b)
    assert result['observed_encoder_speedup'] == 2
    assert result['candidate']['encoder_mean_ms'] == 50
    assert result['hard_timing_guarantee'] is False


@pytest.mark.parametrize('change', [
    lambda r: r.update(complete=False),
    lambda r: r.update(image_sha256='e'*64),
    lambda r: r['cases'][0].update(hidden_sha256='e'*64),
    lambda r: r['cases'][0].update(predictions=[{'head': 'wrong'}]),
    lambda r: r['cases'][0].update(bit_exact=False),
    lambda r: r['cases'][0].update(request_clocks=99),
])
def test_rejects_unmatched_or_unverified_measurements(change):
    a = report()
    b = deepcopy(a)
    change(b)
    with pytest.raises(ValueError):
        compare(a, b)
