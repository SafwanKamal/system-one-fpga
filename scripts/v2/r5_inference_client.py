"""Linux ingress/formatting only: R5 controls PL and computes head logits/labels."""
from pathlib import Path
import argparse,hashlib,json,mmap,os,struct,sys,time
if os.name=='posix':import fcntl
REPO=Path(os.environ.get('SYSONE_REPO','/home/ubuntu/system-one-fpga'))
sys.path.insert(0,str(REPO/'src'))
from sysone.v2.host_heads import DATASETS,build_chain
from sysone.v2.wordpiece import WordPiece
BOX=0x62400000;STRIDE=1808;HEADER=320
CONTROL=Path('/sys/class/misc/sysone_r5_smoke')
HEAD_NAMES=['intent.atis','intent.clinc','intent.embed','intent.hwu','intent.sgd','pair.msrp','pair.sick','slots.atis','slots.hwu','slots.sgd']

def jobs_for(chain,dataset):
    spec=DATASETS['multi' if dataset=='multi_clinc' else dataset];jobs=[]
    last=max(chain.word_rows) if chain.word_rows else 0
    if 'intent' in spec:
        segments=sorted(chain.word_rows) if spec['task']=='multi' else [last]
        for segment in segments:
            rows=[i for i,s in enumerate(chain.seg) if s==segment]
            jobs.append(('intent.'+spec['intent'],rows,dict(segment=segment)))
    if 'slots' in spec:
        for row,word in zip(chain.word_rows[last],chain.words[last]):
            jobs.append(('slots.'+spec['slots'],[row],dict(segment=last,word=word)))
    if 'pair' in spec:jobs.append(('pair.'+spec['pair'],list(range(len(chain.ids))),dict(segment=None)))
    return jobs

def pack_request(chain,jobs,sequence=1):
    if not 1<=len(chain.ids)<=128 or not 1<=len(jobs)<=256:raise ValueError('Request shape')
    data=bytearray(HEADER+len(jobs)*STRIDE)
    struct.pack_into('<16I',data,0,0x52354931,1,sequence,1,0,len(chain.ids),len(jobs),*([0]*9))
    struct.pack_into('<'+'H'*len(chain.ids),data,64,*chain.ids)
    for j,(name,rows,meta) in enumerate(jobs):
        if not rows or len(rows)>128 or rows!=sorted(set(rows)):raise ValueError('Selected rows')
        offset=HEADER+j*STRIDE
        struct.pack_into('<4I',data,offset,HEAD_NAMES.index(name),len(rows),0,0)
        struct.pack_into('<'+'H'*len(rows),data,offset+16,*rows)
    return data

def unpack_result(data,jobs,manifest):
    labels={h['kind']+'.'+h['name']:h['labels'] for h in manifest['heads']};out=[]
    for j,(name,rows,meta) in enumerate(jobs):
        offset=HEADER+j*STRIDE;head,count,label,classes=struct.unpack_from('<4I',data,offset)
        if head!=HEAD_NAMES.index(name) or count!=len(rows) or classes!=len(labels[name]) or label>=classes:raise RuntimeError('R5 output shape mismatch')
        logits=list(struct.unpack_from('<'+'i'*classes,data,offset+272))
        out.append(dict(head=name,**meta,label=labels[name][label],label_index=label,logits=logits))
    return out

def command(value): (CONTROL/'command').write_text(value+'\n')

def execute(chain,jobs,manifest):
    from sysone.v2.kr260_runtime import check_runtime,discover_memory
    region=discover_memory();runtime=check_runtime(0xa0000000,region)
    if not(region[0]<=BOX and BOX+0x80000<=sum(region)):raise RuntimeError('Mailbox outside reservation')
    if not CONTROL.exists():raise RuntimeError('R5 inference module is not loaded')
    previous=(CONTROL/'status').read_text()
    if 'may_run=1' in previous or 'quarantine=1' in previous:raise RuntimeError('R5 session is not idle')
    data=pack_request(chain,jobs,int(time.monotonic()*1000)&0xffffffff)
    fd=os.open('/dev/mem',os.O_RDWR|os.O_SYNC)
    with os.fdopen(fd,'rb',closefd=True) as raw:
      with mmap.mmap(raw.fileno(),0x80000,mmap.MAP_SHARED,mmap.PROT_READ|mmap.PROT_WRITE,offset=BOX) as memory:
        memory[:len(data)]=data
        command('audit');command('prepare');command('start')
        deadline=time.monotonic()+25
        while True:
            state=struct.unpack_from('<I',memory,12)[0]
            if state in [3,4]:break
            if time.monotonic()>deadline:raise TimeoutError('R5 inference timed out; PL retained for inspection')
            time.sleep(.005)
        header=struct.unpack_from('<16I',memory)
        if state!=3:raise RuntimeError('R5 inference error '+hex(header[4])+' phase '+str(header[9]))
        answer=bytes(memory[:len(data)]);trace=(CONTROL/'trace').read_text()
        if not trace.startswith('R5: INFERENCE PASS'):raise RuntimeError('Missing R5 completion trace')
        command('stop')
        status=(CONTROL/'status').read_text()
        if any(x+'=1' in status for x in ['pinned','mapped','may_run','quarantine']):raise RuntimeError('R5 cleanup incomplete')
    return dict(backend='R5 PL control + R5 classifier heads',tokens=len(chain.ids),
        clock_hz=runtime['clock_hz'],encoder_clocks=header[7],request_clocks=header[8],
        trace=trace,predictions=unpack_result(answer,jobs,manifest),r5_cleanup_status=status)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--dataset',choices=list(DATASETS),default='atis');parser.add_argument('--json',action='store_true');parser.add_argument('text',nargs='+');args=parser.parse_args()
    if os.geteuid()!=0:raise SystemExit('Run with sudo')
    with Path('/run/lock/sysone-inference.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        image=REPO/'export/v2/image/minilm-l12-v1-kr260';manifest=json.loads((image/'manifest.json').read_text())
        wp=WordPiece.from_file(REPO/'export/v2/chain/minilm-l12-v1/tokenizer.json')
        chain=build_chain(wp,[s.split() for s in args.text],DATASETS[args.dataset]['task'],128)
        result=execute(chain,jobs_for(chain,args.dataset),manifest)
        if args.json:print(json.dumps(result,indent=2))
        else:
            print(result['backend']);print(f"{result['tokens']} tokens; PL encoder {result['encoder_clocks']/result['clock_hz']*1000:.2f} ms")
            for p in result['predictions']:print(p['head']+': '+(p.get('word','')+' -> ' if 'word' in p else '')+p['label'])

if __name__=='__main__':main()
