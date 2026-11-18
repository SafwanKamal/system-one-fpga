"""Finite CPU/FPGA chain pilot. All writes are to a separate benchmark folder."""
import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True
from sysone.v2.v8_chain_pilot_v5 import campaign,summarize,VERSION


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def dump(path,value):
    tmp=path.with_suffix('.new');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)


class CPU:
    def __init__(self,package,out):
        import tokenizers
        from sysone.v2.qwen_tokenizer_v1 import Vocabulary
        self.vocab=Vocabulary(package);self.out=out
        self.model=ROOT/'models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf'
        if sha(self.model)!='9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031':
            raise RuntimeError('Pinned model differs')
    def infer(self,job):
        path=self.out/(job['id']+'.prompt.txt');path.write_text(job['prompt'],encoding='utf-8')
        command=[str(ROOT/'build/v2/generation/windows/llama-completion.exe'),'-m',str(self.model),
            '-f',str(path),'-n',str(job['output_tokens']),'-c','256','-ngl','0','--temp','0','--seed','0',
            '--repeat-penalty','1','--no-conversation','--no-display-prompt','--no-escape','--no-warmup']
        t=time.monotonic();p=subprocess.run(command,capture_output=True,timeout=120)
        (self.out/(job['id']+'.stdout')).write_bytes(p.stdout);(self.out/(job['id']+'.stderr')).write_bytes(p.stderr)
        if p.returncode:raise RuntimeError('CPU failed: '+job['id'])
        raw=p.stdout.decode().replace('\r\n','\n');eos=' [end of text]' in raw
        text=raw.split(' [end of text]',1)[0] if eos else raw.rstrip('\n')
        return dict(generated_text=text,terminal_eos=eos,seconds=time.monotonic()-t,
            output_tokens_estimate=len(self.vocab.encode_text(text)),
            backend='CPU llama.cpp Q8; process/model-load time included; quality control only')
    def close(self):self.vocab.close()


class FPGA:
    def __init__(self,package,out):
        from run_v8_benchmark import Session
        self.session=Session(package);self.session.package=package;self.vocab=self.session.vocab
    def infer(self,job):
        e,v=self.session.engine,self.vocab;t=time.monotonic();ids=v.encode_text(job['prompt'])
        if ids!=job['prompt_ids']:raise RuntimeError('Token IDs changed within request')
        if len(ids)+job['output_tokens']>e.context:raise RuntimeError('Context limit')
        e.begin_prefix(ids,enabled=False)
        for pos in range(0,len(ids),e.prefill_batch_size):
            group=ids[pos:pos+e.prefill_batch_size]
            token=e.prefill_batch(group,pos,logits=pos+len(group)==len(ids))
        prefill=time.monotonic()-t;decode=time.monotonic();raw=b'';generated=[];eos=False
        # Consume the complete response to actual EOS or budget. Never accept a
        # parseable prefix while contradictory trailing text could still follow.
        for i in range(job['output_tokens']):
            generated.append(token);raw+=v.piece(token);eos=token in e.manifest['eos_ids']
            if eos:break
            if i+1<job['output_tokens']:token=e.step(token,len(ids)+i,logits=True)
        return dict(generated_text=raw.decode('utf-8',errors='replace'),terminal_eos=eos,generated_ids=generated,
            output_tokens=len(generated),seconds=time.monotonic()-t,prefill_seconds=prefill,
            decode_seconds=time.monotonic()-decode,prefix_tokens_reused=0,
            backend='FPGA unchanged v8; no CPU model arithmetic')
    def close(self):self.session.close()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--backend',choices=['cpu','fpga'],required=True)
    ap.add_argument('--package',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    frozen=json.loads((a.manifest.parent/'source-sha256.json').read_text())
    for name,h in frozen.items():
        if sha(ROOT/name)!=h:raise RuntimeError('Frozen source differs: '+name)
    spec=json.loads(a.manifest.read_text())
    if spec['version']!=VERSION:raise RuntimeError('Version mismatch')
    dump(a.out/'run-config.json',dict(backend=a.backend,manifest_sha256=sha(a.manifest),
        source_sha256=frozen,full_sweep_started=False,tool_execution=False))
    backend=None;lock=None;count=0
    def commit(row):
        nonlocal count
        with (a.out/'requests.jsonl').open('a') as f:f.write(json.dumps(row)+'\n');f.flush()
        count+=1;dump(a.out/'status.json',dict(stage='running',records=count,last_id=row['id']))
        print(json.dumps({k:row[k] for k in ('id','status','accepted','native_format','correct','input_tokens')}),flush=True)
    try:
        if a.backend=='fpga':
            import fcntl
            from run_v8_benchmark import fixture,package_identity
            lock=Path('/run/lock/sysone-inference.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            before=package_identity(a.package);dump(a.out/'deployment-before.json',before)
            backend=FPGA(a.package,a.out);dump(a.out/'fixture-before.json',fixture(backend.session))
        else:backend=CPU(a.package,a.out)
        rows=campaign(spec,backend.vocab.encode_text,backend.infer,commit)
        if a.backend=='fpga':
            dump(a.out/'fixture-after.json',fixture(backend.session));after=package_identity(a.package)
            dump(a.out/'deployment-after.json',after)
            if before!=after:raise RuntimeError('Deployment changed')
        dump(a.out/'summary.json',summarize(rows));dump(a.out/'status.json',dict(stage='complete',records=count,full_sweep_started=False))
    except Exception as exc:
        dump(a.out/'status.json',dict(stage='attention',records=count,error=str(exc)));raise
    finally:
        if backend is not None:backend.close()
        if lock is not None:lock.close()


if __name__=='__main__':main()
