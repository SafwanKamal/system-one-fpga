#include "xmul.hpp"
#include "xmul_hls.hpp"

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>

namespace {

inline uint32_t f32_to_bits(float x) {
    uint32_t u = 0u;
    std::memcpy(&u, &x, sizeof(u));
    return u;
}

inline float bits_to_f32(uint32_t u) {
    float x = 0.0f;
    std::memcpy(&x, &u, sizeof(x));
    return x;
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

    // 3. Boundary exponents for underflow (1..27), unit range (126..128), overflow (250..254)
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
        0x000000u,
        0x400000u, 0x400001u, 0x555555u, 0x7fffffu,
        0x000001u, 0x000080u, 0x2aaaaau, 0x3fffffu
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
    const std::vector<uint32_t> fp32_set = build_stratified_fp32();
    const uint64_t total_pairs = static_cast<uint64_t>(fp32_set.size()) * 65536ull;

    // Compile-time default check via function pointer matching exact drop-in signature.
    using MulFn = float (*)(float, uint16_t);
    MulFn default_fn = &mul_xb;
    const uint32_t bound_a = make_f32(0u, 63u, 0x2aaaaau);
    const uint16_t bound_b = static_cast<uint16_t>((64u << 7) | 0x40u);
    const uint32_t expected_default =
#if XMUL_HLS_IEEE
        0x00800000u;
#else
        0x00000000u;
#endif
    if (f32_to_bits(default_fn(bits_to_f32(bound_a), bound_b)) != expected_default) {
        std::printf("FAIL compile-time policy default check\n");
        return 1;
    }

    uint64_t ftz_mismatches = 0;
    uint64_t ieee_mismatches = 0;

    for (size_t i = 0; i < fp32_set.size(); ++i) {
        const uint32_t a_bits = fp32_set[i];
        const float a = bits_to_f32(a_bits);

        for (uint32_t b_idx = 0; b_idx < 65536u; ++b_idx) {
            const uint16_t b = static_cast<uint16_t>(b_idx);

            const uint32_t got_ftz = f32_to_bits(
                xmul_hls::mul_xb<xmul_hls::DenormalPolicy::FTZ>(a, b));
            const uint32_t ref_ftz = xmul::mul_f32_bf16<xmul::DenormalPolicy::FTZ>(a_bits, b);
            if (got_ftz != ref_ftz) {
                if (ftz_mismatches < 10) {
                    std::printf("FTZ MISMATCH a=%08x b=%04x got=%08x ref=%08x\n",
                                a_bits, b, got_ftz, ref_ftz);
                }
                ++ftz_mismatches;
            }

            const uint32_t got_ieee = f32_to_bits(
                xmul_hls::mul_xb<xmul_hls::DenormalPolicy::IEEE>(a, b));
            const uint32_t ref_ieee = xmul::mul_f32_bf16<xmul::DenormalPolicy::IEEE>(a_bits, b);
            if (got_ieee != ref_ieee) {
                if (ieee_mismatches < 10) {
                    std::printf("IEEE MISMATCH a=%08x b=%04x got=%08x ref=%08x\n",
                                a_bits, b, got_ieee, ref_ieee);
                }
                ++ieee_mismatches;
            }
        }
    }

    std::printf("default_policy=%s\n", XMUL_HLS_IEEE ? "IEEE" : "FTZ");
    std::printf("fp32_set_size=%zu\n", fp32_set.size());
    std::printf("bf16_set_size=65536\n");
    std::printf("total_pairs=%llu\n", static_cast<unsigned long long>(total_pairs));
    std::printf("ftz_mismatches=%llu\n", static_cast<unsigned long long>(ftz_mismatches));
    std::printf("ieee_mismatches=%llu\n", static_cast<unsigned long long>(ieee_mismatches));

    return (ftz_mismatches == 0 && ieee_mismatches == 0) ? 0 : 1;
}
