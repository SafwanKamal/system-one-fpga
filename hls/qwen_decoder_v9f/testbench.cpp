#include <ap_int.h>
#include <hls_stream.h>
#include <vector>
#include <fstream>
#include <iostream>
#include <cmath>
#include <cstring>
#include <string>
#include <algorithm>
using word=ap_uint<256>;
using weight_word=ap_uint<256>;
extern "C" void qwen_decoder(weight_word*,word*,unsigned,uint32_t,uint32_t,uint32_t,uint32_t,unsigned,unsigned,unsigned,unsigned,unsigned&);
static void putu(std::vector<word>&m,unsigned a,uint32_t v){unsigned lo=(a&31)*8;m[a/32].range(lo+31,lo)=v;}
static float getf(std::vector<word>&m,unsigned a){uint32_t v=(m[a/32]>>((a&31)*8)).range(31,0).to_uint();float f;std::memcpy(&f,&v,4);return f;}
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
 std::vector<ap_uint<128>> packed(rows*(columns/32)*34/16);
 unsigned cursor=0;
 for(unsigned b=0;b<4;b++)for(unsigned i=0;i<columns;i++)input[b][i]=float((int(i%13)-6)*int(b+1))/32.0f;
 for(unsigned r=0;r<rows;r++)for(unsigned block=0;block<columns/32;block++) {
  for(unsigned byte=0;byte<34;byte++) {
   int value=byte==0?0:byte==1?0x3c:int((r*7+block*3+byte-2)%17)-8;
   packed[cursor/16].range((cursor%16)*8+7,(cursor%16)*8)=uint8_t(value);cursor++;
   
  }
 }
 for(unsigned b=0;b<4;b++)for(unsigned r=0;r<rows;r++) {
  float partial[8]={};
  for(unsigned block=0;block<columns/32;block++) {
   float amax=0;for(unsigned i=0;i<32;i++)amax=std::max(amax,std::abs(input[b][block*32+i]));
   float scale=amax/127.0f,inv=scale==0?0:1.0f/scale;int dot=0;
   for(unsigned i=0;i<32;i++) {float v=input[b][block*32+i]*inv;int q=std::max(-127,std::min(127,int(v>=0?v+.5f:v-.5f)));dot+=(int((r*7+block*3+i)%17)-8)*q;}
   partial[block%8]+=float(dot)*scale;
  }
  expected[b][r]=((partial[0]+partial[1])+(partial[2]+partial[3]))+((partial[4]+partial[5])+(partial[6]+partial[7]));
 }
 hls::stream<ap_uint<128>> words;hls::stream<q8_block> blocks;
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


