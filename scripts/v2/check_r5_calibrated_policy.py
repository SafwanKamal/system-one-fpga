"""Validate R5 calibration numerics on development data, without board access."""
from pathlib import Path
import argparse,hashlib,json,struct,subprocess,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/v2/typed200-linux-r5-calibrated-v1'
SOURCE=ROOT/'firmware/typed200_linux_r5_calibrated_inference'
sys.path.insert(0,str(ROOT/'src'))

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    from sysone.v2 import ddr_image
    from sysone.v2.chain_data import load_clinc
    from sysone.v2.wordpiece import WordPiece
    from sysone.v2.host_heads import build_chain
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',default='policy-check-v1');ap.add_argument('--tau',type=float,default=.48);args=ap.parse_args()
    out=BASE/args.attempt;out.mkdir(exist_ok=False)
    cache=ROOT/'logs/oos_cache/minilm-l12-v1_dev.npy'
    cached=np.load(cache);splits,labels=load_clinc();chains=splits['dev'];oos=labels.index('oos')
    assert cached.shape==(3000,151) and len(chains)==3100
    machine=ddr_image.ImageMachine((ROOT/'export/v2/image/minilm-l12-v1-kr260/minilm-l12-v1-kr260.img').read_bytes())
    wp=WordPiece.from_file(ROOT/'export/v2/chain/minilm-l12-v1/tokenizer.json')
    def probability(index):
        c=chains[index];ch=build_chain(wp,[s.words for s in c.segments],'intent',128)
        hidden=machine.hidden(np.asarray(ch.ids));rows=np.asarray([r for r,s in enumerate(ch.seg) if s==0])
        lg,sc=machine.head_logits(hidden,'intent.clinc',rows);z=np.asarray(lg*sc).reshape(-1);e=np.exp(z-z.max())
        return e/e.sum()
    for index in [0,750,1500,2250,2999]:assert np.array_equal(probability(index),cached[index]),index
    complete=BASE/'policy-check-v1/dev-probabilities.npy'
    if args.attempt!='policy-check-v1' and complete.exists():probs=list(np.load(complete))
    else:
        probs=list(cached)
        for index in range(len(cached),len(chains)):
            probs.append(probability(index))
            if (index+1)%10==0:print(f'Development probabilities {index+1}/{len(chains)}',flush=True)
    probs=np.asarray(probs);np.save(out/'dev-probabilities.npy',probs)
    gold=np.asarray([c.segments[0].intent for c in chains]);argmax=probs.argmax(1)
    expected=np.where(probs.max(1)<args.tau,oos,argmax).astype('<u4')
    # Scores are shifted logits. log(p) preserves softmax and its decision.
    scores=np.log(np.maximum(probs,np.finfo(np.float64).tiny)).astype('<f8')
    scores.tofile(out/'scores.bin');argmax.astype('<u4').tofile(out/'winners.bin')
    grid=np.concatenate([np.linspace(-745,0,20001),[-10000,-1000,0]]).astype('<f8');grid.tofile(out/'exp-input.bin')
    host=r'''#include <stdio.h>
#include "clinc_policy.h"
int main(int argc,char **argv){
 if(argc!=7)return 1;
 FILE *scores=fopen(argv[1],"rb"),*winners=fopen(argv[2],"rb"),*out=fopen(argv[3],"wb");
 if(!scores||!winners||!out)return 2;
 double values[151];uint32_t winner;
 while(fread(values,sizeof(double),151,scores)==151){
  if(fread(&winner,4,1,winners)!=1)return 3;
  uint32_t label=calibrated_clinc_label(values,151,winner);
  if(fwrite(&label,4,1,out)!=1)return 4;
 }
 fclose(scores);fclose(winners);fclose(out);
 FILE *in=fopen(argv[4],"rb"),*expout=fopen(argv[5],"wb");if(!in||!expout)return 5;
 double x;while(fread(&x,8,1,in)==1){double y=policy_exp_negative(x);if(fwrite(&y,8,1,expout)!=1)return 6;}
 fclose(in);fclose(expout);return 0;
}
'''
    (out/'policy-host.c').write_text(host)
    def posix(path):return '/mnt/c/'+path.resolve().as_posix()[3:]
    calls=[['gcc','-O2','-Wall','-Wextra','-Werror','-fno-fast-math','-ffp-contract=off','-I',posix(SOURCE),posix(out/'policy-host.c'),'-o',posix(out/'policy-host')],
        [posix(out/'policy-host'),*[posix(out/name) for name in ['scores.bin','winners.bin','labels.bin','exp-input.bin','exp-output.bin']],'unused']]
    for index,command in enumerate(calls):
        p=subprocess.run(['wsl','-d','Ubuntu-24.04','--',*command],capture_output=True,timeout=60)
        (out/f'command-{index}.log').write_bytes(p.stdout+p.stderr);assert p.returncode==0,p.stderr
    actual=np.fromfile(out/'labels.bin',dtype='<u4');assert np.array_equal(actual,expected)
    exponential=np.fromfile(out/'exp-output.bin',dtype='<f8');error=float(np.max(abs(exponential-np.exp(grid))))
    assert error<4e-14 and np.isfinite(exponential).all() and (exponential>=0).all(),error
    ins=gold!=oos
    def rates(pred):return dict(accuracy=float(np.mean(pred==gold)),in_scope_accuracy=float(np.mean(pred[ins]==gold[ins])),oos_recall=float(np.mean(pred[~ins]==oos)),correct=int(sum(pred==gold)),n=len(gold))
    before=rates(argmax);after=rates(actual)
    assert after['accuracy']>before['accuracy'] and before['in_scope_accuracy']-after['in_scope_accuracy']<=.010001
    receipt=dict(passed=True,candidate_only=True,deployed=False,development_cases=len(gold),cached_prefix_cases=len(cached),cached_prefix_sample_checks=5,completed_missing_dev_cases=len(gold)-len(cached),dev_cache_sha256=sha(cache),dev_probabilities_sha256=sha(out/'dev-probabilities.npy'),policy_sha256=sha(SOURCE/'clinc_policy.h'),tau=args.tau,threshold_unchanged_from_existing_policy=args.tau==.48,new_test_labels_used_for_tuning=False,before=before,after=after,changed_predictions=int(sum(actual!=argmax)),maximum_absolute_exp_error=error,all_development_policy_labels_match_numpy=True,interpretation='Offline development replay. This is fitted dev performance, not an independent held-out gain or a board deployment result.')
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2),flush=True)

if __name__=='__main__':main()
