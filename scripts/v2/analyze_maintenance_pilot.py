"""Independently rescore completed pilot attempts and explain token overhead."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
import tokenizers  # Load host extension before the deployed Linux runtime path is added.

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.maintenance.dataset import public_input, prompt, score
from sysone.v2.maintenance.schema import parse
from sysone.v2.maintenance.baselines import flatten
from sysone.v2.v8_benchmark import chat
from sysone.v2.qwen_tokenizer_v1 import Vocabulary


def read(path):return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=Path,required=True);a=ap.parse_args()
    cases=read(a.work/'audit.jsonl');by_id={c['id']:c for c in cases}
    analysis={}
    for backend in ('rules','tfidf','minilm','qwen'):
        folder=a.work/backend
        rows=read(folder/'audit-predictions.jsonl')
        if [r['id'] for r in rows]!=[c['id'] for c in cases]:raise RuntimeError('Missing/duplicate/reordered attempts')
        groups=defaultdict(list);errors=defaultdict(int);field_errors=defaultdict(int)
        json_values=0;markdown_wrapped=0
        for row in rows:
            case=by_id[row['id']]
            try:
                ast=parse(row['raw_output'],case['catalog']);expected=score(case,ast)
                valid=True;correct=expected['correct'];accepted=expected['accepted']
            except (ValueError,TypeError,KeyError,IndexError):
                valid=False;correct=False;accepted=False
            if (valid,correct,accepted)!=(row['valid'],row['correct'],row['accepted']):
                raise RuntimeError('Stored verdict does not independently reproduce: '+row['id'])
            signature=json.dumps(public_input(case),sort_keys=True)
            groups[signature].append(row)
            if not correct:errors['invalid' if not valid else ('wrong_plan' if accepted else 'wrong_terminal')]+=1
            markdown_wrapped+=row['raw_output'].lstrip().startswith('```')
            try:json.loads(row['raw_output']);json_values+=1
            except ValueError:pass
            if 'predicted_fields' in row:
                expected_fields=flatten(case['gold'],case['catalog'])
                for key,value in expected_fields.items():
                    if value!='_' and row['predicted_fields'].get(key)!=value:field_errors[key]+=1
        unique=[rs[0] for rs in groups.values()]
        analysis[backend]=dict(unique_inputs=len(unique),unique_correct=sum(r['correct'] for r in unique),
            repeated_input_groups=sum(len(rs)>1 for rs in groups.values()),
            repeated_input_output_disagreements=sum(len({r['raw_output'] for r in rs})>1 for rs in groups.values()),
            errors=dict(errors),active_target_field_errors=dict(field_errors),
            well_formed_json_values=json_values,markdown_wrapped_outputs=markdown_wrapped,
            all_verdicts_reproduced=True)
    vocab=Vocabulary(ROOT/'build/v2/qwen-fpga-decoder-v8/deployment')
    components=[]
    try:
        for case in cases:
            user=json.dumps(public_input(case),separators=(',',':'))
            # A hypothetical learned-schema contract is NOT an evaluated prompt/model.
            minimal=chat('Return one maintenance-v1 JSON-array record using your trained schema.',user)
            full=len(vocab.encode_text(prompt(case)))
            empty=len(vocab.encode_text(chat('',user)))
            learned=len(vocab.encode_text(minimal))
            components.append(dict(id=case['id'],full_input=full,framing_and_public_input=empty,
                hypothetical_learned_schema_input=learned,
                hypothetical_reserve96_fits=learned+96<=256))
    finally:vocab.close()
    result=dict(baselines=analysis,token_components=dict(
        full_input_range=[min(r['full_input'] for r in components),max(r['full_input'] for r in components)],
        public_input_and_framing_range=[min(r['framing_and_public_input'] for r in components),max(r['framing_and_public_input'] for r in components)],
        hypothetical_learned_schema_input_range=[min(r['hypothetical_learned_schema_input'] for r in components),max(r['hypothetical_learned_schema_input'] for r in components)],
        hypothetical_learned_schema_reserve96_eligible=sum(r['hypothetical_reserve96_fits'] for r in components),
        hypothetical_requires_task_training=True,hypothetical_inference_run=False),
        development_only=True,board_access=False,energy_measured=False)
    (a.work/'independent-analysis.json').write_text(json.dumps(result,indent=2)+'\n')
    (a.work/'token-budget-components.json').write_text(json.dumps(components,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
