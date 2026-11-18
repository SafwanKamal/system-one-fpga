#ifndef TY_SHA256_H
#define TY_SHA256_H
#include <stdint.h>
#include <stddef.h>
void ty_sha256(const volatile uint8_t *,size_t,uint8_t out[32]);
#endif
