"""Capture only linear LUT loads locally; preserve protocol and sealed parents."""
import argparse
import json
import shutil
from create_typed200_flush_candidate import ROOT, OUT as PARENT, verify as parent_verify, sha

OUT = ROOT/'rtl/v2/candidates/typed200_lut_capture'


def verify():
    parent = parent_verify()
    m = json.loads((OUT/'candidate.json').read_text())
    assert sha(PARENT/'candidate.json') == m['parent_manifest_sha256']
    actual = {p.relative_to(OUT).as_posix(): sha(p) for p in OUT.rglob('*') if p.suffix in ('.sv', '.v')}
    assert actual == m['candidate_sha256']
    assert {n for n in actual if actual[n] != parent['candidate_sha256'].get(n)} == {'encoder/linear_engine.sv'}
    return m


def create():
    parent_verify()
    assert not OUT.exists()
    shutil.copytree(PARENT, OUT)
    p = OUT/'encoder/linear_engine.sv'
    s = p.read_text()
    original = '''    always_ff @(posedge clk) begin
        if (load_state == L_LUT && take) begin
            for (int b = 0; b < 16; b++) begin
                lut[16 * load_beat[3:0] + b] <= $signed(read_data[8*b +: 8]);
            end
        end
'''
    assert s.count(original) == 1
    s = s.replace(original, '''    // Local payload/row capture removes the AXI response bus from the LUT
    // write fanout. Only table writes move one edge; load/request FSMs do not.
    // Compute uses this table after subsequent parameter/weight loading.
    logic lut_capture_valid;
    logic [3:0] lut_capture_row;
    logic [127:0] lut_capture_data;
    always_ff @(posedge clk or posedge reset) begin
        if(reset) lut_capture_valid <= 1'b0;
        else lut_capture_valid <= load_state == L_LUT && take;
    end
    always_ff @(posedge clk) begin
        if(load_state == L_LUT && take) begin
            lut_capture_row <= load_beat[3:0];
            lut_capture_data <= read_data;
        end
        if(lut_capture_valid && !reset) begin
            for(int b=0;b<16;b++)
                lut[16 * lut_capture_row + b] <= $signed(lut_capture_data[8*b +: 8]);
        end
    end

    always_ff @(posedge clk) begin
''')
    p.write_text(s)
    (OUT/'candidate.json').write_text(json.dumps({
        'candidate': 'typed200_lut_capture', 'sealed': False,
        'parent_manifest_sha256': sha(PARENT/'candidate.json'),
        'candidate_sha256': {p.relative_to(OUT).as_posix(): sha(p) for p in OUT.rglob('*') if p.suffix in ('.sv', '.v')},
        'hardware_qualified': False, 'numerical_contract_changed': False,
        'deadline_or_epoch_logic_changed': False,
        'internal_lut_write_delay_cycles': 1,
        'intended_external_cycle_delta': 0,
        'status': 'Experimental: independent arithmetic reference, golden outputs/cycles, reset/ordering and physical evidence required',
    }, indent=2)+'\n')
    verify()


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--verify', action='store_true'); a = p.parse_args()
    verify() if a.verify else create()
    print('PASS isolated LUT capture inventory; behavior/timing not yet verified')
