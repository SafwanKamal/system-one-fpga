#include "token_wire.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static unsigned nibble(char c) {
    if (c>='0' && c<='9') return (unsigned)(c-'0');
    if (c>='a' && c<='f') return (unsigned)(c-'a'+10);
    assert(0);return 0;
}
int main(int argc,char **argv) {
    uint8_t sha[32],storage[8322];char line[16650];
    struct fg_prompt_view view;
    for (unsigned i=0;i<32;i++) sha[i]=(uint8_t)i;
    assert(argc==2);FILE *stream=fopen(argv[1],"r");assert(stream);
    unsigned cases=0,valid=0,invalid=0,high=0;uint32_t last=99;
    while (fgets(line,sizeof(line),stream)) {
        size_t length=strcspn(line,"\r\n");assert(length>=2 && line[1]==' ');
        size_t bytes=(length-2)/2;assert((length-2)%2==0 && bytes<sizeof(storage)-1);
        uint8_t *packet=storage+1; /* Deliberately unaligned input. */
        for (size_t i=0;i<bytes;i++) packet[i]=(uint8_t)((nibble(line[2+2*i])<<4)|nibble(line[3+2*i]));
        view.payload=packet;view.count=123;view.output_reserve=456;
        enum fg_token_status status=fg_prompt_parse(packet,bytes,sha,&view);
        if (line[0]=='0') {
            assert(status==FG_TOKEN_OK);valid++;
            assert(bytes==64+4*(size_t)view.count);
            for (uint32_t i=0;i<view.count;i++) {
                uint32_t token=0;
                assert(fg_prompt_token(&view,i,&token)==FG_TOKEN_OK);
                assert(token<262144);if (token>=65536) high++;
            }
            assert(fg_prompt_token(&view,view.count,&last)==FG_TOKEN_BOUNDS && last==99);
        } else {
            assert(line[0]=='1' && status!=FG_TOKEN_OK);invalid++;
            assert(view.payload==NULL && view.count==0 && view.output_reserve==0);
        }
        cases++;
    }
    assert(fclose(stream)==0 && valid>=5 && invalid>=10 && high>=3);
    assert(fg_prompt_parse(NULL,0,sha,&view)==FG_TOKEN_ARGUMENT);
    assert(fg_prompt_parse(storage,0,NULL,&view)==FG_TOKEN_ARGUMENT);
    assert(fg_prompt_parse(storage,0,sha,NULL)==FG_TOKEN_ARGUMENT);
    assert(fg_prompt_token(NULL,0,&last)==FG_TOKEN_ARGUMENT && last==99);
    printf("PASS cases=%u valid=%u invalid=%u high_ids=%u unaligned_input=true\n",cases,valid,invalid,high);
    return 0;
}
