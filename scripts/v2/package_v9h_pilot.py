"""Package the routed S2 build (v9g + merged q/k-norm RMS call + split small passes on a second
weight port, HP1) as FPGA app sysone-qwen-decoder-v9h plus a board bundle.

CSR map: identical to v9e/v9g except that model_b occupies 0x70-0x77 and scratch moved from
0x78 to 0x7c. The v9h runtime package therefore carries its own registers.json (scratch=124);
model_b resets to 0, the same value the runtime writes for model.
usage: python scripts/v2/package_v9h_pilot.py  -> build/v2/qwen-fpga-decoder-v9h/v9h-pilot.tar
"""
import hashlib, json, re, shutil, subprocess, tarfile, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRIAL = ROOT / 'build/v2/dual-port-study/s1'
BUILD = ROOT / 'build/v2/qwen-fpga-decoder-v9h'
V9E = ROOT / 'build/v2/qwen-fpga-decoder-v9e/deployment/sysone-qwen-decoder-v9e'
APP = 'sysone-qwen-decoder-v9h'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

project = TRIAL / 'vivado'
bit = project / 'qwen_decoder_kr260.runs/impl_1/system_wrapper.bit'
xsa = project / 'qwen_decoder.xsa'
timing = project / 'routed-timing.rpt'
assert 'All user specified timing constraints are met.' in timing.read_text()
skew = (project / 'qwen_decoder_kr260.runs/impl_1/system_wrapper_bus_skew_postroute_physopted.rpt').read_text()
rows = re.findall(r'^\s+(?:Slow|Fast)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(-?\d+\.\d+)\s*$', skew, re.M)
assert rows and all(float(r[2]) >= 0 for r in rows), 'bus skew'
with zipfile.ZipFile(xsa) as z:
    m = [p for p in z.namelist() if p.endswith('.bit')]
    assert len(m) == 1 and z.read(m[0]) == bit.read_bytes(), 'xsa/bit mismatch'
hdr = (TRIAL / 'hls/solution/impl/ip/drivers/qwen_decoder_v1_0/src/xqwen_decoder_hw.h').read_text()
addr = dict(re.findall(r'#define XQWEN_DECODER_CONTROL_ADDR_(\w+)_DATA\s+0x([0-9a-f]+)', hdr))
regs = json.loads((ROOT / 'build/v2/hardware-consolidated-rc1/deployment-r2/registers.json').read_text())
new_regs = {k: int(addr[k.upper()], 16) for k in regs}
changed = {k: (regs[k], new_regs[k]) for k in regs if regs[k] != new_regs[k]}
assert changed == {'scratch': (120, 124)}, changed

if BUILD.exists():
    shutil.rmtree(BUILD)
stage = BUILD / 'pilot'
app = stage / APP
app.mkdir(parents=True)
shutil.copyfile(bit, app / 'decoder.bit')
(app / 'bitstream.bif').write_text('all:\n{\n decoder.bit\n}\n', encoding='ascii')
subprocess.run(['C:/AMDDesignTools/2025.2/Vivado/bin/bootgen.bat', '-arch', 'zynqmp', '-image', 'bitstream.bif',
                '-w', '-process_bitstream', 'bin'], cwd=app, check=True, capture_output=True)
shutil.copyfile(app / 'decoder.bit.bin', app / (APP + '.bit.bin'))
for n in ('decoder.bit', 'decoder.bit.bin', 'bitstream.bif'):
    (app / n).unlink()
dts = (V9E / 'sysone-qwen-decoder-v9e.dts').read_text()
for old, new in (('sysone-qwen-decoder-v9e.bit.bin', APP + '.bit.bin'), ('xlnx,qwen-decoder-v9e-1.0', 'xlnx,qwen-decoder-v9h-1.0')):
    assert dts.count(old) == 1
    dts = dts.replace(old, new)
(app / (APP + '.dts')).write_text(dts, encoding='ascii')
shutil.copyfile(V9E / 'shell.json', app / 'shell.json')
build = json.loads((V9E / 'build.json').read_text())
build.update(app_name=APP, candidate='v9h', baseline='v9g', bitstream_sha256=sha(bit), xsa_sha256=sha(xsa),
             routed_timing_sha256=sha(timing),
             changes_vs_v9g=['merged q/k head-norm RMS call site (same call order)',
                             'split small passes: batch<=4 streams row halves on weights (HP0) and weights_b (HP1) into slots 0-3 / 4-7',
                             'CSR: model_b at 0x70, scratch moved 0x78->0x7c'])
build.pop('compiled_profile_source_sha256', None)
(app / 'build.json').write_text(json.dumps(build, indent=2) + '\n')
(stage / 'registers-v9h.json').write_text(json.dumps(new_regs, indent=2) + '\n')

bundle = stage / 'bundle'
bundle.mkdir()
swap = (ROOT / 'experiments/attention_p4/swap_v9g.py').read_text()
assert swap.count("V9E, V9G = 'sysone-qwen-decoder-v9e', 'sysone-qwen-decoder-v9g'") == 1
swap = swap.replace("'sysone-qwen-decoder-v9g'", "'sysone-qwen-decoder-v9h'").replace('v9g', 'v9h')
(bundle / 'swap_v9h.py').write_text(swap)
pilot = (ROOT / 'experiments/dual_port/v9h_pilot.py').read_text()
(bundle / 'v9h_pilot.py').write_text(pilot)
for src, dst in (('experiments/spec_service/spec_decode.py', 'spec_decode.py'), ('experiments/draft_research/drafters.py', 'drafters.py'),
                 ('build/v2/spec-qual/workload.json', 'workload.json'), ('build/v2/draft-board/expected.json', 'expected.json'),
                 ('build/v2/spec-qual/board/bootb-full/qual.json', 'bootb-full-qual.json'),
                 ('build/v2/spec-qual/board/bootc-resume/qual.json', 'bootc-resume-qual.json')):
    shutil.copyfile(ROOT / src, bundle / dst)
hashes = {str(p.relative_to(stage)).replace('\\', '/'): sha(p) for p in sorted(stage.rglob('*')) if p.is_file()}
(stage / 'pilot-sha256.json').write_text(json.dumps(hashes, indent=1) + '\n')
tar = BUILD / 'v9h-pilot.tar'
with tarfile.open(tar, 'w') as t:
    for p in sorted(stage.rglob('*')):
        if p.is_file():
            t.add(p, arcname=str(p.relative_to(stage)).replace('\\', '/'))
print(json.dumps(dict(tar=str(tar), sha256=sha(tar), files=len(hashes), bitstream=sha(bit))))
