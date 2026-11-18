"""Actual-source clamp arithmetic and full ADD_SKIP endpoint correspondence."""
from pathlib import Path
import argparse, hashlib, json, re, subprocess

ROOT = Path(__file__).resolve().parents[2]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--name',default='typed200-clamp-formal-v1'); a=ap.parse_args()
    out=ROOT/'build/v2'/a.name; out.mkdir(exist_ok=False); rel=out.relative_to(ROOT).as_posix()
    sources=[]; texts={}
    for mode, candidate in [('old','typed200_profile_cache'),('new','typed200_clamp')]:
        src=ROOT/f'rtl/v2/candidates/{candidate}/encoder/add_skip_engine.sv'
        sources.append(src); text=src.read_text(); texts[mode]=text
        # Package supplies only this default here; verify before replacing the import.
        package=src.parent/'encoder_pkg.sv'; sources.append(package)
        assert re.search(r'localparam int READ_LATENCY\s*=\s*3;', package.read_text())
        text=text.replace('module add_skip_engine\n    import encoder_pkg::*;','module '+mode+'_engine')
        text=text.replace('encoder_pkg::READ_LATENCY','3')
        assert 'encoder_pkg' not in text
        (out/f'{mode}_engine.sv').write_text(text)
        begin=text.index('            skip =') if mode=='old' else text.index('            if (rounded[e][25])')
        end=text.index('\n        end',begin)
        body=text[begin:end].replace('rounded[e]','r').replace('a_held[L+2][16*e +: 16]','a')
        body=body.replace('out_data[16*e +: 16]','value').replace('<=','=')
        (out/f'{mode}_lane.sv').write_text(f'''module {mode}_lane(input signed [25:0] r,input signed [15:0] a,output reg [15:0] value);
reg signed [15:0] skip; reg signed [16:0] sum;
always @* begin
{body}
end
endmodule
''')
    (out/'arithmetic.sv').write_text('''module arithmetic(input signed [25:0] r,input signed [15:0] a);
wire [15:0] x,y;
old_lane old(r,a,x);new_lane new(r,a,y);
always @* assert(x==y);
endmodule
''')
    header=texts['old'].split(') (',1)[1].split('\n);',1)[0].replace('BUFFER_ADDRESS_WIDTH-1:0','13:0')
    inputs=[]; outputs=[]
    for line in header.splitlines():
        m=re.match(r'\s*(input|output) logic\s*(\[[^]]+\])?\s*(\w+)',line)
        if m:
            direction,width,name=m.groups(); (inputs if direction=='input' else outputs).append((width or '',name))
    assert len(inputs)==9 and len(outputs)==8,(inputs,outputs)
    code='module correspondence('+','.join('input wire '+w+' '+n for w,n in inputs)+');\n'
    for mode in ('old','new'):
        code+='\n'.join('wire '+w+' '+mode+'_'+n+';' for w,n in outputs)+'\n'
        code+=mode+'_engine inst_'+mode+'('+','.join('.'+n+'('+n+')' for w,n in inputs)+','
        code+=','.join('.'+n+'('+mode+'_'+n+')' for w,n in outputs)+');\n'
    # Both modules' unreset datapath fills after READ_LATENCY+3; control has reset.
    code+='reg [7:0] observed=0;always @(posedge clk) begin observed<={observed[6:0],1\'b1};\n'
    code+='if(!observed[0]) assume(reset);\nif(observed[7]) begin\n'
    code+='\n'.join('assert(old_'+n+'==new_'+n+');' for w,n in outputs)+'\nend end endmodule\n'
    (out/'correspondence.sv').write_text(code)
    receipt={'passed':False,'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in sources},
        'assumptions':['single sampled clock','two-state semantics',
            'inductive equivalence of every matched internal state point; corresponding initial state'],
        'parameters':{'READ_LATENCY':3,'MAX_TOKENS':128,'BUFFER_ADDRESS_WIDTH':14},
        'arithmetic_domain':'all 2^26 rounded values and 2^16 residuals; no reachability restriction',
        'input_constraints':'No protocol, shape, multiplier, shift or data restrictions after reset'}
    for mode,script in [('arithmetic',f'''read_verilog -formal -sv {rel}/old_lane.sv {rel}/new_lane.sv {rel}/arithmetic.sv
prep -top arithmetic -flatten
opt -full
chformal -lower
sat -verify -prove-asserts -timeout 120
'''),('engine',f'''read_verilog -formal -sv {rel}/old_engine.sv {rel}/new_engine.sv
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
''')]:
        (out/f'{mode}.ys').write_text(script)
        with (out/f'{mode}-console.log').open('w') as log:
            r=subprocess.run(['uv','tool','run','--from','yowasp-yosys==0.70.0.0.post1259','yowasp-yosys','-Q','-T',
                '-l',f'{rel}/{mode}.log','-s',f'{rel}/{mode}.ys'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        marker='SUCCESS!' if mode=='arithmetic' else 'Equivalence successfully proven!'
        passed=r.returncode==0 and marker in (out/f'{mode}.log').read_text()
        receipt[mode]={'passed':passed,'exit_code':r.returncode}
        (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        if not passed: raise SystemExit(mode+' NOT PROVED; attempt preserved')
    receipt['passed']=True
    receipt['artifact_sha256']={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='receipt.json'}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS entire arithmetic domain and full ADD_SKIP engine cycle correspondence')


if __name__=='__main__': main()
