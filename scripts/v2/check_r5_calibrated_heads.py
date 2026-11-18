"""Compare native C head implementation against every frozen hidden-state case."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,struct,subprocess,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/v2/typed200-linux-r5-calibrated-v1';SOURCE=ROOT/'firmware/typed200_linux_r5_calibrated_inference'
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);args=ap.parse_args()
    out=BASE/args.attempt;out.mkdir(exist_ok=False);os.environ['SYSONE_REPO']=str(ROOT)
    spec=importlib.util.spec_from_file_location('r5client',ROOT/'scripts/v2/r5_inference_client.py');client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
    from sysone.v2 import eval_suite,ddr_image
    model=ROOT/'export/v2/image/minilm-l12-v1-kr260/minilm-l12-v1-kr260.img';machine=ddr_image.ImageMachine(model.read_bytes())
    suite=json.loads((ROOT/'build/v2/eval/minilm-l12-v1-matched.json').read_text());requests=[];goldens=[]
    wp=client.WordPiece.from_file(ROOT/'export/v2/chain/minilm-l12-v1/tokenizer.json')
    with (out/'requests.bin').open('wb') as stream:
        for case in suite['cases']:
            c=eval_suite.chain(case);chain=client.build_chain(wp,[s.words for s in c.segments],c.task,128)
            assert chain.ids==case['ids'];jobs=client.jobs_for(chain,c.dataset);request=client.pack_request(chain,jobs)
            hidden=eval_suite.reference(case);raw=hidden.astype(np.int8).tobytes()
            stream.write(struct.pack('<II',len(request),len(raw))+request+raw)
            golden=[]
            for name,rows,meta in jobs:
                logits,scales=machine.head_logits(hidden,name,np.asarray(rows));logits=np.asarray(logits).reshape(-1)
                assert len(logits)==machine.heads[name]['classes']
                scores=logits*scales;label=int(np.argmax(scores))
                if name=='intent.clinc' and 1.0/np.exp(scores-scores.max()).sum() < 0.36:label=150
                golden.append((logits.tolist(),label))
            goldens.append(golden);requests.append((case['id'],jobs))
    host=r'''#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include "abi.h"
int main(int argc,char **argv){
 if(argc!=4)return 1;
 void *model=mmap((void*)0x60000000,0x2100000,3,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0);
 void *hidden=mmap((void*)HIDDEN,65536,3,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0);
 struct shared *m=mmap((void*)BOX,0x80000,3,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0);
 if(model==MAP_FAILED||hidden==MAP_FAILED||m==MAP_FAILED)return 2;
 FILE *f=fopen(argv[1],"rb");if(!f)return 3;if(fread(model,1,0x2100000,f)!=33916928)return 8;fclose(f);
 FILE *in=fopen(argv[2],"rb"),*out=fopen(argv[3],"wb");if(!in||!out)return 4;
 unsigned sizes[2];
 while(fread(sizes,4,2,in)==2){
  if(sizes[0]>sizeof(*m)||sizes[1]>49152)return 5;
  if(fread(m,1,sizes[0],in)!=sizes[0]||fread(hidden,1,sizes[1],in)!=sizes[1])return 6;
  int error=compute_heads(m);if(error){fprintf(stderr,"head error %d\n",error);return 7;}
  fwrite(&sizes[0],4,1,out);fwrite(m,1,sizes[0],out);
 }
 fclose(in);fclose(out);return 0;
}
'''
    (out/'host.c').write_text(host)
    def posix(p):return '/mnt/c/'+p.resolve().as_posix()[3:]
    calls=[['gcc','-O2','-Wall','-Wextra','-Werror','-DHOST_TEST','-fno-fast-math','-ffp-contract=off','-I',posix(SOURCE),posix(out/'host.c'),posix(SOURCE/'inference.c'),'-o',posix(out/'heads-test')],
           [posix(out/'heads-test'),posix(model),posix(out/'requests.bin'),posix(out/'results.bin')]]
    for i,cmd in enumerate(calls):
        p=subprocess.run(['wsl','-d','Ubuntu-24.04','--',*cmd],capture_output=True,timeout=180)
        (out/('compile.log' if i==0 else 'run.log')).write_bytes(p.stdout+p.stderr);assert p.returncode==0,(i,p.stderr[-2000:])
    all_logits=0
    with (out/'results.bin').open('rb') as stream:
        for (case,jobs),golden in zip(requests,goldens):
            size=struct.unpack('<I',stream.read(4))[0];data=stream.read(size)
            for j,(want,label) in enumerate(golden):
                offset=client.HEADER+j*client.STRIDE;actual_label,classes=struct.unpack_from('<II',data,offset+8)
                actual=list(struct.unpack_from('<'+'i'*classes,data,offset+272))
                assert actual==want and actual_label==label,(case,j,actual_label,label)
                all_logits+=classes
        assert not stream.read()
    (out/'receipt.json').write_text(json.dumps(dict(passed=True,cases=len(requests),head_jobs=sum(len(j) for _,j in requests),integer_logits_compared=all_logits,calibrated_labels_match=True,source_sha256=hashlib.sha256((SOURCE/'inference.c').read_bytes()).hexdigest()),indent=2)+'\n')
    print(f'PASS {len(requests)} frozen cases, {all_logits} exact C logits and dev-calibrated labels')
if __name__=='__main__':main()
