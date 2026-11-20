#pragma once
// Build-time shape profile. Larger models reuse the Q8 streaming matrix core;
// their weights, fixture, host manifest and memory sizing require a new package.
#ifndef SYS_QWEN_HIDDEN
#define SYS_QWEN_HIDDEN 1024
#endif
#ifndef SYS_QWEN_FFN
#define SYS_QWEN_FFN 3072
#endif
#ifndef SYS_QWEN_QUERY_HEADS
#define SYS_QWEN_QUERY_HEADS 16
#endif
#ifndef SYS_QWEN_KV_HEADS
#define SYS_QWEN_KV_HEADS 8
#endif
#ifndef SYS_QWEN_LAYERS
#define SYS_QWEN_LAYERS 28
#endif
#ifndef SYS_QWEN_VOCAB
#define SYS_QWEN_VOCAB 151936
#endif
#ifndef SYS_QWEN_CONTEXT
#define SYS_QWEN_CONTEXT 2048
#endif
static const unsigned H=SYS_QWEN_HIDDEN,F=SYS_QWEN_FFN;
static const unsigned HD=128,NH=SYS_QWEN_QUERY_HEADS,NK=SYS_QWEN_KV_HEADS;
static const unsigned Q=NH*HD,KV=NK*HD,NL=SYS_QWEN_LAYERS,VOCAB=SYS_QWEN_VOCAB,NC=SYS_QWEN_CONTEXT;
static const unsigned B=8,CHUNK_BITS=24,EMBED_BYTES=(H/32)*34;
static const unsigned XOFF=0,NOFF=H,QOFF=2*H,KOFF=QOFF+Q,VOFF=KOFF+KV;
static const unsigned COFF=VOFF+KV,POFF=COFF+Q,GOFF=POFF+H,UOFF=GOFF+F,ACT=UOFF+F;
static_assert(H%32==0 && F%32==0 && NH%NK==0,"Q8/GQA dimensions must be integral");
static_assert(H>=256 && Q>=256 && F>=256,"Eight-way matrix accumulation needs at least eight blocks");
static_assert(F>=H && F>=Q && F>=KV,"Matrix vector buffers must cover every projection");
