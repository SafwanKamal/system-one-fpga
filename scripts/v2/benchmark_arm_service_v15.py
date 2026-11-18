"""Finite baseline/service v9d comparison, per-request SHA and no prefix reuse."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
from qwen_arm_service_v15 import exchange


def dump(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    server = None
    sock = out/'service.sock'
    def run(name, command, limit=600):
        with (out/(name+'.stdout')).open('wb') as stdout, (out/(name+'.stderr')).open('wb') as stderr:
            tick = time.monotonic()
            p = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=limit)
        if p.returncode:
            raise RuntimeError(name+' failed; inspect saved output')
        return time.monotonic()-tick
    def identity(name):
        run(name, ['flock', '-n', '/run/lock/sysone-inference.lock', sys.executable,
                   str(ROOT/'scripts/v2/inventory_prefix_v14.py')])
        return json.loads((out/(name+'.stdout')).read_text())
    def baseline(i, query):
        name=f'baseline-{i:02}'
        wall=run(name,[sys.executable,str(ROOT/'scripts/v2/run_qwen_fpga_command_v9d.py'),
                       '--package',str(args.package),'--query',query,'--max-tokens','64',
                       '--out',str(out/(name+'.json'))])
        r=json.loads((out/(name+'.json')).read_text())
        record(name,'baseline',query,r,wall)
    def record(name, arm, query, result, wall):
        if not result['complete'] or not result['resident_weights_verified'] or result['prefix_tokens_reused']:
            raise RuntimeError('Completion/verification/cache gate failed')
        row=dict(name=name,arm=arm,query=query,result=result,client_process_seconds=wall)
        rows.append(row)
        dump(out/'progress.json',dict(stage='running',requests=len(rows),last=name))
        print(json.dumps(dict(name=name,client_seconds=wall,verify_ms=result['model_verify_ms'])),flush=True)
    try:
        before=identity('inventory-before')
        dump(out/'source-sha256.json',{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
             for p in list((ROOT/'src/sysone/v2').glob('*v15.py'))+
             [ROOT/'src/sysone/v2/qwen_fpga_runtime_v9d.py',ROOT/'src/sysone/v2/qwen_tokenizer_v1.py',
              ROOT/'scripts/v2/run_qwen_fpga_command_v9d.py',Path(__file__),ROOT/'scripts/v2/qwen_arm_service_v15.py']})
        for phase in ('before',):
            run('fixture-'+phase,[sys.executable,str(ROOT/'scripts/v2/smoke_qwen_fpga_v9d.py'),
                                 '--package',str(args.package),'--out',str(out/('fixture-'+phase))])
        # Same three prompts twice per arm, with baseline blocks bracketing the service.
        queries=['Read '+p for p in ('/proc/sys/kernel/random/boot_id','/proc/uptime','/proc/version')]
        for i,q in enumerate(queries):baseline(i,q)
        with (out/'service.stdout').open('wb') as stdout,(out/'service.stderr').open('wb') as stderr:
            server=subprocess.Popen([sys.executable,'-u',str(ROOT/'scripts/v2/qwen_arm_service_v15.py'),'serve',
                '--package',str(args.package),'--socket',str(sock),'--ready',str(out/'ready.json')],
                stdout=stdout,stderr=stderr)
        deadline=time.monotonic()+45
        while not (out/'ready.json').exists():
            if server.poll() is not None or time.monotonic()>deadline:
                raise RuntimeError('Service did not become ready')
            time.sleep(.1)
        # Invalid requests must not poison a healthy session.
        rejection=exchange(sock,dict(op='generate',query='x',max_tokens=0))
        if rejection['ok'] or exchange(sock,dict(op='health'))['state']!='READY':
            raise RuntimeError('Request rejection lifecycle failed')
        dump(out/'invalid-request.json',rejection)
        for i,q in enumerate(queries+list(reversed(queries))):
            name=f'service-{i:02}'
            wall=run(name,[sys.executable,str(ROOT/'scripts/v2/qwen_arm_service_v15.py'),'request',
                          '--socket',str(sock),'--query',q,'--max-tokens','64','--out',str(out/(name+'.json'))])
            response=json.loads((out/(name+'.json')).read_text())
            if not response['ok']:raise RuntimeError('Service generation failed')
            r=response['result']
            if r['verified_bytes']!=639446688:raise RuntimeError('Incomplete resident verification')
            record(name,'service',q,r,wall)
        shutdown=exchange(sock,dict(op='shutdown'));dump(out/'shutdown.json',shutdown)
        if not shutdown['ok']:raise RuntimeError('Shutdown refused')
        server.wait(timeout=15)
        if server.returncode or sock.exists():raise RuntimeError('Service cleanup failed')
        server=None
        for i,q in enumerate(reversed(queries),3):baseline(i,q)
        for q in queries:
            group=[r for r in rows if r['query']==q]
            ref=group[0]['result']
            for r in group:
                if any(r['result'][k]!=ref[k] for k in ('prompt_ids','generated_ids','generated_text','call')):
                    raise RuntimeError('Exact output parity failed for '+r['name'])
        run('fixture-after',[sys.executable,str(ROOT/'scripts/v2/smoke_qwen_fpga_v9d.py'),
                            '--package',str(args.package),'--out',str(out/'fixture-after')])
        after=identity('inventory-after')
        if before!=after:raise RuntimeError('Board identity changed')
        summary=dict(passed=True,requests=len(rows),exact_output_parity=True,
                     prefix_cache=False,verification='full resident SHA256 before each request',
                     service_startup_seconds=json.loads((out/'ready.json').read_text())['startup_seconds'],
                     full_sweep_started=False,fpga_resource_change=0,by_query=[])
        for q in queries:
            groups={a:[r for r in rows if r['query']==q and r['arm']==a] for a in ('baseline','service')}
            times={a:statistics.mean(r['client_process_seconds'] for r in g) for a,g in groups.items()}
            summary['by_query'].append(dict(query=q,client_mean_seconds=times,
                saved_seconds=times['baseline']-times['service'],
                reduction_percent=100*(1-times['service']/times['baseline']),
                verify_mean_ms={a:statistics.mean(r['result']['model_verify_ms'] for r in g) for a,g in groups.items()},
                runtime_mean_seconds={a:statistics.mean(r['result']['elapsed_seconds'] for r in g) for a,g in groups.items()}))
        means={a:statistics.mean(r['client_process_seconds'] for r in rows if r['arm']==a) for a in ('baseline','service')}
        summary.update(client_mean_seconds=means,saved_seconds=means['baseline']-means['service'],
                       reduction_percent=100*(1-means['service']/means['baseline']))
        dump(out/'requests.json',rows);dump(out/'summary.json',summary)
        dump(out/'progress.json',dict(stage='complete',requests=len(rows)))
        print(json.dumps(summary),flush=True)
    except BaseException as exc:
        dump(out/'requests.json',rows)
        dump(out/'failure.json',dict(error=type(exc).__name__+': '+str(exc),requests=len(rows)))
        if server is not None and server.poll() is None:
            # Ask for a quiescent shutdown; never forcibly kill an in-flight FPGA owner.
            try:
                response=exchange(sock,dict(op='shutdown'),timeout=150)
                dump(out/'failure-shutdown.json',response)
                if response['ok']:server.wait(timeout=15)
            except Exception:
                pass
        raise


if __name__=='__main__':
    main()
