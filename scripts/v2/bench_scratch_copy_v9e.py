"""Time scratch-copy methods on the board's real /dev/mem device mapping.

Writes the package's 1 MB RoPE table to scratch 0x200000-0x300000, which no
runtime uses (RoPE ends at 0x110000 even at 2048 context; the K/V cache starts at
0x400000, so prefix-cache state is never touched), using: the original per-word
'<I' loop, the v9e 64-byte chunked pack_into, and the v9e compare-then-skip path.
Each write is verified by an aligned word readback. No MMIO register access, no
FPGA command; takes the inference lock non-blocking. Writes only --out.
"""
import argparse,fcntl,json,mmap,os,struct,time
from pathlib import Path

BENCH_OFFSET=0x200000
BENCH_END=0x400000   # K/V cache base in every runtime; never cross it


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    if os.geteuid()!=0:raise RuntimeError('Root required')
    rope=(args.package/'rope.bin').read_bytes();count=len(rope)//4;words=struct.unpack('<%dI'%count,rope)
    dt=Path('/sys/firmware/devicetree/base');reserved=list((dt/'reserved-memory').glob('sysone@*'))
    if len(reserved)!=1:raise RuntimeError('Scratch reservation absent')
    base,size=struct.unpack('>QQ',(reserved[0]/'reg').read_bytes())
    if BENCH_OFFSET+len(rope)>BENCH_END or BENCH_END>size:raise RuntimeError('Benchmark area would overlap the K/V cache')
    lock=Path('/run/lock/sysone-inference.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    fd=os.open('/dev/mem',os.O_RDWR|os.O_SYNC);result=dict(bytes=len(rope),offset=hex(BENCH_OFFSET))
    try:
        scratch=mmap.mmap(fd,size,mmap.MAP_SHARED,mmap.PROT_READ|mmap.PROT_WRITE,offset=base)
        def readback():return struct.unpack_from('<%dI'%count,scratch,BENCH_OFFSET)==words
        def chunked(values):
            # Same full-chunk path as runtime_v9e._copy_words for this aligned 1 MB table.
            for start in range(0,count,16):struct.pack_into('<16I',scratch,BENCH_OFFSET+4*start,*values[start:start+16])
        def clear():
            for index in range(count):struct.pack_into('<I',scratch,BENCH_OFFSET+4*index,0)
        for trial in range(3):
            clear();t=time.monotonic()
            for index,value in enumerate(words):struct.pack_into('<I',scratch,BENCH_OFFSET+4*index,value)
            old=time.monotonic()-t;ok_old=readback()
            clear();t=time.monotonic();chunked(words);new=time.monotonic()-t;ok_new=readback()
            t=time.monotonic();present=readback();skip=time.monotonic()-t
            result.setdefault('trials',[]).append(dict(old_loop_ms=old*1000,chunked_64B_ms=new*1000,compare_skip_ms=skip*1000,old_verified=ok_old,new_verified=ok_new,skip_detected=present))
            print(json.dumps(result['trials'][-1]),flush=True)
        # Odd sizes and offsets through the runtime's own _copy_words (the 156-byte
        # page table's tail raised SIGBUS in candidate 4). Verified word by word.
        import sys;sys.path.insert(0,str(args.package/'src'))
        from sysone.v2.qwen_fpga_runtime_v9e import QwenFpga
        class Probe:pass
        probe=Probe();probe.scratch=scratch;copy=QwenFpga._copy_words.__get__(probe)
        cases=[]
        for size,shift in [(4,0),(28,4),(32,0),(44,12),(60,0),(64,0),(68,4),(156,0),(156,4),(1028,8),(4096,0),(4096,36)]:
            payload=os.urandom(size);at=BENCH_OFFSET+(1<<20)+shift;copy(at,payload)
            got=b''.join(struct.pack('<I',struct.unpack_from('<I',scratch,at+4*i)[0]) for i in range(size//4))
            cases.append(dict(bytes=size,offset=hex(at),verified=got==payload));print(json.dumps(cases[-1]),flush=True)
        result['odd_size_cases']=cases
        clear();scratch.close()
        result['passed']=all(t['old_verified'] and t['new_verified'] and t['skip_detected'] for t in result['trials']) and all(c['verified'] for c in result['odd_size_cases'])
    finally:
        os.close(fd);lock.close()
        args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
