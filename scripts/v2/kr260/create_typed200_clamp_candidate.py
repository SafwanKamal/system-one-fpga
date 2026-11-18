"""Separate same-cycle saturation decomposition; never edit a parent candidate."""
import argparse
import json
import shutil
from create_typed200_profile_cache_candidate import ROOT, OUT as PARENT, verify as parent_verify, sha

OUT = ROOT / 'rtl/v2/candidates/typed200_clamp'
CHANGED = {'encoder/add_skip_engine.sv'}


def verify():
    parent = parent_verify()
    manifest = json.loads((OUT / 'candidate.json').read_text())
    assert sha(PARENT / 'candidate.json') == manifest['parent_manifest_sha256']
    actual = {p.relative_to(OUT).as_posix(): sha(p) for p in OUT.rglob('*') if p.suffix in ('.sv', '.v')}
    assert actual == manifest['candidate_sha256']
    assert {n for n in actual if actual[n] != parent['candidate_sha256'].get(n)} == CHANGED
    return manifest


def create():
    parent_verify()
    assert not OUT.exists(), 'Preserve existing candidate'
    shutil.copytree(PARENT, OUT)
    p = OUT / 'encoder/add_skip_engine.sv'
    s = p.read_text()
    old = '''            skip = rounded[e] > 26'sd32767 ? 16'sd32767 :
                   rounded[e] < -26'sd32767 ? -16'sd32767 : 16'(rounded[e]);
            sum = 17'($signed(a_held[L+2][16*e +: 16])) + 17'(skip);
            out_data[16*e +: 16] <= sum > 17'sd32767 ? 16'sd32767 :
                                   sum < -17'sd32767 ? -16'sd32767 : 16'(sum);'''
    new = '''            // The legal negative range excludes -32768. Classify sign
            // extension and the low-bit zero case using reductions, avoiding
            // serial signed magnitude comparisons around the residual adder.
            if (rounded[e][25])
                skip = (&rounded[e][25:15]) && (|rounded[e][14:0]) ?
                       rounded[e][15:0] : 16'h8001;
            else
                skip = (|rounded[e][25:15]) ? 16'h7fff : rounded[e][15:0];
            sum = 17'($signed(a_held[L+2][16*e +: 16])) + 17'(skip);
            if (sum[16])
                out_data[16*e +: 16] <= sum[15] && (|sum[14:0]) ? sum[15:0] : 16'h8001;
            else
                out_data[16*e +: 16] <= sum[15] ? 16'h7fff : sum[15:0];'''
    assert s.count(old) == 1
    p.write_text(s.replace(old, new))
    (OUT / 'README.md').write_text('''# Separate typed200_clamp candidate

Parent: frozen typed200_profile_cache. Only ADD_SKIP clamp logic changes.
Explicit sign-extension/zero reductions implement both asymmetric signed
[-32767,32767] clamps. Product, finite-width rounding, shift, residual addition,
all registers, reset, valid/address/control and cycle boundaries are unchanged.
Requires whole-domain arithmetic proof, whole-engine correspondence, independent
parent arithmetic in full regression, and a matched mapped timing probe before
full physical work. No hardware or WCET qualification. Parent and qualified
sources, packages, recovery, numerical and evidence artifacts remain frozen.
''')
    (OUT / 'candidate.json').write_text(json.dumps({
        'candidate': 'typed200_clamp', 'sealed': False,
        'parent_manifest_sha256': sha(PARENT / 'candidate.json'),
        'candidate_sha256': {p.relative_to(OUT).as_posix(): sha(p) for p in OUT.rglob('*') if p.suffix in ('.sv', '.v')},
        'intended_external_cycle_delta': 0, 'numerical_contract_changed': False,
        'deadline_epoch_logic_changed': False, 'hardware_qualified': False
    }, indent=2) + '\n')
    verify()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--verify', action='store_true'); a = ap.parse_args()
    verify() if a.verify else create()
    print('PASS separate clamp candidate inventory; proof and timing evidence required')
