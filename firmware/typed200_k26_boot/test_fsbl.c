#include "test_fsbl_stubs.h"
#include "seal_policy.h"
#include <assert.h>
#include <setjmp.h>
#include <stdio.h>
#include <string.h>
u64 tb_host_mpidr,tb_host_el;
static jmp_buf env;
static unsigned fault,phase,power_fault,config_fault,write_fault,ack_fault,response_fault,stuck;
static u32 request[8];
static struct {u32 address,value;} regs[32];
static unsigned nr;
static void set(u32 a,u32 v){for(unsigned i=0;i<nr;i++)if(regs[i].address==a){regs[i].value=v;return;}
    assert(nr<32);regs[nr].address=a;regs[nr++].value=v;}
u32 Xil_In32(u32 a){for(unsigned i=0;i<nr;i++)if(regs[i].address==a)return regs[i].value;return 0;}
void Xil_Out32(u32 a,u32 v){if(a!=stuck)set(a,v);}
void tb_host_fail(u32 c){fault=c;longjmp(env,1);}
u32 XFsbl_PowerUpIsland(u32 m){assert(m==0xc00);assert(!phase);return power_fault;}
void usleep(u32 n){assert(n==1);}
static XIpiPsu_Config cfg={0xff300000};
XIpiPsu_Config *XIpiPsu_LookupConfig(u32 a){assert(a==cfg.BaseAddress);return config_fault?0:&cfg;}
u32 XIpiPsu_CfgInitialize(XIpiPsu *i,XIpiPsu_Config *c,u32 a){(void)i;assert(c==&cfg&&a==c->BaseAddress);return 0;}
u32 XIpiPsu_WriteMessage(XIpiPsu *i,u32 mask,u32 *p,u32 words,unsigned kind){
    (void)i;assert(mask==0x10000 && words==8 && kind==0);memcpy(request,p,sizeof request);return write_fault;}
u32 XIpiPsu_TriggerIpi(XIpiPsu *i,u32 mask){(void)i;assert(mask==0x10000);phase=1;return 0;}
u32 XIpiPsu_PollForAck(const XIpiPsu *i,u32 mask,u32 count){(void)i;assert(mask==0x10000&&count);return ack_fault;}
u32 XIpiPsu_ReadMessage(XIpiPsu *i,u32 mask,u32 *r,u32 words,unsigned kind){
    (void)i;assert(mask==0x10000&&words==8&&kind==1&&phase);
    memcpy(r,request,sizeof request);r[0]=TB_MODULE<<16;
    if(response_fault)r[2]^=1;
    return 0;
}
static void reset(void){
    nr=0;fault=phase=power_fault=config_fault=write_fault=ack_fault=response_fault=stuck=0;
    tb_host_mpidr=0;tb_host_el=12;
    set(0xff5e0220,1);set(0xa00000c0,0x54590201);set(0xa00000cc,2);
    set(0xffd80044,11);set(0xffca300c,1);set(0xffca3010,8);
    set(0x100f0000,0x4d565031);set(0x100f0004,1);set(0x100f0008,42);set(0x100f000c,99);
}
static void run(u64 a,u32 flags,u32 expected){
    if(!setjmp(env))TypedBootFinal(a,flags);
    assert(fault==expected);
    if(expected){assert(!Xil_In32(0xa0001000));assert(Xil_In32(0x100f1000)==(0xe1000000|expected));}
    else {assert(Xil_In32(0x100f1000)==0x5345414c && phase);}
}
int main(void){
    reset();run(0x10000000,1,0);
    reset();run(0xfffc0000,1,1);reset();run(0x10000000,0,1);
    reset();tb_host_mpidr=1;run(0x10000000,1,1);
    reset();tb_host_el=4;run(0x10000000,1,1);
    reset();set(0xff5e0220,4);run(0x10000000,1,2);
    reset();set(0xa00000c0,0);run(0x10000000,1,3);
    reset();set(0xa0001000,1);run(0x10000000,1,3);
    reset();set(0xa0000004,2);run(0x10000000,1,3);
    reset();set(0xa00000cc,0);run(0x10000000,1,3);
    reset();power_fault=1;run(0x10000000,1,4);
    reset();stuck=0xfd1a0104;run(0x10000000,1,5);
    reset();set(0xff9a0100,1);stuck=0xff9a0100;run(0x10000000,1,6);
    reset();stuck=0xff5e023c;run(0x10000000,1,7);
    reset();set(0xffd80044,3);run(0x10000000,1,8);
    reset();set(0xffc80008,1);run(0x10000000,1,9);
    reset();set(0xffc80808,1);run(0x10000000,1,9);
    reset();set(0xffca300c,0);run(0x10000000,1,9);
    reset();set(0xffca3010,0);run(0x10000000,1,9);
    reset();set(0x100f0008,0);set(0x100f000c,0);run(0x10000000,1,10);
    reset();config_fault=1;run(0x10000000,1,11);
    reset();write_fault=1;run(0x10000000,1,12);
    reset();ack_fault=1;run(0x10000000,1,12);
    reset();response_fault=1;run(0x10000000,1,13);
    puts("actual fsbl_final.c PASS: success plus 23 wrong-entry/state/MMIO/protocol/timeout cases (ASM mocked)");
}
