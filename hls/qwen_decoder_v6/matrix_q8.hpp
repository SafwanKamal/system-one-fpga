#pragma once
// Independent of model layer/head counts. A block is a half scale and 32 Q8s.
// The unpacker reads one AXI word per cycle, emitting one block per 2/3 cycles.
// It removes the old three-read worst-case bound from the arithmetic pipeline.
using q8_block=ap_uint<272>;
static void unpack_q8(hls::stream<word>& input,unsigned words,hls::stream<q8_block>& blocks) {
#pragma HLS INLINE off
    ap_uint<384> window=0;unsigned available=0;
    for(unsigned i=0;i<words;i++) {
#pragma HLS PIPELINE II=1
        window|=ap_uint<384>(input.read())<<(available*8);available+=16;
        if(available>=34) {
            blocks.write(window.range(271,0));window>>=272;available-=34;
        }
    }
}
// An explicit pipelined add avoids tool-dependent zero-cycle FP reductions.
static float q8_add(float a,float b) {
#pragma HLS INLINE off
#pragma HLS PIPELINE II=1
#pragma HLS LATENCY min=4 max=4
    return a+b;
}
template<unsigned TOKENS> struct matrix_partials {float values[TOKENS][8];};
template<unsigned TOKENS,unsigned CAPACITY>
static void accumulate_q8(hls::stream<q8_block>& stream,const float input[TOKENS][CAPACITY],
                          unsigned rows,unsigned cols,unsigned batch,
                          hls::stream<matrix_partials<TOKENS>>& completed) {
#pragma HLS INLINE off
    // A statically addressed eight-register rotation exposes the true eight-block
    // recurrence to HLS. At a row boundary the slots are in original sum order.
    float partial[TOKENS][8]={};
#pragma HLS ARRAY_PARTITION variable=partial complete
    unsigned block=0,row=0;const unsigned blocks=cols/32;
    for(unsigned index=0;index<rows*blocks;index++) {
#pragma HLS PIPELINE II=2
        q8_block weights=stream.read();float scale=half_to_float(weights.range(15,0));
        matrix_partials<TOKENS> result={};
        
        for(unsigned b=0;b<TOKENS;b++) {
#pragma HLS UNROLL
            if(b<batch) {
                float tree[32];
#pragma HLS ARRAY_PARTITION variable=tree complete
                for(unsigned lane=0;lane<32;lane++) {
#pragma HLS UNROLL
                    ap_int<8> w=weights.range(16+lane*8+7,16+lane*8);
                    tree[lane]=float(w.to_int())*input[b][block*32+lane];
                }
                for(unsigned stride=16;stride;stride>>=1) {
#pragma HLS UNROLL
                    for(unsigned lane=0;lane<16;lane++) {
#pragma HLS UNROLL
                        if(lane<stride)tree[lane]+=tree[lane+stride];
                    }
                }
                float update=q8_add(block<8?0.0f:partial[b][0],tree[0]*scale);
                float values[8];
#pragma HLS ARRAY_PARTITION variable=values complete
                for(unsigned i=0;i<7;i++) {
#pragma HLS UNROLL
                    values[i]=partial[b][i+1];partial[b][i]=values[i];
                }
                values[7]=update;partial[b][7]=update;
                if(block+1==blocks) {
                    float ordered[8];
#pragma HLS ARRAY_PARTITION variable=ordered complete
                    for(unsigned i=0;i<8;i++) {
#pragma HLS UNROLL
                        ordered[i]=values[(i+7-(block&7))&7];
                    }
                    for(unsigned i=0;i<8;i++) {
#pragma HLS UNROLL
                        result.values[b][i]=ordered[i];
                    }
                }
            }
        }
        if(block+1==blocks){completed.write(result);block=0;row++;}else block++;
    }
}

template<unsigned TOKENS,unsigned CAPACITY>
static void reduce_q8(hls::stream<matrix_partials<TOKENS>>& completed,float output[TOKENS][CAPACITY],
                      unsigned rows,unsigned batch,unsigned token_base,bool vocabulary,
                      float &maximum,uint32_t &token) {
#pragma HLS INLINE off
    float local_max=maximum;uint32_t local_token=token;
    for(unsigned row=0;row<rows;row++) {
#pragma HLS PIPELINE II=16
        matrix_partials<TOKENS> values=completed.read();
        for(unsigned b=0;b<TOKENS;b++) {
#pragma HLS UNROLL
            if(b<batch) {
                float a0=q8_add(values.values[b][0],values.values[b][1]);
                float a1=q8_add(values.values[b][2],values.values[b][3]);
                float a2=q8_add(values.values[b][4],values.values[b][5]);
                float a3=q8_add(values.values[b][6],values.values[b][7]);
                float c0=q8_add(a0,a1);float c1=q8_add(a2,a3);
                float sum=q8_add(c0,c1);
                if(vocabulary && b==0) {
                    if(sum>local_max || (sum==local_max && token_base+row<local_token)) {
                        local_max=sum;local_token=token_base+row;
                    }
                } else if(!vocabulary && row<CAPACITY)output[b][row]=sum;
            }
        }
    }
    maximum=local_max;token=local_token;
}
template<unsigned TOKENS,unsigned CAPACITY>
static void compute_q8(hls::stream<q8_block>& stream,const float input[TOKENS][CAPACITY],
                       float output[TOKENS][CAPACITY],unsigned rows,unsigned cols,
                       unsigned batch,unsigned token_base,bool vocabulary,float &maximum,uint32_t &token) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
    hls::stream<matrix_partials<TOKENS>> completed("completed");
#pragma HLS STREAM variable=completed depth=4
#pragma HLS BIND_STORAGE variable=completed type=fifo impl=srl
    accumulate_q8<TOKENS,CAPACITY>(stream,input,rows,cols,batch,completed);
    reduce_q8<TOKENS,CAPACITY>(completed,output,rows,batch,token_base,vocabulary,maximum,token);
}
