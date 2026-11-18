"""Actual sequencer/cache proof plus arithmetic and conditional engine refinement."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='typed200-predecode-formal-v1');a=ap.parse_args()
    out=ROOT/'build/v2'/a.name;out.mkdir(exist_ok=False);rel=out.relative_to(ROOT).as_posix()
    layer=ROOT/'rtl/v2/candidates/typed200_predecode/encoder/encoder_layer.sv';ls=layer.read_text()
    func=ls[ls.index('    function automatic logic signed [25:0] add_round_bias'):ls.index('    logic signed [25:0] add_round_bias_reg;')]
    sources=[layer];old_text=None
    for mode,candidate in [('old','typed200_profile_cache'),('new','typed200_predecode')]:
        src=ROOT/f'rtl/v2/candidates/{candidate}/encoder/add_skip_engine.sv';s=src.read_text();sources.append(src)
        pkg=src.parent/'encoder_pkg.sv';sources.append(pkg);assert 'localparam int READ_LATENCY = 3;' in pkg.read_text()
        normalized=s.replace('module add_skip_engine\n    import encoder_pkg::*;','module '+mode+'_engine').replace('encoder_pkg::READ_LATENCY','3')
        if mode=='old':old_text=normalized
        else:
            port='    input logic signed [25:0] rounding_bias, // Trusted encoder_layer predecode of this same shift.\n'
            assert normalized.count(port)==1;normalized=normalized.replace(port,'')
            normalized=normalized.replace('    typedef enum',func+'    wire signed [25:0] rounding_bias=add_round_bias(shift);\n    typedef enum',1)
        anchor='    output logic [15:0] destination_enable\n';assert normalized.count(anchor)==1
        normalized=normalized.replace(anchor,anchor.rstrip()+',\n    output wire [127:0] proof_stage\n')
        stage="rounded[k] > 26'sd32767 ? 16'sd32767 : rounded[k] < -26'sd32767 ? -16'sd32767 : 16'(rounded[k])" if mode=='old' else 'skip_clamped[k]'
        normalized=normalized.replace('endmodule',f'for(genvar k=0;k<8;k++) assign proof_stage[16*k+:16]={stage};\nendmodule')
        (out/f'{mode}_engine.sv').write_text(normalized)
        begin=s.index("            if (shift != '0)") if mode=='old' else s.index('            rounded_value =')
        end=s.index('\n        end',begin);body=s[begin:end]
        body=body.replace('rounded[e]','rounded_value').replace('product[e]','p').replace('skip_clamped[e]','skip_clamped')
        body=body.replace('a_held[L+2][16*e +: 16]','a').replace('out_data[16*e +: 16]','value').replace('<=','=')
        stage='skip' if mode=='old' else 'skip_clamped'
        (out/f'{mode}_lane.sv').write_text(f'''module {mode}_lane(input signed [25:0] p,input [5:0] shift,input signed [15:0] a,output reg [15:0] value,output wire [15:0] stage_value);
{func}
wire signed [25:0] rounding_bias=add_round_bias(shift);
reg signed [25:0] rounded_value;reg signed [15:0] skip,skip_clamped;reg signed [16:0] sum;
always @* begin
{body}
end
assign stage_value={stage};
endmodule
''')
    (out/'arithmetic.sv').write_text('''module arithmetic(input signed [25:0] p,input [5:0] shift,input signed [15:0] a);
wire [15:0] x,y,sx,sy;old_lane old(p,shift,a,x,sx);new_lane new(p,shift,a,y,sy);
always @* begin assert(x==y);assert(sx==sy);end
endmodule
''')
    # Copy the ACTUAL sequencer enum/state, instruction/predecode capture and FSM.
    defs=ls[ls.index('    typedef enum'):ls.index('    // engines')]
    for fn in ('byte_at','u16_at','u32_at'):
        pattern=r'(function automatic logic \[[^]]+\] '+fn+r'\(input int i\);\s*)return ([^;]+);'
        defs,n=re.subn(pattern,lambda m:m[1]+fn+' = '+m[2]+';',defs);assert n==1
    regs=ls[ls.index('    always_ff @(posedge clk or posedge reset)'):ls.index('    // memory port:')]
    start=ls.index('    always_comb begin',ls.index('    logic fetch_request_valid, fetch_read_ready;'))
    fsm=ls[start:ls.index('    assign busy =',start)]
    pkg=(ROOT/'rtl/v2/candidates/typed200_predecode/encoder/encoder_pkg.sv').read_text()
    opcodes='\n'.join(line for line in pkg.splitlines() if 'localparam logic [7:0] OP_' in line)
    # Actual ADD_SKIP valid/control/address pipeline, with datapath removed only in this control lemma.
    control=old_text[:old_text.index('    logic signed [25:0] product')]
    control=control.replace('module old_engine','module add_control',1)
    control=control.replace('    output logic [15:0] destination_enable\n','    output logic [15:0] destination_enable,\n    output wire [5:0] proof_valid\n')
    control+='''    assign destination_write=s_valid[D];
    assign proof_valid=s_valid;
    assign destination_address=s_address[D];assign destination_data=0;assign destination_enable=16'hffff;
endmodule
'''
    (out/'add_control.sv').write_text(control)
    code='''module sequencer(input clk,reset,start,input [39:0] program_address,input [15:0] first_instruction,instruction_count,hidden,
input [7:0] token_count,input read_request_ready,read_valid,read_last,input [127:0] read_data,input engine_done);
localparam ADDRESS_WIDTH=40,TILE_OUT=32,FPGA_HEADS=0;
'''+opcodes+'\n'+defs+'\n'+regs+'''
logic linear_start,attention_start,add_start,norm_start,embed_start,pool_start;
logic fetch_request_valid,fetch_read_ready;
'''+fsm+'''
wire control_write,control_busy;
wire [5:0] control_valid;
add_control add(.clk(clk),.reset(reset),.start(add_start),.busy(control_busy),.done(),
 .multiplier(17'(u32_at(8))),.shift(instruction_reg[8*12+:6]),.width(hidden_reg),.token_count(tokens_reg),
 .a_address(),.a_data(read_data),.x_address(),.x_data(read_data),.destination_write(control_write),
 .destination_address(),.destination_data(),.destination_enable(),.proof_valid(control_valid));
reg sampled=0,ever_word0=0,frame_word0=0;
always @(posedge clk) begin
 sampled<=1;
 if(!sampled) assume(reset);
 if(reset) ever_word0<=0;
 else if(state_reg==FETCH_RECEIVE && read_valid && beat_reg==0) ever_word0<=1;
 if(reset || state_reg==FETCH_REQUEST) frame_word0<=0;
 else if(state_reg==FETCH_RECEIVE && read_valid && beat_reg==0) frame_word0<=1;
 if(sampled) begin
   assert(!frame_word0 || ever_word0);
   if(!reset && state_reg==FETCH_RECEIVE && !frame_word0) assert(beat_reg==0);
   if(ever_word0) assert(add_round_bias_reg==add_round_bias(instruction_reg[8*12+:6]));
   if(!reset && (state_reg==DISPATCH || state_reg==EXECUTE || state_reg==NEXT)) begin assert(frame_word0);assert(ever_word0);end
   if(!reset && control_busy) assert(ever_word0);
   for(integer j=0;j<6;j=j+1) if(!reset && control_valid[j]) begin
      assert(ever_word0);
      if(j>=1) assert($past(ever_word0));
      if(j>=2) assert($past(ever_word0,2));
   end
   if($past(state_reg==DISPATCH || state_reg==EXECUTE))
      assert(instruction_reg==$past(instruction_reg));
   if(!reset && control_write) begin
      assert(ever_word0);assert($past(ever_word0));assert($past(ever_word0,2));
   end
 end
end
endmodule
'''
    (out/'sequencer.sv').write_text(code)
    receipt={'passed':False,'assumptions':['first sampled reset for sequencer proof','one sampled clock','two-state semantics',
        'engine refinement has corresponding initial datapath/clamp state and bias=f(current shift); the sequencer discharges this relation for every observable write and its arithmetic history'],
        'sequencer_scope':'Actual extracted FSM/state/instruction and predecode capture. All engine_done values, fetch data/valid/last, reset and request inputs arbitrary; no other-engine stability assumption.',
        'composition':'Cache invariant holds in ALL sequencer states after word0, not just EXECUTE. Fresh word0 before DISPATCH and two-cycle bias-history availability for actual ADD_SKIP valid writes proved. Invalid startup datapath values are not external writes.',
        'arithmetic_domain':'all26bit products/all64 shifts/all16bit residuals; exact26bit overflow',
        'parameters':{'READ_LATENCY':3,'BUFFER_ADDRESS_WIDTH':14,'TILE_OUT':32,'FPGA_HEADS':0,'ADDRESS_WIDTH':40},
        'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in sources}}
    scripts={
      'sequencer':f'''read_verilog -formal -sv {rel}/add_control.sv {rel}/sequencer.sv
prep -top sequencer -flatten
memory
opt -full
async2sync
chformal -lower
formalff -clk2ff
dffunmap
opt -full
sat -verify -prove-asserts -tempinduct -seq 2 -maxsteps 16 -set-assumes -set clk 1 -timeout 120 -dump_vcd {rel}/sequencer-counterexample.vcd
''',
      'arithmetic':f'''read_verilog -formal -sv {rel}/old_lane.sv {rel}/new_lane.sv {rel}/arithmetic.sv
prep -top arithmetic -flatten
opt -full
chformal -lower
sat -verify -prove-asserts -timeout 120
''',
      'engine':f'''read_verilog -formal -sv {rel}/old_engine.sv {rel}/new_engine.sv
proc
memory
opt -full
async2sync
equiv_make old_engine new_engine engine_equivalence
hierarchy -top engine_equivalence
opt -full
equiv_simple -seq 3
equiv_induct -seq 3
equiv_status -assert
'''}
    for mode,script in scripts.items():
        (out/f'{mode}.ys').write_text(script)
        with (out/f'{mode}-console.log').open('w') as log:
            r=subprocess.run(['uv','tool','run','--from','yowasp-yosys==0.70.0.0.post1259','yowasp-yosys','-Q','-T',
                '-l',f'{rel}/{mode}.log','-s',f'{rel}/{mode}.ys'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        txt=(out/f'{mode}.log').read_text();marker={'sequencer':'Induction step proven: SUCCESS!','arithmetic':'SUCCESS!','engine':'Equivalence successfully proven!'}[mode]
        passed=r.returncode==0 and marker in txt;receipt[mode]={'passed':passed,'exit_code':r.returncode}
        if mode=='engine' and passed:receipt[mode]['equivalence_points']=int(re.search(r'Of those cells (\d+) are proven and 0 are unproven',txt)[1])
        (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        if not passed:raise SystemExit(mode+' NOT PROVED; preserve attempt')
    receipt['passed']=True;receipt['artifact_sha256']={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='receipt.json'}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS actual sequencer/cache/valid-history induction, exhaustive arithmetic and conditional engine refinement')

if __name__=='__main__':main()
