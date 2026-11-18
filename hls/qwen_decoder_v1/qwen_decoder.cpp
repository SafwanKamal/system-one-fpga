#include <ap_int.h>
#include <hls_stream.h>
#include <hls_math.h>

#include <stdint.h>
#include <float.h>

using word = ap_uint<128>;
static const unsigned H=1024, Q=2048, F=3072, HD=128, NH=16, NK=8, NC=256;
static const unsigned CHUNK_BITS=24;
static uint32_t model_pages[64];
static unsigned page_count=0;
static float hidden[H], normed[H], query[Q], keyvec[H], valuevec[H];
static float context[Q], gate[F], up[F], projected[H];
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
static void compute_matvec(hls::stream<word>& stream,const float *input,float *output,
                           unsigned rows,unsigned cols,unsigned token_base,bool vocabulary,
                           float &maximum,uint32_t &token) {
#pragma HLS INLINE off
    float local_max=maximum;uint32_t local_token=token;
    ap_uint<384> window=0;unsigned available=0;
    for(unsigned r=0;r<rows;r++) {
        float partial[8]={0,0,0,0,0,0,0,0};
#pragma HLS ARRAY_PARTITION variable=partial complete
        for(unsigned block=0;block<cols/32;block++) {
#pragma HLS PIPELINE II=4
            // Q8_0 block: little-endian half scale, then 32 signed bytes.
            for(unsigned beat=0;beat<3;beat++) {
                if(available<34) {
                    word next=stream.read();window |= ap_uint<384>(next) << (available*8);available+=16;
                }
            }
            float scale=half_to_float(window.range(15,0));
            float tree[32];
#pragma HLS ARRAY_PARTITION variable=tree complete
            for(unsigned lane=0;lane<32;lane++) {
#pragma HLS UNROLL
                ap_int<8> w=window.range(16+lane*8+7,16+lane*8);
                tree[lane]=float(w.to_int())*input[block*32+lane];
            }
            for(unsigned stride=16;stride;stride>>=1) {
#pragma HLS UNROLL
                for(unsigned lane=0;lane<16;lane++) {
#pragma HLS UNROLL
                    if(lane<stride)tree[lane]=tree[lane]+tree[lane+stride];
                }
            }
            partial[block&7]+=tree[0]*scale;
            window>>=272;available-=34;
        }
        float sum=((partial[0]+partial[1])+(partial[2]+partial[3]))+
                  ((partial[4]+partial[5])+(partial[6]+partial[7]));
        if(vocabulary) {
            if(sum>local_max || (sum==local_max && token_base+r<local_token)) {
                local_max=sum;local_token=token_base+r;
            }
        } else if(r<F)output[r]=sum;
    }
    maximum=local_max;token=local_token;
}
static void matvec(word *memory,uint32_t logical,const float *input,float *output,
                   unsigned rows,unsigned cols,unsigned token_base,bool vocabulary,
                   float &maximum,uint32_t &token) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
    hls::stream<word> weights("weights");
