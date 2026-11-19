// v9f batched-head audit: cmd 11 + cmd 12 versus the v9e sequential head path
// (cmd 9, 3, 4) over the full vocabulary. See PROTOCOL.md.
// argv: <gguf> <meta.bin> <rope.bin> <v9e schedule-invariance results.json> <results.json>
#include <ap_int.h>
#include <hls_stream.h>
#include <vector>
#include <fstream>
#include <sstream>
#include <iostream>
#include <cstring>
#include <string>
#include <chrono>
#include <stdexcept>
#include <stdint.h>
#include <float.h>
using word=ap_uint<256>;
using weight_word=ap_uint<256>;
extern "C" void qwen_decoder(weight_word*,word*,unsigned,uint32_t,uint32_t,uint32_t,uint32_t,unsigned,unsigned,unsigned,unsigned,unsigned&);
// Direct reducer test: the v9f matrix core header, as the kernel compiles it.
static float asfloat(uint32_t value){union{uint32_t i;float f;}x;x.i=value;return x.f;}
static float half_to_float(ap_uint<16> value){
    uint32_t h=value.to_uint(),sign=(h&0x8000u)<<16,exponent=(h>>10)&31u,mantissa=h&1023u;
    if(exponent==0){if(mantissa==0)return asfloat(sign);unsigned shifts=0;for(unsigned i=0;i<10;i++)if((mantissa&1024u)==0){mantissa<<=1;shifts++;}return asfloat(sign|((113u-shifts)<<23)|((mantissa&1023u)<<13));}
    return asfloat(sign|((exponent==31?255:exponent+112)<<23)|(mantissa<<13));
}
#include "../../hls/qwen_decoder_v9f/matrix_q8.hpp"

static const unsigned NL=28,H=1024,ROWBYTES=1088,VOCAB=151936,CHUNK=8192,NC=2048,NK=8,HD=128,B=8;
static const uint32_t PAGES=0x100,DESC=0x400,IDS=0x600,ROPE=0x1000,RESULT=0x180000,CACHE=0x200000;
static const uint32_t CACHE_BYTES=NL*2*NK*NC*HD*2;
static void putu(std::vector<word>&m,uint32_t a,uint32_t v){unsigned lo=(a&31)*8;m[a/32].range(lo+31,lo)=v;}
static uint32_t getu(const std::vector<word>&m,uint32_t a){return (m[a/32]>>((a&31)*8)).range(31,0).to_uint();}
static std::vector<char> slurp(const std::string&p){std::ifstream f(p,std::ios::binary|std::ios::ate);if(!f)throw std::runtime_error("cannot read "+p);size_t n=f.tellg();f.seekg(0);std::vector<char>b(n);f.read(b.data(),n);return b;}
static double now(){return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();}
static uint32_t bits(float f){uint32_t u;std::memcpy(&u,&f,4);return u;}

// Crafted partial sums through reduce_q8: ties within a slot, ties across slots,
// +0/-0, and fewer active slots than TOKENS. Returns the number of mismatches.
static unsigned reducer_test(){
    const unsigned rows=12,batch=6;unsigned bad=0;
    float sums[rows][B];
    const float pattern[rows]={1.0f,3.0f,-0.0f,3.0f,0.0f,2.5f,3.0f,-1.0f,0.0f,3.0f,-0.0f,2.0f};
    for(unsigned r=0;r<rows;r++)for(unsigned b=0;b<B;b++){
        if(b==0)sums[r][b]=pattern[r];
        else if(b==1)sums[r][b]=-pattern[r];             // maxima among -0/+0/1/... ties
        else if(b==2)sums[r][b]=0.0f*float(r%2?1:-1);     // all zeros of both signs: lowest row wins
        else if(b==3)sums[r][b]=float(r);                 // last row wins
        else if(b==4)sums[r][b]=float(rows-r);            // first row wins
        else sums[r][b]=pattern[(r+5)%rows];
    }
    for(unsigned pass=0;pass<2;pass++){                   // pass 1 continues the running maxima (second chunk)
        hls::stream<matrix_partials<B>> completed;
        for(unsigned r=0;r<rows;r++){matrix_partials<B> v;for(unsigned b=0;b<B;b++){for(unsigned i=0;i<8;i++)v.values[b][i]=0.0f;v.values[b][0]=sums[r][b];}completed.write(v);}
        static float out[B][64];float maximum[B];uint32_t token[B];
        for(unsigned b=0;b<B;b++){maximum[b]=-FLT_MAX;token[b]=0;}
        if(pass==1){for(unsigned b=0;b<B;b++){maximum[b]=2.75f;token[b]=5;}}
        reduce_q8<B,64>(completed,out,rows,batch,pass?100:0,true,maximum,token);
        for(unsigned b=0;b<B;b++){
            float m=pass?2.75f:-FLT_MAX;uint32_t t=pass?5:0;
            if(b<batch)for(unsigned r=0;r<rows;r++){
                // Same tree the reducer applies: ((v0+v1)+(v2+v3))+((v4+v5)+(v6+v7)).
                float s=((sums[r][b]+0.0f)+(0.0f+0.0f))+((0.0f+0.0f)+(0.0f+0.0f));
                uint32_t id=(pass?100:0)+r;if(s>m||(s==m&&id<t)){m=s;t=id;}
            }
            if(bits(maximum[b])!=bits(m)||token[b]!=t){bad++;std::cout<<"REDUCER mismatch pass="<<pass<<" slot="<<b<<" got "<<token[b]<<"/"<<maximum[b]<<" want "<<t<<"/"<<m<<std::endl;}
        }
    }
    std::cout<<"REDUCER synthetic test mismatches="<<bad<<std::endl;return bad;
}

