#include "mailbox.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static struct amp_mailbox c;
static struct ti_input input,reference_input;
static struct ty_service reference;
static struct ty_shared reference_shared;
static volatile uint32_t ingress[AMP_REQUEST_WORDS],result[AMP_RESULT_WORDS];
static volatile uint32_t mmio[64],ref_mmio[64],permit[1],ref_permit[1];
static volatile uint16_t ids[128],ref_ids[128];
static int8_t hidden[128*384];
static const uint64_t session=UINT64_C(0x123456789abcdef0);
static void setup(void) {
 memset(&c,0,sizeof(c));memset((void *)mmio,0,sizeof(mmio));
 memset((void *)ref_mmio,0,sizeof(ref_mmio));
 memset((void *)ingress,0,sizeof(ingress));memset((void *)result,0xa5,sizeof(result));
 memset((void *)ids,0,sizeof(ids));memset((void *)ref_ids,0,sizeof(ref_ids));
 mmio[0xc0/4]=TI200_ABI;ref_mmio[0xc0/4]=TI200_ABI;
 assert(!amp_mailbox_init(&c,session,0,ingress,result,mmio,permit,ids,hidden,&input));
 assert(permit[0]==0 && c.phase==AMP_MB_SEALED);
 assert(amp_mailbox_init(&c,session,1,ingress,result,mmio,permit,ids,hidden,&input));
 reference_shared=(struct ty_shared){0};
 reference_shared.magic=TY_CONFIG_MAGIC;reference_shared.version=TY_SHARED_VERSION;
 reference_shared.session=session;reference_shared.exclusive_buffers_attested=1;
 assert(ty_service_init(&reference,ref_mmio,ref_permit,ref_ids,hidden,&reference_shared,&reference_input,1));
 mmio[1]=ref_mmio[1]=17;
 mmio[0x80/4]=ref_mmio[0x80/4]=(uint32_t)session;
 mmio[0x84/4]=ref_mmio[0x84/4]=(uint32_t)(session>>32);
 amp_mailbox_poll(&c);ty_service_poll(&reference);
 assert(c.phase==AMP_MB_READY && permit[0]==1 && !result[2]);
 ingress[0]=AMP_REQUEST_MAGIC;ingress[1]=1;ingress[2]=1;ingress[3]=7;
 ingress[4]=(uint32_t)session;ingress[5]=(uint32_t)(session>>32);
 ingress[6]=2;ingress[7]=0;ingress[8]=2;ingress[9]=500;
 ingress[16]=101;ingress[17]=102;
}
static void same(void) {
 for(unsigned i=0;i<64;i++)assert(mmio[i]==ref_mmio[i]);
 for(unsigned i=0;i<128;i++)assert(ids[i]==ref_ids[i]);
 assert(permit[0]==ref_permit[0]);
 assert(c.service.phase==reference.phase);
}
static void poll_both(void) {amp_mailbox_poll(&c);ty_service_poll(&reference);same();}
static void submit(void) {
 reference_shared.sequence=7;reference_shared.tokens=2;reference_shared.first=0;
 reference_shared.count=2;reference_shared.budget=500;
 reference_shared.ids[0]=101;reference_shared.ids[1]=102;
 reference_shared.command_state=TY_CMD_READY;poll_both();
 assert(c.phase==AMP_MB_BUSY && c.service.phase==TY_ADMISSION);
 /* Linux cannot change the private copy; poison every ingress word now. */
 for(unsigned i=0;i<AMP_REQUEST_WORDS;i++)ingress[i]=UINT32_MAX;
 assert(c.private_shared.tokens==2 && ids[0]==101 && ids[1]==102);
}
static void active(void) {
 mmio[1]=ref_mmio[1]=18;mmio[0x88/4]=ref_mmio[0x88/4]=1;
 for(unsigned i=0;i<8;i++)mmio[0x90/4+i]=ref_mmio[0x90/4+i]=mmio[0x20/4+i];
 mmio[0xc4/4]=ref_mmio[0xc4/4]=2;mmio[0xc8/4]=ref_mmio[0xc8/4]=2;
 poll_both();assert(c.service.phase==TY_CORE);
}
static void check_result(void) {
 const struct ti_record *r=&reference_shared.result;
 assert(c.phase==AMP_MB_SEALED && result[0]==AMP_RESULT_MAGIC && result[1]==1 && result[2]==1);
 assert(result[3]==reference_shared.result_sequence && result[4]==reference_shared.result_origin);
 assert(result[5]==r->outcome && result[6]==r->label && result[7]==r->reserved_score && result[8]==r->elapsed);
 assert(result[9]==(uint32_t)r->identity.session && result[10]==(uint32_t)(r->identity.session>>32));
 assert(result[11]==(uint32_t)r->identity.request && result[12]==(uint32_t)(r->identity.request>>32));
 for(unsigned i=0;i<8;i++) {
  const uint8_t *p=r->identity.contract+4*i;
  assert(result[13+i]==((uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3]));
 }
 for(unsigned i=21;i<AMP_RESULT_WORDS;i++)assert(!result[i]);
 if(result[5]!=TI_ACCEPTED)assert(!result[6] && !result[7]);
 uint32_t saved[AMP_RESULT_WORDS];for(unsigned i=0;i<AMP_RESULT_WORDS;i++)saved[i]=result[i];
 mmio[0]=0;ingress[2]=1;ingress[3]=8;
 for(unsigned i=0;i<100;i++)amp_mailbox_poll(&c);
 assert(mmio[0]==0);for(unsigned i=0;i<AMP_RESULT_WORDS;i++)assert(result[i]==saved[i]);
}
static void finish(unsigned outcome,unsigned wrong_identity,unsigned wrong_label) {
 mmio[1]=ref_mmio[1]=20;
 mmio[0xb0/4]=ref_mmio[0xb0/4]=outcome|((c.service.proposal.label+wrong_label)<<16);
 if(outcome!=TI_ACCEPTED)mmio[0xb0/4]=ref_mmio[0xb0/4]=outcome;
 mmio[0xb4/4]=ref_mmio[0xb4/4]=0;mmio[0xb8/4]=ref_mmio[0xb8/4]=91;
 if(wrong_identity)mmio[0x88/4]=ref_mmio[0x88/4]=99;
 poll_both();check_result();
}
int main(void) {
 unsigned mutations=0;
 /* Every bit in the request: reject malformed vectors or copy only validated
  * shapes/IDs. Unused uint16 token slots may change without affecting input. */
 for(unsigned word=0;word<AMP_REQUEST_WORDS;word++)for(unsigned bit=0;bit<32;bit++) {
  setup();ingress[word]^=UINT32_C(1)<<bit;amp_mailbox_poll(&c);mutations++;
  assert(c.phase==AMP_MB_SEALED || c.phase==AMP_MB_BUSY || c.phase==AMP_MB_READY);
  if(c.phase==AMP_MB_SEALED) {
   assert(result[4]==0 && result[5]==TI_INVALID && !result[6] && !result[7]);
   assert(!mmio[0x10/4]);
  } else if(c.phase==AMP_MB_BUSY) {
   assert(c.private_shared.tokens>0 && c.private_shared.tokens<=128);
   assert(c.private_shared.first<c.private_shared.tokens && c.private_shared.count);
   assert(c.private_shared.count<=c.private_shared.tokens-c.private_shared.first);
   for(unsigned i=0;i<c.private_shared.tokens;i++)assert(ids[i]<30522);
  }
 }
 /* Matched real frozen service/driver/head, comparing every MMIO register,
  * poll transition, input ID and canonical output after each step. This is a
  * software trace regression; it does not measure FPGA cycles or board WCET. */
 for(unsigned outcome=1;outcome<=6;outcome++) {
  setup();submit();active();
  mmio[0xcc/4]=ref_mmio[0xcc/4]=18;poll_both();
  mmio[0xcc/4]=ref_mmio[0xcc/4]=30;poll_both();
  assert(c.service.phase==TY_TERMINAL);finish(outcome,0,0);
 }
 setup();submit();active();mmio[0xcc/4]=ref_mmio[0xcc/4]=30;poll_both();finish(1,1,0);
 setup();submit();active();mmio[0xcc/4]=ref_mmio[0xcc/4]=30;poll_both();finish(1,0,1);
 setup();submit();
 mmio[0x88/4]=ref_mmio[0x88/4]=1;
 for(unsigned i=0;i<8;i++)mmio[0x90/4+i]=ref_mmio[0x90/4+i]=mmio[0x20/4+i];
 mmio[0xcc/4]=ref_mmio[0xcc/4]=16;finish(5,0,0);
 printf("PASS %u wire-bit mutations; 9 matched service traces; one-shot sealing; no ingress reads after submission\n",mutations);
 return 0;
}
