/* Host-only capture fixtures using the exact frozen service and mock registers.
 * Not a target loader, not a PL model, not a numerical/WCET qualification.
 */
#include <stdio.h>
#include "abi_layout.c"
#define main sealed_policy_test_main
#include "../typed200_r5/test_service.c"
#undef main
_Static_assert(offsetof(struct ty_shared,result_sequence)==300,"sequence offset");
_Static_assert(offsetof(struct ty_shared,result_origin)==304,"origin offset");
_Static_assert(offsetof(struct ty_shared,exception_reason)==376,"exception offset");
_Static_assert(sizeof(struct ti_record)==64,"record size");
_Static_assert(offsetof(struct ti_record,elapsed)==48,"age offset");
_Static_assert(offsetof(struct ti_record,outcome)==56,"outcome offset");

static void capture(const char *dir,const char *name) {
    char path[4096];unsigned char buf[384];
    assert(snprintf(path,sizeof(path),"%s/%s.shared.bin",dir,name)>0);
    memcpy(buf,(const void *)&shared,sizeof(shared));
    FILE *f=fopen(path,"wb");assert(f);assert(fwrite(buf,1,sizeof(shared),f)==sizeof(shared));assert(fclose(f)==0);
    assert(snprintf(path,sizeof(path),"%s/%s.pl.bin",dir,name)>0);
    memcpy(buf,(const void *)mmio,sizeof(mmio));
    f=fopen(path,"wb");assert(f);assert(fwrite(buf,1,sizeof(mmio),f)==sizeof(mmio));assert(fclose(f)==0);
    printf("%s outcome=%u label=%u origin=%u request=%llu\n",name,
           shared.result.outcome,shared.result.label,shared.result_origin,
           (unsigned long long)shared.result.identity.request);
}
static void finish(unsigned outcome,unsigned label,unsigned age,unsigned native) {
    memset((void *)&shared.result,0xa5,sizeof(shared.result));
    mmio[1]=outcome==TI_FAULT || outcome==TI_DEADLINE ? 28:20;
    mmio[0xb0/4]=outcome | label<<16;mmio[0xb4/4]=0;mmio[0xb8/4]=age;
    mmio[0xcc/4]=native;ty_service_poll(&context);
}
int main(int argc,char **argv) {
    assert(argc==2);const uint32_t endian=1;assert(*(const unsigned char *)&endian==1);
    assert(sealed_policy_test_main()==0);
    init();command(1);ty_service_poll(&context);active();
    mmio[0xcc/4]=30;ty_service_poll(&context);
    finish(TI_ACCEPTED,context.proposal.label,91,30);
    assert(shared.result_origin==1 && shared.result.outcome==TI_ACCEPTED);
    capture(argv[1],"accepted");
    init();command(1);ty_service_poll(&context);active();
    finish(TI_DEADLINE,0,500,16);
    assert(shared.result_origin==1 && shared.result.outcome==TI_DEADLINE);
    capture(argv[1],"deadline");
    init();command(1);ty_service_poll(&context);active();
    mmio[0xcc/4]=10;ty_service_poll(&context);
    finish(TI_FAULT,0,91,10);
    assert(shared.result_origin==1 && shared.result.outcome==TI_FAULT);
    capture(argv[1],"fault");
    init();command(1);shared.ids[1]=30522;ty_service_poll(&context);
    assert(shared.result_origin==0 && shared.result.outcome==TI_INVALID);
    capture(argv[1],"cpu-invalid");
    init();command(1);ty_service_poll(&context);active();
    mmio[0xcc/4]=30;ty_service_poll(&context);
    finish(TI_ACCEPTED,(context.proposal.label+1)%18,91,30);
    assert(shared.result_origin==0 && shared.result.outcome==TI_FAULT);
    capture(argv[1],"cpu-fault");
    return 0;
}
