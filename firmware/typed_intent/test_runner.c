/* Host numerical/protocol oracle transport; excluded from R5 firmware. */
#include "typed_intent.h"
#include "typed_mailbox.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <fenv.h>
static struct ti_input input;
static void mailbox_tests(void) {
    volatile uint32_t regs[64]={0};
    struct ti_identity id={0};
    id.session=0x123456789abcdef0ULL;id.request=0xfedcba9876543210ULL;
    memcpy(id.contract,ti_contract(),32);
    ti_mmio_provision(regs,id.session);
    assert(regs[0]==1 && regs[2]==0x9abcdef0 && regs[3]==0x12345678);
    ti_mmio_start(regs,&id,321);
    assert(regs[0]==2 && regs[4]==0x76543210 && regs[5]==0xfedcba98 && regs[6]==321);
    for(unsigned i=0;i<8;i++)assert(regs[8+i]==((uint32_t)id.contract[4*i] |
        (uint32_t)id.contract[4*i+1]<<8 | (uint32_t)id.contract[4*i+2]<<16 |
        (uint32_t)id.contract[4*i+3]<<24));
    struct ti_proposal p={id,17,0,TI_ACCEPTED};ti_mmio_propose(regs,&p);
    assert(regs[0]==4 && regs[16]==regs[2] && regs[17]==regs[3]);
    assert(regs[18]==regs[4] && regs[19]==regs[5] && regs[28]==0x00110001 && regs[29]==0);
    struct ti_record r;
    assert(!ti_mmio_observe(regs,&r));
    regs[1]=4;
    for(unsigned i=0;i<12;i++)regs[32+i]=regs[16+i];
    regs[44]=regs[28];regs[45]=0;regs[46]=99;
    assert(ti_mmio_observe(regs,&r));
    assert(r.identity.session==id.session && r.identity.request==id.request);
    assert(memcmp(r.identity.contract,id.contract,32)==0 && r.label==17 && r.outcome==1 && r.elapsed==99);
    ti_mmio_ack(regs);assert(regs[0]==8);
}
static void bridge_tests(void) {
    struct ti_bridge b;
    struct ti_identity id={0};
    struct ti_proposal p;
    assert(!ti_bridge_init(&b,0) && b.state==TI_QUARANTINE);
    assert(ti_bridge_init(&b,123));
    id.session=123; id.request=1; memcpy(id.contract,ti_contract(),32);
    assert(!ti_bridge_core(&b,1,1,1,&input,&p));
    assert(ti_bridge_admitted(&b,&id));
    assert(!ti_bridge_admitted(&b,&id));
    assert(!ti_bridge_core(&b,0,1,1,&input,&p));
    input.tokens=1; input.count=1; input.rows[0]=0;
    assert(ti_bridge_core(&b,1,1,1,&input,&p));
    assert(p.outcome==TI_ACCEPTED && p.label<18 && p.reserved_score==0);
    assert(!ti_bridge_core(&b,1,1,1,&input,&p));
    struct ti_identity stale=id; stale.session++;
    assert(!ti_bridge_terminal(&b,&stale,TI_ACCEPTED,p.label,0,1));
    assert(ti_bridge_terminal(&b,&id,TI_ACCEPTED,p.label,0,1) && b.state==TI_IDLE);
    assert(!ti_bridge_admitted(&b,&id));
    id.request=2; id.contract[0]^=1; assert(!ti_bridge_admitted(&b,&id)); id.contract[0]^=1;
    assert(ti_bridge_admitted(&b,&id));
    assert(ti_bridge_terminal(&b,&id,TI_DEADLINE,0,0,1) && b.state==TI_QUARANTINE);
    assert(!ti_bridge_core(&b,1,1,1,&input,&p));
    assert(!ti_bridge_admitted(&b,&id));
    /* Each reset here models provisioning a NEW session, not quarantine recovery. */
    for(unsigned scenario=0;scenario<9;scenario++) {
        ti_bridge_init(&b,1000+scenario); id.session=1000+scenario; id.request=1;
        assert(ti_bridge_admitted(&b,&id));
        if(scenario==0) {
            assert(ti_bridge_terminal(&b,&id,TI_ACCEPTED,0,0,1));
        } else {
            if(scenario==8) input.count=0;
            assert(ti_bridge_core(&b,1,scenario!=1,scenario!=2,&input,&p));
            if(scenario==1 || scenario==2 || scenario==8) assert(p.outcome==TI_FAULT && p.label==0);
            unsigned outcome=scenario==3 ? 7 : (unsigned)p.outcome;
            uint16_t label=scenario==4 ? (uint16_t)((p.label+1)%18) : p.label;
            assert(ti_bridge_terminal(&b,&id,(uint8_t)outcome,label,scenario==5,scenario!=6));
        }
        assert(b.state==(scenario==7 ? TI_IDLE : TI_QUARANTINE));
    }
    int32_t tied[18]={0}; assert(ti_choose(tied)==0);
}
int main(int argc,char **argv) {
    assert(argc==3 && fegetround()==FE_TONEAREST);
    bridge_tests();
    mailbox_tests();
    FILE *in=fopen(argv[1],"rb"), *out=fopen(argv[2],"wb"); assert(in && out);
    uint32_t n; assert(fread(&n,4,1,in)==1);
    for(uint32_t i=0;i<n;i++) {
        assert(fread(&input.tokens,2,1,in)==1 && fread(&input.count,2,1,in)==1);
        assert(fread(input.rows,2,128,in)==128);
        assert(fread(input.hidden,1,sizeof(input.hidden),in)==sizeof(input.hidden));
        struct ti_head_result r;
        uint32_t ok=(uint32_t)ti_head(&input,&r), label=r.label;
        assert(fwrite(&ok,4,1,out)==1 && fwrite(&label,4,1,out)==1);
        assert(fwrite(r.logits,4,18,out)==18);
    }
    assert(fgetc(in)==EOF); assert(fclose(in)==0 && fclose(out)==0);
    return 0;
}
