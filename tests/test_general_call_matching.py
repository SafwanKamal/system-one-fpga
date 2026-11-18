import pytest
from sysone.v2.general_call_matching import exact_calls


def test_numeric_equivalence_does_not_round_large_integers():
    tools=[dict(name='f',parameters={'x':{'type':'number'}})]
    def call(x):return [dict(name='f',arguments={'x':x})]
    assert exact_calls(call(1),call(1.0),tools)
    assert exact_calls(call(-0.0),call(0),tools)
    assert not exact_calls(call(2**53+1),call(float(2**53)),tools)
    assert not exact_calls(call(2**53+1),call(2**53),tools)
    with pytest.raises(ValueError):exact_calls(call(True),call(1),tools)
