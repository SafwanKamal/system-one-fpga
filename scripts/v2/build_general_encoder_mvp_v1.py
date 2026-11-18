"""Build an H768 encoder image and matching private-TCM R5 candidate offline.

Reuse existing operator family. No board contacts, PL rebuild or deployment.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

os.environ['OPENBLAS_NUM_THREADS']='1'
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
import torch
from sysone.v2.general_tool_encoder import ToolEncoder
from sysone.v2.general_tool_integer import IntegerToolEncoder,bank_ids


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()


def main():
    out=ROOT/'build/v2/general-tool-encoder-mvp-v1';out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(2)
    parent=ROOT/'build/v2/general-tool-expanded-training-v4/encoder'
    run=json.loads((parent/'run.json').read_text(encoding='utf-8'))
    model=ToolEncoder(run['arguments']['model'],4)
    checkpoint=torch.load(parent/'best.pt',map_location='cpu',weights_only=False)
    model.load_state_dict(checkpoint['trainable_state'],strict=False);model.eval()
    jobs=json.loads((parent/'training-jobs.json').read_text(encoding='utf-8'))
    calibration=[j for j in jobs if len(j['tokens']['input_ids'])<=128][:32]
    if len(calibration)!=32:raise ValueError('calibration count')
    integer=IntegerToolEncoder(model,calibration,out,32)
    manifest=json.loads((out/'integer-manifest.json').read_text(encoding='utf-8'))
    qualification=json.loads((out/'integer-qualification.json').read_text(encoding='utf-8'))
    if not qualification['proposed_layout']['fits_reserved']:raise ValueError('reserved memory capacity')
    firmware=out/'firmware';firmware.mkdir()
    prior=ROOT/'firmware/typed200_linux_r5_inference'
    for name in ['start.S','tcm.ld']:shutil.copyfile(prior/name,firmware/name)
    # New ABI and buffers; old deployed sources/addresses are never modified.
    abi=(prior/'abi.h').read_text(encoding='utf-8')
    layout=qualification['proposed_layout']
    for before,after in [('0x62400000u',layout['mailbox']+'u'),('0x62101000u',layout['hidden']+'u'),
        ('0x62100000u',layout['ids']+'u'),('MAX_CLASSES 384u','MAX_CLASSES 16u'),
        ('sizeof(struct job)==1808','sizeof(struct job)==336')]:abi=abi.replace(before,after)
    (firmware/'abi.h').write_text(abi,encoding='utf-8')
    source=(prior/'inference.c').read_text(encoding='utf-8')
    source=source.replace('384','768').replace('24*512','48*512').replace('>=30522','>=61044')
    source=source.replace('box->magic!=0x52354931','box->magic!=0x47354931')
    (firmware/'inference.c').write_text(source,encoding='utf-8')
    pool=next(s['address'] for s in manifest['sections'] if s['name']=='tables')+512
    # Tables contain 256 uint16 exp entries then uint32 pooling reciprocals.
    heads='static const struct head heads[]={\n'
    for h in manifest['heads']:
        heads+='{'+','.join(str(v)+'u' for v in [h['classes'],h['stream'],h['scales'],pool,1])+ '},\n'
    heads+='};\n';(firmware/'heads.inc').write_text(heads,encoding='utf-8')
    tools=Path('C:/AMDDesignTools/2025.2/win64/tools/clang-16/bin')
    env=os.environ.copy();env['PATH']='C:/AMDDesignTools/2025.2/Vitis/lib/win64.o;'+str(tools)+';'+env['PATH']
    flags=['--target=arm-none-eabi','-mcpu=cortex-r5','-mfpu=vfpv3-d16','-mfloat-abi=hard',
        '-O2','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-fstack-usage',
        '-fno-fast-math','-ffp-contract=off','-fno-unwind-tables','-ffunction-sections','-fdata-sections']
    commands=[]
    for name in ['start.S','inference.c']:
        commands.append([str(tools/'clang.exe'),*flags,'-c',str(firmware/name),'-o',str(firmware/(name+'.o'))])
    commands.append([str(tools/'ld.lld.exe'),'-T',str(firmware/'tcm.ld'),'--gc-sections','--no-undefined',
        str(firmware/'start.S.o'),str(firmware/'inference.c.o'),'-o',str(firmware/'inference.elf')])
    for i,command in enumerate(commands):
        result=subprocess.run(command,env=env,capture_output=True,timeout=60)
        (firmware/f'build-{i}.log').write_bytes(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError('R5 build failed; logs preserved')
    elf=(firmware/'inference.elf').read_bytes();phoff=struct.unpack_from('<I',elf,28)[0]
    phsize,phnum=struct.unpack_from('<HH',elf,42);image=bytearray(65536)
    for i in range(phnum):
        p=struct.unpack_from('<8I',elf,phoff+i*phsize)
        if p[0]!=1:continue
        if p[2]!=p[3] or p[2]+p[5]>0xe000:raise ValueError('TCM placement')
        image[p[2]:p[2]+p[4]]=elf[p[1]:p[1]+p[4]]
    (firmware/'image.bin').write_bytes(image)
    record=dict(stage='offline_candidate_built',board_contacted=False,pl_rebuild=False,
        parent_checkpoint_sha256=sha(parent/'best.pt'),image_sha256=sha(out/'candidate.img'),
        r5_elf_sha256=sha(firmware/'inference.elf'),tokens_max=128,hidden=768,token_ids_max=61043,
        classifier_rows=manifest['classifier_rows'],layout=layout,commands=commands,
        source_sha256={str(Path(__file__).relative_to(ROOT)):sha(Path(__file__))},
        calibration='first32 training-only checked jobs within128token profile',
        remaining=['host smoke of generated R5 heads','Linux request adapter for relocated ABI',
            'explicit board switch window preserving rollback','hardware execution comparison',
            'typed call reconstruction and terminal-by-D integration'],
        scope='candidate image and R5 firmware; not end-to-end MVP or hardware qualification')
    (out/'candidate.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record),flush=True)


if __name__=='__main__':main()
