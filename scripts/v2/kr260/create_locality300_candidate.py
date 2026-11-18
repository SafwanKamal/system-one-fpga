"""Create once (or verify) an isolated candidate from the qualified RTL snapshot.

Never edits public/frozen sources, packages, fixtures or recovery. No Vivado or
deployment is invoked. Candidate source changes require a new manifest/review.
"""
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'build/v2/kr260-opt-attention-context-capture-large'
OUT = ROOT / 'rtl/v2/candidates/locality300'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise ValueError(f'Expected exactly one source anchor: {path}: {old[:60]}')
    path.write_text(text.replace(old, new), encoding='utf-8')


def verify():
    manifest = json.loads((OUT / 'candidate.json').read_text())
    actual_rtl = {p.relative_to(OUT).as_posix() for p in OUT.rglob('*')
                  if p.is_file() and p.suffix in ('.sv', '.v')}
    if actual_rtl != set(manifest['candidate_sha256']):
        raise ValueError('Unexpected candidate RTL source inventory')
    for name, expected in manifest['baseline_sha256'].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f'Qualified public source changed: {name}')
        frozen = BASE / 'rtl-snapshot' / Path(name).relative_to('rtl/v2')
        if sha(frozen) != expected:
            raise ValueError(f'Qualified snapshot changed: {name}')
    for name, expected in manifest['candidate_sha256'].items():
        if sha(OUT / name) != expected:
            raise ValueError(f'Candidate changed after manifest: {name}')
    return manifest


