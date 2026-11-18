"""Balanced full-profile comparison and parallel, same-cycle admission decisions."""
import argparse
import json
import shutil
from create_typed200_flush_candidate import ROOT,OUT as PARENT,verify as parent_verify,sha
from create_typed200_profile_tree_candidate import OUT as TREE,verify as tree_verify

OUT=ROOT/'rtl/v2/candidates/typed200_validation_tree'


def verify():
    parent=parent_verify();m=json.loads((OUT/'candidate.json').read_text())
    assert sha(PARENT/'candidate.json')==m['parent_manifest_sha256']
    actual={p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.suffix in ('.sv','.v')}
    assert actual==m['candidate_sha256']
    assert {n for n in actual if actual[n]!=parent['candidate_sha256'].get(n)}=={
        'contracts/typed_intent_guard.sv','contracts/typed_publication_gate.sv'}
    return m


def create():
    parent_verify();tree_verify();assert not OUT.exists();shutil.copytree(PARENT,OUT)
    s=(TREE/'contracts/typed_intent_guard.sv').read_text()
    assert s.count('request_id>last_seen_request')==3
    s=s.replace('request_id>last_seen_request','request_is_new')
    anchor='    logic [63:0] last_seen_request;';assert s.count(anchor)==1
    s=s.replace(anchor,anchor+'''\n    // Keep the sequence decision independent of profile-valid control fan-in.
    (* keep = "true" *) wire request_is_new = request_id > last_seen_request;''')
    (OUT/'contracts/typed_intent_guard.sv').write_text(s)
    p=OUT/'contracts/typed_publication_gate.sv';s=p.read_text()
    anchor='    logic [31:0] limit_reg;';assert s.count(anchor)==1
    s=s.replace(anchor,anchor+'''\n    // Same boolean checks, same edge. Preserve individual decision boundaries
    // so an unrelated valid flag need not propagate through a wide comparator.
    (* keep = "true" *) wire budget_is_zero = budget_cycles == 0;
    (* keep = "true" *) wire request_not_new = request_id <= last_request;
    (* keep = "true" *) wire contract_is_empty = contract_sha256 == 0;''')
    anchor='budget_cycles==0 || request_id<=last_request || contract_sha256==0'
    assert s.count(anchor)==1;s=s.replace(anchor,'budget_is_zero || request_not_new || contract_is_empty')
    p.write_text(s)
    (OUT/'README.md').write_text('''# typed200_validation_tree: same-cycle parallel typed admission

Experimental sibling of sealed typed200_flush. All256 contract bits compare in
balanced preserved byte/group reductions. Existing request-sequence, zero-budget,
and empty-contract decisions retain separate KEEP boundaries. No check is removed,
no digest is shortened and no register, latency or deadline pause is introduced.
Only typed_intent_guard and typed_publication_gate change; arithmetic, native
epoch/drain/error, transport ABI and frozen numerical contract remain unchanged.

Formal old/new guard-and-gate equivalence, full regression, mapped probe and actual
physical evidence are required. Compile only this candidate namespace with the
qualified1024-capacity/16-attention-lane pipeline profile. No hardware qualification
or programming is implied. HANDOFF.md and the timing continuation report track
actual evidence rather than requested clock frequency.
''')
    (OUT/'candidate.json').write_text(json.dumps({'candidate':'typed200_validation_tree','sealed':False,
        'parent_manifest_sha256':sha(PARENT/'candidate.json'),'profile_tree_parent_sha256':sha(TREE/'candidate.json'),
        'candidate_sha256':{p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.suffix in ('.sv','.v')},
        'contract_bits_checked':256,'pipeline_stages_added':0,'intended_cycle_delta':0,
        'numerical_contract_changed':False,'deadline_epoch_logic_changed':False,'hardware_qualified':False},indent=2)+'\n')
    verify()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true');a=p.parse_args()
    verify() if a.verify else create()
    print('PASS parallel full-check validation inventory; functional/physical evidence pending')
