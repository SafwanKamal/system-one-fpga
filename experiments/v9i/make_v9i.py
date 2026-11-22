"""Derive the v9i decoder source: the D3 full dual weight port design with P=2 attention.
usage: python make_v9i.py [ROOT]   (ROOT = source checkout, default S:/)
- input  build/v2/dual-port-study/src-d3 (v9g + merged q/k RMS call site + full dual weight port,
         slot-pair DSP packing, static reorder; docs/research/2026-11-19-dual-weight-port-study.md)
- output build/v2/v9i/src
- patch: attention serves two tokens per pass over the on-chip K/V tile instead of four
         (exact by construction: each token keeps its own state and operation order; see
         docs/research/2026-11-21-attention-reclaim.md)
- check: the s_axilite CSR map equals v9h's (build/v2/dual-port-study/src-s2), so the runtime's
         v9h registers.json override applies unchanged.
"""
import re, shutil, sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else 'S:/')
src, out, v9h = (root / 'build/v2/dual-port-study/src-d3', root / 'build/v2/v9i/src',
                 root / 'build/v2/dual-port-study/src-s2')
if out.exists():
    shutil.rmtree(out)
shutil.copytree(src, out)
p = out / 'qwen_decoder.cpp'
s = p.read_bytes().decode()
old, new = 'static const unsigned TILE=256,P=4;', 'static const unsigned TILE=256,P=2;'
if s.count(old) != 1:
    raise SystemExit('patch point count %d != 1' % s.count(old))
p.write_bytes(s.replace(old, new).encode())

csr = lambda text: re.findall(r'port=(\w+) bundle=control offset=(0x[0-9a-fA-F]+)', text)
mine, ref = csr(p.read_text()), csr((v9h / 'qwen_decoder.cpp').read_text())
if sorted(mine) != sorted(ref):
    raise SystemExit('CSR map differs from v9h:\n v9i %s\n v9h %s' % (sorted(mine), sorted(ref)))
print(out)
print('CSR map identical to v9h:', ', '.join('%s@%s' % kv for kv in sorted(ref, key=lambda kv: int(kv[1], 16))))
