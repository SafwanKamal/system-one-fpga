"""Derive the S1 (split small passes) decoder source from the v9g source directory.
usage: python make_split.py SRC_DIR OUT_DIR
- appends matrix_split.hpp to matrix_q8.hpp;
- quantize_activation duplicates token t into slot t+B/2 when dup (batch<=B/2, cols%512==0);
- matvec streams row halves on two masters into one accumulator when split (dup and rows even);
- adds the model_b m_axi port (bundle weights_b, control offset 0x70). The host must write the
  model buffer address to 0x70/0x74 as well as 0x10/0x14.
"""
import shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
src, out = Path(sys.argv[1]), Path(sys.argv[2])
if out.exists():
    shutil.rmtree(out)
out.mkdir(parents=True)
for f in ('qwen_decoder.cpp', 'matrix_q8.hpp', 'model_profile.hpp'):
    shutil.copyfile(src / f, out / f)
crlf = b'\r\n' in (out / 'qwen_decoder.cpp').read_bytes()
NL = '\r\n' if crlf else '\n'
fix = lambda s: s.replace('\r\n', '\n').replace('\n', NL)

m = (out / 'matrix_q8.hpp').read_text(newline='')
m += NL + fix((HERE / 'matrix_split.hpp').read_text())
(out / 'matrix_q8.hpp').write_text(m, newline='')

s = (out / 'qwen_decoder.cpp').read_text(newline='')


def sub(old, new, count=1):
    global s
    old, new = fix(old), fix(new)
    if s.count(old) != count:
        raise SystemExit('patch point count %d != %d: %r' % (s.count(old), count, old[:80]))
    s = s.replace(old, new)


LOADB = '''// S1: port-b loader with a private page-table copy, so the two concurrent loaders do not
// force dataflow channels for the 64 shared page registers.
static void load_model_b(weight_word *memory,uint32_t logical,unsigned words,hls::stream<weight_word>& stream) {
#pragma HLS INLINE off
    unsigned done=0;
    while(done<words) {
        uint32_t offset=logical&((1u<<CHUNK_BITS)-1);
        unsigned count=((1u<<CHUNK_BITS)-offset)>>5;
        if(count>words-done)count=words-done;
        uint32_t address=(model_pages_b[logical>>CHUNK_BITS]+offset)>>5;
        for(unsigned i=0;i<count;i++) {
#pragma HLS PIPELINE II=1
            stream.write(memory[address+i]);
        }
        done+=count;logical+=count*32;
    }
}
'''
sub('static uint32_t model_pages[64];\n', 'static uint32_t model_pages[64],model_pages_b[64];\n')
sub('#pragma HLS ARRAY_PARTITION variable=model_pages complete\n',
    '#pragma HLS ARRAY_PARTITION variable=model_pages complete\n#pragma HLS ARRAY_PARTITION variable=model_pages_b complete\n')
sub('for(unsigned i=0;i<rows;i++)model_pages[i]=loadu(scratch,page+4*i);',
    'for(unsigned i=0;i<rows;i++){model_pages[i]=loadu(scratch,page+4*i);model_pages_b[i]=model_pages[i];}')
sub('#include "matrix_q8.hpp"\n', LOADB + '#include "matrix_q8.hpp"\n')
sub('static void quantize_activation(unsigned input,unsigned cols,unsigned batch) {',
    'static void quantize_activation(unsigned input,unsigned cols,unsigned batch,bool dup) {')
sub('qscales[bb][k]=scale;inverse[bb*(F/32)+k]=scale==0?0.0f:1.0f/scale;',
    'qscales[bb][k]=scale;if(dup)qscales[bb+B/2][k]=scale;inverse[bb*(F/32)+k]=scale==0?0.0f:1.0f/scale;')
sub('            quantized[b][block]=word;\n',
    '            quantized[b][block]=word;if(dup)quantized[b+B/2][block]=word;\n')
a = s.index('static void matvec(weight_word *memory,')
b = s.index('// Contiguous FP32 vector loads')
NEW = '''// S1: passes of at most B/2 tokens stream the two row halves on two masters into the
// idle slot datapaths (matrix_split.hpp); larger passes use port a only, as in v9g.
static void matvec(weight_word *memory,weight_word *memory_b,uint32_t logical,const ap_uint<256> input[B][F/32],const float scales[B][F/32],float output[B][F],
                   unsigned rows,unsigned cols,unsigned batch,bool split,unsigned token_base,bool vocabulary,
                   float maximum[B],uint32_t token[B]) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
    hls::stream<weight_word> words_a("words_a"),words_b("words_b");
    hls::stream<q8_block> blocks_a("blocks_a"),blocks_b("blocks_b");
    hls::stream<matrix_partials<B>> completed("completed");
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
    unsigned part=split?rows/2:rows;
    unsigned count=(part*(cols/32)*34)/32;
    load_model(memory,logical,count,words_a);
    load_model_b(memory_b,logical+count*32,split?count:0,words_b);
    unpack_q8(words_a,count,blocks_a);
    unpack_q8(words_b,split?count:0,blocks_b);
    accumulate_q8_split<B,F>(blocks_a,blocks_b,input,scales,part,cols,batch,split,completed);
    reduce_q8_split<B,F>(completed,output,part,batch,split,token_base,vocabulary,maximum,token);
}
'''
s = s[:a] + fix(NEW) + s[b:]
sub('extern "C" void qwen_decoder(weight_word *model,word *scratch,',
    'extern "C" void qwen_decoder(weight_word *model,weight_word *model_b,word *scratch,')
old = '#pragma HLS INTERFACE m_axi port=model offset=slave bundle=weights depth=67108864 max_read_burst_length=64 num_read_outstanding=8\n'
sub(old, old + '#pragma HLS INTERFACE m_axi port=model_b offset=slave bundle=weights_b depth=67108864 max_read_burst_length=64 num_read_outstanding=8\n'
               '#pragma HLS INTERFACE s_axilite port=model_b bundle=control offset=0x70\n')
sub('            if(!(decoder&&(op==1||op==2||op==5)))quantize_activation(input,columns,batch);\n'
    '            matvec(model,weights,quantized,qscales,dotoutput,outputs,columns,batch,token_base,!decoder,best_logit,best_token);\n',
    '            bool dup=batch<=B/2 && columns%512==0;\n'
    '            bool split=dup && outputs%2==0;\n'
    '            if(!(decoder&&(op==1||op==2||op==5)))quantize_activation(input,columns,batch,dup);\n'
    '            matvec(model,model_b,weights,quantized,qscales,dotoutput,outputs,columns,batch,split,token_base,!decoder,best_logit,best_token);\n')
(out / 'qwen_decoder.cpp').write_text(s, newline='')
print('wrote', out)
