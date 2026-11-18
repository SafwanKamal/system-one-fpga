#include "service.h"
#include <assert.h>
#include <stddef.h>
#include <string.h>
_Static_assert(sizeof(struct ty_shared)==384,"shared ABI");
_Static_assert(offsetof(struct ty_shared,result)==312,"shared result ABI");
static struct ti_input input;
static struct ty_service context;
static volatile struct ty_shared shared;
static volatile uint32_t mmio[64],permit[1];
static volatile uint16_t ids[128];
static int8_t hidden[128*384];
static void init(void) {
    memset((void *)mmio,0,sizeof(mmio));memset((void *)&shared,0,sizeof(shared));
    shared.magic=TY_CONFIG_MAGIC;shared.version=1;shared.session=0x12345678;shared.exclusive_buffers_attested=1;
    mmio[0xc0/4]=TI200_ABI;
    assert(!ty_service_init(&context,mmio,permit,ids,hidden,&shared,&input,0) && permit[0]==0);
    mmio[1]=16;assert(!ty_service_init(&context,mmio,permit,ids,hidden,&shared,&input,1));mmio[1]=0;
    assert(ty_service_init(&context,mmio,permit,ids,hidden,&shared,&input,1));
    assert(context.phase==TY_BOOT_WAIT && mmio[0]==1 && permit[0]==0);
    mmio[1]=17;mmio[0x80/4]=0x12345678;ty_service_poll(&context);
    assert(context.phase==TY_IDLE && permit[0]==1);
}
static void command(unsigned seq) {
    shared.sequence=seq;shared.tokens=2;shared.first=0;shared.count=2;shared.budget=500;
    shared.ids[0]=101;shared.ids[1]=102;shared.command_state=TY_CMD_READY;
}
static void active(void) {
    mmio[1]=18;mmio[0x88/4]=(uint32_t)context.identity.request;mmio[0x8c/4]=0;
    for(unsigned i=0;i<8;i++)mmio[0x90/4+i]=mmio[0x20/4+i];
    mmio[0xc4/4]=2;mmio[0xc8/4]=2;ty_service_poll(&context);
    assert(context.phase==TY_CORE && context.bridge.state==TI_WAIT_CORE);
}
static void publish(unsigned tag,unsigned label) {
    memset((void *)&shared.result,0xa5,sizeof(shared.result));
    mmio[1]=20;mmio[0xb0/4]=tag | label<<16;mmio[0xb4/4]=0;mmio[0xb8/4]=91;
    ty_service_poll(&context);
    const volatile unsigned char *bytes=(const volatile unsigned char *)&shared.result;
    for(unsigned i=offsetof(struct ti_record,outcome)+1;i<sizeof(shared.result);i++)assert(bytes[i]==0);
}
int main(void) {
    init();command(1);ty_service_poll(&context);
    assert(context.phase==TY_ADMISSION && mmio[0]==2 && ids[0]==101 && ids[1]==102);
    active();mmio[0xcc/4]=18;ty_service_poll(&context);assert(context.phase==TY_CORE);
    mmio[0xcc/4]=30;ty_service_poll(&context);
    assert(context.phase==TY_TERMINAL && mmio[0]==4 && context.proposal.outcome==TI_ACCEPTED);
    unsigned label=context.proposal.label;assert(label<18);
    publish(1,label);assert(context.phase==TY_IDLE && mmio[0]==8 && shared.result.outcome==TI_ACCEPTED && shared.result_origin==1);
    command(1);ty_service_poll(&context);assert(shared.result.outcome==TI_INVALID && shared.result.label==0 && mmio[0]==8);
    command(2);shared.ids[1]=30522;ty_service_poll(&context);assert(shared.result.outcome==TI_INVALID && shared.result_origin==0);
    command(0);ty_service_poll(&context);assert(context.last_sequence==2);
    command(1);ty_service_poll(&context);assert(shared.result.outcome==TI_INVALID && context.last_sequence==2);
    init();command(1);ty_service_poll(&context);
    mmio[0x88/4]=1;for(unsigned i=0;i<8;i++)mmio[0x90/4+i]=mmio[0x20/4+i];
    mmio[0xcc/4]=16;publish(5,0);
    assert(context.phase==TY_HALTED && shared.result.outcome==TI_DEADLINE && shared.result_origin==1);
    command(2);mmio[0]=0;ty_service_poll(&context);assert(mmio[0]==0);
    init();command(1);ty_service_poll(&context);active();mmio[0xcc/4]=10;
    ty_service_poll(&context);assert(context.proposal.outcome==TI_FAULT && context.proposal.label==0);
    publish(4,0);assert(context.phase==TY_HALTED && shared.result.outcome==TI_FAULT && shared.result_origin==1);
    init();command(1);ty_service_poll(&context);active();mmio[0xcc/4]=30;ty_service_poll(&context);
    publish(1,(context.proposal.label+1)%18);
    assert(context.phase==TY_HALTED && shared.result.outcome==TI_FAULT && shared.result.label==0 && shared.result_origin==0);
    init();command(1);ty_service_poll(&context);active();mmio[0x88/4]=99;publish(5,0);
    assert(context.phase==TY_HALTED && shared.result.outcome==TI_FAULT && shared.result.label==0);
    return 0;
}
