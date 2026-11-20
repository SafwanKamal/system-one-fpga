"""Package the routed v9g bitstream (v9f + P=4 attention) as a pilot FPGA app plus the board bundle.

The bitstream is the routed place-and-route trial in build/v2/core-feasibility/p4. Its HLS
source is byte-identical to hls/qwen_decoder_v9g/ and, apart from the two #include paths, to
the source that passed the C-sim exactness audit (experiments/attention_p4/PROTOCOL.md). Its
HLS and Vivado scripts equal v9f's apart from directory paths.

  --freeze   write build/v2/qwen-fpga-decoder-v9g/hardware-source-sha256.json (once)
  (default)  verify everything and write the pilot stage and v9g-pilot.tar

Writes only under build/v2/qwen-fpga-decoder-v9g. Nothing here touches the sealed RC1 package.
"""
import hashlib, json, re, shutil, subprocess, sys, tarfile, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRIAL = ROOT / 'build/v2/core-feasibility/p4'
BUILD = ROOT / 'build/v2/qwen-fpga-decoder-v9g'
V9E = ROOT / 'build/v2/qwen-fpga-decoder-v9e/deployment/sysone-qwen-decoder-v9e'
APP = 'sysone-qwen-decoder-v9g'
AUDIT_DIR = ROOT / 'build/v2/attention-p4-audit'
AUDITED = ROOT / 'experiments/attention_p4/qwen_decoder.cpp'
SRC = ['qwen_decoder.cpp', 'matrix_q8.hpp', 'model_profile.hpp']
PILOT_FILES = ['experiments/attention_p4/pilot.py', 'experiments/attention_p4/swap_v9g.py',
               'experiments/attention_p4/BOARD_PROTOCOL.md', 'build/v2/spec-qual/workload.json',
               'build/v2/spec-qual/board/bootb-full/qual.json', 'build/v2/spec-qual/board/bootc-resume/qual.json']


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 24), b''):
            h.update(b)
    return h.hexdigest()


def lines(p):
    return Path(p).read_bytes().replace(b'\r\n', b'\n').split(b'\n')


def frozen_set():
    names = ['hls/qwen_decoder_v9g/' + n for n in SRC + ['release-synth.tcl', 'create_kr260.tcl']]
    names += ['build/v2/core-feasibility/p4/src/' + n for n in SRC]
    names += ['build/v2/core-feasibility/p4/ip.zip', 'build/v2/core-feasibility/p4/synth.tcl',
              'build/v2/core-feasibility/p4/create_kr260.tcl']
    return {n: sha(ROOT / n) for n in names}


