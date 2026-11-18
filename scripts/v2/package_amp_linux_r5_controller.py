"""Snapshot controller sources and the previously qualified smoke ELF for build."""
from pathlib import Path
import argparse
import base64
import hashlib
import io
import json
import struct
import tarfile

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'build/v2/typed200-amp-linux-r5-controller-v1'
SOURCE = ROOT/'firmware/typed200_amp_linux_r5_controller'
ELF = BASE/'smoke-build-v1/sysone-r5-smoke.elf'
EXPECTED = json.loads((BASE/'smoke-build-v1/receipt.json').read_text())['elf_sha256']


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--attempt',required=True)
    args=ap.parse_args()
    out=BASE/args.attempt
    out.mkdir(exist_ok=False)
    elf=ELF.read_bytes()
    assert hashlib.sha256(elf).hexdigest()==EXPECTED
    emulation=json.loads((BASE/'smoke-emulation-v1/receipt.json').read_text())
    assert emulation['passed'] and emulation['actual_elf_sha256']==EXPECTED
    assert emulation['prior_vbar_image_rejected'] and emulation['cp15_instruction_allowlist_checked']
    assert struct.pack('<I',0xee0c0f10) not in elf
    image=bytearray(0x1100)
    phoff=struct.unpack_from('<I',elf,28)[0]
    phsize,phnum=struct.unpack_from('<HH',elf,42)
    intervals=[]
    for i in range(phnum):
        p=struct.unpack_from('<8I',elf,phoff+i*phsize)
        if p[0]!=1:continue
        _,offset,va,pa,filesz,memsz,flags,align=p
        assert va==pa and pa%8==filesz%8==memsz%8==0
        assert pa+memsz<=len(image) and filesz<=memsz
        assert not any(pa<b and a<pa+memsz for a,b in intervals)
        intervals.append((pa,pa+memsz))
        image[pa:pa+filesz]=elf[offset:offset+filesz]
    assert len(intervals)==3
    assert image[0x1000:0x1009]==b'R5: WAIT\n'
    header='/* Generated from the sealed smoke ELF; little-endian AArch64 only. */\n'
    header+=f'#define SMOKE_ELF_SHA256 "{EXPECTED}"\nstatic const u64 smoke_image[] = {{\n'
    header+=''.join(f'0x{word:016x}ULL,\n' for (word,) in struct.iter_unpack('<Q',image))+'};\n'
    sources={name:(SOURCE/name).read_bytes() for name in ['Makefile','linux.c','session.c','session.h']}
    sources['smoke_image.h']=header.encode()
    for name,data in sources.items():(out/name).write_bytes(data)
    with tarfile.open(out/'controller.tar.gz','w:gz') as tf:
        for name,data in sources.items():
            info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o600
            tf.addfile(info,io.BytesIO(data))
    remote='/home/ubuntu/sysone-r5-smoke-'+args.attempt
    encoded=base64.b64encode((out/'controller.tar.gz').read_bytes()).decode()
    command=f"umask 077; mkdir '{remote}' && printf '%s' '{encoded}' | base64 -d | tar -xz -C '{remote}' && make -C /lib/modules/$(uname -r)/build M='{remote}' CC=aarch64-linux-gnu-gcc-13 modules -j2"
    plan=dict(commands=[
        dict(name='build',command=command,timeout=90),
        dict(name='module-info',command=f"modinfo '{remote}/sysone_r5_smoke.ko'; sha256sum '{remote}/sysone_r5_smoke.ko'"),
        dict(name='module-binary',command=f"cat '{remote}/sysone_r5_smoke.ko'",timeout=30),
        dict(name='health',command="uptime; cat /proc/sys/kernel/tainted; cat /proc/sys/kernel/random/boot_id; ls -la /sys/class/remoteproc")])
    (out/'build-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    (out/'receipt.json').write_text(json.dumps(dict(passed=True,elf_sha256=EXPECTED,
        embedded_image_bytes=len(image),image_sha256=hashlib.sha256(image).hexdigest(),
        source_sha256={n:hashlib.sha256(d).hexdigest() for n,d in sources.items()},
        remote_build_directory=remote,
        live_enabled=b'#define SYSONE_R5_LIVE_ADMITTED 1' in sources['linux.c'],
        prepare_enabled=b'#define SYSONE_R5_PREPARE_ADMITTED 1' in sources['linux.c'],
        target_loaded=False),indent=2)+'\n')
    print(f'PASS fixed image packaging; fresh build plan at {out}/build-plan.json')


if __name__=='__main__':main()
