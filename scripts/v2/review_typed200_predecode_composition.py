"""Discharge actual instance wiring/control identity for the modular formal proof."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canonical(s):return re.sub(r'\s+','',re.sub(r'//[^\n]*','',s))

def main():
    proof_dir=ROOT/'build/v2/typed200-predecode-formal-v3';p=json.loads((proof_dir/'receipt.json').read_text());assert p['passed']
    for n,h in p['source_sha256'].items():assert sha(ROOT/n)==h,n
    for n,h in p['artifact_sha256'].items():assert sha(proof_dir/n)==h,n
    parent=ROOT/'rtl/v2/candidates/typed200_profile_cache/encoder/add_skip_engine.sv'
    new=ROOT/'rtl/v2/candidates/typed200_predecode/encoder/add_skip_engine.sv'
    old_control=parent.read_text().split('    logic signed [25:0] product',1)[0]
    new_control=new.read_text().split('    logic signed [25:0] product',1)[0]
    port='    input logic signed [25:0] rounding_bias, // Trusted encoder_layer predecode of this same shift.\n'
    assert new_control.count(port)==1;new_control=new_control.replace(port,'')
    assert canonical(old_control)==canonical(new_control),'Control/valid/address/reset model diverged'
    layer=ROOT/'rtl/v2/candidates/typed200_predecode/encoder/encoder_layer.sv';s=layer.read_text()
    start=s.index('    ) add_skip_inst (');instance=s[start:s.index('\n    );',start)]
    bindings={
        'clk':'clk','reset':'reset','start':'add_start',
        'shift':'instruction_reg[8*12 +: 6]','rounding_bias':'add_round_bias_reg',
        'width':'hidden_reg','token_count':'tokens_reg','multiplier':"17'(u32_at(8))",
        'destination_write':'add_write','destination_data':'add_wdata'}
    for name,value in bindings.items():assert canonical(instance).count('.'+name+'('+canonical(value)+')')==1,name
    # The extracted state/FSM proof must match the actual candidate, not a handwritten controller.
    seq=(proof_dir/'sequencer.sv').read_text()
    state=s[s.index('    typedef enum'):s.index('    function automatic logic [7:0] byte_at')]
    assert canonical(state) in canonical(seq)
    regs=s[s.index('    always_ff @(posedge clk or posedge reset)'):s.index('    // memory port:')]
    assert canonical(regs) in canonical(seq)
    begin=s.index('    always_comb begin',s.index('    logic fetch_request_valid, fetch_read_ready;'))
    fsm=s[begin:s.index('    assign busy =',begin)];assert canonical(fsm) in canonical(seq)
    dest=ROOT/'build/v2/typed200-predecode-composition-v1';dest.mkdir(exist_ok=False)
    result={'passed':True,'scope':'Actual instance bindings, exact control/valid/address identity and actual extracted sequencer source close modular proof boundary',
        'bindings':bindings,'proof_sha256':sha(proof_dir/'receipt.json'),
        'control_prefix_identical_after_port_and_comments_removed':True,
        'sequencer_state_capture_and_fsm_copies_match_actual_source':True,
        'limits':['No analog reset/CDC proof','Invalid startup datapath values are not admitted writes','No physical/WCET evidence'],
        'source_sha256':{q.relative_to(ROOT).as_posix():sha(q) for q in (parent,new,layer,Path(__file__))}}
    (dest/'receipt.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS actual modular composition bindings and control/source identity')

if __name__=='__main__':main()
