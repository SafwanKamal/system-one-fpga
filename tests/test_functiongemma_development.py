import pytest
import torch
from sysone.v2.functiongemma_development import interpolate, improves


def test_interpolation_endpoints_exact_and_declared_blend():
    left={'a':torch.tensor([1.0,1e8,-1e-6])}
    right={'a':torch.tensor([2.0,1e-8,1e6])}
    assert torch.equal(interpolate(left,right,0)['a'],left['a'])
    assert torch.equal(interpolate(left,right,1)['a'],right['a'])
    assert torch.equal(interpolate(left,right,.25)['a'],left['a']+.25*(right['a']-left['a']))
    with pytest.raises(ValueError):interpolate(left,right,.5)
    with pytest.raises(ValueError):interpolate(left,{'a':torch.tensor([float('nan')])},.25)


def test_selection_requires_precision_and_correct_accepted_non_regression():
    base=dict(correct=10,accepted=10,correct_accepted=8,wrong_accepted=2)
    assert improves(dict(correct=11,accepted=12,correct_accepted=10,wrong_accepted=2),base)
    assert not improves(dict(correct=11,accepted=15,correct_accepted=11,wrong_accepted=4),base)
    assert not improves(dict(correct=10,accepted=8,correct_accepted=8,wrong_accepted=0),base)
    assert not improves(dict(correct=11,accepted=8,correct_accepted=7,wrong_accepted=1),base)
