"""RC1.1: enable or disable lossless speculative decoding on the RC1 default service.

Runs on the KR260 as root. The sealed RC1 package, launcher, init unit and base
service unit stay unchanged. Speculation is a systemd drop-in that replaces only
ExecStart with firmware/rc1_spec/spec_service.py, which imports the sealed RC1
package and replaces only the decode loop (qualified 2026-11-18, 181/181 bit-identical).

  install --staged DIR   create /var/lib/sysone/rc1-spec-v1 from DIR (SHA-checked), then enable
  enable                 write the drop-in, restart RC1, require READY plus a speculative probe
  disable                remove the drop-in, restart RC1, require READY plus a plain probe
  status                 print the drop-in, ExecStart, health and bundle hashes

Any failure while enabling disables again (plain RC1) and requires that to come up READY.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

BUNDLE = Path('/var/lib/sysone/rc1-spec-v1')
BASE = Path('/var/lib/sysone/rc1-default-v1')
PACKAGE = Path('/var/lib/sysone/hardware-consolidated-rc1-20261108')
OUT = Path('/var/lib/sysone/qualifications/rc1-spec-20261118')
UNIT = Path('/etc/systemd/system/sysone-rc1.service')
DROPIN_DIR = Path('/etc/systemd/system/sysone-rc1.service.d')
DROPIN = DROPIN_DIR / '10-speculation.conf'
FILES = ('spec_service.py', 'spec_decode.py', '10-speculation.conf', 'config.json')
SOCKET = Path('/run/sysone-rc1/api.sock')
PROBE = 'Read /proc/version'


def run(args, check=True):
    r = subprocess.run(args, capture_output=True, text=True, timeout=360)
    print(json.dumps(dict(command=args, returncode=r.returncode, stdout=r.stdout[-4000:], stderr=r.stderr[-2000:])), flush=True)
    if check:
        r.check_returncode()
    return r.stdout


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def log(event, **kw):
    OUT.mkdir(parents=True, exist_ok=True)
    rec = dict(event=event, utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(), **kw)
    with (OUT / 'events.jsonl').open('a') as f:
        f.write(json.dumps(rec) + '\n')
    print(json.dumps(rec), flush=True)


def preflight():
    base = json.loads((BASE / 'bundle-sha256.json').read_text())
    if sha(UNIT) != base['sysone-rc1.service']:
        raise RuntimeError('Installed sysone-rc1.service differs from the rc1-default-v1 bundle')
    if sha(PACKAGE / 'package-sha256.json') != json.loads((BASE / 'config.json').read_text())['package_manifest_sha256']:
        raise RuntimeError('RC1 package manifest differs from rc1-default-v1 config')
    others = [p.name for p in DROPIN_DIR.iterdir() if p != DROPIN] if DROPIN_DIR.exists() else []
    if others:
        raise RuntimeError('Unexpected sysone-rc1 drop-ins: ' + ', '.join(others))


def check_bundle():
    manifest = json.loads((BUNDLE / 'bundle-sha256.json').read_text())
    for name in FILES:
        if sha(BUNDLE / name) != manifest[name]:
            raise RuntimeError('Bundle file changed: ' + name)
    return manifest


def probe(expect_spec):
    """READY gate (same as ExecStartPost), then one generation through the live socket."""
    run(['/usr/bin/python3', str(BASE / 'control.py'), 'wait-ready'])
    sys.path.insert(0, str(PACKAGE / 'scripts/v2'))
    from qwen_arm_service_candidate import exchange
    resp = exchange(SOCKET, dict(op='generate', query=PROBE, max_tokens=64, conversation_id='rc1-spec-probe', reset_cache=True))
    r = resp.get('result') or {}
    if not resp['ok'] or not r.get('complete') or (r.get('tool_result') or {}).get('path') != '/proc/version':
        raise RuntimeError('Probe generation failed: ' + json.dumps(resp)[:600])
    mode = r.get('speculate')
    if expect_spec and mode != 'adaptive':
        raise RuntimeError('Service is not running speculative decoding (speculate=%r)' % mode)
    if not expect_spec and mode is not None:
        raise RuntimeError('Plain RC1 expected but service reports speculate=%r' % mode)
    state = run(['systemctl', 'show', 'sysone-rc1.service', '-p', 'ActiveState', '-p', 'SubState', '-p', 'MainPID', '-p', 'NRestarts', '-p', 'ExecStart'])
    return dict(generated_ids=r['generated_ids'], text=r.get('generated_text'), speculate=mode,
                speculation=r.get('speculation'), decode_seconds=r.get('decode_seconds'), service=state)


def restart():
    run(['systemctl', 'daemon-reload'])
    run(['systemctl', 'stop', 'sysone-rc1.service'])     # drains; never SIGKILL (base unit)
    run(['systemctl', 'start', 'sysone-rc1.service'])    # ExecStartPost requires READY


def disable(reason='requested'):
    if DROPIN.exists():
        keep = OUT / 'disabled'
        keep.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DROPIN, keep / ('10-speculation.conf.' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())))
        DROPIN.unlink()
    if DROPIN_DIR.exists() and not any(DROPIN_DIR.iterdir()):
        DROPIN_DIR.rmdir()
    restart()
    p = probe(expect_spec=False)
    log('disabled', reason=reason, probe=p)
    return p


def enable():
    preflight()
    manifest = check_bundle()
    run(['systemd-analyze', 'verify', str(UNIT)])
    try:
        DROPIN_DIR.mkdir(exist_ok=True)
        tmp = DROPIN.with_suffix('.tmp')
        shutil.copyfile(BUNDLE / '10-speculation.conf', tmp)
        tmp.chmod(0o644)
        tmp.replace(DROPIN)
        restart()
        exec_start = run(['systemctl', 'show', 'sysone-rc1.service', '-p', 'ExecStart'])
        if str(BUNDLE / 'spec_service.py') not in exec_start:
            raise RuntimeError('Drop-in not in effect')
        p = probe(expect_spec=True)
    except BaseException as exc:
        log('enable_failed', error=type(exc).__name__ + ': ' + str(exc))
        disable(reason='automatic rollback after failed enable')
        raise
    log('enabled', bundle_sha256=manifest, dropin_sha256=sha(DROPIN), probe=p)
    return p


def install(staged):
    preflight()
    if BUNDLE.exists():
        raise RuntimeError('Bundle already exists; use enable')
    expected = json.loads((staged / 'bundle-sha256.json').read_text())
    for name in FILES:
        if sha(staged / name) != expected[name]:
            raise RuntimeError('Staged file does not match manifest: ' + name)
    if json.loads((staged / 'config.json').read_text())['package_manifest_sha256'] != sha(PACKAGE / 'package-sha256.json'):
        raise RuntimeError('RC1 package manifest differs from config')
    tmp = BUNDLE.with_name(BUNDLE.name + '.staging')
    tmp.mkdir()
    for name in FILES + ('bundle-sha256.json',):
        shutil.copyfile(staged / name, tmp / name)
        (tmp / name).chmod(0o644)
    tmp.rename(BUNDLE)
    log('installed', bundle_sha256=check_bundle())
    return enable()


def status():
    out = dict(dropin=DROPIN.exists(), dropin_sha256=sha(DROPIN) if DROPIN.exists() else None,
               bundle=check_bundle() if BUNDLE.exists() else None)
    out['service'] = run(['systemctl', 'show', 'sysone-rc1.service', '-p', 'ActiveState', '-p', 'SubState', '-p', 'MainPID', '-p', 'NRestarts', '-p', 'ExecStart', '-p', 'DropInPaths'])
    print(json.dumps(out, indent=1), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('install').add_argument('--staged', type=Path, required=True)
    sub.add_parser('enable'); sub.add_parser('disable'); sub.add_parser('status')
    a = ap.parse_args()
    if a.cmd == 'install':
        install(a.staged)
    elif a.cmd == 'enable':
        enable()
    elif a.cmd == 'disable':
        disable()
    else:
        status()
    print('RC1-SPEC ' + a.cmd.upper() + ': OK', flush=True)


if __name__ == '__main__':
    main()
