"""Fit a CLINC rejection threshold on development accuracy, never benchmark labels."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/v2/typed200-linux-r5-calibrated-v1'
SOURCE=ROOT/'firmware/typed200_linux_r5_calibrated_inference'
sys.path.insert(0,str(ROOT/'src'))

def main():
    from sysone.v2.chain_data import load_clinc
    path=BASE/'policy-check-v1/dev-probabilities.npy';p=np.load(path)
    splits,labels=load_clinc();y=np.asarray([c.segments[0].intent for c in splits['dev']]);oos=labels.index('oos')
    assert p.shape==(len(y),151)
    ins=y!=oos;winner=p.argmax(1);base_in=float(np.mean(winner[ins]==y[ins]))
    def rates(tau):
        pred=np.where(p.max(1)<tau,oos,winner)
        return dict(tau=float(tau),correct=int(sum(pred==y)),n=len(y),accuracy=float(np.mean(pred==y)),in_scope_accuracy=float(np.mean(pred[ins]==y[ins])),oos_recall=float(np.mean(pred[~ins]==oos)))
    grid=[rates(tau) for tau in np.arange(0,1.00001,.005)]
    eligible=[r for r in grid if base_in-r['in_scope_accuracy']<=.01+1e-12]
    best=max(eligible,key=lambda r:(r['correct'],r['oos_recall'],-r['tau']))
    assert best['accuracy']>rates(0)['accuracy']
    result=dict(passed=True,candidate_only=True,deployed=False,split='dev',objective='Maximum total dev classification accuracy; tie: OOS recall then lower threshold; at most1 percentage point in-scope loss',before=rates(0),legacy_policy=rates(.48),selected=best,grid=grid,dev_probabilities_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),test_labels_used=False,encoder_weights_changed=False,classifier_weights_changed=False,interpretation='Fitted development-set improvement; requires independent held-out and hardware evaluation before a deployment gain can be claimed.')
    (BASE/'calibration-dev-fit.json').write_text(json.dumps(result,indent=2)+'\n')
    header=SOURCE/'clinc_policy.h'
    (BASE/'clinc_policy.tau048.h').write_bytes(header.read_bytes())
    header.write_text(header.read_text().replace('#define CLINC_TAU 0.48',f"#define CLINC_TAU {best['tau']!r}"))
    p=ROOT/'scripts/v2/build_r5_calibrated_candidate.py';p.write_text(p.read_text().replace("out=BASE/'firmware-build-v1'","out=BASE/'firmware-build-v2'"))
    p=ROOT/'scripts/v2/check_r5_calibrated_heads.py';p.write_text(p.read_text().replace('sum() < 0.48:',f"sum() < {best['tau']!r}:"))
    print(json.dumps(dict(before=result['before'],legacy=result['legacy_policy'],selected=best),indent=2),flush=True)

if __name__=='__main__':main()
