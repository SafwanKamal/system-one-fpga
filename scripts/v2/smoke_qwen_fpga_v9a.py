"""v9a causal hardware checks against the exact-order v9a reference, plus a bounded
per-position decode-layer timing microbenchmark. Writes only to --out."""
import argparse,fcntl,json,math,struct,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.qwen_fpga_runtime_v9a import QwenFpga,DESCRIPTOR,OUTPUT
TOLERANCE=0.00002
CASES=[]


def compare(engine,expected_path,record):
    raw=bytes(engine.scratch[OUTPUT:OUTPUT+engine.hidden*4])
    actual=struct.unpack('<'+str(engine.hidden)+'f',raw);expected=struct.unpack('<'+str(engine.hidden)+'f',expected_path.read_bytes())
    errors=[abs(a-b) for a,b in zip(actual,expected)]
    record.update(max_absolute_error=max(errors),rmse=math.sqrt(sum(e*e for e in errors)/engine.hidden),finite=all(math.isfinite(a) for a in actual))
    CASES.append(record);print(json.dumps(record),flush=True)
    if not record['finite'] or record['max_absolute_error']>TOLERANCE:raise RuntimeError('FPGA output differs from causal reference: '+json.dumps(record))


def prefill(engine,ids,start,count):
    engine._copy_words(0x2100,struct.pack('<'+'I'*count,*[engine.manifest['embedding']+ids[start+b]*engine.embedding_row_bytes for b in range(count)]))
    engine.command(7,page=0x2100,rows=count,position=start)
    engine._copy_words(DESCRIPTOR,struct.pack('<11I',*engine.manifest['layer_offsets'][0]))
    engine.command(8,page=DESCRIPTOR,rows=count,layer=0,position=start)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();package=args.package;args.out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();result=dict(passed=False,backend='FPGA v9a',tolerance=TOLERANCE,cases=CASES,timing=[])
    lock=Path('/run/lock/sysone-inference.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);engine=None
    try:
        engine=QwenFpga(package)
        block=package/'block-fixture';ids=json.loads((block/'manifest.json').read_text())['ids']
        for start,count in [(0,8),(0,1),(1,7)]:
            prefill(engine,ids,start,count)
            for lane in range(count):
                engine.command(10,layer=lane)
                compare(engine,block/f'expected-{start+lane}.bin',dict(fixture='block',mode='prefill',position=start+lane,batch_tokens=count,lane=lane))
        long=package/'long-fixture';ids=json.loads((long/'manifest.json').read_text())['ids']
        for start in range(0,len(ids),8):
            count=min(8,len(ids)-start);prefill(engine,ids,start,count)
            for lane in range(count):
                engine.command(10,layer=lane)
                compare(engine,long/f'expected-{start+lane}.bin',dict(fixture='long',mode='prefill',position=start+lane,batch_tokens=count,lane=lane))
        for position,token in enumerate(ids):
            engine.command(1,page=engine.manifest['embedding']+token*engine.embedding_row_bytes,position=position)
            engine._copy_words(DESCRIPTOR,struct.pack('<11I',*engine.manifest['layer_offsets'][0]))
            engine.command(2,page=DESCRIPTOR,layer=0,position=position);engine.command(5)
            compare(engine,long/f'expected-{position}.bin',dict(fixture='long',mode='decode',position=position))
        # Timing only: positions past the fixture attend over stale cache rows,
        # so their outputs are not compared. Each call is one layer-0 decode.
        for position in [39,63,127,191,255]:
            samples=[]
            for _ in range(3):
                engine.command(1,page=engine.manifest['embedding']+ids[0]*engine.embedding_row_bytes,position=position)
                engine._copy_words(DESCRIPTOR,struct.pack('<11I',*engine.manifest['layer_offsets'][0]))
                before=engine.command_timing.get('2',dict(seconds=0.0))['seconds']
                engine.command(2,page=DESCRIPTOR,layer=0,position=position)
                samples.append(engine.command_timing['2']['seconds']-before)
            result['timing'].append(dict(command=2,layer=0,position=position,seconds=samples))
            print(json.dumps(result['timing'][-1]),flush=True)
        result.update(passed=True,clock_hz=engine.clock_hz,memory_clock_hz=engine.memory_clock_hz,model_verify_ms=engine.model_verify_ms,model_verify_method=engine.model_verify_method)
    except Exception as exc:result['error']=type(exc).__name__+': '+str(exc);raise
    finally:
        if engine is not None:engine.close()
        lock.close();result['elapsed_seconds']=time.monotonic()-started
        if result['cases']:result['worst_max_absolute_error']=max(c['max_absolute_error'] for c in result['cases'])
        (args.out/'hardware-smoke.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
