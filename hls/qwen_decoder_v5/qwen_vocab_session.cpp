#include "llama.h"
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <stdexcept>
static void quiet(ggml_log_level,const char*,void*){}
int main(int argc,char **argv) {
    llama_model *model=nullptr;
    try {
        if(argc!=2)throw std::runtime_error("model path required");
        llama_log_set(quiet,nullptr);llama_backend_init();
        auto params=llama_model_default_params();params.vocab_only=true;params.n_gpu_layers=0;
        model=llama_model_load_from_file(argv[1],params);
        if(!model)throw std::runtime_error("vocabulary open failed");
        const auto *vocab=llama_model_get_vocab(model);
        std::cout<<"READY\n"<<std::flush;
        std::string line;
        while(std::getline(std::cin,line)) {
            if(line=="Q")break;
            if(line.size()<2 || line[1]!='\t')throw std::runtime_error("bad protocol");
            if(line[0]=='E') {
                std::ifstream input(line.substr(2),std::ios::binary);
                if(!input)throw std::runtime_error("prompt file missing");
                std::string text((std::istreambuf_iterator<char>(input)),{});
                std::vector<llama_token> tokens(text.size()*2+1024);
                int n=llama_tokenize(vocab,text.data(),text.size(),tokens.data(),tokens.size(),false,true);
                if(n<0)throw std::runtime_error("token buffer too short");
                std::cout<<'[';
                for(int i=0;i<n;i++){if(i)std::cout<<',';std::cout<<tokens[i];}
                std::cout<<"]\n"<<std::flush;
            } else if(line[0]=='D') {
                std::istringstream input(line.substr(2));int token;
                std::vector<char> piece(16384);const char *hex="0123456789abcdef";
                while(input>>token) {
                    if(token<0 || token>=llama_vocab_n_tokens(vocab))throw std::runtime_error("token outside vocabulary");
                    int n=llama_token_to_piece(vocab,token,piece.data(),piece.size(),0,false);
                    if(n<0)throw std::runtime_error("piece buffer too short");
                    for(int i=0;i<n;i++){unsigned char c=piece[i];std::cout<<hex[c>>4]<<hex[c&15];}
                }
                std::cout<<'\n'<<std::flush;
            } else throw std::runtime_error("unknown protocol command");
        }
        llama_model_free(model);llama_backend_free();return 0;
    } catch(const std::exception &e) {
        std::cerr<<e.what()<<'\n';if(model)llama_model_free(model);llama_backend_free();return 1;
    }
}
