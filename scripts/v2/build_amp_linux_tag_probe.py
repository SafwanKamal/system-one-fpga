"""Build a separate TCM tag-probe ELF; preserve the original probe package/ELFs."""
from pathlib import Path
import hashlib
import json
import os
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-linux-tag-probe-v1'
SOURCE=ROOT/'firmware/typed200_amp_linux_tag_probe'


def main():
    out=BASE/'firmware-build-v1';out.mkdir(exist_ok=False)
    tool=Path('C:/AMDDesignTools/2025.2/win64/tools/clang-16/bin')
    env=os.environ.copy();env['PATH']='C:/AMDDesignTools/2025.2/Vitis/lib/win64.o;'+str(tool)+';'+env['PATH']
    commands=[([str(tool/'clang.exe'),'--target=arm-none-eabi','-mcpu=cortex-r5','-mfloat-abi=soft','-c',str(SOURCE/'tag_probe.S'),'-o',str(out/'probe.o')],'compile.log'),
        ([str(tool/'ld.lld.exe'),'-T',str(SOURCE/'smoke-padded.ld'),'--gc-sections','--no-undefined',str(out/'probe.o'),'-o',str(out/'probe.elf')],'link.log'),
        ([str(tool/'llvm-objdump.exe'),'-d',str(out/'probe.elf')],'disassembly.txt')]
    for command,name in commands:
        run=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env,timeout=60)
        (out/name).write_bytes(run.stdout);assert not run.returncode,name
    elf=(out/'probe.elf').read_bytes()
    assert elf[:6]==b'\x7fELF\x01\x01' and struct.unpack_from('<H',elf,18)[0]==40
    entry,phoff=struct.unpack_from('<II',elf,24);phsize,phnum=struct.unpack_from('<HH',elf,42)
    assert entry==0 and struct.pack('<I',0xee0c0f10) not in elf
    segments=[];image=bytearray(0x1100)
    for i in range(phnum):
        p=struct.unpack_from('<8I',elf,phoff+i*phsize)
        if p[0]!=1:continue
        assert p[2]==p[3] and p[2]+p[5]<=len(image) and p[4]<=p[5]
        assert p[2]%8==p[4]%8==p[5]%8==0 and p[6]&3!=3
        assert not any(p[2]<s['address']+s['memsz'] and s['address']<p[2]+p[5] for s in segments)
        segments.append(dict(address=p[2],offset=p[1],filesz=p[4],memsz=p[5],flags=p[6]))
        image[p[2]:p[2]+p[4]]=elf[p[1]:p[1]+p[4]]
    assert len(segments)==3 and image[0x1000:0x1009]==b'R5: WAIT\n'
    table=image[0x800:0x848]
    assert struct.unpack_from('<9I',table)==(1,1,0,0,20,2,0x1000,128,0)
    assert table[36:68]==b'sysone-smoke\0'+b'\0'*19
    (out/'image.bin').write_bytes(image)
    header='/* Generated fixed tag-probe image; never accepts arbitrary firmware. */\n'
    digest=hashlib.sha256(elf).hexdigest()
    header+=f'#define SMOKE_ELF_SHA256 "{digest}"\nstatic const u64 smoke_image[] = {{\n'
    header+=''.join(f'0x{x:016x}ULL,\n' for (x,) in struct.iter_unpack('<Q',image))+'};\n'
    (out/'smoke_image.h').write_text(header)
    (out/'receipt.json').write_text(json.dumps(dict(passed=True,elf_sha256=digest,segments=segments,
        resource_table='one trace only',private_tcm=[0,65535],pl_aperture=[0xa0000000,0xa0000fff],
        pl_marker_offsets=[16,20,24,28],ddr_access=False,ps_mmio_access=False,
        source_sha256={n:hashlib.sha256((SOURCE/n).read_bytes()).hexdigest() for n in ['tag_probe.S','smoke-padded.ld']},
        diagnostic_only=True,target_executed=False),indent=2)+'\n')
    print('PASS separate TCM/PL tag-probe ELF and fixed-image header')


if __name__=='__main__':main()
