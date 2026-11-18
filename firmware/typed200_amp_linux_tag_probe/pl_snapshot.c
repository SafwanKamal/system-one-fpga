#define _GNU_SOURCE
#include <assert.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>
#include <unistd.h>
/* Read-only snapshot of the single reviewed PL probe page. */
static uint32_t rd(volatile uint32_t *p) {
 uint32_t value=*p;
 __asm__ volatile("dsb sy" ::: "memory");
 return value;
}
int main(void) {
 setbuf(stdout,NULL);
 int fd=open("/dev/mem",O_RDONLY|O_SYNC);assert(fd>=0);
 volatile uint32_t *p=mmap(NULL,4096,PROT_READ,MAP_SHARED,fd,0xa0000000);
 assert(p!=MAP_FAILED);
 uint32_t magic=rd(p),version=rd(p+1),writes=rd(p+2),errors=rd(p+3);
 assert(magic==0x4f524731 && version==1);
 printf("{\"magic\":%u,\"version\":%u,\"writes\":%u,\"errors\":%u,\"slots\":[",magic,version,writes,errors);
 for(unsigned j=0;j<16;j++) {
  uint32_t tag=rd(p+64+4*j),address=rd(p+65+4*j),value=rd(p+66+4*j),metadata=rd(p+67+4*j);
  printf("%s{\"tag\":%u,\"address\":%u,\"value\":%u,\"metadata\":%u}",j?",":"",tag,address,value,metadata);
 }
 puts("]}");assert(munmap((void *)p,4096)==0);close(fd);return 0;
}
