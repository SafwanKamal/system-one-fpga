#include "abi.h"
struct head {uint32_t classes,stream,scales,recip,kind;};
#include "heads.inc"

int compute_heads(volatile struct shared *m) {
 if(!m->tokens || m->tokens>128 || !m->jobs || m->jobs>MAX_JOBS)return 1;
 for(uint32_t j=0;j<m->jobs;j++) {
  volatile struct job *job=&m->job[j];
  if(job->head>=sizeof(heads)/sizeof(heads[0]) || !job->count || job->count>m->tokens)return 2;
  const struct head *h=&heads[job->head];
  if(h->classes>MAX_CLASSES)return 3;
  int32_t pooled[384];
  for(uint32_t r=0;r<job->count;r++)if(job->rows[r]>=m->tokens || (r && job->rows[r]<=job->rows[r-1]))return 4;
  /* A token head receives one selected row per job, retaining wordpiece rules. */
  if(h->kind==1 && job->count!=1)return 5;
  uint32_t recip=*(const volatile uint32_t *)(uintptr_t)(h->recip+4*job->count);
  for(uint32_t d=0;d<384;d++) {
   int32_t sum=0;
   for(uint32_t r=0;r<job->count;r++)sum+=*(const volatile int8_t *)(uintptr_t)(HIDDEN+384*job->rows[r]+d);
   pooled[d]=h->kind==1 ? sum : (int32_t)(((int64_t)sum*recip+32768)>>16);
  }
  double best=0;uint32_t label=0;
  for(uint32_t c=0;c<h->classes;c++) {
   uint32_t tile=h->stream+(c/32)*(256+24*512);
   int64_t acc=*(const volatile int32_t *)(uintptr_t)(tile+(c%32)*8);
   for(uint32_t d=0;d<384;d++) {
    int8_t w=*(const volatile int8_t *)(uintptr_t)(tile+256+(d/16)*512+(c%32)*16+d%16);
    acc+=(int64_t)pooled[d]*w;
   }
   if(acc>2147483647LL || acc<(-2147483647LL-1))return 6;
   job->logits[c]=(int32_t)acc;
   float scale=*(const volatile float *)(uintptr_t)(h->scales+c*4);
   double score=(double)(int32_t)acc*(double)scale;
   if(!c || score>best){best=score;label=c;}
  }
  job->label=label;job->classes=h->classes;
 }
 return 0;
}

#ifndef HOST_TEST
static inline void fence(void){__asm__ volatile("dsb sy":::"memory");}
static volatile struct shared * const box=(volatile struct shared *)BOX;
__attribute__((section(".trace"))) volatile char trace[128]="R5: WAIT\n";
static void message(const char *s){for(uint32_t i=0;i<127;i++){trace[i]=s[i];if(!s[i])break;}fence();}
__attribute__((noreturn)) void exception(uint32_t why) {
 box->error=0x80000000u|why;fence();box->state=4;message("R5: EXCEPTION\n");
 for(;;)__asm__ volatile("wfi");
}
void main_r5(void) {
 volatile uint32_t *csr=(volatile uint32_t *)0xa0000000u;
 if(box->magic!=0x52354931 || box->version!=1 || box->state!=1)exception(10);
 box->state=2;box->phase=1;fence();
 if(csr[0x14/4]!=0x53595332 || csr[0x18/4]!=0x20804004 || csr[0x1c/4]!=0x5377ffff || (csr[0]&1))exception(11);
 if(!box->tokens || box->tokens>128 || !box->jobs || box->jobs>MAX_JOBS)exception(12);
 for(uint32_t i=0;i<box->tokens;i++) {
  if(box->ids[i]>=30522)exception(13);
  ((volatile uint16_t *)IDS)[i]=box->ids[i];
 }
 fence();csr[0x20/4]=PROGRAM;csr[0x24/4]=(384u<<16)|box->tokens;
 csr[0x28/4]=IDS;csr[0x2c/4]=HIDDEN;box->phase=2;fence();csr[0]=1;fence();
 uint32_t poll=0;
 while(!(csr[0]&2)){if(++poll==50000000u)exception(14);}
 box->encoder_clocks=csr[8/4];box->total_clocks=csr[12/4];box->status=csr[4/4];
 csr[0]=2;fence();box->phase=3;fence();
 if(box->status)exception(15);
 uint32_t error=compute_heads(box);if(error)exception(20+error);
 fence();box->phase=4;message("R5: INFERENCE PASS\n");box->state=3;fence();
 for(;;)__asm__ volatile("wfi");
}
#endif
