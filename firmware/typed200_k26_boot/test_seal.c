#include "seal_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void){
    const uint32_t good[8]={TB_REQUEST,TB_MAGIC,0x12345678,0x87654321,1,0,0,0};
    unsigned checks=0;
    for(unsigned bit=0;bit<8*32;bit++){
        uint32_t p[8];memcpy(p,good,sizeof p);p[bit/32]^=1u<<(bit%32);
        struct tb_seal s={0};uint32_t result=tb_request(&s,0,1,p,8,11);
        if(bit/32==2 || bit/32==3){assert(result==TB_OK);}
        else {assert(result==TB_INVALID && !s.pending && !s.closed);}
        checks++;
    }
    for(unsigned i=0;i<32;i++){
        struct tb_seal s={0};assert(tb_request(&s,0,1u<<i,good,8,11)==(i?TB_INVALID:TB_OK));checks++;
    }
    for(unsigned c=0;c<16;c++){
        struct tb_seal s={0};assert(tb_request(&s,0,1,good,8,c)==(c==11?TB_OK:TB_NOT_READY));checks++;
    }
    for(unsigned n=0;n<6;n++){
        struct tb_seal s={0};assert(tb_request(&s,0,1,good,n,11)==TB_INVALID);checks++;
    }
    for(unsigned ipi=1;ipi<4;ipi++){
        struct tb_seal s={0};assert(tb_request(&s,ipi,1,good,8,11)==TB_INVALID);checks++;
    }
    struct tb_seal s={0};assert(!tb_commit(&s,11));
    assert(tb_request(&s,0,1,good,8,11)==TB_OK && s.pending && !s.closed);
    assert(tb_request(&s,0,1,good,8,11)==TB_BUSY);
    assert(!tb_commit(&s,3) && !s.closed);
    /* Interrupt request cannot ACK/close until active callback has returned. */
    assert(tb_commit(&s,11) && s.closed && !s.pending);
    struct tb_seal frozen=s;
    assert(tb_request(&s,0,1,good,8,11)==TB_BUSY && !memcmp(&s,&frozen,sizeof s));
    assert(!tb_commit(&s,11) && !memcmp(&s,&frozen,sizeof s));
    for(unsigned event=0;event<83;event++)for(unsigned em=0;em<2;em++){
        assert(tb_event_allowed(&s,em,event)==(em&&(event==4||event==5)));checks++;
    }
    uint32_t zero[8];memcpy(zero,good,sizeof zero);zero[2]=zero[3]=0;
    struct tb_seal z={0};assert(tb_request(&z,0,1,zero,8,11)==TB_INVALID);
    printf("seal policy PASS: %u matrix/bit cases plus transition assertions\n",checks);
    return 0;
}
