"""Isolate typed publication integration from the qualified 200 MHz snapshot.

Creates an unsealed development candidate. --seal is allowed once, after staged
verification. --verify thereafter checks both baseline and complete RTL inventory.
Never invokes FPGA builds or board actions.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'build/v2/kr260-opt-attention-context-capture-large'
OUT=ROOT/'rtl/v2/candidates/typed200'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inventory():return {p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.suffix in ('.sv','.v')}
def baseline():
    r=json.loads((BASE/'regression.json').read_text())
    for name,h in r['rtl_sha256'].items():
        assert sha(ROOT/name)==h,name
        assert sha(BASE/'rtl-snapshot'/Path(name).relative_to('rtl/v2'))==h,name
    return r
def create():
    r=baseline()
    if OUT.exists():raise FileExistsError('Preserve candidate')
    for name in r['rtl_sha256']:
        rel=Path(name).relative_to('rtl/v2');dst=OUT/rel;dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(BASE/'rtl-snapshot'/rel,dst)
    for src,dst in [('rtl/contracts/typed_publication_gate.sv','contracts/typed_publication_gate.sv'),
                    ('rtl/contracts/typed_intent_v1/typed_intent_guard.sv','contracts/typed_intent_guard.sv'),
                    ('rtl/contracts/typed_intent_v1/typed_intent_axil.sv','contracts/typed_intent_axil.sv'),
                    ('rtl/contracts/typed_epoch_tracker.sv','contracts/typed_epoch_tracker.sv')]:
        target=OUT/dst;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/src,target)
    # Pure observation of live state. No arithmetic/control changes in the port.
    p=OUT/'platform/kr260/axi_memory_port.sv';s=p.read_text()
    s=s.replace('output logic response_error ', 'output wire drained,\n    output logic response_error ',1)
    s=s.replace('\nendmodule','''
    // Pending descriptor slots appear as core_*_request_valid in both modes.
    // Include same-edge upstream requests and bus activity: an idle FSM alone
    // does not establish quiescence. Never use delayed diagnostic counters.
    assign drained = !reset && read_state_reg==READ_IDLE && write_state_reg==WRITE_IDLE
        && read_outstanding_reg==0 && deliver_left_reg==0 && length_count==0
        && responses_due_reg==0 && !read_request_valid && !write_request_valid
        && !core_read_request_valid && !core_write_request_valid && !write_valid
        && !m_axi_arvalid && !m_axi_awvalid && !m_axi_wvalid && !m_axi_rvalid && !m_axi_bvalid;
endmodule''')
    p.write_text(s)
    # Candidate-only ABI successor: native status, shape frame, deployment guard.
    p=OUT/'contracts/typed_intent_axil.sv';s=p.read_text()
    s=s.replace('    output wire admitted,','''    input logic environment_ready,
    input logic [31:0] encoder_clocks, request_clocks,
    output wire terminal_valid, terminal_quarantined, retired,
    output wire [15:0] admission_tokens, admission_first, admission_count,
    output logic [15:0] owned_tokens, owned_first, owned_count,
    output wire admitted,''')
    s=s.replace('wire start=control && wd==2 && request_complete && ready;',
        'wire start=control && wd==2 && request_complete && ready && environment_ready;')
    s=s.replace('    assign s_awready=', '''    wire shape_ok=bank[5][15:0]>0 && bank[5][15:0]<=128 && bank[28][31:16]==0
        && bank[28][15:0]>0 && bank[5][31:16]<bank[5][15:0]
        && ({1'b0,bank[5][31:16]}+{1'b0,bank[28][15:0]})<={1'b0,bank[5][15:0]};
    assign admission_tokens=bank[5][15:0];
    assign admission_first=bank[5][31:16];
    assign admission_count=bank[28][15:0];
    assign terminal_valid=valid;
    assign terminal_quarantined=quarantine;
    assign retired=ack;
    assign s_awready=''',1)
    s=s.replace('request_complete=written[2]==15 && written[3]==15 && written[4]==15;',
        'request_complete=written[2]==15 && written[3]==15 && written[4]==15 && written[5]==15 && written[28]==15;')
    s=s.replace("8'h04:read_value={27'd0,configured,quarantine,valid,active,ready};",
        "8'h04:read_value={27'd0,configured,quarantine,valid,active,(ready && environment_ready)};")
    s=s.replace("8'hc0:read_value=32'h54590101;", """8'hc4:read_value={owned_first,owned_tokens};
            8'hc8:read_value={16'd0,owned_count};
            8'hcc:read_value={27'd0,environment_ready,core_complete,core_success,live_quiet,quarantine};
            8'hd0:read_value=encoder_clocks;
            8'hd4:read_value=request_clocks;
            8'hc0:read_value=32'h54590201;""")
    s=s.replace('aw_full<=0;w_full<=0;aw<=0;wd<=0;ws<=0;',
        'aw_full<=0;w_full<=0;aw<=0;wd<=0;ws<=0;owned_tokens<=0;owned_first<=0;owned_count<=0;')
    s=s.replace('            if(s_bvalid && s_bready)', '''            if(admitted) begin
                owned_tokens<=admission_tokens;owned_first<=admission_first;owned_count<=admission_count;
            end
            if(s_bvalid && s_bready)''',1)
    s=s.replace('for(int i=2;i<14;i++) written[i]<=0;', 'for(int i=2;i<14;i++) written[i]<=0;\n                        written[28]<=0;')
    s=s.replace("aw<=8'h74 && aw[1:0]==0 && aw!=8'h1c", "aw<=8'h78 && aw[1:0]==0")
    s=s.replace('.budget_cycles(bank[4])','.budget_cycles(shape_ok ? bank[4] : 32\'d0)')
    p.write_text(s)
    # Reuse the exact qualified encoder/memory connections; remove legacy CSR
    # control entirely from the new top. Fixed model/buffer addresses have no CSR.
    s=(OUT/'platform/kr260/kr260_encoder.sv').read_text()
    s=s.replace('module kr260_encoder #(','''module typed200_encoder #(
    parameter logic [31:0] PROGRAM_ADDRESS=32'd1610613760,
    parameter logic [31:0] IDS_ADDRESS=32'd1645215744,
    parameter logic [31:0] RESULT_ADDRESS=32'd1645219840,''',1)
    s=s.replace('    input logic clk,','    input logic deployment_ready,\n    input logic clk,',1)
    s='// Isolated typed200 integration, ABI 0x54590201; no legacy start/descriptor CSR.\n'+s[s.index('module typed200_encoder #('):]
    a=s.index('    logic reset;');b=s.index('    // ------------------------------------------------------------- encoder',a)
    control=(ROOT/'scripts/v2/kr260/typed200_control.txt').read_text()
    s=s[:a]+control+'\n'+s[b:]
    s=s.replace('.response_error(memory_error)', '.response_error(memory_error), .drained(memory_drained)')
    (OUT/'platform/kr260/typed200_encoder.sv').write_text(s)
    manifest={'candidate':'typed200','sealed':False,'target_mhz':200,'hardware_qualified':False,
        'physical_timing_qualified':False,'baseline_sha256':r['rtl_sha256'],
        'baseline_profile':r['profile'],'candidate_sha256':inventory(),
        'description':'Qualified arithmetic; live drain observer + epoch tracker + exclusive typed AXI-Lite control',
        'template_sha256':sha(ROOT/'scripts/v2/kr260/typed200_control.txt'),
        'abi':'0x54590201','contract_sha256':'8133633315487f8f322ecac49e95e7aca3801d00fccb4b4fba36026c5b2752d2'}
    (OUT/'candidate.json').write_text(json.dumps(manifest,indent=2)+'\n')
def verify(seal=False):
    baseline();p=OUT/'candidate.json';m=json.loads(p.read_text())
    if seal:
        if m['sealed']:raise ValueError('Already sealed; preserve')
        m['candidate_sha256']=inventory();m['sealed']=True
        p.write_text(json.dumps(m,indent=2)+'\n')
    assert m['candidate_sha256']==inventory(),'Candidate changed after manifest'
    return m
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--verify',action='store_true');a.add_argument('--seal',action='store_true');x=a.parse_args()
    verify(x.seal) if x.verify or x.seal else create()
    print('PASS typed200 candidate and qualified source preservation')
