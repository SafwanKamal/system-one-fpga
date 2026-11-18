"""Prove actual old/new shape expressions for all 64 raw bits, without assumptions."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='typed200-row-range-arithmetic-v2');a=ap.parse_args()
    out=ROOT/'build/v2'/a.name;out.mkdir(exist_ok=False);rel=out.relative_to(ROOT).as_posix();sources=[]
    code='module range_formal(input wire [31:0] raw_shape,raw_count);\n'
    for prefix,candidate in [('old','typed200_predecode'),('new','typed200_row_range')]:
        p=ROOT/'rtl/v2/candidates'/candidate/'contracts/typed_intent_axil.sv';sources.append(p);s=p.read_text()
        a=s.index('    wire shape_ok=') if prefix=='old' else s.index('    wire [8:0] selected_row_end=')
        b=s.index('    assign admission_tokens=',a)
        expression=s[a:b].replace('bank[5]','raw_shape').replace('bank[28]','raw_count')
        expression=re.sub(r'\bshape_ok\b',prefix+'_shape_ok',expression)
        expression=re.sub(r'\bselected_row_end\b',prefix+'_selected_row_end',expression)
        code+=expression
    code+='always @* assert(old_shape_ok==new_shape_ok);\nendmodule\n'
    (out/'miter.sv').write_text(code)
    (out/'prove.ys').write_text(f'read_verilog -formal -sv {rel}/miter.sv\nprep -top range_formal -flatten\nchformal -lower\nsat -verify -prove-asserts -show-inputs -show-outputs -dump_vcd {rel}/counterexample.vcd\n')
    with (out/'console.log').open('w') as log:
        r=subprocess.run(['uv','tool','run','--from','yowasp-yosys==0.70.0.0.post1259','yowasp-yosys','-Q','-T','-l',f'{rel}/prove.log','-s',f'{rel}/prove.ys'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    passed=r.returncode==0 and 'SUCCESS!' in (out/'prove.log').read_text()
    (out/'receipt.json').write_text(json.dumps({'passed':passed,'exit_code':r.returncode,
        'scope':'All 2^64 raw shape/count encodings: tokens16,first16,count16,reserved16; valid and invalid, high bits, zero and overflow; exact actual-source expressions',
        'assumptions':[],'semantics':'Two-state unsigned SystemVerilog finite-width arithmetic',
        'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in sources},
        'artifact_sha256':{p.name:sha(p) for p in out.iterdir() if p.is_file()}},indent=2)+'\n')
    print('PASS all raw row-range encodings' if passed else 'NOT PROVED; preserve attempt')
    raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()
