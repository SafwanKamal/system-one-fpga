"""Train-only byte preservation of the isolated property-name template repair."""
import hashlib
import json
from pathlib import Path
import sys
from jinja2.sandbox import ImmutableSandboxedEnvironment
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.functiongemma_faithful_template import faithful_parameter_template
from sysone.v2.general_schema_annotations import adapt_records
from sysone.v2.general_tools import normalize_tool


def main():
    run=ROOT/'build/v2/general-tool-clean-training-v3/functiongemma'
    parent=json.loads((run/'run.json').read_text(encoding='utf-8'))
    model=Path(parent['arguments']['model'])
    original=(model/'chat_template.jinja').read_text(encoding='utf-8')
    fixed=faithful_parameter_template(original)
    env=ImmutableSandboxedEnvironment(trim_blocks=True,lstrip_blocks=True)
    templates=[env.from_string(t) for t in [original,fixed]]
    bos=json.loads((model/'tokenizer_config.json').read_text(encoding='utf-8'))['bos_token']
    cases=adapt_records(json.loads((run/'training-cases.json').read_text(encoding='utf-8')))
    names={'description','type','properties','required','nullable'}
    def affected(spec):
        if not isinstance(spec,dict):return False
        return bool(names&set(spec.get('properties',{}))) or any(affected(v) for v in spec.get('properties',{}).values()) or ('items' in spec and affected(spec['items']))
    rows=[]
    for case in cases:
        tools=[dict(type='function',function=normalize_tool(t)) for t in case['tools']]
        expected=any(affected(t['function']['parameters']) for t in tools)
        values=dict(messages=[dict(role='developer',content='You are a model that can do function calling with the following functions'),dict(role='user',content=case['query'])],tools=tools,bos_token=bos,add_generation_prompt=True)
        texts=[t.render(**values) for t in templates]
        rows.append(dict(id=case['id'],contains_reserved_property=expected,bytes_identical=texts[0]==texts[1]))
    unexpected=[r['id'] for r in rows if not r['contains_reserved_property'] and not r['bytes_identical']]
    out=ROOT/'build/v2/functiongemma-parameter-template-qualification-v5';out.mkdir(exist_ok=False)
    source=ROOT/'src/sysone/v2/functiongemma_faithful_template.py'
    result=dict(stage='complete' if not unexpected else 'failed',requests=len(rows),
        unaffected=sum(not r['contains_reserved_property'] for r in rows),
        changed=sum(not r['bytes_identical'] for r in rows),unexpected_changed=unexpected,
        original_template_sha256=hashlib.sha256(original.encode()).hexdigest(),
        repaired_template_sha256=hashlib.sha256(fixed.encode()).hexdigest(),
        scope='v3 training prompts only; no development or public benchmark input',
        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),source]},records=rows)
    (out/'qualification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (out/'parameter-template.jinja').write_text(fixed,encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='records'}))
    if unexpected:raise ValueError('unaffected prompt bytes changed')


if __name__=='__main__':main()
