"""Finite matched retention chains; no hardware programming or full-sweep entrypoint."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True
from sysone.v2.v8_json_fpga_qualification_v11 import cpu_prompt_file_bytes
from sysone.v2.v8_json_retention_v12 import execute,summarize
from run_v8_chain_pilot_v5 import CPU,FPGA,dump


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


class DiagnosticCPU(CPU):
    def infer(self,job):
        path=self.out/(job['id']+'.prompt.txt');path.write_bytes(cpu_prompt_file_bytes(job['prompt']))
        cmd=[str(ROOT/'build/v2/generation/windows/llama-completion.exe'),'-m',str(self.model),
             '-f',str(path),'-n',str(job['output_tokens']),'-c','256','-ngl','0','--temp','0','--seed','0',
             '--repeat-penalty','1','--no-conversation','--no-display-prompt','--no-escape','--no-warmup','--verbose-prompt']
        tick=time.monotonic();p=subprocess.run(cmd,capture_output=True,timeout=120)
        (self.out/(job['id']+'.stdout')).write_bytes(p.stdout);(self.out/(job['id']+'.stderr')).write_bytes(p.stderr)
        if p.returncode:raise RuntimeError('CPU inference failed')
        verbose_ids=[int(n) for n in re.findall(r"\b(\d+)\s*->\s*'",p.stderr.decode(errors='replace'))]
        if verbose_ids!=job['prompt_ids']:raise RuntimeError('Actual llama.cpp prompt tokens differ; inspect verbose stderr')
        raw=p.stdout.decode().replace('\r\n','\n');eos=' [end of text]' in raw
        text=raw.split(' [end of text]',1)[0] if eos else raw.rstrip('\n')
        return dict(generated_text=text,terminal_eos=eos,seconds=time.monotonic()-tick,
                    actual_cpu_prompt_ids=verbose_ids,backend='CPU pinned Q8_0 greedy, actual CLI prompt tokens logged')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--backend',choices=['cpu','fpga'],required=True)
    ap.add_argument('--work',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--package',type=Path,required=True);args=ap.parse_args()
    hashes=json.loads((args.work/'source-sha256.json').read_text())
    def verify():
        for n,h in hashes.items():
            if sha(args.work/n)!=h:raise RuntimeError('Frozen source/input differs: '+n)
            if n.startswith(('scripts/','src/')) and not n.endswith('qwen_fpga_runtime_v7.py'):
                actual=ROOT/n
                if actual.exists() and sha(actual)!=h:raise RuntimeError('Executing source differs from frozen bundle: '+n)
    verify();jobs=json.loads((args.work/'frozen-jobs.json').read_text())
    spec=json.loads((args.work/'manifest.json').read_text())
    if args.backend=='cpu' and sha(ROOT/'build/v2/generation/windows/llama-completion.exe')!=spec['cpu_cli_sha256']:
        raise RuntimeError('Pinned CPU executable differs')
    total=spec['maximum_inferences']
    if len(jobs)!=total or total!=236:raise ValueError('Frozen workload count')
    args.out.mkdir(parents=True,exist_ok=False);backend=None;lock=None;rows=[]
    try:
        if args.backend=='fpga':
            import fcntl
            from inventory_v8_json_retention_v11 import inventory,validate
            from run_v8_benchmark import fixture,package_identity
            lock=Path('/run/lock/sysone-inference.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            before=inventory(args.package);validate(before);dump(args.out/'board-before.json',before)
            identity=package_identity(args.package);dump(args.out/'deployment-before.json',identity)
            backend=FPGA(args.package,args.out)
            dump(args.out/'startup.json',dict(backend.session.setup,model_sha256=backend.session.engine.manifest['sha256'],
                model_verify_method=backend.session.engine.model_verify_method))
            dump(args.out/'fixture-before.json',fixture(backend.session))
        else:backend=DiagnosticCPU(args.package,args.out)
        for i,job in enumerate(jobs):
            actual_ids=backend.vocab.encode_text(job['prompt'])
            if actual_ids!=job['prompt_ids']:raise RuntimeError('Tokenizer differs from frozen CPU inputs')
            (args.out/(job['id']+'.prompt.txt')).write_text(job['prompt'],encoding='utf-8')
            def infer_model(request):
                result=backend.infer(request)
                if 'output_tokens' in result:result['generated_token_count']=result.pop('output_tokens')
                return result
            row=execute(job,infer_model);row['backend_input_ids']=actual_ids
            dump(args.out/(job['id']+'.output.json'),row)
            with (args.out/'requests.jsonl').open('a') as f:f.write(json.dumps(row)+'\n');f.flush()
            rows.append(row);dump(args.out/'status.json',dict(stage='running',completed=len(rows),total=total,
                last_id=row['id'],case_id=row['case_id'],correct=sum(r['correct'] for r in rows),
                parsed=sum(r['parsed'] for r in rows),full_sweep_started=False))
            print(json.dumps(dict(id=row['id'],correct=row['correct'],parsed=row['parsed'],completed=len(rows))),flush=True)
            if args.backend=='fpga' and (i+1==len(jobs) or jobs[i+1]['case_id']!=job['case_id']):
                dump(args.out/(job['case_id']+'.fixture.json'),fixture(backend.session))
                verify()
        if args.backend=='fpga':
            dump(args.out/'fixture-after.json',fixture(backend.session))
            after=inventory(args.package);validate(after);dump(args.out/'board-after.json',after)
            new_identity=package_identity(args.package);dump(args.out/'deployment-after.json',new_identity)
            if before!=after or identity!=new_identity:raise RuntimeError('Deployment/board identity changed')
        verify();dump(args.out/'summary.json',summarize(rows))
        dump(args.out/'status.json',dict(stage='complete',completed=len(rows),total=total,
             correct=sum(r['correct'] for r in rows),parsed=sum(r['parsed'] for r in rows),
             source_integrity_passed=True,full_sweep_started=False,closed_loop_included=False))
    except Exception as exc:
        dump(args.out/'status.json',dict(stage='attention',completed=len(rows),error=str(exc),full_sweep_started=False));raise
    finally:
        if backend is not None:backend.close()
        if lock is not None:lock.close()


if __name__=='__main__':main()
