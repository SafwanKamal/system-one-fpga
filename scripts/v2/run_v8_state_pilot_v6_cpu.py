"""Run exactly the frozen CPU pilot. There is no board or deployment entrypoint."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True
from sysone.v2.v8_state_pilot_v6 import VERSION,campaign,summarize
from run_v8_chain_pilot_v5 import CPU,dump


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    frozen=json.loads((a.manifest.parent/'source-sha256.json').read_text())
    def verify():
        for n,h in frozen.items():
            if sha(ROOT/n)!=h:raise RuntimeError('Frozen input changed: '+n)
    verify();spec=json.loads(a.manifest.read_text())
    if spec['version']!=VERSION:raise RuntimeError('Version mismatch')
    dump(a.out/'run-config.json',dict(version=VERSION,manifest_sha256=sha(a.manifest),source_sha256=frozen,
        backend='CPU llama.cpp pinned Qwen3-0.6B Q8_0 greedy, ngl0',
        timing='process/model-load included; not hardware latency or throughput',board_access=False,full_sweep_started=False))
    backend=None;count=0
    def commit(row):
        nonlocal count
        with (a.out/'requests.jsonl').open('a') as f:f.write(json.dumps(row)+'\n');f.flush()
        count+=1;dump(a.out/'status.json',dict(stage='running',records=count,last_id=row['id'],board_access=False))
        print(json.dumps({k:row[k] for k in ('id','status','accepted','correct','input_tokens')}),flush=True)
    try:
        backend=CPU(ROOT/'build/v2/qwen-fpga-decoder-v8/deployment',a.out)
        rows=campaign(spec,backend.vocab.encode_text,backend.infer,commit);verify()
        dump(a.out/'summary.json',summarize(rows));dump(a.out/'status.json',dict(stage='complete',records=count,
            source_integrity_passed=True,board_access=False,full_sweep_started=False))
    except Exception as exc:
        dump(a.out/'status.json',dict(stage='attention',records=count,error=str(exc),board_access=False));raise
    finally:
        if backend is not None:backend.close()


if __name__=='__main__':main()
