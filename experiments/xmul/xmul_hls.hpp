#pragma once

#include <cstdint>
#include <cstring>

#ifdef __SYNTHESIS__
#include <ap_int.h>
#endif

// Compile-time denormal policy for mul_xb(float, uint16_t):
//   XMUL_HLS_IEEE == 0 (default): FTZ (matches Xilinx fmul hardware on v9h)
//   XMUL_HLS_IEEE != 0          : IEEE gradual underflow (matches x86 C-sim)
#ifndef XMUL_HLS_IEEE
#define XMUL_HLS_IEEE 0
#endif

namespace xmul_hls {

enum class DenormalPolicy : uint8_t {
    IEEE = 0,
    FTZ  = 1
};

constexpr DenormalPolicy kDefaultPolicy =
    (XMUL_HLS_IEEE != 0) ? DenormalPolicy::IEEE : DenormalPolicy::FTZ;

namespace detail {

inline uint32_t f32_to_bits(float x) {
#ifdef __SYNTHESIS__
#pragma HLS INLINE
#endif
    uint32_t bits = 0u;
    std::memcpy(&bits, &x, sizeof(bits));
    return bits;
}

inline float bits_to_f32(uint32_t bits) {
#ifdef __SYNTHESIS__
#pragma HLS INLINE
#endif
    float x = 0.0f;
    std::memcpy(&x, &bits, sizeof(x));
    return x;
}

inline uint32_t mul_24x8(uint32_t man_a, uint32_t man_b) {
#ifdef __SYNTHESIS__
#pragma HLS INLINE
    ap_uint<24> ma = ap_uint<24>(man_a);
    ap_uint<8>  mb = ap_uint<8>(man_b);
    ap_uint<32> prod_ap = ma * mb;
#pragma HLS BIND_OP variable=prod_ap op=mul impl=dsp
    return prod_ap.to_uint();
#else
    return man_a * man_b;
#endif
}

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

inline void extract_norm_f32(uint32_t exp_a, uint32_t frac_a,
                             uint32_t &man_a, int32_t &ea,
                             PolicyTag<DenormalPolicy::FTZ>) {
#ifdef __SYNTHESIS__
#pragma HLS INLINE
#endif
    man_a = 0x00800000u | frac_a;
    ea    = static_cast<int32_t>(exp_a);
}

inline void extract_norm_f32(uint32_t exp_a, uint32_t frac_a,
                             uint32_t &man_a, int32_t &ea,
                             PolicyTag<DenormalPolicy::IEEE>) {
#ifdef __SYNTHESIS__
#pragma HLS INLINE
#endif
    if (exp_a != 0u) {
        man_a = 0x00800000u | frac_a;
        ea    = static_cast<int32_t>(exp_a);
    } else {
        int32_t lz_a = 0;
        man_a = normalize_subnormal_f32(frac_a, lz_a);
        ea    = 1 - lz_a;
    }
}

inline void extract_norm_bf16(uint32_t exp_b, uint32_t frac_b,
                              uint32_t &man_b, int32_t &eb,
                              PolicyTag<DenormalPolicy::FTZ>) {
#ifdef __SYNTHESIS__
#pragma HLS INLINE
#endif
    man_b = 0x80u | frac_b;
    eb    = static_cast<int32_t>(exp_b);
}

inline void extract_norm_bf16(uint32_t exp_b, uint32_t frac_b,
                              uint32_t &man_b, int32_t &eb,
                              PolicyTag<DenormalPolicy::IEEE>) {
#ifdef __SYNTHESIS__
#pragma HLS INLINE
#endif
    if (exp_b != 0u) {
        man_b = 0x80u | frac_b;
        eb    = static_cast<int32_t>(exp_b);
    } else {
        int32_t lz_b = 0;
        man_b = normalize_subnormal_bf16(frac_b, lz_b);
        eb    = 1 - lz_b;
    }
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
    return (sign_out << 31) | sub_final;
}

} // namespace detail

template <DenormalPolicy Policy>
inline uint32_t mul_xb_bits(uint32_t a_bits, uint16_t b_bf16) {
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
            return 0x7fc00000u;
        }
        return (sign_out << 31) | 0x7f800000u;
    }

    if (a_is_zero || b_is_zero) {
        return sign_out << 31;
    }

    uint32_t man_a = 0u;
    int32_t  ea    = 0;
    detail::extract_norm_f32(exp_a, frac_a, man_a, ea, policy_tag);

    uint32_t man_b = 0u;
    int32_t  eb    = 0;
    detail::extract_norm_bf16(exp_b, frac_b, man_b, eb, policy_tag);

    const uint32_t prod = detail::mul_24x8(man_a, man_b);
    const uint32_t norm = prod >> 31;

    const int32_t exp_norm = ea + eb - 127 + static_cast<int32_t>(norm);

    const uint32_t sig24     = (norm != 0u) ? (prod >> 8) : (prod >> 7);
    const uint32_t round_bit = (norm != 0u) ? ((prod >> 7) & 1u) : ((prod >> 6) & 1u);
    const bool     sticky    = (norm != 0u) ? ((prod & 0x7fu) != 0u) : ((prod & 0x3fu) != 0u);

    if (exp_norm <= 0) {
        return detail::underflow_result(sign_out, exp_norm, sig24, round_bit, sticky, policy_tag);
    }

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

template <DenormalPolicy Policy>
inline float mul_xb(float a, uint16_t b_bf16) {
#ifdef __SYNTHESIS__
#pragma HLS INLINE
#endif
    return detail::bits_to_f32(mul_xb_bits<Policy>(detail::f32_to_bits(a), b_bf16));
}

// Default drop-in: selects FTZ (default) or IEEE via XMUL_HLS_IEEE.
inline float mul_xb(float a, uint16_t b_bf16) {
#ifdef __SYNTHESIS__
#pragma HLS INLINE
#endif
    return mul_xb<kDefaultPolicy>(a, b_bf16);
}

} // namespace xmul_hls

using xmul_hls::mul_xb;
