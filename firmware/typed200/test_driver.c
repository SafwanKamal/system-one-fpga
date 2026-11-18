#include "typed200.h"
#include <assert.h>
#include <string.h>
static struct ti_input input;
static int8_t memory[128*384];
int main(void) {
    volatile uint32_t regs[64]={0};
    struct ti_identity id={0};id.session=123;id.request=9;memcpy(id.contract,ti_contract(),32);
    assert(!ti200_start(regs,&id,100,2,0,2));
    regs[0xc0/4]=TI200_ABI;regs[1]=1;regs[0x80/4]=123;
    assert(!ti200_start(regs,&id,100,129,0,1));
    assert(!ti200_start(regs,&id,100,128,127,2));
    assert(!ti200_start(regs,&id,0,2,0,2));
    assert(ti200_start(regs,&id,100,128,1,127));
    assert(regs[0]==2 && regs[0x1c/4]==0x00010080 && regs[0x78/4]==127);
    assert(ti200_admission_observe(regs,&id,128,1,127)==0);
    regs[1]=2;regs[0x88/4]=9;regs[0xc4/4]=0x00010080;regs[0xc8/4]=127;
    for(unsigned i=0;i<8;i++)regs[0x90/4+i]=regs[0x20/4+i];
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
    return 0;
}
