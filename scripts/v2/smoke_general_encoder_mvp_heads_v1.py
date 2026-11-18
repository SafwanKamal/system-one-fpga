"""One ABI smoke fixture for generated H768 R5 head code, offline only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.ddr_image import ImageMachine


def main():
    bundle=ROOT/'build/v2/general-tool-encoder-mvp-v1';out=bundle/'head-smoke';out.mkdir(exist_ok=False)
    machine=ImageMachine((bundle/'candidate.img').read_bytes())
    hidden=np.random.default_rng(20261018).integers(-127,128,size=(2,768),dtype=np.int8)
    meta,_=machine.head_logits(hidden,'intent.meta',np.array([0]))
    spans,_=machine.head_logits(hidden,'slots.span',np.array([0,1]))
    (out/'fixture.bin').write_bytes(hidden.tobytes()+meta.astype('<i4').tobytes()+spans.astype('<i4').tobytes())
    code=r'''#define _GNU_SOURCE
#include "../firmware/abi.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
static struct shared box;
int main(int argc,char **argv) {
 assert(argc==3);
 void *memory=mmap((void *)0x60000000,0x10000000,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);
 assert(memory==(void *)0x60000000);
 FILE *image=fopen(argv[1],"rb");assert(image);
 assert(fread(memory,1,0x10000000,image)>0);assert(!ferror(image));fclose(image);
 FILE *fixture=fopen(argv[2],"rb");assert(fixture);
 assert(fread((void *)(uintptr_t)HIDDEN,1,1536,fixture)==1536);
 int32_t golden[19];assert(fread(golden,4,19,fixture)==19);fclose(fixture);
 box.tokens=2;box.jobs=3;
 box.job[0].head=0;box.job[0].count=1;box.job[0].rows[0]=0;
 for(unsigned i=1;i<3;i++){box.job[i].head=1;box.job[i].count=1;box.job[i].rows[0]=(uint16_t)(i-1);}
 assert(compute_heads(&box)==0 && box.job[0].classes==15);
 assert(!memcmp(box.job[0].logits,golden,60));
 assert(box.job[1].classes==2 && !memcmp(box.job[1].logits,golden+15,8));
 assert(box.job[2].classes==2 && !memcmp(box.job[2].logits,golden+17,8));
 assert(munmap(memory,0x10000000)==0);
 puts("PASS H768 R5 head ABI: 19 integer logits exact on one two-row fixture");return 0;
}
'''
    (out/'test_heads.c').write_text(code,encoding='utf-8')
    rel=bundle.relative_to(ROOT).as_posix();wslroot='/mnt/'+ROOT.drive[0].lower()+ROOT.as_posix()[2:]
    commands=[['wsl','-d','Ubuntu-24.04','--cd',wslroot,'--','gcc','-std=c11','-O2','-Wall','-Wextra','-Werror',
        '-DHOST_TEST','-fsanitize=undefined','-fno-sanitize-recover=all',rel+'/firmware/inference.c',rel+'/head-smoke/test_heads.c','-o',rel+'/head-smoke/test-heads'],
        ['wsl','-d','Ubuntu-24.04','--cd',wslroot,'--',rel+'/head-smoke/test-heads',rel+'/candidate.img',rel+'/head-smoke/fixture.bin']]
    for i,command in enumerate(commands):
        result=subprocess.run(command,capture_output=True,timeout=60)
        (out/f'command-{i}.log').write_bytes(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError('smoke failed; logs preserved')
    (out/'result.json').write_text(json.dumps(dict(passed=True,fixtures=1,integer_logits=19,
        undefined_sanitizer=True,board_contacted=False,scope='generated R5 head arithmetic/ABI only'))+'\n',encoding='utf-8')
    print((out/'command-1.log').read_text(encoding='utf-8'))


if __name__=='__main__':main()
