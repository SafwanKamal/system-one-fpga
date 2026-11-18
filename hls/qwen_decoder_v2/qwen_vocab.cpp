#include "llama.h"
#include <fstream>
#include <iostream>
#include <vector>
#include <string>
#include <stdexcept>
static void quiet(ggml_log_level,const char*,void*){}
int main(int argc,char**argv){
 try{
  if(argc<4)throw std::runtime_error("model --encode file | model --decode token...");
  llama_log_set(quiet,nullptr);llama_backend_init();auto params=llama_model_default_params();params.vocab_only=true;params.n_gpu_layers=0;
  llama_model*model=llama_model_load_from_file(argv[1],params);if(!model)throw std::runtime_error("vocab-only model open failed");const llama_vocab*vocab=llama_model_get_vocab(model);
  if(std::string(argv[2])=="--encode"){
   std::ifstream in(argv[3],std::ios::binary);if(!in)throw std::runtime_error("prompt file missing");std::string text((std::istreambuf_iterator<char>(in)),{});std::vector<llama_token>tokens(text.size()*2+1024);
   int n=llama_tokenize(vocab,text.data(),text.size(),tokens.data(),tokens.size(),false,true);if(n<0)throw std::runtime_error("token buffer too short");std::cout<<"[";for(int i=0;i<n;i++){if(i)std::cout<<",";std::cout<<tokens[i];}std::cout<<"]\n";
  }else if(std::string(argv[2])=="--decode"){
   std::vector<char>piece(16384);for(int i=3;i<argc;i++){int n=llama_token_to_piece(vocab,std::stoi(argv[i]),piece.data(),piece.size(),0,false);if(n<0)throw std::runtime_error("piece buffer too short");std::cout.write(piece.data(),n);}
  }else throw std::runtime_error("unknown mode");
  llama_model_free(model);llama_backend_free();return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}
}
