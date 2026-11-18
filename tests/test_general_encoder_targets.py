import pytest
pytest.importorskip('torch')
pytest.importorskip('transformers')
from sysone.v2.general_encoder_targets import checked_span_label
from sysone.v2.general_tool_encoder import KINDS


class Encoding(dict):
    def sequence_ids(self):return self['sequences']


def test_case_rewrite_is_not_a_copy_target_but_exact_schema_default_is():
    enc=Encoding(offset_mapping=[(0,4),(0,4)],sequences=[0,1])
    spec={'type':'string'}
    assert checked_span_label('visa',spec,'Visa','xxxx',0,enc)[0]==KINDS.index('unrepresentable')
    assert checked_span_label('visa',spec,'Visa','visa',0,enc)==(KINDS.index('span'),0,0)
    assert checked_span_label('visa',spec,'Visa','visa',4,enc)[0]==KINDS.index('unrepresentable')


def test_numeric_span_round_trip_requires_declared_type():
    enc=Encoding(offset_mapping=[(0,3)],sequences=[1])
    assert checked_span_label(1.0,{'type':'number'},'1.0','',0,enc)[0]==KINDS.index('span')
    assert checked_span_label(1,{'type':'integer'},'1.0','',0,enc)[0]==KINDS.index('unrepresentable')
