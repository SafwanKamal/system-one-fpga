"""Fault matrix for PL restore admission and exact hardware-observation checks."""
from pathlib import Path
import copy
import argparse
import itertools
import json
from amp_linux_tag_policy import idle,restore_allowed,parse_trace,check_apu,check_r5

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-linux-tag-probe-v1'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);args=ap.parse_args()
    out=BASE/args.attempt;out.mkdir(exist_ok=False);cases=0
    flags=['pinned','reserved','lease_pending','mapped','may_run','loaded','quarantine']
    for values in itertools.product('01',repeat=11):
        status=dict(zip(flags,values[:7]));attempted,quiet,apu,apuquiet=(x=='1' for x in values[7:])
        allowed=restore_allowed(dict(r5_start_attempted=attempted,r5_quiet_proved=quiet,apu_access_attempted=apu,apu_quiet_proved=apuquiet),status)
        assert allowed==(all(x=='0' for x in values[:7]) and (not attempted or quiet) and (not apu or apuquiet));cases+=1
    assert not idle({}) and not restore_allowed({},{});cases+=1
    stopped=dict.fromkeys(flags,'0')
    for state in [{},dict(r5_start_attempted=True,r5_quiet_proved='false'),dict(r5_start_attempted=0,r5_quiet_proved=True)]:
        assert not restore_allowed(state,stopped);cases+=1
    apu=json.loads((ROOT/'build/v2/typed200-amp-deployment-v1/probe-target-v1/apu-observations.json').read_text())
    check_apu(apu);cases+=1
    trace='R5: PASS\nSCTLR=00e50878\nCPSR=000001d3\nMIDR=411fc153\nAR=00010003\nARID=00000055\n'
    snap=dict(magic=0x4f524731,version=1,writes=68,errors=0,slots=copy.deepcopy(apu['cores'][3]['slots']))
    for j in range(4,8):snap['slots'][j]=dict(tag=0x10003,address=0xa0000000+j*4,value=0x52350000+j,metadata=((60+j)<<16)|0x66)
    check_r5(snap,trace,apu);cases+=1
    bad=[]
    for field in ['magic','version','writes','errors']:
        x=copy.deepcopy(snap);x[field]^=1;bad.append((x,trace,apu))
    for j in range(16):
        for field in ['tag','address','value','metadata']:
            x=copy.deepcopy(snap);x['slots'][j][field]^=1;bad.append((x,trace,apu))
    for text in [trace.replace('PASS','WAIT'),trace[:-1],trace.replace('00e50878','00e51878'),
                 trace.replace('000001d3','00000153'),trace.replace('411fc153','411fc143'),
                 trace.replace('00010003','00080000')]:bad.append((snap,text,apu))
    for tag in [c['slots'][0]['tag'] for c in apu['cores']]:
        x=copy.deepcopy(snap)
        for j in range(4,8):x['slots'][j]['tag']=tag
        bad.append((x,trace,apu))
    for tag in [c['ar_tag'] for c in apu['cores']]:
        bad.append((snap,trace.replace('AR=00010003',f'AR={tag:08x}'),apu))
    for x,t,a in bad:
        try:check_r5(x,t,a)
        except (RuntimeError,KeyError):pass
        else:raise AssertionError('Fault accepted')
        cases+=1
    for n in range(len(trace)):
        try:parse_trace(trace[:n])
        except RuntimeError:pass
        else:raise AssertionError('Partial trace accepted')
        cases+=1
    (out/'receipt.json').write_text(json.dumps(dict(passed=True,cases=cases,
        restore_requires_released_r5=True,post_start_restore_requires_complete_quiet_trace=True,
        software_only=True,target_tags_measured=False),indent=2)+'\n')
    print(f'PASS {cases} restore/metadata/schema fault cases')


if __name__=='__main__':main()
