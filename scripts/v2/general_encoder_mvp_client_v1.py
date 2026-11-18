"""Candidate Linux general-call ingress; R5 runs PL and computes every logit.

No deployment/automatic model loading. --reference is explicitly CPU-only.
"""
import argparse
import hashlib
import json
import mmap
import os
from pathlib import Path
import struct
import sys
import time
import numpy as np
from tokenizers import Tokenizer

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.general_tools import normalize_tool,validate_calls
from sysone.v2.general_schema_annotations import adapt_tool


class EncoderBackend:
    def __init__(self,bundle,reference):
        self.bundle=bundle;self.reference=reference;self.passes=0
        self.manifest=json.loads((bundle/'integer-manifest.json').read_text(encoding='utf-8'))
        self.candidate=json.loads((bundle/'candidate.json').read_text(encoding='utf-8'));self.layout=self.candidate['layout']
        self.scales=[]
        self.image=(bundle/'candidate.img').read_bytes()
        if hashlib.sha256(self.image).hexdigest()!=self.candidate['image_sha256']:raise RuntimeError('candidate image changed')
        for head in self.manifest['heads']:
            offset=head['scales']-self.manifest['base']
            self.scales.append(np.frombuffer(self.image,dtype='<f4',count=head['classes'],offset=offset).astype(np.float64))
        if reference:
            from sysone.v2.ddr_image import ImageMachine
            self.machine=ImageMachine(self.image)
        else:
            if os.name!='posix' or os.geteuid()!=0:raise RuntimeError('hardware mode requires root on target Linux')
            from sysone.v2.kr260_runtime import discover_memory,check_runtime
            from sysone.v2.kr260_link import Kr260Link
            region=discover_memory();check_runtime(0xa0000000,region)
            box=int(self.layout['mailbox'],16)
            if not region[0]<=box or box+0x80000>sum(region):raise RuntimeError('mailbox outside reserved region')
            link=Kr260Link(memory=region)
            try:link.verify_loaded_image(self.manifest['base'],self.image)
            finally:link.close()
            self.control=Path('/sys/class/misc/sysone_r5_smoke')
            if not self.control.exists():raise RuntimeError('matching candidate R5 module not loaded')

    def predict(self,ids,types):
        if not 1<=len(ids)<=128 or len(types)!=len(ids):raise ValueError('128-token hardware profile')
        if any(not 0<=i<30522 for i in ids) or any(t not in [0,1] for t in types):raise ValueError('token/type profile')
        banked=np.asarray(ids,dtype=np.int64)+np.asarray(types,dtype=np.int64)*30522
        self.passes+=1
        if self.reference:
            hidden=self.machine.hidden(banked)
            meta,ms=self.machine.head_logits(hidden,'intent.meta',np.array([0]))
            span,ss=self.machine.head_logits(hidden,'slots.span',np.arange(len(ids)))
            return meta.reshape(-1)*ms,span*ss
        return self.hardware(banked)

    def hardware(self,ids):
        header,stride=320,336;n=len(ids);jobs=1+n
        data=bytearray(header+jobs*stride)
        sequence=int(time.monotonic_ns())&0xffffffff
        struct.pack_into('<16I',data,0,0x47354931,1,sequence,1,0,n,jobs,*([0]*9))
        struct.pack_into('<'+'H'*n,data,64,*map(int,ids))
        for j in range(jobs):
            offset=header+j*stride
            struct.pack_into('<4I',data,offset,0 if j==0 else 1,1,0,0)
            struct.pack_into('<H',data,offset+16,0 if j==0 else j-1)
        previous=(self.control/'status').read_text()
        if 'image_sha256='+self.candidate['r5_elf_sha256'] not in previous:raise RuntimeError('wrong R5 firmware; no request written')
        if any(k+'=1' in previous for k in ['may_run','quarantine']):raise RuntimeError('R5 session not idle')
        fd=os.open('/dev/mem',os.O_RDWR|os.O_SYNC)
        def command(value):(self.control/'command').write_text(value+'\n')
        with os.fdopen(fd,'rb',closefd=True) as raw:
            with mmap.mmap(raw.fileno(),0x80000,mmap.MAP_SHARED,mmap.PROT_READ|mmap.PROT_WRITE,offset=int(self.layout['mailbox'],16)) as memory:
                memory[:len(data)]=data
                command('audit');command('prepare');command('start')
                deadline=time.monotonic()+25
                while struct.unpack_from('<I',memory,12)[0] not in [3,4]:
                    if time.monotonic()>deadline:raise TimeoutError('R5 timed out; retain state for inspection')
                    time.sleep(.005)
                h=struct.unpack_from('<16I',memory)
                if h[0]!=0x47354931 or h[2]!=sequence or h[3]!=3 or h[4]:raise RuntimeError('R5 result/error identity')
                result=bytes(memory[:len(data)])
                if not (self.control/'trace').read_text().startswith('R5: INFERENCE PASS'):raise RuntimeError('R5 trace')
                command('stop')
                status=(self.control/'status').read_text()
                if any(k+'=1' in status for k in ['pinned','mapped','may_run','quarantine']):raise RuntimeError('R5 cleanup incomplete')
        values=[]
        for j in range(jobs):
            offset=header+j*stride;head,count,label,classes=struct.unpack_from('<4I',result,offset)
            expected=15 if j==0 else 2
            row=struct.unpack_from('<H',result,offset+16)[0]
            if head!=(0 if j==0 else 1) or count!=1 or classes!=expected or row!=(0 if j==0 else j-1):raise RuntimeError('head output shape')
            logits=np.array(struct.unpack_from('<'+'i'*classes,result,offset+272),dtype=np.float64)
            values.append(logits*self.scales[head])
        return values[0],np.stack(values[1:])


