"""Create a separate timed platform/linker from frozen reset-entry sources."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
    base=ROOT/'firmware/typed200_r5';out=ROOT/'firmware/typed200_timed'
    for n in ('platform.c','tcm.ld'):assert not (out/n).exists(),n
    p=(base/'platform.c').read_text()
    p=p.replace('#include "service.h"','#include "../typed200_r5/service.h"')
    p=p.replace('#include "sha256.h"','#include "../typed200_r5/sha256.h"\n#include "pmu.h"')
    anchor='    if(!ty_service_init(';assert p.count(anchor)==1
    p=p.replace(anchor,'    if(!ty_pmu_bind(ty_shared.session))ty_exception(14);\n'+anchor)
    (out/'platform.c').write_text(p)
    s=(base/'tcm.ld').read_text();assert s.count('KEEP(*(.shared))')==1
    (out/'tcm.ld').write_text(s.replace('KEEP(*(.shared))','KEEP(*(.shared)) KEEP(*(.clock_config))'))
    print('Created separate timed platform; frozen inputs unchanged')
if __name__=='__main__':main()
