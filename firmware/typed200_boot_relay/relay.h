#ifndef TYPED200_BOOT_RELAY_H
#define TYPED200_BOOT_RELAY_H
#include <stdint.h>
#include <stddef.h>
#define RELAY_INPUT UINT32_C(0x100f0000)
#define RELAY_STATUS UINT32_C(0x100f1000)
#define RELAY_DEST_INPUT UINT32_C(0xfffee000)
int relay_destination_valid(uint64_t address,uint64_t filesz,uint64_t memsz);
void relay_main(void);
void relay_fault(uint32_t why) __attribute__((noreturn));
#endif
