#include <ap_int.h>
#include <hls_stream.h>
#include <hls_math.h>
#include <stdint.h>
#include <float.h>
// v9f: v9e plus a batched vocabulary head for speculative verification. cmd 11
// applies the final norm to token slots 0..rows-1 and cmd 12 scores one head
// chunk for slots 0..layer-1 in one weight pass, with one running argmax per
// slot. Every slot's arithmetic is the v9e slot-0 path (cmd 9, 3, 4) applied to
// that slot; cmd 3 and cmd 4 are unchanged.
// v9e: v9d with a BF16 K/V cache (round-to-nearest-even on store, exact widening
// on load) and a 2048-token context. All arithmetic stays FP32.
// v9d: v9c plus two prompt tokens scored per K/V pass in prefill attention.
// v9c: v9a build 3 plus tiled online-softmax attention (context set by SYS_QWEN_CONTEXT).
// v9a: same register ABI and Q8 matrix core as v8. The state port is 256 bits
// wide, the KV cache is head-major so each head is one contiguous burst, and
// the serial vector work reads four activation lanes per cycle.
using word=ap_uint<256>;
using weight_word=ap_uint<256>;
#include "../../hls/qwen_decoder_v9f/model_profile.hpp"
static_assert(HD==128 && NH%NK==0,"Head-major attention assumes 128-wide heads");
static_assert(NH/NK<=2,"Tile state holds one query-head pair per KV head");
static uint32_t model_pages[64];
static unsigned page_count=0,model_extent=0;
static float activation[B][ACT],dotoutput[B][F];
// One 256-bit word (32 INT8 lanes) per token and 32-value block, in BRAM.
static ap_uint<256> quantized[B][F/32];
// All four norm weight vectors share one buffer so a single RMS engine serves
// every call site (v8 and v9a build 1 instantiated four copies).
static const unsigned NORM_G=0,FFN_G=H,QUERY_G=2*H,KEY_G=2*H+HD;
static float gamma_all[2*H+2*HD];
static float qscales[B][F/32];
static float best_logit[B];
static uint32_t best_token[B];
// Quad-indexed access: index 4*quad+lane makes the cyclic-4 bank a constant.
#define A(b,quad,lane) activation[b][(quad)*4+(lane)]
static float asfloat(uint32_t value) {
#pragma HLS INLINE
    union { uint32_t i; float f; } x; x.i=value; return x.f;
}
static float half_to_float(ap_uint<16> value) {
#pragma HLS INLINE
    uint32_t h=value.to_uint(),sign=(h&0x8000u)<<16;
    uint32_t exponent=(h>>10)&31u,mantissa=h&1023u;
    if(exponent==0) {
        if(mantissa==0)return asfloat(sign);
        unsigned shifts=0;
        for(unsigned i=0;i<10;i++) {
#pragma HLS UNROLL
            if((mantissa&1024u)==0){mantissa<<=1;shifts++;}
        }
        return asfloat(sign|((113u-shifts)<<23)|((mantissa&1023u)<<13));
    }
    return asfloat(sign|((exponent==31?255:exponent+112)<<23)|(mantissa<<13));
}
static uint32_t asbits(float value) {
#pragma HLS INLINE
    union { uint32_t i; float f; } x; x.f=value; return x.i;
}
static uint32_t loadu(word *memory, uint32_t physical) {
#pragma HLS INLINE
    word x=memory[physical>>5];
    return (x >> ((physical&31)*8)).range(31,0).to_uint();
}
static uint32_t model_address(uint32_t logical) {
#pragma HLS INLINE
    return model_pages[logical>>CHUNK_BITS]+(logical&((1u<<CHUNK_BITS)-1));
}
// Split only at owned DMA-segment boundaries. The inner loop is a contiguous
// AXI burst; no speculative reference to a neighbouring Linux page is needed.
static void load_model(weight_word *memory,uint32_t logical,unsigned words,hls::stream<weight_word>& stream) {
#pragma HLS INLINE off
    unsigned done=0;
    while(done<words) {
        uint32_t offset=logical&((1u<<CHUNK_BITS)-1);
        unsigned count=((1u<<CHUNK_BITS)-offset)>>5;
        if(count>words-done)count=words-done;
        uint32_t address=model_address(logical)>>5;
        for(unsigned i=0;i<count;i++) {
#pragma HLS PIPELINE II=1
            stream.write(memory[address+i]);
        }
        done+=count;logical+=count*32;
    }
}
#include "../../hls/qwen_decoder_v9f/matrix_q8.hpp"
// Quantization reads activations directly (no FP32 staging copy), four lanes
// per cycle in three narrow passes. Scale, reciprocal and rounding are
// bit-identical to v8 for finite inputs. The max-abs pass compares IEEE bit
// patterns of |x| as unsigned integers, which orders all finite magnitudes
// exactly; |-0| becomes +0, matching v8's +0-initialised scan.
static void quantize_activation(unsigned input,unsigned cols,unsigned batch) {
#pragma HLS INLINE off
    // Four lane maxima per block; the 4:1 reduction happens in the scale pass
    // so no compare tree sits between the URAM read and the BRAM write.
    static uint32_t magnitude[B*(F/32)][4];
#pragma HLS ARRAY_PARTITION variable=magnitude complete dim=2
    static float inverse[B*(F/32)];
    const unsigned blocks=cols/32;
    unsigned lane_max[4]={0,0,0,0};
#pragma HLS ARRAY_PARTITION variable=lane_max complete
    unsigned b=0,block=0,j=0;
    for(unsigned index=0;index<batch*blocks*8;index++) {
#pragma HLS PIPELINE II=1
        for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
            unsigned a=asbits(A(b,input/4+block*8+j,lane))&0x7fffffffu;
            unsigned previous=j==0?0u:lane_max[lane];
            lane_max[lane]=a>previous?a:previous;
        }
        if(j==7)for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
            magnitude[b*(F/32)+block][lane]=lane_max[lane];
        }
        if(j==7){j=0;if(block+1==blocks){block=0;b++;}else block++;}else j++;
    }
    for(unsigned bb=0;bb<batch;bb++)for(unsigned k=0;k<blocks;k++) {
#pragma HLS PIPELINE II=1
        unsigned row=bb*(F/32)+k,m0=magnitude[row][0],m1=magnitude[row][1],m2=magnitude[row][2],m3=magnitude[row][3];
        unsigned m01=m0>m1?m0:m1,m23=m2>m3?m2:m3;
        float scale=asfloat(m01>m23?m01:m23)/127.0f;
        qscales[bb][k]=scale;inverse[bb*(F/32)+k]=scale==0?0.0f:1.0f/scale;
    }
    // Eight cycles fill a 32-value shift register; the block is then written as
    // one packed 256-bit BRAM word (quantized is not LUTRAM since build 2).
    ap_int<8> pending[32];
