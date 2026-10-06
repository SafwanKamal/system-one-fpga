"""First-order cost of running a small BERT on the Nexys 4 DDR (XC7A100T).

    uv run python scripts/transformer_hw_estimate.py

Counts only what decides feasibility: where the weights live, multiply-accumulates
per inference, and the time to stream weights from DDR2 when they do not fit in
block RAM. Softmax / GELU / LayerNorm are assumed to run on small dedicated units
overlapped with the matrix work (they are O(seq * hidden), not O(hidden^2)).

Assumptions (stated so they can be argued with):
  * token ids come from the host (WordPiece tokenisation on chip is a separate
    problem), so the embedding lookup is seq_len row reads
  * block RAM left for weights if the current model is replaced: ~110 RAMB36
    (~495 KB); the rest is activations, Ethernet buffers, softmax tables
  * DDR2: 16-bit at 650 MT/s through MIG, ~1.3 GB/s peak, 0.8 GB/s sustained for
    long sequential bursts
  * MAC array: N_DSP DSP48E1 at 100 MHz, one INT8 MAC per DSP per clock, 80%
    utilisation; weights read once per inference and reused across all tokens
"""

from __future__ import annotations

MODELS = {           # layers, hidden, ffn, vocab
    "bert-tiny":  (2, 128, 512, 30522),
    "bert-mini":  (4, 256, 1024, 30522),
    "minilm-l6":  (6, 384, 1536, 30522),
}
SEQ = 12            # CLINC150 mean is ~10 WordPiece tokens + [CLS] + [SEP]
BRAM_BYTES = 110 * 4608
DDR_BPS = 0.8e9
CLK = 100e6


def main() -> None:
    print(f"{'model':10s} {'encoder params':>14s} {'emb params':>11s} {'bits':>4s} "
          f"{'weights':>9s} {'fits BRAM':>9s} {'MACs/inf':>9s} {'compute':>9s} "
          f"{'DDR2 stream':>11s} {'latency':>9s}")
    for name, (L, H, F, V) in MODELS.items():
        enc = L * (4 * H * H + 2 * H * F + 4 * H + F + 4 * H)    # weights + biases + 2 LN
        emb = V * H + 512 * H
        macs = SEQ * L * (4 * H * H + 2 * H * F) + L * 2 * SEQ * SEQ * H
        for bits in (8, 4):
            wbytes = enc * bits / 8
            fits = wbytes <= BRAM_BYTES
            for n_dsp in (128, 200):
                compute = macs / (n_dsp * 0.8 * CLK)
                stream = 0.0 if fits else wbytes / DDR_BPS
                lat = max(compute, stream)
                print(f"{name:10s} {enc / 1e6:13.2f}M {emb / 1e6:10.2f}M {bits:4d} "
                      f"{wbytes / 1024:8.0f}K {'yes' if fits else 'no':>9s} "
                      f"{macs / 1e6:8.1f}M {compute * 1e3:7.2f}ms "
                      f"{stream * 1e3:9.2f}ms {lat * 1e3:7.2f}ms  ({n_dsp} DSP)")
    print("\nembedding tables (V x H) go to DDR2 in every case: one row read per token.")


if __name__ == "__main__":
    main()
