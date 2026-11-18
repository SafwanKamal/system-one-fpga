"""Record this finite continuation without running more model evaluations."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    out=ROOT/'build/v2/general-tool-parallel-report-v5'
    if (out/'seal.json').exists():raise FileExistsError('seal already exists')
    folders=['general-tool-parallel-work-v5','general-tool-parallel-protocol-v5',
        'general-tool-head-audit-v6','general-tool-encoder-improvement-v5',
        'functiongemma-development-v5','functiongemma-template-audit-v5',
        'functiongemma-parameter-template-qualification-v5','functiongemma-token-wire-v1',
        'general-tool-encoder-mvp-v1','general-tool-parallel-report-v5']
    folders += [p.name for p in (ROOT/'build/v2').glob('functiongemma-packed-fetch*') if p.is_dir()]
    paths={ROOT/'docs/research/2026-10-18-fpga-mvp-progress.md',Path(__file__)}
    for folder in folders:
        paths.update(p for p in (ROOT/'build/v2'/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    manifests=[]
    for folder in folders:
        manifests.extend((ROOT/'build/v2'/folder).rglob('run.json'))
        manifests.extend((ROOT/'build/v2'/folder).glob('qualification.json'))
    for path in manifests:
        value=json.loads(path.read_text(encoding='utf-8'))
        mapping=value.get('source_sha256',{})
        if isinstance(mapping,dict):
            for name in mapping:
                source=Path(name)
                if not source.is_absolute():source=ROOT/source
                if source.is_file() and source.is_relative_to(ROOT):paths.add(source)
    names=['prepare_parallel_model_protocol_v5.py','prepare_encoder_head_audit_v6.py',
        'build_general_encoder_mvp_v1.py','prepare_general_encoder_mvp_runtime_v1.py',
        'general_encoder_mvp_client_v1.py','smoke_general_encoder_mvp_heads_v1.py',
        'bringup_general_encoder_mvp_v1_target.py','qualify_functiongemma_token_wire.py']
    paths.update(ROOT/'scripts/v2'/name for name in names)
    paths.update(p for p in (ROOT/'firmware/functiongemma_token_v1').rglob('*') if p.is_file())
    paths.update((ROOT/'tests').glob('*encoder*decode*v5*.py'))
    paths.update((ROOT/'tests').glob('*functiongemma*development*.py'))
    paths.update((ROOT/'tests').glob('*functiongemma*template*.py'))
    paths.add(ROOT/'tests/test_functiongemma_token_wire.py')
    paths.add(ROOT/'rtl/v2/common/packed_weight_row_descriptor_v1.sv')
    files={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(paths)}
    (out/'seal.json').write_text(json.dumps(dict(files=files,files_count=len(files)),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(files=len(files),seal=str(out/'seal.json'))))


if __name__=='__main__':main()
