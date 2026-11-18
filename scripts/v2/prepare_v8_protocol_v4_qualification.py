"""Freeze the selected protocol/qualification jobs separately from deployment."""
import hashlib,json,shutil,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    work=ROOT/'build/v2/v8-protocol-v4';cpu=work/'cpu'
    manifest=cpu/'qualification-manifest.json'
    if not manifest.exists():raise RuntimeError('CPU development selection has not frozen a manifest')
    stage=work/'snapshot';stage.mkdir(exist_ok=False)
    files=['scripts/v2/run_v8_benchmark.py','scripts/v2/qualify_v8_protocol_v4_fpga.py',
           'src/sysone/v2/v8_benchmark.py','src/sysone/v2/v8_benchmark_protocol_v2.py',
           'src/sysone/v2/v8_benchmark_protocol_v4.py','src/sysone/v2/v8_benchmark_protocol_v3.py','scripts/v2/qualify_v8_protocol_v4_cpu.py',
           'src/sysone/v2/qwen_fpga_runtime_v7.py','src/sysone/v2/qwen_tokenizer_v1.py']
    hashes={}
    for name in files:
        dest=stage/name;dest.parent.mkdir(parents=True,exist_ok=True)
        source=ROOT/name
        if 'qwen_fpga_runtime' in name or 'qwen_tokenizer' in name:
            source=ROOT/'build/v2/qwen-fpga-decoder-v8/deployment'/name
        shutil.copyfile(source,dest);hashes[name]=sha(dest)
    for name in ('src/sysone/__init__.py','src/sysone/v2/__init__.py'):
        dest=stage/name;dest.write_text('"""Private protocol qualification snapshot."""\n');hashes[name]=sha(dest)
    shutil.copyfile(manifest,stage/'qualification-manifest.json')
    hashes['qualification-manifest.json']=sha(stage/'qualification-manifest.json')
    (stage/'source-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
    archive=work/'qualification.tar'
    with tarfile.open(archive,'w') as out:
        for path in sorted(stage.rglob('*')):
            if path.is_file():out.add(path,arcname=path.relative_to(stage).as_posix())
    result=dict(archive=str(archive),sha256=sha(archive),source_sha256=hashes,
                manifest_sha256=sha(manifest),deployment_modified=False,full_sweep_started=False)
    (work/'prepared.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