def check_sources():
    for n in SRC:
        if sha(TRIAL / 'src' / n) != sha(ROOT / 'hls/qwen_decoder_v9g' / n):
            raise RuntimeError('v9g source differs from the routed trial: ' + n)
    for n in SRC[1:]:
        if sha(ROOT / 'hls/qwen_decoder_v9f' / n) != sha(ROOT / 'hls/qwen_decoder_v9g' / n):
            raise RuntimeError('Header differs from v9f (audit used the v9f headers): ' + n)
    a, b = lines(AUDITED), lines(ROOT / 'hls/qwen_decoder_v9g/qwen_decoder.cpp')
    expect = {b'#include "../../hls/qwen_decoder_v9f/model_profile.hpp"': b'#include "model_profile.hpp"',
              b'#include "../../hls/qwen_decoder_v9f/matrix_q8.hpp"': b'#include "matrix_q8.hpp"'}
    diffs = [(x, y) for x, y in zip(a, b) if x != y]
    if len(a) != len(b) or sorted(diffs) != sorted(expect.items()):
        raise RuntimeError('v9g source differs from the audited source beyond the include paths')
    prereg = json.loads((AUDIT_DIR / 'prereg.json').read_text())
    if AUDITED.read_bytes().replace(b'\r\n', b'\n') != AUDITED.read_bytes() or \
            sha(AUDITED) not in json.dumps(prereg):
        raise RuntimeError('Audited source hash not in the audit pre-run receipt')
    if json.loads((AUDIT_DIR / 'p4-results.json').read_text())['result'] != 'PASS' or \
            json.loads((AUDIT_DIR / 'item1-cross-kernel.json').read_text())['result'] != 'PASS':
        raise RuntimeError('P=4 audit did not pass')
    fx = (AUDIT_DIR / 'fixtures-console.log').read_text(errors='replace')
    if 'PASS long context positions=2048' not in fx or 'PASS four real Q8 batch lanes' not in fx:
        raise RuntimeError('P=4 fixtures did not pass')
    for t in ('synth.tcl', 'create_kr260.tcl'):
        v9f = (ROOT / 'hls/qwen_decoder_v9f' / ('release-synth.tcl' if t == 'synth.tcl' else t)).read_text()
        v9f = v9f.replace('S:/build/v2/qwen-fpga-decoder-v9f/hls-synth/solution', 'S:/build/v2/core-feasibility/p4/hls/solution')
        v9f = v9f.replace('S:/hls/qwen_decoder_v9f/', 'S:/build/v2/core-feasibility/p4/src/')
        v9f = v9f.replace('S:/build/v2/qwen-fpga-decoder-v9f/qwen_decoder_ip.zip', 'S:/build/v2/core-feasibility/p4/ip.zip')
        v9f = v9f.replace('S:/build/v2/qwen-fpga-decoder-v9f/hls-synth', 'S:/build/v2/core-feasibility/p4/hls')
        v9f = v9f.replace('S:/build/v2/qwen-fpga-decoder-v9f/', 'S:/build/v2/core-feasibility/p4/')
        if v9f.replace('\r\n', '\n') != (TRIAL / t).read_text().replace('\r\n', '\n'):
            raise RuntimeError('Trial script differs from v9f beyond paths: ' + t)


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    pin = BUILD / 'hardware-source-sha256.json'
    check_sources()
    if '--freeze' in sys.argv:
        if pin.exists():
            raise RuntimeError('Already frozen')
        pin.write_text(json.dumps(frozen_set(), indent=1) + '\n')
        print('frozen', pin)
        return
    frozen = json.loads(pin.read_text())
    if frozen != frozen_set():
        raise RuntimeError('Hardware source changed after freezing')
    project = TRIAL / 'vivado'
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
    if (TRIAL / 'ip.zip').stat().st_mtime > bit.stat().st_mtime:
        raise RuntimeError('IP export is newer than the bitstream')
    header = (TRIAL / 'hls/solution/impl/ip/drivers/qwen_decoder_v1_0/src/xqwen_decoder_hw.h').read_text()
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
    for old, new in (('sysone-qwen-decoder-v9e.bit.bin', APP + '.bit.bin'), ('xlnx,qwen-decoder-v9e-1.0', 'xlnx,qwen-decoder-v9g-1.0')):
        if dts.count(old) != 1:
            raise RuntimeError('Unexpected v9e overlay source: ' + old)
        dts = dts.replace(old, new)
    (app / (APP + '.dts')).write_text(dts, encoding='ascii')
    shutil.copyfile(V9E / 'shell.json', app / 'shell.json')
    build = json.loads((V9E / 'build.json').read_text())
    build.update(app_name=APP, candidate='v9g', baseline='v9e sysone-qwen-decoder-v9e',
                 bitstream_sha256=sha(bit), xsa_sha256=sha(xsa), routed_timing_sha256=sha(timing),
                 bus_skew_report_sha256=sha(skew), bus_skew_min_slack_ns=min(float(r[2]) for r in rows),
                 matrix_core_sha256=frozen['hls/qwen_decoder_v9g/matrix_q8.hpp'],
                 hardware_sources_sha256=frozen, csim_audit_sha256=sha(AUDIT_DIR / 'p4-results.json'),
                 audited_source_sha256=sha(AUDITED),
                 changes_vs_v9e=['v9f commands 11 and 12 (batched final norm and vocabulary head)',
                                 'attention serves P=4 tokens per K/V tile pass (v9e/v9f: P=2); carried per-slot state indexed [slot/P][slot%P] in LUTRAM',
                                 'per-token arithmetic and order unchanged (C-sim audit: v9f and P=4 dumps byte-identical; mixed/rollback/decode schedules identical; fixtures worst=0)'])
    build.pop('compiled_profile_source_sha256', None)
    (app / 'build.json').write_text(json.dumps(build, indent=2) + '\n')
    bundle = stage / 'bundle'
    bundle.mkdir()
    for name in PILOT_FILES:
        shutil.copyfile(ROOT / name, bundle / Path(name).name if 'qual.json' not in name else bundle / (Path(name).parent.name + '-qual.json'))
    shutil.copyfile(ROOT / 'experiments/spec_service/spec_decode.py', bundle / 'spec_decode.py')
    hashes = {str(p.relative_to(stage)).replace('\\', '/'): sha(p) for p in stage.rglob('*') if p.is_file()}
    (stage / 'pilot-sha256.json').write_text(json.dumps(hashes, indent=2) + '\n')
    archive = BUILD / 'v9g-pilot.tar'
    with tarfile.open(archive, 'w') as out:
        for p in sorted(stage.rglob('*')):
            if p.is_file():
                out.add(p, arcname=str(p.relative_to(stage)).replace('\\', '/'))
    print(json.dumps(dict(archive=str(archive), sha256=sha(archive), files=len(hashes), bitstream_sha256=build['bitstream_sha256'])))


if __name__ == '__main__':
    main()
