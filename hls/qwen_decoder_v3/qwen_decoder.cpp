#include <ap_int.h>
#include <hls_stream.h>
#include <hls_math.h>
#include <stdint.h>
#include <float.h>
using word=ap_uint<128>;
static const unsigned H=1024,Q=2048,F=3072,HD=128,NH=16,NK=8,NC=256;
static const unsigned CHUNK_BITS=24;
static const unsigned XOFF=0,NOFF=1024,QOFF=2048,KOFF=4096,VOFF=5120;
static const unsigned COFF=6144,POFF=8192,GOFF=9216,UOFF=12288,ACT=15360;
static uint32_t model_pages[64];
static unsigned page_count=0,model_extent=0;
static float activation[ACT],dotinput[F],dotoutput[F];
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
#pragma HLS PIPELINE II=3
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
            k.range(32*lane+31,32*lane)=asbits(activation[KOFF+i+lane]);
            v.range(32*lane+31,32*lane)=asbits(activation[VOFF+i+lane]);
        }
        memory[(cache+((layer*2*NC+position)*H+i)*4)>>4]=k;
        memory[(cache+(((layer*2+1)*NC+position)*H+i)*4)>>4]=v;
    }
}
static void attention(word *memory,unsigned layer,unsigned position,uint32_t cache) {
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
            uint32_t kbase=(cache+((layer*2*NC+t)*H+kvhead*HD)*4)>>4;
            uint32_t vbase=(cache+(((layer*2+1)*NC+t)*H+kvhead*HD)*4)>>4;
            for(unsigned d=0;d<32;d++) {
#pragma HLS PIPELINE II=1
                key_rows[t*32+d]=memory[kbase+d];
            }
            for(unsigned d=0;d<32;d++) {
#pragma HLS PIPELINE II=1
                value_rows[t*32+d]=memory[vbase+d];
            }
        }
        for(unsigned group=0;group<2;group++) {
        unsigned head=kvhead*2+group;float max_score=-FLT_MAX;
        for(unsigned t=0;t<=position;t++) {
            float parts[4]={0,0,0,0};
#pragma HLS ARRAY_PARTITION variable=parts complete
            for(unsigned d=0;d<HD;d+=4) {
#pragma HLS PIPELINE
                word row=key_rows[t*32+d/4];
                for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
                    parts[lane]+=activation[QOFF+head*HD+d+lane]*asfloat(row.range(32*lane+31,32*lane).to_uint());
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
            activation[COFF+head*HD+d]=acc[d]*inverse;
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
#pragma HLS ARRAY_PARTITION variable=activation cyclic factor=4
#pragma HLS BIND_STORAGE variable=activation type=ram_t2p impl=bram
#pragma HLS ARRAY_PARTITION variable=dotinput cyclic factor=32
#pragma HLS BIND_STORAGE variable=dotinput type=ram_t2p impl=bram
#pragma HLS BIND_STORAGE variable=dotoutput type=ram_t2p impl=bram
    status=0;
    if(cmd==0) {
        if(rows==0 || rows>64 || token_base==0 || token_base>rows*(1u<<CHUNK_BITS)) {status=1;return;}
        for(unsigned i=0;i<rows;i++)model_pages[i]=loadu(scratch,page+4*i);
        page_count=rows;model_extent=token_base;return;
    }
    if(page_count==0){status=2;return;}
    if(cmd==1) {
        if(page>model_extent || model_extent-page<1088){status=3;return;}
        ap_uint<384> window=0;unsigned available=0;unsigned logical=page;
        for(unsigned block=0;block<32;block++) {
            for(unsigned beat=0;beat<3;beat++)if(available<34) {
                window|=ap_uint<384>(model[model_address(logical)>>4])<<(available*8);logical+=16;available+=16;
            }
            float scale=half_to_float(window.range(15,0));
            for(unsigned lane=0;lane<32;lane++) {
#pragma HLS UNROLL
                ap_int<8> w=window.range(16+lane*8+7,16+lane*8);activation[XOFF+32*block+lane]=scale*float(w.to_int());
            }
            window>>=272;available-=34;
        }
    } else if(cmd==2 || cmd==4) {
        uint32_t offsets[11];
        if(cmd==2) {
            if(layer>=28 || position>=NC || cache>0x10000000u-28*2*NC*H*4 || rotary>0x10000000u-NC*512 || page>0x10000000u-44){status=4;return;}
            for(unsigned i=0;i<11;i++)offsets[i]=loadu(scratch,page+4*i);
            for(unsigned i=0;i<11;i++) {
                unsigned length=i==0||i==3?Q*H/32*34:i==1||i==2?H*H/32*34:i<7?F*H/32*34:i<9?H*4:HD*4;
                if(offsets[i]>model_extent || model_extent-offsets[i]<length){status=5;return;}
            }
            rms(model,activation+XOFF,activation+NOFF,H,offsets[7]);
        } else {
            if(rows==0 || rows>8192 || token_base+rows>151936 || result>0x10000000u-16 || page>model_extent || model_extent-page<rows*(H/32)*34){status=6;return;}
            if(token_base==0){best_logit=-FLT_MAX;best_token=0;}
        }
        unsigned operations=cmd==2?7:1;
        for(unsigned op=0;op<operations;op++) {
            unsigned input=NOFF,output=POFF,columns=H,outputs=H;
            uint32_t weights=page;
            if(cmd==2) {
                weights=offsets[op];
                if(op==0){output=QOFF;outputs=Q;}
                if(op==1)output=KOFF;
                if(op==2)output=VOFF;
                if(op==3) {
                    for(unsigned head=0;head<NH;head++)rms(model,activation+QOFF+head*HD,activation+QOFF+head*HD,HD,offsets[9]);
                    for(unsigned head=0;head<NK;head++)rms(model,activation+KOFF+head*HD,activation+KOFF+head*HD,HD,offsets[10]);
                    rope(scratch,activation+QOFF,NH,position,rotary);rope(scratch,activation+KOFF,NK,position,rotary);
                    append_kv(scratch,layer,position,cache);attention(scratch,layer,position,cache);
                    input=COFF;columns=Q;
                }
                if(op==4) {
                    for(unsigned i=0;i<H;i++)activation[XOFF+i]+=activation[POFF+i];
                    rms(model,activation+XOFF,activation+NOFF,H,offsets[8]);output=GOFF;outputs=F;
                }
                if(op==5){output=UOFF;outputs=F;}
                if(op==6) {
                    for(unsigned i=0;i<F;i++) {
#pragma HLS PIPELINE
                        float g=activation[GOFF+i];activation[GOFF+i]=(g/(1.0f+hls::expf(-g)))*activation[UOFF+i];
                    }
                    input=GOFF;columns=F;
                }
            } else outputs=rows;
            for(unsigned i=0;i<columns;i++) {
#pragma HLS PIPELINE
                dotinput[i]=activation[input+i];
            }
            // One call site, one pair of buffers: HLS cannot clone the GEMV
            // datapath merely because layer projections use different arrays.
            matvec(model,weights,dotinput,dotoutput,outputs,columns,token_base,cmd==4,best_logit,best_token);
            if(cmd==2)for(unsigned i=0;i<outputs;i++) {
#pragma HLS PIPELINE
                activation[output+i]=dotoutput[i];
            }
        }
        if(cmd==2)for(unsigned i=0;i<H;i++)activation[XOFF+i]+=activation[POFF+i];
        else {word out=0;out.range(31,0)=best_token;out.range(63,32)=asbits(best_logit);scratch[result>>4]=out;}
    } else if(cmd==3) {
        if(page>model_extent || model_extent-page<H*4){status=7;return;}
        rms(model,activation+XOFF,activation+NOFF,H,page);
    } else if(cmd==5 || cmd==6) {
        if(result>0x10000000u-H*4){status=8;return;}
        for(unsigned i=0;i<H;i+=4) {
#pragma HLS PIPELINE
            word out;
            for(unsigned lane=0;lane<4;lane++) {
#pragma HLS UNROLL
                out.range(32*lane+31,32*lane)=asbits(activation[(cmd==5?XOFF:NOFF)+i+lane]);
            }
            scratch[(result+i*4)>>4]=out;
        }
    } else status=9;
}
