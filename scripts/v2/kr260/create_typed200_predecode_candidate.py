"""Instruction-word-local bias predecode; no added request or arithmetic stage."""
import argparse,json,shutil
from create_typed200_stage_clamp_candidate import ROOT,OUT as PARENT,verify as parent_verify,sha
OUT=ROOT/'rtl/v2/candidates/typed200_predecode'
CHANGED={'encoder/add_skip_engine.sv','encoder/encoder_layer.sv'}

def verify():
    parent=parent_verify();m=json.loads((OUT/'candidate.json').read_text())
    assert sha(PARENT/'candidate.json')==m['parent_manifest_sha256']
    actual={p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.suffix in ('.sv','.v')}
    assert actual==m['candidate_sha256']
    assert {n for n in actual if actual[n]!=parent['candidate_sha256'].get(n)}==CHANGED
    return m

def create():
    parent_verify();assert not OUT.exists();shutil.copytree(PARENT,OUT)
    p=OUT/'encoder/add_skip_engine.sv';s=p.read_text()
    anchor='    input logic [5:0] shift,\n';assert s.count(anchor)==1
    s=s.replace(anchor,anchor+'    input logic signed [25:0] rounding_bias, // Trusted encoder_layer predecode of this same shift.\n')
    old='''            if (shift != '0) begin
                rounded_value = (product[e] + (26'sd1 <<< (shift - 6'd1))) >>> shift;
            end else begin
                rounded_value = product[e];
            end'''
    new='''            // Bias is zero for shift0; exact signed26 overflow before shifting.
            // Encoder-layer capture proves rounding_bias == bias(shift) every edge.
            rounded_value = (product[e] + rounding_bias) >>> shift;'''
    assert s.count(old)==1;s=s.replace(old,new);p.write_text(s)
    p=OUT/'encoder/encoder_layer.sv';s=p.read_text()
    anchor='    logic [511:0] instruction_reg;';assert s.count(anchor)==1
    s=s.replace(anchor,anchor+'''
    // Mirror the shift's word0 capture. No reset here, exactly like instruction_reg;
    // the sequencer must capture word0 before dispatch. No live permission cached.
    function automatic logic signed [25:0] add_round_bias(input logic [5:0] s);
        add_round_bias = (s == 0) ? 26'sd0 : (26'sd1 <<< (s - 6'd1));
    endfunction
    logic signed [25:0] add_round_bias_reg;
    always_ff @(posedge clk) begin
        if (state_reg == FETCH_RECEIVE && read_valid && beat_reg == 0)
            add_round_bias_reg <= add_round_bias(read_data[8*12 +: 6]);
    end
''')
    anchor='        .shift(instruction_reg[8*12 +: 6]),';assert s.count(anchor)==1
    s=s.replace(anchor,anchor+'\n        .rounding_bias(add_round_bias_reg),');p.write_text(s)
    (OUT/'README.md').write_text('''# Separate typed200_predecode candidate

Parent: frozen typed200_stage_clamp. Only encoder_layer and ADD_SKIP change.
Encoder_layer predecodes signed26 rounding bias on exactly the instruction word0
capture edge that stores shift bits101:96. The cached bias is a function of the
current stored shift, not a cached live permission. Like the instruction bank,
it has no reset; word0 must be captured before dispatch. ADD_SKIP consumes it
before the unchanged arithmetic shift and first clamp at the existing L+2 edge.
No request or arithmetic cycle added; exact26bit overflow and zero-shift behavior.
Requires actual-source sequencer/cache invariant and dispatch freshness proof,
whole-engine equivalence under the discharged bias relation, independent parent
arithmetic regression and all-stage matched timing against profile_cache.
No arbitrary untrusted-bias standalone equivalence or hardware/WCET claim.
All prior candidates, qualified package/recovery and numerical baselines frozen.
''')
    (OUT/'candidate.json').write_text(json.dumps({'candidate':'typed200_predecode','sealed':False,
        'parent_manifest_sha256':sha(PARENT/'candidate.json'),
        'candidate_sha256':{q.relative_to(OUT).as_posix():sha(q) for q in OUT.rglob('*') if q.suffix in ('.sv','.v')},
        'intended_external_cycle_delta':0,'numerical_contract_changed':False,'deadline_epoch_logic_changed':False,
        'hardware_qualified':False,'predecode_bits':26,'trusted_bias_relation_required':True},indent=2)+'\n')
    verify()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');a=ap.parse_args()
    verify() if a.verify else create();print('PASS separate instruction-local predecode inventory')
