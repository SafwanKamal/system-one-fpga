ENTRY(_a53_start)
MEMORY { CODE (rx) : ORIGIN = 0xfffc0000, LENGTH = 0x20000
         RAM (rw) : ORIGIN = 0xfffe0000, LENGTH = 0xc000 }
PHDRS { code PT_LOAD FLAGS(5); ram PT_LOAD FLAGS(6); }
SECTIONS {
 .text : { KEEP(*(.text.start)) *(.text*) *(.rodata*) } >CODE :code
 .data : { *(.data*) } >RAM :ram
 .bss (NOLOAD) : { . = ALIGN(8); __a53_bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __a53_bss_end = .; } >RAM :ram
 .stack (NOLOAD) : { . = ALIGN(16); . += 16384; __a53_stack_top = .; } >RAM :ram
 /DISCARD/ : { *(.comment) *(.note*) *(.llvm_addrsig) *(.eh_frame*) }
}
