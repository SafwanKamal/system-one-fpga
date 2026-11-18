"""Reserve a fresh audit before the predeclared encoder head refinement runs."""
import hashlib
import json
from pathlib import Path
import random

ROOT=Path(__file__).resolve().parents[2]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    data=ROOT/'build/v2/general-tool-data-v1'
    protocol=ROOT/'build/v2/general-tool-parallel-protocol-v5'
    out=ROOT/'build/v2/general-tool-head-audit-v6';out.mkdir(parents=True,exist_ok=False)
    dev=[json.loads(line) for line in (data/'dev.jsonl').read_text(encoding='utf-8').splitlines()]
    random.Random(2026101702).shuffle(dev)
    blocked={r['split_component'] for r in dev[:768]};inputs=[]
    for folder in ['general-tool-clean-training-v2','general-tool-clean-training-v3',
        'general-tool-expanded-training-v4','general-tool-parallel-protocol-v5']:
        for filename in ['selection-cases.json','audit-cases.json']:
            for path in (ROOT/'build/v2'/folder).rglob(filename):
                rows=json.loads(path.read_text(encoding='utf-8'))
                blocked.update(r['split_component'] for r in rows)
                inputs.append(dict(path=str(path.relative_to(ROOT)),sha256=sha(path)))
    audit=[r for r in dev[768:] if r['split_component'] not in blocked][:64]
    if len(audit)!=64:raise ValueError('insufficient unseen audit components')
    audit += [{**r,'id':r['id']+':v6-head-deny','answers':[],
        'query':f'Case {i+1}: no function should run. Leave the tool call list empty.',
        'provenance':'synthetic_explicit_no_action_instruction_v6_head_audit'}
        for i,r in enumerate(audit[::8])]
    assert not ({r['split_component'] for r in audit}&blocked)
    path=out/'audit-cases.json';path.write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8')
    manifest=dict(stage='complete',scope='fresh public development audit; not blind',requests=72,
        original=64,synthetic_denials=8,offset=768,blocked_components=len(blocked),
        selection_protocol=str(protocol.relative_to(ROOT)),selection_sha256=sha(protocol/'selection-cases.json'),
        audit_sha256=sha(path),historical_inputs=inputs,data_sha256={'dev.jsonl':sha(data/'dev.jsonl')},
        source_sha256={str(Path(__file__).relative_to(ROOT)):sha(Path(__file__))},
        policy='freeze head epoch on reused v5 selection before opening audit; no audit tuning')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(out=str(out),requests=72,blocked_components=len(blocked))))


if __name__=='__main__':main()
