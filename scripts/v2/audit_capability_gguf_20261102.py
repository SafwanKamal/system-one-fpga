"""Read GGUF metadata/tensor descriptors without loading model weights."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'build/v2/model-capability-20261102'

def audit(path):
    with path.open('rb') as f:
        def number(fmt):return struct.unpack('<'+fmt,f.read(struct.calcsize('<'+fmt)))[0]
        def string():return f.read(number('Q')).decode('utf-8')
        def value(kind,keep=True):
            formats={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
            if kind in formats:return number(formats[kind])
            if kind==8:
                size=number('Q')
                if keep:return f.read(size).decode('utf-8')
                f.seek(size,1);return None
            if kind==9:
                inner,count=number('I'),number('Q')
                if inner in formats and not keep:
                    f.seek(count*struct.calcsize('<'+formats[inner]),1);return None
                result=[] if keep else None
                for _ in range(count):
                    v=value(inner,keep)
                    if keep:result.append(v)
                return result
            raise ValueError('Unknown GGUF metadata type '+str(kind))
        if f.read(4)!=b'GGUF':raise ValueError('Not GGUF')
        version=number('I')
        if version!=3:raise ValueError('Unexpected GGUF version')
        tensors,entries=number('Q'),number('Q')
        metadata={}
        for _ in range(entries):
            name,kind=string(),number('I')
            keep=not name.startswith('tokenizer.') or name in ['tokenizer.chat_template','tokenizer.ggml.add_bos_token','tokenizer.ggml.add_eos_token','tokenizer.ggml.bos_token_id','tokenizer.ggml.eos_token_id']
            val=value(kind,keep)
            if keep:metadata[name]=val
        descriptions=[]
        for _ in range(tensors):
            name=string();dims=[number('Q') for _ in range(number('I'))]
            kind,offset=number('I'),number('Q')
            count=1
            for d in dims:count*=d
            descriptions.append(dict(name=name,shape=dims,type=kind,offset=offset,parameters=count))
        alignment=metadata.get('general.alignment',32)
        start=(f.tell()+alignment-1)//alignment*alignment
        names={0:'F32',1:'F16',2:'Q4_0',3:'Q4_1',6:'Q5_0',7:'Q5_1',8:'Q8_0',10:'Q2_K',11:'Q3_K',12:'Q4_K',13:'Q5_K',14:'Q6_K',30:'BF16'}
        counts=Counter();params=Counter()
        for t in descriptions:
            key=names.get(t['type'],str(t['type']));counts[key]+=1;params[key]+=t['parameters']
        return dict(path=str(path),file_bytes=path.stat().st_size,version=version,tensors=tensors,
                    tensor_type_counts=dict(counts),parameter_counts_by_type=dict(params),
                    total_tensor_parameters=sum(params.values()),data_start=start,metadata=metadata,
                    descriptors=descriptions)

if __name__=='__main__':
    models=json.loads((WORK/'models.json').read_text())
    for model in models:
        path=Path(model['path'])
        if not path.exists():continue
        result=audit(path)
        out=WORK/'gguf-audits'/f"{model['key']}.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(dict(model=model['key'],bytes=result['file_bytes'],types=result['tensor_type_counts'],architecture=result['metadata'].get('general.architecture'))))