#pragma HLS ARRAY_PARTITION variable=pending complete
    b=0;block=0;j=0;
    for(unsigned index=0;index<batch*blocks*8;index++) {
#pragma HLS PIPELINE II=1
        float scale_inverse=inverse[b*(F/32)+block];
        for(unsigned i=0;i<28;i++) {
#pragma HLS UNROLL
            pending[i]=pending[i+4];
        }
        for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
            float v=A(b,input/4+block*8+j,lane)*scale_inverse;
            int value=int(v>=0?v+0.5f:v-0.5f);
            if(value>127)value=127;if(value<-127)value=-127;
            pending[28+lane]=value;
        }
        if(j==7) {
            ap_uint<256> word=0;
            for(unsigned i=0;i<32;i++) {
#pragma HLS UNROLL
                word.range(i*8+7,i*8)=ap_uint<8>(pending[i]);
            }
            quantized[b][block]=word;
        }
        if(j==7){j=0;if(block+1==blocks){block=0;b++;}else block++;}else j++;
    }
}
static void matvec(weight_word *memory,uint32_t logical,const ap_uint<256> input[B][F/32],const float scales[B][F/32],float output[B][F],
                   unsigned rows,unsigned cols,unsigned batch,unsigned token_base,bool vocabulary,
                   float maximum[B],uint32_t token[B]) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
    hls::stream<weight_word> words("words");
    hls::stream<q8_block> blocks("blocks");
