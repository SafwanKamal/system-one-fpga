.syntax unified
.cpu cortex-r5
.arm
/* Diagnostic only: execute from a verified, saved no-map DDR window, not TCM.
 * No inference, deadline, exclusive-memory, or qualified reset-entry claim.
 * Debugger loads and starts this image only after the PL probe is verified.
 */
.section .vectors,"ax",%progbits
.global _start
_start:
 b probe_reset
 b probe_undefined
 b probe_svc
 b probe_prefetch
 b probe_abort
 b probe_reserved
 b probe_irq
 b probe_fiq
.section .text,"ax",%progbits
probe_reset:
 cpsid if
 cps #0x13
 ldr sp,=0x63f10000
 ldr r0,=0x63f00000
 mcr p15,0,r0,c12,c0,0
 isb
 ldr r8,=probe_results
 mov r0,#1
 str r0,[r8,#8]
 mrs r0,cpsr
 str r0,[r8,#12]
 mrc p15,0,r0,c0,c0,0
 str r0,[r8,#16]
 mrc p15,0,r0,c1,c0,0
 str r0,[r8,#20]
 ldr r1,=0x1005
 tst r0,r1
 bne probe_bad_state
 bic r0,r0,#0x2000
 mcr p15,0,r0,c1,c0,0
 dsb sy
 isb
 ldr r4,=0xa0000000
 ldr r0,[r4]
 str r0,[r8,#24]
 ldr r1,=0x4f524731
 cmp r0,r1
 bne probe_bad_image
 ldr r0,[r4,#0x18]
 str r0,[r8,#28]
 ldr r0,[r4,#0x1c]
 str r0,[r8,#32]
 mov r5,#4
 ldr r6,=0x52350004
1:
 str r6,[r4,r5,lsl #2]
 dsb sy
 add r5,r5,#1
 add r6,r6,#1
 cmp r5,#8
 blo 1b
 dsb sy
 ldr r0,=0xd00d0001
 str r0,[r8,#8]
 dsb sy
2:
 wfi
 b 2b
probe_bad_state:
 ldr r0,=0xe0000001
 b probe_fail
probe_bad_image:
 ldr r0,=0xe0000002
 b probe_fail
probe_undefined: mov r0,#1
 b probe_exception
probe_svc: mov r0,#2
 b probe_exception
probe_prefetch: mov r0,#3
 b probe_exception
probe_abort: mov r0,#4
 b probe_exception
probe_reserved: mov r0,#5
 b probe_exception
probe_irq: mov r0,#6
 b probe_exception
probe_fiq: mov r0,#7
probe_exception:
 orr r0,r0,#0xe1000000
probe_fail:
 ldr r8,=probe_results
 str r0,[r8,#8]
 dsb sy
 b 2b
.ltorg
.section .results,"aw",%progbits
.global probe_results
probe_results:
 .word 0x52503531,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0
