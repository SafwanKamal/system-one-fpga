"""Inductively compare live FIFO state/data with the parent under sampled reset."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def body(p,prefix,old=False):
    s=p.read_text();s=s[s.index('    localparam integer ADDRESS_WIDTH'):s.rindex('endmodule')]
    for n in ['ADDRESS_WIDTH','memory','write_pointer_reg','write_pointer_next','read_pointer_reg',
              'read_pointer_next','do_write','do_read','full','empty','count','read_data','write_data',
              'write_enable','read_enable']:
        s=re.sub(r'\b'+n+r'\b',prefix+n,s)
    if old:s=re.sub(r'\breset\b','combined_reset',s)
    return s
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='typed200-flush-live-formal-v3')
    ap.add_argument('--depth',type=int,default=8);ap.add_argument('--width',type=int,default=128);a=ap.parse_args()
    assert a.depth>=2 and a.depth&(a.depth-1)==0 and a.width>0
    out=ROOT/'build/v2'/a.name;out.mkdir(exist_ok=False);rel=out.relative_to(ROOT).as_posix()
    old=ROOT/'rtl/v2/candidates/typed200/common/sync_fifo.sv'
    new=ROOT/'rtl/v2/candidates/typed200_flush/common/stream_fifo_sync_clear.sv'
    code='''module fifo_flush_formal(input clk,reset,clear,w,r,input [WIDTH-1:0] d);
    parameter WIDTH=128,DEPTH=8;
    localparam AW=$clog2(DEPTH);
    wire combined_reset=reset || clear;
'''
    for prefix in ['o_','n_']:
        code+=f'''wire {prefix}write_enable=w, {prefix}read_enable=r;
        wire [WIDTH-1:0] {prefix}write_data=d,{prefix}read_data;
        wire [AW:0] {prefix}count; wire {prefix}full,{prefix}empty;
'''
    code+=body(old,'o_',True)+body(new,'n_')
    code+='''
    logic past_valid=0;
    always @(posedge clk) begin
        past_valid<=1;
        if(!past_valid) assume(reset);
        if(past_valid && !combined_reset) begin
            assert(n_count<=DEPTH);
            assert(n_count==o_count && n_empty==o_empty && n_full==o_full);
            assert(n_read_pointer_reg==o_read_pointer_reg);
            assert(n_write_pointer_reg==o_write_pointer_reg);
            for(int i=0;i<DEPTH;i++)begin
                if((((AW+1)'(i)-{1'b0,n_read_pointer_reg[AW-1:0]}) & (AW+1)'(DEPTH-1))<n_count)
                    assert(n_memory[i]==o_memory[i]);
            end
            if(!n_empty)assert(n_read_data==o_read_data);
        end
    end
    endmodule
'''
    code=code.replace('parameter WIDTH=128,DEPTH=8;',f'parameter WIDTH={a.width},DEPTH={a.depth};')
    (out/'miter.sv').write_text(code)
    (out/'prove.ys').write_text(f'''read_verilog -formal -sv {rel}/miter.sv
prep -top fifo_flush_formal -flatten
memory_map
async2sync
chformal -lower
formalff -clk2ff
dffunmap
opt_clean
sat -verify -prove-asserts -tempinduct -seq 2 -maxsteps 12 -set-assumes -set clk 1 -timeout 60 -dump_vcd {rel}/counterexample.vcd
''')
    with (out/'console.log').open('w') as f:
        r=subprocess.run(['uv','tool','run','--from','yowasp-yosys==0.70.0.0.post1259','yowasp-yosys',
            '-Q','-T','-l',f'{rel}/prove.log','-s',f'{rel}/prove.ys'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
    passed=r.returncode==0 and 'Induction step proven: SUCCESS!' in (out/'prove.log').read_text()
    (out/'receipt.json').write_text(json.dumps({'passed':passed,'exit_code':r.returncode,
        'tool_package':'yowasp-yosys==0.70.0.0.post1259','source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in [old,new]},
        'assumptions':['first sampled edge reset','single sampled clock'],
        'depth':a.depth,'width':a.width,
        'scope':'Live pointer/count/flags/data equivalence and occupancy safety against parent; arbitrary sampled clear/input/backpressure',
        'limits':['no equivalence of inactive data/raw asynchronous reset signals','not whole encoder or physical timing proof'],
        'artifact_sha256':{p.name:sha(p) for p in out.iterdir() if p.is_file()}},indent=2)+'\n')
    print('PASS inductive live FIFO equivalence' if passed else 'NOT PROVED; preserve attempt')
    raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()
