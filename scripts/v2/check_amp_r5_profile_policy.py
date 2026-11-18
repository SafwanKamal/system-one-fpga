"""Test the new workload validator without revising the sealed failed trial."""
from copy import deepcopy
from pathlib import Path
import hashlib,json
from amp_r5_profile_policy import review
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-r5-profile-filter-v1'

def main():
    out=BASE/'policy-check-v1';out.mkdir(exist_ok=False)
    source=ROOT/'build/v2/typed200-amp-linux-tag-probe-v1/target-trial-v2/collection-v1/collect.stdout'
    d=json.loads(source.read_text());snap=json.loads(d['pl-snapshot.json'])
    apu=json.loads(d['apu-observations.json']);trace=d['r5-trace.txt']
    result=review(snap,trace,apu);checks=1;rejections=0
    def rejected(s,t=trace):
        nonlocal checks,rejections
        try:review(s,t,apu)
        except RuntimeError:rejections+=1
        else:raise AssertionError('Invalid observation admitted')
        checks+=1
    for j in range(4,8):
        # IDs may repeat, vary or span 16 bits; all admitted without identity inference.
        for ident in [0,1,73,105,137,169,65535]:
            s=deepcopy(snap);s['slots'][j]['metadata']=(60+j)<<16|ident
            assert review(s,trace,apu)['passed'];checks+=1
        for user in range(65536):
            if user in (0x2000,0x2800):continue
            s=deepcopy(snap);s['slots'][j]['tag']=0x10000|user;rejected(s)
        for prot in range(8):
            if prot==1:continue
            s=deepcopy(snap);s['slots'][j]['tag']=prot<<16|0x2000;rejected(s)
        for field,bad in [('metadata',-1),('metadata',1<<32),('metadata',0),
                          ('tag',True),('tag',-1),('value',0),('address',0xa0001000)]:
            s=deepcopy(snap);s['slots'][j][field]=bad;rejected(s)
    for j in [0,3,8,15]:
        s=deepcopy(snap);s['slots'][j]['value']^=1;rejected(s)
    for field,bad in [('magic',0),('version',2),('writes',67),('errors',1)]:
        s=deepcopy(snap);s[field]=bad;rejected(s)
    for changed in [trace.replace('R5: PASS','R5: WAIT'),trace[:-1],
                    trace.replace('AR=00012000','AR=00012400'),
                    trace.replace('AR=00012000','AR=00022000')]:rejected(snap,changed)
    (out/'observation.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'receipt.json').write_text(json.dumps(dict(passed=True,cases=checks,rejections=rejections,
        observations_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        original_trial_reclassified=False,source_path_qualified=False,
        validator_scope='Captured workload integrity and narrow profile only'),indent=2)+'\n')
    print(f'PASS {checks} workload validator cases; original failed qualification unchanged')

if __name__=='__main__':main()
