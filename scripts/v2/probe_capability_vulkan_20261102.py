"""Bounded local GPU runtime probe on development inputs only."""
import importlib.util
import json
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('runner',ROOT/'scripts/v2/capability_comparison_20261102.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
r.WORK=ROOT/'build/v2/model-capability-20261102-r2';r.PORT=18193
folder=r.WORK/'vulkan-qualification';folder.mkdir(exist_ok=True)
model=next(x for x in r.rows_json(r.WORK/'models.json') if x['key']=='qwen4-q4')
exe=ROOT/'build/v2/model-capability-runtime-vulkan-b11540/bin/llama-server.exe'
args=[str(exe),'-m',model['path'],'--host','127.0.0.1','--port',str(r.PORT),'-ngl','99',
      '-c','2048','-np','1','-t','4','-tb','4','-b','512','-ub','512','--jinja','--no-context-shift','--cache-ram','0','--reasoning-budget','0']
with (folder/'server.log').open('ab') as log:
    process=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:
        for _ in range(150):
            if process.poll() is not None:raise RuntimeError('GPU server exited')
            try:
                if r.local_get('/health')['status']=='ok':break
            except Exception:time.sleep(1)
        else:raise TimeoutError('GPU startup timeout')
        r.CHECKER=r.BFCLPythonChecker(ROOT/'build/v2/general-tool-data-v1/bfcl-python-checker')
        dev=r.rows(r.WORK/'development.jsonl')
        selected=[next(c for c in dev if c['domain']=='maintenance' and c['stratum']==s) for s in ['direct','conditional','composition','context_correction','clarification','unsupported']]
        selected += [next(c for c in dev if c['domain']=='general' and c['category']==s) for s in ['simple_python','multiple','parallel','parallel_multiple','irrelevance']]
        r.dump(folder/'setup.json',dict(args=args,pid=process.pid,selected_ids=[c['id'] for c in selected],selection='First development case per stratum/category; runtime qualification only.'))
        results=[]
        for c in selected:
            x=r.generate(c,'direct');results.append(x)
            r.write_rows(folder/'predictions.jsonl',results)
            print(json.dumps(dict(id=x['id'],seconds=x['seconds'],correct=x['correct'],generated_tokens=x.get('generated_tokens'))),flush=True)
        r.dump(folder/'summary.json',dict(summary=r.summarize(results),runtime_version=subprocess.check_output([str(exe),'--version'],stderr=subprocess.STDOUT,text=True),
            source_sha256=r.EXECUTED_SOURCE_SHA,scope='GPU runtime probe, not a controlled CPU/GPU speed or FPGA comparison.'))
    finally:
        if process.poll() is None:process.terminate()
        process.wait(timeout=20)
