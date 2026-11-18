import pytest
pytest.importorskip('torch')
pytest.importorskip('transformers')
from scripts.v2.run_functiongemma_command_pilot import parse_call
from sysone.v2.command_codec import encode


def test_official_tool_syntax_roundtrips_and_does_not_ignore_extra_calls():
    gold={'outcome':'Accepted','actions':[{'api':'set_speed','asset':'M2','args':{'rpm':1500}}],'condition':None}
    fields=encode(gold)
    payload=','.join(k+':<escape>'+v+'<escape>' for k,v in sorted(fields.items()))
    raw='<start_function_call>call:publish_command{'+payload+'}<end_function_call><start_function_response>'
    assert parse_call(raw)==gold
    for bad in [raw+raw, raw[:-10], raw.replace('rpm','RPM'), raw.replace('asset0:', 'api0:')]:
        if bad==raw:
            continue
        with pytest.raises(ValueError):
            parse_call(bad)
