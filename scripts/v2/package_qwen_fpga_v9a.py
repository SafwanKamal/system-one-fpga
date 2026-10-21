"""Package the timing-qualified v9a candidate as a separate versioned deployment.

Reads the sealed v8 package only for unchanged host assets (tokenizer, model
manifest, RoPE, registers), verifying each against v8's package-sha256.json.
Writes only under build/v2/qwen-fpga-decoder-v9a.
"""
import hashlib,json,re,shutil,subprocess,tarfile,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/v2/qwen-fpga-decoder-v9a'
V8=ROOT/'build/v2/qwen-fpga-decoder-v8'
APP='sysone-qwen-decoder-v9a-b3'
COMPATIBLE='xlnx,qwen-decoder-v9a-1.0'
SOURCES=ROOT/'hls/qwen_decoder_v9a'
HOST_FILES=['src/sysone/v2/qwen_fpga_runtime_v9a.py','src/sysone/v2/qwen_tokenizer_v1.py',
            'scripts/v2/run_qwen_fpga_command_v9a.py','scripts/v2/deploy_qwen_fpga_v9a.py',
            'scripts/v2/smoke_qwen_fpga_v9a.py']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    frozen=json.loads((BUILD/'hardware-source-sha256.json').read_text())
    for name,digest in frozen.items():
        if sha(ROOT/name)!=digest:raise RuntimeError('Hardware source changed after synthesis: '+name)
    exported=json.loads((BUILD/'ip-rtl-consistency.json').read_text())
    if not exported['passed'] or exported['ip_archive_sha256']!=sha(BUILD/'qwen_decoder_ip.zip'):raise RuntimeError('Qualified HLS export changed')
    if not exported.get('vivado_imported_rtl_verified'):raise RuntimeError('Physical project RTL must match the qualified export')
    project=BUILD/'vivado'
    header=(BUILD/'hls-release/solution/impl/ip/drivers/qwen_decoder_v1_0/src/xqwen_decoder_hw.h').read_text()
    offsets={name.lower():int(value,16) for name,value in re.findall(r'#define XQWEN_DECODER_CONTROL_ADDR_(\w+)_DATA\s+(0x[0-9a-fA-F]+)',header)}
    v8_hashes=json.loads((V8/'deployment/package-sha256.json').read_text())
    def v8_asset(name):
        path=V8/'deployment'/name
        if sha(path)!=v8_hashes[name]:raise RuntimeError('Sealed v8 asset differs: '+name)
        return path
    if offsets!=json.loads(v8_asset('registers.json').read_text()):raise RuntimeError('Kernel CSR ABI changed; regenerate runtime map')
    bit=project/'qwen_decoder_kr260.runs/impl_1/system_wrapper.bit'
    xsa=project/'qwen_decoder.xsa'
    timing=project/'routed-timing.rpt'
    if not all(p.is_file() for p in [bit,xsa,timing]):raise RuntimeError('Completed routed hardware export required')
    if 'All user specified timing constraints are met.' not in timing.read_text():raise RuntimeError('Routed timing did not pass')
    skew=project/'qwen_decoder_kr260.runs/impl_1/system_wrapper_bus_skew_postroute_physopted.rpt'
    skew_rows=re.findall(r'^\s+(?:Slow|Fast)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(-?\d+\.\d+)\s*$',skew.read_text(),re.M)
    if not skew_rows or any(float(row[2])<0 for row in skew_rows):raise RuntimeError('Clock converter bus skew did not pass')
    with zipfile.ZipFile(xsa) as export:
        members=[p for p in export.namelist() if p.endswith('.bit')]
        if len(members)!=1 or export.read(members[0])!=bit.read_bytes():raise RuntimeError('Hardware export does not contain final bitstream')
    stage=BUILD/'deployment'
    if stage.exists():raise RuntimeError('Deployment stage exists; preserve it and use a new candidate version')
    stage.mkdir();app=stage/APP;app.mkdir()
    shutil.copyfile(bit,app/'decoder.bit')
    (app/'bitstream.bif').write_text('all:\n{\n decoder.bit\n}\n',encoding='ascii')
    subprocess.run(['C:/AMDDesignTools/2025.2/Vivado/bin/bootgen.bat','-arch','zynqmp','-image','bitstream.bif','-w','-process_bitstream','bin'],cwd=app,check=True)
    shutil.copyfile(app/'decoder.bit.bin',app/(APP+'.bit.bin'))
    for name in ['decoder.bit','decoder.bit.bin','bitstream.bif']:(app/name).unlink()
    # The v8 overlay differs only in firmware name and compatible string.
    v8_app=V8/'deployment/sysone-qwen-decoder-wide-int8'
    dts=v8_asset('sysone-qwen-decoder-wide-int8/sysone-qwen-decoder-wide-int8.dts').read_text()
    for old,new in [('sysone-qwen-decoder-wide-int8.bit.bin',APP+'.bit.bin'),('xlnx,qwen-decoder-wide-int8-1.0',COMPATIBLE)]:
        if dts.count(old)!=1:raise RuntimeError('Unexpected v8 overlay source: '+old)
        dts=dts.replace(old,new)
    (app/(APP+'.dts')).write_text(dts,encoding='ascii')
    shutil.copyfile(v8_asset('sysone-qwen-decoder-wide-int8/shell.json'),app/'shell.json')
    for name in ['model-manifest.json','rope.bin','registers.json','tokenizer.json','tokenizer-bpe.pkl',
                 'tokenizer-bpe-source.json','tokenizer-correctness.json','tokenizer-wheel-source.json']:
        shutil.copyfile(v8_asset(name),stage/name)
    if sha(stage/'rope.bin')!=sha(BUILD/'rope.bin'):raise RuntimeError('RoPE table differs from the v9a reference')
    for name in [n for n in v8_hashes if n.startswith('tokenizer-runtime/')]:
        target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(v8_asset(name),target)
    for name in HOST_FILES:
        target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    for fixture,count in [('block-fixture',8),('long-fixture',40)]:
        (stage/fixture).mkdir()
        for index in range(count):shutil.copyfile(BUILD/fixture/f'expected-{index}.bin',stage/fixture/f'expected-{index}.bin')
        shutil.copyfile(BUILD/fixture/'manifest.json',stage/fixture/'manifest.json')
    v8_build=json.loads((v8_app/'build.json').read_text())
    manifest=dict(app_name=APP,candidate='v9a',baseline='v8 sysone-qwen-decoder-wide-int8',
                  clock_requested_hz=125000000,clock_timing_max_hz=125000000,
                  memory_clock_requested_hz=250000000,memory_clock_timing_max_hz=250000000,
                  bitstream_sha256=sha(bit),xsa_sha256=sha(xsa),routed_timing_sha256=sha(timing),timing_qualified=True,
                  bus_skew_report_sha256=sha(skew),bus_skew_min_slack_ns=min(float(row[2]) for row in skew_rows))
    compiled_path=BUILD/'hls-release/solution/.autopilot/db/qwen_decoder.pp.0.cpp'
    preprocessed=compiled_path.read_text()
    declarations=[]
    for name in ('H','HD','Q','B'):
        declaration=re.search(r'static const unsigned '+name+r'\s*=[^;]+;',preprocessed)
        if not declaration:raise RuntimeError('Compiled model profile declaration absent: '+name)
        declarations.append(declaration[0])
    constants={name:int(value) for name,value in re.findall(r'(?:unsigned\s+|,)\s*(\w+)\s*=\s*(\d+)\b','\n'.join(declarations))}
    profile=json.loads((stage/'model-manifest.json').read_text())
    keys=dict(hidden='H',ffn='F',q_heads='NH',kv_heads='NK',layers='NL',vocab='VOCAB',max_context='NC',head_dim='HD')
    for key,constant in keys.items():
        if constants.get(constant)!=profile[key]:raise RuntimeError('Compiled build/weight profile mismatch: '+key)
    if constants.get('B')!=8:raise RuntimeError('Runtime requires eight token slots')
    manifest['model_profile']=dict(v8_build['model_profile'])
    manifest['matrix_core_sha256']=sha(SOURCES/'matrix_q8.hpp')
    manifest['model_profile_header_sha256']=sha(SOURCES/'model_profile.hpp')
    manifest['compiled_profile_source_sha256']=sha(compiled_path)
    manifest['hardware_sources_sha256']=frozen
    manifest['optimizations']=dict(v8_build['optimizations'])
    manifest['optimizations'].update(state_port_bits=256,kv_cache_layout='head-major [layer][k/v][kv_head][position][128] FP32',
        attention='8-wide score and value accumulation, chunk-major scoring with >=16-row padding',
        quantization='direct from activation, four lanes per cycle, bit-identical to v8 for finite inputs',
        vector_lanes=4)
    manifest['numerical_changes_vs_v8']=['RMS sum of squares: four lane partials combined (l0+l1)+(l2+l3)',
        'attention score: 16 sequential chunk sums, each an 8-product balanced tree',
        'reference: scripts/v2/prepare_qwen_fpga_v9a.py (exact order); same INT8 matrix arithmetic']
    manifest['tokenizer_sha256']=v8_build['tokenizer_sha256'];manifest['compiled_tokenizer_sha256']=v8_build['compiled_tokenizer_sha256']
    (app/'build.json').write_text(json.dumps(manifest,indent=2)+'\n')
    hashes={str(p.relative_to(stage)).replace('\\','/'):sha(p) for p in stage.rglob('*') if p.is_file() and p.name!='package-sha256.json'}
    (stage/'package-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
    archive=BUILD/'qwen-fpga-v9a-deployment.tar'
    if archive.exists():raise RuntimeError('Archive exists; preserve it')
    with tarfile.open(archive,'w') as output:
        for p in sorted(stage.rglob('*')):
            if p.is_file():output.add(p,arcname=str(p.relative_to(stage)).replace('\\','/'))
    print(json.dumps(dict(archive=str(archive),sha256=sha(archive),files=len(hashes))))

if __name__=='__main__':main()
