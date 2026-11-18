"""Freeze the CPU-only v6 cases, prompts and sources without touching the board."""
import hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.v8_state_pilot_v6 import manifest,prompt,apply_observation,expected
from sysone.v2.v8_benchmark import reduce_observed


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    w=ROOT/'build/v2/v8-state-pilot-v6-r2';w.mkdir(parents=True,exist_ok=False)
    stage=w/'snapshot';stage.mkdir()
    names=['src/sysone/v2/v8_state_pilot_v6.py','src/sysone/v2/v8_chain_pilot_v5.py',
           'src/sysone/v2/v8_benchmark.py','src/sysone/v2/qwen_tokenizer_v1.py',
           'scripts/v2/run_v8_chain_pilot_v5.py','scripts/v2/run_v8_state_pilot_v6_cpu.py',
           'scripts/v2/prepare_v8_state_pilot_v6.py','tests/test_v8_state_pilot_v6.py']
    hashes={}
    for name in names:
        p=ROOT/name;dst=stage/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst);hashes[name]=sha(p)
    tokenizer=ROOT/'build/v2/qwen-fpga-decoder-v8/deployment/src/sysone/v2/qwen_tokenizer_v1.py'
    if hashes['src/sysone/v2/qwen_tokenizer_v1.py']!=sha(tokenizer):raise RuntimeError('Tokenizer differs from sealed package')
    spec=manifest();(w/'pilot-manifest.json').write_text(json.dumps(spec,indent=2)+'\n')
    manifest_name=(w/'pilot-manifest.json').relative_to(ROOT).as_posix()
    hashes[manifest_name]=sha(w/'pilot-manifest.json')
    exe=ROOT/'build/v2/generation/windows/llama-completion.exe';hashes[exe.relative_to(ROOT).as_posix()]=sha(exe)
    (w/'source-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
    shutil.copyfile(w/'pilot-manifest.json',stage/'pilot-manifest.json')
    # Freeze all deterministic snapshot prompts before model responses exist.
    controls=[]
    for c in spec['cases']:
        state=c['initial']
        for i,s in enumerate(c['steps']):
            if c['mode']=='retention':state=apply_observation(state,s['observation'])
            for arm in ('J','C'):
                text,_=prompt(c,i,state,arm)
                controls.append(dict(case_id=c['id'],step=i+1,arm=arm,prompt=text))
            if c['mode']=='closed-loop':state=reduce_observed(state,expected(c,state,s))
    (w/'frozen-control-prompts.json').write_text(json.dumps(controls,indent=2)+'\n')
    print(json.dumps(dict(version=spec['version'],cases=len(spec['cases']),controls=len(controls),
        maximum_inferences=spec['maximum_inferences'],manifest_sha256=hashes[manifest_name],
        full_sweep_started=False,board_access=False),indent=2))


if __name__=='__main__':main()
