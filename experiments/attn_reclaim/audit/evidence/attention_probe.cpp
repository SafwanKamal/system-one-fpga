#include "qwen_decoder.cpp"

#include <cstdio>
#include <vector>

static uint32_t next_word(uint32_t &state) {
    state ^= state << 13;
    state ^= state >> 17;
    state ^= state << 5;
    return state;
}

static float sample(uint32_t &state) {
    return static_cast<float>(next_word(state) >> 8) / 8388608.0f - 1.0f;
}

int main() {
    std::vector<word> memory(cache_row(0, 0, 1, NK - 1, 260) + 8);
    uint32_t state = 0x4d3e7ac9;
    for (unsigned kv = 0; kv < 2; ++kv) {
        for (unsigned head = 0; head < NK; ++head) {
            for (unsigned pos = 0; pos <= 259; ++pos) {
                const unsigned row = cache_row(0, 0, kv, head, pos);
                for (unsigned w = 0; w < 8; ++w) {
                    word packed = 0;
                    for (unsigned lane = 0; lane < 16; ++lane) {
                        packed.range(lane * 16 + 15, lane * 16) = to_bf16(sample(state));
                    }
                    memory[row + w] = packed;
                }
            }
        }
    }
    const struct { unsigned start, batch; } cases[] = {
        {0, 1}, {23, 1}, {255, 1}, {256, 1}, {257, 1},
        {0, 8}, {16, 8}, {248, 8}, {252, 8},
    };
    for (const auto &test : cases) {
        for (unsigned token = 0; token < test.batch; ++token) {
            for (unsigned index = 0; index < Q; ++index) {
                activation[token][QOFF + index] = sample(state);
            }
        }
        attention(memory.data(), 0, test.start, 0, test.batch);
        for (unsigned token = 0; token < test.batch; ++token) {
            for (unsigned index = 0; index < Q; ++index) {
                const float value = activation[token][COFF + index];
                if (!std::isfinite(value)) return 1;
                std::printf("%u,%u,%u,%u,%08x\n", test.start, test.batch, token, index, asbits(value));
            }
        }
    }
}
