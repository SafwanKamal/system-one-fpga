#ifndef R5_INFERENCE_ABI_H
#define R5_INFERENCE_ABI_H
#include <stdint.h>
#define BOX 0x62400000u
#define HIDDEN 0x62101000u
#define IDS 0x62100000u
#define PROGRAM 0x60000400u
#define MAX_JOBS 256u
#define MAX_CLASSES 384u
struct job {
 uint32_t head,count,label,classes;
 uint16_t rows[128];
 int32_t logits[MAX_CLASSES];
};
struct shared {
 uint32_t magic,version,sequence,state,error,tokens,jobs,encoder_clocks;
 uint32_t total_clocks,phase,status,reserved[5];
 uint16_t ids[128];
 struct job job[MAX_JOBS];
};
_Static_assert(sizeof(struct job)==1808,"job ABI");
_Static_assert(__builtin_offsetof(struct shared,job)==320,"mailbox ABI");
int compute_heads(volatile struct shared *m);
#endif
