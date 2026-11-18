#ifndef TYPED_BOOT_PMU_SEAL_H
#define TYPED_BOOT_PMU_SEAL_H
#include "xpfw_default.h"
#include "xpfw_module.h"
int TypedBootIpi(u32 ipi,u32 source,const u32 *p,u32 words);
int TypedBootEvent(const XPfw_Module_t *mod,u32 event);
int TypedBootClosed(void);
void TypedBootService(void);
#endif
