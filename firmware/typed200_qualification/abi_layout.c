/* Compile-only probes for the frozen public mailbox; never linked into v8. */
#include "../typed200_r5/service.h"
#define AT(type,member,offset) _Static_assert(offsetof(type,member)==offset,"ABI " #member)
_Static_assert(sizeof(struct ti_record)==64,"record size");
_Static_assert(sizeof(struct ty_shared)==384,"shared size");
AT(struct ti_record,identity,0);
AT(struct ti_identity,session,0);
AT(struct ti_identity,request,8);
AT(struct ti_identity,contract,16);
AT(struct ti_record,elapsed,48);
AT(struct ti_record,label,52);
AT(struct ti_record,reserved_score,54);
AT(struct ti_record,outcome,56);
AT(struct ty_shared,magic,0);
AT(struct ty_shared,version,4);
AT(struct ty_shared,session,8);
AT(struct ty_shared,exclusive_buffers_attested,16);
AT(struct ty_shared,boot_status,20);
AT(struct ty_shared,command_state,24);
AT(struct ty_shared,sequence,28);
AT(struct ty_shared,tokens,32);
AT(struct ty_shared,first,34);
AT(struct ty_shared,count,36);
AT(struct ty_shared,reserved,38);
AT(struct ty_shared,budget,40);
AT(struct ty_shared,ids,44);
AT(struct ty_shared,result_sequence,300);
AT(struct ty_shared,result_origin,304);
AT(struct ty_shared,result,312);
AT(struct ty_shared,exception_reason,376);
#undef AT
