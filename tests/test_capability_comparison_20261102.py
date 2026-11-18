"""Qualification of boundaries that could otherwise inflate capability scores."""
import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('capability_comparison',ROOT/'scripts/v2/capability_comparison_20261102.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def test_schema_parameter_named_type_is_not_itself_a_type_tag():
    source={'type':'dict','properties':{'type':{'type':'string'},'value':{'type':'float'}}}
    assert mod.normalize_schema(source)=={'type':'object','properties':{'type':{'type':'string'},'value':{'type':'number'}}}
    assert source['type']=='dict'

def test_bfcl_any_becomes_unrestricted_json_schema():
    assert mod.normalize_schema({'type':'any','description':'Unrestricted input'})=={'description':'Unrestricted input'}

@pytest.mark.parametrize('text',[
    '[{"name":"read_sensor","arguments":{"asset":"unit-87"}}]',
    '<tool_call>{"name":"read_sensor","arguments":{"asset":"unit-87"}}</tool_call>',
    '<|tool_call_start|>[read_sensor(asset="unit-87")]<|tool_call_end|>',
])
def test_native_formats_preserve_exact_arguments(text):
    assert mod.parse_calls(text)==[{'name':'read_sensor','arguments':{'asset':'unit-87'}}]

def test_lfm_documented_trailing_assistant_text_is_not_a_call():
    text='<|tool_call_start|>[read_sensor(asset="unit-87")]<|tool_call_end|>Checking the sensor now.'
    assert mod.parse_calls(text)==[{'name':'read_sensor','arguments':{'asset':'unit-87'}}]

def test_decoder_preserves_native_markers_and_removes_terminal_eog(monkeypatch):
    def fake(endpoint,body,timeout=240):
        assert endpoint=='/detokenize' and body['tokens']==[10,100,11]
        return {'content':'<|tool_call_start|>[read_sensor(asset="unit-87")]<|tool_call_end|>'}
    monkeypatch.setattr(mod,'post',fake)
    text=mod.decode_generated({'tokens':[10,100,11,7],'stop_type':'eos','content':'suppressed markers'})
    assert mod.parse_calls(text)[0]['name']=='read_sensor'

def test_native_plain_assistant_message_has_no_tool_calls():
    assert mod.parse_calls('No available function can perform that request.',allow_text_no_calls=True)==[]
    with pytest.raises((ValueError,SyntaxError)):
        mod.parse_calls('[{"name":',allow_text_no_calls=True)

def test_native_json_call_and_assistant_content_are_separate():
    text='Checking now. <tool_call>{"name":"read_sensor","arguments":{"asset":"unit-87"}}</tool_call> Waiting for the result.'
    assert mod.parse_calls(text,allow_text_no_calls=True)==[{'name':'read_sensor','arguments':{'asset':'unit-87'}}]

@pytest.mark.parametrize('text',[
    'I would call read_sensor(asset="unit-87")',
    '<tool_call>{"name":"read_sensor","arguments":{}}</tool_call> extra',
    '[read_sensor(asset=__import__("os").getcwd())]',
    '[read_sensor("unit-87")]',
    '<think>unfinished',
])
def test_no_semantic_repair_or_execution(text):
    with pytest.raises((ValueError,SyntaxError,TypeError)):
        mod.parse_calls(text)

def test_wrong_comparison_fails_even_when_schema_is_valid():
    case=next(c for c in mod.rows(ROOT/'build/v2/maintenance-sft-v3/conditional.jsonl') if c['gold']['predicate']['op']=='gt')
    wrong=json.loads(json.dumps(case['gold']))
    wrong['predicate']['op']='ge'
    assert not mod.maintenance_score(case,wrong)['correct']

def test_context_rejection_stays_in_denominator(monkeypatch):
    case=dict(mod.rows(ROOT/'build/v2/maintenance-sft-v3/fresh.jsonl')[0],domain='maintenance',subset='fresh')
    def fake(endpoint,body,timeout=240):
        if endpoint=='/apply-template':return {'prompt':'example'}
        if endpoint=='/tokenize':return {'tokens':list(range(1800))}
        raise AssertionError('Over-capacity request reached inference')
    monkeypatch.setattr(mod,'post',fake)
    result=mod.generate(case,'direct')
    assert result['status']=='context_rejection' and not result['correct']
    assert mod.summarize([result])['fresh']['count']==1

def test_truncated_valid_payload_does_not_pass(monkeypatch):
    case=dict(mod.rows(ROOT/'build/v2/maintenance-sft-v3/fresh.jsonl')[0],domain='maintenance',subset='fresh')
    def fake(endpoint,body,timeout=240):
        if endpoint=='/apply-template':return {'prompt':'example'}
        if endpoint=='/tokenize':return {'tokens':[1,2]}
        return {'content':mod.maintenance_encode(case['gold']),'tokens_predicted':256,'stop_type':'limit','timings':{}}
    monkeypatch.setattr(mod,'post',fake)
    result=mod.generate(case,'direct')
    assert result['valid'] and result['truncated'] and not result['correct']

def test_upstream_checker_accepts_gold_rejects_changed_argument():
    from sysone.v2.general_tool_eval import checker_self_check
    checker_self_check(ROOT/'build/v2/general-tool-data-v1/bfcl-python-checker',
        mod.rows(ROOT/'build/v2/general-tool-data-v1/external-evaluation.jsonl'),
        mod.rows_json(ROOT/'build/v2/general-tool-data-v1/bfcl-answer-registry.json'))

def test_rendered_bos_is_not_added_twice(monkeypatch):
    case=dict(mod.rows(ROOT/'build/v2/maintenance-sft-v3/fresh.jsonl')[0],domain='maintenance',subset='fresh')
    monkeypatch.setattr(mod,'ACTIVE_BOS',99)
    def fake(endpoint,body,timeout=240):
        if endpoint=='/apply-template':return {'prompt':'<BOS>example'}
        if endpoint=='/tokenize':return {'tokens':[99,99,1,2]}
        assert body['prompt']==[99,1,2]
        return {'content':mod.maintenance_encode(case['gold']),'tokens_predicted':20,'stop_type':'eos','timings':{}}
    monkeypatch.setattr(mod,'post',fake)
    result=mod.generate(case,'direct')
    assert result['removed_duplicate_bos'] and result['correct']

def test_qwen35_xml_uses_declared_argument_types_without_repair():
    text='Checking the requested condition.\n<tool_call><function=check><parameter=asset>unit-87</parameter><parameter=threshold>70</parameter></function></tool_call>'
    tools=[{'name':'check','parameters':{'properties':{'asset':{'type':'string'},'threshold':{'type':'integer'}}}}]
    assert mod.parse_calls(text,tools)==[{'name':'check','arguments':{'asset':'unit-87','threshold':70}}]
    with pytest.raises(ValueError):
        mod.parse_calls(text.replace('>70<','>seventy<'),tools)

def test_xml_plan_json_stays_a_string():
    payload='["reject","unknown_asset"]'
    text='<tool_call><function=submit_maintenance_plan><parameter=plan_json>'+payload+'</parameter></function></tool_call>'
    assert mod.parse_calls(text,[mod.SUBMIT])[0]['arguments']['plan_json']==payload

def test_xml_duplicate_arguments_rejected():
    with pytest.raises(ValueError):
        mod.parse_calls('<tool_call><function=f><parameter=a>1</parameter><parameter=a>2</parameter></function></tool_call>')

def test_reasoning_prefix_already_in_template_is_parsed_once(monkeypatch):
    case=dict(mod.rows(ROOT/'build/v2/maintenance-sft-v3/fresh.jsonl')[0],domain='maintenance',subset='fresh')
    monkeypatch.setattr(mod,'THINKING',True)
    monkeypatch.setattr(mod,'OUTPUT_BUDGET',1024)
    monkeypatch.setattr(mod,'ACTIVE_CONTEXT',4096)
    def fake(endpoint,body,timeout=240):
        if endpoint=='/apply-template':
            assert body['enable_thinking']
            return {'prompt':'assistant\n<think>\n'}
        if endpoint=='/tokenize':return {'tokens':[1,2]}
        assert body['n_predict']==1024
        return {'content':'Reasoning text.</think>\n'+mod.maintenance_encode(case['gold']),'tokens_predicted':40,'stop_type':'eos','timings':{}}
    monkeypatch.setattr(mod,'post',fake)
    result=mod.generate(case,'direct')
    assert result['reasoning_prefix_in_prompt'] and result['correct']
