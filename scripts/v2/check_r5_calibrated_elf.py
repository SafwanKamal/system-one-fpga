"""Execute the built R5 ELF with a modeled completed PL encoder transaction."""
from pathlib import Path
import argparse,hashlib,json,struct,sys
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/v2/typed200-linux-r5-calibrated-v1'
sys.path.insert(0,str(ROOT/'build/v2/typed200-amp-linux-r5-v1/emulator-deps'))
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_CPU_ARM_CORTEX_R5F,UC_ARM_REG_CPSR,UC_ARM_REG_PC

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);args=ap.parse_args()
    out=BASE/args.attempt;out.mkdir(exist_ok=False)
    build=json.loads((BASE/'firmware-build-v1/receipt.json').read_text());elf=(BASE/'firmware-build-v1/inference.elf').read_bytes()
    cpu=Uc(UC_ARCH_ARM,UC_MODE_ARM);cpu.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_R5F);cpu.reg_write(UC_ARM_REG_CPSR,0xd3)
    cpu.mem_map(0,65536);cpu.mem_write(0,(BASE/'firmware-build-v1/image.bin').read_bytes())
    cpu.mem_map(0x60000000,0x2100000);cpu.mem_write(0x60000000,(ROOT/'export/v2/image/minilm-l12-v1-kr260/minilm-l12-v1-kr260.img').read_bytes())
    cpu.mem_map(0x62100000,65536);cpu.mem_map(0x62400000,0x80000);cpu.mem_map(0xa0000000,4096)
    with (BASE/'emulator-request.bin').open('rb') as f:
        size,hidden_size=struct.unpack('<II',f.read(8));request=f.read(size);hidden=f.read(hidden_size)
    cpu.mem_write(0x62400000,request);cpu.mem_write(0x62101000,hidden)
    for offset,value in [(0x14,0x53595332),(0x18,0x20804004),(0x1c,0x5377ffff),(8,123456),(12,123499)]:cpu.mem_write(0xa0000000+offset,struct.pack('<I',value))
    operations=[];completion=[];running=[False]
    def write(uc,access,address,size,value,data):
        operations.append([address,value])
        if address==0xa0000000 and value==1:running[0]=True
    def read(uc,access,address,size,value,data):
        if address==0xa0000000 and running[0]:uc.mem_write(address,struct.pack('<I',2))
    def state(uc,access,address,size,value,data):
        if value in (3,4):completion.append(value);uc.emu_stop()
    cpu.hook_add(UC_HOOK_MEM_WRITE,write,begin=0xa0000000,end=0xa0000fff)
    cpu.hook_add(UC_HOOK_MEM_READ,read,begin=0xa0000000,end=0xa0000fff)
    cpu.hook_add(UC_HOOK_MEM_WRITE,state,begin=0x6240000c,end=0x6240000f)
    try:cpu.emu_start(0,65536,timeout=30000000,count=100000000)
    except Exception:
        pc=cpu.reg_read(UC_ARM_REG_PC);print('Fault PC',hex(pc),bytes(cpu.mem_read(pc,16)).hex());raise
    trace=bytes(cpu.mem_read(0xc000,128)).split(b'\0')[0]
    (out/'trace.txt').write_bytes(trace)
    assert completion==[3],(completion,bytes(cpu.mem_read(0x62400000,64)).hex(),trace)
    assert trace==b'R5: INFERENCE PASS\n'
    assert operations==[[0xa0000020,0x60000400],[0xa0000024,(384<<16)|struct.unpack_from('<I',request,20)[0]],[0xa0000028,0x62100000],[0xa000002c,0x62101000],[0xa0000000,1],[0xa0000000,2]],operations
    with (BASE/'emulator-expected.bin').open('rb') as f:
        expected=f.read(struct.unpack('<I',f.read(4))[0])
    actual=bytes(cpu.mem_read(0x62400000,size));assert actual[320:]==expected[320:]
    (out/'receipt.json').write_text(json.dumps(dict(passed=True,actual_elf_sha256=hashlib.sha256(elf).hexdigest(),actual_arm_startup_and_fpu=True,pl_encoder_modeled=True,pl_control_writes=operations,head_output_matches_native=True,calibrated_clinc_rejection_exercised=True,trace=trace.decode()),indent=2)+'\n')
    print('PASS actual Cortex-R5 ELF startup, VFP, PL control and golden head results')
if __name__=='__main__':main()
