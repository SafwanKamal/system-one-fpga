"""Move saturation across an existing register, without adding a pipeline cycle."""
import argparse,json,shutil
from create_typed200_profile_cache_candidate import ROOT,OUT as PARENT,verify as parent_verify,sha

OUT=ROOT/'rtl/v2/candidates/typed200_stage_clamp'
CHANGED={'encoder/add_skip_engine.sv'}

def verify():
    parent=parent_verify();m=json.loads((OUT/'candidate.json').read_text())
    assert sha(PARENT/'candidate.json')==m['parent_manifest_sha256']
    actual={p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.suffix in ('.sv','.v')}
    assert actual==m['candidate_sha256']
    assert {n for n in actual if actual[n]!=parent['candidate_sha256'].get(n)}==CHANGED
    return m

def create():
    parent_verify();assert not OUT.exists();shutil.copytree(PARENT,OUT)
    p=OUT/'encoder/add_skip_engine.sv';s=p.read_text()
    a='    logic signed [25:0] rounded [0:7];';assert s.count(a)==1
    s=s.replace(a,'    logic signed [15:0] skip_clamped [0:7]; // Same L+2 edge; different state encoding.')
    a='            logic signed [15:0] skip;';assert s.count(a)==1
    s=s.replace(a,'            logic signed [25:0] rounded_value;')
    s=s.replace('rounded[e] <=','rounded_value =')
    a='''            skip = rounded[e] > 26'sd32767 ? 16'sd32767 :
                   rounded[e] < -26'sd32767 ? -16'sd32767 : 16'(rounded[e]);
            sum = 17'($signed(a_held[L+2][16*e +: 16])) + 17'(skip);'''
    b='''            // Saturate the EXACT signed26 rounding result before the existing
            // L+2 register. The output stage consumes its previous-cycle value.
            skip_clamped[e] <= rounded_value > 26'sd32767 ? 16'sd32767 :
                               rounded_value < -26'sd32767 ? -16'sd32767 : 16'(rounded_value);
            sum = 17'($signed(a_held[L+2][16*e +: 16])) + 17'(skip_clamped[e]);'''
    assert s.count(a)==1;s=s.replace(a,b)
    s=s.replace('// L+3 sum -> destination','// L+3 residual sum -> destination (first clamp is already registered)')
    s=s.replace('// L+2 rounded skip;','// L+2 rounded/clamped skip;')
    assert 'rounded[e]' not in s
    p.write_text(s)
    (OUT/'README.md').write_text('''# Separate typed200_stage_clamp candidate

Parent: frozen typed200_profile_cache; only ADD_SKIP changes. The first clamp
moves before the existing L+2 register; the stored state is now INT16 saturated
skip rather than INT26 rounded skip. The exact finite-width INT26 rounding and
shift are preserved before saturation. Residual INT17 addition/final clamp,
all control/address/valid/reset and external cycle boundaries are unchanged.
The new register is renamed because its state meaning differs. Proof must
establish skip_clamped == clamp(old.rounded), not equality of raw state.
Requires both-stage timing probes and independent parent arithmetic regression.
No qualification or deployment. All parents/baselines/packages stay frozen.
''')
    (OUT/'candidate.json').write_text(json.dumps({'candidate':'typed200_stage_clamp','sealed':False,
        'parent_manifest_sha256':sha(PARENT/'candidate.json'),
        'candidate_sha256':{q.relative_to(OUT).as_posix():sha(q) for q in OUT.rglob('*') if q.suffix in ('.sv','.v')},
        'intended_external_cycle_delta':0,'numerical_contract_changed':False,
        'deadline_epoch_logic_changed':False,'hardware_qualified':False},indent=2)+'\n')
    verify()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');a=ap.parse_args()
    verify() if a.verify else create();print('PASS separate stage-clamp inventory')
