"""Fixed-point reference vectors; no frequency/table/model calibration."""
from pathlib import Path
import sys
import numpy as np
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'src'))
from sysone.v2.decoder_reference import rope_int8
out=root/'build/v2/rope-pair';out.mkdir(exist_ok=True)
rng=np.random.default_rng(924);rows=[]
for fraction in range(1,16):
 limit=1<<fraction;corners=[-127,-126,-1,0,1,126,127];tables=[-limit,-limit+1,0,limit-1,limit]
 inputs=[(lo,hi,c,s) for lo in corners for hi in corners for c in tables for s in tables]
 inputs += [tuple(map(int,v)) for v in np.column_stack([rng.integers(-127,128,(2048,2)),rng.integers(-limit,limit+1,(2048,2))])]
 x=np.array([(lo,hi) for lo,hi,c,s in inputs],dtype=np.int64)[:,None,:]
 c=np.array([c for lo,hi,c,s in inputs],dtype=np.int64)[:,None];s=np.array([s for lo,hi,c,s in inputs],dtype=np.int64)[:,None]
 expected=rope_int8(x,c,s,fraction=fraction)[:,0,:]
 rows.extend((*values,fraction,int(result[0]),int(result[1]),0) for values,result in zip(inputs,expected))
rows += [(-128,1,1,0,1,0,0,1),(1,-128,1,0,1,0,0,1),(1,1,3,0,1,0,0,1),(1,1,0,-3,1,0,0,1),(1,1,0,0,0,0,0,1),(1,1,0,0,16,0,0,1)]
(out/'vectors.txt').write_text('\n'.join(' '.join(map(str,r)) for r in rows)+'\n')
print(len(rows),'RoPE corner/random/invalid vectors')
