#include "mailbox.h"
static void fence(void) {
#if defined(__arm__)
 __asm__ volatile("dmb sy":::"memory");
#else
 __asm__ volatile("":::"memory");
#endif
}
static void publish(struct amp_mailbox *c) {
 const struct ty_shared *s=&c->private_shared;
 const struct ti_record *r=&s->result;
 uint32_t v[AMP_RESULT_WORDS]={0};
 v[0]=AMP_RESULT_MAGIC;v[1]=1;v[3]=s->result_sequence;
 v[4]=s->result_origin;v[5]=r->outcome;v[6]=r->label;v[7]=r->reserved_score;
 v[8]=r->elapsed;v[9]=(uint32_t)r->identity.session;v[10]=(uint32_t)(r->identity.session>>32);
 v[11]=(uint32_t)r->identity.request;v[12]=(uint32_t)(r->identity.request>>32);
 for(unsigned i=0;i<8;i++) {
  const uint8_t *p=r->identity.contract+i*4;
  v[13+i]=(uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3];
 }
 /* APU cannot write publication word. Unpublished fields must not be consumed.
  * Actual cache mapping/barriers across processors need target qualification. */
 for(unsigned i=0;i<AMP_RESULT_WORDS;i++)c->result[i]=v[i];
 fence();c->result[2]=1;fence();c->phase=AMP_MB_SEALED;
}
static void reject(struct amp_mailbox *c,uint32_t sequence,uint8_t outcome) {
 struct ty_shared *s=&c->private_shared;
 s->result=(struct ti_record){0};s->result.identity=c->service.identity;
 s->result.outcome=outcome;s->result_sequence=sequence;s->result_origin=0;
 publish(c);
}
int amp_mailbox_init(struct amp_mailbox *c,uint64_t session,int verified,
 const volatile uint32_t *ingress,volatile uint32_t *result,volatile uint32_t *mmio,
 volatile uint32_t *permit,volatile uint16_t *ids,const volatile int8_t *hidden,
 struct ti_input *input) {
 if(!c || !permit)return 0;
 permit[0]=0;fence();
 c->phase=AMP_MB_SEALED;
 if(!verified || !session || !ingress || !result || !mmio || !ids || !hidden || !input)return 0;
 c->ingress=ingress;c->result=result;c->session=session;
 c->private_shared=(struct ty_shared){0};
 c->private_shared.magic=TY_CONFIG_MAGIC;c->private_shared.version=TY_SHARED_VERSION;
 c->private_shared.session=session;c->private_shared.exclusive_buffers_attested=1;
 for(unsigned i=0;i<AMP_RESULT_WORDS;i++)result[i]=0;
 fence();
 if(!ty_service_init(&c->service,mmio,permit,ids,hidden,&c->private_shared,input,verified))return 0;
 c->phase=AMP_MB_BOOT;return 1;
}
void amp_mailbox_poll(struct amp_mailbox *c) {
 if(c->phase==AMP_MB_SEALED)return;
 if(c->phase==AMP_MB_BOOT) {
  ty_service_poll(&c->service);
  if(c->service.phase==TY_IDLE)c->phase=AMP_MB_READY;
  return;
 }
 if(c->phase==AMP_MB_READY) {
  const volatile uint32_t *p=c->ingress;
  if(p[2]!=1)return;
  uint32_t before=p[3],v[AMP_REQUEST_WORDS];
  fence();for(unsigned i=0;i<AMP_REQUEST_WORDS;i++)v[i]=p[i];fence();
  uint32_t after=p[3],ready=p[2];
  int valid=v[0]==AMP_REQUEST_MAGIC && v[1]==1 && v[2]==1 && v[3] &&
   before==v[3] && after==v[3] && ready==1 &&
   ((uint64_t)v[4]|(uint64_t)v[5]<<32)==c->session &&
   v[6]>0 && v[6]<=128 && v[7]<v[6] && v[8]>0 && v[8]<=v[6]-v[7] && v[9];
  for(unsigned i=10;i<16;i++)if(v[i])valid=0;
  for(unsigned i=144;i<AMP_REQUEST_WORDS;i++)if(v[i])valid=0;
  for(unsigned i=0;i<128;i++)if(v[16+i]>65535 || (i<v[6] && v[16+i]>=30522))valid=0;
  if(!valid){reject(c,v[3],TI_INVALID);return;}
  struct ty_shared *s=&c->private_shared;
  s->sequence=v[3];s->tokens=(uint16_t)v[6];s->first=(uint16_t)v[7];
  s->count=(uint16_t)v[8];s->budget=v[9];
  for(unsigned i=0;i<128;i++)s->ids[i]=(uint16_t)v[16+i];
  s->command_state=TY_CMD_READY;c->phase=AMP_MB_BUSY;
 }
 ty_service_poll(&c->service);
 if(c->private_shared.command_state==TY_CMD_DONE)publish(c);
 else if(c->service.phase==TY_HALTED)reject(c,c->private_shared.sequence,TI_FAULT);
}
