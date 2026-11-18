"""Prove invariants on a formal-only copy; preserve source and every attempt."""
from pathlib import Path
import hashlib
import json
import subprocess
import argparse

ROOT=Path(__file__).resolve().parents[2]
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--name',default='typed-formal-invariants')
    p.add_argument('--target',choices=['gate','guard','axil'],default='gate')
    args=p.parse_args()
    out=ROOT/'build/v2'/args.name
    if out.exists(): raise FileExistsError('Preserve proof attempt')
    out.mkdir()
    rtl=ROOT/('rtl/contracts/typed_publication_gate.sv' if args.target=='gate'
              else f'rtl/contracts/typed_intent_v1/typed_intent_{args.target}.sv')
    props=ROOT/('formal/typed_publication/invariants.vh' if args.target=='gate'
                else f'formal/typed_publication/{args.target}_properties.vh')
    source=rtl.read_text()
    if source.count('endmodule')!=1: raise ValueError('Expected one original module')
    instrumented=source.replace('endmodule',props.read_text()+'\nendmodule')
    rel=out.relative_to(ROOT).as_posix()
    extra='' if args.target=='gate' else 'rtl/contracts/typed_publication_gate.sv'
    if args.target=='axil':extra+=' rtl/contracts/typed_intent_v1/typed_intent_guard.sv'
    observed_dependency={}
    if args.target=='guard':
        # A formal-only observation port connects the real wrapper state to a
        # cross-module invariant. It does not feed any functional logic.
        dep=ROOT/'rtl/contracts/typed_publication_gate.sv'
        invariant=ROOT/'formal/typed_publication/invariants.vh'
        observed=dep.read_text().replace('output logic [31:0] elapsed',
            'input wire [63:0] f_last_seen_request,\n    output logic [31:0] elapsed')
        observed=observed.replace('endmodule',invariant.read_text()+'''
    always @(posedge clk) if(f_past_valid && !$past(reset))
        assert(last_request<=f_last_seen_request);
endmodule''')
        (out/'observed_gate.sv').write_text(observed)
        instrumented=instrumented.replace('.clk(clk),.reset(reset),.start(',
            '.f_last_seen_request(last_seen_request),.clk(clk),.reset(reset),.start(')
        extra=f'{rel}/observed_gate.sv'
        observed_dependency={str(dep.relative_to(ROOT)):digest(dep),
                             str(invariant.relative_to(ROOT)):digest(invariant)}
    (out/'instrumented.sv').write_text(instrumented)
    top='typed_publication_gate' if args.target=='gate' else f'typed_intent_{args.target}'
    parameters='chparam -set LABEL_COUNT 18 -set MIN_CONFIDENCE 0 typed_publication_gate' if args.target=='gate' else ''
    (out/'prove.ys').write_text(f'''read_verilog -formal -sv {extra} {rel}/instrumented.sv
{parameters}
prep -top {top} -flatten
memory_map
async2sync
chformal -lower
formalff -clk2ff
dffunmap
opt_clean
sat -verify -prove-asserts -tempinduct -seq 2 -maxsteps 6 -set-assumes -set clk 1 -timeout 60 -dump_vcd {rel}/induction.vcd
''')
    with (out/'console.log').open('w') as f:
        result=subprocess.run(['uv','tool','run','--from','yowasp-yosys','yowasp-yosys','-Q','-T',
            '-l',f'{rel}/prove.log','-s',f'{rel}/prove.ys'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
    log=(out/'prove.log').read_text()
    passed=result.returncode==0 and 'Induction step proven: SUCCESS!' in log
    (out/'receipt.json').write_text(json.dumps({'exit_code':result.returncode,'induction_proved':passed,
        'rtl_sha256':digest(rtl),'properties_sha256':digest(props),
        'instrumented_sha256':digest(out/'instrumented.sv'),'labels':18,'minimum_confidence':0,
        'target':args.target,
        'dependency_sha256':{s:digest(ROOT/s) for s in extra.split()},
        'observation_dependency_sha256':observed_dependency,
        'assumptions':['first sampled edge reset','synchronous RTL step semantics'],
        'claim':('inductive RTL safety/progress/deadline-boundary invariants' if args.target=='gate'
                 else ('session immutability, monotone consumed IDs, validated launch and accepted-proposal prerequisites'
                       if args.target=='guard' else
                       'AXI-Lite AW/W capture, one-response execution, held B/R response stability and read capture')),
        'limits':['no physical/CDC/ARM/DDR proof','AXI protocol properties do not prove full endpoint functional correctness']},indent=2)+'\n')
    print('PASS RTL invariant induction' if passed else 'NOT PROVED; preserve logs')
    raise SystemExit(0 if passed else 1)

if __name__=='__main__':main()
