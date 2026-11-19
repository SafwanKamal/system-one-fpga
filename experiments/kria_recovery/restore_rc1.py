"""Restore the qualified RC1 deployment onto a freshly flashed KR260 (run as root on the board).

Stages, in order (each refuses to overwrite a target that differs):
  policy   - update policy: no unattended upgrades, needrestart list-only and never for sysone-*.
             Run first: a fresh card restarts services after every library upgrade.
  memory   - /etc/sysone/kr260-memory.json (0x60000000, 256 MiB) + reserved-memory kernel hooks
  files    - v9e FPGA app, RC1 package, rc1-default-v1 bundle, units, launcher; verifies every pinned hash
  enable   - systemd daemon-reload and enable sysone-rc1.service (starts on next boot)
  (reboot; plain RC1 comes up READY)
  spec     - RC1.1: installs <src>/rc1_spec (firmware/rc1_spec from the repo plus
             scripts/v2/install_rc1_spec.py) and enables speculative decoding
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


# Update policy deployed 2026-11-18 (user-approved). Contents and hashes match the live board.
POLICY = {
    Path('/etc/apt/apt.conf.d/99sysone-no-auto-upgrade'): (
        '// sysone (2026-11-18): no unattended installs; upgrade by hand in a maintenance window with RC1 drained.\n'
        'APT::Periodic::Unattended-Upgrade "0";\n'
        'APT::Periodic::Download-Upgradeable-Packages "0";\n',
        'f864cd0a8878873d8bb0a76e3a4bbda9e49ac83a9b72a722a5bfdb9b21a7d227'),
    Path('/etc/needrestart/conf.d/99-sysone.conf'): (
        '# sysone (2026-11-18): never auto-restart services after upgrades; list only.\n'
        "$nrconf{restart} = 'l';\n"
        '# never restart RC1 or test units, even from an interactive prompt\n'
        '$nrconf{override_rc}{qr(^sysone-)} = 0;\n'
        '$nrconf{override_rc}{qr(^spec-qual)} = 0;\n',
        'fd1af7e560c36fd630f05ec76e752655064012287b7b981b75f3caf1d6cd171e'),
}


def policy(_src):
    for path, (text, digest) in POLICY.items():
        if hashlib.sha256(text.encode()).hexdigest() != digest:
            raise RuntimeError('embedded policy text differs from its pin: ' + str(path))
        if path.exists():
            if sha(path) != digest:
                raise RuntimeError('policy file exists with other content: ' + str(path))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + '.tmp')
        tmp.write_text(text)
        tmp.chmod(0o644)
        tmp.replace(path)
        if sha(path) != digest:
            raise RuntimeError('policy file hash differs after write: ' + str(path))
    if subprocess.run(['perl', '-c', str(next(p for p in POLICY if 'needrestart' in str(p)))],
                      capture_output=True).returncode != 0:
        raise RuntimeError('needrestart policy does not parse')
    print(run(['apt-config', 'dump', 'APT::Periodic']))
    print(json.dumps(dict(stage='policy', passed=True)), flush=True)


def spec(src):
    """RC1.1 on top of a READY plain RC1 (after the post-enable reboot)."""
    staged = src / 'rc1_spec'
    run([sys.executable, str(staged / 'install_rc1_spec.py'), 'install', '--staged', str(staged)])
    print(json.dumps(dict(stage='spec', passed=True)), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('stage', choices=['policy', 'memory', 'files', 'enable', 'spec'])
    ap.add_argument('--src', type=Path, required=True)
    a = ap.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('run as root')
    dict(policy=policy, memory=memory, files=files, enable=enable, spec=spec)[a.stage](a.src)


if __name__ == '__main__':
    main()
