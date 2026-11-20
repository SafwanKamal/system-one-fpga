"""RC1.3: enable or disable the v9h + cost-aware speculative service on the RC1 default service.

Runs on the KR260 as root, on top of RC1.1 (drop-in 10-speculation.conf stays). RC1.3 is a
second drop-in, 20-rc13.conf: switch to v9h before start, run spec_service_rc13.py, switch
back to v9e after stop. RC1.2's drop-in 20-rc12.conf is moved aside while RC1.3 is enabled
(both would stack their image switches) and restored on disable, so disabling returns to
RC1.2 if it was enabled, else to RC1.1. The service is always stopped under the old unit
before the drop-ins change, so each unit's ExecStopPost sees its own image.

  install --staged DIR   create /var/lib/sysone/rc1-3-v1 (bundle + package copy with the v9h app), then enable
  update --staged DIR    replace the installed bundle's own files (not the package copy) and restart; rolls back on failure
  enable | disable | status
  bench --label L [--keep-cache]   run the tool queries in queries.json through the live socket -> OUT/bench-L.json
                         (default reset_cache=True per query; --keep-cache sends new conversations without reset)

Any failure while enabling disables again and requires RC1.1 to come up READY.
"""
import argparse, hashlib, json, shutil, subprocess, sys, time
from pathlib import Path

BUNDLE = Path('/var/lib/sysone/rc1-3-v1')
BASE = Path('/var/lib/sysone/rc1-default-v1')
RC1 = Path('/var/lib/sysone/hardware-consolidated-rc1-20261108')
OUT = Path('/var/lib/sysone/qualifications/rc1-3')
DROPIN_DIR = Path('/etc/systemd/system/sysone-rc1.service.d')
DROPIN = DROPIN_DIR / '20-rc13.conf'
RC11 = DROPIN_DIR / '10-speculation.conf'
RC12 = DROPIN_DIR / '20-rc12.conf'
RC12_SAVED = OUT / 'rc12-dropin'
SOCKET = Path('/run/sysone-rc1/api.sock')
V9H = 'sysone-qwen-decoder-v9h'


def run(args, check=True):
    r = subprocess.run(args, capture_output=True, text=True, timeout=600)
    print(json.dumps(dict(command=args, returncode=r.returncode, stdout=r.stdout[-3000:], stderr=r.stderr[-2000:])), flush=True)
    if check:
        r.check_returncode()
    return r.stdout


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def log(event, **kw):
    OUT.mkdir(parents=True, exist_ok=True)
    rec = dict(event=event, utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(), **kw)
    with (OUT / 'events.jsonl').open('a') as f:
        f.write(json.dumps(rec) + '\n')
    print(json.dumps(rec)[:2000], flush=True)


def check_bundle(root=BUNDLE):
    m = json.loads((root / 'bundle-sha256.json').read_text())
    bad = [k for k, v in m.items() if sha(root / k) != v]
    if bad:
        raise RuntimeError('Bundle files differ: ' + ', '.join(bad))
    return m


def exchange(req):
    sys.path.insert(0, str(RC1 / 'scripts/v2'))
    from qwen_arm_service_candidate import exchange as ex
    return ex(SOCKET, req)


def probe(expect):
    run(['/usr/bin/python3', str(BASE / 'control.py'), 'wait-ready'])
    resp = exchange(dict(op='generate', query='Read /proc/version', max_tokens=64, conversation_id='rc13-probe', reset_cache=True))
    r = resp.get('result') or {}
    if not resp['ok'] or not r.get('complete') or (r.get('tool_result') or {}).get('path') != '/proc/version':
        raise RuntimeError('Probe failed: ' + json.dumps(resp)[:600])
    if r.get('speculate') != expect:
        raise RuntimeError('Expected speculate=%r, got %r' % (expect, r.get('speculate')))
    return dict(generated_ids=r['generated_ids'], speculate=r.get('speculate'), decode_seconds=r.get('decode_seconds'))


def image(direction):
    run(['/usr/bin/python3', str(BUNDLE / 'rc13_image.py'), direction])


def disable(reason='requested'):
    run(['systemctl', 'stop', 'sysone-rc1.service'], check=False)   # RC1.3 ExecStopPost -> v9e
    image('down')                      # make sure v9e is active even if the stop hook failed
    if DROPIN.exists():
        keep = OUT / 'disabled'; keep.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DROPIN, keep / ('20-rc13.conf.' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())))
        DROPIN.unlink()
    expect = 'adaptive'
    if RC12_SAVED.exists():
        tmp = RC12.with_suffix('.tmp'); shutil.copyfile(RC12_SAVED, tmp); tmp.chmod(0o644); tmp.replace(RC12)
        RC12_SAVED.unlink(); expect = 'rc1.2-costaware'
    run(['systemctl', 'daemon-reload'])
    run(['systemctl', 'start', 'sysone-rc1.service'])
    p = probe(expect)
    log('disabled', reason=reason, probe=p)
    return p


def enable():
    if not RC11.exists():
        raise RuntimeError('RC1.1 drop-in missing; RC1.3 layers on RC1.1')
    check_bundle()
    try:
        run(['systemctl', 'stop', 'sysone-rc1.service'])   # old unit's ExecStopPost (RC1.2 -> v9e)
        if RC12.exists():
            OUT.mkdir(parents=True, exist_ok=True)
            shutil.copy2(RC12, RC12_SAVED); RC12.unlink()
        tmp = DROPIN.with_suffix('.tmp')
        shutil.copyfile(BUNDLE / '20-rc13.conf', tmp); tmp.chmod(0o644); tmp.replace(DROPIN)
        run(['systemctl', 'daemon-reload'])
        run(['systemctl', 'start', 'sysone-rc1.service'])
        p = probe('rc1.3-costaware')
    except BaseException as exc:
        log('enable_failed', error=type(exc).__name__ + ': ' + str(exc))
        disable('automatic rollback after failed enable')
        raise
    log('enabled', dropin_sha256=sha(DROPIN), probe=p)
    return p


