.arch armv8-a
.section .text.start,"ax"
.global _relay_start
_relay_start:
    msr daifset,#15
    mrs x0,CurrentEL
    cmp x0,#12
    b.ne 9f
    mrs x0,sctlr_el3
    mov x1,#0x1005
    tst x0,x1
    b.ne 9f
    mrs x0,mpidr_el1
    and x0,x0,#0xff
    cbnz x0,9f
    msr spsel,#1
    ldr x0,=__relay_stack_top
    mov sp,x0
    adr x0,_relay_vectors
    msr vbar_el3,x0
    isb
    ldr x0,=__relay_bss_start
    ldr x1,=__relay_bss_end
1:  cmp x0,x1
    b.hs 2f
    str xzr,[x0],#8
    b 1b
2:  bl relay_main
9:  wfi
    b 9b
.balign 2048
_relay_vectors:
.rept 16
    mov w0,#0x80
    b relay_fault
    .balign 128
.endr
