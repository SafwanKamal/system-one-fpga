# Streaming Q8 decoder core and larger-model transfer - 2026-10-19

Implementation: `hls/qwen_decoder_v6/matrix_q8.hpp` and `model_profile.hpp`.
The current 0.6B profile is deployed: one real cold command passed in 27.430s
with Linux live, setup slack +0.896ns and hold +0.010ns at 100MHz. See
`build/v2/qwen-fpga-decoder-v6/deployment-proof.json`. Larger profiles remain
unqualified until separately built and checked.

## Data path

Four backpressured stages replace the original row-at-a-time matrix loop:

1. Read contiguous 128-bit weight bursts, splitting at owned 16MiB DMA boundaries.
2. Unpack each 34-byte Q8_0 block into a half scale and 32 signed weights.
3. Compute the four token lanes, with a flat pipeline across matrix output rows.
4. Reduce completed row partials and write outputs or update vocabulary argmax.

The accumulator accepts a block every two cycles when data is available. The
128-bit reader supplies a block every 2/3 cycles (2.125 average), so II2 is a
scheduling capability, not a claim of unlimited bandwidth. Backpressure handles
DDR stalls. No speculative read crosses into another Linux-owned allocation.

Each token keeps eight rotating FP32 accumulator registers. Static addressing
exposes the eight-block recurrence to HLS. At row completion the partials are
rotated back to slot order before reduction, including non-multiple-of-eight
block counts. The order remains: float(weight)*input, pairwise tree32, multiply
by block scale, accumulate in eight interleaved slots, then pairwise tree8.
The row reducer has II16 while a supported row needs at least eight blocks;
current model rows have 32 to 96 blocks, leaving ample time to consume each row.
Short wide FIFOs use SRLs instead of wasting block RAM on very shallow queues.

This changes throughput, not model weights, precision, vocabulary, output
format, prompt or tool registry. Batch prefill still uses four tokens. Each
layer appends KV/attends in increasing token position. Decode uses batch one.

## What transfers

The matrix template takes token count and vector capacity as template parameters,
with row/column counts supplied per projection. It does not encode layer count,
head count, vocabulary size, command text or a specific path. The same template
passed directed functional checks with 2048, 6144 and 1056 columns at capacity
6144, checking four token lanes, all output rows and vocabulary argmax. A real
four-token 0.6B first-layer fixture also passed full and partial causal batches,
final normalization and head argmax (max error 5.72205e-6 versus reference).
These checks establish functional portability of the primitive, not a complete
larger model's accuracy, fit or speed.

`model_profile.hpp` separates hidden/FFN dimensions, query and KV head counts,
layers, context and vocabulary. Activation offsets derive from these dimensions.
KV width is `kv_heads*128`, independent of hidden width; GQA group count derives
from query/KV head ratio. Embedding stride derives from hidden width and Q8_0
packing. Vector-buffer capacity follows the FFN dimension, with compile-time
bounds. The supported head dimension remains 128 and matrix inputs need at least
eight Q8 blocks; these restrictions are explicit. The current embedding reader also requires hidden
width divisible by 256 so its Q8 rows begin on 16-byte boundaries; the host
profile guard rejects unsupported alignment.

`qwen_fpga_runtime_v5.py` verifies the bitstream's declared shape against its
weight manifest before MMIO, derives layer/context/vocabulary counts, embedding
stride, KV reservation size and RoPE length, and accepts an optional separate
`output_projection` offset for an untied Q8 head. Current 0.6B still uses its tied
embedding/head tensor. Full resident SHA256 verification retains bounded cached staging buffers and
checks every byte on every invocation. Direct uncached reads were slower on
the board (9.621s in the numerical smoke), so that experiment was discarded
before the successful cold call; final verification took 4.747s.

The package helper accepts `--manifest`, `--rope` and `--model-path` and rejects
compiled-shape/manifest mismatches or changes to sources frozen before physical build.
A different shape needs a new compile, bitstream and matching manifest; passing
a larger manifest to the existing 0.6B image is intentionally rejected.

## Work still required for a larger model

- Generate and validate that model's tensor offsets, tokenizer/vocabulary, RoPE,
  weights and any separate output head. Preserve its own numerical reference.
- Build its own shape profile and check actual LUT/BRAM/URAM/DSP usage and routed
  timing. A larger vector-capacity C test does not establish KR260 physical fit.
- Extend and qualify model-memory ownership where necessary. The current DMA
  driver and FPGA page table support 64x16MiB segments (1GiB model limit), with
  32-bit DMA constrained below 2GiB physical addresses. These were not enlarged.
- Add a separately verified unpacker for other quantizations. Current wire blocks
  are Q8_0; Q4/K formats are not silently interchangeable. The separated unpacking
  boundary allows their work to reuse the downstream dot/reduction architecture,
  subject to their scaling and arithmetic-order requirements.
- Execute a directed full-model real command on the resulting profile, keeping
  Linux live, before making any capability or timing claim.

The current optimization does not deploy, train or evaluate a larger model and
does not establish worst-case execution time. The current 0.6B target was achieved by one 27.430s cold real tool call with
Linux running and all model math on FPGA.
