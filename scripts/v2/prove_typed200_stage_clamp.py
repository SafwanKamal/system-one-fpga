"""Prove the changed register relation and full-engine public cycle equivalence."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='typed200-stage-clamp-formal-v1');a=ap.parse_args()
    out=ROOT/'build/v2'/a.name;out.mkdir(exist_ok=False);rel=out.relative_to(ROOT).as_posix();sources=[]
    for mode,candidate in [('old','typed200_profile_cache'),('new','typed200_stage_clamp')]:
        src=ROOT/f'rtl/v2/candidates/{candidate}/encoder/add_skip_engine.sv';s=src.read_text();sources.append(src)
        pkg=src.parent/'encoder_pkg.sv';sources.append(pkg)
        assert re.search(r'localparam int READ_LATENCY\s*=\s*3;',pkg.read_text())
        normalized=s.replace('module add_skip_engine\n    import encoder_pkg::*;','module '+mode+'_engine').replace('encoder_pkg::READ_LATENCY','3')
        assert 'encoder_pkg' not in normalized
        # Proof-only observation: compare the changed state RELATION, never raw rounded bits.
        anchor='    output logic [15:0] destination_enable\n'
        assert normalized.count(anchor)==1
        normalized=normalized.replace(anchor,'    output logic [15:0] destination_enable,\n    output wire [127:0] proof_stage\n')
        stage="rounded[k] > 26'sd32767 ? 16'sd32767 : rounded[k] < -26'sd32767 ? -16'sd32767 : 16'(rounded[k])" if mode=='old' else 'skip_clamped[k]'
        normalized=normalized.replace('endmodule',f'for(genvar k=0;k<8;k++) assign proof_stage[16*k+:16]={stage};\nendmodule')
        (out/f'{mode}_engine.sv').write_text(normalized)
        begin=s.index("            if (shift != '0)");end=s.index('\n        end',begin)
        body=s[begin:end].replace('rounded[e]','rounded_value').replace('product[e]','p')
        body=body.replace('skip_clamped[e]','skip_clamped').replace('a_held[L+2][16*e +: 16]','a')
        body=body.replace('out_data[16*e +: 16]','value').replace('<=','=')
        stage='skip' if mode=='old' else 'skip_clamped'
        (out/f'{mode}_lane.sv').write_text(f'''module {mode}_lane(input signed [25:0] p,input [5:0] shift,input signed [15:0] a,output reg [15:0] value,output wire [15:0] stage_value);
reg signed [25:0] rounded_value;reg signed [15:0] skip,skip_clamped;reg signed [16:0] sum;
always @* begin
{body}
end
assign stage_value={stage};
endmodule
''')
    (out/'arithmetic.sv').write_text('''module arithmetic(input signed [25:0] p,input [5:0] shift,input signed [15:0] a);
wire [15:0] x,y,sx,sy;
old_lane old(p,shift,a,x,sx);new_lane new(p,shift,a,y,sy);
always @* begin assert(x==y);assert(sx==sy);end
endmodule
''')
    receipt={'passed':False,'parameters':{'READ_LATENCY':3,'MAX_TOKENS':128,'BUFFER_ADDRESS_WIDTH':14},
        'stage_relation':'new.skip_clamped[e] == signed_clamp_32767(old.rounded[e]) at the same L+2 edge',
        'assumptions':['one sampled clock','two-state semantics','corresponding unchanged initial state; changed stage initially related by the stated clamp relation'],
        'arithmetic_domain':'all 2^26 product values, all64 shift encodings, all2^16 residuals; exact26bit rounding overflow',
        'input_constraints':'No protocol/shape/shift/data constraints',
        'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in sources}}
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
        txt=(out/f'{mode}.log').read_text();marker='SUCCESS!' if mode=='arithmetic' else 'Equivalence successfully proven!'
        passed=r.returncode==0 and marker in txt;receipt[mode]={'passed':passed,'exit_code':r.returncode}
        if mode=='engine' and passed:
            receipt['engine']['equivalence_points']=int(re.search(r'Of those cells (\d+) are proven and 0 are unproven',txt)[1])
        (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        if not passed:raise SystemExit(mode+' NOT PROVED; preserve attempt')
    receipt['passed']=True;receipt['artifact_sha256']={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='receipt.json'}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS actual-source rounding/clamp arithmetic, stage relation and full-engine cycle equivalence')

if __name__=='__main__':main()
