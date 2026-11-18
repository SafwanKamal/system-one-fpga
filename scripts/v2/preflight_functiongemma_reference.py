"""Audit the already-declared reference inputs; no model scoring or filtering."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from transformers import AutoTokenizer

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.general_schema_annotations import adapt_tool
from sysone.v2.functiongemma_profile import validate_prompt_ids


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evaluation',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    run=json.loads((args.evaluation/'run.json').read_text(encoding='utf-8'))
    model=Path(run['model_path']);config=json.loads((model/'config.json').read_text(encoding='utf-8'))
    tok=AutoTokenizer.from_pretrained(model,local_files_only=True)
    cases=json.loads((args.evaluation/'selected-cases.json').read_text(encoding='utf-8'))
    rows=[]
    for case in cases:
        tools=[dict(type='function',function=adapt_tool(t)) for t in case['tools']]
        messages=[dict(role='developer',content='You are a model that can do function calling with the following functions'),dict(role='user',content=case['query'])]
        text=tok.apply_chat_template(messages,tools=tools,add_generation_prompt=True,tokenize=False)
        ids=tok.encode(text,add_special_tokens=False)
        invalid=sorted({v for v in ids if not 0<=v<config['vocab_size']})
        status='supported'
        try:
            if len(tools)>8:raise ValueError('tool-count profile')
            validate_prompt_ids(ids,config['vocab_size'])
        except ValueError as exc:status=str(exc)
        rows.append(dict(id=case['id'],prompt_tokens=len(ids),status=status,
            invalid_model_ids=invalid,max_token_id=max(ids,default=None)))
    result=dict(scope='input preflight; no model scores, request selection or filtering',
        requests=len(rows),status_histogram=dict(Counter(r['status'] for r in rows)),
        requests_with_unsupported_ids=sum(bool(r['invalid_model_ids']) for r in rows),
        model_vocab_size=config['vocab_size'],tokenizer_extra_ids=[262144,262145],rows=rows,
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [Path(__file__),ROOT/'src/sysone/v2/functiongemma_profile.py']})
    args.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['rows','source_sha256']}))


if __name__=='__main__':main()
