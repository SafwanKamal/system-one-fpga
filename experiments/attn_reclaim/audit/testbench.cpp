// C-sim exactness audit testbench for Qwen3-0.6B HLS decoder variants.
// Derived from experiments/dual_port/testbench_s1.cpp.
//
// Runs either prefill (batch-N groups, N in {8,16}) or decode (single-token
// steps) over all 28 layers, including a deterministic-KV-seeded crossing of
// the 256-row attention TILE boundary, and writes a binary dump of hidden
// states, K/V cache rows, final norm outputs, winning tokens, and raw logit
// bits indexed per kept position (not per group) so runs with different batch
// sizes over the same prompt positions are directly comparable token by token.
//
// argv: <gguf> <meta.bin> <rope.bin> <results.json> <dump.bin> <prefill|decode> [tile_cross:1|0] [batch:8|16]

#include <algorithm>
#include <ap_int.h>
#include <chrono>
#include <cstring>
#include <fstream>
#include <iostream>
#include <stdint.h>
#include <stdexcept>
#include <string>
#include <vector>

using word = ap_uint<256>;
using weight_word = ap_uint<256>;

#ifdef SINGLE_PORT
extern "C" void qwen_decoder(weight_word*, word*, unsigned, uint32_t, uint32_t,
                             uint32_t, uint32_t, unsigned, unsigned, unsigned,
                             unsigned, unsigned&);
static inline void invoke_kernel(weight_word* model, word* scratch, unsigned c,
                                 uint32_t page, uint32_t cache, uint32_t rope,
                                 uint32_t result, unsigned layer,
                                 unsigned position, unsigned rows,
                                 unsigned token_base, unsigned& status) {
  qwen_decoder(model, scratch, c, page, cache, rope, result, layer, position,
               rows, token_base, status);
}
#else
extern "C" void qwen_decoder(weight_word*, weight_word*, word*, unsigned,
                             uint32_t, uint32_t, uint32_t, uint32_t, unsigned,
                             unsigned, unsigned, unsigned, unsigned&);
static inline void invoke_kernel(weight_word* model, word* scratch, unsigned c,
                                 uint32_t page, uint32_t cache, uint32_t rope,
                                 uint32_t result, unsigned layer,
                                 unsigned position, unsigned rows,
                                 unsigned token_base, unsigned& status) {
  qwen_decoder(model, model, scratch, c, page, cache, rope, result, layer,
               position, rows, token_base, status);
}
#endif

static const unsigned NL = 28, NK = 8, NC = 2048, HD = 128, H = 1024;
static const unsigned ROWBYTES = 1088, HEADROWS = 8192;
static const uint32_t PAGES = 0x100, DESC = 0x400, IDS = 0x600;
static const uint32_t ROPE = 0x1000, RESULT = 0x180000, CACHE = 0x200000;
static const uint32_t CACHE_BYTES = NL * 2 * NK * NC * HD * 2;

static void putu(std::vector<word>& m, uint32_t a, uint32_t v) {
  unsigned lo = (a & 31) * 8;
  m[a / 32].range(lo + 31, lo) = v;
}

static uint32_t getu(const std::vector<word>& m, uint32_t a) {
  return (m[a / 32] >> ((a & 31) * 8)).range(31, 0).to_uint();
}

static std::vector<char> slurp(const std::string& p) {
  std::ifstream f(p, std::ios::binary | std::ios::ate);
  if (!f) throw std::runtime_error("cannot read " + p);
  size_t n = f.tellg();
  f.seekg(0);
  std::vector<char> b(n);
  f.read(b.data(), n);
  return b;
}

// Deterministic finite non-uniform BF16 generator for seeding pre-tile KV rows
// without running 250+ full 28-layer passes. Exponents sit in [0x3a, 0x3e]
// (~0.03125 to 0.5) so values never overflow, underflow to subnormals, or NaN.
static uint32_t hash32(uint32_t x) {
  x ^= x >> 16;
  x *= 0x7feb352du;
  x ^= x >> 15;
  x *= 0x846ca68bu;
  x ^= x >> 16;
  return x;
}

