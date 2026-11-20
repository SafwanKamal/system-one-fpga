// Split mode (S1): when a pass has at most TOKENS/2 tokens, rows [0,R/2) stream on port a
// into slots 0..TOKENS/2-1 and rows [R/2,R) stream on port b into slots TOKENS/2..TOKENS-1.
// quantize_activation duplicates token t's quantized input and scales into slot t+TOKENS/2,
// so every slot runs the unchanged single-row arithmetic (products, integer tree, two FP
// scalings, eight-register rotation, ordered final tree). Requires rows even and
// cols%512==0 (each half is whole 32-byte words); otherwise the single-port path runs.
// The vocabulary argmax keeps one running best per slot and merges slot t+TOKENS/2 into
// slot t with the same rule (larger value; on equality the smaller index), which equals
// the single-port row-order scan for finite values.
template<unsigned TOKENS,unsigned CAPACITY>
static void accumulate_q8_split(hls::stream<q8_block>& stream_a,hls::stream<q8_block>& stream_b,
                                const ap_uint<256> input[TOKENS][CAPACITY/32],const float scales[TOKENS][CAPACITY/32],
                                unsigned rows,unsigned cols,unsigned batch,bool split,
                                hls::stream<matrix_partials<TOKENS>>& completed) {
#pragma HLS INLINE off
    float partial[TOKENS][8]={};
#pragma HLS ARRAY_PARTITION variable=partial complete
    unsigned block=0;const unsigned blocks=cols/32;
    for(unsigned index=0;index<rows*blocks;index++) {
#pragma HLS PIPELINE II=1
        q8_block wa=stream_a.read();
        q8_block wb=wa;
        if(split)wb=stream_b.read();
        float sa=half_to_float(wa.range(15,0)),sb=half_to_float(wb.range(15,0));
        matrix_partials<TOKENS> result={};
        for(unsigned b=0;b<TOKENS;b++) {
#pragma HLS UNROLL
            bool upper=b>=TOKENS/2;
            bool active=split?(b-(upper?TOKENS/2:0))<batch:b<batch;
            if(active) {
                q8_block weights=upper?wb:wa;   // wb==wa unless split
                float scale=upper?sb:sa;
                ap_uint<256> packed=input[b][block];
                ap_int<32> tree[32];
#pragma HLS ARRAY_PARTITION variable=tree complete
                for(unsigned lane=0;lane<32;lane++) {
#pragma HLS UNROLL
                    ap_int<8> w=weights.range(16+lane*8+7,16+lane*8);
                    ap_int<8> x=packed.range(lane*8+7,lane*8);ap_int<16> product=w*x;
                    tree[lane]=product;
                }
                for(unsigned stride=16;stride;stride>>=1) {
#pragma HLS UNROLL
                    for(unsigned lane=0;lane<16;lane++) {
#pragma HLS UNROLL
                        if(lane<stride)tree[lane]+=tree[lane+stride];
                    }
                }
                float update=q8_add(block<8?0.0f:partial[b][0],(float(tree[0].to_int())*scale)*scales[b][block]);
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
        if(block+1==blocks){completed.write(result);block=0;}else block++;
    }
}

template<unsigned TOKENS,unsigned CAPACITY>
static void reduce_q8_split(hls::stream<matrix_partials<TOKENS>>& completed,float output[TOKENS][CAPACITY],
                            unsigned rows,unsigned batch,bool split,unsigned token_base,bool vocabulary,
                            float maximum[TOKENS],uint32_t token[TOKENS]) {
#pragma HLS INLINE off
    const unsigned HALF=TOKENS/2;
    float local_max[TOKENS];uint32_t local_token[TOKENS];
#pragma HLS ARRAY_PARTITION variable=local_max complete
#pragma HLS ARRAY_PARTITION variable=local_token complete
    for(unsigned b=0;b<TOKENS;b++) {
#pragma HLS UNROLL
        unsigned src=(split&&b>=HALF)?b-HALF:b;
        local_max[b]=maximum[src];local_token[b]=token[src];
    }
    for(unsigned row=0;row<rows;row++) {
#pragma HLS PIPELINE II=16
        matrix_partials<TOKENS> values=completed.read();
        for(unsigned b=0;b<TOKENS;b++) {
#pragma HLS UNROLL
            bool upper=split&&b>=HALF;
            unsigned t=upper?b-HALF:b;
            if(t<batch) {
                unsigned r=upper?rows+row:row;
                float a0=q8_add(values.values[b][0],values.values[b][1]);
                float a1=q8_add(values.values[b][2],values.values[b][3]);
                float a2=q8_add(values.values[b][4],values.values[b][5]);
                float a3=q8_add(values.values[b][6],values.values[b][7]);
                float c0=q8_add(a0,a1);float c1=q8_add(a2,a3);
                float sum=q8_add(c0,c1);
                if(vocabulary) {
                    if(sum>local_max[b] || (sum==local_max[b] && token_base+r<local_token[b])) {
                        local_max[b]=sum;local_token[b]=token_base+r;
                    }
                } else if(r<CAPACITY)output[t][r]=sum;
            }
        }
    }
    for(unsigned b=0;b<TOKENS;b++) {
#pragma HLS UNROLL
        float m=local_max[b];uint32_t k=local_token[b];
        if(split&&b<HALF) {
            float m2=local_max[b+HALF];uint32_t k2=local_token[b+HALF];
            if(m2>m || (m2==m && k2<k)){m=m2;k=k2;}
        }
        if(!(split&&b>=HALF)){maximum[b]=m;token[b]=k;}
    }
}
