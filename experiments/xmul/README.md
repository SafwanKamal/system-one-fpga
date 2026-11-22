# `xmul` — Integer-Only `fp32 × bf16 → fp32` Reference

Bit-exact integer-only C++14 reference ([`xmul.hpp`](xmul.hpp)) for the attention multiplications in the Qwen decoder (`q * k` scoring and `mass * v` value accumulation in [`hls/qwen_decoder_v9e/qwen_decoder.cpp`](../../hls/qwen_decoder_v9e/qwen_decoder.cpp)), where the FP32 query or softmax mass is multiplied by a BF16 key or value (`bf16` = upper 16 bits of an IEEE-754 `binary32` float).

## Interface & Denormal Policies

```cpp
enum class DenormalPolicy : uint8_t { IEEE = 0, FTZ = 1 };

template <DenormalPolicy Policy>
inline uint32_t mul_f32_bf16(uint32_t a_bits, uint16_t b_bf16);

inline uint32_t mul_f32_bf16(uint32_t a_bits, uint16_t b_bf16);

inline uint32_t mul_f32_bf16(uint32_t a_bits, uint16_t b_bf16, DenormalPolicy policy);
```

- **`DenormalPolicy::IEEE`** (default via `mul_f32_bf16(uint32_t, uint16_t)`): Gradual underflow per IEEE-754 `binary32` RNE. Subnormal inputs are normalized prior to multiplication, and underflowing products (`exp_norm <= 0`) are right-shifted by `1 - exp_norm` (`1..24`) and rounded to nearest-even (including carry-out to `0x00800000`, `2^-126`). Matches x86 native `float` C-sim bit-for-bit on all non-NaN results (finite, subnormal, signed zero, signed `Inf`) and single-NaN payload propagation (`a_nan != b_nan`); for `0 * Inf` (`0x7fc00000u` canonical qNaN vs x86 `0xffc00000u` qNaN indefinite) and two-NaN operands (where IEEE-754 leaves invalid-op sign/payload and operand selection implementation-defined), preserves IEEE-754 quiet-NaN semantics.
- **`DenormalPolicy::FTZ`**: Flush-to-zero matching Xilinx Floating-Point Operator (PG060) **pre-rounding denormal handling** only: subnormal inputs (`exp == 0 && frac != 0`) are treated as signed zero on entry (`subnormal * Inf -> qNaN`), and any product whose pre-rounding normalized exponent satisfies `exp_norm <= 0` is flushed to signed zero (`sign_out << 31`). NaN handling in `FTZ` intentionally retains this experiment's IEEE-754 NaN payload policy rather than PG060's canonical positive qNaN output (e.g., `0xffc00001 * 0x3f80` returns `0xffc00001`).
- **Inf / NaN**: Per IEEE-754 in both `IEEE` and `FTZ` modes. Single NaN inputs quiet and propagate that operand's payload (`| 0x00400000u`), and two-NaN inputs propagate quieted `a_bits`; `0 * Inf` (and `subnormal * Inf` in `FTZ`) returns canonical positive quiet NaN `0x7fc00000u` (verifying quiet-NaN class against x86 `0xffc00000u`); non-zero finite × Inf returns signed Inf; overflow (`exp_final >= 255`) rounds to signed Inf.

## Integer Datapath Widths

All arithmetic in `mul_f32_bf16` uses portable C++14 integer operations (`uint32_t`, `uint16_t`, `int32_t`, no floating-point types or intrinsics):