int main(int argc,char**argv){
 try{
  if(argc!=6)throw std::runtime_error("usage: <gguf> <meta.bin> <rope.bin> <v9e results.json> <results.json>");
  unsigned reducer_bad=reducer_test();
  std::vector<uint32_t> baseline;
  {auto t=slurp(argv[4]);std::string s(t.begin(),t.end());size_t a=s.find("\"baseline_tokens\": [");if(a==std::string::npos)throw std::runtime_error("baseline_tokens missing");
   a=s.find('[',a)+1;size_t e=s.find(']',a);std::stringstream ss(s.substr(a,e-a));std::string item;while(std::getline(ss,item,','))baseline.push_back(std::stoul(item));}
  auto mb=slurp(argv[2]);std::vector<uint32_t> meta(mb.size()/4);std::memcpy(meta.data(),mb.data(),meta.size()*4);
  const uint32_t extent=meta[0],embedding=meta[1],output_norm=meta[2];const uint32_t*layer_offsets=&meta[3];
  const unsigned n=meta[3+NL*11];const uint32_t*ids=&meta[4+NL*11];const uint32_t*wrong=ids+n;
  if(n!=24||baseline.size()!=24)throw std::runtime_error("expects 24 positions and 24 baseline tokens");
  const unsigned chunks=(extent+(1u<<24)-1)>>24;
  std::vector<weight_word> model(size_t(chunks)<<19);
  {auto g=slurp(argv[1]);if(g.size()!=extent)throw std::runtime_error("model size differs from metadata");g.resize(size_t(chunks)<<24,0);
   for(size_t i=0;i<g.size();i+=32){weight_word v;for(unsigned lane=0;lane<4;lane++){uint64_t x;std::memcpy(&x,g.data()+i+lane*8,8);v.range(lane*64+63,lane*64)=x;}model[i/32]=v;}}
  std::vector<word> scratch((CACHE+CACHE_BYTES)/32+64);
  for(unsigned i=0;i<chunks;i++)putu(scratch,PAGES+4*i,i<<24);
  {auto rope=slurp(argv[3]);if(rope.size()!=NC*512)throw std::runtime_error("rope size");for(unsigned i=0;i<rope.size();i+=4){uint32_t v;std::memcpy(&v,rope.data()+i,4);putu(scratch,ROPE+i,v);}}
  unsigned status=99;
  auto call=[&](unsigned c,uint32_t page,unsigned layer=0,unsigned position=0,unsigned rows=0,unsigned token_base=0){
   qwen_decoder(model.data(),scratch.data(),c,page,CACHE,ROPE,RESULT,layer,position,rows,token_base,status);
   if(status)throw std::runtime_error("kernel status "+std::to_string(status)+" cmd "+std::to_string(c));
  };
  call(0,PAGES,0,0,chunks,extent);
  // Kernel argmax state starts dirty: a cmd 12 scan over slots 0..7 with unrelated content.
  call(12,embedding,B,0,64,0);
  struct G{unsigned start,count,real;};
  const G groups[]={{0,8,8},{8,8,2},{10,8,8},{18,5,5},{23,1,1}};
  std::ofstream json(argv[5]);json<<"{\n \"lanes\": [";
  unsigned lanes=0,lane_bad=0,base_bad=0;bool first=true;double t0=now();
  for(const G&g:groups){
   double t1=now();
   for(unsigned i=0;i<g.count;i++){unsigned p=g.start+i;putu(scratch,IDS+4*i,embedding+(i<g.real?ids[p]:wrong[p])*ROWBYTES);}
   call(7,IDS,0,g.start,g.count);
   for(unsigned layer=0;layer<NL;layer++){for(unsigned i=0;i<11;i++)putu(scratch,DESC+4*i,layer_offsets[layer*11+i]);call(8,DESC,layer,g.start,g.count);}
   // Batched head (v9f): one weight pass per chunk for all slots.
   double tb=now();
   call(11,output_norm,0,0,g.count);
   for(unsigned s=0;s<VOCAB;s+=CHUNK)call(12,embedding+s*ROWBYTES,g.count,0,std::min(CHUNK,VOCAB-s),s);
   std::vector<uint32_t> bt(g.count),bl(g.count);
   for(unsigned b=0;b<g.count;b++){bt[b]=getu(scratch,RESULT+32*b);bl[b]=getu(scratch,RESULT+32*b+4);}
   double batched_seconds=now()-tb,ts=now();
   // v9e reference: one slot at a time through slot 0.
   for(unsigned b=0;b<g.count;b++){
    unsigned p=g.start+b;bool real=b<g.real;
    if(b)call(9,0,b);
    call(3,output_norm);
    if(real&&p<n){
     call(4,embedding,0,0,CHUNK,0);uint32_t t8=getu(scratch,RESULT);
     bool ok8=t8==baseline[p];base_bad+=!ok8;
     std::cout<<"BASELINE position="<<p<<" first8192 token="<<t8<<" v9e="<<baseline[p]<<(ok8?" equal":" DIFFERENT")<<std::endl;
    }
    for(unsigned s=0;s<VOCAB;s+=CHUNK)call(4,embedding+s*ROWBYTES,0,0,std::min(CHUNK,VOCAB-s),s);
    uint32_t rt=getu(scratch,RESULT),rl=getu(scratch,RESULT+4);
    bool ok=rt==bt[b]&&rl==bl[b];lane_bad+=!ok;lanes++;
    std::cout<<"LANE group_start="<<g.start<<" slot="<<b<<" position="<<p<<(real?" real":" wrong")<<" batched="<<bt[b]<<"/"<<std::hex<<bl[b]<<" sequential="<<std::dec<<rt<<"/"<<std::hex<<rl<<std::dec<<(ok?" IDENTICAL":" DIFFERENT")<<std::endl;
    json<<(first?"":",")<<"\n  {\"group_start\": "<<g.start<<", \"slot\": "<<b<<", \"position\": "<<p<<", \"real\": "<<(real?"true":"false")<<", \"batched_token\": "<<bt[b]<<", \"batched_logit_bits\": "<<bl[b]<<", \"sequential_token\": "<<rt<<", \"sequential_logit_bits\": "<<rl<<", \"identical\": "<<(ok?"true":"false")<<"}";
    first=false;json.flush();
   }
   std::cout<<"GROUP start="<<g.start<<" count="<<g.count<<" seconds="<<now()-t1<<" batched_head_seconds="<<batched_seconds<<" sequential_head_seconds="<<now()-ts<<std::endl;
  }
  bool pass=lanes==30&&lane_bad==0&&base_bad==0&&reducer_bad==0;
  json<<"\n ],\n \"lanes_compared\": "<<lanes<<",\n \"lanes_differing\": "<<lane_bad<<",\n \"baseline_8192_differing\": "<<base_bad<<",\n \"reducer_mismatches\": "<<reducer_bad<<",\n \"seconds\": "<<now()-t0<<",\n \"result\": \""<<(pass?"PASS":"FAIL")<<"\"\n}\n";
  json.close();
  std::cout<<"AUDIT RESULT: "<<(pass?"PASS":"FAIL")<<" lanes="<<lanes<<" differing="<<lane_bad<<" baseline_differing="<<base_bad<<" reducer="<<reducer_bad<<std::endl;
  return pass?0:2;
 }catch(const std::exception&e){std::cerr<<"AUDIT ERROR: "<<e.what()<<std::endl;return 1;}
}
