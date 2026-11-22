"""Stage, activate, benchmark and roll back the RC1.4 pilot on a reserved KR260."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BUNDLE = Path('/var/lib/sysone/rc1-4-pilot')
BASE = Path('/var/lib/sysone/rc1-default-v1')
RC1 = Path('/var/lib/sysone/hardware-consolidated-rc1-20261108')
OUT = Path('/var/lib/sysone/qualifications/rc1-4')
FIRMWARE = Path('/lib/firmware/xilinx')
RC13 = Path('/etc/systemd/system/sysone-rc1.service.d/20-rc13.conf')
DROPIN = Path('/run/systemd/system/sysone-rc1.service.d/30-rc14-pilot.conf')
SOCKET = Path('/run/sysone-rc1/api.sock')
APP = 'sysone-qwen-decoder-v9i'
UNIT = 'sysone-rc1.service'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def check_bundle(root):
    manifest = load(root / 'bundle-sha256.json')
    for key, digest in manifest.items():
        path = root / key
        if not path.resolve().is_relative_to(root.resolve()) or sha(path) != digest:
            raise RuntimeError('Bundle file differs: ' + key)
    return manifest


def run(args):
    # RC1 has TimeoutStopSec=infinity and SendSIGKILL=no. Let it drain.
    subprocess.run([str(arg) for arg in args], check=True)


def systemctl(*args):
    run(['systemctl', *args])


def exchange(request):
    sys.path.insert(0, str(RC1 / 'scripts/v2'))
    from qwen_arm_service_candidate import exchange as send
    return send(SOCKET, request)


def probe(expect):
    run(['/usr/bin/python3', BASE / 'control.py', 'wait-ready'])
    response = exchange(dict(op='generate', query='Read /proc/version', max_tokens=64,
                             conversation_id='rc14-probe', reset_cache=True))
    result = response.get('result') or {}
    if (not response.get('ok') or not result.get('complete')
            or result.get('speculate') != expect
            or (result.get('tool_result') or {}).get('path') != '/proc/version'):
        raise RuntimeError('Unexpected probe result: ' + json.dumps(response)[:600])
    print(json.dumps(dict(speculate=expect, generated_ids=result['generated_ids'])), flush=True)


def stage(staged):
    check_bundle(staged)
    config = load(staged / 'config.json')
    package_manifest = RC1 / 'package-sha256.json'
    if sha(package_manifest) != config['rc1_package_manifest_sha256']:
        raise RuntimeError('RC1 package manifest differs')
    for target in (BUNDLE, FIRMWARE / APP):
        if target.exists():
            raise RuntimeError('Already staged: ' + str(target))

    # Build complete directories before publishing either one.
    BUNDLE.parent.mkdir(parents=True, exist_ok=True)
    FIRMWARE.mkdir(parents=True, exist_ok=True)
    with (tempfile.TemporaryDirectory(prefix='.rc14-', dir=BUNDLE.parent) as bundle_tmp,
          tempfile.TemporaryDirectory(prefix='.rc14-', dir=FIRMWARE) as firmware_tmp):
        bundle = Path(bundle_tmp) / 'bundle'
        firmware = Path(firmware_tmp) / APP
        shutil.copytree(staged, bundle)
        package = bundle / 'package'
        run(['cp', '-a', RC1, package])
        for key, digest in load(package_manifest).items():
            if sha(package / key) != digest:
                raise RuntimeError('RC1 package copy differs: ' + key)
        shutil.copyfile(bundle / 'registers-v9h.json', package / 'registers.json')
        shutil.copytree(bundle / APP, package / APP)
        shutil.copytree(bundle / APP, firmware)
        run(['dtc', '-@', '-I', 'dts', '-O', 'dtb', '-o', firmware / f'{APP}.dtbo',
             firmware / f'{APP}.dts'])
        check_bundle(bundle)
        firmware.rename(FIRMWARE / APP)
        try:
            bundle.rename(BUNDLE)
        except OSError:
            (FIRMWARE / APP).rename(firmware)
            raise
    print(json.dumps(dict(bundle=str(BUNDLE), firmware=str(FIRMWARE / APP))), flush=True)


def stop():
    systemctl('stop', UNIT)


def start():
    systemctl('start', UNIT)


def rollback():
    if not RC13.is_file():
        raise RuntimeError('RC1.3 drop-in missing')
    if DROPIN.exists():
        stop()  # RC1.4 ExecStopPost returns to v9e.
        run(['/usr/bin/python3', BUNDLE / 'rc14_image.py', 'down'])
        DROPIN.unlink()
    systemctl('daemon-reload')
    start()
    probe('rc1.3-costaware')


def enable():
    if not RC13.is_file() or DROPIN.exists():
        raise RuntimeError('Expected the persistent RC1.3 drop-in only')
    check_bundle(BUNDLE)
    probe('rc1.3-costaware')
    DROPIN.parent.mkdir(parents=True, exist_ok=True)
    pending = DROPIN.with_suffix('.tmp')
    shutil.copyfile(BUNDLE / DROPIN.name, pending)
    pending.chmod(0o644)
    stop()  # RC1.3 ExecStopPost returns to v9e.
    try:
        pending.replace(DROPIN)
        systemctl('daemon-reload')
        start()
        probe('rc1.4-costaware')
    except BaseException:
        rollback()
        raise


def bench(label, keep_cache=False):
    # Preserve the RC1.3 bench record and BENCH-JSON stdout formats.
    if not label or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in label):
        raise ValueError('Use a lowercase bench label with digits or hyphens')
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT / ('bench-' + label + '.json')
    if output.exists():
        raise FileExistsError(output)
    queries = load(BUNDLE / 'queries.json')
    results = []
    for i, query in enumerate(queries):
        tick = time.monotonic()
        response = exchange(dict(op='generate', query=query, max_tokens=64,
                                 conversation_id='rc14-bench-%d' % i, reset_cache=not keep_cache))
        row = response.get('result') or {}
        results.append(dict(query=query, ok=response['ok'], complete=row.get('complete'),
                            speculate=row.get('speculate'), prefix_tokens_reused=row.get('prefix_tokens_reused'),
                            generated_ids=row.get('generated_ids'), path=(row.get('tool_result') or {}).get('path'),
                            prefill_seconds=row.get('prefill_seconds'), decode_seconds=row.get('decode_seconds'),
                            elapsed_seconds=row.get('elapsed_seconds'), wall_seconds=time.monotonic() - tick,
                            speculation=row.get('speculation')))
    encoded = json.dumps(results)
    with output.open('x', encoding='utf-8') as stream:
        stream.write(encoded + '\n')
    print('BENCH-JSON ' + encoded, flush=True)
    if not all(row['ok'] and row['complete'] and row['speculate'] == 'rc1.4-costaware' for row in results):
        raise SystemExit('RC1.4 tool bench failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)
    for name in ('stage', 'install'):
        sub.add_parser(name).add_argument('--staged', required=True, type=Path)
    for name in ('enable', 'rollback', 'probe'):
        sub.add_parser(name)
    b = sub.add_parser('bench')
    b.add_argument('--label', required=True)
    b.add_argument('--keep-cache', action='store_true')
    args = parser.parse_args()
    if args.cmd in ('stage', 'install'):
        stage(args.staged)
    if args.cmd in ('enable', 'install'):
        enable()
    if args.cmd == 'rollback':
        rollback()
    if args.cmd == 'probe':
        probe('rc1.4-costaware')
    if args.cmd == 'bench':
        bench(args.label, args.keep_cache)


if __name__ == '__main__':
    main()
