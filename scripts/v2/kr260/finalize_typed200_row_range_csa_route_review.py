"""Correct only the completed review's self-log hash; retain original receipt."""
import json
from typed200_row_range_csa_route_common import ROOT,OUT,sha,verify_parent
def main():
    verify_parent();dest=OUT/'route-review-final.json';assert not dest.exists()
    original=OUT/'route-review.json';r=json.loads(original.read_text())
    unstable=(OUT/'review-console.log').relative_to(ROOT).as_posix();old=r['evidence_sha256'][unstable]
    for n,h in r['evidence_sha256'].items():
        if n!=unstable:assert sha(ROOT/n)==h,n
    assert (OUT/'review-console.log').read_text().strip().startswith('Routed closure passed=True; setup=0.048ns; hold=0.011ns;')
    done=json.loads((OUT/'completion.json').read_text());assert done['completed'] and done['review_exit_code']==0 and done['native_exit_code']==0
    r['evidence_sha256'][unstable]=sha(ROOT/unstable)
    r['evidence_sha256'][original.relative_to(ROOT).as_posix()]=sha(original)
    r['receipt_correction']={'scope':'Only reviewer self-console hash after final print',
        'path':unstable,'original_snapshot_hash':old,'completed_log_hash':sha(ROOT/unstable),
        'original_receipt_sha256':sha(original),'native_results_changed':False}
    with dest.open('x') as f:json.dump(r,f,indent=2);f.write('\n')
    print('PASS all native evidence unchanged; final review log hash corrected in separate receipt')
if __name__=='__main__':main()
