"""Seal a completed timing-only route assessment, including failed closure."""
from pathlib import Path
from datetime import datetime,timezone
import json
from typed200_row_range_csa_route_common import ROOT,OUT,sha,verify_parent
def main():
    dest=ROOT/'docs/research/2026-10-16-typed200-row-range-csa-route-validation.json'
    assert not dest.exists();preserved,prior=verify_parent()
    complete=json.loads((OUT/'completion.json').read_text());assert complete['completed']
    assert complete['native_exit_code']==0 and complete['review_exit_code']==0
    reviewed=json.loads((OUT/'route-review.json').read_text());assert reviewed['review_completed']
    for n,h in reviewed['evidence_sha256'].items():assert sha(ROOT/n)==h,n
    inp=json.loads((OUT/'input-proof.json').read_text())
    for n,h in inp['source_sha256'].items():assert sha(ROOT/n)==h,n
    assert sha(OUT/'input/placed.dcp')==inp['input_checkpoint_sha256']
    assert not any(p.suffix.lower() in ('.bit','.bin','.xsa','.pdi') for p in OUT.rglob('*') if p.is_file())
    source=[Path(__file__),*[ROOT/n for n in inp['source_sha256']]]
    report=ROOT/'docs/research/2026-10-16-typed200-row-range-csa-route.md'
    evidence=[p for p in OUT.rglob('*') if p.is_file() and '.Xil' not in p.parts]
    result={'verified_utc':datetime.now(timezone.utc).isoformat(),'experiment_complete':True,
        'routed_closure_passed':reviewed['routed_closure_passed'],'target_mhz':200,
        'setup_ns':reviewed['setup_ns'],'hold_ns':reviewed['hold_ns'],
        'constraints_unchanged':reviewed['constraints_unchanged'],
        'preserved_unique_files':len(preserved),'all_preserved_files_unchanged':True,
        'preserved_sha256':preserved,'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in source},
        'documentation_sha256':{report.relative_to(ROOT).as_posix():sha(report)},
        'evidence_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in evidence},
        'hardware_qualified':False,'wcet_certified':False,'bitstream_created':False,
        'package_or_deployment_approved':False,'target_executed':False}
    with dest.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print('PASS route assessment sealed;',len(preserved),'prior paths unchanged; routed closure='+str(result['routed_closure_passed']))
if __name__=='__main__':main()
