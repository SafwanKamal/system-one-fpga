#include "xpfw_default.h"
#define XPFW_IPI_MAX_MSG_LEN 8u
#define XIPIPSU_BUF_TYPE_RESP 1u
extern void *Ipi0InstPtr;
int XIpiPsu_WriteMessage(void *,u32,u32 *,u32,unsigned);
