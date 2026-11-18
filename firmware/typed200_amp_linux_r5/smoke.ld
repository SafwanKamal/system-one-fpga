ENTRY(_start)
PHDRS { code PT_LOAD FLAGS(5); metadata PT_LOAD FLAGS(6); trace PT_LOAD FLAGS(6); }
SECTIONS {
 . = 0;
 .text : { KEEP(*(.vectors)) *(.text*) *(.rodata*) } :code
 ASSERT(. <= 0x800,"TCM code exceeds private page allocation")
 . = 0x800;
 .resource_table : { KEEP(*(.resource_table)) } :metadata
 ASSERT(. <= 0x1000,"Resource table overlaps private trace")
 . = 0x1000;
 .trace : { KEEP(*(.trace)) } :trace
 ASSERT(. <= 0x2000,"Trace exceeds private TCM allocation")
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
