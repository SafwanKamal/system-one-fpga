"""One real-weight, two-token FPGA block fixture before full decoder execution."""
import argparse,fcntl,json,math,struct,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.qwen_fpga_runtime_v1 import QwenFpga

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True);args=ap.parse_args()
    package=args.package;started=time.monotonic();out=package/'hardware-block-smoke.json'
    result=dict(passed=False,backend='FPGA',cases=[])
    lock=Path('/run/lock/sysone-inference.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX);engine=None
    try:
        engine=QwenFpga(package)
        for pos,token in enumerate([151644,8948]):
            raw=engine.block_fixture(token,pos);(package/f'hardware-block-{pos}.bin').write_bytes(raw)
            actual=struct.unpack('<1024f',raw);expected=struct.unpack('<1024f',(package/f'expected-{pos}.bin').read_bytes())
            errors=[abs(a-b) for a,b in zip(actual,expected)]
            record=dict(position=pos,input_token=token,max_absolute_error=max(errors),rmse=math.sqrt(sum(e*e for e in errors)/1024))
            result['cases'].append(record)
            print(json.dumps(record),flush=True)
            if not all(math.isfinite(a) for a in actual) or max(errors)>0.002:raise RuntimeError('FPGA first-layer fixture differs from independent Q8 reference')
        result.update(passed=True,clock_hz=engine.clock_hz,model_verify_ms=engine.model_verify_ms)
    except Exception as exc:result['error']=type(exc).__name__+': '+str(exc);raise
    finally:
        if engine is not None:engine.close()
        lock.close();result['elapsed_seconds']=time.monotonic()-started;out.write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
