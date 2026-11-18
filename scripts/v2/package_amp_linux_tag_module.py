"""Stage new module/helper sources; reuse the unchanged qualified PL package."""
from pathlib import Path
import argparse
import base64
import hashlib
import io
import json
import tarfile

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-linux-tag-probe-v1'
SOURCE=ROOT/'firmware/typed200_amp_linux_tag_probe'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);args=ap.parse_args()
    out=BASE/args.attempt;out.mkdir(exist_ok=False)
    build=json.loads((BASE/'firmware-build-v1/receipt.json').read_text())
    checks=json.loads((BASE/'firmware-check-v1/receipt.json').read_text())
    assert build['passed'] and checks['passed'] and build['elf_sha256']==checks['actual_elf_sha256']
    sources={n:(SOURCE/n).read_bytes() for n in ['Makefile','linux.c','session.c','session.h','pl_snapshot.c']}
    sources['smoke_image.h']=(BASE/'firmware-build-v1/smoke_image.h').read_bytes()
    sources['apu_probe.c']=(ROOT/'firmware/typed200_amp_probe/apu_probe.c').read_bytes()
    for name,data in sources.items():(out/name).write_bytes(data)
    with tarfile.open(out/'sources.tar.gz','w:gz') as tf:
        for name,data in sources.items():
            info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o600;tf.addfile(info,io.BytesIO(data))
    remote='/home/ubuntu/sysone-linux-tag-'+args.attempt
    encoded=base64.b64encode((out/'sources.tar.gz').read_bytes()).decode()
    cmd=f"umask 077; mkdir '{remote}' && printf '%s' '{encoded}' | base64 -d | tar -xz -C '{remote}' && make -C /lib/modules/$(uname -r)/build M='{remote}' CC=aarch64-linux-gnu-gcc-13 modules -j2 && gcc -O2 -static -Wall -Wextra -Werror '{remote}/apu_probe.c' -o '{remote}/apu_probe' && gcc -O2 -static -Wall -Wextra -Werror '{remote}/pl_snapshot.c' -o '{remote}/pl_snapshot'"
    plan=dict(commands=[dict(name='build',command=cmd,timeout=90),
        dict(name='hashes',command=f"sha256sum '{remote}/sysone_r5_smoke.ko' '{remote}/apu_probe' '{remote}/pl_snapshot'; modinfo '{remote}/sysone_r5_smoke.ko'"),
        *[dict(name=name,command=f"cat '{remote}/{file}'",timeout=30) for name,file in [('module','sysone_r5_smoke.ko'),('apu-probe','apu_probe'),('pl-snapshot','pl_snapshot')]]])
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    (out/'receipt.json').write_text(json.dumps(dict(passed=True,remote_directory=remote,
        embedded_elf_sha256=build['elf_sha256'],source_sha256={n:hashlib.sha256(d).hexdigest() for n,d in sources.items()},
        target_loaded=False,pl_package_rebuilt=False),indent=2)+'\n')
    print('PASS new tag module and fixed-aperture helper build plan')


if __name__=='__main__':main()
