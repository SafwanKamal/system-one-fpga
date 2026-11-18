"""Check four FPGA batch lanes and a partial causal group with real Q8 weights."""
import argparse,fcntl,json,math,struct,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.qwen_fpga_runtime_v5 import QwenFpga,DESCRIPTOR,OUTPUT

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True);args=ap.parse_args()
    package=args.package;started=time.monotonic();result=dict(passed=False,backend='FPGA',cases=[])
    lock=Path('/run/lock/sysone-inference.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX);engine=None
    try:
        engine=QwenFpga(package);ids=json.loads((package/'fixture-manifest.json').read_text())['ids']
        if len(ids)!=4:raise ValueError('Four-token fixture required')
        for start,count in [(0,4),(0,1),(1,3)]:
            engine._copy_words(0x2100,struct.pack('<'+'I'*count,*[engine.manifest['embedding']+ids[start+b]*engine.embedding_row_bytes for b in range(count)]))
            engine.command(7,page=0x2100,rows=count,position=start)
            engine._copy_words(DESCRIPTOR,struct.pack('<11I',*engine.manifest['layer_offsets'][0]))
            engine.command(8,page=DESCRIPTOR,rows=count,layer=0,position=start)
            for lane in range(count):
                engine.command(10,layer=lane)
                raw=bytes(engine.scratch[OUTPUT:OUTPUT+engine.hidden*4]);(package/f'hardware-batch-{start}-{count}-{lane}.bin').write_bytes(raw)
                actual=struct.unpack('<'+str(engine.hidden)+'f',raw);expected=struct.unpack('<'+str(engine.hidden)+'f',(package/f'expected-{start+lane}.bin').read_bytes())
                errors=[abs(a-b) for a,b in zip(actual,expected)]
                record=dict(position=start+lane,batch_tokens=count,lane=lane,max_absolute_error=max(errors),rmse=math.sqrt(sum(e*e for e in errors)/engine.hidden));result['cases'].append(record)
                print(json.dumps(record),flush=True)
                if not all(math.isfinite(a) for a in actual) or max(errors)>0.002:raise RuntimeError('FPGA batch differs from causal reference')
        result.update(passed=True,clock_hz=engine.clock_hz,model_verify_ms=engine.model_verify_ms)
    except Exception as exc:result['error']=type(exc).__name__+': '+str(exc);raise
    finally:
        if engine is not None:engine.close()
        lock.close();result['elapsed_seconds']=time.monotonic()-started;(package/'hardware-block-smoke.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
