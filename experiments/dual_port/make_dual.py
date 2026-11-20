"""Derive the dual-weight-port decoder source from a single-port source directory.
usage: python make_dual.py SRC_DIR OUT_DIR
- appends matrix_dual.hpp to matrix_q8.hpp;
- replaces matvec with the two-port version (two load_model + unpack_q8, one dual accumulator);
- adds the model_b m_axi port (bundle weights_b) and its control register at 0x70.
"""
import shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
src, out = Path(sys.argv[1]), Path(sys.argv[2])
PACKED = '--packed' in sys.argv
if out.exists():
    shutil.rmtree(out)
shutil.copytree(src, out)
m = (out / 'matrix_q8.hpp').read_bytes()
m += b'\r\n' + (HERE / 'matrix_dual.hpp').read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n').replace(b'#pragma once\r\n', b'')
(out / 'matrix_q8.hpp').write_bytes(m)

p = out / 'qwen_decoder.cpp'
s = p.read_bytes().decode()
a = s.index('static void matvec(weight_word *memory,')
b = s.index('// Contiguous FP32 vector loads')
NEW = r'''// Dual weight port: the row halves stream on two AXI masters into one lockstep core.
static void matvec(weight_word *memory,weight_word *memory_b,uint32_t logical,const ap_uint<256> input[B][F/32],const float scales[B][F/32],float output[B][F],
                   unsigned rows,unsigned cols,unsigned batch,unsigned token_base,bool vocabulary,
                   float maximum[B],uint32_t token[B]) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
    hls::stream<weight_word> words_a("words_a"),words_b("words_b");
    hls::stream<q8_block> blocks_a("blocks_a"),blocks_b("blocks_b");
    hls::stream<matrix_pair<B>> completed("completed");
#pragma HLS STREAM variable=words_a depth=128
#pragma HLS STREAM variable=words_b depth=128
#pragma HLS STREAM variable=blocks_a depth=32
#pragma HLS STREAM variable=blocks_b depth=32
#pragma HLS STREAM variable=completed depth=4
#pragma HLS BIND_STORAGE variable=words_a type=fifo impl=srl
#pragma HLS BIND_STORAGE variable=words_b type=fifo impl=srl
#pragma HLS BIND_STORAGE variable=blocks_a type=fifo impl=srl
#pragma HLS BIND_STORAGE variable=blocks_b type=fifo impl=srl
#pragma HLS BIND_STORAGE variable=completed type=fifo impl=srl
    unsigned half=rows/2;
    unsigned count=(half*(cols/32)*34)/32;
    load_model(memory,logical,count,words_a);
    load_model(memory_b,logical+count*32,count,words_b);
    unpack_q8(words_a,count,blocks_a);
    unpack_q8(words_b,count,blocks_b);
    accumulate_q8_dual@@<B,F>(blocks_a,blocks_b,input,scales,half,cols,batch,completed);
    reduce_q8_dual<B,F>(completed,output,half,batch,token_base,vocabulary,maximum,token);
}
'''.replace('\n', '\r\n')
s = s[:a] + NEW.replace('@@', '_packed' if PACKED else '') + s[b:]
old = 'extern "C" void qwen_decoder(weight_word *model,word *scratch,'
assert s.count(old) == 1
s = s.replace(old, 'extern "C" void qwen_decoder(weight_word *model,weight_word *model_b,word *scratch,')
old = '#pragma HLS INTERFACE m_axi port=model offset=slave bundle=weights depth=67108864 max_read_burst_length=64 num_read_outstanding=8\r\n'
assert s.count(old) == 1
s = s.replace(old, old + '#pragma HLS INTERFACE m_axi port=model_b offset=slave bundle=weights_b depth=67108864 max_read_burst_length=64 num_read_outstanding=8\r\n'
                        '#pragma HLS INTERFACE s_axilite port=model_b bundle=control offset=0x70\r\n')
assert s.count('matvec(model,weights,') == 1
s = s.replace('matvec(model,weights,', 'matvec(model,model_b,weights,')
p.write_bytes(s.encode())
print('wrote', out)