// v9e: causal positions of layer 0 across eight 256-row attention tiles (BF16 K/V) (five prefill groups, then the same
// positions again as single-token decode steps), beyond the 16-row score padding.
static void long_context(const std::string&dir) {
 auto b=read(dir+"/model.bin");auto mb=read(dir+"/metadata.bin");std::vector<uint32_t> meta(mb.size()/4);std::memcpy(meta.data(),mb.data(),mb.size());
 const unsigned n=meta[0];const uint32_t*embed=&meta[2];const uint32_t*off=&meta[2+n];
 std::vector<weight_word>model((48u<<20)/32);std::vector<word>scratch((16u<<20)/32);
 for(unsigned i=0;i<b.size();i+=32){unsigned physical=i<(16u<<20)?i:(32u<<20)+(i&((16u<<20)-1));weight_word v;for(unsigned lane=0;lane<8;lane++){uint32_t x=0;if(i+lane*4<b.size())std::memcpy(&x,b.data()+i+lane*4,4);v.range(lane*32+31,lane*32)=x;}model[physical/32]=v;}
 putu(scratch,0,0);putu(scratch,4,32u<<20);for(unsigned i=0;i<11;i++)putu(scratch,0x400+i*4,off[i]);
 auto rope=read(dir+"/../rope.bin");for(unsigned i=0;i<rope.size();i+=4){uint32_t v;std::memcpy(&v,rope.data()+i,4);putu(scratch,0x1000+i,v);}
 unsigned status=99;
 auto call=[&](unsigned c,unsigned p,unsigned pos=0,unsigned rows=0,unsigned tokenbase=0,unsigned lane=0){qwen_decoder(model.data(),scratch.data(),c,p,0x200000,0x1000,0x180000,lane,pos,rows,tokenbase,status);if(status)throw std::runtime_error("kernel status "+std::to_string(status));};
 call(0,0,0,2,meta[1]);double worst=0;
 auto check=[&](unsigned position,unsigned lane,const char*mode){
  call(10,0,0,0,0,lane);auto expected=read(dir+"/expected-"+std::to_string(position)+".bin");double maxerr=0;
  for(unsigned i=0;i<1024;i++){float x;std::memcpy(&x,expected.data()+4*i,4);double d=std::abs(getf(scratch,0x180000+4*i)-x);if(!std::isfinite(d))throw std::runtime_error("nonfinite result");maxerr=std::max(maxerr,d);}
  worst=std::max(worst,maxerr);if(maxerr>0.00002){std::cerr<<mode<<" position="<<position<<" max_abs="<<maxerr<<std::endl;throw std::runtime_error("long-context mismatch");}
 };
 for(unsigned start=0;start<n;start+=8){
  unsigned count=std::min(8u,n-start);
  for(unsigned i=0;i<count;i++)putu(scratch,0x600+4*i,embed[start+i]);
  call(7,0x600,start,count);call(8,0x400,start,count);
  for(unsigned i=0;i<count;i++)check(start+i,i,"prefill");
 }
 // Decode re-runs only the last eight positions (deepest causal span); every
 // position is already checked through prefill.
 for(unsigned position=n>8?n-8:0;position<n;position++){call(1,embed[position],position);call(2,0x400,position);check(position,0,"decode");}
 std::cout<<"PASS long context positions="<<n<<" prefill groups and final decode steps, worst="<<worst<<std::endl;
}
int main(int argc,char**argv){
 try{
  portability(2048);portability(6144);portability(1056);
  if(argc<2||argc>3)throw std::runtime_error("fixture directory [long-context fixture] required");std::string dir=argv[1];const double tolerance=0.00002;auto b=read(dir+"/model.bin");auto mb=read(dir+"/metadata.bin");uint32_t meta[23];std::memcpy(meta,mb.data(),sizeof(meta));
  std::vector<weight_word>model((48u<<20)/32);std::vector<word>scratch((16u<<20)/32);
  for(unsigned i=0;i<b.size();i+=32){unsigned physical=i<(16u<<20)?i:(32u<<20)+(i&((16u<<20)-1));weight_word v;for(unsigned lane=0;lane<8;lane++){uint32_t x;std::memcpy(&x,b.data()+i+lane*4,4);v.range(lane*32+31,lane*32)=x;}model[physical/32]=v;}
  putu(scratch,0,0);putu(scratch,4,32u<<20);for(unsigned i=0;i<11;i++)putu(scratch,0x400+i*4,meta[9+i]);
  auto rope=read(dir+"/../rope.bin");for(unsigned i=0;i<rope.size();i+=4){uint32_t v;std::memcpy(&v,rope.data()+i,4);putu(scratch,0x1000+i,v);}
  unsigned status=99;
  auto call=[&](unsigned c,unsigned p,unsigned pos=0,unsigned rows=0,unsigned tokenbase=0,unsigned lane=0){qwen_decoder(model.data(),scratch.data(),c,p,0x200000,0x1000,0x180000,lane,pos,rows,tokenbase,status);if(status)throw std::runtime_error("kernel status "+std::to_string(status));};
  call(0,0,0,2,meta[0]);double worst=0;
  auto batch=[&](unsigned start,unsigned count){
   for(unsigned i=0;i<count;i++)putu(scratch,0x600+4*i,meta[1+start+i]);
   call(7,0x600,start,count);call(8,0x400,start,count);
   for(unsigned b=0;b<count;b++) {
    call(10,0,0,0,0,b);auto expected=read(dir+"/expected-"+std::to_string(start+b)+".bin");double squares=0,maxerr=0;
    for(unsigned i=0;i<1024;i++){float x;std::memcpy(&x,expected.data()+4*i,4);double d=std::abs(getf(scratch,0x180000+4*i)-x);if(!std::isfinite(d))throw std::runtime_error("nonfinite result");squares+=d*d;maxerr=std::max(maxerr,d);}
    std::cout<<"batch="<<count<<" position="<<start+b<<" max_abs="<<maxerr<<" rmse="<<std::sqrt(squares/1024)<<std::endl;worst=std::max(worst,maxerr);if(maxerr>tolerance)throw std::runtime_error("batched decoder mismatch");
   }
  };
  batch(0,8); // All four parallel lanes.
  batch(0,1);batch(1,7); // Partial final group and nonzero causal position.
  call(9,0,0,0,0,6); // Select final token from the three-lane group.
  call(3,meta[20]);call(6,0);auto expected=read(dir+"/normalized-7.bin");double maxerr=0;
  for(unsigned i=0;i<1024;i++){float x;std::memcpy(&x,expected.data()+4*i,4);maxerr=std::max(maxerr,double(std::abs(getf(scratch,0x180000+4*i)-x)));}
  std::cout<<"final norm max_abs="<<maxerr<<std::endl;
  if(maxerr>tolerance)throw std::runtime_error("final norm mismatch");
  call(4,meta[21],0,32,0);unsigned token=scratch[0x180000/32].range(31,0).to_uint();if(token!=meta[22])throw std::runtime_error("vocabulary argmax mismatch");
  std::cout<<"PASS four real Q8 batch lanes, partial batch and sequential causal equivalence, causal KV/GQA/RoPE/SwiGLU, final norm, argmax="<<token<<", scatter boundary, worst="<<worst<<std::endl;if(argc==3)long_context(argv[2]);return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 1;}
}
