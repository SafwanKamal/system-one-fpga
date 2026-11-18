#define main frozen_service_regression
#include "../typed200_r5/test_service.c"
#undef main
#include "supervisor.h"
#include <stdio.h>
static uint32_t corrupt;
static uint32_t read_owner(void *c,uint32_t a){
    (void)c;if(a==MVP_PERMIT)return permit[0];
    for(size_t i=0;i<mvp_rule_count;i++)if(mvp_rules[i].address==a)
        return mvp_rules[i].expected^(a==corrupt?mvp_rules[i].mask&(~mvp_rules[i].mask+1):0);
    assert(0);return 0;
}
static void write_owner(void *c,uint32_t a,uint32_t v){(void)c;assert(a==MVP_PERMIT&&v==0);permit[0]=v;}
static void barrier_owner(void *c){(void)c;}
int main(void){
    const struct mvp_io io={0,read_owner,write_owner,barrier_owner};
    assert(frozen_service_regression()==0);
    for(size_t i=0;i<mvp_rule_count;i++){
        init();command(1);uint32_t before[64];memcpy(before,(const void *)mmio,sizeof(before));
        struct mvp_owner owner={0};corrupt=mvp_rules[i].address;
        assert(mvp_step(&io,&owner,&context,0)==-1&&permit[0]==0);
        assert(!memcmp(before,(const void *)mmio,sizeof(before))&&shared.command_state==TY_CMD_READY);
        corrupt=0;assert(mvp_step(&io,&owner,&context,0)==-1); /* no auto heal */
    }
    init();struct mvp_owner owner={0};assert(mvp_step(&io,&owner,&context,1)==-1&&permit[0]==0);
    /* Exact frozen accepted/fault/deadline/invalid records survive terminal parking. */
    const unsigned tags[]={1,4,5};
    for(unsigned i=0;i<3;i++){
        init();command(1);ty_service_poll(&context);active();
        mmio[0xcc/4]=tags[i]==1?30:tags[i]==4?10:16;
        if(tags[i]!=5)ty_service_poll(&context);
        publish(tags[i],tags[i]==1?context.proposal.label:0);
        struct ty_shared saved;memcpy(&saved,(const void *)&shared,sizeof(saved));owner=(struct mvp_owner){0};
        assert(mvp_step(&io,&owner,&context,0)==1&&permit[0]==0);
        assert(!memcmp(&saved,(const void *)&shared,sizeof(saved)));
    }
    init();command(1);shared.tokens=0;owner=(struct mvp_owner){0};
    assert(mvp_step(&io,&owner,&context,0)==1&&permit[0]==0&&shared.result.outcome==TI_INVALID);
    puts("PASS actual supervisor: ownership fault blocks service MMIO; sticky failure; accepted/fault/deadline/invalid preserved and permit low");
    return 0;
}
