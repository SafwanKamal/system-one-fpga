#include "ownership.h"
static int write_address(uint32_t a) {
 if(a&3u)return 0;
 /* Only protection registers. No reset/PLL/DDR timing/GPIO/CSU write API. */
 if(a>=0xfd000000u && a<0xfd060000u) {
  uint32_t o=a&0xffffu;
  return o==0 || o==0xcu || o==0x20u || (o>=0x100 && o<0x200);
 }
 if((a>=0xfd5d0000u && a<0xfd5d0200u) ||
    (a>=0xffa70000u && a<0xffa70200u)) {
  uint32_t o=a&0xffffu;
  return o==0 || o==0xcu || o==0x20u || (o>=0x100 && o<0x200);
 }
 if(a==0xff980000u || (a>=0xff980100u && a<0xff980150u) ||
    (a>=0xff981000u && a<0xff981644u))return 1;
 return 0;
}
int amp_install(const struct amp_io *io,struct amp_owner *s,uint64_t session,
 uint32_t gates,const struct amp_write *p,size_t n) {
 if(!io || !s || !io->read || !io->write || !io->barrier)return 0;
 /* Off first, including every validation/failure path. No rollback/unseal. */
 io->write(io->ctx,AMP_PERMIT,0);io->barrier(io->ctx);
 if(s->phase!=AMP_BOOT || !session || gates!=AMP_GATES || !p || !n || n>2048 ||
    io->read(io->ctx,AMP_PERMIT)!=0)goto bad;
 for(size_t i=0;i<n;i++)if(!write_address(p[i].address) || !p[i].mask ||
    (p[i].value&~p[i].mask))goto bad;
 for(size_t i=0;i<n;i++) {
  uint32_t v=io->read(io->ctx,p[i].address);
  io->write(io->ctx,p[i].address,(v&~p[i].mask)|p[i].value);
  io->barrier(io->ctx);
  if((io->read(io->ctx,p[i].address)&p[i].mask)!=p[i].value) {
   s->failed_step=(uint32_t)i+1;goto bad;
  }
 }
 /* Re-read final register images after all writes, not intermediate disables.
  * Lock readback is necessary, but target denial tests remain a separate gate. */
 for(size_t i=0;i<n;i++) {
  int final=1;
  for(size_t j=i+1;j<n;j++)if(p[j].address==p[i].address)final=0;
  if(final && (io->read(io->ctx,p[i].address)&p[i].mask)!=p[i].value) {
   s->failed_step=(uint32_t)i+1;goto bad;
  }
 }
 if(io->read(io->ctx,AMP_PERMIT)!=0)goto bad;
 s->session=session;s->phase=AMP_OWNED;return 1;
bad:
 s->phase=AMP_QUARANTINED;
 io->write(io->ctx,AMP_PERMIT,0);io->barrier(io->ctx);return 0;
}
static int zeros(const uint32_t *p,size_t first) {
 for(size_t i=first;i<6;i++)if(p[i])return 0;
 return 1;
}
int amp_pm_allow(const struct amp_owner *s,uint32_t ipi,uint32_t source,
 const uint32_t *p,size_t n) {
 /* APU=1, RPU0=0x100 in the pinned PMU BSP. Others never forward after lease.
  * Only bit24 (ATF security attribute) may accompany a canonical PM API byte.
  * Unknown module IDs, extra flags, malformed lengths and arguments fail closed. */
 if(!s || s->phase!=AMP_OWNED || !s->session || ipi ||
    (source!=1 && source!=0x100) || !p || n!=6 || (p[0]&~0x010000ffu))return 0;
 switch(p[0]&0xffu) {
  case 1: case 24: return zeros(p,1); /* version/chipid */
  case 18: return p[1]>=1000 && p[1]<1120 && zeros(p,2); /* reset status */
  case 38: case 44: return p[1]<=112 && zeros(p,2); /* clock state/parent */
  case 40: return p[1]<=112 && p[2]<=1 && zeros(p,3); /* divider read */
  default:return 0;
 }
}
int amp_pm_event_allow(const struct amp_owner *s,int is_safety) {
 /* Must be used for ALL non-IPI event/scheduler paths during owned/quarantine.
  * Safety shutdown stays allowed; it invalidates the uninterrupted-clock run. */
 return s && (s->phase==AMP_BOOT || is_safety);
}
