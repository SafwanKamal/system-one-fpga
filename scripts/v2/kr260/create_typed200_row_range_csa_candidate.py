"""Carry-save row-range comparison, isolated from the preserved direct-sum attempt."""
import argparse,json,shutil
from create_typed200_predecode_candidate import ROOT,OUT as PARENT,verify as parent_verify,sha
OUT=ROOT/'rtl/v2/candidates/typed200_row_range_csa'
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
    p=OUT/'contracts/typed_intent_axil.sv';s=p.read_text();a=s.index('    wire shape_ok=');b=s.index('    assign admission_tokens=',a)
    s=s[:a]+'''    // Compare first+count<=tokens using one carry-propagating addition.
    // A+B+~T = A+B-T+255: accepted iff there is no bit above bit7.
    // XOR/majority form an exact carry-save sum. Preserve BOTH possible carries:
    // row_carry[7] is already above bit7; row_total[8] is the final carry.
    // Reject high raw bits before using the narrowed fields; no legal-input assumption.
    wire [7:0] row_xor={1'b0,bank[5][22:16]} ^ bank[28][7:0] ^ ~bank[5][7:0];
    wire [7:0] row_carry=({1'b0,bank[5][22:16]} & bank[28][7:0])
        | ({1'b0,bank[5][22:16]} & ~bank[5][7:0]) | (bank[28][7:0] & ~bank[5][7:0]);
    wire [8:0] row_total={1'b0,row_xor}+{1'b0,row_carry[6:0],1'b0};
    wire shape_ok=bank[5][15:8]==0 && bank[5][7:0]!=0 && bank[5][7:0]<=8'd128
        && bank[5][31:23]==0 && bank[28][31:8]==0 && bank[28][7:0]!=0
        && !row_carry[7] && !row_total[8];
'''+s[b:];p.write_text(s)
    (OUT/'README.md').write_text('''# Carry-save typed row-range candidate

Parent: sealed typed200_predecode, independent from the direct-sum attempt.
Only typed_intent_axil changes. Explicit raw high-bit rejection and carry-save
first+count+~tokens compare; preserve both carries above bit7. No new state/cycle.
Requires actual-source all-raw-input and full endpoint proofs, independent full
regression and matched overall/shape timing gain before synthesis and placement.
No live permission cached; no hardware or timing-guarantee claim.
''')
    (OUT/'candidate.json').write_text(json.dumps({'candidate':'typed200_row_range_csa',
        'parent_manifest_sha256':sha(PARENT/'candidate.json'),
        'candidate_sha256':{q.relative_to(OUT).as_posix():sha(q) for q in OUT.rglob('*') if q.suffix in ('.sv','.v')},
        'intended_external_cycle_delta':0,'numerical_contract_changed':False,
        'deadline_epoch_logic_changed':False,'hardware_qualified':False},indent=2)+'\n')
    verify()
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');a=ap.parse_args()
    verify() if a.verify else create();print('PASS isolated carry-save row-range inventory')
