#include <ap_int.h>
#include <hls_stream.h>
#include <vector>
#include <fstream>
#include <iostream>
#include <cmath>
#include <cstring>
#include <string>
#include <algorithm>
using word=ap_uint<128>;
extern "C" void qwen_decoder(word*,word*,unsigned,uint32_t,uint32_t,uint32_t,uint32_t,unsigned,unsigned,unsigned,unsigned,unsigned&);
static void putu(std::vector<word>&m,unsigned a,uint32_t v){unsigned lo=(a&15)*8;m[a/16].range(lo+31,lo)=v;}
static float getf(std::vector<word>&m,unsigned a){uint32_t v=(m[a/16]>>((a&15)*8)).range(31,0).to_uint();float f;std::memcpy(&f,&v,4);return f;}
static std::vector<char> read(const std::string&p){std::ifstream f(p,std::ios::binary|std::ios::ate);if(!f)throw std::runtime_error(p);size_t n=f.tellg();f.seekg(0);std::vector<char>b(n);f.read(b.data(),n);return b;}
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
#include "matrix_q8.hpp"
// Same core instantiated at larger capacity, without a second model deployment.
static void portability(unsigned columns) {
 const unsigned rows=16;static float input[4][6144],output[4][6144];float expected[4][16]={};
 std::vector<word> packed(rows*(columns/32)*34/16);
 unsigned cursor=0;
 for(unsigned b=0;b<4;b++)for(unsigned i=0;i<columns;i++)input[b][i]=float((int(i%13)-6)*int(b+1))/32.0f;
 for(unsigned r=0;r<rows;r++)for(unsigned block=0;block<columns/32;block++) {
  for(unsigned byte=0;byte<34;byte++) {
   int value=byte==0?0:byte==1?0x3c:int((r*7+block*3+byte-2)%17)-8;
   packed[cursor/16].range((cursor%16)*8+7,(cursor%16)*8)=uint8_t(value);cursor++;
   if(byte>=2)for(unsigned b=0;b<4;b++)expected[b][r]+=float(value)*input[b][block*32+byte-2];
  }
 }
 hls::stream<word> words;hls::stream<q8_block> blocks;
 for(auto v:packed)words.write(v);unpack_q8(words,packed.size(),blocks);
 float maximum=-1e30f;uint32_t token=0;
 compute_q8<4,6144>(blocks,input,output,rows,columns,4,700,false,maximum,token);
 for(unsigned b=0;b<4;b++)for(unsigned r=0;r<rows;r++)if(std::abs(output[b][r]-expected[b][r])>0.0001f)throw std::runtime_error("portable matrix mismatch");
 for(auto v:packed)words.write(v);unpack_q8(words,packed.size(),blocks);
 compute_q8<4,6144>(blocks,input,output,rows,columns,1,700,true,maximum,token);
 unsigned best=0;for(unsigned r=1;r<rows;r++)if(expected[0][r]>expected[0][best])best=r;
 if(token!=700+best || std::abs(maximum-expected[0][best])>0.0001f)throw std::runtime_error("portable argmax mismatch");
 std::cout<<"PASS portable matrix columns="<<columns<<" capacity=6144 full4 and full-vocabulary reduction"<<std::endl;
}

int main(int argc,char**argv){
 try{
  portability(2048);portability(6144);portability(1056);
  if(argc!=2)throw std::runtime_error("fixture directory required");std::string dir=argv[1];auto b=read(dir+"/model.bin");auto mb=read(dir+"/metadata.bin");uint32_t meta[19];std::memcpy(meta,mb.data(),sizeof(meta));
  std::vector<word>model((48u<<20)/16),scratch((4u<<20)/16);
  for(unsigned i=0;i<b.size();i+=16){unsigned physical=i<(16u<<20)?i:(32u<<20)+(i&((16u<<20)-1));word v;for(unsigned lane=0;lane<4;lane++){uint32_t x;std::memcpy(&x,b.data()+i+lane*4,4);v.range(lane*32+31,lane*32)=x;}model[physical/16]=v;}
  putu(scratch,0,0);putu(scratch,4,32u<<20);for(unsigned i=0;i<11;i++)putu(scratch,0x400+i*4,meta[5+i]);
  auto rope=read(dir+"/../rope.bin");for(unsigned i=0;i<rope.size();i+=4){uint32_t v;std::memcpy(&v,rope.data()+i,4);putu(scratch,0x1000+i,v);}
  unsigned status=99;
  auto call=[&](unsigned c,unsigned p,unsigned pos=0,unsigned rows=0,unsigned tokenbase=0,unsigned lane=0){qwen_decoder(model.data(),scratch.data(),c,p,0x100000,0x1000,0x30000,lane,pos,rows,tokenbase,status);if(status)throw std::runtime_error("kernel status "+std::to_string(status));};
  call(0,0,0,2,meta[0]);double worst=0;
  auto batch=[&](unsigned start,unsigned count){
   for(unsigned i=0;i<count;i++)putu(scratch,0x600+4*i,meta[1+start+i]);
   call(7,0x600,start,count);call(8,0x400,start,count);
   for(unsigned b=0;b<count;b++) {
    call(10,0,0,0,0,b);auto expected=read(dir+"/expected-"+std::to_string(start+b)+".bin");double squares=0,maxerr=0;
    for(unsigned i=0;i<1024;i++){float x;std::memcpy(&x,expected.data()+4*i,4);double d=std::abs(getf(scratch,0x30000+4*i)-x);if(!std::isfinite(d))throw std::runtime_error("nonfinite result");squares+=d*d;maxerr=std::max(maxerr,d);}
    std::cout<<"batch="<<count<<" position="<<start+b<<" max_abs="<<maxerr<<" rmse="<<std::sqrt(squares/1024)<<std::endl;worst=std::max(worst,maxerr);if(maxerr>0.002)throw std::runtime_error("batched decoder mismatch");
   }
  };
  batch(0,4); // All four parallel lanes.
  batch(0,1);batch(1,3); // Partial final group and nonzero causal position.
  call(9,0,0,0,0,2); // Select final token from the three-lane group.
  call(3,meta[16]);call(6,0);auto expected=read(dir+"/normalized-3.bin");double maxerr=0;
  for(unsigned i=0;i<1024;i++){float x;std::memcpy(&x,expected.data()+4*i,4);maxerr=std::max(maxerr,double(std::abs(getf(scratch,0x30000+4*i)-x)));}
  if(maxerr>0.002)throw std::runtime_error("final norm mismatch");
  call(4,meta[17],0,32,0);unsigned token=scratch[0x30000/16].range(31,0).to_uint();if(token!=meta[18])throw std::runtime_error("vocabulary argmax mismatch");
  std::cout<<"PASS four real Q8 batch lanes, partial batch and sequential causal equivalence, causal KV/GQA/RoPE/SwiGLU, final norm, argmax="<<token<<", scatter boundary, worst="<<worst<<std::endl;return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 1;}
}