def create():
    if OUT.exists():
        raise FileExistsError('Preserve existing candidate; use --verify')
    reg = json.loads((BASE / 'regression.json').read_text())
    for name, expected in reg['rtl_sha256'].items():
        source = BASE / 'rtl-snapshot' / Path(name).relative_to('rtl/v2')
        if sha(source) != expected or sha(ROOT / name) != expected:
            raise ValueError(f'Baseline mismatch: {name}')
    OUT.mkdir(parents=True)
    for name in reg['rtl_sha256']:
        relative = Path(name).relative_to('rtl/v2')
        target = OUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((BASE / 'rtl-snapshot' / relative).read_bytes())

    # Duplicate the existing mux output stage per query group, not an extra stage.
    # Each copy has its own selector/data FFs so query consumers need not route
    # through the global shared operand register. Latency remains five clocks.
    p = OUT / 'common/activation_read_capture.sv'
    replace_once(p, 'parameter integer PORTS = 4,',
                 'parameter integer PORTS = 4,\n    parameter integer QUERY_GROUPS = 4,')
    replace_once(p, 'output logic [WIDTH-1:0] port_data [0:PORTS-1]',
                 'output logic [WIDTH-1:0] port_data [0:PORTS-1],\n'
                 '    output logic [WIDTH-1:0] query_group_data [0:QUERY_GROUPS-1]')
    replace_once(p, '\nendmodule', '''
    for (genvar g = 0; g < QUERY_GROUPS; g++) begin : gen_query_read
        (* DONT_TOUCH = "TRUE" *) logic [SELECT_WIDTH-1:0] select_reg;
        (* DONT_TOUCH = "TRUE" *) logic [WIDTH-1:0] data_reg;
        always_ff @(posedge clk) begin
            select_reg <= physical_select[0];
            data_reg <= select_reg < BUFFERS ? captured_data[select_reg] : '0;
        end
        assign query_group_data[g] = data_reg;
    end
endmodule''')

    p = OUT / 'encoder/encoder_layer.sv'
    replace_once(p, 'if (LOCAL_READ_CAPTURE != 0) begin : gen_local_read_capture',
                 'localparam integer QUERY_GROUPS = (ATTENTION_LANES + 3) / 4;\n'
                 '    logic [127:0] query_group_data [0:QUERY_GROUPS-1];\n'
                 '    if (LOCAL_READ_CAPTURE != 0) begin : gen_local_read_capture')
    replace_once(p, 'activation_read_capture capture_inst (.clk(clk),',
                 'activation_read_capture #(.QUERY_GROUPS(QUERY_GROUPS)) capture_inst (.clk(clk),')
    replace_once(p, '.port_data(port_data_reg));',
                 '.port_data(port_data_reg), .query_group_data(query_group_data));')
    replace_once(p, 'end else begin : gen_original_read_mux',
                 'end else begin : gen_original_read_mux\n'
                 '        for (genvar g=0; g<QUERY_GROUPS; g++)\n'
                 '            assign query_group_data[g] = port_data_reg[0];')
    replace_once(p, '.q_data(port_data[0]),',
                 '.q_data(port_data[0]),\n        .query_group_data(query_group_data),')
    old = '''    always_comb begin
        if (opcode == OP_ATTENTION) begin
            mac_a = attention_mac_a;
            mac_b = attention_mac_b;
        end else begin
            mac_a = linear_mac_a;
            mac_b = linear_mac_b;
        end
    end'''
    new = '''    // Local registered selects settle during instruction setup, before any
    // operand issues. No added MAC latency, no retimed arithmetic/tag pipeline.
    for (genvar c=0; c<TILE_OUT; c++) begin : gen_local_mac_select
        for (genvar g=0; g<4; g++) begin : gen_word_group
            (* DONT_TOUCH = "TRUE" *) logic select_reg;
            always_ff @(posedge clk) select_reg <= opcode == OP_ATTENTION;
            for (genvar r=g*4; r<(g+1)*4; r++)
                assign mac_a[c][r] = select_reg ? attention_mac_a[c][r] : linear_mac_a[c][r];
`ifndef SYNTHESIS
            always @(posedge clk) if (!reset && (linear_perf[2] || attention_mac_issue))
                assert(select_reg == (opcode == OP_ATTENTION))
                    else $fatal(1,"Local MAC A select not settled before issue");
`endif
        end
    end
    for (genvar r=0; r<16; r++) begin : gen_local_b_select
        (* DONT_TOUCH = "TRUE" *) logic select_reg;
        always_ff @(posedge clk) select_reg <= opcode == OP_ATTENTION;
        assign mac_b[r] = select_reg ? attention_mac_b[r] : linear_mac_b[r];
    end'''
    replace_once(p, old, new)

    p = OUT / 'encoder/attention_engine.sv'
    replace_once(p, 'input logic [127:0] q_data,',
                 'input logic [127:0] q_data,\n'
                 '    input logic [127:0] query_group_data [0:(LANES+3)/4-1],')
    replace_once(p, 'data_reg <= q_data;', 'data_reg <= query_group_data[g];')

    # A new family is intentionally rejected by existing deployment/runtime guards.
    p = OUT / 'platform/kr260/kr260_encoder.sv'
    replace_once(p, "32'h53700000", "32'h53800000")
    replace_once(p, 'logic run_done, busy;', '''logic run_done, busy;
    logic contract_start, contract_valid, contract_active, contract_ready, contract_quarantined;
    logic [2:0] contract_outcome;
    logic [31:0] contract_age, contract_budget;
    wire contract_ack = write_fire && s_axil_awaddr[7:2] == 0 && s_axil_wdata[1];
    deadline_supervisor contract_inst(.clk, .reset, .start(contract_start),
        .budget_cycles(contract_budget), .ack(contract_ack), .core_done(run_done),
        .core_fault(run_result[71:64] != 0), .ready(contract_ready),
        .active(contract_active), .result_valid(contract_valid),
        .quarantined(contract_quarantined), .outcome(contract_outcome), .elapsed(contract_age));''')
    replace_once(p, "run_start <= 1'b0;\n            result_latch", "run_start <= 1'b0;\n            contract_start <= 1'b0;\n            contract_budget <= 32'hffffffff;\n            result_latch")
    replace_once(p, "end else begin\n            run_start <= 1'b0;", "end else begin\n            run_start <= 1'b0;\n            contract_start <= 1'b0;")
    replace_once(p, 'if (run_done) begin', 'if (run_done && !contract_quarantined) begin')
    replace_once(p, "if (s_axil_wdata[0] && !busy && !run_start) begin\n                            run_start <= 1'b1;", "if (s_axil_wdata[0] && !busy && !run_start && contract_ready) begin\n                            contract_start <= 1'b1;\n                            run_start <= contract_budget != 0;")
    replace_once(p, "6'h0B: result_reg <= s_axil_wdata;", "6'h0B: result_reg <= s_axil_wdata;\n                    6'h1A: if (!busy && contract_ready && !run_start) contract_budget <= s_axil_wdata;")
    replace_once(p, "6'h08: s_axil_rdata <= program_reg;", "6'h18: s_axil_rdata <= {21'd0, contract_outcome, 4'd0, contract_ready, contract_quarantined, contract_active, contract_valid};\n                    6'h19: s_axil_rdata <= contract_age;\n                    6'h1A: s_axil_rdata <= contract_budget;\n                    6'h1B: s_axil_rdata <= 32'h53595431; // independent deadline-outcome ABI\n                    6'h08: s_axil_rdata <= program_reg;")
    replace_once(p, 'assign irq = done_reg;', 'assign irq = done_reg || contract_valid;')

    supervisor = ROOT / 'rtl/contracts/deadline_supervisor.sv'
    (OUT / 'common/deadline_supervisor.sv').write_bytes(supervisor.read_bytes())
    manifest = {
        'candidate': 'locality300', 'experimental': True, 'target_mhz': 300,
        'timing_qualified': False, 'hardware_qualified': False,
        'baseline_sha256': reg['rtl_sha256'],
        'candidate_sha256': {p.relative_to(OUT).as_posix(): sha(p) for p in OUT.rglob('*') if p.is_file()},
        'capability_word': '0x5387ffff', 'deadline_abi': '0x53595431',
        'profiles': {'encoder384': {**reg['profile'], 'max_hidden': 384},
                     'capacity1024': reg['profile']},
        'read_latency': 5, 'arithmetic_changed': False,
        'claims': ['No 300 MHz closure or successful-completion guarantee established',
                   'Supervisor bounds outcome-register availability in active PL clock domain',
                   'Timeout quarantines until safe external system reset; AXI is never aborted'],
    }
    (OUT / 'candidate.json').write_text(json.dumps(manifest, indent=2)+'\n')
    verify()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.verify:
        verify()
    else:
        create()
    print('PASS locality300 isolated source manifest; no build/deployment')
