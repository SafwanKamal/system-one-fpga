"""Finite diagnostic/startup/cache ablation on one sealed v9d FPGA system."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from qwen_arm_service_v16 import exchange
from load_sealed_qwen_v16 import load,assert_idle
from sysone.v2.qwen_dma_ownership_v16 import ownership


def dump(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def inventory():
    from inventory_prefix_v14 import inventory as snapshot
    with Path('/run/lock/sysone-inference.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        assert_idle()
        d=snapshot()
        if d['active_fpga_app']!='sysone-qwen-decoder-v9d' or d['benchmark_processes'] or d['r5_loaded']:
            raise RuntimeError('Unexpected live deployment/clients')
        d['ownership']=ownership()
        if not d['ownership']['sealed'] or d['ownership']['loading'] or d['ownership']['owner_tgid'] or d['ownership']['vmas']:
            raise RuntimeError('Weights not sealed and quiescent')
        return d


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package',type=Path,required=True)
    ap.add_argument('--model',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();out=a.out;out.mkdir(parents=True,exist_ok=False)
    rows=[];references={};phase_startups=[];server=None;sock=None
    queries=['Read '+p for p in ('/proc/sys/kernel/random/boot_id','/proc/uptime','/proc/version')]
    def run(name,args,limit=600):
        with (out/(name+'.stdout')).open('wb') as stdout,(out/(name+'.stderr')).open('wb') as stderr:
            tick=time.monotonic();p=subprocess.run(args,stdout=stdout,stderr=stderr,timeout=limit)
        if p.returncode:raise RuntimeError(name+' failed; inspect saved outputs')
        return time.monotonic()-tick
    def progress(name):
        dump(out/'progress.json',dict(stage='running',last=name,requests=len(rows)))
        print(json.dumps(dict(event=name,requests=len(rows))),flush=True)
    def check(q,r):
        if not r['complete']:raise RuntimeError('Incomplete result')
        if q not in references:references[q]=r
        if any(r[k]!=references[q][k] for k in ('prompt_ids','generated_ids','generated_text','call')):
            raise RuntimeError('Exact output mismatch')
    def phase(label,verification,cache,sequence):
        nonlocal server,sock
        directory=out/label;directory.mkdir();sock=directory/'api.sock'
        command=[sys.executable,'-u',str(ROOT/'scripts/v2/qwen_arm_service_v16.py'),'serve',
                 '--package',str(a.package),'--socket',str(sock),'--ready',str(directory/'ready.json'),
                 '--verification',verification]
        if not cache:command.append('--no-prefix-cache')
        with (directory/'server.stdout').open('wb') as stdout,(directory/'server.stderr').open('wb') as stderr:
            server=subprocess.Popen(command,stdout=stdout,stderr=stderr)
        deadline=time.monotonic()+45
        while not (directory/'ready.json').exists():
            if server.poll() is not None or time.monotonic()>deadline:raise RuntimeError(label+' startup failed')
            time.sleep(.05)
        ready=json.loads((directory/'ready.json').read_text());phase_startups.append(dict(phase=label,**ready))
        if ready['startup_proof']['verified_bytes']!=639446688:raise RuntimeError('Startup coverage failed')
        for i,q in enumerate(sequence):
            name=label+'-'+str(i)
            wall=run(name,[sys.executable,str(ROOT/'scripts/v2/qwen_arm_service_v16.py'),'request',
                '--socket',str(sock),'--query',q,'--out',str(out/(name+'.json'))])
            response=json.loads((out/(name+'.json')).read_text())
            if not response['ok']:raise RuntimeError('Generation failed: '+str(response))
            r=response['result'];check(q,r)
            if r['request_weights_hashed']!=(verification=='per-request'):raise RuntimeError('Wrong verification mode')
            if r['verified_bytes']!=(639446688 if verification=='per-request' else 0):raise RuntimeError('Wrong hash coverage')
            if r['work']['prefill_tokens']!=len(r['prompt_ids'])-r['prefix_tokens_reused']:raise RuntimeError('Cache work mismatch')
            if not cache and r['prefix_tokens_reused']:raise RuntimeError('Unexpected cache')
            if cache and i==0 and r['prefix_tokens_reused']:raise RuntimeError('Reuse crossed service restart')
            if cache and i>0 and not r['prefix_tokens_reused']:raise RuntimeError('Expected common prefix not reused')
            arm='cached' if cache else verification
            rows.append(dict(name=name,arm=arm,query=q,result=r,client_process_seconds=wall))
            progress(name)
        if cache:
            checks=[]
            for tag,request,expect in [
                ('conversation-switch',dict(op='generate',query=queries[0],conversation_id='other'),0),
                ('identical',dict(op='generate',query=queries[0],conversation_id='other'),None),
                ('explicit-reset',dict(op='generate',query=queries[0],conversation_id='other',reset_cache=True),0),
                ('changed-prefix',dict(op='generate',query=queries[1],conversation_id='other'),None)]:
                response=exchange(sock,request);dump(directory/(tag+'.json'),response)
                if not response['ok']:raise RuntimeError('Cache qualification failure')
                r=response['result'];check(request['query'],r)
                if (expect==0 and r['prefix_tokens_reused']) or (expect is None and not r['prefix_tokens_reused']):
                    raise RuntimeError('Wrong reuse after '+tag)
                checks.append(dict(check=tag,passed=True,reused=r['prefix_tokens_reused']))
            invalid=exchange(sock,dict(op='generate',query='x '*1000,max_tokens=128))
            if invalid['ok'] or exchange(sock,dict(op='health'))['state']!='READY':raise RuntimeError('Capacity rejection faulted service')
            dump(directory/'capacity-rejection.json',invalid)
            dump(directory/'cache-qualification.json',dict(passed=True,checks=checks))
        response=exchange(sock,dict(op='shutdown'));dump(directory/'shutdown.json',response)
        if not response['ok']:raise RuntimeError('Shutdown refused')
        server.wait(timeout=15)
        if server.returncode or sock.exists():raise RuntimeError('Service cleanup failed')
        server=None
    try:
        before=inventory();dump(out/'inventory-before.json',before)
        sources=list((ROOT/'src/sysone/v2').glob('*v16.py'))+list((ROOT/'scripts/v2').glob('*v16.py'))
        sources += [ROOT/'src/sysone/v2/prefix_cache_v14.py',ROOT/'firmware/qwen_dma_v2/sysone_qwen_dma_v2.c']
        hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
        dump(out/'source-sha256.json',hashes)
        run('fixture-before',[sys.executable,str(ROOT/'scripts/v2/smoke_qwen_fpga_v16.py'),
                             '--package',str(a.package),'--out',str(out/'fixture-before')])
        phase('diag-before','per-request',False,queries)
        # A controlled same-model reload proves transition invalidation/reverification.
        with Path('/run/lock/sysone-inference.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            proof=load(a.package,a.model)
            if proof['ownership']['instance']!=before['ownership']['instance'] or proof['ownership']['generation']<=before['ownership']['generation']:
                raise RuntimeError('Reload did not advance generation')
            dump(out/'transition-proof.json',proof)
        phase('startup-before','startup',False,queries)
        phase('cached','startup',True,queries+list(reversed(queries)))
        phase('startup-after','startup',False,list(reversed(queries)))
        phase('diag-after','per-request',False,list(reversed(queries)))
        run('fixture-after',[sys.executable,str(ROOT/'scripts/v2/smoke_qwen_fpga_v16.py'),
                            '--package',str(a.package),'--out',str(out/'fixture-after')])
        after=inventory();dump(out/'inventory-after.json',after)
        if {k:v for k,v in before.items() if k!='ownership'}!={k:v for k,v in after.items() if k!='ownership'}:
            raise RuntimeError('Board identity changed outside declared transition')
        if any(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=h for n,h in hashes.items()):raise RuntimeError('Source changed')
        means={arm:statistics.mean(r['client_process_seconds'] for r in rows if r['arm']==arm) for arm in ('per-request','startup','cached')}
        summary=dict(passed=True,requests=len(rows),exact_output_parity=True,client_mean_seconds=means,
            verification_saved_seconds=means['per-request']-means['startup'],
            cache_saved_seconds=means['startup']-means['cached'],
            total_reduction_percent=100*(1-means['cached']/means['per-request']),
            prefix_reused_tokens=sum(r['result']['prefix_tokens_reused'] for r in rows if r['arm']=='cached'),
            startup_records=phase_startups,full_sweep_started=False,fpga_resource_change=0)
        summary['components']={arm:{key:statistics.mean(r['result'][key] for r in rows if r['arm']==arm)
            for key in ('model_verify_ms','prefill_seconds','decode_seconds','elapsed_seconds')} for arm in means}
        summary['by_query']=[dict(query=q,mean_seconds={arm:statistics.mean(r['client_process_seconds'] for r in rows if r['arm']==arm and r['query']==q) for arm in means}) for q in queries]
        dump(out/'requests.json',rows);dump(out/'summary.json',summary)
        dump(out/'progress.json',dict(stage='complete',requests=len(rows)))
        print(json.dumps(summary),flush=True)
    except BaseException as exc:
        dump(out/'requests.json',rows);dump(out/'failure.json',dict(error=type(exc).__name__+': '+str(exc),requests=len(rows)))
        if server is not None and server.poll() is None:
            try:
                response=exchange(sock,dict(op='shutdown'),timeout=150);dump(out/'failure-shutdown.json',response)
                if response['ok']:server.wait(timeout=15)
            except Exception:pass
        raise


if __name__=='__main__':main()