#pragma HLS STREAM variable=weights depth=64
    load_model(memory,logical,(rows*(cols/32)*34)/16,weights);
    compute_matvec(weights,input,output,rows,cols,token_base,vocabulary,maximum,token);
}
static void rms(word *memory,const float *input,float *output,unsigned n,uint32_t gamma) {
#pragma HLS INLINE off
    float squares=0;
    for(unsigned i=0;i<n;i++) {
#pragma HLS PIPELINE
        squares+=input[i]*input[i];
    }
    float inverse=1.0f/hls::sqrtf(squares/float(n)+1.0e-6f);
    for(unsigned i=0;i<n;i++) {
#pragma HLS PIPELINE
        output[i]=input[i]*inverse*modelf(memory,gamma+4*i);
    }
}
static void rope(word *memory,float *data,unsigned heads,unsigned position,uint32_t table) {
#pragma HLS INLINE off
    for(unsigned head=0;head<heads;head++) {
        for(unsigned i=0;i<64;i++) {
#pragma HLS PIPELINE
            float c=loadf(memory,table+position*512+i*4);
            float s=loadf(memory,table+position*512+256+i*4);
            float a=data[head*128+i],b=data[head*128+i+64];
            data[head*128+i]=a*c-b*s;data[head*128+i+64]=b*c+a*s;
        }
    }
}
static void append_kv(word *memory,unsigned layer,unsigned position,uint32_t cache) {
#pragma HLS INLINE off
    for(unsigned i=0;i<H;i+=4) {
#pragma HLS PIPELINE II=1
        word k,v;
        for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
            k.range(32*lane+31,32*lane)=asbits(keyvec[i+lane]);
            v.range(32*lane+31,32*lane)=asbits(valuevec[i+lane]);
        }
        memory[(cache+((layer*2*NC+position)*H+i)*4)>>4]=k;
        memory[(cache+(((layer*2+1)*NC+position)*H+i)*4)>>4]=v;
    }
}
static void attention(word *memory,unsigned layer,unsigned position,uint32_t cache) {
#pragma HLS INLINE off
    float score[NC],mass[NC],acc[HD];
#pragma HLS ARRAY_PARTITION variable=acc cyclic factor=4
    for(unsigned head=0;head<NH;head++) {
        unsigned kvhead=head/2;float max_score=-FLT_MAX;
        for(unsigned t=0;t<=position;t++) {
            float parts[4]={0,0,0,0};
#pragma HLS ARRAY_PARTITION variable=parts complete
            for(unsigned d=0;d<HD;d+=4) {
#pragma HLS PIPELINE
                word row=memory[(cache+((layer*2*NC+t)*H+kvhead*HD+d)*4)>>4];
                for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
                    parts[lane]+=query[head*HD+d+lane]*asfloat(row.range(32*lane+31,32*lane).to_uint());
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
                word row=memory[(cache+(((layer*2+1)*NC+t)*H+kvhead*HD+d)*4)>>4];
                for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
                    acc[d+lane]+=mass[t]*asfloat(row.range(32*lane+31,32*lane).to_uint());
                }
            }
        }
        float inverse=1.0f/total;
        for(unsigned d=0;d<HD;d++) {
#pragma HLS PIPELINE
            context[head*HD+d]=acc[d]*inverse;
        }
    }
}
extern "C" void qwen_decoder(word *memory,unsigned cmd,uint32_t page,uint32_t cache,
                             uint32_t rotary,uint32_t result,unsigned layer,unsigned position,
                             unsigned rows,unsigned token_base,unsigned &status) {
#pragma HLS INTERFACE m_axi port=memory offset=slave bundle=ddr depth=134217728 max_read_burst_length=256 num_read_outstanding=16 max_write_burst_length=256
#pragma HLS INTERFACE s_axilite port=memory bundle=control offset=0x10
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
#pragma HLS ARRAY_PARTITION variable=hidden cyclic factor=32
#pragma HLS ARRAY_PARTITION variable=normed cyclic factor=32
#pragma HLS ARRAY_PARTITION variable=context cyclic factor=32
#pragma HLS ARRAY_PARTITION variable=gate cyclic factor=32
#pragma HLS ARRAY_PARTITION variable=up cyclic factor=32
#pragma HLS ARRAY_PARTITION variable=query cyclic factor=4
#pragma HLS ARRAY_PARTITION variable=keyvec cyclic factor=4
#pragma HLS ARRAY_PARTITION variable=valuevec cyclic factor=4
#pragma HLS ALLOCATION function instances=matvec limit=1
#pragma HLS ALLOCATION function instances=rms limit=1
    status=0;
    if(cmd==0) {
        if(rows==0 || rows>64){status=1;return;}
        for(unsigned i=0;i<rows;i++)model_pages[i]=loadu(memory,page+4*i);
        page_count=rows;return;
    }
    if(page_count==0){status=2;return;}
    float unused=0;uint32_t unused_id=0;
    if(cmd==1) {
        // The embedding row is exactly 32 Q8_0 blocks = 1088 bytes.
        ap_uint<384> window=0;unsigned available=0;unsigned logical=page;
        for(unsigned block=0;block<32;block++) {
            for(unsigned beat=0;beat<3;beat++)if(available<34) {
                window|=ap_uint<384>(memory[model_address(logical)>>4])<<(available*8);logical+=16;available+=16;
            }
            float scale=half_to_float(window.range(15,0));
            for(unsigned lane=0;lane<32;lane++) {
#pragma HLS UNROLL
                ap_int<8> w=window.range(16+lane*8+7,16+lane*8);hidden[32*block+lane]=scale*float(w.to_int());
            }
            window>>=272;available-=34;
        }
    } else if(cmd==2) {
        if(layer>=28 || position>=NC){status=3;return;}
        uint32_t offsets[11];
        for(unsigned i=0;i<11;i++)offsets[i]=loadu(memory,page+i*4);
        rms(memory,hidden,normed,H,offsets[7]);
        matvec(memory,offsets[0],normed,query,Q,H,0,false,unused,unused_id);
        matvec(memory,offsets[1],normed,keyvec,H,H,0,false,unused,unused_id);
        matvec(memory,offsets[2],normed,valuevec,H,H,0,false,unused,unused_id);
        for(unsigned h=0;h<NH;h++)rms(memory,query+h*HD,query+h*HD,HD,offsets[9]);
        for(unsigned h=0;h<NK;h++)rms(memory,keyvec+h*HD,keyvec+h*HD,HD,offsets[10]);
        rope(memory,query,NH,position,rotary);rope(memory,keyvec,NK,position,rotary);
        append_kv(memory,layer,position,cache);attention(memory,layer,position,cache);
        matvec(memory,offsets[3],context,projected,H,Q,0,false,unused,unused_id);
        for(unsigned i=0;i<H;i++)hidden[i]+=projected[i];
        rms(memory,hidden,normed,H,offsets[8]);
        matvec(memory,offsets[4],normed,gate,F,H,0,false,unused,unused_id);
        matvec(memory,offsets[5],normed,up,F,H,0,false,unused,unused_id);
        for(unsigned i=0;i<F;i++) {
#pragma HLS PIPELINE
            gate[i]=(gate[i]/(1.0f+hls::expf(-gate[i])))*up[i];
        }
        matvec(memory,offsets[6],gate,projected,H,F,0,false,unused,unused_id);
        for(unsigned i=0;i<H;i++)hidden[i]+=projected[i];
    } else if(cmd==3) {
        rms(memory,hidden,normed,H,page);
    } else if(cmd==4) {
        if(rows==0 || rows>8192 || token_base+rows>151936){status=4;return;}
        if(token_base==0){best_logit=-FLT_MAX;best_token=0;}
        matvec(memory,page,normed,projected,rows,H,token_base,true,best_logit,best_token);
        word out=0;out.range(31,0)=best_token;out.range(63,32)=asbits(best_logit);memory[result>>4]=out;
    } else if(cmd==5 || cmd==6) {
        for(unsigned i=0;i<H;i+=4) {
#pragma HLS PIPELINE
            word out;
            for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
                out.range(32*lane+31,32*lane)=asbits(cmd==5?hidden[i+lane]:normed[i+lane]);
            }
            memory[(result+i*4)>>4]=out;
        }
    } else status=5;
}
