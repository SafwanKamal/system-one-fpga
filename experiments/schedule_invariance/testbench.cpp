// Schedule-invariance audit: drives the unmodified v9e kernel through all 28
// layers under several host schedules and compares raw bit patterns.
// See PROTOCOL.md. argv: <gguf> <meta.bin> <rope.bin> <results.json>
#include <ap_int.h>
#include <vector>
#include <fstream>
#include <iostream>
#include <cstring>
#include <string>
#include <chrono>
#include <stdexcept>
#include <stdint.h>
using word=ap_uint<256>;
using weight_word=ap_uint<256>;
extern "C" void qwen_decoder(weight_word*,word*,unsigned,uint32_t,uint32_t,uint32_t,uint32_t,unsigned,unsigned,unsigned,unsigned,unsigned&);
static const unsigned NL=28,NK=8,NC=2048,HD=128,H=1024,ROWBYTES=1088,HEADROWS=8192;
static const uint32_t PAGES=0x100,DESC=0x400,IDS=0x600,ROPE=0x1000,RESULT=0x180000,CACHE=0x200000;
static const uint32_t CACHE_BYTES=NL*2*NK*NC*HD*2;
static void putu(std::vector<word>&m,uint32_t a,uint32_t v){unsigned lo=(a&31)*8;m[a/32].range(lo+31,lo)=v;}
static uint32_t getu(const std::vector<word>&m,uint32_t a){return (m[a/32]>>((a&31)*8)).range(31,0).to_uint();}
static std::vector<char> slurp(const std::string&p){std::ifstream f(p,std::ios::binary|std::ios::ate);if(!f)throw std::runtime_error("cannot read "+p);size_t n=f.tellg();f.seekg(0);std::vector<char>b(n);f.read(b.data(),n);return b;}
struct Group{unsigned start;std::vector<uint32_t> ids;unsigned keep;bool batch_path;};
struct Record{
    std::vector<uint32_t> hidden,norm,kv,token,logit;std::vector<unsigned char> seen;
    explicit Record(unsigned n):hidden(size_t(NL)*n*H),norm(size_t(n)*H),kv(size_t(NL)*2*NK*n*64),token(n),logit(n),seen(n,0){}
};
static double now(){return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();}
int main(int argc,char**argv){
 try{
  if(argc!=5)throw std::runtime_error("usage: <gguf> <meta.bin> <rope.bin> <results.json>");
  auto mb=slurp(argv[2]);std::vector<uint32_t> meta(mb.size()/4);std::memcpy(meta.data(),mb.data(),meta.size()*4);
  const uint32_t extent=meta[0],embedding=meta[1],output_norm=meta[2];const uint32_t*layer_offsets=&meta[3];
  const unsigned n=meta[3+NL*11];const uint32_t*ids=&meta[4+NL*11];const uint32_t*wrong=ids+n;
  const unsigned chunks=(extent+(1u<<24)-1)>>24;
  std::vector<weight_word> model(size_t(chunks)<<19);
  {
   auto g=slurp(argv[1]);if(g.size()!=extent)throw std::runtime_error("model size differs from metadata");
   g.resize(size_t(chunks)<<24,0);
   for(size_t i=0;i<g.size();i+=32){weight_word v;for(unsigned lane=0;lane<4;lane++){uint64_t x;std::memcpy(&x,g.data()+i+lane*8,8);v.range(lane*64+63,lane*64)=x;}model[i/32]=v;}
  }
  std::vector<word> scratch((CACHE+CACHE_BYTES)/32+64);
  for(unsigned i=0;i<chunks;i++)putu(scratch,PAGES+4*i,i<<24);
  {auto rope=slurp(argv[3]);if(rope.size()!=NC*512)throw std::runtime_error("rope size");for(unsigned i=0;i<rope.size();i+=4){uint32_t v;std::memcpy(&v,rope.data()+i,4);putu(scratch,ROPE+i,v);}}
  unsigned status=99;
  auto call=[&](unsigned c,uint32_t page,unsigned layer=0,unsigned position=0,unsigned rows=0,unsigned token_base=0){
   qwen_decoder(model.data(),scratch.data(),c,page,CACHE,ROPE,RESULT,layer,position,rows,token_base,status);
   if(status)throw std::runtime_error("kernel status "+std::to_string(status)+" cmd "+std::to_string(c));
  };
  call(0,PAGES,0,0,chunks,extent);
  word poison;for(unsigned lane=0;lane<16;lane++)poison.range(lane*16+15,lane*16)=0x7fc0;
  auto run=[&](const std::string&name,const std::vector<Group>&groups){
   Record r(n);double t0=now();
   for(size_t i=CACHE/32;i<(CACHE+CACHE_BYTES)/32;i++)scratch[i]=poison;
   for(const Group&g:groups){
    unsigned count=g.ids.size();double t1=now();
    if(count==1&&!g.batch_path)call(1,embedding+g.ids[0]*ROWBYTES,0,g.start);
    else{for(unsigned i=0;i<count;i++)putu(scratch,IDS+4*i,embedding+g.ids[i]*ROWBYTES);call(7,IDS,0,g.start,count);}
    for(unsigned layer=0;layer<NL;layer++){
     for(unsigned i=0;i<11;i++)putu(scratch,DESC+4*i,layer_offsets[layer*11+i]);
     if(count==1&&!g.batch_path)call(2,DESC,layer,g.start);else call(8,DESC,layer,g.start,count);
     for(unsigned lane=0;lane<g.keep;lane++){
      call(10,0,lane);uint32_t*dst=&r.hidden[(size_t(layer)*n+g.start+lane)*H];
      for(unsigned i=0;i<H;i++)dst[i]=getu(scratch,RESULT+4*i);
     }
    }
    for(unsigned lane=0;lane<g.keep;lane++){
     unsigned position=g.start+lane;if(r.seen[position])throw std::runtime_error("position kept twice");r.seen[position]=1;
     if(lane)call(9,0,lane);
     call(3,output_norm);call(6,0);
     for(unsigned i=0;i<H;i++)r.norm[size_t(position)*H+i]=getu(scratch,RESULT+4*i);
     call(4,embedding,0,0,HEADROWS,0);
     r.token[position]=getu(scratch,RESULT);r.logit[position]=getu(scratch,RESULT+4);
    }
    std::cout<<name<<" group start="<<g.start<<" size="<<count<<" keep="<<g.keep<<" seconds="<<now()-t1<<std::endl;
   }
   for(unsigned p=0;p<n;p++)if(!r.seen[p])throw std::runtime_error("schedule leaves a position uncovered");
   size_t k=0;
   for(unsigned layer=0;layer<NL;layer++)for(unsigned kv=0;kv<2;kv++)for(unsigned head=0;head<NK;head++)for(unsigned p=0;p<n;p++){
    uint32_t base=CACHE+((((layer*2+kv)*NK+head)*NC+p)*HD)*2;
    for(unsigned i=0;i<64;i++)r.kv[k++]=getu(scratch,base+4*i);
   }
   std::cout<<name<<" complete seconds="<<now()-t0<<std::endl;return r;
  };
  auto real=[&](unsigned start,unsigned count){return std::vector<uint32_t>(ids+start,ids+start+count);};
  auto tail=[&](unsigned start,unsigned count,unsigned keep){auto v=real(start,count);for(unsigned i=keep;i<count;i++)v[i]=wrong[start+i];return v;};
  if(n!=24)throw std::runtime_error("schedules are written for 24 positions");
  std::vector<Group> prefill8={{0,real(0,8),8,true},{8,real(8,8),8,true},{16,real(16,8),8,true}};
  std::vector<Group> mixed={{0,real(0,3),3,true},{3,real(3,1),1,false},{4,real(4,8),8,true},{12,real(12,1),1,true},{13,real(13,5),5,true},{18,real(18,2),2,true},{20,real(20,4),4,true}};
  std::vector<Group> rollback={{0,real(0,8),8,true},{8,tail(8,8,2),2,true},{10,real(10,8),8,true},{18,tail(18,6,1),1,true},{19,real(19,1),1,false},{20,real(20,4),4,true}};
  std::vector<Group> decode;for(unsigned p=0;p<n;p++)decode.push_back({p,real(p,1),1,false});
  std::ofstream json(argv[4]);json<<"{\n \"positions\": "<<n<<",\n \"baseline\": \"prefill8\",\n \"comparisons\": [";
  bool pass=true,first=true;
  Record base=run("prefill8",prefill8);
  auto compare=[&](const std::string&name,const Record&r){
   auto diff=[&](const std::vector<uint32_t>&a,const std::vector<uint32_t>&b,size_t&at){size_t d=0;at=size_t(-1);for(size_t i=0;i<a.size();i++)if(a[i]!=b[i]){if(!d)at=i;d++;}return d;};
   size_t at_h,at_k,at_n,at_t,at_l;
   size_t dh=diff(base.hidden,r.hidden,at_h),dk=diff(base.kv,r.kv,at_k),dn=diff(base.norm,r.norm,at_n),dt=diff(base.token,r.token,at_t),dl=diff(base.logit,r.logit,at_l);
   bool ok=!(dh||dk||dn||dt||dl);pass=pass&&ok;
   std::cout<<"COMPARE "<<name<<" vs prefill8: hidden_words="<<base.hidden.size()<<" differing="<<dh<<"; kv_words="<<base.kv.size()<<" differing="<<dk<<"; norm_words="<<base.norm.size()<<" differing="<<dn<<"; tokens differing="<<dt<<"; logits differing="<<dl<<(ok?" => IDENTICAL":" => DIFFERENT")<<std::endl;
   if(dh)std::cout<<"  first hidden difference: layer="<<at_h/(size_t(n)*H)<<" position="<<(at_h/H)%n<<" element="<<at_h%H<<std::endl;
   json<<(first?"":",")<<"\n  {\"schedule\": \""<<name<<"\", \"hidden_words\": "<<base.hidden.size()<<", \"hidden_differing\": "<<dh<<", \"kv_words\": "<<base.kv.size()<<", \"kv_differing\": "<<dk<<", \"norm_words\": "<<base.norm.size()<<", \"norm_differing\": "<<dn<<", \"tokens_differing\": "<<dt<<", \"logits_differing\": "<<dl<<", \"first_hidden_difference\": "<<(dh?long(at_h):-1L)<<"}";
   first=false;json.flush();
  };
  compare("mixed",run("mixed",mixed));
  compare("rollback",run("rollback",rollback));
  compare("decode",run("decode",decode));
  size_t nan_kv=0;for(uint32_t v:base.kv){if((v&0x7f80u)==0x7f80u&&(v&0x7fu))nan_kv++;if(((v>>16)&0x7f80u)==0x7f80u&&((v>>16)&0x7fu))nan_kv++;}
  json<<"\n ],\n \"baseline_tokens\": [";for(unsigned p=0;p<n;p++)json<<(p?",":"")<<base.token[p];
  json<<"],\n \"baseline_kv_nan_values\": "<<nan_kv<<",\n \"result\": \""<<(pass?"PASS":"FAIL")<<"\"\n}\n";json.close();
  std::cout<<"baseline K/V NaN values among kept rows="<<nan_kv<<std::endl;
  std::cout<<"AUDIT RESULT: "<<(pass?"PASS":"FAIL")<<std::endl;return 0;
 }catch(const std::exception&e){std::cerr<<"AUDIT ERROR: "<<e.what()<<std::endl;return 1;}
}
