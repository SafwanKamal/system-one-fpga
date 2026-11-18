"""Full sequential guard equivalence; all 256 digest bits, no added clock stage."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parents[2]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='typed200-validation-tree-formal-v1');a=ap.parse_args()
    out=ROOT/'build/v2'/a.name;out.mkdir(exist_ok=False);rel=out.relative_to(ROOT).as_posix()
    old=ROOT/'rtl/v2/candidates/typed200_flush/contracts/typed_intent_guard.sv'
    new=ROOT/'rtl/v2/candidates/typed200_validation_tree/contracts/typed_intent_guard.sv'
    gate=ROOT/'rtl/v2/candidates/typed200_flush/contracts/typed_publication_gate.sv'
    new_gate=ROOT/'rtl/v2/candidates/typed200_validation_tree/contracts/typed_publication_gate.sv'
    # Explicit observation ports avoid unsupported frontend hierarchical references.
    # Only copied miter modules gain ports; no candidate source changes.
    for source,name in [(old,'old_guard'),(new,'new_guard')]:
        s=source.read_text().replace('module typed_intent_guard #(',f'module {name} #(',1)
        s=s.replace('    output wire [31:0] elapsed\n','    output wire [31:0] elapsed,\n    output wire [63:0] proof_seen,proof_last,\n    output wire [31:0] proof_limit\n')
        assert 'proof_seen' in s
        s=s.replace('.elapsed(elapsed)', '.elapsed(elapsed),.proof_last(proof_last),.proof_limit(proof_limit)')
        s=s.replace('typed_publication_gate #(',('old_publication_gate' if name=='old_guard' else 'new_publication_gate')+' #(',1)
        s=s.replace('endmodule','assign proof_seen=last_seen_request;\nendmodule',1)
        (out/(name+'.sv')).write_text(s)
    for source,module in [(gate,'old_publication_gate'),(new_gate,'new_publication_gate')]:
        s=source.read_text().replace('module typed_publication_gate #(',f'module {module} #(',1)
        s=s.replace('    output logic [31:0] elapsed\n',
            '    output logic [31:0] elapsed,\n    output wire [63:0] proof_last,\n    output wire [31:0] proof_limit\n')
        assert 'proof_last' in s
        s=s.replace('endmodule','assign proof_last=last_request;\nassign proof_limit=limit_reg;\nendmodule',1)
        (out/(module+'.sv')).write_text(s)
    inputs={'clk':1,'reset':1,'install_session':1,'session_value':64,'start':1,'ack':1,
        'request_id':64,'request_contract':256,'budget_cycles':32,'proposal_valid':1,
        'proposal_session':64,'proposal_request_id':64,'proposal_contract':256,'proposal_outcome':3,
        'proposal_label':16,'proposal_reserved_score':16,'core_complete':1,'core_success':1,
        'live_quiet':1,'core_session':64,'core_request_id':64}
    outputs={'session_configured':1,'result_session':64,'ready':1,'admitted':1,'active':1,
        'result_valid':1,'quarantined':1,'result_request_id':64,'result_contract':256,
        'result_outcome':3,'result_label':16,'result_reserved_score':16,'elapsed':32,
        'proof_seen':64,'proof_last':64,'proof_limit':32}
    def decl(kind,name,width):return kind+(' ' if width==1 else f' [{width-1}:0] ')+name
    code='module profile_tree_formal('+',\n'.join(decl('input wire',n,w) for n,w in inputs.items())+');\n'
    for prefix,module in [('o','old_guard'),('n','new_guard')]:
        code+=';\n'.join(decl('wire',prefix+'_'+n,w) for n,w in outputs.items())+';\n'
        ports=[f'.{n}({n})' for n in inputs]+[f'.{n}({prefix}_{n})' for n in outputs]
        code+=f'{module} {prefix}('+','.join(ports)+');\n'
    code+='''reg past_valid=0;
    always @(posedge clk) begin
        past_valid<=1;
        if(!past_valid) assume(reset);
        if(past_valid) begin
'''
    for n in outputs:code+=f'assert(o_{n}==n_{n});\n'
    # Correspondence invariants include private history/limit state so induction
    # cannot choose unrelated invisible histories in the two implementations.
    code+='end\nend\nendmodule\n';(out/'miter.sv').write_text(code)
    (out/'prove.ys').write_text(f'''read_verilog -formal -sv {rel}/old_publication_gate.sv {rel}/new_publication_gate.sv {rel}/old_guard.sv {rel}/new_guard.sv {rel}/miter.sv
prep -top profile_tree_formal -flatten
async2sync
chformal -lower
formalff -clk2ff
dffunmap
opt_clean
sat -verify -prove-asserts -tempinduct -seq 2 -maxsteps 12 -set-assumes -set clk 1 -timeout 60 -dump_vcd {rel}/counterexample.vcd
''')
    with (out/'console.log').open('w') as log:
        r=subprocess.run(['uv','tool','run','--from','yowasp-yosys==0.70.0.0.post1259','yowasp-yosys',
            '-Q','-T','-l',f'{rel}/prove.log','-s',f'{rel}/prove.ys'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    passed=r.returncode==0 and 'Induction step proven: SUCCESS!' in (out/'prove.log').read_text()
    (out/'receipt.json').write_text(json.dumps({'passed':passed,'exit_code':r.returncode,
        'digest_bits':256,'latency_cycles_added':0,
        'scope':'All guard outputs and private history/limit state equivalent at every sampled edge; arbitrary frames/proposals/core status/quiet and resets',
        'assumptions':['first sampled edge reset','single sampled clock','two-state formal semantics'],
        'limits':['not analog glitch/timing proof','not whole encoder or deployed WCET proof'],
        'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in [old,new,gate,new_gate]},
        'artifact_sha256':{p.name:sha(p) for p in out.iterdir() if p.is_file()}},indent=2)+'\n')
    print('PASS exact sequential typed guard equivalence, all256 digest bits' if passed else 'NOT PROVED; preserve attempt')
    raise SystemExit(0 if passed else 1)


if __name__=='__main__':
    main()
