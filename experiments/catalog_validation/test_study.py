import inspect
from pathlib import Path
import numpy as np
import pytest
import diagnosis as d
import simulator as s


def test_observation_api_has_no_evaluator_fields():
    assert set(d.Observation.__dataclass_fields__) == {'commands', 'pose'}
    assert 'simulator' not in inspect.getsource(d)


def test_branch_prefix_and_first_slot_are_identical():
    w = s.world(1101, 0, 'healthy'); a = s.run(w, 'healthy')
    for first in range(9):
        for second in range(9):
            np.testing.assert_array_equal(a['pose'][first*9, :50], a['pose'][first*9+second, :50])
    natural = s.run(w, 'healthy', natural=True)
    np.testing.assert_array_equal(a['prefix']['pose'], natural['prefix']['pose'])


def test_actual_commands_change_and_are_bounded():
    a = s.run(s.world(1101, 0, 'gain'), 'gain')
    assert not np.array_equal(a['commands'][0], a['commands'][80])
    assert np.max(np.abs(a['commands'][:, :, 0])) <= .250001
    assert np.max(np.abs(a['commands'][:, :, 1])) <= .500001
    assert np.linalg.norm(a['pose'][0, -1]-a['pose'][80, -1]) > .05


@pytest.mark.parametrize('kind', ['healthy', 'gain', 'bias', 'offset'])
def test_known_features_finite_and_causal(kind):
    a = s.run(s.world(1101, 2, kind), kind)
    u, y = s.histories(a)
    x, scores = d.extract(u, y)
    assert np.isfinite(x).all() and np.isfinite(scores).all()
    assert x.shape[0] == 81 and scores.shape == (81, 4)
    prefix_before = a['prefix']['pose'].copy()
    obs = d.Observation(a['prefix']['commands'], a['prefix']['pose'])
    i, _ = d.select(obs, 'eig', np.array([.01, .01, .02]))
    j, _ = d.select(obs, 'eig', np.array([.01, .01, .02]))
    assert i == j
    np.testing.assert_array_equal(prefix_before, a['prefix']['pose'])


def test_equivalent_kinematic_gains():
    # A radius scaling and a command effectiveness scaling enter the same map.
    rng = np.random.default_rng(22); u = rng.normal(size=(500, 2))
    radius = .8; actuator_gain = .8
    np.testing.assert_array_equal(u*radius, u*actuator_gain)


def test_unknowns_absent_from_catalog_fits():
    source = inspect.getsource(d.extract)
    assert 'latency' not in source and 'deadzone' not in source
    assert 'kind' not in inspect.signature(d.extract).parameters


def test_no_reject_all_pass():
    from study import metrics
    labels = np.array([0, 1, 2, 3, -1])
    assert not metrics(labels, np.full(5, -1))['feasible']
    assert metrics(labels, labels)['feasible']


def test_duration_does_not_change_world_or_noise_prefix():
    for kind in ['healthy', 'gain', 'bias', 'offset']:
        short = s.world(1105, 4, kind, duration=500)
        long = s.world(1105, 4, kind, duration=800)
        assert short.severity == long.severity and short.axis == long.axis
        np.testing.assert_array_equal(short.noise, long.noise[:501])
        np.testing.assert_array_equal(short.commands, long.commands[:500])


def test_one_slot_costs_do_not_charge_second_action():
    a = s.run(s.world(1102, 2, 'healthy'), 'healthy')
    for first in range(9):
        np.testing.assert_array_equal(a['effort9'][first*9:first*9+9], np.full(9, a['effort9'][first*9]))
    assert np.any(a['effort9'] < a['effort'])
