#ifndef FUNCTIONGEMMA_TOKEN_WIRE_H
#define FUNCTIONGEMMA_TOKEN_WIRE_H
#include <stddef.h>
#include <stdint.h>

/* Proposed offline boundary only. Not the currently deployed R5 ABI. */
enum fg_token_status {
    FG_TOKEN_OK=0, FG_TOKEN_ARGUMENT, FG_TOKEN_HEADER, FG_TOKEN_IDENTITY,
    FG_TOKEN_BOUNDS, FG_TOKEN_EXTENT, FG_TOKEN_CRC, FG_TOKEN_ID
};
struct fg_prompt_view {
    const uint8_t *payload;
    uint32_t count;
    uint32_t output_reserve;
};
enum fg_token_status fg_prompt_parse(const uint8_t *data, size_t length,
    const uint8_t expected_model_sha[32], struct fg_prompt_view *view);
enum fg_token_status fg_prompt_token(const struct fg_prompt_view *view,
    uint32_t index, uint32_t *token);
#endif
