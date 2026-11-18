"""Restore the qualified RC1 deployment onto a freshly flashed KR260 (run as root on the board).

Stages (each idempotent-refusing: it stops if a target already exists):
  memory   - /etc/sysone/kr260-memory.json (0x60000000, 256 MiB) + reserved-memory kernel hooks
  files    - v9e FPGA app, RC1 package, rc1-default-v1 bundle, units, launcher; verifies every pinned hash
  enable   - systemd daemon-reload and enable sysone-rc1.service (starts on next boot)
Nothing here programs the FPGA, loads the DMA module or the model; the RC1 boot initializer does that.
usage: python3 restore_rc1.py <stage> --src <unpacked recovery dir>
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, tarfile
from pathlib import Path

PACKAGE = Path('/var/lib/sysone/hardware-consolidated-rc1-20261108')
BUNDLE = Path('/var/lib/sysone/rc1-default-v1')
FIRMWARE = Path('/lib/firmware/xilinx/sysone-qwen-decoder-v9e')
UNITS = Path('/etc/systemd/system')
LAUNCHER = Path('/usr/local/bin/sysone-qwen-fpga')
MODEL = Path('/home/ubuntu/sysone-generation/Qwen3-0.6B-Q8_0.gguf')
MODEL_SHA = '9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031'
LAUNCHER_SHA = '378b619e4b5d88bad3f8a71870ae92e5b113162272575ad3a9e6ffe6019594e5'


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 24), b''):
            h.update(b)
    return h.hexdigest()


def run(args):
    r = subprocess.run(args, capture_output=True, text=True, timeout=600)
    print(json.dumps(dict(command=args, rc=r.returncode, out=r.stdout[-2000:], err=r.stderr[-2000:])), flush=True)
    r.check_returncode()
    return r.stdout


def check(root, hashes):
    for name, digest in hashes.items():
        if sha(root / name) != digest:
            raise RuntimeError('hash differs: ' + str(root / name))


def memory(src):
    cfg = Path('/etc/sysone/kr260-memory.json')
    if cfg.exists():
        raise RuntimeError('memory config already present')
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps(dict(base='0x60000000', bytes='0x10000000')) + '\n')
    run(['sh', str(src / 'memory/install_memory_hooks.sh')])


def files(src):
    bundle_cfg = json.loads((src / 'bundle/config.json').read_text())
    for p in (PACKAGE, BUNDLE, FIRMWARE, UNITS / 'sysone-rc1.service', UNITS / 'sysone-rc1-init.service'):
        if p.exists():
            raise RuntimeError('target already exists: ' + str(p))
    if sha(MODEL) != MODEL_SHA:
        raise RuntimeError('model hash differs')
    # FPGA app
    check(src / 'firmware', bundle_cfg['firmware_sha256'])
    FIRMWARE.mkdir(parents=True)
    for name in bundle_cfg['firmware_sha256']:
        shutil.copyfile(src / 'firmware' / name, FIRMWARE / name)
    check(FIRMWARE, bundle_cfg['firmware_sha256'])
    # RC1 package
    PACKAGE.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(src / 'package.tar') as t:
        t.extractall(PACKAGE.parent, filter='data')
    if sha(PACKAGE / 'package-sha256.json') != bundle_cfg['package_manifest_sha256']:
        raise RuntimeError('package manifest differs')
    check(PACKAGE, json.loads((PACKAGE / 'package-sha256.json').read_text()))
    # boot bundle
    hashes = json.loads((src / 'bundle/bundle-sha256.json').read_text())
    check(src / 'bundle', hashes)
    BUNDLE.mkdir(parents=True)
    for name in list(hashes) + ['bundle-sha256.json']:
        shutil.copyfile(src / 'bundle' / name, BUNDLE / name)
    check(BUNDLE, hashes)
    (BUNDLE / 'launcher.py').chmod(0o755)
    run(['systemd-analyze', 'verify', str(BUNDLE / 'sysone-rc1-init.service'), str(BUNDLE / 'sysone-rc1.service')])
    for name in ('sysone-rc1-init.service', 'sysone-rc1.service'):
        shutil.copyfile(BUNDLE / name, UNITS / name)
        (UNITS / name).chmod(0o644)
    if LAUNCHER.exists():
        raise RuntimeError('launcher already exists')
    shutil.copyfile(BUNDLE / 'launcher.py', LAUNCHER)
    LAUNCHER.chmod(0o755)
    if sha(LAUNCHER) != LAUNCHER_SHA:
        raise RuntimeError('launcher hash differs')
    print(json.dumps(dict(stage='files', passed=True)), flush=True)


def enable(_src):
    run(['systemctl', 'daemon-reload'])
    run(['systemctl', 'enable', 'sysone-rc1.service'])
    print(run(['systemctl', 'show', 'sysone-rc1.service', 'sysone-rc1-init.service', '-p', 'UnitFileState', '-p', 'ActiveState']))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('stage', choices=['memory', 'files', 'enable'])
    ap.add_argument('--src', type=Path, required=True)
    a = ap.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('run as root')
    dict(memory=memory, files=files, enable=enable)[a.stage](a.src)


if __name__ == '__main__':
    main()
