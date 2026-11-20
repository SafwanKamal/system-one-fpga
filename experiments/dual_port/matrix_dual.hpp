#pragma once
// Dual weight port: rows [0,R/2) arrive on stream a and rows [R/2,R) on stream b.
// One pipeline consumes one block from each stream per cycle. Row i and row i+R/2 use the
// same input block, so the input is read once per cycle, as in the single-port core.
// Each row's arithmetic (products, integer tree, two FP scalings, eight-register rotation,
// fixed-order final tree) is the single-port code applied per row, so outputs are identical.
// Requires rows even and cols%512==0, which holds for every Qwen3-0.6B matrix and every
// head chunk the host issues (8192 and 4480 rows).
template<unsigned TOKENS> struct matrix_pair {float values[2][TOKENS][8];};


// Slot-pair packed dot product (exact). Slots b and b+1 share the weight operand, so
// (x_b*2^19 + x_b1)*w gives both products in one DSP multiply. Sixteen lanes are summed in
// one chain: |sum of x_b1*w| <= 16*127*128 = 260096 < 2^18, so the low 19 bits, sign
// extended, are exactly that sum and the rest is exactly the x_b sum. Activations are
// clamped to [-127,127] by quantize_activation, so the packed operand fits 27 signed bits.
static void pair_dot(const q8_block& wv,ap_uint<256> xa,ap_uint<256> xb,ap_int<32>& sa,ap_int<32>& sb) {
#pragma HLS INLINE
    ap_int<32> ta=0,tb=0;
    for(unsigned half=0;half<2;half++) {
#pragma HLS UNROLL
        ap_int<48> acc=0;
        for(unsigned lane=0;lane<16;lane++) {
#pragma HLS UNROLL
            unsigned l=half*16+lane;
            ap_int<8> w=wv.range(16+l*8+7,16+l*8);
            ap_int<8> a=xa.range(l*8+7,l*8);ap_int<8> c=xb.range(l*8+7,l*8);
            ap_int<27> pk=(ap_int<27>(a)<<19)+ap_int<27>(c);
            acc+=pk*w;
        }
        ap_int<19> lo=acc.range(18,0);
        ap_int<48> hi=(acc-ap_int<48>(lo))>>19;
        ta+=ap_int<32>(hi);tb+=ap_int<32>(lo);
    }
    sa=ta;sb=tb;
}

