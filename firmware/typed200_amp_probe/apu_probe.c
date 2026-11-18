#define _GNU_SOURCE
#include <assert.h>
#include <fcntl.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>
#include <unistd.h>

/* Diagnostic only. Every AXI access is one volatile, aligned 32-bit access. */
static uint32_t rd(volatile uint32_t *p) {
    uint32_t x=*p;
    __asm__ volatile("dsb sy" ::: "memory");
    return x;
}
static void wr(volatile uint32_t *p,uint32_t x) {
    *p=x;
    __asm__ volatile("dsb sy" ::: "memory");
}
int main(void) {
    setbuf(stdout,NULL);
    int fd=open("/dev/mem",O_RDWR|O_SYNC);
    assert(fd>=0);
    volatile uint32_t *p=mmap(NULL,4096,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0xa0000000);
    assert(p!=MAP_FAILED);
    assert(rd(p)==0x4f524731 && rd(p+1)==1);
    uint32_t count=rd(p+2), errors=rd(p+3);
    assert(count==0 && errors==0);
    puts("{\"cores\":[");
    for(int cpu=0;cpu<4;cpu++) {
        cpu_set_t set;
        CPU_ZERO(&set);CPU_SET(cpu,&set);
        assert(sched_setaffinity(0,sizeof set,&set)==0);
        assert(sched_getcpu()==cpu);
        uint32_t ar=rd(p+6), arid=rd(p+7), tick=rd(p+4);
        for(unsigned j=0;j<16;j++)wr(p+j,0x41500000|((unsigned)cpu<<8)|j);
        assert(rd(p+2)==count+16 && rd(p+3)==errors);
        printf("%s{\"cpu\":%d,\"ar_tag\":%u,\"ar_id\":%u,\"slots\":[",cpu?",":"",cpu,ar,arid);
        uint32_t first=rd(p+64);
        for(unsigned j=0;j<16;j++) {
            uint32_t tag=rd(p+64+4*j),addr=rd(p+65+4*j);
            uint32_t value=rd(p+66+4*j),meta=rd(p+67+4*j);
            assert(tag==first && addr==0xa0000000+4*j);
            assert(value==(0x41500000|((unsigned)cpu<<8)|j));
            assert((meta>>16)==count+j);
            printf("%s{\"tag\":%u,\"address\":%u,\"value\":%u,\"metadata\":%u}",j?",":"",tag,addr,value,meta);
        }
        assert(rd(p+4)!=tick);
        puts("]}");count+=16;
    }
    printf("],\"writes\":%u,\"errors\":%u,\"passed\":true}\n",rd(p+2),rd(p+3));
    assert(munmap((void *)p,4096)==0);close(fd);
    return 0;
}
