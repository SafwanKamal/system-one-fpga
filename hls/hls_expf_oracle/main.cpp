#include <cstdio>
#include <vector>
void hls_expf_top(const float*,float*,int);
int main(int argc,char**argv){
 if(argc!=3)return 2;FILE*f=std::fopen(argv[1],"rb");if(!f)return 3;
 std::fseek(f,0,SEEK_END);long n=std::ftell(f)/4;std::fseek(f,0,SEEK_SET);std::vector<float>x(n),y(n);
 if(std::fread(x.data(),4,n,f)!=size_t(n))return 4;std::fclose(f);hls_expf_top(x.data(),y.data(),int(n));
 FILE*g=std::fopen(argv[2],"wb");if(!g)return 5;std::fwrite(y.data(),4,n,g);std::fclose(g);std::printf("ORACLE expf n=%ld\n",n);return 0;}
