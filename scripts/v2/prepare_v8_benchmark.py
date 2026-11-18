"""Prepare a frozen benchmark-only source archive; never edit sealed v8 files."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
from sysone.v2.v8_benchmark import prepare_manifest, chat, chain_prompt, VERSION


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''): h.update(block)
    return h.hexdigest()


def main():
    # Preload the host-native module before the pinned ARM tokenizer search path.
    import tokenizers
    from sysone.v2.qwen_tokenizer_v1 import Vocabulary
    work = ROOT/'build/v2/v8-baseline-v1'
    stage = work/'snapshot'
    stage.mkdir(parents=True, exist_ok=False)
    deployment = ROOT/'build/v2/qwen-fpga-decoder-v8/deployment'
    vocab = Vocabulary(deployment)
    manifest = prepare_manifest()
    prefix = vocab.encode_text('<|im_start|>system\nContinue.<|im_end|>\n<|im_start|>user\n')
    suffix = vocab.encode_text('<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n')
    pads = [vocab.encode_text(text) for text in (' x',' y',' z')]
    if any(len(p)!=1 for p in pads): raise ValueError('Padding must be one actual token')
    for job in manifest['fixed']:
        n = job['input_tokens']-len(prefix)-len(suffix)
        if n<1: raise ValueError('Template exceeds declared token count')
        job['prompt_ids'] = prefix+pads[job['variant']]*n+suffix
        job['input_policy'] = 'Synthetic token-ID padding inside user message; no truncation or prefix reuse'
    counts=[]
    for item in manifest['chains']:
        prompt,_=chain_prompt(item['chain'],0,item['chain']['initial'],item['context'],item['wire'],[])
        count=len(vocab.encode_text(prompt))
        counts.append(dict(id=item['id'],tokens=count, fits=count+manifest['output_reserve']<=256))
    if not all(row['fits'] for row in counts): raise ValueError('Chain initial prompt cannot fit')
    manifest['initial_chain_token_counts'] = counts
    manifest['tokenizer_compiled_sha256'] = sha(deployment/'tokenizer-bpe.pkl')
    manifest['deviations'] = [
        'Initial chain task is a bounded two-entity simulator; no claims about arbitrary tool workflows.',
        'Development uses 12 four-step chains; no automatic prompt adaptation.',
        'Application cases are 20 frozen paraphrases x five paths, not 100 independent capabilities.',
        'No real tools execute; historical command is generated/scored against its known path.',
        'Oracle-state diagnostics, energy instrumentation, confidence intervals and plotting are follow-up analysis, not this runner.',
        'Persistent startup is additional to per-request time; cold_call excludes process exec and includes setup; harness_wall includes exec.',
        'No external CPU/model quality baseline is executed in this sweep.']
    (stage/'workloads.json').write_text(json.dumps(manifest,indent=2)+'\n')
    sources = ['scripts/v2/run_v8_benchmark.py', 'src/sysone/v2/v8_benchmark.py',
               'src/sysone/v2/qwen_fpga_runtime_v7.py', 'src/sysone/v2/qwen_tokenizer_v1.py']
    hashes={}
    for name in sources:
        dest=stage/name;dest.parent.mkdir(parents=True,exist_ok=True)
        # Use sealed deployment copies of production runtime/tokenizer.
        source=deployment/name if name.startswith('src/') and not name.endswith('v8_benchmark.py') else ROOT/name
        shutil.copyfile(source,dest); hashes[name]=sha(dest)
    # Explicit package roots prevent an unrelated installed sysone package winning.
    for name in ('src/sysone/__init__.py','src/sysone/v2/__init__.py'):
        dest=stage/name;dest.write_text('"""Isolated benchmark source snapshot."""\n')
        hashes[name]=sha(dest)
    hashes['workloads.json']=sha(stage/'workloads.json')
    (stage/'source-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
    (stage/'README.md').write_text('Finite '+VERSION+' benchmark source snapshot.\n'
        'No deployment, firmware, model, launcher or reboot operations.\n'
        'One exclusive inference lock; pre/post causal fixtures; no automatic retry.\n'
        'Persistent requests reinitialize logical KV by full prefill at position zero.\n'
        'Stop after a command failure and inspect hardware; never unload in-flight hardware.\n')
    board=work/'board';board.mkdir(exist_ok=True)
    archive=board/'benchmark.tar'
    with tarfile.open(archive,'w') as out:
        for p in sorted(stage.rglob('*')):
            if p.is_file():out.add(p,arcname=p.relative_to(stage).as_posix())
    # Deliberately do not publish upload-ready here: local tests and review first.
    (work/'prepared.json').write_text(json.dumps(dict(version=VERSION,sha256=sha(archive),
        source_sha256=hashes, fixed_requests=360, historical_requests=30,
        application_requests=100, max_chain_requests=12*4*6+24*16*6,
        upload_ready=False),indent=2)+'\n')
    print(json.dumps(dict(archive=str(archive),sha256=sha(archive),initial_chain_token_range=[
        min(x['tokens'] for x in counts),max(x['tokens'] for x in counts)])))


if __name__=='__main__':main()
