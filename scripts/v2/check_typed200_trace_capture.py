"""Offline diagnostic trace review; never opens live target memory."""
from pathlib import Path
import argparse,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.typed200_capture import ExpectedCapture
from sysone.v2.typed200_trace import assess_trace
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--trace',type=Path,required=True)
    ap.add_argument('--expected',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args()
    raw=a.trace.read_bytes();expect=a.expected.read_bytes()
    fields=json.loads(expect);fields['token_ids']=tuple(fields['token_ids'])
    result=assess_trace(raw,ExpectedCapture(**fields))
    result['input_sha256']={'trace':hashlib.sha256(raw).hexdigest(),
                            'expected':hashlib.sha256(expect).hexdigest()}
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print('PASS offline pre-ACK trace consistency; no target timing certification')
if __name__=='__main__':main()
