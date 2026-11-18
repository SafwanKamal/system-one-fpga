"""Execute the real diagnostic ELF in Unicorn's Cortex-R5 model; no board I/O."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'build/v2/typed200-amp-linux-r5-controller-v1'
sys.path.insert(0,str(ROOT/'build/v2/typed200-amp-linux-r5-v1/emulator-deps'))
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_CPU_ARM_CORTEX_R5, UC_ARM_REG_CPSR, UC_ARM_REG_PC, UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10
import unicorn


def accepted(trace):
    text = trace.split(b'\0',1)[0]
    return re.fullmatch(rb'R5: PASS\nSCTLR=[0-9a-f]{8}\nCPSR=[0-9a-f]{8}\nMIDR=[0-9a-f]{8}\n',text) is not None


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--build',required=True)
    ap.add_argument('--attempt',required=True)
    args=ap.parse_args()
    assert re.fullmatch(r'smoke-build-v[0-9]+',args.build)
    assert re.fullmatch(r'smoke-emulation-v[0-9]+',args.attempt)
    out = BASE/args.attempt
    out.mkdir(exist_ok=False)
    elf = (BASE/args.build/'sysone-r5-smoke.elf').read_bytes()
    unsupported_vbar = struct.pack('<I',0xee0c0f10)
    old_elf = (ROOT/'build/v2/typed200-amp-linux-r5-v1/smoke-build-v2/sysone-r5-smoke.elf').read_bytes()
    assert unsupported_vbar in old_elf, 'Prior-image negative regression must detect VBAR'
    assert unsupported_vbar not in elf, 'Cortex-R5 does not implement VBAR'
    build = json.loads((BASE/args.build/'receipt.json').read_text())
    assert hashlib.sha256(elf).hexdigest() == build['elf_sha256']
    segments = build['segments']
    cases = []

    def execute(start=0,sctlr=None,midr=None,cpsr=None,stop_after=None):
        uc = Uc(UC_ARCH_ARM,UC_MODE_ARM)
        uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_R5)
        uc.mem_map(0,0x10000)
        for p in segments:
            uc.mem_write(p['address'],elf[p['offset']:p['offset']+p['filesz']]+b'\0'*(p['memsz']-p['filesz']))
        uc.reg_write(UC_ARM_REG_CPSR,0xd3)
        writes = []
        cp15 = []
        halted = []

        def code(machine,address,size,_):
            assert 0 <= address < 0x800, hex(address)
            if stop_after is not None and len(writes) >= stop_after:
                machine.emu_stop()
                return
            instruction = struct.unpack('<I',machine.mem_read(address,4))[0]
            if instruction & 0x0f000f10 == 0x0e000f10:
                assert instruction in [0xee118f10,0xee10af10,0xee010f10], hex(instruction)
            # Reset-state fault injection overrides only the diagnostic read;
            # all branches, formatting, publication and exception vectors run
            # unchanged machine code. Normal case uses the real R5 model CP15.
            if instruction == 0xee118f10 and sctlr is not None:
                machine.reg_write(UC_ARM_REG_R8,sctlr)
                machine.reg_write(UC_ARM_REG_PC,address+4)
            elif instruction == 0xee10af10 and midr is not None:
                machine.reg_write(UC_ARM_REG_R10,midr)
                machine.reg_write(UC_ARM_REG_PC,address+4)
            elif instruction == 0xe10f9000 and cpsr is not None:
                machine.reg_write(UC_ARM_REG_R9,cpsr)
                machine.reg_write(UC_ARM_REG_PC,address+4)
            elif instruction == 0xe320f003:
                halted.append(address)
                machine.emu_stop()
            if instruction in [0xee0c0f10,0xee010f10]:
                cp15.append(instruction)

        def write(machine,access,address,size,value,_):
            assert 0x1000 <= address and address+size <= 0x1100+128, (address,size)
            writes.append((address,size,value))

        uc.hook_add(UC_HOOK_CODE,code)
        uc.hook_add(UC_HOOK_MEM_WRITE,write)
        uc.emu_start(start,0x800,count=20000)
        trace = bytes(uc.mem_read(0x1000,128))
        return dict(trace=trace,writes=writes,halted=bool(halted),cp15=cp15)

    normal = execute()
    assert normal['halted'] and accepted(normal['trace']),normal['trace']
    assert normal['writes'][-1] == (0x1004,4,0x53534150)
    cases.append('real-Cortex-R5-reset-model')
    (out/'normal-trace.txt').write_bytes(normal['trace'].split(b'\0')[0])
    # Every interruption before final publication must remain unaccepted.
    for n in range(len(normal['writes'])):
        r = execute(stop_after=n)
        assert not accepted(r['trace']),n
        cases.append(f'partial-publication-{n}')
    for flag in [1,4,0x1000,0x1005]:
        r = execute(sctlr=flag)
        assert b'R5: FAIL\nERROR=00000008\n' in r['trace'] and not accepted(r['trace'])
        cases.append(f'reject-sctlr-{flag:x}')
    for bit in range(4,16):
        r = execute(midr=0x411fc153^(1<<bit))
        assert not accepted(r['trace']) and b'ERROR=00000008' in r['trace']
        cases.append(f'reject-cpu-part-bit-{bit}')
    for value in [0x13,0x53,0x93,0xd0,0xf3]:
        r = execute(cpsr=value)
        assert not accepted(r['trace']) and b'ERROR=00000008' in r['trace']
        cases.append(f'reject-cpsr-{value:x}')
    for vector in range(1,8):
        r = execute(start=vector*4)
        assert not accepted(r['trace']) and f'ERROR={vector:08x}'.encode() in r['trace']
        cases.append(f'exception-vector-{vector}')
    for value in [0,0x2000,0xc50078,0xc52078]:
        r = execute(sctlr=value)
        assert accepted(r['trace']) and f'SCTLR={value:08x}'.encode() in r['trace']
        cases.append(f'valid-sctlr-{value:x}')
    result = dict(passed=True,cases=len(cases),checks=cases,emulator_version=unicorn.__version__,
        cpu_model='UC_CPU_ARM_CORTEX_R5',actual_elf_sha256=hashlib.sha256(elf).hexdigest(),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        software_only=True,power_reset_clock_qualified=False,target_executed=False,
        prior_vbar_image_rejected=True,cp15_instruction_allowlist_checked=True,
        timing_or_wcet_claim=False)
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS {len(cases)} actual-ELF Cortex-R5 emulation/fault/publication cases; no target action')


if __name__ == '__main__':
    main()
