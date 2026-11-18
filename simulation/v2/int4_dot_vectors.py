"""Generate independent packed-weight/reference-sum vectors for the RTL primitive."""
import argparse
from pathlib import Path
import sys
import json
import hashlib
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.int4_reference import pack,matvec

def main():
    ap=argparse.ArgumentParser();ap.add_argument('output',type=Path)
    output=ap.parse_args().output;output.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(5318)
    rows=[]
    def add(x,w,*,raw_edge=False):
        packed=pack(w)
        result=sum(int(a)*int(b) for a,b in zip(x,w)) if raw_edge else int(matvec(x,packed,1,16)[0])
        assert -32768<=result<=32767
        a=int.from_bytes(np.asarray(x,dtype=np.int8).tobytes(),'little')
        b=int.from_bytes(packed,'little')
        rows.append(f'{((result&65535)<<192)|(a<<64)|b:052x}')
    # A known noncommutative nibble-order example: -8*1 + 7*2 - 1*3 = 3.
    add(np.array([1,2,3]+[0]*13),np.array([-8,7,-1]+[0]*13))
    for a in range(-127,128):
        for w in range(-8,8):add(np.full(16,a),np.full(16,w))
    for _ in range(2048):add(rng.integers(-127,128,16),rng.integers(-8,8,16))
    # Raw signed-byte -128 is a hardware width edge; model reference rejects it.
    for w in range(-8,8):add(np.full(16,-128),np.full(16,w),raw_edge=True)
    text='\n'.join(rows)+'\n';(output/'vectors.mem').write_text(text,newline='\n')
    (output/'vectors.json').write_text(json.dumps({'cases':len(rows),'seed':5318,
        'format':'expected signed16, activations128, packed weights64; low-first nibble',
        'raw_int8_minus128_cases':16,'vector_sha256':hashlib.sha256((output/'vectors.mem').read_bytes()).hexdigest()},indent=2)+'\n')
    print(f'Generated {len(rows)} independent INT4 vectors')

if __name__=='__main__':main()
