# V9J attention exactness probe

D3 and V9J matched bit for bit on all 75,776 output words from the existing attention fixture. A directed fixture produced only denormal-related differences. Every differing product used a subnormal operand or had a subnormal host result, and V9J returned the correctly signed zero for all of them.

| Fixture | Decode words | Decode differences | Batch-8 prefill words | Prefill differences |
|---|---:|---:|---:|---:|
| Existing attention probe | 10,240 | 0 | 65,536 | 0 |
| Directed subnormal inputs/results | 10,240 | 5,120 | 65,536 | 32,768 |

All 37,888 differing output words in the directed fixture changed from a D3 subnormal to V9J zero. Half had the same sign and half changed from negative subnormal to positive zero after accumulation. All outputs were finite. The comparison checked the complete ordered keys `(start, batch, token, index)` and the FP32 output bits. The probe exercised decode at starts 0, 23, 255, 256 and 257, and prefill at starts 0, 16, 248 and 252, including the 256-row tile boundary.

## Product-level counts

| Fixture | Product site | Executions | Different | Subnormal input only | Subnormal result only | Both | Unexpected |
|---|---|---:|---:|---:|---:|---:|---:|
| Existing | Query × key | 15,990,784 | 0 | 0 | 0 | 0 | 0 |
| Existing | Softmax mass × value | 10,379,264 | 0 | 0 | 0 | 0 | 0 |
| Directed | Query × key | 15,990,784 | 8,099,328 | 0 | 4,049,664 | 4,049,664 | 0 |
| Directed | Softmax mass × value | 10,379,264 | 5,189,632 | 0 | 0 | 5,189,632 | 0 |

The counts cover all executed calls, including padded score rows. At each site a diagnostic wrapper compared the native FP32 multiplication of the same operands (BF16 widened exactly by shifting left 16 bits) with `mul_xb`. A differing result was expected only when at least one operand or the native product was subnormal and the replacement product was zero with the sign of the native product. The wrapper returned the V9J product and left the surrounding attention arithmetic in place. Uninstrumented V9J builds produced identical output words for both fixtures. A separate scratch build with `XMUL_HLS_IEEE=1` and the policy assertion set to IEEE matched D3 on all 75,776 directed output words.

## Reproduction

Use [attention_probe.cpp](../attn_reclaim/audit/evidence/attention_probe.cpp) and [Run-AttentionProbe.ps1](../attn_reclaim/audit/evidence/Run-AttentionProbe.ps1) from the published attention audit at `24e1075abfb22bfd71db579f32bfe1ae63fda50c`. Compile the fixture once against each staged source directory. The run used the audit's Vitis 2025.2 Clang 16 and simulation libraries with `-O1 -ffp-contract=off`, so D3's host multiply preserves subnormals.

For the directed copy, keep the probe's positions, allocation and output loop. Replace the packed cache assignment with the following BF16 words indexed by `lane % 8`, repeated across every cache row. Replace the query assignment with `asfloat(query[index % 8])`.

```cpp
constexpr uint16_t keys[] = {0x3f00, 0x3f80, 0x0040, 0x8040, 0x3f00, 0xbf00, 0x3f80, 0xbf80};
constexpr uint16_t vals[] = {0x0040, 0x8040, 0x0001, 0x8001, 0x0080, 0x8080, 0x3f00, 0xbf00};
constexpr uint32_t query[] = {0x00800000, 0x00400000, 0x3f000000, 0x3f000000,
                              0x80800000, 0x00800000, 0x00000000, 0x80000000};
packed.range(lane * 16 + 15, lane * 16) = (kv ? vals : keys)[lane % 8];
```

Local artifacts are under `build/v2/v9j/probe/`. SHA-256 values below use UTF-8 CSV with LF terminators.

| Output | SHA-256 |
|---|---|
| Existing fixture, either decoder | `bb363bc5f3b0968f4455163e2ce613ca2b817d0603a5985c2d0ec450589be23f` |
| Directed fixture, D3 | `53b09d05b4bfc8322b1b93a871c47def0a0ce78fdedac7bd0dc2c49c4c16f6ce` |
| Directed fixture, V9J | `9d282dc3149567fb025b6b436f7cb99a9a79fb7aae5bb7ef97e70fca6f249211` |
