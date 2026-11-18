"""Fixed four-candidate selection, then paired official/frozen-winner audit.

No public benchmark files are opened. All failures remain in denominators.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time
import torch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.general_clean_inference import CleanInference
from sysone.v2.general_schema_annotations import adapt_records
from sysone.v2.general_tools import parse_functiongemma,validate_calls
from sysone.v2.general_call_matching import exact_calls
from sysone.v2.functiongemma_batch import generate_ids
from sysone.v2.functiongemma_profile import validate_prompt_ids
from sysone.v2.functiongemma_development import interpolate,improves
from sysone.v2.functiongemma_faithful_template import faithful_parameter_template
from sysone.v2.command_metrics import process_memory
from sysone.v2.checkpoint_io import write_checkpoint


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,default=Path('build/v2/general-tool-clean-training-v3/functiongemma'))
    ap.add_argument('--data',type=Path,default=Path('build/v2/general-tool-data-v1'))
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--protocol',type=Path,default=Path('build/v2/general-tool-parallel-protocol-v5'))
    ap.add_argument('--threads',type=int,default=2)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(args.threads)
    parent=json.loads((args.run/'run.json').read_text(encoding='utf-8'))
    selection=adapt_records(json.loads((args.protocol/'selection-cases.json').read_text(encoding='utf-8')))
    audit=adapt_records(json.loads((args.protocol/'audit-cases.json').read_text(encoding='utf-8')))
    if len(selection)!=40 or len(audit)!=72:raise ValueError('common protocol case counts differ')
    if {r['split_component'] for r in selection}&{r['split_component'] for r in audit}:
        raise ValueError('common protocol component overlap')
    def dump(name,value):(args.out/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    sources=[Path(__file__)]+[ROOT/'src/sysone/v2'/n for n in ['functiongemma_development.py','functiongemma_faithful_template.py','general_clean_inference.py','general_schema_annotations.py','general_tools.py','general_call_matching.py','functiongemma_batch.py','functiongemma_profile.py','checkpoint_io.py','command_metrics.py']]
    manifest=dict(stage='starting',family='functiongemma',parent_run=str(args.run),
        model_path=parent['arguments']['model'],candidates=[dict(name='official',alpha=0.0,renderer='original'),dict(name='blend-quarter',alpha=0.25,renderer='original'),dict(name='v3',alpha=1.0,renderer='original'),dict(name='official-faithful-parameters',alpha=0.0,renderer='faithful_parameters')],threads=args.threads,batch_size=4,
        profile=dict(context=2048,output=256,tools=8),
        policy='strictly higher complete correct; no fewer correct accepted; no worse observed accepted-error fraction; ties retain earlier candidate',
        data_sha256={n:digest(args.data/n) for n in ['dev.jsonl','train.jsonl','manifest.json']},
        protocol_path=str(args.protocol),protocol_sha256={n:digest(args.protocol/n) for n in ['selection-cases.json','audit-cases.json','manifest.json']},
        parent_checkpoint_sha256=digest(args.run/'best.pt'),
        parent_run_sha256=digest(args.run/'run.json'),
        source_sha256={str(p.relative_to(ROOT)):digest(p) for p in sources},
        selection_excludes_shuffled_prefix=256,audit_excludes_shuffled_prefix=512,
        selection_requests=40,audit_requests=72,public_benchmark_used=False,blind=False,
        training='no new optimizer updates; fixed affine interpolation of official and v3 last-two-block weights',
        execution='host_CPU_FP32_only_no_tools_or_board',paid_compute=False)
    (args.out/'sources').mkdir()
    for path in sources:(args.out/'sources'/path.name).write_bytes(path.read_bytes())
    dump('run.json',manifest);dump('selection-cases.json',selection);dump('audit-cases.json',audit)
    engine=CleanInference('functiongemma',manifest['model_path'],None)
    model,tok=engine.model,engine.tok
    original_template=(Path(manifest['model_path'])/'chat_template.jinja').read_text(encoding='utf-8')
    repaired_template=faithful_parameter_template(original_template)
    manifest.update(original_template_sha256=hashlib.sha256(original_template.encode()).hexdigest(),
        repaired_template_sha256=hashlib.sha256(repaired_template.encode()).hexdigest())
    dump('run.json',manifest)
    trained=torch.load(args.run/'best.pt',map_location='cpu',weights_only=False)['trainable_state']
    if not all(n.startswith(('model.layers.16.','model.layers.17.')) for n in trained):
        raise ValueError('unexpected adapted parameters')
    official={n:model.state_dict()[n].clone() for n in trained}
    expected={n for n,_ in model.named_parameters() if n.startswith(('model.layers.16.','model.layers.17.'))}
    if set(trained)!=expected:raise ValueError('partial checkpoint key set differs')
    def install(alpha):
        values=interpolate(official,trained,alpha)
        model.load_state_dict(values,strict=False)
    def prepare(rows,renderer):
        prepared=[]
        for row in rows:
            item=dict(id=row['id'],correct=False,valid=False,calls=[],gold_valid=True)
            try:validate_calls(row['answers'],row['tools'])
            except Exception as exc:item.update(gold_valid=False,gold_error=str(exc))
            try:
                if len(row['tools'])>8:raise ValueError('tool-count profile')
                messages=[dict(role='developer',content='You are a model that can do function calling with the following functions'),dict(role='user',content=row['query'])]
                text=tok.apply_chat_template(messages,tools=[dict(type='function',function=t) for t in row['tools']],add_generation_prompt=True,tokenize=False,chat_template=original_template if renderer=='original' else repaired_template)
                ids=tok.encode(text,add_special_tokens=False)
                validate_prompt_ids(ids,model.config.vocab_size)
                prepared.append((row,item,ids))
            except Exception as exc:
                item.update(error=type(exc).__name__+': '+str(exc),accepted=False)
                prepared.append((row,item,None))
        return sorted(prepared,key=lambda r:(len(r[2]) if r[2] else 0,r[0]['id']))
    def evaluate(rows,name,renderer='original'):
        prepared=prepare(rows,renderer);results=[];ready=[]
        for row,item,ids in prepared:
            if ids is None:results.append(item)
            else:ready.append((row,item,ids))
        with (args.out/f'{name}-requests.jsonl').open('w',encoding='utf-8') as stream:
            for item in results:stream.write(json.dumps(item)+'\n');stream.flush()
            for offset in range(0,len(ready),4):
                batch=ready[offset:offset+4]
                emitted,wall_ms=generate_ids(model,[r[2] for r in batch],engine.stops,model.config.pad_token_id)
                for (row,item,ids),tokens in zip(batch,emitted):
                    item.update(raw_output=tok.decode(tokens,skip_special_tokens=False).strip(),prompt_tokens=len(ids),output_tokens=len(tokens),batch_wall_ms=wall_ms)
                    try:
                        if tokens[-1] not in engine.stops:raise ValueError('output work cap exhausted')
                        calls=parse_functiongemma(item['raw_output'],row['tools'])
                        item.update(calls=calls,valid=True)
                        item['correct']=item['gold_valid'] and exact_calls(calls,row['answers'],row['tools'])
                    except (ValueError,TypeError,KeyError) as exc:item['error']=type(exc).__name__+': '+str(exc)
                    item['accepted']=item['valid'] and bool(item['calls'])
                    results.append(item);stream.write(json.dumps(item)+'\n');stream.flush()
                print(json.dumps(dict(evaluation=name,completed=len(results),total=len(rows))),flush=True)
        accepted=[r for r in results if r['accepted']]
        summary=dict(requests=len(results),correct=sum(r['correct'] for r in results),
            accepted=len(accepted),correct_accepted=sum(r['correct'] for r in accepted),
            wrong_accepted=sum(not r['correct'] for r in accepted),valid=sum(r['valid'] for r in results),
            gold_errors=sum(not r['gold_valid'] for r in results),errors=dict(Counter(r['error'] for r in results if 'error' in r)))
        dump(name+'-summary.json',summary);return summary
    started=time.perf_counter();history=[];best=None;selected=None
    for candidate in manifest['candidates']:
        install(candidate['alpha']);summary=evaluate(selection,'selection-'+candidate['name'],candidate['renderer'])
        chosen=best is None or improves(summary,best)
        history.append(dict(candidate=candidate,summary=summary,selected_when_seen=chosen))
        if chosen:best=summary;selected=candidate
        dump('selection-history.json',history)
    manifest.update(stage='audit',selected_candidate=selected,selected_alpha=selected['alpha'],selection_summary=best)
    selected_template=original_template if selected['renderer']=='original' else repaired_template
    (args.out/'selected-template.jinja').write_text(selected_template,encoding='utf-8')
    manifest['selected_template_sha256']=hashlib.sha256(selected_template.encode()).hexdigest()
    dump('run.json',manifest)
    install(selected['alpha'])
    selected_state={n:model.state_dict()[n] for n in official}
    checkpoint_manifest={**parent,'arguments':{**parent['arguments'],'out':str(args.out)}}
    write_checkpoint(dict(trainable_state=selected_state,manifest=checkpoint_manifest,
        tag=f'dev_selected_{selected["name"]}',renderer=selected['renderer'],parent_sha256=manifest['parent_checkpoint_sha256']),args.out/'best.pt',torch.save)
    if selected['name']!='official':
        install(0.0)
        manifest['official_audit_summary']=evaluate(audit,'official-audit')
        dump('run.json',manifest)
        install(selected['alpha'])
    manifest['audit_summary']=evaluate(audit,'selected-audit',selected['renderer'])
    if selected['name']=='official':manifest['official_audit_summary']=manifest['audit_summary']
    manifest.update(stage='complete',selected_checkpoint_sha256=digest(args.out/'best.pt'),
        evaluation_seconds=time.perf_counter()-started,memory_at_end=process_memory())
    dump('run.json',manifest);print(json.dumps(manifest),flush=True)


if __name__=='__main__':main()
