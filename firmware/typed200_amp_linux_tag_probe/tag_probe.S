.syntax unified
.cpu cortex-r5
.arm
/* Separate Linux-managed origin diagnostic. Private TCM plus fixed PL probe.
 * No DDR, PS MMIO, timer, IPI, admission or inference operation.
 */
.section .vectors,"ax",%progbits
.global _start
_start:
 b reset
 b bad_undefined
 b bad_svc
 b bad_prefetch
 b bad_abort
 b bad_reserved
 b bad_irq
 b bad_fiq

.section .text,"ax",%progbits
reset:
 cpsid if
 cps #0x13
 ldr sp,=0xff00
 /* Cortex-R5 has no VBAR. Low vectors are selected by SCTLR.V below. */
 isb
 mrc p15,0,r8,c1,c0,0
 mrs r9,cpsr
 mrc p15,0,r10,c0,c0,0
 ldr r0,=0x1005
 tst r8,r0
 bne bad_reset_state
 and r0,r9,#0xff
 cmp r0,#0xd3
 bne bad_reset_state
 ldr r0,=0xfff0
 and r0,r10,r0
 ldr r1,=0xc150
 cmp r0,r1
 bne bad_reset_state
 bic r0,r8,#0x2000
 mcr p15,0,r0,c1,c0,0
 dsb sy
 isb
 /* Only touch the reviewed PL probe after reset-state validation. The board
  * controller verifies the installed image and completes the 64 APU writes
  * before permitting R5 entry. Each R5 access is aligned, 32-bit and ordered.
  */
 ldr r4,=0xa0000000
 ldr r0,[r4]
 ldr r1,=0x4f524731
 cmp r0,r1
 bne bad_probe_image
 ldr r0,[r4,#4]
 cmp r0,#1
 bne bad_probe_image
 ldr r0,[r4,#8]
 cmp r0,#64
 bne bad_probe_count
 ldr r0,[r4,#12]
 cmp r0,#0
 bne bad_probe_count
 ldr r11,[r4,#24]
 ldr r12,[r4,#28]
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
 ldr r0,[r4,#8]
 cmp r0,#68
 bne bad_probe_count
 ldr r0,[r4,#12]
 cmp r0,#0
 bne bad_probe_count
 /* Format in an unpublished scratch buffer. Publish by copying all fields
  * with final PASS marker last, so a reader can reject incomplete records.
  */
 ldr r0,=success_template
 ldr r1,=scratch
 bl copy_string
 mov r0,r8
 ldr r1,=scratch+(sctlr_digits-success_template)
 bl puthex
 mov r0,r9
 ldr r1,=scratch+(cpsr_digits-success_template)
 bl puthex
 mov r0,r10
 ldr r1,=scratch+(midr_digits-success_template)
 bl puthex
 mov r0,r11
 ldr r1,=scratch+(ar_digits-success_template)
 bl puthex
 mov r0,r12
 ldr r1,=scratch+(arid_digits-success_template)
 bl puthex
 ldr r0,=scratch
 ldr r1,=trace_buffer
 bl copy_string
 dsb sy
 /* Final marker is a single aligned 32-bit store, after the complete text.
  * Consumers require the marker AND the fixed text/hex schema.
  */
 ldr r0,=0x53534150
 ldr r1,=trace_buffer+4
 str r0,[r1]
 dsb sy
halt:
 wfi
 b halt

copy_string:
 ldrb r2,[r0],#1
 strb r2,[r1],#1
 cmp r2,#0
 bne copy_string
 bx lr

puthex:
 mov r2,#8
1:
 mov r3,r0,lsr #28
 cmp r3,#10
 addlo r3,r3,#48
 addhs r3,r3,#87
 strb r3,[r1],#1
 lsl r0,r0,#4
 subs r2,r2,#1
 bne 1b
 bx lr

bad_undefined: mov r7,#1
 b fail
bad_svc: mov r7,#2
 b fail
bad_prefetch: mov r7,#3
 b fail
bad_abort: mov r7,#4
 b fail
bad_reserved: mov r7,#5
 b fail
bad_irq: mov r7,#6
 b fail
bad_fiq: mov r7,#7
 b fail
bad_reset_state: mov r7,#8
 b fail
bad_probe_image: mov r7,#9
 b fail
bad_probe_count: mov r7,#10
fail:
 cpsid if
 ldr r0,=error_template
 ldr r1,=scratch
 bl copy_string
 mov r0,r7
 ldr r1,=scratch+(error_digits-error_template)
 bl puthex
 ldr r0,=scratch
 ldr r1,=trace_buffer
 bl copy_string
 dsb sy
 b halt
.ltorg

.section .rodata,"a",%progbits
success_template:
 .ascii "R5: WAIT\nSCTLR="
sctlr_digits: .ascii "00000000\nCPSR="
cpsr_digits: .ascii "00000000\nMIDR="
midr_digits: .ascii "00000000\nAR="
ar_digits: .ascii "00000000\nARID="
arid_digits: .asciz "00000000\n"
error_template:
 .ascii "R5: FAIL\nERROR="
error_digits: .asciz "00000000\n"

.section .resource_table,"aw",%progbits
.balign 4
.global resource_table
resource_table:
 .word 1,1,0,0
 .word trace_resource-resource_table
trace_resource:
 .word 2,trace_buffer,128,0
 .asciz "sysone-smoke"
 .space 32-(.-(trace_resource+16)),0

.section .trace,"aw",%progbits
.balign 4
.global trace_buffer
trace_buffer:
 .asciz "R5: WAIT\n"
 .space 128-(.-trace_buffer),0
scratch:
 .space 128,0
