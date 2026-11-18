from sysone.v2.general_encoder_decode_v5 import decode_argument
from sysone.v2.general_tool_encoder import KINDS

def test_joint_numeric_span_skips_invalid_start():
    scores=[-10.]*len(KINDS);scores[KINDS.index('span')]=10
    spans=[[10,0],[9,9],[0,10]]
    args=(scores,spans,[(0,3),(4,5),(6,9)],[1,1,1],0,'','abc 2 xyz',{'type':'integer'},True)
    assert decode_argument(*args)==(True,2)

def test_kind_mask_and_enum():
    scores=[-10.]*len(KINDS);scores[KINDS.index('true')]=11;scores[KINDS.index('span')]=10
    assert decode_argument(scores,[[1,1]],[(0,3)],[1],0,'','red',{'type':'string','enum':['red']},True)==(True,'red')

def test_unrepresentable_stays_failure():
    import pytest
    scores=[0.]*len(KINDS);scores[-1]=10
    with pytest.raises(ValueError,match='unrepresentable'):
        decode_argument(scores,[],[],[],0,'','',{'type':'string'},True)
