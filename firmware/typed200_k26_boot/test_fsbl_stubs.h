#include <stdint.h>
typedef uint32_t u32;typedef uint64_t u64;
typedef struct {u32 BaseAddress;} XIpiPsu_Config;
typedef struct {u32 unused;} XIpiPsu;
#define XIPIPSU_MAX_MSG_LEN 8
#define XFSBL_HANDOFFEXIT 1
#define XFSBL_SUCCESS 0
#define XST_SUCCESS 0
#define PMU_GLOBAL_PWR_STATE_R5_0_MASK 0x400
#define PMU_GLOBAL_PWR_STATE_R5_1_MASK 0x800
#define XIPIPSU_BUF_TYPE_MSG 0
#define XIPIPSU_BUF_TYPE_RESP 1
extern u64 tb_host_mpidr,tb_host_el;
void tb_host_fail(u32) __attribute__((noreturn));
u32 Xil_In32(u32);
void Xil_Out32(u32,u32);
u32 XFsbl_PowerUpIsland(u32);
void usleep(u32);
XIpiPsu_Config *XIpiPsu_LookupConfig(u32);
u32 XIpiPsu_CfgInitialize(XIpiPsu *,XIpiPsu_Config *,u32);
u32 XIpiPsu_WriteMessage(XIpiPsu *,u32,u32 *,u32,unsigned);
u32 XIpiPsu_TriggerIpi(XIpiPsu *,u32);
u32 XIpiPsu_PollForAck(const XIpiPsu *,u32,u32);
u32 XIpiPsu_ReadMessage(XIpiPsu *,u32,u32 *,u32,unsigned);
void TypedBootFinal(u64,u32);
