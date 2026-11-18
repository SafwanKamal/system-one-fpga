import pytest
from scripts.v2.kr260.check_routed_evidence import validate

TIMING='''| Design State : Routed |
WNS(ns) TNS(ns) TNS Failing Endpoints TNS Total Endpoints WHS(ns) THS(ns) THS Failing Endpoints THS Total Endpoints WPWS(ns) TPWS(ns) TPWS Failing Endpoints TPWS Total Endpoints
------- ------- ------ ------ ------- ------ ------ ------ ------ ------ ------ ------
0.401 0.000 0 242285 0.010 0.000 0 242285 2.500 0.000 0 81690
All user specified timing constraints are met.
clk_pl_0 {0.000 4.000} 8.000 125.000
clk_pl_1 {0.000 4.000} 8.000 125.000
'''
ROUTES='''# of routable nets..... : 164277 :
# of fully routed nets..... : 164277 :
# of nets with routing errors..... : 0 :'''

def test_actual_vivado_routed_label_with_complete_counts():
    r=validate(TIMING,ROUTES,125)
    assert r['setup_slack_ns']==.401 and r['hold_slack_ns']==.010
    assert r['timing_qualified'] and not r['hardware_qualified']
    validate(TIMING.replace('Routed |','Fully Routed |'),ROUTES,125)

@pytest.mark.parametrize('old,new',[('Routed |','Fully Placed |'),('0.401','0.000'),
    ('0.401','-0.001'),('0.010','0.000'),('0.010','nan'),
    ('0 242285 0.010','1 242285 0.010'),('2.500 0.000','-0.001 0.000'),
    ('8.000 125.000','6.667 150.000'),('All user specified timing constraints are met.','')])
def test_rejects_unqualified_timing(old,new):
    with pytest.raises(ValueError):validate(TIMING.replace(old,new),ROUTES,125)

@pytest.mark.parametrize('routes',[ROUTES.replace('fully routed nets..... : 164277','fully routed nets..... : 164276'),
    ROUTES.replace('errors..... : 0','errors..... : 1'),ROUTES.replace('fully routed nets','partial nets'),''])
def test_state_label_alone_cannot_qualify_routing(routes):
    with pytest.raises(ValueError):validate(TIMING,routes,125)
