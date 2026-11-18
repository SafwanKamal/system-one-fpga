"""Scoped clocked FIFO equivalence against the immutable parent; no timing claim."""
from pathlib import Path
import argparse,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='typed200-flush-formal-v1');a=ap.parse_args()
    out=ROOT/'build/v2'/a.name;out.mkdir(exist_ok=False);rel=out.relative_to(ROOT).as_posix()
    old=ROOT/'rtl/v2/candidates/typed200/common/sync_fifo.sv'
    new=ROOT/'rtl/v2/candidates/typed200_flush/common/stream_fifo_sync_clear.sv'
    (out/'old.sv').write_bytes(old.read_bytes());(out/'new.sv').write_bytes(new.read_bytes())
    wrappers=''
    for top,mod in [('gold','sync_fifo'),('gate','stream_fifo_sync_clear')]:
        conn='.reset(reset || clear)' if top=='gold' else '.reset(reset),.clear(clear)'
        wrappers+=f'''module {top}(input clk,reset,clear,w,r,input [7:0] d,
            output [7:0] q,output [2:0] n,output full,empty);
            wire [7:0] data; wire [2:0] count; wire f,e;
            {mod} #(.WIDTH(8),.DEPTH(4)) fifo(.clk(clk),{conn},
                .write_enable(w && !reset && !clear),.read_enable(r && !reset && !clear),
                .write_data(d),.read_data(data),.count(count),.full(f),.empty(e));
            assign q=(reset || clear || e) ? 8'd0 : data;
            assign n=(reset || clear) ? 3'd0 : count;
            assign full=!(reset || clear) && f;
            assign empty=(reset || clear) || e;
        endmodule
'''
    (out/'wrappers.sv').write_text(wrappers)
    (out/'prove.ys').write_text(f'''read_verilog -formal -sv {rel}/old.sv {rel}/new.sv {rel}/wrappers.sv
hierarchy -check
proc
memory
flatten gold gate
async2sync
opt_clean
equiv_make gold gate equiv
hierarchy -top equiv
equiv_simple
equiv_induct -seq 6
equiv_status -assert
''')
    with (out/'console.log').open('w') as f:
        r=subprocess.run(['uv','tool','run','--from','yowasp-yosys==0.70.0.0.post1259','yowasp-yosys',
            '-Q','-T','-l',f'{rel}/prove.log','-s',f'{rel}/prove.ys'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
    passed=r.returncode==0 and 'Equivalence successfully proven!' in (out/'prove.log').read_text()
    (out/'receipt.json').write_text(json.dumps({'passed':passed,'exit_code':r.returncode,
        'tool_package':'yowasp-yosys==0.70.0.0.post1259','source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in [old,new]},
        'assumptions':['single sampled clock','reset/clear observed at clock edges',
            'writes/reads disabled during reset/clear','empty data and reset/clear outputs masked'],
        'scope':'Depth4 WIDTH8 clocked FIFO live data/count/full/empty equivalence; not asynchronous behavior or whole encoder',
        'artifact_sha256':{p.name:sha(p) for p in out.iterdir() if p.is_file()}},indent=2)+'\n')
    print('PASS scoped FIFO equivalence' if passed else 'NOT PROVED; preserve attempt')
    raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()
