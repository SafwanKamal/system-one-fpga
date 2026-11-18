"""Build a fixed private-TCM inference controller for the already deployed PL."""
from pathlib import Path
import hashlib,json,os,struct,subprocess
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/v2/typed200-linux-r5-calibrated-v1';SOURCE=ROOT/'firmware/typed200_linux_r5_calibrated_inference'
def main():
    out=BASE/'firmware-build-v2';out.mkdir(exist_ok=False)
    tool=Path('C:/AMDDesignTools/2025.2/win64/tools/clang-16/bin');env=os.environ.copy();env['PATH']='C:/AMDDesignTools/2025.2/Vitis/lib/win64.o;'+str(tool)+';'+env['PATH']
    flags=['--target=arm-none-eabi','-mcpu=cortex-r5','-mfpu=vfpv3-d16','-mfloat-abi=hard','-O2','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-fno-fast-math','-ffp-contract=off','-fno-unwind-tables','-ffunction-sections','-fdata-sections']
    commands=[([str(tool/'clang.exe'),*flags,'-c',str(SOURCE/n),'-o',str(out/(n+'.o'))],n+'.log') for n in ['start.S','inference.c']]
    commands += [([str(tool/'ld.lld.exe'),'-T',str(SOURCE/'tcm.ld'),'--gc-sections','--no-undefined',str(out/'start.S.o'),str(out/'inference.c.o'),'-o',str(out/'inference.elf')],'link.log'),([str(tool/'llvm-objdump.exe'),'-d',str(out/'inference.elf')],'disassembly.txt')]
    for cmd,name in commands:
        p=subprocess.run(cmd,env=env,capture_output=True,timeout=60);(out/name).write_bytes(p.stdout+p.stderr);assert p.returncode==0,name
    elf=(out/'inference.elf').read_bytes();assert struct.pack('<I',0xee0c0f10) not in elf
    phoff=struct.unpack_from('<I',elf,28)[0];phsize,phnum=struct.unpack_from('<HH',elf,42)
    image=bytearray(65536);segments=[]
    for i in range(phnum):
        p=struct.unpack_from('<8I',elf,phoff+i*phsize)
        if p[0]!=1:continue
        assert p[2]==p[3] and p[2]+p[5]<=0xe000
        image[p[2]:p[2]+p[4]]=elf[p[1]:p[1]+p[4]];segments.append(dict(address=p[2],offset=p[1],filesz=p[4],memsz=p[5]))
    assert image[0xc000:0xc009]==b'R5: WAIT\n'
    digest=hashlib.sha256(elf).hexdigest();(out/'image.bin').write_bytes(image)
    header=f'#define SMOKE_ELF_SHA256 "{digest}"\nstatic const u64 smoke_image[]={{\n'+''.join(f'0x{x:016x}ULL,\n' for (x,) in struct.iter_unpack('<Q',image))+'};\n'
    (out/'smoke_image.h').write_text(header)
    (out/'receipt.json').write_text(json.dumps(dict(passed=True,elf_sha256=digest,segments=segments,trace_offset=0xc000,image_bytes=65536,no_vbar=True,pl_rebuilt=False),indent=2)+'\n')
    print('PASS fixed TCM inference ELF '+digest)
if __name__=='__main__':main()