static uint16_t synth_bf16(unsigned layer, unsigned kv, unsigned head,
                           unsigned pos, unsigned elem) {
  uint32_t seed = (layer * 131071u) ^ (kv * 65537u) ^ (head * 8191u) ^
                  (pos * 1021u) ^ elem;
  uint32_t h = hash32(seed);
  uint16_t sign = (h >> 31) & 1u;
  uint16_t exp = 0x3au + ((h >> 24) % 5u);  // [0x3a..0x3e]
  uint16_t mant = h & 0x7fu;
  return uint16_t((sign << 15) | (exp << 7) | mant);
}

static void seed_kv_rows(std::vector<word>& scratch, unsigned start_pos,
                         unsigned end_pos_excl) {
  for (unsigned layer = 0; layer < NL; layer++) {
    for (unsigned kv = 0; kv < 2; kv++) {
      for (unsigned head = 0; head < NK; head++) {
        for (unsigned pos = start_pos; pos < end_pos_excl; pos++) {
          uint32_t base =
              CACHE + ((((layer * 2 + kv) * NK + head) * NC + pos) * HD) * 2;
          for (unsigned w = 0; w < 8; w++) {
            word val;
            for (unsigned lane = 0; lane < 16; lane++) {
              uint16_t bf = synth_bf16(layer, kv, head, pos, w * 16 + lane);
              val.range(lane * 16 + 15, lane * 16) = bf;
            }
            scratch[base / 32 + w] = val;
          }
        }
      }
    }
  }
}

struct Group {
  unsigned start;
  std::vector<uint32_t> ids;
  unsigned keep;
  bool batch_path;
  bool seed_before;
  unsigned seed_from;
  unsigned seed_to;
};

struct Record {
  std::vector<unsigned> positions;
  std::vector<uint32_t> hidden, norm, kv, token, logit;
  explicit Record(size_t m)
      : hidden(size_t(NL) * m * H),
        norm(m * H),
        kv(size_t(NL) * 2 * NK * m * 64),
        token(m),
        logit(m) {}
};

static double now() {
  return std::chrono::duration<double>(
             std::chrono::steady_clock::now().time_since_epoch())
      .count();
}

static unsigned parse_batch(const std::string& s) {
  if (s == "8") return 8u;
  if (s == "16") return 16u;
  throw std::runtime_error("batch must be 8 or 16, got: " + s);
}

