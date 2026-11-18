import pytest
from sysone.v2.general_tools import normalize_tool,parse_functiongemma,validate_calls

TOOL={'name':'math.sum','description':'sum values','parameters':{'type':'dict','properties':{
    'values':{'type':'array','items':{'type':'integer'}},'round':{'type':'boolean'}},'required':['values']}}


def test_native_general_call_nested_values_and_multiple_calls():
    raw='<start_function_call>call:math.sum{round:false,values:[1,2,3]}<end_function_call><start_function_response>'
    assert parse_functiongemma(raw,[TOOL])==[{'name':'math.sum','arguments':{'round':False,'values':[1,2,3]}}]
    assert parse_functiongemma(raw.replace('round:false,values:[1,2,3]', 'round: false, values: [1, 2, 3]'),[TOOL])==parse_functiongemma(raw,[TOOL])
    with pytest.raises(ValueError):
        parse_functiongemma(raw.replace('round:false','round:1'),[TOOL])
    with pytest.raises(ValueError):
        parse_functiongemma(raw.replace('values:[1,2,3]','values:[true]'),[TOOL])
    with pytest.raises(ValueError):
        parse_functiongemma(raw.replace('round:false','round:false,round:true'),[TOOL])


def test_xlam_normalization_preserves_parameter_named_type():
    t=normalize_tool({'name':'f','parameters':{'type':{'type':'str','required':True,'description':'kind'}}})
    assert t['parameters']['required']==['type']
    validate_calls([{'name':'f','arguments':{'type':'beta'}}],[t])
    with pytest.raises(ValueError):
        validate_calls([{'name':'f','arguments':{}}],[t])


def test_malformed_call_is_not_reinterpreted_as_no_call():
    with pytest.raises(ValueError):
        parse_functiongemma('<start_function_call>call:missing{}',[TOOL])
    assert parse_functiongemma('No suitable function.<end_of_turn>',[TOOL])==[]
