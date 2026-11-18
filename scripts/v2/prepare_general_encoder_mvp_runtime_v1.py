"""Prepare candidate Linux ingress/module sources, never access the target."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import struct

ROOT=Path(__file__).resolve().parents[2]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    bundle=ROOT/'build/v2/general-tool-encoder-mvp-v1';runtime=bundle/'runtime';runtime.mkdir(exist_ok=False)
    pure='import json,re\nfrom sysone.v2.general_tools import normalize_tool\n'
    for file,names in [('general_tool_encoder.py',['job_text','scalar_from_span']),('general_training_v2.py',['encoder_text'])]:
        source=(ROOT/'src/sysone/v2'/file).read_text(encoding='utf-8')
        for node in ast.parse(source).body:
            if isinstance(node,ast.FunctionDef) and node.name in names:pure+=ast.get_source_segment(source,node)+'\n\n'
    pure+="KINDS=('omit','span','true','false','null','empty_string','empty_array','empty_object','unrepresentable')\n"
    (runtime/'helpers.py').write_text(pure,encoding='utf-8')
    parent=json.loads((ROOT/'build/v2/general-tool-expanded-training-v4/encoder/run.json').read_text(encoding='utf-8'))
    shutil.copyfile(Path(parent['arguments']['model'])/'tokenizer.json',runtime/'tokenizer.json')
    request=dict(query='Add 3 and 5.',tools=[dict(name='sum_values',description='Add two numbers.',
        parameters=dict(type='object',properties={'a':{'type':'integer'},'b':{'type':'integer'}},required=['a','b']))])
    (runtime/'smoke-request.json').write_text(json.dumps(request,indent=2)+'\n',encoding='utf-8')
    module=bundle/'linux-module-candidate';module.mkdir()
    prior=ROOT/'firmware/typed200_linux_r5_inference'
    for name in ['linux.c','session.c','session.h','Makefile']:shutil.copyfile(prior/name,module/name)
    image=(bundle/'firmware/image.bin').read_bytes();elfsha=sha(bundle/'firmware/inference.elf')
    header=f'#define SMOKE_ELF_SHA256 "{elfsha}"\nstatic const u64 smoke_image[]={{\n'
    header+=''.join(f'0x{x:016x}ULL,\n' for (x,) in struct.iter_unpack('<Q',image))+'};\n'
    (module/'smoke_image.h').write_text(header,encoding='utf-8')
    record=dict(stage='offline_runtime_prepared',board_contacted=False,
        module_sources='unchanged existing Linux lifecycle controller; only fixed firmware image/header differs',
        client='scripts/v2/general_encoder_mvp_client_v1.py',target_dependencies=['numpy','tokenizers','existing sysone source'],
        no_torch_on_target=True,r5_elf_sha256=elfsha,
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),ROOT/'scripts/v2/general_encoder_mvp_client_v1.py']},
        runtime_sha256={p.name:sha(p) for p in runtime.iterdir() if p.is_file()},
        module_sha256={p.name:sha(p) for p in module.iterdir() if p.is_file()},
        hardware_executed=False,remaining=['one host/R5-head smoke','target kernel-module build','board switch/rollback window','physical inference','terminal deadline integration'])
    (bundle/'runtime-preparation.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print('Prepared Linux general-call ingress and fixed-image module candidate; target untouched')


if __name__=='__main__':main()
