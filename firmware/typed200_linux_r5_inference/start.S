.syntax unified
.cpu cortex-r5
.fpu vfpv3-d16
.arm
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
.section .text.start,"ax",%progbits
reset:
 cpsid if
 cps #0x11
 ldr sp,=0xfb00
 cps #0x12
 ldr sp,=0xfa00
 cps #0x17
 ldr sp,=0xfd00
 cps #0x1b
 ldr sp,=0xfc00
 cps #0x1f
 ldr sp,=0xfe00
 cps #0x13
 ldr sp,=0xff00
 mrc p15,0,r0,c1,c0,0
 ldr r1,=0x1005
 tst r0,r1
 bne bad_reset
 bic r0,r0,#0x2000
 mcr p15,0,r0,c1,c0,0
 dsb sy
 isb
 mrc p15,0,r0,c1,c0,2
 orr r0,r0,#0x00f00000
 mcr p15,0,r0,c1,c0,2
 isb
 mov r0,#0x40000000
 vmsr fpexc,r0
 mov r0,#0
 vmsr fpscr,r0
 bl main_r5
bad_reset: mov r0,#9
 b exception
bad_undefined: mov r0,#1
 b exception
bad_svc: mov r0,#2
 b exception
bad_prefetch: mov r0,#3
 b exception
bad_abort: mov r0,#4
 b exception
bad_reserved: mov r0,#5
 b exception
bad_irq: mov r0,#6
 b exception
bad_fiq: mov r0,#7
 b exception
