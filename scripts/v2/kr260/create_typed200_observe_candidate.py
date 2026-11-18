"""Separate observational cycle-count pipeline; preserve all sealed parents."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
from create_typed200_flush_candidate import ROOT, OUT as PARENT, verify as parent_verify

OUT = ROOT/'rtl/v2/candidates/typed200_observe'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify():
    parent_verify()
    m = json.loads((OUT/'candidate.json').read_text())
    assert sha(PARENT/'candidate.json') == m['parent_manifest_sha256']
    actual = {p.relative_to(OUT).as_posix(): sha(p) for p in OUT.rglob('*') if p.suffix in ('.sv', '.v')}
    assert actual == m['candidate_sha256']
    parent = json.loads((PARENT/'candidate.json').read_text())['candidate_sha256']
    assert {n for n in actual if actual[n] != parent.get(n)} == {
        'encoder/encoder_system.sv', 'common/observed_cycle_counter.sv'}
    return m


def create():
    m = parent_verify()
    assert m['sealed'] and not OUT.exists()
    shutil.copytree(PARENT, OUT)
    module = '''// Observational only: registered event controls, exact current-edge count.
// Pending clear dominates increment. Unsigned arithmetic wraps modulo 2**WIDTH.
// Never use this module as a delayed deadline or as proof of bus quiescence.
module observed_cycle_counter #(parameter integer WIDTH=32)(
    input logic clk, reset, clear, increment,
    output wire [WIDTH-1:0] count
);
    logic pending_clear, pending_increment;
    logic [WIDTH-1:0] bank;
    always_ff @(posedge clk or posedge reset) begin
        if(reset) begin
            pending_clear <= 0;
            pending_increment <= 0;
            bank <= 0;
        end else begin
            pending_clear <= clear;
            pending_increment <= increment;
            if(pending_clear) bank <= 0;
            else if(pending_increment) bank <= bank + 1'b1;
        end
    end
    assign count = pending_clear ? {WIDTH{1'b0}} : bank + {{(WIDTH-1){1'b0}}, pending_increment};
endmodule
'''
    (OUT/'common/observed_cycle_counter.sv').write_text(module)
    p = OUT/'encoder/encoder_system.sv'
    s = p.read_text()
    for line in ("            encoder_clocks_reg <= '0;\n", "            total_clocks_reg <= '0;\n",
                 "            if (state_reg != IDLE) total_clocks_reg <= total_clocks_reg + 1'b1;\n",
                 "            if (encoder_busy) encoder_clocks_reg <= encoder_clocks_reg + 1'b1;\n",
                 "                        encoder_clocks_reg <= '0;\n", "                        total_clocks_reg <= '0;\n"):
        # Exact indentation prevents accidentally removing accepted-start clears twice.
        assert s.count('\n'+line) == 1, repr(line)
        s = s.replace('\n'+line, '\n', 1)
    anchor = '    assign busy = (state_reg != IDLE);'
    assert s.count(anchor) == 1
    s = s.replace(anchor, '''    // Clear at the original accepted-start edge; these outputs are observational.
    wire count_clear = state_reg == IDLE && run_start;
    observed_cycle_counter encoder_count_inst (
        .clk(clk), .reset(reset), .clear(count_clear),
        .increment(encoder_busy), .count(encoder_clocks_reg));
    observed_cycle_counter request_count_inst (
        .clk(clk), .reset(reset), .clear(count_clear),
        .increment(state_reg != IDLE), .count(total_clocks_reg));

'''+anchor)
    p.write_text(s)
    m = {'candidate': 'typed200_observe', 'sealed': False,
         'parent_manifest_sha256': sha(PARENT/'candidate.json'),
         'candidate_sha256': {p.relative_to(OUT).as_posix(): sha(p) for p in OUT.rglob('*') if p.suffix in ('.sv', '.v')},
         'hardware_qualified': False, 'numerical_contract_changed': False,
         'deadline_or_epoch_logic_changed': False,
         'intended_cycle_delta': 0, 'intended_reported_count_delta': 0,
         'status': 'Experimental; requires independent proof, regression and physical evidence'}
    (OUT/'candidate.json').write_text(json.dumps(m, indent=2)+'\n')
    verify()


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--verify', action='store_true'); args = p.parse_args()
    verify() if args.verify else create()
    print('PASS isolated observation candidate inventory; no qualification claimed')
