#include "sha256.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char **argv) {
    assert(argc==2);FILE *f=fopen(argv[1],"rb");assert(f);
    assert(fseek(f,0,SEEK_END)==0);long n=ftell(f);assert(n>=0);rewind(f);
    uint8_t *p=malloc((size_t)n+1);assert(p);assert(fread(p,1,(size_t)n,f)==(size_t)n);assert(fclose(f)==0);
    uint8_t hash[32];ty_sha256(p,(size_t)n,hash);free(p);
    for(unsigned i=0;i<32;i++)printf("%02x",hash[i]);
    putchar('\n');return 0;
}
