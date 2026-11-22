"""Derive an attention-reclaim variant of the v9h decoder source.
usage: python make_attn.py SRC_DIR OUT_DIR VARIANT[+VARIANT...]
SRC_DIR is v9h (build/v2/dual-port-study/src-s2). Every variant keeps each token's floating-point
operations and their order unchanged, so outputs are bit-identical by construction:
  p2   two token lanes per attention pass instead of four (P=4 -> P=2). Each token keeps its own
       count, max, sum and accumulator, so only the schedule changes; passes of 3-8 tokens make two
       passes over the on-chip K/V tile instead of one. Halves the FP pool of the score/value loops.
  aux  relax the per-tile helper loops that do not set the throughput (accumulator rescale and
       output normalisation, 16-32 iterations per tile) from II=1 to II=4, so they need a quarter
       of the multipliers at their peak and add fewer sources to the shared operator muxes.
  lim  cap attention's FP multipliers/adders at the count one score or value iteration needs
       (ALLOCATION), so helper loops cannot widen the shared pool.
  bram move query / acc / run_acc storage from LUTRAM to block RAM.
  tmx  time-multiplex the P x 2 lanes of the scale/max and exp/mass loops (II = P*2): one lane
       per cycle shares one multiplier, comparator, expf and adder; per-lane order is unchanged.
"""
import shutil, sys
from pathlib import Path

src, out, variants = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3].split('+')
KNOWN = ('base', 'p2', 'aux', 'lim', 'bram', 'tmx')
for v in variants:
    if v not in KNOWN:
        raise SystemExit('unknown variant %r (known: %s)' % (v, ', '.join(KNOWN)))
if out.exists():
    shutil.rmtree(out)
out.mkdir(parents=True)
for f in ('qwen_decoder.cpp', 'matrix_q8.hpp', 'model_profile.hpp'):
    shutil.copyfile(src / f, out / f)
crlf = b'\r\n' in (out / 'qwen_decoder.cpp').read_bytes()
NL = '\r\n' if crlf else '\n'
fix = lambda s: s.replace('\r\n', '\n').replace('\n', NL)
s = (out / 'qwen_decoder.cpp').read_text(newline='')


def sub(old, new, count=1):
    global s
    old, new = fix(old), fix(new)
    if s.count(old) != count:
        raise SystemExit('patch point count %d != %d: %r' % (s.count(old), count, old[:80]))
    s = s.replace(old, new)


if 'p2' in variants:
    # B % P == 0 still holds (B=8). run_* state is indexed [slot/P][slot%P], so every slot keeps
    # its own carried state; the b0 loop steps by 2 and visits each slot exactly once per tile.
    sub('static const unsigned TILE=256,P=4;', 'static const unsigned TILE=256,P=2;')

if 'aux' in variants:
    # Accumulator rescale at the start of each tile (16 iterations).
    sub('''                for(unsigned c=0;c<HD/8;c++) {
#pragma HLS PIPELINE II=1
                    for(unsigned p=0;p<P;p++)for(unsigned g=0;g<2;g++) {
#pragma HLS UNROLL
                        word carried=run_acc''', '''                for(unsigned c=0;c<HD/8;c++) {
#pragma HLS PIPELINE II=4
                    for(unsigned p=0;p<P;p++)for(unsigned g=0;g<2;g++) {
#pragma HLS UNROLL
                        word carried=run_acc''')
    # Output normalisation for a token's last tile (32 iterations, 8 multiplies each).
    sub('''                        for(unsigned g=0;g<2;g++)for(unsigned c=0;c<HD/8;c++) {
#pragma HLS PIPELINE II=1
                            word w=acc[p][g][c];''', '''                        for(unsigned g=0;g<2;g++)for(unsigned c=0;c<HD/8;c++) {
#pragma HLS PIPELINE II=4
                            word w=acc[p][g][c];''')

if 'bram' in variants:
    # Query, tile accumulator and carried accumulator from LUTRAM to block RAM (storage only).
    for v in ('run_acc', 'query', 'acc'):
        sub('#pragma HLS BIND_STORAGE variable=%s type=ram_s2p impl=lutram' % v,
            '#pragma HLS BIND_STORAGE variable=%s type=ram_s2p impl=bram' % v)

if 'tmx' in variants:
    # Scale/max and exp/mass loops: one (token, head) lane per cycle (II = P*2), so one fmul, one
    # fcmp, one fexp and one fadd serve all lanes in the same per-lane order.
    head = '''                for(unsigned s=0;s<longest;s++) {
#pragma HLS PIPELINE
                    for(unsigned p=0;p<P;p++)for(unsigned g=0;g<2;g++) {'''
    sub(head, head.replace('#pragma HLS PIPELINE', '#pragma HLS PIPELINE II=%d' % (2 * (2 if 'p2' in variants else 4))), 2)

if 'lim' in variants:
    # One score or value iteration needs P tokens x 2 heads x 8 lanes multiplies and adds.
    lanes = (2 if 'p2' in variants else 4) * 2 * 8
    sub('''static void attention(word *memory,unsigned layer,unsigned first,uint32_t cache,unsigned batch) {
#pragma HLS INLINE off''', '''static void attention(word *memory,unsigned layer,unsigned first,uint32_t cache,unsigned batch) {
#pragma HLS INLINE off
#pragma HLS ALLOCATION operation instances=fmul limit=%d
#pragma HLS ALLOCATION operation instances=fadd limit=%d''' % (lanes, lanes))

(out / 'qwen_decoder.cpp').write_text(s, newline='')
print(out)