| Stage | Width | Details |
|---|---|---|
| Unpack `a_bits` (`fp32`) | 1 + 8 + 23 bits | `sign_a`, `exp_a`, `frac_a` |
| Unpack `b_bf16` (`bf16`) | 1 + 8 + 7 bits | `sign_b`, `exp_b`, `frac_b` |
| Sign XOR | 1 bit | `sign_out = sign_a ^ sign_b` |
| Subnormal input norm (`IEEE` only) | 24-bit / 8-bit | 5-stage (`16/8/4/2/1`) mux tree on `frac_a` (`lz_a ∈ [1,23]`); 3-stage (`4/2/1`) on `frac_b` (`lz_b ∈ [1,7]`) |
| Significand multiply | **24 × 8 → 32 bits** | `man_a ∈ [2^23, 2^24-1]`, `man_b ∈ [2^7, 2^8-1]`, `prod < 2^32` (fits in **one 27×18 DSP48E2**) |
| 1-bit product norm & GRS | 24 + 1 + 1 bits | `norm = prod[31]`; `sig24 = prod[31:8]` or `prod[30:7]`; `round_bit` (`prod[7]`/`[6]`); `sticky` (7-bit / 6-bit OR) |
| Exponent add | 10-bit signed | `exp_norm = ea + eb - 127 + norm` (`[-125, 382]` in `FTZ`; `[-155, 382]` in `IEEE`) |
| Normal RNE & carry-out | 24 + 1 bits | `sig_round = sig24 + round_inc` (25-bit sum); if `>= 2^24`, shift right 1 and `exp_final = exp_norm + 1` |
| Subnormal RNE (`IEEE` only) | 24-bit shifter | `shift = 1 - exp_norm ∈ [1, 24]`; 24-bit right-shift + low-bit sticky mask + 24-bit `+1` RNE (`shift >= 25 → ±0.0`) |

## Analytic LUT / DSP Estimate vs Xilinx `fmul` `max_dsp`

Comparison per multiplier instance targeting UltraScale+ (KR260 `xck26`, analytical estimates for `xmul`; no Vivado synthesis run performed in this sandbox):

| Implementation | DSP48E2 / inst | LUT / inst | Notes |
|---|---:|---:|---|
| Xilinx `fmul` `max_dsp` (`fp32 × fp32`) | **3** | **~139** | Reference baseline from Vivado FP operator |
| `xmul` (`DenormalPolicy::FTZ`, estimated) | **1** | **~55–85** (est.) | Single 24×8 DSP; ~15–20 LUT classify/mux, ~15–20 LUT 1-bit norm + sticky/RNE, ~12–18 LUT 10-bit exp add/range, ~12–24 LUT 24-bit `+1` carry |
| `xmul` (`DenormalPolicy::IEEE`, estimated) | **1** | **~160–220** (est.) | Adds ~45–60 LUT (`fp32` subnormal CLZ/lshift), ~12–18 LUT (`bf16` subnormal lshift), ~50–65 LUT (24-bit output rshift/sticky) |

In [`hls/qwen_decoder_v9e/qwen_decoder.cpp`](../../hls/qwen_decoder_v9e/qwen_decoder.cpp), `attention()` executes 32 `fp32 * bf16` products per cycle in the `q * k` scoring loop (`P=2, g=2, lane=8`) and 32 per cycle in the `mass * v` accumulation loop (64 total unshared instances, or 32 if shared across the two sequential loops). Replacing 3-DSP `fmul` with a 1-DSP `FTZ` multiplier saves **2 DSPs per instance** (**64 DSPs** for 32 shared, **128 DSPs** for 64 unshared) and roughly **~40–60% LUT** per multiplier instance (**~1.7k–2.7k LUT** across 32, **~3.5k–5.4k LUT** across 64).

## When `FTZ` vs `IEEE` Can Differ in Attention

