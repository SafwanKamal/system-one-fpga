ENTRY(_vector_table)
MEMORY {
  ATCM (rx) : ORIGIN = 0x00000000, LENGTH = 0x0000f000
  ESTACK (rw) : ORIGIN = 0x0000f000, LENGTH = 0x00001000
  BTCM (rw) : ORIGIN = 0x00020000, LENGTH = 0x0000d000
  SVCSTACK (rw) : ORIGIN = 0x0002d000, LENGTH = 0x00002000
  SHARED (rw) : ORIGIN = 0x0002f000, LENGTH = 0x00001000
}
PHDRS { code PT_LOAD FLAGS(5); estack PT_LOAD FLAGS(6); data PT_LOAD FLAGS(6); stack PT_LOAD FLAGS(6); shared PT_LOAD FLAGS(6); }
SECTIONS {
  .vectors : { KEEP(*(.vectors)) } >ATCM :code
  .text : { *(.text.start) *(.text*) } >ATCM :code
  .rodata : { *(.rodata*) } >ATCM :code
  .ARM.exidx : { *(.ARM.exidx*) } >ATCM :code
  .exception_stacks (NOLOAD) : {
    . += 256; __fiq_stack_top = .; . += 256; __irq_stack_top = .;
    . += 256; __abort_stack_top = .; . += 256; __undef_stack_top = .;
    . += 256; __system_stack_top = .;
  } >ESTACK :estack
  .data : { *(.data*) } >BTCM :data
  .bss (NOLOAD) : { . = ALIGN(8); __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; } >BTCM :data
  .svc_stack (NOLOAD) : { . += 8192; __svc_stack_top = .; } >SVCSTACK :stack
  .shared (NOLOAD) : { KEEP(*(.shared)) } >SHARED :shared
  /DISCARD/ : { *(.comment) *(.note*) *(.llvm_addrsig) }
  ASSERT(SIZEOF(.shared)<=4096,"shared mailbox overflow")
  ASSERT(__bss_end<=ORIGIN(BTCM)+LENGTH(BTCM),"BTCM work overflow")
}