template<unsigned TOKENS,unsigned CAPACITY>
static void accumulate_q8_dual(hls::stream<q8_block>& stream_a,hls::stream<q8_block>& stream_b,
                               const ap_uint<256> input[TOKENS][CAPACITY/32],const float scales[TOKENS][CAPACITY/32],
                               unsigned half_rows,unsigned cols,unsigned batch,hls::stream<matrix_pair<TOKENS>>& completed) {
#pragma HLS INLINE off
    float partial[2][TOKENS][8]={};
#pragma HLS ARRAY_PARTITION variable=partial complete
    unsigned block=0;const unsigned blocks=cols/32;
    for(unsigned index=0;index<half_rows*blocks;index++) {
#pragma HLS PIPELINE II=1
        q8_block wv[2];
#pragma HLS ARRAY_PARTITION variable=wv complete
        wv[0]=stream_a.read();wv[1]=stream_b.read();
        matrix_pair<TOKENS> result={};
        for(unsigned b=0;b<TOKENS;b++) {
#pragma HLS UNROLL
            if(b<batch) {
                ap_uint<256> packed=input[b][block];float s_in=scales[b][block];
                for(unsigned h=0;h<2;h++) {
#pragma HLS UNROLL
                    float scale=half_to_float(wv[h].range(15,0));
                    ap_int<32> tree[32];
#pragma HLS ARRAY_PARTITION variable=tree complete
                    for(unsigned lane=0;lane<32;lane++) {
#pragma HLS UNROLL
                        ap_int<8> w=wv[h].range(16+lane*8+7,16+lane*8);
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
                    float update=q8_add(block<8?0.0f:partial[h][b][0],(float(tree[0].to_int())*scale)*s_in);
                    float values[8];
#pragma HLS ARRAY_PARTITION variable=values complete
                    for(unsigned i=0;i<7;i++) {
#pragma HLS UNROLL
                        values[i]=partial[h][b][i+1];partial[h][b][i]=values[i];
                    }
                    values[7]=update;partial[h][b][7]=update;
                    if(block+1==blocks) {
                        for(unsigned i=0;i<8;i++) {
#pragma HLS UNROLL
                            result.values[h][b][i]=values[i]; // blocks%16==0, so the last block of a row is rotation slot 7
                        }
                    }
                }
            }
        }
        if(block+1==blocks){completed.write(result);block=0;}else block++;
    }
}

template<unsigned TOKENS,unsigned CAPACITY>
static void accumulate_q8_dual_packed(hls::stream<q8_block>& stream_a,hls::stream<q8_block>& stream_b,
                               const ap_uint<256> input[TOKENS][CAPACITY/32],const float scales[TOKENS][CAPACITY/32],
                               unsigned half_rows,unsigned cols,unsigned batch,hls::stream<matrix_pair<TOKENS>>& completed) {
#pragma HLS INLINE off
    float partial[2][TOKENS][8]={};
#pragma HLS ARRAY_PARTITION variable=partial complete
    unsigned block=0;const unsigned blocks=cols/32;
    for(unsigned index=0;index<half_rows*blocks;index++) {
#pragma HLS PIPELINE II=1
        q8_block wv[2];
#pragma HLS ARRAY_PARTITION variable=wv complete
        wv[0]=stream_a.read();wv[1]=stream_b.read();
        matrix_pair<TOKENS> result={};
        for(unsigned h=0;h<2;h++) {
#pragma HLS UNROLL
            float scale=half_to_float(wv[h].range(15,0));
            ap_int<32> sums[TOKENS];
#pragma HLS ARRAY_PARTITION variable=sums complete
            for(unsigned b=0;b<TOKENS;b+=2) {
#pragma HLS UNROLL
                pair_dot(wv[h],input[b][block],input[b+1][block],sums[b],sums[b+1]);
            }
            for(unsigned b=0;b<TOKENS;b++) {
#pragma HLS UNROLL
                if(b<batch) {
                    float update=q8_add(block<8?0.0f:partial[h][b][0],(float(sums[b].to_int())*scale)*scales[b][block]);
                    float values[8];
#pragma HLS ARRAY_PARTITION variable=values complete
                    for(unsigned i=0;i<7;i++) {
#pragma HLS UNROLL
                        values[i]=partial[h][b][i+1];partial[h][b][i]=values[i];
                    }
                    values[7]=update;partial[h][b][7]=update;
                    if(block+1==blocks) {
                        for(unsigned i=0;i<8;i++) {
#pragma HLS UNROLL
                            result.values[h][b][i]=values[i]; // blocks%16==0, so the last block of a row is rotation slot 7
                        }
                    }
                }
            }
        }
        if(block+1==blocks){completed.write(result);block=0;}else block++;
    }
}

template<unsigned TOKENS,unsigned CAPACITY>
static void reduce_q8_dual(hls::stream<matrix_pair<TOKENS>>& completed,float output[TOKENS][CAPACITY],
                           unsigned half_rows,unsigned batch,unsigned token_base,bool vocabulary,
                           float maximum[TOKENS],uint32_t token[TOKENS]) {
#pragma HLS INLINE off
    // Same per-row sum as reduce_q8. The argmax rule (larger, or equal with the smaller
    // index) does not depend on the order rows are visited, so it equals the single-port scan.
    float local_max[TOKENS];uint32_t local_token[TOKENS];
#pragma HLS ARRAY_PARTITION variable=local_max complete
#pragma HLS ARRAY_PARTITION variable=local_token complete
    for(unsigned b=0;b<TOKENS;b++) {
#pragma HLS UNROLL
        local_max[b]=maximum[b];local_token[b]=token[b];
    }
    matrix_pair<TOKENS> pair;
#pragma HLS ARRAY_PARTITION variable=pair.values complete
    for(unsigned step=0;step<2*half_rows;step++) {
#pragma HLS PIPELINE II=16
        unsigned h=step&1;
        if(h==0)pair=completed.read();
        unsigned row=h?half_rows+(step>>1):(step>>1);
        for(unsigned b=0;b<TOKENS;b++) {
#pragma HLS UNROLL
            if(b<batch) {
                float v[8];
#pragma HLS ARRAY_PARTITION variable=v complete
                for(unsigned i=0;i<8;i++) {
#pragma HLS UNROLL
                    v[i]=h?pair.values[1][b][i]:pair.values[0][b][i];
                }
                float a0=q8_add(v[0],v[1]);
                float a1=q8_add(v[2],v[3]);
                float a2=q8_add(v[4],v[5]);
                float a3=q8_add(v[6],v[7]);
                float c0=q8_add(a0,a1);float c1=q8_add(a2,a3);
                float sum=q8_add(c0,c1);
                if(vocabulary) {
                    if(sum>local_max[b] || (sum==local_max[b] && token_base+row<local_token[b])) {
                        local_max[b]=sum;local_token[b]=token_base+row;
                    }
                } else if(row<CAPACITY)output[b][row]=sum;
            }
        }
    }
    for(unsigned b=0;b<TOKENS;b++) {
#pragma HLS UNROLL
        maximum[b]=local_max[b];token[b]=local_token[b];
    }
}
