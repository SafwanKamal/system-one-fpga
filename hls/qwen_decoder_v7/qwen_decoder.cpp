#include <ap_int.h>
#include <hls_stream.h>
#include <hls_math.h>
#include <stdint.h>
#include <float.h>
using word=ap_uint<128>;
#include "model_profile.hpp"
static uint32_t model_pages[64];
static unsigned page_count=0,model_extent=0;
static float activation[B][ACT],dotinput[B][F],dotoutput[B][F];
static float best_logit=-FLT_MAX;
static uint32_t best_token=0;
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
    word x=memory[physical>>4];
    return (x >> ((physical&15)*8)).range(31,0).to_uint();
}
static float loadf(word *memory,uint32_t physical) {
#pragma HLS INLINE
    return asfloat(loadu(memory,physical));
}
static uint32_t model_address(uint32_t logical) {
#pragma HLS INLINE
    return model_pages[logical>>CHUNK_BITS]+(logical&((1u<<CHUNK_BITS)-1));
}
static float modelf(word *memory,uint32_t logical) {
#pragma HLS INLINE
    return loadf(memory,model_address(logical));
}
// Split only at owned DMA-segment boundaries. The inner loop is a contiguous
// AXI burst; no speculative reference to a neighbouring Linux page is needed.
static void load_model(word *memory,uint32_t logical,unsigned words,hls::stream<word>& stream) {
#pragma HLS INLINE off
    unsigned done=0;
    while(done<words) {
        uint32_t offset=logical&((1u<<CHUNK_BITS)-1);
        unsigned count=((1u<<CHUNK_BITS)-offset)>>4;
        if(count>words-done)count=words-done;
        uint32_t address=model_address(logical)>>4;
        for(unsigned i=0;i<count;i++) {
#pragma HLS PIPELINE II=1
            stream.write(memory[address+i]);
        }
        done+=count;logical+=count*16;
    }
}
#include "matrix_q8.hpp"
static void matvec(word *memory,uint32_t logical,const float input[B][F],float output[B][F],
                   unsigned rows,unsigned cols,unsigned batch,unsigned token_base,bool vocabulary,
                   float &maximum,uint32_t &token) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
    hls::stream<word> words("words");
    hls::stream<q8_block> blocks("blocks");
