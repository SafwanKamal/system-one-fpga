"""Run the actual tag-probe ELF in private TCM plus a bounded PL register model."""
from pathlib import Path
import hashlib
import json
import re
import struct
import sys

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-linux-tag-probe-v1'
sys.path.insert(0,str(ROOT/'build/v2/typed200-amp-linux-r5-v1/emulator-deps'))
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_MEM_WRITE,UC_HOOK_MEM_READ
from unicorn.arm_const import UC_CPU_ARM_CORTEX_R5,UC_ARM_REG_CPSR,UC_ARM_REG_PC,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10


def accepted(trace):
    return re.fullmatch(rb'R5: PASS\nSCTLR=[0-9a-f]{8}\nCPSR=[0-9a-f]{8}\nMIDR=[0-9a-f]{8}\nAR=[0-9a-f]{8}\nARID=[0-9a-f]{8}\n',trace.split(b'\0')[0]) is not None


def main():
    out=BASE/'firmware-check-v1';out.mkdir(exist_ok=False)
    elf=(BASE/'firmware-build-v1/probe.elf').read_bytes()
    build=json.loads((BASE/'firmware-build-v1/receipt.json').read_text())
    assert hashlib.sha256(elf).hexdigest()==build['elf_sha256']
    assert struct.pack('<I',0xee0c0f10) not in elf
    def execute(sctlr=None,cpsr=None,midr=None,start=0,stop_after=None,
                magic=0x4f524731,version=1,initial_count=64,initial_errors=0,
                corrupt_count=False,corrupt_errors=False,tag=0x12345,ident=0x77):
        cpu=Uc(UC_ARCH_ARM,UC_MODE_ARM);cpu.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_R5)
        cpu.mem_map(0,65536);cpu.mem_map(0xa0000000,4096)
        for p in build['segments']:
            cpu.mem_write(p['address'],elf[p['offset']:p['offset']+p['filesz']]+b'\0'*(p['memsz']-p['filesz']))
        cpu.reg_write(UC_ARM_REG_CPSR,0xd3)
        writes=[];accesses=[];halt=[];markers=[]
        def code(uc,address,size,data):
            assert 0<=address<0x800,hex(address)
            if stop_after is not None and len(writes)>=stop_after:
                uc.emu_stop();return
            instruction=struct.unpack('<I',uc.mem_read(address,4))[0]
            if instruction & 0x0f000f10==0x0e000f10:
                assert instruction in [0xee118f10,0xee10af10,0xee010f10],hex(instruction)
            for opcode,register,override in [(0xee118f10,UC_ARM_REG_R8,sctlr),
                    (0xe10f9000,UC_ARM_REG_R9,cpsr),(0xee10af10,UC_ARM_REG_R10,midr)]:
                if instruction==opcode and override is not None:
                    uc.reg_write(register,override);uc.reg_write(UC_ARM_REG_PC,address+4)
            if instruction==0xe320f003:halt.append(address);uc.emu_stop()
        def read(uc,access,address,size,value,data):
            if address<0xa0000000:return
            assert size==4 and address in [0xa0000000+x for x in [0,4,8,12,24,28]],hex(address)
            count=initial_count+len(markers)+(1 if corrupt_count and markers else 0)
            errors=initial_errors+(1 if corrupt_errors and markers else 0)
            v={0:magic,4:version,8:count,12:errors,24:tag,28:ident}[address-0xa0000000]
            uc.mem_write(address,struct.pack('<I',v));accesses.append(dict(kind='read',address=address,value=v))
        def write(uc,access,address,size,value,data):
            writes.append((address,size,value))
            if address>=0xa0000000:
                ordinal=len(markers)
                assert size==4 and ordinal<4 and address==0xa0000010+ordinal*4
                assert value==0x52350004+ordinal
                markers.append(value);accesses.append(dict(kind='write',address=address,value=value))
            else:
                assert 0x1000<=address and address+size<=0x1100,hex(address)
        cpu.hook_add(UC_HOOK_CODE,code);cpu.hook_add(UC_HOOK_MEM_READ,read);cpu.hook_add(UC_HOOK_MEM_WRITE,write)
        cpu.emu_start(start,0x800,count=30000)
        return dict(trace=bytes(cpu.mem_read(0x1000,128)),writes=writes,accesses=accesses,markers=markers,halted=bool(halt))
    cases=[];normal=execute()
    assert accepted(normal['trace']) and normal['halted'] and len(normal['markers'])==4
    assert normal['writes'][-1]==(0x1004,4,0x53534150)
    cases.append('actual-elf-normal')
    for n in range(len(normal['writes'])):
        assert not accepted(execute(stop_after=n)['trace']);cases.append(f'partial-{n}')
    for flag in [1,4,0x1000,0x1005]:
        r=execute(sctlr=flag);assert b'ERROR=00000008' in r['trace'] and not r['accesses'];cases.append(f'cpu-state-{flag}')
    for value in [0x13,0x53,0x93,0xd0,0xf3]:
        r=execute(cpsr=value);assert not accepted(r['trace']) and not r['accesses'];cases.append(f'cpsr-{value}')
    for bit in range(4,16):
        r=execute(midr=0x411fc153^(1<<bit));assert not accepted(r['trace']) and not r['accesses'];cases.append(f'cpu-id-{bit}')
    for vector in range(1,8):
        r=execute(start=vector*4);assert f'ERROR={vector:08x}'.encode() in r['trace'] and not r['accesses'];cases.append(f'vector-{vector}')
    for params,code in [(dict(magic=0),9),(dict(version=2),9),(dict(initial_count=63),10),
                        (dict(initial_errors=1),10),(dict(corrupt_count=True),10),(dict(corrupt_errors=True),10)]:
        r=execute(**params);assert f'ERROR={code:08x}'.encode() in r['trace'] and not accepted(r['trace']);cases.append(str(params))
    r=execute(sctlr=0xe50878,cpsr=0x1d3);assert accepted(r['trace']);cases.append('observed-hardware-reset-state')
    for tag,ident in [(0,0),(0x7ffff,65535),(0x20081,0x3ff)]:
        r=execute(tag=tag,ident=ident);assert accepted(r['trace']) and f'AR={tag:08x}\nARID={ident:08x}'.encode() in r['trace'];cases.append(f'tag-{tag}')
    (out/'normal-trace.txt').write_bytes(normal['trace'].split(b'\0')[0])
    (out/'actual-elf-transactions.json').write_text(json.dumps(normal['accesses'],indent=2)+'\n')
    (out/'receipt.json').write_text(json.dumps(dict(passed=True,cases=len(cases),checks=cases,
        actual_elf_sha256=build['elf_sha256'],mapped_regions=['private TCM 64KiB','PL probe 4KiB'],
        emitted_pl_reads=8,emitted_pl_writes=4,ps_mmio_access=False,ddr_access=False,
        software_only=True,target_origin_tags_qualified=False,timing_claim=False),indent=2)+'\n')
    print(f'PASS {len(cases)} actual-ELF CPU/model scenarios; 8 PL reads and 4 exact marker writes')


if __name__=='__main__':main()
