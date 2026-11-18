"""Round-trip saved encoder span targets through the actual value decoder."""
import argparse
import copy
import json
from pathlib import Path
import sys
from transformers import AutoTokenizer

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.general_training_v2 import encoder_text
from sysone.v2.general_call_matching import exact_calls
from sysone.v2.general_tool_encoder import KINDS,scalar_from_span


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--jobs',type=Path)
    args=ap.parse_args()
    run=json.loads((args.run/'run.json').read_text())
    tok=AutoTokenizer.from_pretrained(run['arguments']['model'],local_files_only=True)
    cases={r['id']:r for r in json.loads((args.run/'training-cases.json').read_text())}
    jobs=json.loads((args.jobs or args.run/'training-jobs.json').read_text())
    checked=0;failures=[]
    for job in jobs:
        if job['task']!='argument' or KINDS[job['kind']]!='span':continue
        checked+=1
        row=cases[job['record_id']]
        tool_name,key,slot=job['id'][len(row['id'])+1:].rsplit(':',2)
        tool=next(t for t in row['tools'] if t['name']==tool_name)
        gold=next(a for i,a in enumerate([a for a in row['answers'] if a['name']==tool_name]) if i==int(slot))
        question,_=encoder_text(tool,key,int(slot))
        enc=tok(question,row['query'],truncation=False,return_offsets_mapping=True)
        assert enc['input_ids']==job['tokens']['input_ids']
        a,b=job['start'],job['end'];seq=enc.sequence_ids()[a]
        assert seq==enc.sequence_ids()[b]
        source=row['query'] if seq==1 else question
        text=source[enc['offset_mapping'][a][0]:enc['offset_mapping'][b][1]]
        try:
            value=scalar_from_span(text,tool['parameters']['properties'][key])
            proposal=copy.deepcopy(gold);proposal['arguments'][key]=value
            if not exact_calls([proposal],[gold],[tool]):
                failures.append(dict(id=job['id'],span_text=text,expected=gold['arguments'][key],decoded=value,reason='typed_value_differs'))
        except (ValueError,TypeError,KeyError) as exc:
            failures.append(dict(id=job['id'],span_text=text,expected=gold['arguments'][key],reason=str(exc)))
    result=dict(span_targets_checked=checked,round_trip_failures=len(failures),failures=failures,
        scope='training target audit only; no development or external predictions',training_changed=False)
    args.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='failures'}))


if __name__=='__main__':main()
