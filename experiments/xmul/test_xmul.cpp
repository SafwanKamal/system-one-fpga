#include "xmul.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>
#include <vector>

namespace {

inline float bits_to_f32(uint32_t u) {
    float f = 0.0f;
    std::memcpy(&f, &u, sizeof(f));
    return f;
}

inline uint32_t native_mul_f32_bf16(uint32_t a_bits, uint16_t b_bf16) {
    uint32_t b_bits = static_cast<uint32_t>(b_bf16) << 16;
    float a = bits_to_f32(a_bits);
    float b = bits_to_f32(b_bits);
    // Prevent constant-folding or FMA contraction across callers.
    volatile float va = a;
    volatile float vb = b;
    float r = va * vb;
    uint32_t r_bits = 0;
    std::memcpy(&r_bits, &r, sizeof(r_bits));
    return r_bits;
}

inline bool is_nan_f32(uint32_t u) {
    return ((u & 0x7f800000u) == 0x7f800000u) && ((u & 0x007fffffu) != 0u);
}

inline bool is_qnan_f32(uint32_t u) {
    return ((u & 0x7fc00000u) == 0x7fc00000u) && ((u & 0x007fffffu) != 0u);
}

inline bool is_nan_bf16(uint16_t b) {
    return ((b & 0x7f80u) == 0x7f80u) && ((b & 0x007fu) != 0u);
}

inline bool is_subnormal_f32(uint32_t u) {
    return ((u & 0x7f800000u) == 0u) && ((u & 0x007fffffu) != 0u);
}

inline bool is_subnormal_bf16(uint16_t b) {
    return ((b & 0x7f80u) == 0u) && ((b & 0x007fu) != 0u);
}

inline uint32_t make_f32(uint32_t sign, uint32_t exp, uint32_t frac) {
    return ((sign & 1u) << 31) | ((exp & 0xffu) << 23) | (frac & 0x7fffffu);
}

std::vector<uint32_t> build_stratified_fp32() {
    std::vector<uint32_t> vals;
    vals.reserve(6000);

    // 1. exp = 0: signed zeros + all 23 single-bit subnormals + edge patterns
    for (uint32_t s = 0; s < 2; ++s) {
        vals.push_back(make_f32(s, 0u, 0u));
        for (uint32_t k = 0; k < 23; ++k) {
            vals.push_back(make_f32(s, 0u, 1u << k));
        }
        const uint32_t sub_edges[] = {
            0x000003u, 0x00007fu, 0x000081u, 0x000101u,
            0x3fffffu, 0x400001u, 0x7ffffeu, 0x7fffffu,
            0x555555u, 0x2aaaaau
        };
        for (uint32_t f : sub_edges) {
            vals.push_back(make_f32(s, 0u, f));
        }
    }

    // 2. All 254 normal exponents (1..254) x both signs x core mantissa patterns
    const uint32_t core_fracs[] = {
        0x000000u, 0x000001u, 0x000040u, 0x000080u,
        0x0000c0u, 0x000100u, 0x400000u, 0x7ffffeu,
        0x7fffffu, 0x555555u, 0x2aaaaau
    };
    for (uint32_t exp = 1; exp <= 254; ++exp) {
        for (uint32_t s = 0; s < 2; ++s) {
            for (uint32_t f : core_fracs) {
                vals.push_back(make_f32(s, exp, f));
            }
        }
    }

    // 3. Boundary exponents for underflow (1..27), unit range (126..128), overflow (250..254):
    //    dense low-bit and high-bit mantissas to catch exact ties and rounding carries.
    std::vector<uint32_t> boundary_exps;
    for (uint32_t e = 1; e <= 27; ++e) boundary_exps.push_back(e);
    for (uint32_t e = 126; e <= 128; ++e) boundary_exps.push_back(e);
    for (uint32_t e = 250; e <= 254; ++e) boundary_exps.push_back(e);

    const uint32_t dense_fracs[] = {
        0x000002u, 0x000003u, 0x000020u, 0x000060u, 0x0000a0u, 0x0000e0u,
        0x000140u, 0x000180u, 0x0001c0u, 0x000200u, 0x000400u, 0x001000u,
        0x7fff40u, 0x7fff80u, 0x7fffc0u, 0x7fffd0u, 0x7fffe0u, 0x7ffff0u,
        0x7ffff8u, 0x7ffffcu, 0x7ffffdu
    };
    for (uint32_t exp : boundary_exps) {
        for (uint32_t s = 0; s < 2; ++s) {
            for (uint32_t f : dense_fracs) {
                vals.push_back(make_f32(s, exp, f));
            }
        }
    }

    // 4. exp = 255: +-Inf, quiet NaNs, signaling NaNs
    const uint32_t special_fracs[] = {
        0x000000u, // Inf
        0x400000u, 0x400001u, 0x555555u, 0x7fffffu, // qNaN
        0x000001u, 0x000080u, 0x2aaaaau, 0x3fffffu  // sNaN
    };
    for (uint32_t s = 0; s < 2; ++s) {
        for (uint32_t f : special_fracs) {
            vals.push_back(make_f32(s, 255u, f));
        }
    }

    // 5. Deterministic PRNG spread across all bit patterns
    uint32_t rng = 0x13579bdfu;
    for (int i = 0; i < 512; ++i) {
        rng ^= rng << 13;
        rng ^= rng >> 17;
        rng ^= rng << 5;
        vals.push_back(rng);
    }

    std::sort(vals.begin(), vals.end());
    vals.erase(std::unique(vals.begin(), vals.end()), vals.end());
    return vals;
}

} // namespace

