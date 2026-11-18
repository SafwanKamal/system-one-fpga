"""Prove actual-size LUT capture preserves every initialized row after drain."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

ROOT=Path(__file__).resolve().parents[2]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--name',default='typed200-lut-capture-formal-v2'); a=ap.parse_args()
    out=ROOT/'build/v2'/a.name; out.mkdir(exist_ok=False); rel=out.relative_to(ROOT).as_posix()
    old=ROOT/'rtl/v2/candidates/typed200_flush/encoder/linear_engine.sv'
    new=ROOT/'rtl/v2/candidates/typed200_lut_capture/encoder/linear_engine.sv'
    s=old.read_text(); start=s.index('    always_ff @(posedge clk) begin\n        if (load_state == L_LUT && take)')
    end=s.index('        if (load_state == L_PARAMETERS && take)',start)
    original=s[start:end]+'    end\n'
    original=re.sub(r'\blut\b','original_lut',original)
    original=original.replace('original_lut[16 * load_beat[3:0] + b] <=',
        'if (watched == 8\'(16 * load_beat[3:0] + b)) original_byte <=')
    s=new.read_text(); start=s.index('    logic lut_capture_valid;'); end=s.index('    always_ff @(posedge clk) begin\n        if (load_state == L_PARAMETERS && take)',start)
    capture=s[start:end]
    capture=capture.replace('lut[16 * lut_capture_row + b] <=',
        'if (watched == 8\'(16 * lut_capture_row + b)) captured_byte <=')
    code='''module lut_capture_formal(input clk,reset,accept,input [3:0] row,input [127:0] data);
    localparam L_LUT=1;
    wire load_state=1;
    wire take=accept;
    wire [15:0] load_beat={12'd0,row};
    wire [127:0] read_data=data;
    // Arbitrary stable address universally covers every table byte. Writes have
    // no cross-byte dependencies; scalarization avoids the WASM array expansion.
    (* anyconst *) reg [7:0] watched;
    logic signed [7:0] captured_byte,original_byte;
'''+original+capture+'''
    reg initialized=0;
    reg past_valid=0;
    always @(posedge clk) begin
        past_valid<=1;
        if(!past_valid) assume(reset);
        if(reset) initialized<=0;
        else if(accept && row==watched[7:4]) initialized<=1;
        if(past_valid && !reset) begin
            if(initialized && !(lut_capture_valid && lut_capture_row==watched[7:4]))
                assert(captured_byte == original_byte);
        end
    end
endmodule
'''
    (out/'miter.sv').write_text(code)
    (out/'prove.ys').write_text(f'''read_verilog -formal -sv {rel}/miter.sv
prep -top lut_capture_formal -flatten
memory_map
async2sync
chformal -lower
formalff -clk2ff
dffunmap
opt_clean
sat -verify -prove-asserts -tempinduct -seq 2 -maxsteps 12 -set-assumes -set clk 1 -timeout 60 -dump_vcd {rel}/counterexample.vcd
''')
    with (out/'console.log').open('w') as log:
        r=subprocess.run(['uv','tool','run','--from','yowasp-yosys==0.70.0.0.post1259',
            'yowasp-yosys','-Q','-T','-l',f'{rel}/prove.log','-s',f'{rel}/prove.ys'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    passed=r.returncode==0 and 'Induction step proven: SUCCESS!' in (out/'prove.log').read_text()
    (out/'receipt.json').write_text(json.dumps({'passed':passed,'exit_code':r.returncode,
        'rows':16,'bytes_per_row':16,'assumptions':['first sampled edge reset','single sampled clock'],
        'scope':'Mechanically extracted actual table-write/capture logic, scalarized at arbitrary stable byte address across all 256 bytes; arbitrary accepted rows/data/stalls/reset; initialized byte matches except current one-edge pending row write',
        'limits':['reset invalidates initialization evidence','not whole-engine scheduling/read safety proof','not physical or WCET proof'],
        'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in [old,new]},
        'artifact_sha256':{p.name:sha(p) for p in out.iterdir() if p.is_file()}},indent=2)+'\n')
    print('PASS actual-size LUT capture induction' if passed else 'NOT PROVED; preserve attempt')
    raise SystemExit(0 if passed else 1)


if __name__=='__main__':
    main()
