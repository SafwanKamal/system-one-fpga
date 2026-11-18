ENTRY(_start)
PHDRS {code PT_LOAD FLAGS(5); trace PT_LOAD FLAGS(6);}
SECTIONS {
 . = 0;
 .text : {KEEP(*(.vectors)) *(.text*) *(.rodata*) . = ALIGN(8);} :code
 ASSERT(. < 0xb000,"private TCM code overflow")
 . = 0xc000;
 .trace : {KEEP(*(.trace)) . = ALIGN(8);} :trace
 .bss (NOLOAD) : {*(.bss*) *(COMMON) . = ALIGN(8);} :trace
 ASSERT(. < 0xe000,"private TCM work overflow")
 /DISCARD/ : {*(.ARM.exidx*) *(.ARM.extab*) *(.comment*)}
}
