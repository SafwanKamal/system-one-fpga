"""Offline review of a timed trace and its committed PMU evidence."""
from pathlib import Path
import argparse,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.typed200_capture import ExpectedCapture
from sysone.v2.typed200_timed import assess_timed_trace
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ('trace','pmu','expected','output'):ap.add_argument('--'+n,type=Path,required=True)
    a=ap.parse_args();raw={k:getattr(a,k).read_bytes() for k in ('trace','pmu','expected')}
    fields=json.loads(raw['expected']);fields['token_ids']=tuple(fields['token_ids'])
    r=assess_timed_trace(raw['trace'],raw['pmu'],ExpectedCapture(**fields))
    r['input_sha256']={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
    with a.output.open('x',encoding='utf-8') as f:json.dump(r,f,indent=2);f.write('\n')
    print('PASS conditional timed-trace consistency; no frequency/ownership/WCET certification')
if __name__=='__main__':main()
