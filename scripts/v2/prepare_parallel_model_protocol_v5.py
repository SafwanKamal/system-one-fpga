"""One predeclared development protocol for parallel model improvement lanes."""
import hashlib
import json
from pathlib import Path
import random
import re

ROOT=Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    data=ROOT/'build/v2/general-tool-data-v1'
    out=ROOT/'build/v2/general-tool-parallel-protocol-v5'
    out.mkdir(parents=True,exist_ok=False)
    dev=[json.loads(line) for line in (data/'dev.jsonl').read_text(encoding='utf-8').splitlines()]
    random.Random(2026101702).shuffle(dev)
    historical=[];blocked={r['split_component'] for r in dev[:256]}
    for folder in ['general-tool-clean-training-v2','general-tool-clean-training-v3','general-tool-expanded-training-v4']:
        for filename in ['selection-cases.json','audit-cases.json']:
            for path in (ROOT/'build/v2'/folder).rglob(filename):
                rows=json.loads(path.read_text(encoding='utf-8'))
                blocked.update(r['split_component'] for r in rows)
                historical.append(dict(path=str(path.relative_to(ROOT)),sha256=sha(path),requests=len(rows)))
    selection=[r for r in dev[256:] if r['split_component'] not in blocked][:32]
    if len(selection)!=32:raise ValueError('insufficient fresh selection cases')
    audit_blocked=blocked|{r['split_component'] for r in dev[:512]}|{r['split_component'] for r in selection}
    audit=[r for r in dev[512:] if r['split_component'] not in audit_blocked][:64]
    if len(audit)!=64:raise ValueError('insufficient fresh audit cases')
    selection += [{**r,'id':r['id']+':v5-selection-deny','answers':[],
        'query':f'For this request ({i+1}), do not invoke any listed function. Return no calls.',
        'provenance':'synthetic_explicit_no_action_instruction_v5_selection'}
        for i,r in enumerate(selection[::4])]
    audit += [{**r,'id':r['id']+':v5-audit-deny','answers':[],
        'query':f'Instruction {i+1}: leave all available functions unused and produce no tool calls.',
        'provenance':'synthetic_explicit_no_action_instruction_v5_audit'}
        for i,r in enumerate(audit[::8])]
    normalize=lambda r:re.sub(r'\s+',' ',r['query'].strip().casefold())
    for key in ['id','split_component']:
        if {r[key] for r in selection}&{r[key] for r in audit}:raise ValueError('cross-split overlap '+key)
    if {normalize(r) for r in selection}&{normalize(r) for r in audit}:raise ValueError('cross-split prompt overlap')
    for rows in [selection,audit]:
        if {r['split_component'] for r in rows}&blocked:raise ValueError('historical component reuse')
    manifest=dict(stage='complete',seed=2026101702,scope='public xLAM development; not blind or external evaluation',
        selection_original=32,selection_denials=8,audit_original=64,audit_denials=8,
        historical_components_excluded=len(blocked),selection_offset=256,audit_offset=512,
        policy='predeclare candidate/gate grid; select on selection only; freeze before audit; never select using BFCL or audit',
        historical_inputs=historical,data_sha256={n:sha(data/n) for n in ['dev.jsonl','manifest.json']},
        source_sha256={str(Path(__file__).relative_to(ROOT)):sha(Path(__file__))},board_contacted=False)
    for name,rows in [('selection',selection),('audit',audit)]:
        path=out/f'{name}-cases.json';path.write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
        manifest[name+'_sha256']=sha(path)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(out=str(out),selection=len(selection),audit=len(audit),historical_components_excluded=len(blocked))))


if __name__=='__main__':main()