int main() {
    // Verify host x86 native float environment runs in IEEE-754 gradual underflow RNE mode
    // and double has 53-bit significand + exponent range for exact 24x8 product tininess.
    if (native_mul_f32_bf16(0x00000001u, 0x3f80u) != 0x00000001u ||
        native_mul_f32_bf16(0x00800000u, 0x3f00u) != 0x00400000u ||
        std::numeric_limits<double>::radix != 2 ||
        std::numeric_limits<double>::digits < 32 ||
        std::numeric_limits<double>::min_exponent > -252 ||
        std::numeric_limits<double>::max_exponent < 256) {
        std::printf("FAIL: host float/double environment does not meet IEEE assumptions\n");
        return 1;
    }
    const double min_norm_f64 = static_cast<double>(bits_to_f32(0x00800000u));
    if (min_norm_f64 != std::ldexp(1.0, -126)) {
        std::printf("FAIL: unexpected 2^-126 double constant\n");
        return 1;
    }

    const std::vector<uint32_t> fp32_set = build_stratified_fp32();
    const uint64_t total_pairs = static_cast<uint64_t>(fp32_set.size()) * 65536ull;

    // --- Test 0: API signature & function-pointer compile check + NaN payload policy ---
    using Mul = uint32_t (*)(uint32_t, uint16_t);
    using MulWithPolicy = uint32_t (*)(uint32_t, uint16_t, DenormalPolicy);
    Mul callback = &mul_f32_bf16;
    Mul ns_callback = &xmul::mul_f32_bf16;
    MulWithPolicy policy_callback = &mul_f32_bf16;
    if (callback(0x1faaaaaau, 0x2040u) != 0x00800000u ||
        ns_callback(0x1faaaaaau, 0x2040u) != 0x00800000u ||
        policy_callback(0x1faaaaaau, 0x2040u, DenormalPolicy::FTZ) != 0x00000000u ||
        policy_callback(0xffc00001u, 0x3f80u, DenormalPolicy::FTZ) != 0xffc00001u ||
        callback(0xffc00001u, 0x3f80u) != 0xffc00001u) {
        std::printf("FAIL API/NaN-payload check\n");
        return 1;
    }

    // --- Test 1: IEEE mode over all 65,536 bf16 x stratified fp32 ---
    uint64_t ieee_mismatches = 0;
    uint64_t ieee_nan_checks = 0;
    uint64_t ieee_subnormal_out = 0;
    uint64_t ieee_tie_normal = 0;
    uint64_t ieee_tie_subnormal = 0;

    for (size_t i = 0; i < fp32_set.size(); ++i) {
        const uint32_t a = fp32_set[i];
        const bool a_nan = is_nan_f32(a);
        for (uint32_t b_idx = 0; b_idx < 65536u; ++b_idx) {
            const uint16_t b = static_cast<uint16_t>(b_idx);
            const uint32_t got = mul_f32_bf16(a, b);
            const uint32_t ref = native_mul_f32_bf16(a, b);

            if (is_nan_f32(ref)) {
                ++ieee_nan_checks;
                // Output must be a quiet NaN; when only one input is NaN,
                // sign and quieted payload must match x86 native float bit-for-bit.
                const bool b_nan = is_nan_bf16(b);
                bool ok = is_qnan_f32(got);
                if (ok && (a_nan != b_nan)) {
                    ok = (got == ref);
                }
                if (!ok) {
                    if (ieee_mismatches < 10) {
                        std::printf("IEEE NaN MISMATCH a=%08x b=%04x got=%08x ref=%08x\n",
                                    a, b, got, ref);
                    }
                    ++ieee_mismatches;
                }
            } else {
                if (got != ref) {
                    if (ieee_mismatches < 10) {
                        std::printf("IEEE MISMATCH a=%08x b=%04x got=%08x ref=%08x\n",
                                    a, b, got, ref);
                    }
                    ++ieee_mismatches;
                }
                if (is_subnormal_f32(got)) {
                    ++ieee_subnormal_out;
                }
            }

            // Count exact ties exercised (for diagnostic confidence).
            const uint32_t exp_a = (a >> 23) & 0xffu;
            const uint32_t exp_b = (static_cast<uint32_t>(b) >> 7) & 0xffu;
            if (exp_a >= 1u && exp_a <= 254u && exp_b >= 1u && exp_b <= 254u) {
                const uint32_t man_a = 0x800000u | (a & 0x7fffffu);
                const uint32_t man_b = 0x80u | (static_cast<uint32_t>(b) & 0x7fu);
                const uint32_t prod = man_a * man_b;
                const uint32_t norm = prod >> 31;
                const int32_t exp_norm = static_cast<int32_t>(exp_a) + static_cast<int32_t>(exp_b) - 127 + static_cast<int32_t>(norm);
                if (exp_norm >= 1 && exp_norm <= 254) {
                    if ((norm && (prod & 0xffu) == 0x80u) || (!norm && (prod & 0x7fu) == 0x40u)) {
                        ++ieee_tie_normal;
                    }
                } else if (exp_norm <= 0 && exp_norm >= -23) {
                    const uint32_t shift = static_cast<uint32_t>(1 - exp_norm);
                    const uint32_t sig24 = norm ? (prod >> 8) : (prod >> 7);
                    const uint32_t rb = norm ? ((prod >> 7) & 1u) : ((prod >> 6) & 1u);
                    const bool st = norm ? ((prod & 0x7fu) != 0u) : ((prod & 0x3fu) != 0u);
                    const uint32_t sub_round = (sig24 >> (shift - 1u)) & 1u;
                    const uint32_t low_mask = (shift >= 2u) ? ((1u << (shift - 1u)) - 1u) : 0u;
                    const bool sub_sticky = ((sig24 & low_mask) != 0u) || (rb != 0u) || st;
                    if (sub_round && !sub_sticky) {
                        ++ieee_tie_subnormal;
                    }
                }
            }
        }
    }

    // --- Test 2: FTZ mode over all 65,536 bf16 x stratified fp32 ---
    // Independent PG060-style FTZ oracle:
    // 1. Flush subnormal inputs to signed zero.
    // 2. Multiply flushed operands using native x86 float arithmetic.
    // 3. For finite non-zero flushed operands, check pre-rounding tininess
    //    (|a_ftz * b_ftz| < 2^-126) via exact 53-bit binary64 double product
    //    (24 + 8 = 32-bit exact significand, no rounding or underflow in double).
    // 4. For NaNs, enforce the same IEEE quiet-NaN contract as Test 1.
    uint64_t ftz_mismatches = 0;
    uint64_t ftz_nan_checks = 0;
    uint64_t ftz_flushed_inputs = 0;
    uint64_t ftz_flushed_outputs = 0;

    for (size_t i = 0; i < fp32_set.size(); ++i) {
        const uint32_t a = fp32_set[i];
        const bool a_sub = is_subnormal_f32(a);
        const uint32_t a_ftz_in = a_sub ? (a & 0x80000000u) : a;
        const bool a_ftz_nan = is_nan_f32(a_ftz_in);
        const bool a_ftz_finite_nonzero =
            ((a_ftz_in & 0x7fffffffu) != 0u) && ((a_ftz_in & 0x7f800000u) != 0x7f800000u);
        const double da_ftz = a_ftz_finite_nonzero ? static_cast<double>(bits_to_f32(a_ftz_in)) : 0.0;

        for (uint32_t b_idx = 0; b_idx < 65536u; ++b_idx) {
            const uint16_t b = static_cast<uint16_t>(b_idx);
            const bool b_sub = is_subnormal_bf16(b);
            const uint16_t b_ftz_in = b_sub ? static_cast<uint16_t>(b & 0x8000u) : b;

            const uint32_t got_ftz = mul_f32_bf16<DenormalPolicy::FTZ>(a, b);
            const uint32_t got_ftz_rt = mul_f32_bf16(a, b, DenormalPolicy::FTZ);
            if (got_ftz != got_ftz_rt) {
                if (ftz_mismatches < 10) {
                    std::printf("FTZ runtime/template MISMATCH a=%08x b=%04x\n", a, b);
                }
                ++ftz_mismatches;
            }

            if (a_sub || b_sub) {
                ++ftz_flushed_inputs;
            }

            const uint32_t nat_ftz = native_mul_f32_bf16(a_ftz_in, b_ftz_in);
            if (is_nan_f32(nat_ftz)) {
                ++ftz_nan_checks;
                const bool b_ftz_nan = is_nan_bf16(b_ftz_in);
                bool ok = is_qnan_f32(got_ftz);
                if (ok && (a_ftz_nan != b_ftz_nan)) {
                    ok = (got_ftz == nat_ftz);
                }
                if (!ok) {
                    if (ftz_mismatches < 10) {
                        std::printf("FTZ NaN MISMATCH a=%08x b=%04x got=%08x nat=%08x\n",
                                    a, b, got_ftz, nat_ftz);
                    }
                    ++ftz_mismatches;
                }
            } else {
                uint32_t expected_ftz = nat_ftz;
                const bool b_ftz_finite_nonzero =
                    ((static_cast<uint32_t>(b_ftz_in) & 0x7fffu) != 0u) &&
                    ((b_ftz_in & 0x7f80u) != 0x7f80u);
                if (a_ftz_finite_nonzero && b_ftz_finite_nonzero) {
                    const double db_ftz = static_cast<double>(
                        bits_to_f32(static_cast<uint32_t>(b_ftz_in) << 16));
                    if (std::fabs(da_ftz * db_ftz) < min_norm_f64) {
                        expected_ftz = ((a >> 31) ^ (static_cast<uint32_t>(b) >> 15)) << 31;
                        ++ftz_flushed_outputs;
                    }
                }

                if (got_ftz != expected_ftz) {
                    if (ftz_mismatches < 10) {
                        std::printf("FTZ MISMATCH a=%08x b=%04x got=%08x exp=%08x\n",
                                    a, b, got_ftz, expected_ftz);
                    }
                    ++ftz_mismatches;
                }
            }
        }
    }

    // --- Test 3: Explicit boundary assertions (FTZ vs IEEE divergence case) ---
    // Normal * normal with pre-rounding exp_norm == 0 that rounds UP to 2^-126
    // in IEEE, but flushes to +0.0f in PG060 pre-rounding FTZ:
    //   bound_a = make_f32(0, 63, 0x2aaaaa) -> exp_a = 63, man_a = 0xaaaaaa
    //   bound_b = (64 << 7) | 0x40          -> exp_b = 64, man_b = 0xc0
    //   prod = 0xaaaaaa * 0xc0 = 0x7fffff80 (norm = 0, exp_norm = 63 + 64 - 127 = 0)
    //   pre-shift: sig24 = prod >> 7 = 0xffffff, normal guard round_bit = 0, sticky = 0
    //   post-shift (shift = 1 - exp_norm = 1):
    //     sub_sig = sig24 >> 1 = 0x7fffff (sub_lsb = 1, odd),
    //     sub_round = sig24 & 1 = 1, sub_sticky = 0 (exact odd tie)
    //   IEEE RNE rounds 0x7fffff + 1 -> 0x00800000 (2^-126);
    //   PG060 pre-rounding FTZ sees exp_norm <= 0 (|exact_prod| < 2^-126) -> 0x00000000.
    const uint32_t bound_a = make_f32(0u, 63u, 0x2aaaaau);
    const uint16_t bound_b = static_cast<uint16_t>((64u << 7) | 0x40u);
    const uint32_t bound_ieee = mul_f32_bf16<DenormalPolicy::IEEE>(bound_a, bound_b);
    const uint32_t bound_ftz  = mul_f32_bf16<DenormalPolicy::FTZ>(bound_a, bound_b);
    const uint32_t bound_nat  = native_mul_f32_bf16(bound_a, bound_b);
    if (bound_ieee != 0x00800000u || bound_nat != 0x00800000u || bound_ftz != 0x00000000u) {
        std::printf("FAIL boundary check: ieee=%08x nat=%08x ftz=%08x\n",
                    bound_ieee, bound_nat, bound_ftz);
        return 1;
    }

    std::printf("fp32_set_size=%zu\n", fp32_set.size());
    std::printf("bf16_set_size=65536\n");
    std::printf("total_pairs=%llu\n", static_cast<unsigned long long>(total_pairs));
    std::printf("ieee_mismatches=%llu\n", static_cast<unsigned long long>(ieee_mismatches));
    std::printf("ieee_nan_checks=%llu\n", static_cast<unsigned long long>(ieee_nan_checks));
    std::printf("ieee_subnormal_outputs=%llu\n", static_cast<unsigned long long>(ieee_subnormal_out));
    std::printf("ieee_exact_ties_normal=%llu\n", static_cast<unsigned long long>(ieee_tie_normal));
    std::printf("ieee_exact_ties_subnormal=%llu\n", static_cast<unsigned long long>(ieee_tie_subnormal));
    std::printf("ftz_mismatches=%llu\n", static_cast<unsigned long long>(ftz_mismatches));
    std::printf("ftz_nan_checks=%llu\n", static_cast<unsigned long long>(ftz_nan_checks));
    std::printf("ftz_flushed_inputs=%llu\n", static_cast<unsigned long long>(ftz_flushed_inputs));
    std::printf("ftz_flushed_outputs=%llu\n", static_cast<unsigned long long>(ftz_flushed_outputs));

    return (ieee_mismatches == 0 && ftz_mismatches == 0) ? 0 : 1;
}
