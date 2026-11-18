"""Same-cycle, full-width contract comparison with explicit balanced boundaries."""
import argparse
import json
import shutil
from create_typed200_flush_candidate import ROOT, OUT as PARENT, verify as parent_verify, sha

OUT=ROOT/'rtl/v2/candidates/typed200_profile_tree'


def verify():
    parent=parent_verify();m=json.loads((OUT/'candidate.json').read_text())
    assert sha(PARENT/'candidate.json')==m['parent_manifest_sha256']
    actual={p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.suffix in ('.sv','.v')}
    assert actual==m['candidate_sha256']
    assert {n for n in actual if actual[n]!=parent['candidate_sha256'].get(n)}=={'contracts/typed_intent_guard.sv'}
    return m


def create():
    parent_verify();assert not OUT.exists();shutil.copytree(PARENT,OUT)
    p=OUT/'contracts/typed_intent_guard.sv';s=p.read_text()
    assert s.count('request_contract==CONTRACT')==2
    s=s.replace('request_contract==CONTRACT','request_contract_ok')
    anchor='    wire gate_ready,gate_admitted;'
    assert s.count(anchor)==1
    s=s.replace(anchor,'''    // Preserve bounded reduction boundaries rather than one long carry chain.
    // Every one of the 256 bits is checked combinationally on the SAME edge.
    // No register, bypass, delayed permission or truncated digest is introduced.
    (* keep = "true" *) wire [31:0] request_contract_byte_equal;
    (* keep = "true" *) wire [3:0] request_contract_group_equal;
    for(genvar b=0;b<32;b++) begin : gen_contract_bytes
        assign request_contract_byte_equal[b] = request_contract[8*b+:8] == CONTRACT[8*b+:8];
    end
    for(genvar g=0;g<4;g++) begin : gen_contract_groups
        assign request_contract_group_equal[g] = &request_contract_byte_equal[8*g+:8];
    end
    wire request_contract_ok = &request_contract_group_equal;

'''+anchor)
    p.write_text(s)
    (OUT/'README.md').write_text('''# typed200_profile_tree: same-cycle balanced contract validation

Separate experimental sibling of sealed typed200_flush. Only typed_intent_guard
changes: all256 contract bits are compared in 32 byte groups, four reductions and
a final reduction. KEEP boundaries express bounded combinational depth to Vivado.
No register, digest truncation, admission delay or permission bypass is added.
Deadline, identity, current live quiet/error veto, ABI and numerical head are
unchanged. The candidate targets the measured24-level/21CARRY8 placed SHA-to-
admission path in the corrected clock-flow control. Formal equivalence, regression
and actual synthesis/placement are required; no timing benefit is claimed yet.

Use only this RTL namespace and the inherited qualified1024-capacity/16-attention-
lane physical profile. Target inference remains H384/T1..128. Qualified baseline,
all earlier candidates and numerical/package/recovery sources stay frozen.
No hardware programming is part of this experiment.
''')
    (OUT/'candidate.json').write_text(json.dumps({'candidate':'typed200_profile_tree','sealed':False,
        'parent_manifest_sha256':sha(PARENT/'candidate.json'),
        'candidate_sha256':{p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.suffix in ('.sv','.v')},
        'contract_bits_checked':256,'pipeline_stages_added':0,'intended_cycle_delta':0,
        'numerical_contract_changed':False,'deadline_epoch_logic_changed':False,'hardware_qualified':False},indent=2)+'\n')
    verify()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true');a=p.parse_args()
    verify() if a.verify else create()
    print('PASS balanced full-width contract candidate inventory; verification/physical evidence pending')
