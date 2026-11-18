"""Build/audit a separate TCM-only remoteproc ELF; never touches the target."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'build/v2/typed200-amp-linux-r5-v1'


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--attempt',required=True)
    ap.add_argument('--linker',choices=['smoke.ld','smoke-padded.ld'],required=True)
    args=ap.parse_args()
    assert args.attempt.startswith('smoke-build-v') and args.attempt[len('smoke-build-v'):].isdigit()
    out = BASE/args.attempt
    out.mkdir(exist_ok=False)
    tool = Path('C:/AMDDesignTools/2025.2/win64/tools/clang-16/bin')
    env = os.environ.copy()
    env['PATH'] = 'C:/AMDDesignTools/2025.2/Vitis/lib/win64.o'+os.pathsep+str(tool)+os.pathsep+env['PATH']
    source = ROOT/'firmware/typed200_amp_linux_r5'
    old = ROOT/'build/v2/typed200-amp-deployment-v1/r5-probe-build-v1/r5_probe.elf'
    expected_old = '79ed1f7178027011252d3b31ae8b9a098c6db444843243f3cf7f0e2bc6944e12'
    assert hashlib.sha256(old.read_bytes()).hexdigest() == expected_old
    commands = []

    def run(args, log):
        args = [str(a) for a in args]
        r = subprocess.run(args, env=env, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        (out/log).write_bytes(r.stdout)
        commands.append(args)
        assert not r.returncode, log

    run([tool/'clang.exe','--target=arm-none-eabi','-mcpu=cortex-r5','-mfloat-abi=soft',
         '-c',source/'smoke.S','-o',out/'smoke.o'], 'compile.log')
    elf = out/'sysone-r5-smoke.elf'
    run([tool/'ld.lld.exe','-T',source/args.linker,'--gc-sections','--no-undefined',
         '-Map='+str(out/'smoke.map'),out/'smoke.o','-o',elf], 'link.log')
    run([tool/'llvm-readelf.exe','-hlSs',elf], 'elf-audit.txt')
    run([tool/'llvm-objdump.exe','-d',elf], 'disassembly.txt')
    data = elf.read_bytes()
    assert data[:6] == b'\x7fELF\x01\x01' and struct.unpack_from('<H',data,18)[0] == 40
    entry, phoff = struct.unpack_from('<II',data,24)
    phsize, phnum = struct.unpack_from('<HH',data,42)
    assert entry == 0
    segments = []
    for i in range(phnum):
        p = struct.unpack_from('<8I',data,phoff+i*phsize)
        if p[0] != 1:
            continue
        assert p[2] == p[3] and p[4] <= p[5] and p[2]+p[5] <= 0x2000 and p[6]&3 != 3
        if args.linker=='smoke-padded.ld':
            assert p[2]%8==0 and p[4]%8==0 and p[5]%8==0
        segments.append(dict(address=p[2],offset=p[1],filesz=p[4],memsz=p[5],flags=p[6]))
    assert len(segments) == 3
    resource = next(p for p in segments if p['address'] == 0x800)
    table = data[resource['offset']:resource['offset']+resource['filesz']]
    assert struct.unpack_from('<5I',table) == (1,1,0,0,20)
    assert struct.unpack_from('<4I',table,20) == (2,0x1000,128,0)
    assert table[36:68] == b'sysone-smoke\0'+b'\0'*19
    assert hashlib.sha256(old.read_bytes()).hexdigest() == expected_old
    receipt = dict(passed=True,diagnostic_only=True,entry=entry,segments=segments,linker=args.linker,
        elf_sha256=hashlib.sha256(data).hexdigest(),resource_table='one RSC_TRACE only',
        allowed_address_range=[0,0xffff],ddr_access=False,pl_access=False,ps_mmio_access=False,
        old_probe_elf_sha256=expected_old,target_executed=False,reset_startup_qualified=False,
        source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in source.iterdir() if p.is_file()},commands=commands)
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS separate TCM-only ELF and trace-only resource table; old probe unchanged')


if __name__ == '__main__':
    main()