def install(staged):
    if BUNDLE.exists():
        raise RuntimeError('Bundle exists; use enable')
    check_bundle(staged)
    cfg = json.loads((staged / 'config.json').read_text())
    if sha(RC1 / 'package-sha256.json') != cfg['rc1_package_manifest_sha256']:
        raise RuntimeError('RC1 package manifest differs')
    tmp = BUNDLE.with_name(BUNDLE.name + '.staging')
    shutil.copytree(staged, tmp, symlinks=False)
    run(['cp', '-a', str(RC1), str(tmp / 'package')])
    shutil.copytree(staged / V9H, tmp / 'package' / V9H)
    m = json.loads((RC1 / 'package-sha256.json').read_text())
    bad = [k for k, v in m.items() if sha(tmp / 'package' / k) != v]
    if bad:
        raise RuntimeError('Package copy differs: ' + ', '.join(bad[:5]))
    shutil.copyfile(staged / 'registers-v9h.json', tmp / 'package' / 'registers.json')   # model_b 0x70, scratch 0x7c
    tmp.rename(BUNDLE)
    log('installed', bundle_sha256=check_bundle())
    return enable()


def bench(label, keep_cache=False):
    queries = json.loads((Path(__file__).resolve().parent / 'queries.json').read_text())
    res = []
    for i, q in enumerate(queries):
        t = time.monotonic()
        resp = exchange(dict(op='generate', query=q, max_tokens=64, conversation_id='rc13-bench-%d' % i, reset_cache=not keep_cache))
        r = resp.get('result') or {}
        res.append(dict(query=q, ok=resp['ok'], complete=r.get('complete'), speculate=r.get('speculate'), prefix_tokens_reused=r.get('prefix_tokens_reused'),
                        generated_ids=r.get('generated_ids'), path=(r.get('tool_result') or {}).get('path'),
                        prefill_seconds=r.get('prefill_seconds'), decode_seconds=r.get('decode_seconds'),
                        elapsed_seconds=r.get('elapsed_seconds'), wall_seconds=time.monotonic() - t, speculation=r.get('speculation')))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / ('bench-' + label + '.json')).write_text(json.dumps(res) + '\n')
    print(json.dumps(dict(label=label, n=len(res), ok=sum(bool(x['complete']) for x in res),
                          decode=round(sum(x['decode_seconds'] or 0 for x in res), 3),
                          elapsed=round(sum(x['elapsed_seconds'] or 0 for x in res), 3))), flush=True)
    print('BENCH-JSON ' + json.dumps(res), flush=True)


def update(staged):
    if not BUNDLE.exists() or not DROPIN.exists():
        raise RuntimeError('RC1.3 not installed and enabled')
    new = check_bundle(staged)
    cfg = json.loads((staged / 'config.json').read_text())
    if sha(RC1 / 'package-sha256.json') != cfg['rc1_package_manifest_sha256']:
        raise RuntimeError('RC1 package manifest differs')
    old = check_bundle()
    backup = OUT / ('bundle-backup-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()))
    backup.mkdir(parents=True)
    old = list(old) + ['bundle-sha256.json']
    for k in old:
        (backup / k).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(BUNDLE / k, backup / k)
    def put(src, names):
        for k in names:
            (BUNDLE / k).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src / k, BUNDLE / k)
    run(['systemctl', 'stop', 'sysone-rc1.service'])
    try:
        put(staged, list(new) + ['bundle-sha256.json'])
        check_bundle()
        shutil.copyfile(BUNDLE / '20-rc13.conf', DROPIN)
        run(['systemctl', 'daemon-reload'])
        run(['systemctl', 'start', 'sysone-rc1.service'])
        p = probe('rc1.3-costaware')
    except BaseException as exc:
        log('update_failed', error=type(exc).__name__ + ': ' + str(exc))
        run(['systemctl', 'stop', 'sysone-rc1.service'], check=False)
        put(backup, old)
        shutil.copyfile(BUNDLE / '20-rc13.conf', DROPIN)
        run(['systemctl', 'daemon-reload'])
        run(['systemctl', 'start', 'sysone-rc1.service'])
        probe('rc1.3-costaware')
        raise
    log('updated', bundle_sha256=check_bundle(), probe=p)
    return p


def status():
    out = dict(rc11=RC11.exists(), rc12=RC12.exists(), rc12_saved=RC12_SAVED.exists(), rc13=DROPIN.exists(), bundle=check_bundle() if BUNDLE.exists() else None)
    out['service'] = run(['systemctl', 'show', 'sysone-rc1.service', '-p', 'ActiveState', '-p', 'SubState', '-p', 'MainPID',
                          '-p', 'NRestarts', '-p', 'ExecStart', '-p', 'DropInPaths'])
    print(json.dumps(out, indent=1), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('install').add_argument('--staged', type=Path, required=True)
    b = sub.add_parser('bench'); b.add_argument('--label', required=True); b.add_argument('--keep-cache', action='store_true')
    sub.add_parser('update').add_argument('--staged', type=Path, required=True)
    for c in ('enable', 'disable', 'status'):
        sub.add_parser(c)
    a = ap.parse_args()
    {'install': lambda: install(a.staged), 'update': lambda: update(a.staged), 'bench': lambda: bench(a.label, a.keep_cache), 'enable': enable,
     'disable': disable, 'status': status}[a.cmd]()
    print('RC1.3 ' + a.cmd.upper() + ': OK', flush=True)


if __name__ == '__main__':
    main()
