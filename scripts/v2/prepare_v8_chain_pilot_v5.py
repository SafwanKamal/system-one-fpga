"""Freeze one pilot plan and source snapshot without modifying previous runs."""
import hashlib,json,shutil,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.v8_chain_pilot_v5 import manifest


def main():
    w=ROOT/'build/v2/v8-chain-pilot-v5';w.mkdir(parents=True,exist_ok=True)
    stage=w/'snapshot';stage.mkdir(exist_ok=False)
    files=['scripts/v2/run_v8_chain_pilot_v5.py','scripts/v2/run_v8_benchmark.py',
           'src/sysone/v2/v8_chain_pilot_v5.py','src/sysone/v2/v8_benchmark.py',
           'src/sysone/v2/qwen_fpga_runtime_v7.py','src/sysone/v2/qwen_tokenizer_v1.py']
    for name in files:
        src=ROOT/name
        if 'qwen_fpga_runtime' in name or 'qwen_tokenizer' in name:
            src=ROOT/'build/v2/qwen-fpga-decoder-v8/deployment'/name
        dst=stage/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
    for name in ('src/sysone/__init__.py','src/sysone/v2/__init__.py'):(stage/name).write_text('"""Private benchmark snapshot."""\n')
    (stage/'pilot-manifest.json').write_text(json.dumps(manifest(),indent=2)+'\n')
    hashes={p.relative_to(stage).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.rglob('*') if p.is_file()}
    (stage/'source-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
    # The local runner verifies repository sources; the copied runner verifies
    # the same source bytes in its private root. Manifest hash is also checked.
    local={n:h for n,h in hashes.items() if n in files and 'qwen_fpga_runtime' not in n and 'qwen_tokenizer' not in n}
    local['build/v2/v8-chain-pilot-v5/pilot-manifest.json']=hashes['pilot-manifest.json']
    shutil.copyfile(stage/'pilot-manifest.json',w/'pilot-manifest.json')
    (w/'source-sha256.json').write_text(json.dumps(local,indent=2)+'\n')
    archive=w/'pilot.tar'
    with tarfile.open(archive,'w') as t:
        for p in sorted(stage.rglob('*')):
            if p.is_file():t.add(p,arcname=p.relative_to(stage).as_posix())
    result=dict(archive=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        manifest_sha256=hashes['pilot-manifest.json'],source_sha256=hashes,full_sweep_started=False)
    (w/'prepared.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