#pragma HLS STREAM variable=words depth=128
#pragma HLS STREAM variable=blocks depth=32
#pragma HLS BIND_STORAGE variable=words type=fifo impl=srl
#pragma HLS BIND_STORAGE variable=blocks type=fifo impl=srl
    unsigned count=(rows*(cols/32)*34)/16;
    load_model(memory,logical,count,words);
    unpack_q8(words,count,blocks);
    compute_q8<B,F>(blocks,input,output,rows,cols,batch,token_base,vocabulary,maximum,token);
}
// Contiguous FP32 vector loads use the same owned DMA-page boundary splitter
// as matrix weights. Norm weights are loaded once for the whole token batch.
static void load_gamma(word *memory,uint32_t logical,float *gamma,unsigned n) {
#pragma HLS INLINE off
    unsigned done=0;
    while(done<n/4) {
        unsigned count=((1u<<CHUNK_BITS)-(logical&((1u<<CHUNK_BITS)-1)))>>4;
        if(count>n/4-done)count=n/4-done;
        uint32_t address=model_address(logical)>>4;
        for(unsigned i=0;i<count;i++) {
#pragma HLS PIPELINE II=1
            word value=memory[address+i];
            for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
                gamma[(done+i)*4+lane]=asfloat(value.range(lane*32+31,lane*32).to_uint());
            }
        }
        done+=count;logical+=count*16;
    }
}
static void rms(const float *input,float *output,unsigned n,const float *gamma) {
#pragma HLS INLINE off
    // Each element is read before its own write; distinct iterations never
    // overlap, including the supported input==output head-normalization case.
#pragma HLS DEPENDENCE variable=input inter false
#pragma HLS DEPENDENCE variable=output inter false
    float squares=0;
    for(unsigned i=0;i<n;i++) {
#pragma HLS PIPELINE
        squares+=input[i]*input[i];
    }
    float inverse=1.0f/hls::sqrtf(squares/float(n)+1.0e-6f);
    for(unsigned i=0;i<n;i++) {
#pragma HLS PIPELINE
        output[i]=input[i]*inverse*gamma[i];
    }
}
// One 512-byte table row serves every Q/K head of a token, with burst reads.
static void load_rotary(word *memory,unsigned position,uint32_t table,float cosine[64],float sine[64]) {
#pragma HLS INLINE off
    word values[32];
    for(unsigned i=0;i<32;i++) {
#pragma HLS PIPELINE II=1
        values[i]=memory[(table+position*512)/16+i];
    }
    for(unsigned i=0;i<16;i++) {
#pragma HLS PIPELINE II=1
        for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
            cosine[i*4+lane]=asfloat(values[i].range(lane*32+31,lane*32).to_uint());
            sine[i*4+lane]=asfloat(values[i+16].range(lane*32+31,lane*32).to_uint());
        }
    }
}
static void rope(float *data,unsigned heads,const float cosine[64],const float sine[64]) {
#pragma HLS INLINE off
    // Iteration (head,i) owns exactly {head*128+i, head*128+i+64}.
    // No other iteration reads or writes these two elements.
#pragma HLS DEPENDENCE variable=data inter false
    for(unsigned head=0;head<heads;head++) {
        for(unsigned i=0;i<64;i++) {
#pragma HLS PIPELINE
            float c=cosine[i],s=sine[i];
            float a=data[head*128+i],b=data[head*128+i+64];
            data[head*128+i]=a*c-b*s;data[head*128+i+64]=b*c+a*s;
        }
    }
}
static void append_kv(word *memory,unsigned layer,unsigned position,uint32_t cache,unsigned b) {
#pragma HLS INLINE off
    for(unsigned i=0;i<KV;i+=4) {
#pragma HLS PIPELINE II=1
        word k,v;
        for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
            k.range(32*lane+31,32*lane)=asbits(activation[b][KOFF+i+lane]);
            v.range(32*lane+31,32*lane)=asbits(activation[b][VOFF+i+lane]);
        }
        memory[(cache+((layer*2*NC+position)*KV+i)*4)>>4]=k;
        memory[(cache+(((layer*2+1)*NC+position)*KV+i)*4)>>4]=v;
    }
}
static void attention(word *memory,unsigned layer,unsigned position,uint32_t cache,unsigned b) {
#pragma HLS INLINE off
    float score[NC],mass[NC],acc[HD];
#pragma HLS ARRAY_PARTITION variable=acc cyclic factor=4
    // Buffer one KV head once, serving both grouped query heads from URAM.
    // Explicit contiguous row loads permit AXI bursts instead of scalar loads
    // in the floating-point recurrence loop.
    static word key_rows[NC*32],value_rows[NC*32];
#pragma HLS BIND_STORAGE variable=key_rows type=ram_2p impl=uram
#pragma HLS BIND_STORAGE variable=value_rows type=ram_2p impl=uram
    for(unsigned kvhead=0;kvhead<NK;kvhead++) {
        for(unsigned t=0;t<=position;t++) {
            uint32_t kbase=(cache+((layer*2*NC+t)*KV+kvhead*HD)*4)>>4;
            uint32_t vbase=(cache+(((layer*2+1)*NC+t)*KV+kvhead*HD)*4)>>4;
            for(unsigned d=0;d<32;d++) {
#pragma HLS PIPELINE II=1
                key_rows[t*32+d]=memory[kbase+d];
            }
            for(unsigned d=0;d<32;d++) {
#pragma HLS PIPELINE II=1
                value_rows[t*32+d]=memory[vbase+d];
            }
        }
        for(unsigned group=0;group<NH/NK;group++) {
        unsigned head=kvhead*(NH/NK)+group;float max_score=-FLT_MAX;
        for(unsigned t=0;t<=position;t++) {
            float parts[4]={0,0,0,0};
#pragma HLS ARRAY_PARTITION variable=parts complete
            for(unsigned d=0;d<HD;d+=4) {
#pragma HLS PIPELINE
                word row=key_rows[t*32+d/4];
                for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
                    parts[lane]+=activation[b][QOFF+head*HD+d+lane]*asfloat(row.range(32*lane+31,32*lane).to_uint());
                }
            }
            float value=((parts[0]+parts[1])+(parts[2]+parts[3]))*0.08838834764831845f;
            score[t]=value;if(value>max_score)max_score=value;
        }
        float total=0;
        for(unsigned t=0;t<=position;t++) {
#pragma HLS PIPELINE
            float e=hls::expf(score[t]-max_score);mass[t]=e;total+=e;
        }
        for(unsigned d=0;d<HD;d++)acc[d]=0;
        for(unsigned t=0;t<=position;t++) {
            for(unsigned d=0;d<HD;d+=4) {
#pragma HLS PIPELINE
                word row=value_rows[t*32+d/4];
                for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
                    acc[d+lane]+=mass[t]*asfloat(row.range(32*lane+31,32*lane).to_uint());
                }
            }
        }
        float inverse=1.0f/total;
        for(unsigned d=0;d<HD;d++) {
#pragma HLS PIPELINE
            activation[b][COFF+head*HD+d]=acc[d]*inverse;
        }
    }
    }
}
extern "C" void qwen_decoder(word *model,word *scratch,unsigned cmd,uint32_t page,uint32_t cache,
                             uint32_t rotary,uint32_t result,unsigned layer,unsigned position,
                             unsigned rows,unsigned token_base,unsigned &status) {
#pragma HLS INTERFACE m_axi port=model offset=slave bundle=weights depth=134217728 max_read_burst_length=64 num_read_outstanding=8
#pragma HLS INTERFACE m_axi port=scratch offset=slave bundle=state depth=16777216 max_read_burst_length=64 num_read_outstanding=2 max_write_burst_length=64 num_write_outstanding=2
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
#pragma HLS ARRAY_PARTITION variable=activation complete dim=1
#pragma HLS ARRAY_PARTITION variable=activation cyclic factor=4 dim=2
#pragma HLS BIND_STORAGE variable=activation type=ram_t2p impl=uram
#pragma HLS ARRAY_PARTITION variable=dotinput complete dim=1
#pragma HLS ARRAY_PARTITION variable=dotinput cyclic factor=32 dim=2
#pragma HLS ARRAY_PARTITION variable=dotoutput complete dim=1
#pragma HLS BIND_STORAGE variable=dotinput type=ram_t2p impl=bram
#pragma HLS BIND_STORAGE variable=dotoutput type=ram_t2p impl=bram
    float norm_gamma[H],ffn_gamma[H],query_gamma[HD],key_gamma[HD];
#pragma HLS ARRAY_PARTITION variable=norm_gamma cyclic factor=4
#pragma HLS ARRAY_PARTITION variable=ffn_gamma cyclic factor=4
#pragma HLS ARRAY_PARTITION variable=query_gamma cyclic factor=4
#pragma HLS ARRAY_PARTITION variable=key_gamma cyclic factor=4
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
        if(batch==0 || batch>B || (cmd==7 && page>0x10000000u-16)){status=10;return;}
        for(unsigned b=0;b<batch;b++) {
            unsigned logical=cmd==7?loadu(scratch,page+4*b):page;
            if(logical>model_extent || model_extent-logical<EMBED_BYTES){status=3;return;}
            ap_uint<384> window=0;unsigned available=0;
            for(unsigned block=0;block<H/32;block++) {
                for(unsigned beat=0;beat<3;beat++)if(available<34) {
                    window|=ap_uint<384>(model[model_address(logical)>>4])<<(available*8);logical+=16;available+=16;
                }
                float scale=half_to_float(window.range(15,0));
                for(unsigned lane=0;lane<32;lane++) {
#pragma HLS UNROLL
                    ap_int<8> w=window.range(16+lane*8+7,16+lane*8);activation[b][XOFF+32*block+lane]=scale*float(w.to_int());
                }
                window>>=272;available-=34;
            }
        }
    } else if(cmd==2 || cmd==8 || cmd==4) {
        bool decoder=cmd!=4;unsigned batch=cmd==8?rows:1;uint32_t offsets[11];
        if(batch==0 || batch>B){status=10;return;}
        if(decoder) {
            if(layer>=NL || position>=NC || batch>NC-position || cache>0x10000000u-NL*2*NC*KV*4 || rotary>0x10000000u-NC*512 || page>0x10000000u-44){status=4;return;}
            for(unsigned i=0;i<11;i++)offsets[i]=loadu(scratch,page+4*i);
            for(unsigned i=0;i<11;i++) {
                unsigned length=i==0||i==3?Q*H/32*34:i==1||i==2?KV*H/32*34:i<7?F*H/32*34:i<9?H*4:HD*4;
                if(offsets[i]>model_extent || model_extent-offsets[i]<length){status=5;return;}
            }
            load_gamma(model,offsets[7],norm_gamma,H);
            load_gamma(model,offsets[8],ffn_gamma,H);
            load_gamma(model,offsets[9],query_gamma,HD);
            load_gamma(model,offsets[10],key_gamma,HD);
            for(unsigned b=0;b<batch;b++)rms(activation[b]+XOFF,activation[b]+NOFF,H,norm_gamma);
        } else {
            if(rows==0 || rows>8192 || token_base+rows>VOCAB || result>0x10000000u-16 || page>model_extent || model_extent-page<rows*(H/32)*34){status=6;return;}
            if(token_base==0){best_logit=-FLT_MAX;best_token=0;}
        }
        for(unsigned op=0;op<(decoder?7u:1u);op++) {
            unsigned input=NOFF,output=POFF,columns=H,outputs=H;uint32_t weights=page;
            if(decoder) {
                weights=offsets[op];
                if(op==0){output=QOFF;outputs=Q;}
                if(op==1){output=KOFF;outputs=KV;}
                if(op==2){output=VOFF;outputs=KV;}
                if(op==3) {
                    // Append/attend in token order: no future batch token is visible.
                    for(unsigned b=0;b<batch;b++) {
                        for(unsigned head=0;head<NH;head++)rms(activation[b]+QOFF+head*HD,activation[b]+QOFF+head*HD,HD,query_gamma);
                        for(unsigned head=0;head<NK;head++)rms(activation[b]+KOFF+head*HD,activation[b]+KOFF+head*HD,HD,key_gamma);
                        load_rotary(scratch,position+b,rotary,cosine,sine);
                        rope(activation[b]+QOFF,NH,cosine,sine);rope(activation[b]+KOFF,NK,cosine,sine);
                        append_kv(scratch,layer,position+b,cache,b);attention(scratch,layer,position+b,cache,b);
                    }
                    input=COFF;columns=Q;
                }
                if(op==4) {
                    for(unsigned b=0;b<batch;b++) {
                        for(unsigned i=0;i<H;i++)activation[b][XOFF+i]+=activation[b][POFF+i];
                        rms(activation[b]+XOFF,activation[b]+NOFF,H,ffn_gamma);
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
            for(unsigned b=0;b<batch;b++)for(unsigned i=0;i<columns;i++) {
#pragma HLS PIPELINE
                dotinput[b][i]=activation[b][input+i];
            }
            matvec(model,weights,dotinput,dotoutput,outputs,columns,batch,token_base,!decoder,best_logit,best_token);
            if(decoder)for(unsigned b=0;b<batch;b++)for(unsigned i=0;i<outputs;i++) {
#pragma HLS PIPELINE
                activation[b][output+i]=dotoutput[b][i];
            }
        }
        if(decoder)for(unsigned b=0;b<batch;b++)for(unsigned i=0;i<H;i++)activation[b][XOFF+i]+=activation[b][POFF+i];
        else {word out=0;out.range(31,0)=best_token;out.range(63,32)=asbits(best_logit);scratch[result>>4]=out;}
    } else if(cmd==3) {
        if(page>model_extent || model_extent-page<H*4){status=7;return;}
        load_gamma(model,page,norm_gamma,H);
        rms(activation[0]+XOFF,activation[0]+NOFF,H,norm_gamma);
    } else if(cmd==9) {
        if(layer>=B){status=10;return;}
        for(unsigned i=0;i<H;i++) {
#pragma HLS PIPELINE
            activation[0][XOFF+i]=activation[layer][XOFF+i];
        }
    } else if(cmd==5 || cmd==6 || cmd==10) {
        unsigned b=cmd==10?layer:0;
        if(b>=B || result>0x10000000u-H*4){status=8;return;}
        for(unsigned i=0;i<H;i+=4) {
#pragma HLS PIPELINE
            word out;
            for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
                out.range(32*lane+31,32*lane)=asbits(activation[b][(cmd==6?NOFF:XOFF)+i+lane]);
            }
            scratch[(result+i*4)>>4]=out;
        }
    } else status=9;
}
