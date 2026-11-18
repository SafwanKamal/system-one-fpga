"""Successor span targets verified through the inference value decoder.

Does not change the recorded v3 experiment or relax typed string equality.
"""
from collections import Counter
import json
import re
from .general_training_v2 import prepare_jobs as legacy_prepare_jobs, encoder_text
from .general_tool_encoder import KINDS, scalar_from_span
from .general_call_matching import exact_calls
from .general_schema_annotations import adapt_records


def checked_span_label(value, spec, query, question, lower, encoding):
    offsets=encoding['offset_mapping'];seqs=encoding.sequence_ids()
    forms=[value] if isinstance(value,str) else [json.dumps(value),json.dumps(value,separators=(',',':'))]
    if type(value) is float and value.is_integer():forms.append(str(int(value)))
    tools=[dict(name='value',parameters={'x':spec})]
    gold=[dict(name='value',arguments={'x':value})]
    for text,seq,start in ((query,1,0),(question,0,lower)):
        for form in forms:
            # Case changes are transformations, not exact copy spans.
            for match in re.finditer(re.escape(form),text):
                if match.start()<start:continue
                a=[i for i,(x,y) in enumerate(offsets) if seqs[i]==seq and x==match.start() and y>x]
                b=[i for i,(x,y) in enumerate(offsets) if seqs[i]==seq and y==match.end() and y>x]
                if not a or not b:continue
                try:
                    decoded=scalar_from_span(text[match.start():match.end()],spec)
                    if exact_calls([dict(name='value',arguments={'x':decoded})],gold,tools):
                        return KINDS.index('span'),a[0],b[-1]
                except (ValueError,TypeError,KeyError):pass
    return KINDS.index('unrepresentable'),0,0


def prepare_checked_jobs(rows,tok,cap):
    rows=adapt_records(rows)
    jobs,failures,_=legacy_prepare_jobs(rows,tok,cap)
    cases={r['id']:r for r in rows};corrections=[]
    for job in jobs:
        if job['task']!='argument' or KINDS[job['kind']]!='span':continue
        row=cases[job['record_id']]
        name,key,slot=job['id'][len(row['id'])+1:].rsplit(':',2)
        tool=next(t for t in row['tools'] if t['name']==name)
        gold=[a for a in row['answers'] if a['name']==name][int(slot)]['arguments'][key]
        question,lower=encoder_text(tool,key,int(slot))
        enc=tok(question,row['query'],truncation=False,return_offsets_mapping=True)
        assert enc['input_ids']==job['tokens']['input_ids']
        label=checked_span_label(gold,tool['parameters']['properties'][key],row['query'],question,lower,enc)
        if label!=(job['kind'],job['start'],job['end']):
            corrections.append(dict(id=job['id'],old=[job['kind'],job['start'],job['end']],new=list(label)))
            job.update(kind=label[0],start=label[1],end=label[2])
    kinds=Counter(KINDS[j['kind']] for j in jobs if j['task']=='argument')
    return jobs,failures,dict(kinds),corrections
