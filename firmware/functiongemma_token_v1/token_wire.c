#include "token_wire.h"

static uint32_t le32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1]<<8) |
        ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24);
}
static uint32_t crc32_bytes(const uint8_t *p, size_t length) {
    uint32_t crc=UINT32_C(0xffffffff);
    for (size_t i=0;i<length;i++) {
        crc^=p[i];
        for (unsigned bit=0;bit<8;bit++)
            crc=(crc>>1)^(UINT32_C(0xedb88320)&(0u-(crc&1u)));
    }
    return ~crc;
}
enum fg_token_status fg_prompt_parse(const uint8_t *data, size_t length,
    const uint8_t expected_model_sha[32], struct fg_prompt_view *view) {
    uint32_t count,reserve,extent;
    if (view) { view->payload=NULL;view->count=0;view->output_reserve=0; }
    if (!data || !expected_model_sha || !view) return FG_TOKEN_ARGUMENT;
    if (length<64) return FG_TOKEN_HEADER;
    if (data[0]!='F' || data[1]!='G' || data[2]!='T' || data[3]!='1' ||
        data[4]!=1 || data[5]!=0 || data[6]!=64 || data[7]!=0 ||
        le32(data+16)!=2048 || le32(data+20)!=262144) return FG_TOKEN_HEADER;
    for (unsigned i=0;i<32;i++)
        if (data[32+i]!=expected_model_sha[i]) return FG_TOKEN_IDENTITY;
    count=le32(data+8);reserve=le32(data+12);extent=le32(data+24);
    /* Validate count before multiplication; also bounds worst-case scan work. */
    if (reserve<1 || reserve>256 || count<1 || count>2048-reserve)
        return FG_TOKEN_BOUNDS;
    if (extent!=count*4 || length!=(size_t)64+extent) return FG_TOKEN_EXTENT;
    if (crc32_bytes(data+64,extent)!=le32(data+28)) return FG_TOKEN_CRC;
    for (uint32_t i=0;i<count;i++)
        if (le32(data+64+4*i)>=262144) return FG_TOKEN_ID;
    view->payload=data+64;view->count=count;view->output_reserve=reserve;
    return FG_TOKEN_OK;
}
enum fg_token_status fg_prompt_token(const struct fg_prompt_view *view,
    uint32_t index, uint32_t *token) {
    if (!view || !token || !view->payload) return FG_TOKEN_ARGUMENT;
    if (view->count<1 || view->count>2047 || index>=view->count)
        return FG_TOKEN_BOUNDS;
    uint32_t value=le32(view->payload+4*index);
    if (value>=262144) return FG_TOKEN_ID;
    *token=value;
    return FG_TOKEN_OK;
}