#pragma HLS STREAM variable=words depth=128
#pragma HLS STREAM variable=blocks depth=32
#pragma HLS BIND_STORAGE variable=words type=fifo impl=srl
#pragma HLS BIND_STORAGE variable=blocks type=fifo impl=srl
    unsigned count=(rows*(cols/32)*34)/32;
    load_model(memory,logical,count,words);
    unpack_q8(words,count,blocks);
    integer_dot_packed<B,F>(blocks,input,scales,output,rows,cols,batch,token_base,vocabulary,maximum,token);
}
// Contiguous FP32 vector loads use the same owned DMA-page boundary splitter
// as matrix weights. Norm weights are loaded once for the whole token batch.
static void load_gamma(weight_word *memory,uint32_t logical,unsigned base,unsigned n) {
#pragma HLS INLINE off
    unsigned done=0;
    while(done<n/8) {
        unsigned count=((1u<<CHUNK_BITS)-(logical&((1u<<CHUNK_BITS)-1)))>>5;
        if(count>n/8-done)count=n/8-done;
        uint32_t address=model_address(logical)>>5;
        for(unsigned i=0;i<count;i++) {
#pragma HLS PIPELINE II=1
            weight_word value=memory[address+i];
            for(unsigned lane=0;lane<8;lane++) {
#pragma HLS UNROLL
                gamma_all[base+(done+i)*8+lane]=asfloat(value.range(lane*32+31,lane*32).to_uint());
            }
        }
        done+=count;logical+=count*32;
    }
}
// Four lane-wise partial sums of squares, combined as (l0+l1)+(l2+l3).
// Offsets are in quads (four floats). In-place use (in==out) is supported:
// each element is read before its own write and iterations are disjoint.
static void rms(unsigned b,unsigned in,unsigned out,unsigned quads,unsigned gamma) {
#pragma HLS INLINE off
#pragma HLS DEPENDENCE variable=activation inter false
    float lanes[4]={0,0,0,0};
#pragma HLS ARRAY_PARTITION variable=lanes complete
    for(unsigned q=0;q<quads;q++) {
#pragma HLS PIPELINE
        for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
            float x=A(b,in+q,lane);lanes[lane]+=x*x;
        }
    }
    float squares=(lanes[0]+lanes[1])+(lanes[2]+lanes[3]);
    float inverse=1.0f/hls::sqrtf(squares/float(quads*4)+1.0e-6f);
    for(unsigned q=0;q<quads;q++) {
#pragma HLS PIPELINE II=1
        for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
            A(b,out+q,lane)=A(b,in+q,lane)*inverse*gamma_all[(gamma/4+q)*4+lane];
        }
    }
}
// One 512-byte table row (64 cosines, then 64 sines) serves every Q/K head.
static void load_rotary(word *memory,unsigned position,uint32_t table,float cosine[64],float sine[64]) {
#pragma HLS INLINE off
    for(unsigned i=0;i<16;i++) {
#pragma HLS PIPELINE II=1
        word value=memory[(table+position*512)/32+i];
        for(unsigned lane=0;lane<8;lane++) {
#pragma HLS UNROLL
            float x=asfloat(value.range(lane*32+31,lane*32).to_uint());
            if(i<8)cosine[i*8+lane]=x;else sine[(i-8)*8+lane]=x;
        }
    }
}
static void rope(unsigned b,unsigned base,unsigned heads,const float cosine[64],const float sine[64]) {
#pragma HLS INLINE off
    // Iteration (head,i4) owns elements head*128+i4*4+{0..3} and their +64 partners.
#pragma HLS DEPENDENCE variable=activation inter false
    for(unsigned head=0;head<heads;head++) {
        for(unsigned i4=0;i4<16;i4++) {
#pragma HLS PIPELINE
            for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
                unsigned low=base+head*32+i4,high=low+16;
                float c=cosine[i4*4+lane],s=sine[i4*4+lane];
                float a=A(b,low,lane),x=A(b,high,lane);
                A(b,low,lane)=a*c-x*s;A(b,high,lane)=x*c+a*s;
            }
        }
    }
}
// BF16 K/V: round to nearest even (NaN kept quiet); widening is exact.
static ap_uint<16> to_bf16(float x) {
#pragma HLS INLINE
    uint32_t u=asbits(x);
    if((u&0x7f800000u)==0x7f800000u && (u&0x007fffffu))return ap_uint<16>((u>>16)|0x40u);
    return ap_uint<16>((u+0x7fffu+((u>>16)&1u))>>16);
}
static float from_bf16(ap_uint<16> h) {
#pragma HLS INLINE
    return asfloat(uint32_t(h.to_uint())<<16);
}
// Head-major cache: ((layer*2+kv)*NK+head)*NC+position rows of 128 BF16 values
// (256 bytes = 8 words of 16 values).
static uint32_t cache_row(uint32_t cache,unsigned layer,unsigned kv,unsigned head,unsigned position) {
#pragma HLS INLINE
    return (cache+((((layer*2+kv)*NK+head)*NC+position)*HD)*2)>>5;
}
static void append_kv(word *memory,unsigned layer,unsigned position,uint32_t cache,unsigned b) {
#pragma HLS INLINE off
    for(unsigned kv=0;kv<2;kv++)for(unsigned head=0;head<NK;head++)for(unsigned w=0;w<8;w++) {
#pragma HLS PIPELINE II=2
        word out;
        for(unsigned lane=0;lane<16;lane++) {
#pragma HLS UNROLL
            out.range(16*lane+15,16*lane)=to_bf16(A(b,(kv?VOFF:KOFF)/4+head*32+w*4+lane/4,lane%4));
        }
        memory[cache_row(cache,layer,kv,head,position)+w]=out;
    }
}
// Eight BF16 lanes (one 128-bit half of a cache word) widened to FP32.
static float bf16_lane(word w,unsigned chunk,unsigned lane) {
#pragma HLS INLINE
    ap_uint<128> half=(chunk&1)?ap_uint<128>(w.range(255,128)):ap_uint<128>(w.range(127,0));
    return from_bf16(half.range(lane*16+15,lane*16));
}
// v9d: v9c's tiled online-softmax attention, with P prompt tokens of a prefill
// group scored per pass over the on-chip K/V tile. Each key/value row is read
// once and serves all P tokens. Every token keeps its own causal row count, max,
// sum and accumulator, so each token's operations and order equal v9c; rows
// beyond a token's own position are computed but never read, and accumulation
// is guarded per token.
static const unsigned TILE=256,P=4;
static float lanef(word w,unsigned lane) {
#pragma HLS INLINE
    return asfloat(w.range(lane*32+31,lane*32).to_uint());
}
// Query, accumulator and carried tile state are held as 16 words of 8 floats,
// one word read/written per cycle: no per-lane 16:1 muxes around the FP units.
static void attention(word *memory,unsigned layer,unsigned first,uint32_t cache,unsigned batch) {
#pragma HLS INLINE off
    // BF16 tile buffers: a 128-value row is 8 words; chunk c is half (c&1) of word c/2.
    static word key_rows[TILE*8],value_rows[TILE*8];
#pragma HLS BIND_STORAGE variable=key_rows type=ram_2p impl=uram
#pragma HLS BIND_STORAGE variable=value_rows type=ram_2p impl=uram
    // Running state per token slot and query-head pair, carried across tiles.
    // Indexed [slot/P][slot%P] so the token-in-pass index is a constant bank.
    static word run_acc[B/P][P][2][HD/8];
    static float run_max[B/P][P][2],run_total[B/P][P][2];
#pragma HLS ARRAY_PARTITION variable=run_acc complete dim=2
#pragma HLS ARRAY_PARTITION variable=run_acc complete dim=3
#pragma HLS BIND_STORAGE variable=run_acc type=ram_s2p impl=lutram
#pragma HLS ARRAY_PARTITION variable=run_max complete dim=2
#pragma HLS ARRAY_PARTITION variable=run_max complete dim=3
#pragma HLS ARRAY_PARTITION variable=run_total complete dim=2
#pragma HLS ARRAY_PARTITION variable=run_total complete dim=3
    const unsigned G=NH/NK;
    for(unsigned kvhead=0;kvhead<NK;kvhead++) {
        unsigned total=first+batch;
        for(unsigned tile=0;tile<total;tile+=TILE) {
            unsigned rows=total-tile<TILE?total-tile:TILE;
            // One contiguous burst per head and tile for K, then V.
            uint32_t kbase=cache_row(cache,layer,0,kvhead,tile),vbase=cache_row(cache,layer,1,kvhead,tile);
            for(unsigned i=0;i<rows*8;i++) {
#pragma HLS PIPELINE II=1
                key_rows[i]=memory[kbase+i];
            }
            for(unsigned i=0;i<rows*8;i++) {
#pragma HLS PIPELINE II=1
                value_rows[i]=memory[vbase+i];
            }
            for(unsigned b0=0;b0<batch;b0+=P)for(unsigned pair=0;pair<G;pair+=2) {
                unsigned count[P],longest=0;bool active[P],final[P];
#pragma HLS ARRAY_PARTITION variable=count complete
#pragma HLS ARRAY_PARTITION variable=active complete
#pragma HLS ARRAY_PARTITION variable=final complete
                for(unsigned p=0;p<P;p++) {
#pragma HLS UNROLL
                    unsigned position=first+b0+p;
                    active[p]=b0+p<batch && position>=tile;
                    unsigned visible=position+1-tile;
                    count[p]=active[p]?(visible<rows?visible:rows):0;
                    final[p]=position<tile+TILE;
                    if(count[p]>longest)longest=count[p];
                }
                if(longest==0)continue;
                unsigned padded=longest<16?16:longest;
                bool initial=tile==0;
                word query[P][2][HD/8],acc[P][2][HD/8];
                float score[P][2][TILE],mass[P][2][TILE];
                float maximum[P][2],total_mass[P][2],correction[P][2];
#pragma HLS ARRAY_PARTITION variable=query complete dim=1
#pragma HLS ARRAY_PARTITION variable=query complete dim=2
#pragma HLS BIND_STORAGE variable=query type=ram_s2p impl=lutram
#pragma HLS ARRAY_PARTITION variable=score complete dim=1
#pragma HLS ARRAY_PARTITION variable=score complete dim=2
#pragma HLS ARRAY_PARTITION variable=mass complete dim=1
#pragma HLS ARRAY_PARTITION variable=mass complete dim=2
#pragma HLS ARRAY_PARTITION variable=acc complete dim=1
#pragma HLS ARRAY_PARTITION variable=acc complete dim=2
#pragma HLS BIND_STORAGE variable=acc type=ram_s2p impl=lutram
#pragma HLS ARRAY_PARTITION variable=maximum complete
#pragma HLS ARRAY_PARTITION variable=total_mass complete
#pragma HLS ARRAY_PARTITION variable=correction complete
                for(unsigned p=0;p<P;p++)for(unsigned g=0;g<2;g++) {
#pragma HLS UNROLL
                    maximum[p][g]=-FLT_MAX;total_mass[p][g]=0;
                }
                for(unsigned p=0;p<P;p++)for(unsigned g=0;g<2;g++)for(unsigned c=0;c<HD/8;c++) {
#pragma HLS PIPELINE II=1
                    word w=0;
                    for(unsigned lane=0;lane<8;lane++) {
#pragma HLS UNROLL
                        float x=active[p]&&pair+g<G?A(b0+p,QOFF/4+(kvhead*G+pair+g)*32+c*2+lane/4,lane%4):0.0f;
                        w.range(lane*32+31,lane*32)=asbits(x);
                    }
                    query[p][g][c]=w;
                }
                // Chunk-major scoring: iteration (chunk,t) adds one 8-wide tree to
                // score[p][g][t] for every token. Rows are padded to >=16 so a
                // score's next update is at least 16 iterations later.
                unsigned t=0,chunk=0;
                for(unsigned index=0;index<16*padded;index++) {
#pragma HLS PIPELINE II=1
#pragma HLS DEPENDENCE variable=score inter distance=16 true
                    word key=key_rows[t*8+chunk/2];
                    for(unsigned p=0;p<P;p++)for(unsigned g=0;g<2;g++) {
#pragma HLS UNROLL
                        float q8[8];
#pragma HLS ARRAY_PARTITION variable=q8 complete
                        word qw=query[p][g][chunk];
                        for(unsigned lane=0;lane<8;lane++) {
#pragma HLS UNROLL
                            q8[lane]=lanef(qw,lane)*bf16_lane(key,chunk,lane);
                        }
                        float tree=((q8[0]+q8[1])+(q8[2]+q8[3]))+((q8[4]+q8[5])+(q8[6]+q8[7]));
                        score[p][g][t]=(chunk==0?0.0f:score[p][g][t])+tree;
                    }
                    if(t+1==padded){t=0;chunk++;}else t++;
                }
                for(unsigned s=0;s<longest;s++) {
#pragma HLS PIPELINE
                    for(unsigned p=0;p<P;p++)for(unsigned g=0;g<2;g++) {
#pragma HLS UNROLL
                        if(s<count[p]) {
                            float value=score[p][g][s]*0.08838834764831845f;
                            score[p][g][s]=value;if(value>maximum[p][g])maximum[p][g]=value;
                        }
                    }
                }
                // Merge with earlier tiles: new max, rescale the carried sums.
                for(unsigned p=0;p<P;p++)for(unsigned g=0;g<2;g++) {
#pragma HLS UNROLL
                    if(!initial && active[p]) {
                        float previous=run_max[b0/P][p][g];
                        if(previous>maximum[p][g])maximum[p][g]=previous;
                        correction[p][g]=hls::expf(previous-maximum[p][g]);
                    } else correction[p][g]=0.0f;
                }
                for(unsigned s=0;s<longest;s++) {
#pragma HLS PIPELINE
                    for(unsigned p=0;p<P;p++)for(unsigned g=0;g<2;g++) {
#pragma HLS UNROLL
                        if(s<count[p]) {
                            float value=hls::expf(score[p][g][s]-maximum[p][g]);mass[p][g][s]=value;total_mass[p][g]+=value;
                        }
                    }
                }
                for(unsigned c=0;c<HD/8;c++) {
#pragma HLS PIPELINE II=1
                    for(unsigned p=0;p<P;p++)for(unsigned g=0;g<2;g++) {
#pragma HLS UNROLL
                        word carried=run_acc[b0/P][p][g][c],w=0;
                        for(unsigned lane=0;lane<8;lane++) {
#pragma HLS UNROLL
                            w.range(lane*32+31,lane*32)=asbits(initial||!active[p]?0.0f:lanef(carried,lane)*correction[p][g]);
                        }
                        acc[p][g][c]=w;
                    }
                }
                for(unsigned s=0;s<longest;s++)for(unsigned c=0;c<16;c++) {
#pragma HLS PIPELINE II=1
#pragma HLS DEPENDENCE variable=acc inter distance=16 true
                    word value=value_rows[s*8+c/2];
                    for(unsigned p=0;p<P;p++)for(unsigned g=0;g<2;g++) {
#pragma HLS UNROLL
                        if(s<count[p]) {
                            word old=acc[p][g][c],w;
                            float m=mass[p][g][s];
                            for(unsigned lane=0;lane<8;lane++) {
#pragma HLS UNROLL
                                w.range(lane*32+31,lane*32)=asbits(lanef(old,lane)+m*bf16_lane(value,c,lane));
                            }
                            acc[p][g][c]=w;
                        }
                    }
                }
                for(unsigned p=0;p<P;p++) {
                    if(!active[p])continue;
                    unsigned b=b0+p;
                    float sums[2],inverse[2];
#pragma HLS ARRAY_PARTITION variable=sums complete
#pragma HLS ARRAY_PARTITION variable=inverse complete
                    for(unsigned g=0;g<2;g++) {
#pragma HLS UNROLL
                        sums[g]=initial?total_mass[p][g]:run_total[b0/P][p][g]*correction[p][g]+total_mass[p][g];
                        inverse[g]=1.0f/sums[g];
                    }
                    if(final[p]) {
                        for(unsigned g=0;g<2;g++)for(unsigned c=0;c<HD/8;c++) {
#pragma HLS PIPELINE II=1
                            word w=acc[p][g][c];
                            for(unsigned lane=0;lane<8;lane++) {
#pragma HLS UNROLL
                                if(pair+g<G)A(b,COFF/4+(kvhead*G+pair+g)*32+c*2+lane/4,lane%4)=lanef(w,lane)*inverse[g];
                            }
                        }
                    } else {
                        for(unsigned c=0;c<HD/8;c++) {
#pragma HLS PIPELINE II=1
                            for(unsigned g=0;g<2;g++) {
#pragma HLS UNROLL
                                run_acc[b0/P][p][g][c]=acc[p][g][c];
                            }
                        }
                        for(unsigned g=0;g<2;g++) {
#pragma HLS UNROLL
                            run_max[b0/P][p][g]=maximum[p][g];run_total[b0/P][p][g]=sums[g];
                        }
                    }
                }
            }
        }
    }
}
extern "C" void qwen_decoder(weight_word *model,word *scratch,unsigned cmd,uint32_t page,uint32_t cache,
                             uint32_t rotary,uint32_t result,unsigned layer,unsigned position,
                             unsigned rows,unsigned token_base,unsigned &status) {
#pragma HLS INTERFACE m_axi port=model offset=slave bundle=weights depth=67108864 max_read_burst_length=64 num_read_outstanding=8
#pragma HLS INTERFACE m_axi port=scratch offset=slave bundle=state depth=8388608 max_read_burst_length=64 num_read_outstanding=8 max_write_burst_length=64 num_write_outstanding=4
#pragma HLS INTERFACE s_axilite port=model bundle=control offset=0x10
#pragma HLS INTERFACE s_axilite port=scratch bundle=control offset=0x18
#pragma HLS INTERFACE s_axilite port=cmd bundle=control offset=0x20
#pragma HLS INTERFACE s_axilite port=page bundle=control offset=0x28
#pragma HLS INTERFACE s_axilite port=cache bundle=control offset=0x30
#pragma HLS INTERFACE s_axilite port=rotary bundle=control offset=0x38
#pragma HLS INTERFACE s_axilite port=result bundle=control offset=0x40
#pragma HLS INTERFACE s_axilite port=layer bundle=control offset=0x48
#pragma HLS INTERFACE s_axilite port=position bundle=control offset=0x50
#pragma HLS INTERFACE s_axilite port=rows bundle=control offset=0x58
#pragma HLS INTERFACE s_axilite port=token_base bundle=control offset=0x60
#pragma HLS INTERFACE s_axilite port=status bundle=control offset=0x68
#pragma HLS INTERFACE s_axilite port=return bundle=control
#pragma HLS ARRAY_PARTITION variable=model_pages complete
#pragma HLS ARRAY_PARTITION variable=best_logit complete
#pragma HLS ARRAY_PARTITION variable=best_token complete
// Token slots share deep URAM banks; no wide dynamic token-bank mux.
#pragma HLS ARRAY_PARTITION variable=activation cyclic factor=4 dim=2
#pragma HLS BIND_STORAGE variable=activation type=ram_t2p impl=uram
#pragma HLS ARRAY_PARTITION variable=dotoutput complete dim=1
#pragma HLS ARRAY_PARTITION variable=dotoutput cyclic factor=4 dim=2
#pragma HLS BIND_STORAGE variable=dotoutput type=ram_t2p impl=bram
#pragma HLS ARRAY_PARTITION variable=quantized complete dim=1
#pragma HLS BIND_STORAGE variable=quantized type=ram_s2p impl=bram
#pragma HLS ARRAY_PARTITION variable=qscales complete dim=1
#pragma HLS ARRAY_PARTITION variable=gamma_all cyclic factor=4
#pragma HLS ALLOCATION function instances=rms limit=1
#pragma HLS ALLOCATION function instances=load_gamma limit=1
    float cosine[64],sine[64];
#pragma HLS ARRAY_PARTITION variable=cosine cyclic factor=4
#pragma HLS ARRAY_PARTITION variable=sine cyclic factor=4
    status=0;
    if(cmd==0) {
        if(rows==0 || rows>64 || token_base==0 || token_base>rows*(1u<<CHUNK_BITS)) {status=1;return;}
        for(unsigned i=0;i<rows;i++)model_pages[i]=loadu(scratch,page+4*i);
        page_count=rows;model_extent=token_base;return;
    }
    if(page_count==0){status=2;return;}
    if(cmd==1 || cmd==7) {
        unsigned batch=cmd==7?rows:1;
        if(batch==0 || batch>B || (cmd==7 && page>0x10000000u-B*4)){status=10;return;}
        for(unsigned b=0;b<batch;b++) {
            unsigned logical=cmd==7?loadu(scratch,page+4*b):page;
            if(logical>model_extent || model_extent-logical<EMBED_BYTES){status=3;return;}
            ap_uint<512> window=0;unsigned available=0;
            for(unsigned block=0;block<H/32;block++) {
                for(unsigned beat=0;beat<2;beat++)if(available<34) {
                    window|=ap_uint<512>(model[model_address(logical)>>5])<<(available*8);logical+=32;available+=32;
                }
                float scale=half_to_float(window.range(15,0));
                for(unsigned lane=0;lane<32;lane++) {
#pragma HLS UNROLL
                    ap_int<8> w=window.range(16+lane*8+7,16+lane*8);activation[b][XOFF+32*block+lane]=scale*float(w.to_int());
                }
                window>>=272;available-=34;
            }
        }
    } else if(cmd==2 || cmd==8 || cmd==4 || cmd==12) {
        bool decoder=cmd==2 || cmd==8;unsigned batch=cmd==8?rows:cmd==12?layer:1;uint32_t offsets[11];
        if(batch==0 || batch>B){status=10;return;}
        if(decoder) {
            if(layer>=NL || position>=NC || batch>NC-position || cache>0x10000000u-NL*2*NC*KV*2 || (cache&31) || rotary>0x10000000u-NC*512 || (rotary&31) || page>0x10000000u-44){status=4;return;}
            for(unsigned i=0;i<11;i++)offsets[i]=loadu(scratch,page+4*i);
            for(unsigned i=0;i<11;i++) {
                unsigned length=i==0||i==3?Q*H/32*34:i==1||i==2?KV*H/32*34:i<7?F*H/32*34:i<9?H*4:HD*4;
                if(offsets[i]>model_extent || model_extent-offsets[i]<length){status=5;return;}
            }
            load_gamma(model,offsets[7],NORM_G,H);
            load_gamma(model,offsets[8],FFN_G,H);
            load_gamma(model,offsets[9],QUERY_G,HD);
            load_gamma(model,offsets[10],KEY_G,HD);
            for(unsigned b=0;b<batch;b++)rms(b,XOFF/4,NOFF/4,H/4,NORM_G);
        } else {
            if(rows==0 || rows>8192 || token_base+rows>VOCAB || result>0x10000000u-32*batch || (result&31) || page>model_extent || model_extent-page<rows*(H/32)*34){status=6;return;}
            if(token_base==0)for(unsigned b=0;b<B;b++){best_logit[b]=-FLT_MAX;best_token[b]=0;}
        }
        for(unsigned op=0;op<(decoder?7u:1u);op++) {
            unsigned input=NOFF,output=POFF,columns=H,outputs=H;uint32_t weights=page;
            if(decoder) {
                weights=offsets[op];
                if(op==0){output=QOFF;outputs=Q;}
                if(op==1){output=KOFF;outputs=KV;}
                if(op==2){output=VOFF;outputs=KV;}
                if(op==3) {
                    // Append all K/V first, then each query is bounded by its own position.
                    // The shared head buffer contains later rows but they are never scored.
                    for(unsigned b=0;b<batch;b++) {
                        for(unsigned head=0;head<NH;head++)rms(b,QOFF/4+head*32,QOFF/4+head*32,32,QUERY_G);
                        for(unsigned head=0;head<NK;head++)rms(b,KOFF/4+head*32,KOFF/4+head*32,32,KEY_G);
                        load_rotary(scratch,position+b,rotary,cosine,sine);
                        rope(b,QOFF/4,NH,cosine,sine);rope(b,KOFF/4,NK,cosine,sine);
                        append_kv(scratch,layer,position+b,cache,b);
                    }
                    attention(scratch,layer,position,cache,batch);
                    input=COFF;columns=Q;
                }
                if(op==4) {
                    for(unsigned b=0;b<batch;b++) {
                        for(unsigned q=0;q<H/4;q++) {
#pragma HLS PIPELINE II=1
#pragma HLS DEPENDENCE variable=activation inter false
                            for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
                                A(b,XOFF/4+q,lane)+=A(b,POFF/4+q,lane);
                            }
                        }
                        rms(b,XOFF/4,NOFF/4,H/4,FFN_G);
                    }
                    output=GOFF;outputs=F;
                }
                if(op==5){output=UOFF;outputs=F;}
                if(op==6) {
                    for(unsigned b=0;b<batch;b++)for(unsigned i=0;i<F;i++) {
#pragma HLS PIPELINE
                        float g=activation[b][GOFF+i];activation[b][GOFF+i]=(g/(1.0f+hls::expf(-g)))*activation[b][UOFF+i];
                    }
                    input=GOFF;columns=F;
                }
            } else outputs=rows;
            if(!(decoder&&(op==1||op==2||op==5)))quantize_activation(input,columns,batch);
            matvec(model,weights,quantized,qscales,dotoutput,outputs,columns,batch,token_base,!decoder,best_logit,best_token);
            if(decoder)for(unsigned b=0;b<batch;b++)for(unsigned q=0;q<outputs/4;q++) {
#pragma HLS PIPELINE II=1
                for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
                    A(b,output/4+q,lane)=dotoutput[b][q*4+lane];
                }
            }
        }
        if(decoder)for(unsigned b=0;b<batch;b++)for(unsigned q=0;q<H/4;q++) {
#pragma HLS PIPELINE II=1
#pragma HLS DEPENDENCE variable=activation inter false
            for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
                A(b,XOFF/4+q,lane)+=A(b,POFF/4+q,lane);
            }
        }
        else for(unsigned b=0;b<batch;b++){word out=0;out.range(31,0)=best_token[b];out.range(63,32)=asbits(best_logit[b]);scratch[(result>>5)+b]=out;}
    } else if(cmd==3 || cmd==11) {
        unsigned batch=cmd==11?rows:1;
        if(batch==0 || batch>B){status=10;return;}
        if(page>model_extent || model_extent-page<H*4){status=7;return;}
        load_gamma(model,page,NORM_G,H);
        for(unsigned b=0;b<batch;b++)rms(b,XOFF/4,NOFF/4,H/4,NORM_G);
    } else if(cmd==9) {
        if(layer>=B){status=10;return;}
        for(unsigned q=0;q<H/4;q++) {
#pragma HLS PIPELINE II=1
            for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
                A(0,XOFF/4+q,lane)=A(layer,XOFF/4+q,lane);
            }
        }
    } else if(cmd==5 || cmd==6 || cmd==10) {
        unsigned b=cmd==10?layer:0;
        if(b>=B || result>0x10000000u-H*4 || (result&31)){status=8;return;}
        for(unsigned i=0;i<H;i+=8) {
#pragma HLS PIPELINE II=1
            word out;
            for(unsigned lane=0;lane<8;lane++) {
#pragma HLS UNROLL
                out.range(32*lane+31,32*lane)=asbits(A(b,(cmd==6?NOFF:XOFF)/4+i/4+lane/4,lane%4));
            }
            scratch[(result+i*4)>>5]=out;
        }
    } else status=9;
}