1. **Subnormal `mass` from softmax (`mass * v`)**: In online softmax (`hls::expf(score - maximum)`), tokens whose exact `exp(score - maximum)` lies in `[2^-149, 2^-126)` (exact-magnitude input range `[-103.28, -87.34)`, i.e., `[ln(2^-149), ln(2^-126))`; accounting for `fp32` RNE rounding, `expf` emits subnormals down to the midpoint `ln(2^-150) ≈ -103.972`, e.g., Windows UCRT `expf(-103.5f)` returns `0x00000001`) have subnormal `mass ∈ [2^-149, 2^-126)`. `IEEE` keeps the subnormal `mass` (and can even yield a normal product if `|v| > 1`), whereas `FTZ` flushes `mass * v` to `±0.0f`. Note that `hls::expf` in Xilinx HLS already flushes subnormal outputs to zero, whereas host x86 `expf` emits subnormals.
2. **Normal inputs whose product underflows (`exp_norm <= 0`)**: For example, a small normal `mass` (`2^-120`) times a small normal `v` (`2^-10`) gives `2^-130`. `IEEE` preserves gradual underflow down to `2^-149`, while `FTZ` flushes to `±0.0f`. At the boundary `exp_norm == 0` with `sig24 == 0xffffff` (e.g., `0x1faaaaaa * 0x2040`, where `prod = 0x7fffff80`, `norm = 0`, pre-shift normal guard `round_bit = 0`, `sticky = 0`), gradual underflow right-shifts by `shift = 1 - exp_norm = 1` to retained subnormal significand `sub_sig = 0x7fffff` (odd, `sub_lsb = 1`) and post-shift subnormal guard `sub_round = 1`, `sub_sticky = 0`; `IEEE` RNE rounds this odd tie up to `2^-126` (`0x00800000`), whereas PG060-style pre-rounding `FTZ` sees `exp_norm <= 0` (`|exact_prod| < 2^-126`) and flushes to `±0.0f` (verified explicitly in [`test_xmul.cpp`](test_xmul.cpp)).
3. **Subnormal `K`/`V` cache or `Q` inputs**: Any subnormal `K`/`V` (`|x| < 2^-126`) or `Q` flushes to `±0.0f` under `FTZ` (and `subnormal * ±Inf` produces `qNaN` under `FTZ` vs `±Inf` under `IEEE`).
4. **Practical numerical effect**: Because softmax normalizes weights so the maximum-score key has `mass == 1.0`, the final `acc` magnitude is typically `O(10^-2 .. 10^1)`, so individual subnormal `mass * v` terms (`< 10^-38`) fall ~30 orders of magnitude below the FP32 accumulator ULP. Explicit `FTZ` modeling primarily matters for **bit-exact C-sim vs RTL parity** when hunting 1-ULP or INT8-quantization-boundary divergences across long sequences (cf. [`docs/research/2026-10-21-v9a-hardware-candidate.md`](../../docs/research/2026-10-21-v9a-hardware-candidate.md)).

## Verification

[`test_xmul.cpp`](test_xmul.cpp) compiles as portable C++14 (`cl /nologo /EHsc /std:c++14 /O2 /W4 /WX`) and tests **all 65,536 `bf16` values × 7,656 stratified `fp32` values** (**501,743,616 total pairs** covering all 256 exponents, both signs, subnormals, mantissa edge patterns, normal/subnormal exact ties, rounding carries, overflow, `±Inf`, `qNaN`, and `sNaN`):

- **IEEE mode vs native x86 `float`**: `0` mismatches across all `501,743,616` pairs (bit-exact across all non-NaN and single-NaN pairs; quiet-NaN class verified for `0 * Inf` and two-NaN pairs; `24,406,096` subnormal outputs, `34,654,290` normal exact ties, `410,754` subnormal exact ties, and `2,989,144` NaN checks).
- **FTZ mode vs independent native-`float` + exact-`double` tininess oracle**: `0` mismatches across all `501,743,616` pairs (flushes subnormal inputs to signed zero, multiplies with native x86 `float`, enforces exact pre-rounding tininess `|a_ftz * b_ftz| < 2^-126` via exact 53-bit `binary64` product for PG060 FTZ semantics, and applies the same NaN contract; `6,253,236` flushed subnormal inputs, `81,746,014` flushed normal-input underflows, `2,989,784` NaN checks), plus explicit API function-pointer compile/call checks (`uint32_t (*)(uint32_t, uint16_t)` and `uint32_t (*)(uint32_t, uint16_t, DenormalPolicy)`), NaN payload preservation (`0xffc00001 * 0x3f80 -> 0xffc00001`), and boundary verification of `exp_norm == 0` round-to-normal (`0x00800000` in IEEE vs `0x00000000` in FTZ).

## HLS Drop-In (`xmul_hls.hpp`) & D3 Attention Integration

[`xmul_hls.hpp`](xmul_hls.hpp) wraps the integer-only `24 × 8` multiplier into a Vitis-HLS-synthesizable drop-in function:

```cpp
float mul_xb(float a, uint16_t b_bf16);
```

