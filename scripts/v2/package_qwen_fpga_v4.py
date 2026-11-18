"""Package compact-call software against the sealed, deployed batch FPGA image."""
import hashlib,json,shutil,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/v2/qwen-fpga-decoder-v5'
def main():
    prior=ROOT/'build/v2/qwen-fpga-decoder-v4'
    seal=json.loads((prior/'seal.json').read_text())
    for name,digest in seal['files_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Baseline changed: '+name)
    stage=BUILD/'deployment';stage.mkdir(parents=True,exist_ok=False)
    sources=['scripts/v2/run_qwen_fpga_command_v4.py','scripts/v2/finish_qwen_fpga_v4.py','src/sysone/v2/qwen_fpga_runtime_v3.py','hls/qwen_decoder_v5/qwen_vocab_session.cpp']
    for name in sources:
        target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    for name in ['model-manifest.json','registers.json','rope.bin','sysone-qwen-decoder-batch/build.json']:
        target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(prior/'deployment'/name,target)
    hashes={p.relative_to(stage).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.rglob('*') if p.is_file()}
    (stage/'package-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
    archive=BUILD/'qwen-fpga-deployment.tar'
    with tarfile.open(archive,'w') as output:
        for p in stage.rglob('*'):
            if p.is_file():output.add(p,arcname=p.relative_to(stage).as_posix())
    print(json.dumps(dict(archive=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),FPGA_image_changed=False)))
if __name__=='__main__':main()
