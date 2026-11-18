#include <stddef.h>
void *memcpy(void *d,const void *s,size_t n) {
    unsigned char *a=d;const unsigned char *b=s;
    for(size_t i=0;i<n;i++)a[i]=b[i];return d;
}
void *memset(void *d,int c,size_t n) {
    unsigned char *a=d;for(size_t i=0;i<n;i++)a[i]=(unsigned char)c;return d;
}
void __aeabi_memcpy(void *d,const void *s,size_t n){(void)memcpy(d,s,n);}
void __aeabi_memcpy4(void *d,const void *s,size_t n){(void)memcpy(d,s,n);}
void __aeabi_memcpy8(void *d,const void *s,size_t n){(void)memcpy(d,s,n);}
void __aeabi_memclr(void *d,size_t n){(void)memset(d,0,n);}
void __aeabi_memclr4(void *d,size_t n){(void)memset(d,0,n);}
