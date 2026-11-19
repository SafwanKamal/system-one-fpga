"""Package the routed v9f bitstream as a pilot FPGA app plus the board pilot bundle.

v9f = v9e + batched final norm (cmd 11) and batched vocabulary head (cmd 12); see
experiments/batched_head. The app reuses the v9e overlay (name and compatible string changed)
and the v9e build.json, with v9f's identity fields replaced. Writes only under
build/v2/qwen-fpga-decoder-v9f. Nothing here touches the sealed RC1 package.
"""
import hashlib, json, re, shutil, subprocess, tarfile, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / 'build/v2/qwen-fpga-decoder-v9f'
V9E = ROOT / 'build/v2/qwen-fpga-decoder-v9e/deployment/sysone-qwen-decoder-v9e'
APP = 'sysone-qwen-decoder-v9f'
AUDIT = ROOT / 'build/v2/batched-head-audit/results.json'
PILOT_FILES = ['experiments/batched_head/pilot.py', 'experiments/batched_head/swap_v9f.py',
               'experiments/batched_head/BOARD_PROTOCOL.md', 'build/v2/spec-qual/workload.json',
               'build/v2/spec-qual/board/bootb-full/qual.json', 'build/v2/spec-qual/board/bootc-resume/qual.json']


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 24), b''):
            h.update(b)
    return h.hexdigest()


def main():
    frozen = json.loads((BUILD / 'hardware-source-sha256.json').read_text())
    for name, digest in frozen.items():
        if sha(ROOT / name) != digest:
            raise RuntimeError('Hardware source changed after synthesis: ' + name)
    if json.loads(AUDIT.read_text())['result'] != 'PASS':
        raise RuntimeError('C-sim audit did not pass')
    audited = json.loads((ROOT / 'build/v2/batched-head-audit/prereg.json').read_text())['source_sha256']
    for name in ('hls/qwen_decoder_v9f/qwen_decoder.cpp', 'hls/qwen_decoder_v9f/matrix_q8.hpp', 'hls/qwen_decoder_v9f/model_profile.hpp'):
        if audited[name] != frozen[name]:
            raise RuntimeError('Synthesized source differs from the audited source: ' + name)
    project = BUILD / 'vivado'
    bit = project / 'qwen_decoder_kr260.runs/impl_1/system_wrapper.bit'
    xsa = project / 'qwen_decoder.xsa'
    timing = project / 'routed-timing.rpt'
    if not all(p.is_file() for p in (bit, xsa, timing)):
        raise RuntimeError('Completed routed hardware export required')
    if 'All user specified timing constraints are met.' not in timing.read_text():
        raise RuntimeError('Routed timing did not pass')
    skew = project / 'qwen_decoder_kr260.runs/impl_1/system_wrapper_bus_skew_postroute_physopted.rpt'
    rows = re.findall(r'^\s+(?:Slow|Fast)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(-?\d+\.\d+)\s*$', skew.read_text(), re.M)
    if not rows or any(float(r[2]) < 0 for r in rows):
        raise RuntimeError('Clock converter bus skew did not pass')
    with zipfile.ZipFile(xsa) as export:
        members = [p for p in export.namelist() if p.endswith('.bit')]
        if len(members) != 1 or export.read(members[0]) != bit.read_bytes():
            raise RuntimeError('Hardware export does not contain final bitstream')
    header = (BUILD / 'hls-synth/solution/impl/ip/drivers/qwen_decoder_v1_0/src/xqwen_decoder_hw.h').read_text()
    v9e_header = (ROOT / 'build/v2/qwen-fpga-decoder-v9e/hls-release/solution/impl/ip/drivers/qwen_decoder_v1_0/src/xqwen_decoder_hw.h').read_text()
    if header != v9e_header:
        raise RuntimeError('Kernel CSR map differs from v9e')
    stage = BUILD / 'pilot'
    if stage.exists():
        raise RuntimeError('Pilot stage exists; preserve it')
    app = stage / APP
    app.mkdir(parents=True)
    shutil.copyfile(bit, app / 'decoder.bit')
    (app / 'bitstream.bif').write_text('all:\n{\n decoder.bit\n}\n', encoding='ascii')
    subprocess.run(['C:/AMDDesignTools/2025.2/Vivado/bin/bootgen.bat', '-arch', 'zynqmp', '-image', 'bitstream.bif',
                    '-w', '-process_bitstream', 'bin'], cwd=app, check=True)
    shutil.copyfile(app / 'decoder.bit.bin', app / (APP + '.bit.bin'))
    for name in ('decoder.bit', 'decoder.bit.bin', 'bitstream.bif'):
        (app / name).unlink()
    dts = (V9E / 'sysone-qwen-decoder-v9e.dts').read_text()
    for old, new in (('sysone-qwen-decoder-v9e.bit.bin', APP + '.bit.bin'), ('xlnx,qwen-decoder-v9e-1.0', 'xlnx,qwen-decoder-v9f-1.0')):
        if dts.count(old) != 1:
            raise RuntimeError('Unexpected v9e overlay source: ' + old)
        dts = dts.replace(old, new)
    (app / (APP + '.dts')).write_text(dts, encoding='ascii')
    shutil.copyfile(V9E / 'shell.json', app / 'shell.json')
    build = json.loads((V9E / 'build.json').read_text())
    build.update(app_name=APP, candidate='v9f', baseline='v9e sysone-qwen-decoder-v9e',
                 bitstream_sha256=sha(bit), xsa_sha256=sha(xsa), routed_timing_sha256=sha(timing),
                 bus_skew_report_sha256=sha(skew), bus_skew_min_slack_ns=min(float(r[2]) for r in rows),
                 matrix_core_sha256=frozen['hls/qwen_decoder_v9f/matrix_q8.hpp'],
                 hardware_sources_sha256=frozen, csim_audit_sha256=sha(AUDIT),
                 changes_vs_v9e=['cmd 11: final norm for slots 0..rows-1',
                                 'cmd 12: vocabulary head chunk for slots 0..layer-1 in one weight pass, one running argmax per slot; slot b result at result+32*b',
                                 'cmd 3 and cmd 4 unchanged; decoder arithmetic unchanged (C-sim audit 30/30 lanes identical over the full vocabulary)'])
    build.pop('compiled_profile_source_sha256', None)
    (app / 'build.json').write_text(json.dumps(build, indent=2) + '\n')
    bundle = stage / 'bundle'
    bundle.mkdir()
    for name in PILOT_FILES:
        shutil.copyfile(ROOT / name, bundle / Path(name).name if 'qual.json' not in name else bundle / (Path(name).parent.name + '-qual.json'))
    shutil.copyfile(ROOT / 'experiments/spec_service/spec_decode.py', bundle / 'spec_decode.py')
    hashes = {str(p.relative_to(stage)).replace('\\', '/'): sha(p) for p in stage.rglob('*') if p.is_file()}
    (stage / 'pilot-sha256.json').write_text(json.dumps(hashes, indent=2) + '\n')
    archive = BUILD / 'v9f-pilot.tar'
    with tarfile.open(archive, 'w') as out:
        for p in sorted(stage.rglob('*')):
            if p.is_file():
                out.add(p, arcname=str(p.relative_to(stage)).replace('\\', '/'))
    print(json.dumps(dict(archive=str(archive), sha256=sha(archive), files=len(hashes), bitstream_sha256=build['bitstream_sha256'])))


if __name__ == '__main__':
    main()
