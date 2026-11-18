"""Replay newly measured A53 source metadata through the frozen candidate filter."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-deployment-v1'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);args=ap.parse_args()
    assert re.fullmatch(r'apu-tag-replay-v[0-9]+',args.attempt)
    out=BASE/args.attempt;out.mkdir(exist_ok=False)
    (out/'runner.py').write_bytes(Path(__file__).read_bytes())
    old=ROOT/'build/v2/typed200-amp-candidate-v1/filter-sim-v1'
    old_receipt=json.loads((old/'receipt.json').read_text());assert old_receipt['passed']
    rtl=ROOT/'rtl/v2/candidates/typed200_amp/control/typed200_requester_filter.sv'
    assert hashlib.sha256(rtl.read_bytes()).hexdigest()==old_receipt['rtl_sha256']
    (out/rtl.name).write_bytes(rtl.read_bytes())
    observations=BASE/'probe-target-v1/apu-observations.json'
    a=json.loads(observations.read_text());assert a['passed'] and a['writes']==64 and a['errors']==0
    tb=(old/'tb.sv').read_text()
    marker=' $display("PASS filter:'
    assert tb.count(marker)==1
    cases=[]
    for core in a['cores']:
        tag=core['ar_tag']
        cases.append(f" reset_all();rd({tag&65535},40'ha0000018,0,2,1,0,{tag>>16},0);")
        # Also test a secure-bit mutation: measured MID must still exclude the APU.
        cases.append(f" reset_all();rd({tag&65535},40'ha0000018,0,2,1,0,0,0);")
        for slot in core['slots']:
            tag=slot['tag'];addr=slot['address']
            cases.append(f" reset_all();wr({tag&65535},40'h{addr:x},0,2,1,0,{tag>>16},16'hf,0,0);")
            cases.append(f" reset_all();wr({tag&65535},40'h{addr:x},0,2,1,0,0,16'hf,0,0);")
    tb=tb.replace(marker,'\n'.join(cases)+'\n'+marker)
    (out/'tb.sv').write_text(tb)
    commands=[['C:/iverilog/bin/iverilog.exe','-g2012','-s','tb','-o',str(out/'sim.vvp'),str(out/rtl.name),str(out/'tb.sv')],['C:/iverilog/bin/vvp.exe',str(out/'sim.vvp')]]
    for i,cmd in enumerate(commands):
        r=subprocess.run(cmd,cwd=ROOT,capture_output=True,timeout=120)
        (out/('compile.log' if i==0 else 'run.log')).write_bytes(r.stdout+r.stderr)
        assert r.returncode==0,(i,r.stderr[-2000:])
    assert b'PASS filter:' in (out/'run.log').read_bytes()
    result=dict(passed=True,additional_rejected_transactions=len(cases),measured_transactions=68,
      secure_bit_mutations=68,observations_sha256=hashlib.sha256(observations.read_bytes()).hexdigest(),
      rtl_sha256=old_receipt['rtl_sha256'],r5_target_qualified=False,
      limits=['Measured APU traces only; not exhaustive future APU attributes or active protection on the target',
              'R5 source tags, integration before USER loss, and all control-path bypasses remain target gates'])
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print((out/'run.log').read_text());print('Additional measured/mutated source cases:',len(cases))
if __name__=='__main__':main()
