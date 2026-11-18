from pathlib import Path
import pytest
from jinja2.sandbox import ImmutableSandboxedEnvironment
from sysone.v2.functiongemma_faithful_template import faithful_template,faithful_parameter_template
from sysone.v2.general_tools import parse_functiongemma


def parent_template():
    path=Path.home()/'.cache/huggingface/hub/models--google--functiongemma-270m-it/snapshots/39eccb091651513a5dfb56892d3714c1b5b8276c/chat_template.jinja'
    if not path.exists():pytest.skip('pinned model template not cached')
    return path.read_text(encoding='utf-8')


def test_parent_template_hash_guard():
    with pytest.raises(ValueError,match='unqualified'):faithful_template('changed template')


def test_reserved_names_survive_and_null_target_roundtrips():
    text=faithful_template(parent_template())
    template=ImmutableSandboxedEnvironment(trim_blocks=True,lstrip_blocks=True).from_string(text)
    names=['type','description','properties','required','nullable']
    properties={name:dict(type='string',description='ARGUMENT_'+name) for name in names}
    properties['payload']=dict(type='object',description='nested',properties={'type':dict(type='string',description='NESTED_TYPE')})
    properties['empty_object']=dict(type='object',description='unconstrained')
    properties['nothing']=dict(type='null',description='NULL_ARGUMENT')
    tools=[dict(name='fixture',description='test fixture',parameters=dict(type='object',properties=properties,required=names))]
    wrapped=[dict(type='function',function=t) for t in tools]
    messages=[dict(role='user',content='Use the fixture')]
    prompt=template.render(messages=messages,tools=wrapped,bos_token='<bos>',add_generation_prompt=True)
    for name in names:assert 'ARGUMENT_'+name in prompt
    assert 'NESTED_TYPE' in prompt
    arguments={name:'value' for name in names}
    arguments.update(payload={'type':'child'},empty_object={},nothing=None)
    call=dict(name='fixture',arguments=arguments)
    response=dict(role='assistant',tool_calls=[dict(type='function',function=call)])
    full=template.render(messages=messages+[response],tools=wrapped,bos_token='<bos>',add_generation_prompt=False)
    assert full.startswith(prompt)
    assert parse_functiongemma(full[len(prompt):],tools)==[call]


def test_parameter_only_fix_preserves_unaffected_bytes_and_metadata():
    parent=parent_template();fixed=faithful_parameter_template(parent)
    env=ImmutableSandboxedEnvironment(trim_blocks=True,lstrip_blocks=True)
    original=env.from_string(parent);candidate=env.from_string(fixed)
    tools=[dict(type='function',function=dict(name='fixture',description='description metadata',
        parameters=dict(type='object',properties={
            'value':dict(type='integer',description='number'),
            'outer':dict(type='object',description='nested',properties={'child':dict(type='string',description='child')}),
            'free':dict(type='object',description='free object',required=[])
        },required=['value']))) ]
    values=dict(messages=[dict(role='user',content='fixture')],tools=tools,bos_token='<bos>',add_generation_prompt=True)
    assert original.render(**values)==candidate.render(**values)
    # All five reserved names are real properties at both levels.
    names=['type','description','properties','required','nullable']
    props=tools[0]['function']['parameters']['properties']
    props.update({n:dict(type='string',description='TOP_'+n) for n in names})
    props['outer']['properties'].update({n:dict(type='string',description='INNER_'+n) for n in names})
    rendered=candidate.render(**values)
    for n in names:
        assert 'TOP_'+n in rendered and 'INNER_'+n in rendered
    # This candidate leaves argument/stop serialization untouched.
    assert fixed[fixed.index('{% macro format_argument'):]==parent[parent.index('{% macro format_argument'):]
