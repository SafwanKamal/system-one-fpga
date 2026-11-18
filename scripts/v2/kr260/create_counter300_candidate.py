"""Create a sealed counter-timing successor; never changes either baseline."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import create_locality300_candidate as parent

ROOT = parent.ROOT
OUT = ROOT / 'rtl/v2/candidates/counter300'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify():
    parent.verify()
    m = json.loads((OUT / 'candidate.json').read_text())
    assert sha(parent.OUT / 'candidate.json') == m['parent_manifest_sha256']
    inventory = {p.relative_to(OUT).as_posix() for p in OUT.rglob('*') if p.suffix in ('.v', '.sv')}
    assert inventory == set(m['candidate_sha256']), 'Unexpected RTL inventory'
    for name, value in m['candidate_sha256'].items():
        assert sha(OUT / name) == value, name
    return m


def create():
    m = parent.verify()
    if OUT.exists():
        raise FileExistsError('Preserve successor; use --verify')
    for name in m['candidate_sha256']:
        target = OUT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(parent.OUT / name, target)
    top = OUT / 'platform/kr260/kr260_encoder.sv'
    text = top.read_text()
    start = text.index('        logic [31:0] read_due;')
    end = text.index('    end else begin : gen_no_performance', start)
    text = text[:start] + '''        performance_telemetry telemetry_inst(.clk, .reset, .clear(run_start), .busy,
            .arvalid(m_axi_arvalid), .arready(m_axi_arready), .arlen(m_axi_arlen),
            .rvalid(m_axi_rvalid), .rready(m_axi_rready),
            .wvalid(m_axi_wvalid), .wready(m_axi_wready),
            .write_request_valid, .write_request_ready, .write_request_beats,
            .write_valid, .write_ready, .core_events(perf_events), .counts(perf_counts),
            .pending(telemetry_pending), .snapshot_ready(telemetry_ready));
''' + text[end:]
    text = text.replace('logic [31:0] perf_counts [0:9];',
                        'logic [31:0] perf_counts [0:9];\n    logic telemetry_pending, telemetry_ready;')
    text = text.replace('end else begin : gen_no_performance\n',
                        "end else begin : gen_no_performance\n        assign telemetry_pending = 0;\n        assign telemetry_ready = 1;\n")
    text = text.replace("32'h53800000", "32'h53900000")
    anchor = "6'h1B: s_axil_rdata <= 32'h53595431;"
    assert text.count(anchor) == 1
    text = text.replace(anchor, "6'h1C: s_axil_rdata <= {30'd0, done_reg && telemetry_ready, telemetry_pending};\n                    " + anchor)
    top.write_text(text)
    shutil.copyfile(ROOT / 'rtl/contracts/performance_telemetry.sv', OUT / 'common/performance_telemetry.sv')
    m.update(candidate='counter300', capability_word='0x5397ffff',
             parent_manifest_sha256=sha(parent.OUT / 'candidate.json'),
             telemetry_latency_cycles=1, telemetry_snapshot_register='0x70',
             candidate_sha256={p.relative_to(OUT).as_posix(): sha(p) for p in OUT.rglob('*') if p.suffix in ('.v', '.sv')})
    (OUT / 'candidate.json').write_text(json.dumps(m, indent=2)+'\n')
    verify()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--verify', action='store_true')
    args = p.parse_args()
    verify() if args.verify else create()
    print('PASS counter300 sealed successor and preserved parent/baseline')