int main(int argc, char** argv) {
  try {
    if (argc < 7 || argc > 9) {
      throw std::runtime_error(
          "usage: <gguf> <meta.bin> <rope.bin> <results.json> <dump.bin> "
          "<prefill|decode> [tile_cross:1|0] [batch:8|16]");
    }
    const std::string mode = argv[6];
    if (mode != "prefill" && mode != "decode") {
      throw std::runtime_error("mode must be prefill or decode, got: " + mode);
    }
    const bool tile_cross = (argc >= 8) ? (std::string(argv[7]) != "0") : true;
    const unsigned batch = (argc == 9) ? parse_batch(argv[8]) : 8u;

    auto mb = slurp(argv[2]);
    const size_t header_words = 4 + size_t(NL) * 11;
    if (mb.size() < header_words * 4) {
      throw std::runtime_error("meta.bin too small for header");
    }
    std::vector<uint32_t> meta(mb.size() / 4);
    std::memcpy(meta.data(), mb.data(), meta.size() * 4);
    const uint32_t extent = meta[0], embedding = meta[1],
                   output_norm = meta[2];
    const uint32_t* layer_offsets = &meta[3];
    const unsigned n = meta[3 + NL * 11];
    if (n == 0 || n >= NC || mb.size() < (header_words + size_t(n)) * 4) {
      throw std::runtime_error("invalid base position count in meta.bin");
    }
    const uint32_t* ids = &meta[header_words];

    const unsigned chunks = (extent + (1u << 24) - 1) >> 24;
    std::vector<weight_word> model(size_t(chunks) << 19);
    {
      auto g = slurp(argv[1]);
      if (g.size() != extent) {
        throw std::runtime_error("model size differs from metadata");
      }
      g.resize(size_t(chunks) << 24, 0);
      for (size_t i = 0; i < g.size(); i += 32) {
        weight_word v;
        for (unsigned lane = 0; lane < 4; lane++) {
          uint64_t x;
          std::memcpy(&x, g.data() + i + lane * 8, 8);
          v.range(lane * 64 + 63, lane * 64) = x;
        }
        model[i / 32] = v;
      }
    }

    std::vector<word> scratch((CACHE + CACHE_BYTES) / 32 + 64);
    for (unsigned i = 0; i < chunks; i++) putu(scratch, PAGES + 4 * i, i << 24);
    {
      auto rope = slurp(argv[3]);
      if (rope.size() != NC * 512) throw std::runtime_error("rope size");
      for (unsigned i = 0; i < rope.size(); i += 4) {
        uint32_t v;
        std::memcpy(&v, rope.data() + i, 4);
        putu(scratch, ROPE + i, v);
      }
    }

    unsigned status = 99;
    auto call = [&](unsigned c, uint32_t page, unsigned layer = 0,
                    unsigned position = 0, unsigned rows = 0,
                    unsigned token_base = 0) {
      invoke_kernel(model.data(), scratch.data(), c, page, CACHE, ROPE, RESULT,
                    layer, position, rows, token_base, status);
      if (status) {
        throw std::runtime_error("kernel status " + std::to_string(status) +
                                 " cmd " + std::to_string(c));
      }
    };

    call(0, PAGES, 0, 0, chunks, extent);

    // Poison entire KV cache with BF16 quiet NaN (0x7fc0) so any unread-vs-read
    // out-of-bounds KV access triggers a NaN propagation / mismatch.
    word poison;
    for (unsigned lane = 0; lane < 16; lane++) {
      poison.range(lane * 16 + 15, lane * 16) = 0x7fc0;
    }
    for (size_t i = CACHE / 32; i < (CACHE + CACHE_BYTES) / 32; i++) {
      scratch[i] = poison;
    }

    auto real = [&](unsigned start, unsigned count) {
      return std::vector<uint32_t>(ids + start, ids + start + count);
    };
    auto cyclic_real = [&](unsigned count) {
      std::vector<uint32_t> out(count);
      for (unsigned i = 0; i < count; i++) out[i] = ids[i % n];
      return out;
    };

    std::vector<Group> groups;
    if (mode == "prefill") {
      for (unsigned start = 0; start < n; start += batch) {
        unsigned count = std::min(batch, n - start);
        groups.push_back({start, real(start, count), count, true, false, 0, 0});
      }
      if (tile_cross) {
        const unsigned tile_start = 256u - batch / 2u;
        if (n > tile_start) {
          throw std::runtime_error(
              "base positions overlap tile_cross window");
        }
        // Seed KV rows n..(tile_start-1), then run a batch-N group at
        // position tile_start..(tile_start+N-1) straddling the 256-row
        // attention TILE boundary within one call (half in tile 0, half in
        // tile 1; rows >= tile_start+N remain poisoned with 0x7fc0 NaN).
        groups.push_back({tile_start, cyclic_real(batch), batch, true, true, n,
                          tile_start});
      }
    } else {
      for (unsigned p = 0; p < n; p++) {
        groups.push_back({p, real(p, 1), 1, false, false, 0, 0});
      }
      if (tile_cross) {
        if (n > 255u) {
          throw std::runtime_error(
              "base positions overlap decode tile_cross window");
        }
        // Seed KV rows n..254, then run single-token decode across 255 -> 257.
        groups.push_back({255, real(0, 1), 1, false, true, n, 255});
        groups.push_back({256, real(1 % n, 1), 1, false, false, 0, 0});
        groups.push_back({257, real(2 % n, 1), 1, false, false, 0, 0});
      }
    }

    std::vector<unsigned> kept_positions;
    std::vector<int> pos_to_idx(NC, -1);
    for (const Group& g : groups) {
      for (unsigned lane = 0; lane < g.keep; lane++) {
        unsigned pos = g.start + lane;
        if (pos >= NC || pos_to_idx[pos] >= 0) {
          throw std::runtime_error("invalid or duplicate kept position");
        }
        pos_to_idx[pos] = int(kept_positions.size());
        kept_positions.push_back(pos);
      }
    }

    const size_t M = kept_positions.size();
    Record r(M);
    r.positions = kept_positions;
    double t0 = now();

    for (const Group& g : groups) {
      if (g.seed_before) {
        seed_kv_rows(scratch, g.seed_from, g.seed_to);
      }
      unsigned count = g.ids.size();
      double t1 = now();
      if (count == 1 && !g.batch_path) {
        call(1, embedding + g.ids[0] * ROWBYTES, 0, g.start);
      } else {
        for (unsigned i = 0; i < count; i++) {
          putu(scratch, IDS + 4 * i, embedding + g.ids[i] * ROWBYTES);
        }
        call(7, IDS, 0, g.start, count);
      }
      for (unsigned layer = 0; layer < NL; layer++) {
        for (unsigned i = 0; i < 11; i++) {
          putu(scratch, DESC + 4 * i, layer_offsets[layer * 11 + i]);
        }
        if (count == 1 && !g.batch_path) {
          call(2, DESC, layer, g.start);
        } else {
          call(8, DESC, layer, g.start, count);
        }
        for (unsigned lane = 0; lane < g.keep; lane++) {
          call(10, 0, lane);
          size_t pidx = size_t(pos_to_idx[g.start + lane]);
          uint32_t* dst = &r.hidden[(size_t(layer) * M + pidx) * H];
          for (unsigned i = 0; i < H; i++) {
            dst[i] = getu(scratch, RESULT + 4 * i);
          }
        }
      }
      for (unsigned lane = 0; lane < g.keep; lane++) {
        unsigned position = g.start + lane;
        size_t pidx = size_t(pos_to_idx[position]);
        if (lane) call(9, 0, lane);
        call(3, output_norm);
        call(6, 0);
        for (unsigned i = 0; i < H; i++) {
          r.norm[pidx * H + i] = getu(scratch, RESULT + 4 * i);
        }
        call(4, embedding, 0, 0, HEADROWS, 0);
        r.token[pidx] = getu(scratch, RESULT);
        r.logit[pidx] = getu(scratch, RESULT + 4);
      }
      std::cout << mode << " group start=" << g.start << " size=" << count
                << " keep=" << g.keep << " seconds=" << (now() - t1)
                << std::endl;
    }

    size_t k = 0;
    for (unsigned layer = 0; layer < NL; layer++) {
      for (unsigned kv = 0; kv < 2; kv++) {
        for (unsigned head = 0; head < NK; head++) {
          for (size_t pidx = 0; pidx < M; pidx++) {
            unsigned p = kept_positions[pidx];
            uint32_t base =
                CACHE + ((((layer * 2 + kv) * NK + head) * NC + p) * HD) * 2;
            for (unsigned i = 0; i < 64; i++) {
              r.kv[k++] = getu(scratch, base + 4 * i);
            }
          }
        }
      }
    }

    double elapsed = now() - t0;
    {
      std::ofstream d(argv[5], std::ios::binary);
      if (!d) throw std::runtime_error("cannot write dump " + std::string(argv[5]));
      auto put = [&](const std::vector<uint32_t>& v) {
        uint64_t len = v.size();
        d.write(reinterpret_cast<const char*>(&len), 8);
        d.write(reinterpret_cast<const char*>(v.data()), len * 4);
      };
      put(r.hidden);
      put(r.kv);
      put(r.norm);
      put(r.token);
      put(r.logit);
      std::cout << "DUMP written words="
                << (r.hidden.size() + r.kv.size() + r.norm.size() + 2 * M)
                << std::endl;
    }

    size_t nan_kv = 0;
    for (uint32_t v : r.kv) {
      if ((v & 0x7f80u) == 0x7f80u && (v & 0x7fu)) nan_kv++;
      if (((v >> 16) & 0x7f80u) == 0x7f80u && ((v >> 16) & 0x7fu)) nan_kv++;
    }

    std::ofstream json(argv[4]);
    if (!json) throw std::runtime_error("cannot write json " + std::string(argv[4]));
    json << "{\n"
         << "  \"mode\": \"" << mode << "\",\n"
         << "  \"tile_boundary_crossed\": " << (tile_cross ? "true" : "false")
         << ",\n"
         << "  \"tile_boundary_method\": \""
         << (tile_cross ? "deterministic_kv_seed" : "none") << "\",\n"
         << "  \"positions\": [";
    for (size_t i = 0; i < M; i++) json << (i ? "," : "") << kept_positions[i];
    json << "],\n"
         << "  \"tokens\": [";
    for (size_t i = 0; i < M; i++) json << (i ? "," : "") << r.token[i];
    json << "],\n"
         << "  \"kv_nan_values\": " << nan_kv << ",\n"
         << "  \"elapsed_seconds\": " << elapsed << "\n"
         << "}\n";
    json.close();

    std::cout << mode << " complete seconds=" << elapsed
              << " kv_nan_values=" << nan_kv << std::endl;
    return 0;
  } catch (const std::exception& e) {
    std::cerr << "AUDIT ERROR: " << e.what() << std::endl;
    return 1;
  }
}
