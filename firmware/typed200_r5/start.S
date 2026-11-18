.syntax unified
.cpu cortex-r5
.fpu vfpv3-d16
.arm
.section .vectors,"ax",%progbits
.global _vector_table
_vector_table:
    b _reset
    b _undefined
    b _svc_trap
    b _prefetch
    b _abort
    b _reserved
    b _irq
    b _fiq
.section .text.start,"ax",%progbits
.global _reset
_reset:
    cpsid if
    cps #0x11
    ldr sp,=__fiq_stack_top
    cps #0x12
    ldr sp,=__irq_stack_top
    cps #0x17
    ldr sp,=__abort_stack_top
    cps #0x1b
    ldr sp,=__undef_stack_top
    cps #0x1f
    ldr sp,=__system_stack_top
    cps #0x13
    ldr sp,=__svc_stack_top
    mov r0,#0
    mcr p15,0,r0,c12,c0,0
    isb
    /* Loader contract: reset entry, caches/MPU off, initialized split TCM. */
    mrc p15,0,r0,c1,c0,0
    ldr r1,=0x1005
    tst r0,r1
    bne _bad_loader
    /* Select low vectors explicitly; VBAR alone does not clear SCTLR.V. */
    bic r0,r0,#0x2000
    mcr p15,0,r0,c1,c0,0
    isb
    /* AMD standalone boot.S policy: normal GHT/return stack prediction,
       DBWR disabled for Cortex-R5 erratum 780125. Prediction is NOT a WCET proof. */
    mrc p15,0,r0,c1,c0,1
    bic r0,r0,#0x20000
    bic r0,r0,#0x10000
    bic r0,r0,#0x8000
    orr r0,r0,#0x4000
    mcr p15,0,r0,c1,c0,1
    dsb
    isb
    mrc p15,0,r0,c1,c0,2
    orr r0,r0,#0x00f00000
    mcr p15,0,r0,c1,c0,2
    isb
    mov r0,#0x40000000
    vmsr fpexc,r0
    mov r0,#0
    vmsr fpscr,r0
    vmov d0,r0,r0
    vmov d1,r0,r0
    vmov d2,r0,r0
    vmov d3,r0,r0
    vmov d4,r0,r0
    vmov d5,r0,r0
    vmov d6,r0,r0
    vmov d7,r0,r0
    vmov d8,r0,r0
    vmov d9,r0,r0
    vmov d10,r0,r0
    vmov d11,r0,r0
    vmov d12,r0,r0
    vmov d13,r0,r0
    vmov d14,r0,r0
    vmov d15,r0,r0
    ldr r1,=__bss_start
    ldr r2,=__bss_end
1:  cmp r1,r2
    strlo r0,[r1],#4
    blo 1b
    bl ty_mpu_init
    bl ty_r5_main
    mov r0,#8
    b ty_exception
_undefined: mov r0,#1
    b ty_exception
_svc_trap: mov r0,#2
    b ty_exception
_prefetch: mov r0,#3
    b ty_exception
_abort: mov r0,#4
    b ty_exception
_reserved: mov r0,#5
    b ty_exception
_irq: mov r0,#6
    b ty_exception
_fiq: mov r0,#7
    b ty_exception
_bad_loader: mov r0,#9
    b ty_exception
