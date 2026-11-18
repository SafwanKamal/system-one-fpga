"""End-to-end service check on the board (root). Same query sequence through:
  rc1       - the installed RC1 service (sysone-rc1.service, its own socket)
  off       - spec_service.py --speculate off   (copied generate, plain decode)
  adaptive  - spec_service.py --speculate adaptive
Compares generated_ids/text/tool result per query; records client latency.
Leaves sysone-rc1.service running at the end, even on failure.

usage: python3 e2e.py --package PKG --queries Q.json --out DIR
"""
import argparse, json, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sh(*args, check=True):
    r = subprocess.run(list(args), capture_output=True, text=True, timeout=300)
    if check and r.returncode:
        raise RuntimeError(f'{args}: {r.stderr[-500:]}')
    return r.stdout


def run_queries(script, sock, queries, out):
    sys.path.insert(0, str(script.parent))
    import importlib.util
    spec = importlib.util.spec_from_file_location('rc1_client', script)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    rows = []
    for q in queries:
        req = dict(op='generate', query=q, max_tokens=64, conversation_id='e2e', reset_cache=False)
        t = time.monotonic(); resp = mod.exchange(sock, req); dt = time.monotonic() - t
        r = resp.get('result') or {}
        rows.append(dict(query=q, ok=resp['ok'], error=resp.get('error'), client_seconds=dt,
                         generated_ids=r.get('generated_ids'), text=r.get('generated_text'),
                         tool=(r.get('tool_result') or {}).get('path'), prefill_seconds=r.get('prefill_seconds'),
                         decode_seconds=r.get('decode_seconds'), reused=r.get('prefix_tokens_reused'),
                         speculation=r.get('speculation')))
        print(json.dumps(dict(phase=out, q=q[:40], ok=resp['ok'], s=round(dt, 3), n=len(r.get('generated_ids') or []))), flush=True)
    return rows


def wait_ready(path, proc, timeout=120):
    t = time.monotonic()
    while time.monotonic() - t < timeout:
        if path.exists():
            return
        if proc.poll() is not None:
            raise RuntimeError('spec service exited: ' + proc.stderr.read()[-1500:])
        time.sleep(.5)
    raise RuntimeError('spec service not ready')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package', type=Path, required=True)
    ap.add_argument('--queries', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=False)
    queries = json.loads(a.queries.read_text())['queries']
    client = a.package / 'scripts/v2/qwen_arm_service_candidate.py'
    res = dict(passed=False, boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(), phases={})
    try:
        sh('systemctl', 'start', 'sysone-rc1.service')
        res['phases']['rc1'] = run_queries(client, Path('/run/sysone-rc1/api.sock'), queries, 'rc1')
        sh('systemctl', 'stop', 'sysone-rc1.service')
        for mode in ('off', 'adaptive'):
            sock, ready = Path(f'/run/sysone-spec-{mode}.sock'), Path(f'/run/sysone-spec-{mode}.ready.json')
            ready.unlink(missing_ok=True)
            p = subprocess.Popen([sys.executable, '-u', str(HERE / 'spec_service.py'), 'serve', '--package', str(a.package),
                                  '--socket', str(sock), '--ready', str(ready), '--speculate', mode],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                wait_ready(ready, p)
                res['phases'][mode] = run_queries(client, sock, queries, mode)
            finally:
                try:
                    import importlib.util
                    spec = importlib.util.spec_from_file_location('rc1_client', client)
                    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
                    mod.exchange(sock, dict(op='shutdown'))
                except Exception as exc:
                    res.setdefault('shutdown_errors', []).append(f'{mode}: {exc}')
                try:
                    p.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    p.terminate(); p.wait(timeout=30)
        ref = res['phases']['rc1']
        cmp = {}
        for mode in ('off', 'adaptive'):
            rows = res['phases'][mode]
            cmp[mode] = dict(all_ok=all(r['ok'] for r in rows),
                             ids_equal=sum(r['generated_ids'] == x['generated_ids'] for r, x in zip(rows, ref)),
                             text_equal=sum(r['text'] == x['text'] for r, x in zip(rows, ref)),
                             tool_equal=sum(r['tool'] == x['tool'] for r, x in zip(rows, ref)), n=len(rows))
        res['compare_vs_rc1'] = cmp
        res['passed'] = all(r['ok'] for r in ref) and all(c['all_ok'] and c['ids_equal'] == c['n'] == c['text_equal'] == c['tool_equal'] for c in cmp.values())
    except Exception as exc:
        res['error'] = type(exc).__name__ + ': ' + str(exc)
    finally:
        subprocess.run(['systemctl', 'start', 'sysone-rc1.service'], timeout=300)
        res['rc1_after'] = sh('systemctl', 'show', '-p', 'ActiveState', '-p', 'SubState', 'sysone-rc1.service', check=False)
        (a.out / 'e2e.json').write_text(json.dumps(res, indent=1) + '\n')
        print('E2E RESULT: ' + ('PASS' if res['passed'] else 'FAIL') + (' ' + res['error'] if 'error' in res else ''), flush=True)


if __name__ == '__main__':
    main()
