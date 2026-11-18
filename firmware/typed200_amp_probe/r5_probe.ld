ENTRY(_start)
PHDRS { code PT_LOAD FLAGS(5); result PT_LOAD FLAGS(6); }
SECTIONS {
 . = 0x63f00000;
 .text : { KEEP(*(.vectors)) *(.text*) *(.rodata*) } :code
 ASSERT(. <= 0x63f01000,"probe code exceeded one page")
 . = 0x63f0f000;
 .results : { KEEP(*(.results)) } :result
 ASSERT(. <= 0x63f0f100,"probe result exceeded reserved area")
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
