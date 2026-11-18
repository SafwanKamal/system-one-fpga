"""RC1.1 service check (board, root): the same request sequence against whatever
sysone-rc1.service is currently running, through its live socket and the default CLI.

Sequence: 21 tool queries x 3 passes
  warm1  conversation 'ship', prefix reuse on
  cold   reset_cache=True on every request (cold prefill)
  warm2  conversation 'ship' again (drafter history is now warm in RC1.1)
then 3 queries through `sysone-qwen-fpga --query` (the default command).

usage: python3 svc_check.py --queries Q.json --label NAME --out DIR
"""
import argparse, json, subprocess, sys, time
from pathlib import Path

PACKAGE = Path('/var/lib/sysone/hardware-consolidated-rc1-20261108')
SOCKET = Path('/run/sysone-rc1/api.sock')
CLI = ['3:Read /proc/version', '10:What does /proc/uptime contain?', '19:Get /proc/sys/kernel/random/boot_id for me']


def sh(*a):
    return subprocess.run(list(a), capture_output=True, text=True, timeout=300).stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--queries', type=Path, required=True)
    ap.add_argument('--label', required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(PACKAGE / 'scripts/v2'))
    from qwen_arm_service_candidate import exchange
    queries = json.loads(a.queries.read_text())['queries']
    res = dict(label=a.label, passed=False, boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
               started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               service_before=sh('systemctl', 'show', 'sysone-rc1.service', '-p', 'ActiveState', '-p', 'SubState', '-p', 'MainPID',
                                 '-p', 'NRestarts', '-p', 'ExecStart', '-p', 'DropInPaths'),
               health=exchange(SOCKET, dict(op='health')), rows=[])
    try:
        for phase in ('warm1', 'cold', 'warm2'):
            for i, q in enumerate(queries):
                req = dict(op='generate', query=q, max_tokens=64, conversation_id='ship', reset_cache=phase == 'cold')
                t = time.monotonic(); resp = exchange(SOCKET, req); dt = time.monotonic() - t
                r = resp.get('result') or {}
                row = dict(phase=phase, i=i, query=q, ok=resp['ok'], error=resp.get('error'), client_seconds=dt,
                           generated_ids=r.get('generated_ids'), text=r.get('generated_text'), complete=r.get('complete'),
                           call=r.get('call'), tool=(r.get('tool_result') or {}).get('path'), reused=r.get('prefix_tokens_reused'),
                           prefill_seconds=r.get('prefill_seconds'), decode_seconds=r.get('decode_seconds'),
                           speculate=r.get('speculate'), speculation=r.get('speculation'))
                res['rows'].append(row)
                print(json.dumps(dict(phase=phase, i=i, ok=row['ok'], n=len(row['generated_ids'] or []), reused=row['reused'],
                                      s=round(dt, 3), spec=row['speculate'])), flush=True)
        for item in CLI:
            i, q = item.split(':', 1)
            p = a.out / f'cli-{i}.json'
            t = time.monotonic()
            cp = subprocess.run(['sysone-qwen-fpga', '--query', q, '--out', str(p), '--max-tokens', '64'], capture_output=True, text=True, timeout=300)
            r = json.loads(p.read_text()) if p.exists() else {}
            res['rows'].append(dict(phase='cli', i=int(i), query=q, ok=cp.returncode == 0 and bool(r.get('complete')), error=cp.stderr[-300:] or None,
                                    client_seconds=time.monotonic() - t, generated_ids=r.get('generated_ids'), text=r.get('generated_text'),
                                    complete=r.get('complete'), call=r.get('call'), tool=(r.get('tool_result') or {}).get('path'),
                                    reused=r.get('prefix_tokens_reused'), speculate=r.get('speculate')))
        res['passed'] = all(r['ok'] and r['complete'] for r in res['rows'])
    except Exception as exc:
        res['error'] = type(exc).__name__ + ': ' + str(exc)
    finally:
        res['service_after'] = sh('systemctl', 'show', 'sysone-rc1.service', '-p', 'ActiveState', '-p', 'SubState', '-p', 'MainPID', '-p', 'NRestarts')
        res['finished_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        (a.out / 'svc.json').write_text(json.dumps(res) + '\n')
        print('SVC RESULT: ' + ('PASS' if res['passed'] else 'FAIL') + (' ' + res['error'] if 'error' in res else ''), flush=True)


if __name__ == '__main__':
    main()
