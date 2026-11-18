"""Train-only official Jinja serialization audit; no model inference or board access."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from jinja2.sandbox import ImmutableSandboxedEnvironment

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.general_schema_annotations import adapt_records
from sysone.v2.general_tools import normalize_tool,validate_calls,parse_functiongemma
from sysone.v2.general_call_matching import exact_calls


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,default=Path('build/v2/general-tool-clean-training-v3/functiongemma'))
    ap.add_argument('--out',type=Path,default=Path('build/v2/functiongemma-template-audit-v5'))
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((args.run/'run.json').read_text(encoding='utf-8'))
    parent=Path(manifest['arguments']['model']);template_path=parent/'chat_template.jinja'
    text=template_path.read_text(encoding='utf-8')
    config=json.loads((parent/'tokenizer_config.json').read_text(encoding='utf-8'))
    env=ImmutableSandboxedEnvironment(trim_blocks=True,lstrip_blocks=True)
    template=env.from_string(text)
    rows=adapt_records(json.loads((args.run/'training-cases.json').read_text(encoding='utf-8')))
    records=[]
    reserved={'description','type','properties','required','nullable'}
    for row in rows:
        item=dict(id=row['id'],reference_valid=False,target_roundtrip=False,
            top_level_property_names_skipped_by_template=[dict(tool=t['name'],keys=sorted(reserved&set(normalize_tool(t)['parameters']['properties']))) for t in row['tools'] if reserved&set(normalize_tool(t)['parameters']['properties'])])
        try:
            validate_calls(row['answers'],row['tools']);item['reference_valid']=True
            messages=[dict(role='developer',content='You are a model that can do function calling with the following functions'),dict(role='user',content=row['query'])]
            tools=[dict(type='function',function=normalize_tool(t)) for t in row['tools']]
            prefix=template.render(messages=messages,tools=tools,add_generation_prompt=True,bos_token=config['bos_token'])
            response=dict(role='assistant',tool_calls=[dict(type='function',function=a) for a in row['answers']]) if row['answers'] else dict(role='assistant',content='No suitable function.')
            full=template.render(messages=messages+[response],tools=tools,add_generation_prompt=False,bos_token=config['bos_token'])
            if not full.startswith(prefix):raise ValueError('template prefix mismatch')
            target=full[len(prefix):]
            parsed=parse_functiongemma(target,row['tools'])
            item['target_roundtrip']=exact_calls(parsed,row['answers'],row['tools'])
            if not item['target_roundtrip']:item['error']='target roundtrip differs'
        except (ValueError,TypeError,KeyError) as exc:item['error']=type(exc).__name__+': '+str(exc)
        records.append(item)
    result=dict(stage='complete',scope='existing v3 training cases only; no new development or external evaluation read',
        requests=len(rows),reference_valid=sum(r['reference_valid'] for r in records),
        valid_reference_target_roundtrip=sum(r['target_roundtrip'] for r in records),
        valid_reference_target_failures=[r['id'] for r in records if r['reference_valid'] and not r['target_roundtrip']],
        records_with_skipped_top_parameters=sum(bool(r['top_level_property_names_skipped_by_template']) for r in records),
        errors=dict(Counter(r['error'] for r in records if 'error' in r)),
        source_sha256={str(Path(__file__).relative_to(ROOT)):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        template_path=str(template_path),template_sha256=hashlib.sha256(template_path.read_bytes()).hexdigest(),
        training_cases_sha256=hashlib.sha256((args.run/'training-cases.json').read_bytes()).hexdigest(),records=records)
    (args.out/'audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='records'}))


if __name__=='__main__':main()
