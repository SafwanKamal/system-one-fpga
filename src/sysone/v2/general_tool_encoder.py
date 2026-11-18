"""Schema-conditioned, bounded extractive encoder reference for general tools.

The explicit extractive limitation is measured on all issued requests; examples
requiring rewritten values are not removed from the evaluation denominator.
"""
import json
import re
import torch
from torch import nn
from transformers import AutoModel
from .general_tools import normalize_tool

KINDS=('omit','span','true','false','null','empty_string','empty_array','empty_object','unrepresentable')


class ToolEncoder(nn.Module):
    def __init__(self,path,max_calls_per_tool=4):
        super().__init__()
        self.encoder=AutoModel.from_pretrained(path,local_files_only=True)
        h=self.encoder.config.hidden_size
        self.count=nn.Linear(h,max_calls_per_tool+2) # 0..cap plus overflow
        self.kind=nn.Linear(h,len(KINDS))
        self.span=nn.Linear(h,2)

    def forward(self,tokens):
        hidden=self.encoder(**tokens).last_hidden_state
        return self.count(hidden[:,0]),self.kind(hidden[:,0]),self.span(hidden)


def job_text(tool,argument=None,slot=0,max_calls_per_tool=4):
    tool=normalize_tool(tool)
    params=tool['parameters']['properties']
    prefix=tool['name']+': '+tool['description']
    if argument is None:
        signatures=', '.join(k+' ('+str(v.get('type'))+')' for k,v in params.items())
        count_text='zero, one, two' if max_calls_per_tool==2 else ', '.join(str(i) for i in range(max_calls_per_tool+1))
        return 'Calls: '+count_text+' or overflow? '+prefix+' Parameters: '+signatures
    spec=params[argument]
    required='required' if argument in tool['parameters'].get('required',[]) else 'optional'
    enums=' Choices: '+json.dumps(spec['enum']) if 'enum' in spec else ''
    return (f'Call {slot+1}. '+prefix+f' Argument {argument} ({spec.get("type")}, {required}): '+spec.get('description','')+enums)


def scalar_from_span(text,spec):
    typ=spec.get('type')
    if typ=='string':
        if len(text)>=2 and text[0]==text[-1] and text[0] in ('"',"'"):
            text=text[1:-1]
        return text
    if typ=='integer':
        if not re.fullmatch(r'-?\d+',text.strip()):
            raise ValueError('span is not an integer')
        return int(text)
    if typ in ('number','float'):
        if not re.fullmatch(r'-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',text.strip()):
            raise ValueError('span is not numeric')
        return float(text)
    return json.loads(text)


def label_value(value,query,encoding):
    if value is True:
        return KINDS.index('true'),0,0
    if value is False:
        return KINDS.index('false'),0,0
    for candidate,kind in ((None,'null'),('','empty_string'),([],'empty_array'),({},'empty_object')):
        if type(value) is type(candidate) and value==candidate:
            return KINDS.index(kind),0,0
    forms=[value] if isinstance(value,str) else [json.dumps(value,separators=(',',':')),json.dumps(value)]
    if type(value) is float and value.is_integer():
        forms.append(str(int(value)))
    offsets=encoding['offset_mapping']
    sequence=encoding.sequence_ids()
    for form in forms:
        if not form:
            continue
        for match in re.finditer(re.escape(form),query,flags=re.IGNORECASE):
            starts=[i for i,(a,b) in enumerate(offsets) if sequence[i]==1 and a==match.start() and b>a]
            ends=[i for i,(a,b) in enumerate(offsets) if sequence[i]==1 and b==match.end() and b>a]
            if starts and ends:
                return KINDS.index('span'),starts[0],ends[-1]
    return KINDS.index('unrepresentable'),0,0


def training_jobs(records,tok,max_tokens=512,max_calls_per_tool=4):
    jobs=[]
    failures=[]
    kinds={}
    for row in records:
        for raw_tool in row['tools']:
            tool=normalize_tool(raw_tool)
            answers=[a for a in row['answers'] if a['name']==tool['name']]
            descriptions=[(None,0,None)]
            for slot,answer in enumerate(answers[:max_calls_per_tool]):
                for name in tool['parameters']['properties']:
                    descriptions.append((name,slot,answer['arguments'].get(name,'__OMITTED__')))
            for argument,slot,value in descriptions:
                encoding=tok(job_text(tool,argument,slot,max_calls_per_tool),row['query'],truncation=False,return_offsets_mapping=True)
                job=dict(id=f"{row['id']}:{tool['name']}:{argument}:{slot}",record_id=row['id'],task='count' if argument is None else 'argument')
                if len(encoding['input_ids'])>max_tokens:
                    failures.append({**job,'reason':'encoder_input_profile','tokens':len(encoding['input_ids'])})
                    continue
                job['tokens']={k:v for k,v in encoding.items() if k!='offset_mapping'}
                job.update(count=min(len(answers),max_calls_per_tool+1),kind=0,start=0,end=0)
                if argument is not None:
                    if value=='__OMITTED__':
                        job['kind']=KINDS.index('omit')
                    else:
                        job['kind'],job['start'],job['end']=label_value(value,row['query'],encoding)
                    kinds[KINDS[job['kind']]]=kinds.get(KINDS[job['kind']],0)+1
                jobs.append(job)
    return jobs,failures,kinds
