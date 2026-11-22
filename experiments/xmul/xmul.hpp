#pragma once

#include <cstdint>

namespace xmul {

// Denormal handling policy for fp32 * bf16 -> fp32.
// - IEEE: gradual underflow (subnormal inputs normalized, subnormal outputs
//   rounded to nearest-even), matching x86 C-sim IEEE-754 float arithmetic
//   bit-for-bit on all non-NaN and single-NaN inputs (0 * Inf returns canonical
//   quiet NaN 0x7fc00000u; two-NaN inputs propagate quieted a_bits).
// - FTZ:  flush-to-zero matching Xilinx Floating-Point Operator (PG060)
//   pre-rounding denormal handling (subnormal inputs treated as signed zero
//   and any product with pre-rounding normalized exponent <= 0 flushed to
//   signed zero), while still following this experiment's IEEE-754 NaN
//   payload propagation policy (quieted payload preserved rather than PG060's
//   canonical positive qNaN).
enum class DenormalPolicy : uint8_t {
    IEEE = 0,
    FTZ  = 1
};

namespace detail {

// Normalize a 23-bit non-zero subnormal fraction so bit 23 becomes 1.
// Returns the 24-bit normalized significand and writes the left-shift count
// (in [1, 23]) to shift_out.
inline uint32_t normalize_subnormal_f32(uint32_t frac, int32_t &shift_out) {
#ifdef __SYNTHESIS__
#pragma HLS INLINE
#endif
    uint32_t x = frac << 1;
    int32_t lz = 1;
    if ((x & 0x00ffff00u) == 0u) { x <<= 16; lz += 16; }
    if ((x & 0x00ff0000u) == 0u) { x <<= 8;  lz += 8;  }
    if ((x & 0x00f00000u) == 0u) { x <<= 4;  lz += 4;  }
    if ((x & 0x00c00000u) == 0u) { x <<= 2;  lz += 2;  }
    if ((x & 0x00800000u) == 0u) { x <<= 1;  lz += 1;  }
    shift_out = lz;
    return x;
}

// Normalize a 7-bit non-zero bf16 subnormal fraction so bit 7 becomes 1.
// Returns the 8-bit normalized significand and writes the left-shift count
// (in [1, 7]) to shift_out.
inline uint32_t normalize_subnormal_bf16(uint32_t frac, int32_t &shift_out) {
#ifdef __SYNTHESIS__
#pragma HLS INLINE
#endif
    uint32_t x = frac << 1;
    int32_t lz = 1;
    if ((x & 0xf0u) == 0u) { x <<= 4; lz += 4; }
    if ((x & 0xc0u) == 0u) { x <<= 2; lz += 2; }
    if ((x & 0x80u) == 0u) { x <<= 1; lz += 1; }
    shift_out = lz;
    return x;
}

template <DenormalPolicy Policy>
struct PolicyTag {};

inline bool is_input_zero(uint32_t exp, uint32_t /*frac*/, PolicyTag<DenormalPolicy::FTZ>) {
#ifdef __SYNTHESIS__
#pragma HLS INLINE
#endif
    return exp == 0u;
}

inline bool is_input_zero(uint32_t exp, uint32_t frac, PolicyTag<DenormalPolicy::IEEE>) {
#ifdef __SYNTHESIS__
#pragma HLS INLINE
#endif
    return (exp == 0u) && (frac == 0u);
}

inline uint32_t underflow_result(uint32_t sign_out, int32_t /*exp_norm*/,
                                 uint32_t /*sig24*/, uint32_t /*round_bit*/, bool /*sticky*/,
                                 PolicyTag<DenormalPolicy::FTZ>) {
#ifdef __SYNTHESIS__
#pragma HLS INLINE
#endif
    return sign_out << 31;
}

inline uint32_t underflow_result(uint32_t sign_out, int32_t exp_norm,
                                 uint32_t sig24, uint32_t round_bit, bool sticky,
                                 PolicyTag<DenormalPolicy::IEEE>) {
#ifdef __SYNTHESIS__
#pragma HLS INLINE
#endif
    // Gradual underflow: shift significand right by (1 - exp_norm) before RNE.
    const int32_t shift = 1 - exp_norm;
    if (shift >= 25) {
        return sign_out << 31;
    }
    const uint32_t u_shift    = static_cast<uint32_t>(shift);
    const uint32_t sub_sig    = sig24 >> u_shift;
    const uint32_t sub_round  = (sig24 >> (u_shift - 1u)) & 1u;
    const uint32_t low_mask   = (u_shift >= 2u) ? ((1u << (u_shift - 1u)) - 1u) : 0u;
    const bool     sub_sticky = ((sig24 & low_mask) != 0u) || (round_bit != 0u) || sticky;
    const uint32_t sub_lsb    = sub_sig & 1u;
    const uint32_t sub_inc    = (sub_round != 0u) && (sub_sticky || (sub_lsb != 0u)) ? 1u : 0u;
    const uint32_t sub_final  = sub_sig + sub_inc;
    // Note: if sub_sig == 0x7fffff and sub_inc == 1, sub_final == 0x800000,
    // which naturally encodes exp = 1, frac = 0 (smallest normal).
    return (sign_out << 31) | sub_final;
}

} // namespace detail

// Bit-exact integer-only reference for fp32 * bf16 -> fp32.
// bf16 is the upper 16 bits of an IEEE-754 binary32 float.
// Core datapath uses a 24x8-bit unsigned integer product (fitting one 27x18
// FPGA DSP slice), 1-bit normalization, round-to-nearest-even, and exponent add.
template <DenormalPolicy Policy>
inline uint32_t mul_f32_bf16(uint32_t a_bits, uint16_t b_bf16) {
#ifdef __SYNTHESIS__
#pragma HLS INLINE
#endif
    const detail::PolicyTag<Policy> policy_tag{};

    const uint32_t sign_a = a_bits >> 31;
    const uint32_t exp_a  = (a_bits >> 23) & 0xffu;
    const uint32_t frac_a = a_bits & 0x7fffffu;

    const uint32_t b_u32  = static_cast<uint32_t>(b_bf16);
    const uint32_t sign_b = b_u32 >> 15;
    const uint32_t exp_b  = (b_u32 >> 7) & 0xffu;
    const uint32_t frac_b = b_u32 & 0x7fu;

    const uint32_t sign_out = sign_a ^ sign_b;

    const bool a_is_nan = (exp_a == 0xffu) && (frac_a != 0u);
    const bool b_is_nan = (exp_b == 0xffu) && (frac_b != 0u);
    if (a_is_nan) {
        return a_bits | 0x00400000u;
    }
    if (b_is_nan) {
        return (b_u32 << 16) | 0x00400000u;
    }

    const bool a_is_inf = (exp_a == 0xffu);
    const bool b_is_inf = (exp_b == 0xffu);

    const bool a_is_zero = detail::is_input_zero(exp_a, frac_a, policy_tag);
    const bool b_is_zero = detail::is_input_zero(exp_b, frac_b, policy_tag);

    if (a_is_inf || b_is_inf) {
        if (a_is_zero || b_is_zero) {
            return 0x7fc00000u; // Canonical IEEE-754 quiet NaN for 0 * Inf.
        }
        return (sign_out << 31) | 0x7f800000u;
    }

    if (a_is_zero || b_is_zero) {
        return sign_out << 31;
    }

    // Build normalized significands (24-bit for fp32, 8-bit for bf16) and
    // signed biased exponents (bias = 127).
    uint32_t man_a = 0u;
    int32_t  ea    = 0;
    if (exp_a != 0u) {
        man_a = 0x00800000u | frac_a;
        ea    = static_cast<int32_t>(exp_a);
    } else {
        // Only reachable in IEEE mode (FTZ returned signed zero above).
        int32_t lz_a = 0;
        man_a = detail::normalize_subnormal_f32(frac_a, lz_a);
        ea    = 1 - lz_a;
    }

    uint32_t man_b = 0u;
    int32_t  eb    = 0;
    if (exp_b != 0u) {
        man_b = 0x80u | frac_b;
        eb    = static_cast<int32_t>(exp_b);
    } else {
        int32_t lz_b = 0;
        man_b = detail::normalize_subnormal_bf16(frac_b, lz_b);
        eb    = 1 - lz_b;
    }

    // 24 x 8 unsigned product: max value (2^24 - 1)*(2^8 - 1) < 2^32,
    // fitting cleanly in uint32_t and in a single 27x18 DSP multiplier.
    const uint32_t prod = man_a * man_b;
    const uint32_t norm = prod >> 31; // 1 if prod in [2.0, 4.0), 0 if in [1.0, 2.0).

    const int32_t exp_norm = ea + eb - 127 + static_cast<int32_t>(norm);

    const uint32_t sig24     = (norm != 0u) ? (prod >> 8) : (prod >> 7);
    const uint32_t round_bit = (norm != 0u) ? ((prod >> 7) & 1u) : ((prod >> 6) & 1u);
    const bool     sticky    = (norm != 0u) ? ((prod & 0x7fu) != 0u) : ((prod & 0x3fu) != 0u);

    if (exp_norm <= 0) {
        return detail::underflow_result(sign_out, exp_norm, sig24, round_bit, sticky, policy_tag);
    }

    // Normal rounding (round-to-nearest-even).
    const uint32_t lsb       = sig24 & 1u;
    const uint32_t round_inc = (round_bit != 0u) && (sticky || (lsb != 0u)) ? 1u : 0u;
    uint32_t       sig_round = sig24 + round_inc;
    int32_t        exp_final = exp_norm;

    if (sig_round >= 0x01000000u) {
        sig_round >>= 1;
        exp_final += 1;
    }

    if (exp_final >= 255) {
        return (sign_out << 31) | 0x7f800000u;
    }

    return (sign_out << 31) | (static_cast<uint32_t>(exp_final) << 23) | (sig_round & 0x7fffffu);
}

inline uint32_t mul_f32_bf16(uint32_t a_bits, uint16_t b_bf16) {
#ifdef __SYNTHESIS__
#pragma HLS INLINE
#endif
    return mul_f32_bf16<DenormalPolicy::IEEE>(a_bits, b_bf16);
}

inline uint32_t mul_f32_bf16(uint32_t a_bits, uint16_t b_bf16, DenormalPolicy policy) {
#ifdef __SYNTHESIS__
#pragma HLS INLINE
#endif
    return (policy == DenormalPolicy::FTZ)
               ? mul_f32_bf16<DenormalPolicy::FTZ>(a_bits, b_bf16)
               : mul_f32_bf16<DenormalPolicy::IEEE>(a_bits, b_bf16);
}

} // namespace xmul

using xmul::DenormalPolicy;
using xmul::mul_f32_bf16;