- Bit-casts `a` (`float` ↔ `uint32_t` via `std::memcpy`), performs integer-only arithmetic with one `24 × 8` unsigned significand product (`ap_uint<24> * ap_uint<8>` bound to one DSP48E2 via `#pragma HLS BIND_OP variable=prod_ap op=mul impl=dsp` under `__SYNTHESIS__`), 1-bit normalization, and RNE rounding.
- Defaults to `DenormalPolicy::FTZ` (`#define XMUL_HLS_IEEE 0`) so subnormal normalization and subnormal output shift logic are eliminated at compile time; compile with `-DXMUL_HLS_IEEE=1` (or call `xmul_hls::mul_xb<xmul_hls::DenormalPolicy::IEEE>(a, b)`) for IEEE gradual underflow.

### Where `build/v2/dual-port-study/src-d3/qwen_decoder.cpp` calls `fp32 * bf16`

In `attention()` of `build/v2/dual-port-study/src-d3/qwen_decoder.cpp`, `bf16_lane(word w, unsigned chunk, unsigned lane)` (lines 287–291) widens one 16-bit BF16 lane via `from_bf16(half.range(lane*16+15,lane*16))`. There are two `fp32 * bf16` multiplication sites (both unrolled over `p < P` with `P=4`, `g < 2`, `lane < 8`, i.e., 64 multipliers each):

1. **Score (`q * k`) loop** (lines 397–400):
   ```cpp
   q8[lane]=lanef(qw,lane)*bf16_lane(key,chunk,lane);
   ```
2. **Value (`mass * v`) loop** (lines 455–458):
   ```cpp
   w.range(lane*32+31,lane*32)=asbits(lanef(old,lane)+m*bf16_lane(value,c,lane));
   ```

### How to substitute `mul_xb`

1. Include `"xmul_hls.hpp"` in `qwen_decoder.cpp` (default `XMUL_HLS_IEEE=0` selects `FTZ`).
2. Add a raw 16-bit lane extractor alongside `bf16_lane`:
   ```cpp
   static uint16_t bf16_lane_bits(word w,unsigned chunk,unsigned lane) {
   #pragma HLS INLINE
       ap_uint<128> half=(chunk&1)?ap_uint<128>(w.range(255,128)):ap_uint<128>(w.range(127,0));
       return static_cast<uint16_t>(half.range(lane*16+15,lane*16).to_uint());
   }
   ```
3. Substitute the two multiply expressions:
   - Score (`q * k`) loop:
     ```cpp
     q8[lane]=mul_xb(lanef(qw,lane),bf16_lane_bits(key,chunk,lane));
     ```
   - Value (`mass * v`) loop:
     ```cpp
     w.range(lane*32+31,lane*32)=asbits(lanef(old,lane)+mul_xb(m,bf16_lane_bits(value,c,lane)));
     ```

### Exactness argument vs `v9h`

- **In C-sim (`x86`), identical except denormal products (`IEEE` vs `FTZ`)**: On `x86` C-sim, native `float` multiplies use IEEE-754 gradual underflow with RNE. With `-DXMUL_HLS_IEEE=1`, `mul_xb` is bit-identical to `xmul.hpp` (and therefore to `x86` `float` C-sim on all non-NaN and single-NaN pairs). In its default `FTZ` mode, `mul_xb` differs from `x86` C-sim **only** when an input is subnormal or a product underflows pre-rounding (`exp_norm <= 0`), flushing those denormal inputs/products to signed zero `±0.0f`.
- **On hardware (`v9h`), identical in `FTZ` mode**: On the KR260 FPGA, Xilinx's `fmul` IP (`v9h` hardware) implements pre-rounding flush-to-zero for subnormal inputs and underflowing products (`exp_norm <= 0`) with RNE rounding on normal products. Because `mul_xb` in `FTZ` mode executes that exact pre-rounding FTZ + RNE specification in integer arithmetic, `v9j` with `mul_xb` (`FTZ`) is bit-identical to `v9h` hardware across all finite, zero, overflow, and Inf results.

### Native Verification (`test_xmul_hls.cpp`)

[`test_xmul_hls.cpp`](test_xmul_hls.cpp) verifies `xmul_hls::mul_xb` against `xmul::mul_f32_bf16` in **both** `FTZ` and `IEEE` policies over the same `501,743,616`-pair stratified set (`7,656 fp32 × 65,536 bf16`), plus a compile-time default policy check (`XMUL_HLS_IEEE=0` vs `1`) via `float (*)(float, uint16_t)`.
