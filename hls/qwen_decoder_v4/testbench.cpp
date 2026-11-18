#include <ap_int.h>
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
int main(int argc,char**argv){
 try{
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
