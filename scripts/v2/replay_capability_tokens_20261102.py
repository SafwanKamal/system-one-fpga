"""Restore saved control tokens with pinned tokenizer; do not resample answers."""
import json
from pathlib import Path
import shutil
import time
import argparse
import capability_comparison_20261102 as r

WORK=r.ROOT/'build/v2/model-capability-20261102-r3'
r.WORK=WORK
r.SERVER=r.ROOT/'build/v2/generation/windows/llama-server.exe'
r.GPU_LAYERS=0
r.PORT=18193

def score(case,row,second=False):
    row.setdefault('score_before_token_replay',{k:row.get(k) for k in ['valid','correct','accepted','error','predicted']})
    for key in ['error','predicted','exact','behavioral_match']:
        row.pop(key,None)
    row.update(valid=False,correct=False,accepted=False)
    if row['status']=='context_rejection':return
    text=row['decoded_output']
    if row.get('reasoning_prefix_in_prompt'):text='<think>'+text
    try:
        if case['domain']=='maintenance':
            if row['route']=='native':
                calls=r.parse_calls(text,[r.SUBMIT],allow_text_no_calls=row['route']=='native')
                if len(calls)!=1 or calls[0]['name']!='submit_maintenance_plan' or set(calls[0]['arguments'])!={'plan_json'}:raise ValueError('Expected one maintenance submission')
                payload=calls[0]['arguments']['plan_json']
            else:payload=r.strip_format(text)
            predicted=r.maintenance_parse(payload,case['catalog'])
            row.update(valid=True,predicted=predicted,**r.maintenance_score(case,predicted))
        else:
            try:r.parse_calls(text,case['tools']);row['structured_tool_envelope']=True
            except (ValueError,TypeError,SyntaxError):row['structured_tool_envelope']=False
            calls=r.parse_calls(text,case['tools'],allow_text_no_calls=row['route']=='native')
            row.update(valid=True,predicted=calls,accepted=bool(calls))
            if case['domain']=='general':
                check=r.CHECKER.score(case,calls,case['gold']);row.update(correct=bool(check['valid']),checker=check)
            else:
                gold=case['followup']['gold'] if second else case['gold']
                row['correct']=sorted(json.dumps(c,sort_keys=True) for c in calls)==sorted(json.dumps(c,sort_keys=True) for c in gold)
    except (ValueError,TypeError,KeyError,IndexError,SyntaxError) as exc:row['error']=type(exc).__name__+': '+str(exc)
    if row.get('truncated'):row['correct']=False

def main():
    r.CHECKER=r.BFCLPythonChecker(r.ROOT/'build/v2/general-tool-data-v1/bfcl-python-checker')
    cases={c['id']:c for name in ['development.jsonl','evaluation.jsonl'] for c in r.rows(WORK/name)}
    receipt=[];rerun=[]
    for item in r.rows_json(WORK/'models.json'):
        key=item['key'];folder=WORK/'runs'/key
        done=folder/'token-replay-complete.json'
        if done.exists() and r.rows_json(done).get('processing_version')=='native-message-v2':
            receipt.append(r.rows_json(done));continue
        archive=WORK/'token-replay-original'/key
        if not archive.exists():shutil.copytree(folder,archive)
        for domain in ['maintenance','general','episode']:
            path=folder/f'screen-{domain}.jsonl'
            if not path.exists() and (archive/path.name).exists():shutil.copyfile(archive/path.name,path)
        changed=[];special_count=0;episode_history_change=False
        with r.Server(item,WORK/'token-replay-servers'/key,parallel=1,context=128,warmup=False):
            names=[f'dev-{d}-{route}.jsonl' for d in ['maintenance','general'] for route in ['direct','native']]+[f'screen-{d}.jsonl' for d in ['maintenance','general','episode']]
            for name in names:
                path=folder/name
                if not path.exists():continue
                data=r.rows(path)
                for row in data:
                    old=row['correct']
                    if row['status']=='generated':
                        row['decoded_output']=r.decode_generated(row['response'])
                        row['postprocess_source_sha256']=r.EXECUTED_SOURCE_SHA
                        special_count+=row['decoded_output']!=row['raw']
                        if row['domain']=='episode' and row['decoded_output']!=row['raw']:episode_history_change=True
                    score(cases[row['id']],row)
                    if row.get('second_turn'):
                        sub=row['second_turn']
                        if sub['status']=='generated':sub['decoded_output']=r.decode_generated(sub['response'])
                        score(cases[row['id']],sub,True)
                        row['first_turn_correct']=row['correct'];row['correct']=row['correct'] and sub['correct']
                    if old!=row['correct']:changed.append(dict(file=path.name,id=row['id'],before=old,after=row['correct']))
                r.write_rows(path,data)
        routes=r.rows_json(folder/'routes.json');original=r.rows_json(archive/'routes.json');domains=[]
        for domain in ['maintenance','general']:
            scores={route:sum(x['correct'] for x in r.rows(folder/f'dev-{domain}-{route}.jsonl')) for route in ['direct','native']}
            routes[domain]='native' if scores['native']>scores['direct'] else 'direct';routes[domain+'_scores']=scores
            if routes[domain]!=original[domain]:domains += [domain]+(['episode'] if domain=='general' else [])
        if episode_history_change:domains.append('episode')
        r.dump(folder/'routes.json',routes)
        domains=sorted(set(domains))
        if domains:
            for domain in domains:
                path=folder/f'screen-{domain}.jsonl'
                if path.exists():path.rename(path.with_name(path.stem+'.before-token-replay-'+str(time.time_ns())+'.jsonl'))
            flag=folder/'screen-complete.json'
            if flag.exists():flag.rename(folder/('screen-complete.before-token-replay-'+str(time.time_ns())+'.json'))
            rerun.append(key)
        else:
            result=r.rows_json(folder/'screen-complete.json') if (folder/'screen-complete.json').exists() else r.rows_json(archive/'screen-complete.json')
            data=sum([r.rows(folder/f'screen-{d}.jsonl') for d in ['maintenance','general','episode']],[])
            result.update(summary=r.summarize(data),postprocessing='Control-token replay; original scoring retained under token-replay-original.')
            r.dump(folder/'screen-complete.json',result)
        info=dict(model=key,processing_version='native-message-v2',changed_correctness=changed,decoded_control_frames=special_count,rerun_domains=domains,
            original_routes=original,corrected_routes=routes,raw_token_ids_preserved=True,new_model_inferences_in_this_step=0)
        r.dump(done,info);receipt.append(info)
        print(json.dumps(dict(model=key,changed=len(changed),control_frames=special_count,rerun_domains=domains)),flush=True)
    r.dump(WORK/'token-replay-summary.json',dict(models=receipt,rerun_models=rerun,source_sha256=r.digest(Path(__file__)),
        source_evidence='Pinned server /detokenize uses common_token_to_piece(special=true); LFM published example permits assistant commentary outside Pythonic call delimiters.'))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path)
    args=parser.parse_args()
    if args.work:WORK=args.work.resolve();r.WORK=WORK
    main()