def infer(query,raw_tools,tok,backend,helpers):
    tools=[adapt_tool(t) for t in raw_tools]
    if len(tools)>8 or any(len(t['parameters']['properties'])>8 for t in tools):raise ValueError('MVP tool/argument profile')
    calls=[]
    def predict(tool,key=None,slot=0):
        question,lower=helpers.encoder_text(tool,key,slot);enc=tok.encode(question,query)
        meta,span=backend.predict(enc.ids,enc.type_ids)
        return enc,meta,span,question,lower
    for tool in tools:
        _,meta,*_=predict(tool);count=int(np.argmax(meta[:6]))
        if count==5:raise ValueError('call-count overflow')
        for slot in range(count):
            if len(calls)>=4:raise ValueError('total-call profile')
            arguments={}
            for key,spec in tool['parameters']['properties'].items():
                enc,meta,span,question,lower=predict(tool,key,slot)
                kind=helpers.KINDS[int(np.argmax(meta[6:15]))]
                if kind in ['omit','unrepresentable']:
                    if kind=='unrepresentable' or key in tool['parameters'].get('required',[]):raise ValueError('unrepresentable/required argument')
                    continue
                if kind=='span':
                    valid=[i for i,s in enumerate(enc.sequence_ids) if s is not None and enc.offsets[i][1]>enc.offsets[i][0] and (s==1 or enc.offsets[i][0]>=lower)]
                    if not valid:raise ValueError('no source span')
                    a=max(valid,key=lambda i:span[i,0]);ends=[i for i in valid if a<=i<a+64 and enc.sequence_ids[i]==enc.sequence_ids[a]]
                    b=max(ends,key=lambda i:span[i,1]);source=query if enc.sequence_ids[a]==1 else question
                    arguments[key]=helpers.scalar_from_span(source[enc.offsets[a][0]:enc.offsets[b][1]],spec)
                else:arguments[key]={'true':True,'false':False,'null':None,'empty_string':'','empty_array':[],'empty_object':{}}[kind]
            calls.append(dict(name=tool['name'],arguments=arguments))
    validate_calls(calls,tools);return calls


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--bundle',type=Path,required=True)
    ap.add_argument('--request',type=Path,required=True);ap.add_argument('--reference',action='store_true');args=ap.parse_args()
    import importlib.util
    spec=importlib.util.spec_from_file_location('mvp_helpers',args.bundle/'runtime/helpers.py')
    helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)
    tok=Tokenizer.from_file(str(args.bundle/'runtime/tokenizer.json'));tok.no_truncation();tok.no_padding()
    request=json.loads(args.request.read_text(encoding='utf-8'))
    if not args.reference:
        import fcntl
        lock=Path('/run/lock/sysone-inference.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX)
    backend=EncoderBackend(args.bundle,args.reference)
    started=time.monotonic()
    try:
        calls=infer(request['query'],request['tools'],tok,backend,helpers)
        output=dict(outcome='proposal' if calls else 'no_calls',calls=calls)
    except (ValueError,TypeError,KeyError) as exc:output=dict(outcome='inference_failure',calls=[],error=str(exc))
    output.update(backend='CPU_image_reference' if args.reference else 'R5_controlled_FPGA_and_R5_heads',encoder_passes=backend.passes,
        elapsed_ms=(time.monotonic()-started)*1000,tools_executed=False,terminal_by_D_qualified=False)
    print(json.dumps(output,indent=2))


if __name__=='__main__':main()
