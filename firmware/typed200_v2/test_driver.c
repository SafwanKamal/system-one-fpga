#include "typed200.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
static struct ti_input input;
static int8_t memory[128*384];
int main(int argc,char **argv) {
    assert(argc==2);
    static const uint32_t digest[8]={0x5b2752d2u,0xba36026cu,0xfccb4b4fu,0xa3801d00u,
        0x9e95e7acu,0x322ecac4u,0x15487f8fu,0x81336333u};
    FILE *wire=fopen(argv[1],"w");assert(wire);
    volatile uint32_t regs[64]={0};
    struct ti_identity id={0};id.session=0x12345678;id.request=9;memcpy(id.contract,ti_contract(),32);
    assert(!ti200_start(regs,&id,100,2,0,2));
    regs[0xc0/4]=TI200_ABI;regs[1]=1;regs[0x80/4]=0x12345678;
    assert(!ti200_start(regs,&id,100,129,0,1));
    assert(!ti200_start(regs,&id,100,128,127,2));
    assert(!ti200_start(regs,&id,0,2,0,2));
    assert(ti200_start(regs,&id,500,128,1,127));
    assert(regs[0]==2 && regs[0x1c/4]==0x00010080 && regs[0x78/4]==127);
    for(unsigned i=0;i<8;i++)assert(regs[0x20/4+i]==digest[i]);
    unsigned req_offsets[13]={0x10,0x14,0x18,0x1c,0x78,0x20,0x24,0x28,0x2c,0x30,0x34,0x38,0x3c};
    for(unsigned i=0;i<13;i++)assert(fprintf(wire,"%08x\n",regs[req_offsets[i]/4])>0);
    struct ti_proposal p={id,17,0,TI_ACCEPTED};ti200_propose(regs,&p);assert(regs[0]==4);
    for(unsigned i=0;i<8;i++)assert(regs[0x50/4+i]==digest[i]);
    for(unsigned i=0;i<14;i++)assert(fprintf(wire,"%08x\n",regs[0x40/4+i])>0);
    assert(fclose(wire)==0);
    assert(ti200_admission_observe(regs,&id,128,1,127)==0);
    regs[1]=2;regs[0x88/4]=9;regs[0xc4/4]=0x00010080;regs[0xc8/4]=127;
    for(unsigned i=0;i<8;i++)regs[0x90/4+i]=digest[i];
    assert(ti200_admission_observe(regs,&id,128,1,127)==1);
    regs[0x88/4]++;assert(ti200_admission_observe(regs,&id,128,1,127)==-1);regs[0x88/4]--;
    assert(!ti200_copy_hidden(regs,memory,&input));
    for(unsigned i=0;i<sizeof(memory);i++)memory[i]=(int8_t)((int)(i%256)-128);
    regs[0xcc/4]=30;assert(ti200_copy_hidden(regs,memory,&input));
    assert(input.tokens==128 && input.count==127 && input.rows[0]==1 && input.rows[126]==127);
    assert(memcmp(input.hidden,memory,sizeof(memory))==0);
    for(unsigned bit=0;bit<5;bit++) {
        regs[0xcc/4]=30^(1u<<bit);assert(!ti200_copy_hidden(regs,memory,&input));
    }
    regs[0xcc/4]=30;regs[0xc8/4]=128;assert(!ti200_copy_hidden(regs,memory,&input));
    regs[0xc8/4]=0xffffffffu;assert(!ti200_copy_hidden(regs,memory,&input));
    struct ti_record record;
    assert(!ti200_terminal_observe(regs,&record));
    regs[1]=4;regs[0xb0/4]=0x00110001;regs[0xb4/4]=0;regs[0xb8/4]=91;
    assert(ti200_terminal_observe(regs,&record));
    assert(memcmp(record.identity.contract,id.contract,32)==0);
    assert(record.identity.session==0x12345678 && record.identity.request==9 && record.outcome==1 && record.label==17 && record.elapsed==91);
    return 0;
}
