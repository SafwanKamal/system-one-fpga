import pytest
from sysone.v2.timing_policy import TimingPolicy

def policy(): return TimingPolicy('a'*64,125000000,128,12500000,150)

def test_admission_requires_matched_model_clock_and_input_bound():
    p=policy();p.admit('a'*64,125000000,128)
    for model,clock,n in [('b'*64,125000000,128),('a'*64,300000000,128),('a'*64,125000000,129),('a'*64,125000000,0)]:
        with pytest.raises(ValueError): p.admit(model,clock,n)

def test_budget_boundary_and_counter_wrap_do_not_claim_guarantee():
    p=policy()
    assert p.assess(12500000,150)['board_budget_met']
    assert not p.assess(12500001,151)['board_budget_met']
    assert not p.assess(1,p.counter_wrap_ms+1)['board_budget_met']
    assert not p.assess(1,1)['hard_timing_guarantee']
    assert 'shared DDR service' in p.metadata()['unbounded_components']

@pytest.mark.parametrize('cycles,host',[(1<<32,1),(-1,1),(1,float('nan')),(1,-1)])
def test_rejects_invalid_measurement(cycles,host):
    with pytest.raises(ValueError): policy().assess(cycles,host)

@pytest.mark.parametrize('cycles,host',[(True,1),(1.5,1),(1,float('inf')),(1,True),(1,'1'),(1,None)])
def test_rejects_nonfinite_and_non_numeric_measurements(cycles,host):
    with pytest.raises(ValueError): policy().assess(cycles,host)

@pytest.mark.parametrize('tokens',[True,1.5,'12',None])
def test_rejects_non_integer_admission(tokens):
    with pytest.raises(ValueError): policy().admit('a'*64,125000000,tokens)

def test_accepts_legacy_integral_float_clock():
    policy().admit('a'*64,125000000.0,12)

@pytest.mark.parametrize('field,value',[('image_sha256',None),('clock_hz',True),
    ('max_tokens',True),('request_budget_cycles',True),('host_request_budget_ms',True),
    ('host_request_budget_ms',float('inf')),('host_request_budget_ms','150')])
def test_rejects_invalid_profile_fields(field,value):
    values=dict(image_sha256='a'*64,clock_hz=125000000,max_tokens=128,
                request_budget_cycles=12500000,host_request_budget_ms=150)
    values[field]=value
    with pytest.raises(ValueError): TimingPolicy(**values)
