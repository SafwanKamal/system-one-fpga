"""Package only the completed, timing-qualified Qwen FPGA decoder build."""
import argparse,hashlib,json,re,shutil,subprocess,tarfile,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/v2/qwen-fpga-decoder-v7'
APP='sysone-qwen-decoder-buffered'

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest',type=Path,default=ROOT/'build/v2/qwen-fpga-decoder-v2/model-manifest.json')
    ap.add_argument('--rope',type=Path,default=ROOT/'build/v2/qwen-fpga-decoder-v2/rope.bin')
    ap.add_argument('--model-path',default='/home/ubuntu/sysone-generation/Qwen3-0.6B-Q8_0.gguf')
    args=ap.parse_args()
    frozen=json.loads((BUILD/'hardware-source-sha256.json').read_text())
    for name,digest in frozen.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Hardware source changed after synthesis: '+name)
    exported=json.loads((BUILD/'ip-rtl-consistency.json').read_text())
    if not exported['passed'] or exported['ip_archive_sha256']!=hashlib.sha256((BUILD/'qwen_decoder_ip.zip').read_bytes()).hexdigest():raise RuntimeError('Qualified HLS export changed')
    if not exported.get('vivado_imported_rtl_verified'):raise RuntimeError('Physical project RTL must match the qualified export')
    project=BUILD/'vivado'
    header=(BUILD/'hls-release/solution/impl/ip/drivers/qwen_decoder_v1_0/src/xqwen_decoder_hw.h').read_text()
    offsets={name.lower():int(value,16) for name,value in re.findall(r'#define XQWEN_DECODER_CONTROL_ADDR_(\w+)_DATA\s+(0x[0-9a-fA-F]+)',header)}
    if offsets!=json.loads((ROOT/'build/v2/qwen-fpga-decoder-v2/registers.json').read_text()):raise RuntimeError('Kernel CSR ABI changed; regenerate runtime map')
    bit=project/'qwen_decoder_kr260.runs/impl_1/system_wrapper.bit'
    xsa=project/'qwen_decoder.xsa'
    timing=project/'routed-timing.rpt'
    if not all(p.is_file() for p in [bit,xsa,timing]):raise RuntimeError('Completed routed hardware export required')
    if 'All user specified timing constraints are met.' not in timing.read_text():raise RuntimeError('Routed timing did not pass')
    with zipfile.ZipFile(xsa) as export:
        members=[p for p in export.namelist() if p.endswith('.bit')]
        if len(members)!=1 or export.read(members[0])!=bit.read_bytes():raise RuntimeError('Hardware export does not contain final bitstream')
    stage=BUILD/'deployment';stage.mkdir(exist_ok=True)
    app=stage/APP;app.mkdir(exist_ok=True)
    shutil.copyfile(bit,app/'decoder.bit')
    (app/'bitstream.bif').write_text('all:\n{\n decoder.bit\n}\n',encoding='ascii')
    subprocess.run(['C:/AMDDesignTools/2025.2/Vivado/bin/bootgen.bat','-arch','zynqmp','-image','bitstream.bif','-w','-process_bitstream','bin'],cwd=app,check=True)
    generated=app/'decoder.bit.bin'
    if not generated.is_file():raise RuntimeError('Missing bootgen output')
    shutil.copyfile(generated,app/(APP+'.bit.bin'))
    for name in ['decoder.bit','decoder.bit.bin','bitstream.bif']:(app/name).unlink()
    source=(ROOT/'scripts/v2/kr260/sysone-v2.dts').read_text()
    source=source.replace('sysone-v2.bit.bin',APP+'.bit.bin').replace('100000000','100000000').replace('sysone_clock','qwen_clock').replace('sysone-clocking','qwen-clocking').replace('sysone_fabric','qwen_fabric').replace('sysone_afi','qwen_afi').replace('sysone-afi','qwen-afi').replace('sysone_encoder: encoder@','qwen_decoder: qwen-decoder@').replace('xlnx,kr260-encoder-wrapper-1.0','xlnx,qwen-decoder-buffered-1.0')
    source='\n'.join(line for line in source.splitlines() if not any(s in line for s in ['xlnx,tile-out','xlnx,max-hidden','xlnx,max-tokens','xlnx,max-head-dim','xlnx,drain-lanes','xlnx,norm-lanes']))+'\n'
    (app/(APP+'.dts')).write_text(source,encoding='ascii')
    shutil.copyfile(ROOT/'scripts/v2/kr260/shell.json',app/'shell.json')
    shutil.copyfile(args.manifest,stage/'model-manifest.json')
    shutil.copyfile(args.rope,stage/'rope.bin')
    shutil.copyfile(ROOT/'build/v2/qwen-fpga-decoder-v2/registers.json',stage/'registers.json')
    for name in ['src/sysone/v2/qwen_fpga_runtime_v6.py','scripts/v2/run_qwen_fpga_command_v6.py','scripts/v2/deploy_qwen_fpga_v6.py','scripts/v2/smoke_qwen_fpga_v6.py','scripts/v2/finish_qwen_fpga_v6.py']:
        target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    for index in range(4):shutil.copyfile(BUILD/f'block-fixture/expected-{index}.bin',stage/f'expected-{index}.bin')
    shutil.copyfile(BUILD/'block-fixture/manifest.json',stage/'fixture-manifest.json')
    manifest=dict(app_name=APP,clock_requested_hz=100000000,clock_timing_max_hz=100000000,bitstream_sha256=hashlib.sha256(bit.read_bytes()).hexdigest(),xsa_sha256=hashlib.sha256(xsa.read_bytes()).hexdigest(),routed_timing_sha256=hashlib.sha256(timing.read_bytes()).hexdigest(),timing_qualified=True)
    profile=json.loads((stage/'model-manifest.json').read_text())
    keys=dict(hidden='H',ffn='F',q_heads='NH',kv_heads='NK',layers='NL',vocab='VOCAB',max_context='NC',head_dim='HD')
    header=(ROOT/'hls/qwen_decoder_v7/model_profile.hpp').read_text()
    compiled_path=BUILD/'hls-release/solution/.autopilot/db/qwen_decoder.pp.0.cpp'
    preprocessed=compiled_path.read_text()
    declarations=[]
    for name in ('H','HD','Q','B'):
        declaration=re.search(r'static const unsigned '+name+r'\s*=[^;]+;',preprocessed)
        if not declaration:raise RuntimeError('Compiled model profile declaration absent: '+name)
        declarations.append(declaration[0])
    constants={name:int(value) for name,value in re.findall(r'(?:unsigned\s+|,)\s*(\w+)\s*=\s*(\d+)\b','\n'.join(declarations))}
    for key,constant in keys.items():
        if constants.get(constant)!=profile[key]:raise RuntimeError('Compiled build/weight profile mismatch: '+key)
    if constants.get('B')!=4:raise RuntimeError('Runtime requires four token slots')
    if profile['head_dim']!=128:raise RuntimeError('Head dimension differs')
    if profile['hidden']%256:raise RuntimeError('Embedding rows must be 16-byte aligned in the current profile')
    manifest['model_profile']={k:profile[k] for k in keys}
    manifest['model_profile'].update(quantization='Q8_0',prefill_batch=4)
    manifest['matrix_core_sha256']=hashlib.sha256((ROOT/'hls/qwen_decoder_v7/matrix_q8.hpp').read_bytes()).hexdigest()
    manifest['model_profile_header_sha256']=hashlib.sha256((ROOT/'hls/qwen_decoder_v7/model_profile.hpp').read_bytes()).hexdigest()
    manifest['compiled_profile_source_sha256']=hashlib.sha256(compiled_path.read_bytes()).hexdigest()
    manifest['hardware_sources_sha256']=frozen
    manifest['optimizations']=dict(norm_gamma_reuse='per decoder token batch',rope_reuse='per token across all Q/K heads',inplace_pipeline_dependencies='disjoint elements; arithmetic order preserved',startup='tokenizer overlaps full resident ordered SHA256',dma_hash_staging=dict(workers=2,buffers=4,buffer_bytes=4<<20),command_poll_interval_seconds=0.00005)
    profile['model_path']=args.model_path
    (stage/'model-manifest.json').write_text(json.dumps(profile,indent=2)+'\n')
    (app/'build.json').write_text(json.dumps(manifest,indent=2)+'\n')
    hashes={str(p.relative_to(stage)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.rglob('*') if p.is_file() and p.name!='package-sha256.json'}
    (stage/'package-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
    archive=BUILD/'qwen-fpga-deployment.tar'
    with tarfile.open(archive,'w') as output:
        for p in stage.rglob('*'):
            if p.is_file():output.add(p,arcname=str(p.relative_to(stage)).replace('\\','/'))
    print(json.dumps(dict(archive=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest())))

if __name__=='__main__':main()
