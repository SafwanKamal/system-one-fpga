"""Restore the existing dev-calibrated CLINC rule in a separate R5 candidate."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-linux-r5-calibrated-v1'
SOURCE=ROOT/'firmware/typed200_linux_r5_calibrated_inference'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    BASE.mkdir(exist_ok=False);SOURCE.mkdir(exist_ok=False)
    original=ROOT/'firmware/typed200_linux_r5_inference'
    manifest=json.loads((ROOT/'export/v2/image/minilm-l12-v1-kr260/manifest.json').read_text())
    decision=ROOT/'export/v2/image/minilm-l12-v1/decision.json';policy=json.loads(decision.read_text())
    head=next(h for h in manifest['heads'] if h['kind']== 'intent' and h['name']=='clinc')
    assert policy['head']=='intent.clinc' and policy['rule']=='max_prob' and policy['tau']==0.48
    oos=head['labels'].index(policy['oos_label'])
    for name in ['abi.h','heads.inc','start.S','tcm.ld']:(SOURCE/name).write_bytes((original/name).read_bytes())
    (BASE/'decision.before.json').write_bytes(decision.read_bytes())
    header='''/* Fixed existing validation-tuned CLINC decision rule; no host head math. */
#ifndef R5_CLINC_POLICY_H
#define R5_CLINC_POLICY_H
#include <stdint.h>
#define CLINC_TAU 0.48
#define CLINC_OOS_LABEL OOS_INDEX
/* exp(x), x<=0: range reduction and Taylor polynomial, without libc/libm.
 * The reduced argument is in [-ln(2),0]; degree18 truncation is <2e-20.
 * IEEE754 scaling handles very small probabilities; doubles use R5 VFP.
 */
static double policy_exp_negative(double x) {
 if(x < -745.0)return 0.0;
 uint32_t n=(uint32_t)(-x*1.4426950408889634074);
 double r=x+(double)n*0.69314718055994530942;
 double term=1.0,sum=1.0;
 for(uint32_t k=1;k<=18;k++){term*=r/(double)k;sum+=term;}
 union {uint64_t bits;double value;} scale;
 if(n<=1022)scale.bits=(uint64_t)(1023-n)<<52;
 else if(n<=1074)scale.bits=(uint64_t)1<<(1074-n);
 else return 0.0;
 return sum*scale.value;
}
static uint32_t calibrated_clinc_label(const double *scores,uint32_t count,uint32_t winner) {
 double maximum=scores[winner],denominator=0.0;
 for(uint32_t c=0;c<count;c++)denominator+=policy_exp_negative(scores[c]-maximum);
 return 1.0/denominator < CLINC_TAU ? CLINC_OOS_LABEL : winner;
}
#endif
'''.replace('OOS_INDEX',str(oos))
    (SOURCE/'clinc_policy.h').write_text(header)
    code=(original/'inference.c').read_text().replace('#include "heads.inc"','#include "heads.inc"\n#include "clinc_policy.h"')
    code=code.replace('double best=0;uint32_t label=0;','double best=0,scores[MAX_CLASSES];uint32_t label=0;')
    code=code.replace('if(!c || score>best)', 'scores[c]=score;\n   if(!c || score>best)')
    code=code.replace('job->label=label;job->classes=h->classes;','if(job->head==1)label=calibrated_clinc_label(scores,h->classes,label);\n  job->label=label;job->classes=h->classes;')
    (SOURCE/'inference.c').write_text(code)
    p=(ROOT/'scripts/v2/build_linux_r5_inference.py').read_text().replace('typed200-linux-r5-inference-v1','typed200-linux-r5-calibrated-v1').replace('firmware/typed200_linux_r5_inference','firmware/typed200_linux_r5_calibrated_inference')
    (ROOT/'scripts/v2/build_r5_calibrated_candidate.py').write_text(p)
    p=(ROOT/'scripts/v2/check_linux_r5_heads.py').read_text().replace('typed200-linux-r5-inference-v1','typed200-linux-r5-calibrated-v1').replace('firmware/typed200_linux_r5_inference','firmware/typed200_linux_r5_calibrated_inference')
    p=p.replace('golden.append((logits.tolist(),int(np.argmax(logits*scales))))',f"scores=logits*scales;label=int(np.argmax(scores))\n                if name=='intent.clinc' and 1.0/np.exp(scores-scores.max()).sum() < 0.48:label={oos}\n                golden.append((logits.tolist(),label))")
    p=p.replace('scaled_argmax_labels_match=True','calibrated_labels_match=True').replace('scaled winner labels','dev-calibrated labels')
    (ROOT/'scripts/v2/check_r5_calibrated_heads.py').write_text(p)
    receipt=dict(candidate_only=True,deployed=False,baseline_run_untouched=True,decision_sha256=sha(decision),model_sha256=manifest['sha256'],tau=policy['tau'],oos_index=oos,threshold_tuned_on_current_test=False,encoder_weights_changed=False,classifier_weights_changed=False,improvement='Restore existing development-calibrated OOS rejection inside R5; all non-CLINC labels and integer logits unchanged')
    (BASE/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(f'Prepared R5 CLINC calibration candidate: tau0.48, OOS index{oos}; no board changes')

if __name__=='__main__':main()
