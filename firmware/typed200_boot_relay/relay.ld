ENTRY(_relay_start)
MEMORY {
 CODE (rx) : ORIGIN = 0x10000000, LENGTH = 0xc0000
 RAM (rw) : ORIGIN = 0x100c0000, LENGTH = 0x10000
}
PHDRS { code PT_LOAD FLAGS(5); ram PT_LOAD FLAGS(6); }
SECTIONS {
 .text : { KEEP(*(.text.start)) *(.text*) *(.rodata*) } >CODE :code
 .data : { *(.data*) } >RAM :ram
 .bss (NOLOAD) : { . = ALIGN(8); __relay_bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __relay_bss_end = .; } >RAM :ram
 .stack (NOLOAD) : { . = ALIGN(16); . += 16384; __relay_stack_top = .; } >RAM :ram
 /DISCARD/ : { *(.comment) *(.note*) *(.llvm_addrsig) *(.eh_frame*) }
 ASSERT(__relay_stack_top <= 0x100d0000,"relay stack outside reservation")
}
