import pytest
pytest.importorskip('torch')
pytest.importorskip('transformers')
from sysone.v2.general_training_v2 import exact_calls, encoder_text, value_label
from sysone.v2.general_tool_encoder import KINDS


def test_exact_calls_preserves_multiplicity_and_numeric_schema():
    tools=[dict(name='f',parameters=dict(type='object',properties={'x':{'type':'number'}},required=['x']))]
    a=dict(name='f',arguments={'x':1})
    b=dict(name='f',arguments={'x':2.0})
    assert exact_calls([b,a],[dict(name='f',arguments={'x':1.0}),b],tools)
    assert not exact_calls([a,a],[a,b],tools)
    with pytest.raises(ValueError):
        exact_calls([dict(name='f',arguments={'x':True})],[a],tools)


def test_control_ordinal_is_not_a_schema_value_source():
    tool=dict(name='f',description='choose a mode',parameters={'mode':{'type':'str','description':'Choose game or beta','default':'game'}})
    text, start=encoder_text(tool,'mode',slot=0)
    assert text.index('Call 1') < start < text.index('game')
    assert 'Default:' in text
    class Encoding(dict):
        def sequence_ids(self):return [0,0,1]
    enc=Encoding(offset_mapping=[(5,6),(start,start+4),(0,1)])
    assert value_label(1,'x',text,start,enc)[0]==KINDS.index('unrepresentable')
