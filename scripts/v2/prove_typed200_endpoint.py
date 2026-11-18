"""Reprove protocol and shape admission on the isolated ABI successor."""
from pathlib import Path
import argparse,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--name',default='typed200-endpoint-formal-v1');a=p.parse_args()
    out=ROOT/'build/v2'/a.name;out.mkdir(exist_ok=False);rel=out.relative_to(ROOT).as_posix()
    base=ROOT/'rtl/v2/candidates/typed200/contracts'
    source=base/'typed_intent_axil.sv'
    props=[ROOT/'formal/typed_publication/axil_properties.vh',ROOT/'formal/typed_publication/typed200_endpoint_properties.vh']
    (out/'instrumented.sv').write_text(source.read_text().replace('endmodule','\n'.join(p.read_text() for p in props)+'\nendmodule'))
    deps=[base/'typed_publication_gate.sv',base/'typed_intent_guard.sv']
    depstring=' '.join(p.relative_to(ROOT).as_posix() for p in deps)
    (out/'prove.ys').write_text(f'''read_verilog -formal -sv {depstring} {rel}/instrumented.sv
prep -top typed_intent_axil -flatten
memory_map
async2sync
chformal -lower
formalff -clk2ff
dffunmap
opt_clean
sat -verify -prove-asserts -tempinduct -seq 2 -maxsteps 6 -set-assumes -set clk 1 -timeout 60 -dump_vcd {rel}/induction.vcd
''')
    with (out/'console.log').open('w') as f:
        r=subprocess.run(['uv','tool','run','--from','yowasp-yosys==0.70.0.0.post1259',
            'yowasp-yosys','-Q','-T','-l',f'{rel}/prove.log','-s',f'{rel}/prove.ys'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
    passed=r.returncode==0 and 'Induction step proven: SUCCESS!' in (out/'prove.log').read_text()
    (out/'receipt.json').write_text(json.dumps({'passed':passed,'exit_code':r.returncode,
        'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in [source,*deps,*props]},
        'instrumented_sha256':sha(out/'instrumented.sv'),'tool_package':'yowasp-yosys==0.70.0.0.post1259',
        'scope':'AW/W capture and held B/R; validated shape/environment and immutable admitted shape',
        'assumptions':['first sampled edge reset','single synchronous clock'],
        'limits':['not whole-encoder formal proof','not physical timing/CDC/WCET proof']},indent=2)+'\n')
    print('PASS typed200 endpoint induction' if passed else 'NOT PROVED; retain attempt')
    raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()
