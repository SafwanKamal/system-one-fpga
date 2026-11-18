"""Narrow row-range arithmetic in a separate, hash-checked predecode descendant."""
import argparse, json, shutil
from create_typed200_predecode_candidate import ROOT, OUT as PARENT, verify as parent_verify, sha

OUT=ROOT/'rtl/v2/candidates/typed200_row_range'
CHANGED={'contracts/typed_intent_axil.sv'}

def verify():
    parent=parent_verify();m=json.loads((OUT/'candidate.json').read_text())
    assert sha(PARENT/'candidate.json')==m['parent_manifest_sha256']
    actual={p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.suffix in ('.sv','.v')}
    assert actual==m['candidate_sha256']
    assert {n for n in actual if actual[n]!=parent['candidate_sha256'].get(n)}==CHANGED
    return m

def create():
    parent_verify();assert not OUT.exists();shutil.copytree(PARENT,OUT)
    p=OUT/'contracts/typed_intent_axil.sv';s=p.read_text()
    a=s.index('    wire shape_ok=');b=s.index('    assign admission_tokens=',a)
    s=s[:a]+'''    // A valid frame has tokens 1..128, first 0..127, count 1..128.
    // Reject high raw bits before using narrow arithmetic. Nine-bit sum retains
    // carry for every low-field combination (127+255=382); never wrap a range.
    // Positive count and sum<=tokens imply first<tokens, without a second compare.
    wire [8:0] selected_row_end={2'b0,bank[5][22:16]}+{1'b0,bank[28][7:0]};
    wire shape_ok=bank[5][15:8]==0 && bank[5][7:0]!=0 && bank[5][7:0]<=8'd128
        && bank[5][31:23]==0 && bank[28][31:8]==0 && bank[28][7:0]!=0
        && selected_row_end<={1'b0,bank[5][7:0]};
'''+s[b:];p.write_text(s)
    (OUT/'README.md').write_text('''# Isolated typed row-range candidate

Parent: sealed typed200_predecode. Only contracts/typed_intent_axil.sv changes.
No new register, cache, state, clock, numerical operator or externally visible cycle.
All raw high fields are explicitly rejected. Nine-bit unsigned sum cannot wrap.
The strict first<tokens comparison follows from positive count and bounded sum.
Requires whole raw-input equivalence, full sequential endpoint correspondence,
independent encoder regression and matched timing before physical experiments.
No baseline, package, board ownership, live permission or deadline change.
''')
    (OUT/'candidate.json').write_text(json.dumps({'candidate':'typed200_row_range',
        'parent_manifest_sha256':sha(PARENT/'candidate.json'),
        'candidate_sha256':{q.relative_to(OUT).as_posix():sha(q) for q in OUT.rglob('*') if q.suffix in ('.sv','.v')},
        'intended_external_cycle_delta':0,'numerical_contract_changed':False,
        'deadline_epoch_logic_changed':False,'hardware_qualified':False},indent=2)+'\n')
    verify()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');a=ap.parse_args()
    verify() if a.verify else create();print('PASS isolated row-range candidate inventory')
