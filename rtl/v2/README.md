# v2: a chained, multi-task encoder on FPGA

v1 answers one sentence with one of 151 intents in about 34 µs. v2 spends
milliseconds to tens of milliseconds per request and uses them for a more general
model: one encoder pass over a *chain* of up to 128–256 WordPiece tokens holding
several segments, with small heads on top.

| ability | what the chain holds | output |
|---|---|---|
| intent | one utterance | intent + calibrated probabilities |
| slots + intent | one utterance | intent + a BIO slot tag per word (dates, places, amounts) |
| multi-turn dialogue | the last few turns + the new user turn | intent and slots of the new turn, using the earlier turns |
| multi-sentence input | several utterances | an intent for every one of them, in one pass |
| sentence pairs | two sentences | entailment / contradiction / neutral, paraphrase or not |

The model study behind the choices below is `scripts/v2/train_chain.py`
(results in `results/v2/chain/`), the hardware cost model is
`scripts/v2/chain_hw_estimate.py`.

## Model study (2026-10-04, test splits, one encoder pass of <= 128 tokens)

One shared encoder, trained once on all tasks together (CLINC150, ATIS, SGD
multi-turn dialogue, SICK, MSRP, and synthetic 2–4-utterance chains):

| | bert-mini (4 x 256, 11M) | MiniLM-L6 (6 x 384, 23M) |
|---|---|---|
| CLINC150 in-scope accuracy | 0.930 | **0.953** |
| multi-sentence chains, per-utterance in-scope | 0.918 | **0.944** |
| ATIS intent / slot F1 | 0.961 / 0.809 | 0.959 / 0.782 |
| SGD dialogue intent, **with** previous turns | 0.866 | **0.879** |
| SGD dialogue intent, same turns **without** them | 0.505 | 0.505 |
| SGD slot F1 | 0.480 | 0.496 |
| SICK entailment (3-way) | 0.789 | **0.862** |
| MSRP paraphrase | 0.693 | **0.751** |
| INT8 weights + activations | lossless | lossless |
| est. Nexys 4 DDR latency, 128 tokens | ~29 ms | ~96 ms |
| est. KR260 latency, 128 tokens | ~2.3 ms | ~7.7 ms |

* **Chaining works where it matters.** In multi-turn dialogue the earlier turns
  lift intent accuracy from about 0.50 to 0.87–0.88: most follow-up turns ("yes,
  for 2 people at 7") mean nothing on their own. Packing 2–4 independent requests
  into one pass costs about one point of per-request accuracy.
* **MiniLM-L6 is the pick for the Nexys 4 DDR**: it uses the ~100 ms budget at 128
  tokens and is clearly better on pairs and intents. bert-mini stays as the fast
  fallback (and as the first model to bring up). On the KR260 the same RTL runs
  MiniLM in single-digit milliseconds, or BERT-base-sized models within ~60 ms.
* **Slots were under-weighted, now fixed for bert-mini.** With `--slot-weight 4`
  (`bert-mini-slots4`, 4 epochs, 2026-10-05) ATIS slot F1 goes 0.809 -> **0.911** and
  SGD slot F1 0.480 -> **0.574**, with nothing lost elsewhere (CLINC in-scope 0.932,
  ATIS intent 0.959, SICK 0.803, MSRP 0.687, SGD intent with context 0.868, without
  0.500; INT8 lossless). Integer reference on 500 chains per dataset: ATIS slot F1
  0.905 -> 0.899, SGD slot F1 0.618 -> 0.618, pairs and SGD intent within 1.2 points,
  but CLINC in-scope 0.939 -> 0.920 on that subset. On the whole CLINC test set
  (4,500 in-scope) the loss is smaller, 0.932 -> 0.926 (old bert-mini 0.930 -> 0.920).
* **Calibration statistic.** Each activation's clamp range is the max over
  calibration chains of the per-chain 99.99th percentile. Taking the median instead
  (`int_reference.py --range median --calibration 256`) removes bert-mini-slots4's
  loss: whole CLINC 0.932 -> 0.931, and on 500/dataset every task within 0.6 points
  (CLINC 0.939 -> 0.942, ATIS slot F1 0.905 -> 0.907, SGD slot F1 0.618 -> 0.613),
  98.6% of decisions equal to float (94.7% with max). It is wrong for MiniLM-L6,
  whose activations have heavy outliers: ATIS slot F1 0.779 -> 0.695, SGD slot F1
  0.481 -> 0.408. So the statistic is chosen per model by this check;
  `compile_image.py build --range` follows it. The bert-mini-slots4 image is built
  with median, MiniLM-L6 with max.
* Out-of-scope recall here is plain argmax (0.26–0.31); the v1 probability
  threshold rule applies unchanged to the CLINC head.

## Layout

    rtl/v2/common/                 platform-neutral blocks (FIFOs, divider, display)
    rtl/v2/test/                   bring-up tests that run on any board (ddr_selftest)
    rtl/v2/link/                   DDR over Ethernet (memory link, step 2)
    rtl/v2/encoder/                the encoder datapath (step 4)
    rtl/v2/platform/nexys4ddr/     clocking, MIG adapter, XADC, board tops
    rtl/v2/platform/kr260/         AXI4 memory adapter for the Zynq PS DDR (PS control to come)
    constraints/v2/                board constraints
    ip/v2/nexys4ddr/mig_ddr2.prj   MIG DDR2 configuration (Digilent's, for this board)
    simulation/v2/                 behavioural MIG model, testbenches, Makefile
    scripts/v2/                    model study, project creation, programming
    src/sysone/v2/                 v2 Python package (chained multi-task data)
    build/v2/<board>/              generated Vivado project (gitignored)

v1 is untouched and still builds with `scripts/build_sysone.tcl`; the v2 project
also pulls in the v1 blocks it reuses (Ethernet RX/TX, CRC, `dense_engine`,
`channel_requantizer`).

## The Vivado project

    vivado -mode batch -source scripts/v2/create_project_v2.tcl                  # create
    vivado -mode batch -source scripts/v2/create_project_v2.tcl -tclargs build   # + bitstream
    vivado -mode batch -source scripts/v2/program_board_v2.tcl                   # program
    vivado build/v2/nexys4ddr/sysone_v2_nexys4ddr.xpr                            # GUI

Project mode this time, so it can be opened and inspected in the GUI; the project
directory is generated and can be deleted and recreated at any time.

## Bring-up step 1: DDR2 (`nexys4ddr_ddr_test_top`)

The encoder's weights live in the board's 128 MiB DDR2, so the first thing to prove
on hardware is that memory path. The top writes all 128 MiB with an
address-dependent pattern, reads it back, counts mismatches, and times both phases
using the same 64-beat sequential bursts the encoder will use.

* 7-segment display: write MB/s (left), read MB/s (right). Peak is 1200 MB/s; expect
  roughly 800–1000 read.
* LEDs: 0 MMCM locked, 1 calibration done, 2 running, 3 write phase done,
  4 pass, 5 fail, 6 heartbeat, 15..8 mismatch count.
* SW0 = 1 repeats the test continuously (a soak test); BTNC resets.

Simulated against a behavioural MIG model (`cd simulation/v2 && make ddr`) with 20%
random `app_rdy` / `app_wdf_rdy` stalls: a clean run passes, a single corrupted beat
is reported as exactly one error, `read_last` frames every request, and reads
sustain 79% of peak across request boundaries.

### The memory port

Every v2 block that touches external memory uses one small burst interface:
`*_request_valid/ready/address/beats`, `read_valid/ready/data/last`,
`write_valid/ready/data`. `mig_memory_port` maps it onto the 7-series MIG native
interface; `rtl/v2/platform/kr260/axi_memory_port.sv` maps it onto an AXI4 master
for the KR260's PS DDR (requests split into <= 256-beat bursts that never cross
4 KiB, up to 8 reads in flight, B responses counted). Only that adapter changes per
board. Both adapters run the same `ddr_selftest` in simulation (`make ddr`,
`make axi`); the AXI model checks every AXI4 burst rule and reads sustain 75% of
peak with 25% random stalls on every channel.

## Bring-up step 2: DDR2 over Ethernet (`nexys4ddr_link_top`, default top)

The weights get into DDR2 the same way v1 requests arrive: raw Ethernet frames
(EtherType 0x88B5, protocol version 2), so no CPU or soft core is needed.

| type | direction | header after the 14-byte Ethernet header | payload |
|---|---|---|---|
| 0x20 write | host -> board | version, type, seq (4), address (4), beats (2) | beats x 16 bytes |
| 0x21 ack   | board -> host | same, beats = beats written | - |
| 0x22 read  | host -> board | same | - |
| 0x23 data  | board -> host | same | beats x 16 bytes |

Addresses are byte addresses, multiples of 16; 1..64 beats (1 KiB) per frame; the
byte at the lowest address is bits [7:0] of a beat. Requests that are unaligned,
past the 128 MiB, or with 0 or > 64 beats are dropped without a reply; a bad FCS is
dropped by the v1 receiver. Both operations are idempotent, so the host simply
retransmits anything left unanswered.

`memory_link_core` = v1 `ethernet_RX` / `RX_buffer` -> parser (50 MHz) -> Gray-code
async FIFOs -> executor (MIG `ui_clk`, 75 MHz) -> `mig_memory_port`, and back through
the responder and v1 `TX_buffer` / `ethernet_TX`. The two clocks are declared
asynchronous in `constraints/v2/nexys4ddr_link.xdc`.

* LEDs: 0 MMCM locked, 1 DDR2 calibrated, 2 PHY out of reset, 3 memory busy,
  4 FCS error seen, 5 frame dropped (FIFO full), 6 request rejected, 7 heartbeat.
* 7-segment: requests accepted (left), replies sent (right).

Simulated end to end through the RMII pins with the behavioural MIG and random
stalls (`cd simulation/v2 && make link`): 179 frames from the host's own encoder,
171 answered and 8 correctly ignored (2 bad FCS, 6 malformed), and all 47,872
read-back bytes match a Python model of the memory.

Host client (scapy, Npcap on Windows):

    uv run python scripts/v2/memory_link_client.py --list-interfaces
    uv run python scripts/v2/memory_link_client.py -i "<adapter>" test --mib 1
    uv run python scripts/v2/memory_link_client.py -i "<adapter>" write w.bin --address 0
    uv run python scripts/v2/memory_link_client.py -i "<adapter>" verify w.bin --address 0

Any MB/s the client prints is the host's packet path (Python + Npcap + this
adapter), not the board: DDR2 bandwidth is measured on the board by step 1, and the
encoder never reads weights through this link. Weights are loaded once.

## Bring-up step 3: the DDR image (`scripts/v2/compile_image.py`)

The encoder RTL gets no model-specific parameters. A Python compiler packs
everything a model needs into ONE memory image, written once over the step-2 link:

    ../mlenv/bin/python scripts/v2/compile_image.py build --name bert-mini     # (--board kr260, --base, --tile)
    ../mlenv/bin/python scripts/v2/compile_image.py check --name bert-mini     # bit-exact check
    uv run python scripts/v2/memory_link_client.py -i "Realtek USB FE Family Controller" \
        verify export/v2/image/bert-mini/bert-mini.img --address 0

`build` calibrates the integer reference exactly as `int_reference.py` does (64
training chains per dataset; `--reuse-calibration` takes the ranges from the
existing manifest instead, without the corpora) and writes
`export/v2/image/<name>/{<name>.img, manifest.json, program.txt}`. The format is
specified in `src/sysone/v2/ddr_image.py`; in short:

* **Header (1 KiB)**: magic `SYSONEV2`, format 1, base address, length, body CRC-32,
  model dims, tile shape, and a section table (name, address, bytes, CRC-32).
  Addresses inside the image are absolute, so it is loaded at the base it was built
  for (default 0). Sections start on 1 KiB (64-beat) boundaries, records on beats.
* **program**: 64-byte instructions for the sequencer — `EMBED`, `LAYERNORM`,
  `LINEAR` (weight-stream address, in/out, shift, clamp range, optional 256-entry
  LUT for GELU), `ATTENTION` (heads, head dim, softmax and context multipliers,
  exp-table address), `ADD_SKIP` (INT8 skip rescaled into the INT16 residual),
  `END`; 11 per layer. Operands are named on-chip buffers (X, Q, K, V, CTX, R, A, G).
* **heads**: one 64-byte descriptor per head (kind = segment mean / per token /
  mean of all, classes, weight stream, float32 logit scales, reciprocal table).
* **tables** (softmax exp, pooling reciprocals), **embeddings** (INT8 word and
  position rows, type vector, per-dimension multipliers, LayerNorm params), one
  section per **layer**, one per **head**.
* **Weight streams** are tiled for the weight-stationary array: per output tile of
  TO channels, a block of {bias int32, M int32} per channel, then the input tiles,
  each TO rows of TI INT8 inputs (TI/16 beats). Profiles: `nexys4ddr` 16 x 12,
  `kr260` 32 x 32; dims are zero-padded to the tile.

`check` runs the image with `ImageMachine`, an interpreter that reads every operand
from the image bytes and uses only integer arithmetic — the golden model for the
step-4 sequencer — against `IntEncoder`. It also records the widest intermediate
values and how often each clamp fires.

| | bert-mini | MiniLM-L6 |
|---|---|---|
| image | 11,309,056 B (10.8 MiB) | 22,811,648 B (21.8 MiB) |
| check: test chains / tokens | 1,200 / 38,809 | 600 / 18,973 |
| final hidden codes and head logits | identical (586,241 logits) | identical (289,431 logits) |
| widest values (signed bits) | matmul acc 18, scores 18, P·V 16, LN sum c² 35, LN affine 29 | the same widths |
| values hitting a clamp | ≤ 2e-5 of each kind | ≤ 8e-5 of each kind |

`bert-mini-slots4` (built with `--range median --calibration 256`) packs to the same
11,309,056 bytes and is identical on the same 1,200 chains (586,241 logits); with the
tighter ranges its matmul accumulators reach 19 bits and the LayerNorm sum of
squares 36, and clamps fire on at most 5e-4 of values. On the board (2026-10-05) it
was written at address 0 and read back identical (`verify`); the board answered all
22,091 requests it accepted.

`tests/test_ddr_image.py` (NumPy only, runs with `uv run pytest`) checks the same
on a small random BERT, plus odd tile shapes, relocation to another base, CRC
detection of a single flipped byte and refusal of out-of-range constants.

## Bring-up step 4: one encoder layer, bit-exact in simulation (`rtl/v2/encoder/`)

The datapath that runs the image's layer program. Everything model-specific comes
from external memory through the one memory port; the RTL knows only the tile width
(16 x 12 on the Nexys), the maximum chain length (128) and the buffer sizes.

    encoder_pkg.sv        opcodes, buffer numbers, requant / clamp / element helpers
    encoder_layer.sv      sequencer (fetches 64-byte instructions, dispatches, routes
                          buffers), engines, mac_array, eight activation buffers, host port
    mac_array.sv          16 x 12 signed multipliers (9 x 8 bit), shared by LINEAR and ATTENTION
    linear_engine.sv      weight-stationary tiles; tile streams prefetched, two weight-tile
                          banks, two channel banks, two accumulator banks: loading, MACs
                          and requantisation overlap
    attention_engine.sv   12 queries at a time on the shared array (scores = dot products,
                          P.V = outer products), softmax 12 rows at a time
    layernorm_engine.sv   mean, variance, integer square root, one reciprocal per row
    add_skip_engine.sv    INT8 skip into the INT16 residual, 8 elements per clock
    activation_buffer.sv  128-bit words, one read port, one byte-enabled write port

`simulation/v2/encoder_layer_tb.sv` loads X through the host port, single-steps the
layer's 11 instructions and compares the destination buffer after every one, then
runs the whole layer in one go and compares the final X. Memory is
`memory_port_model.sv` (the image, 12-clock latency, 20% random stalls on requests
and data). Vectors come from `ImageMachine` (`scripts/v2/encoder_vectors.py`): six
real test chains (one per dataset, the longest 128 tokens), a 1-token chain and 128
random token ids.

    cd simulation/v2
    make encoder-vectors ENCODER_MODEL=bert-mini-slots4    # --layer in the script
    make encoder

| image, layer | cases | words compared | mismatches |
|---|---|---|---|
| bert-mini-slots4, layer 0 | 9 | 128,592 | 0 |
| bert-mini-slots4, layer 3 | 9 | 128,592 | 0 |
| MiniLM-L6, layer 5 (12 heads of 32, FFN 1536) | 9 | 192,888 | 0 |

Clocks per layer in simulation (with the model's stalls):

| tokens | bert-mini | MiniLM-L6 |
|---|---|---|
| 1 | 68k | 147k |
| 12 | 77k | 158k |
| 128 | 689k | 1,404k |
| whole encoder, 128 tokens | 2.76M: 27.6 ms at 100 MHz, 36.8 ms at 75 MHz | 8.43M: 84 ms at 100 MHz, 112 ms at 75 MHz |

At 128 tokens (MiniLM): Q/K/V/O 100.7k clocks each (the 16 x 12 array's ideal is
98.3k), FFN in/out 398k each (ideal 393k), attention 97k, LayerNorm 48k each,
ADD_SKIP 6k each. Short chains are bound by weight streaming (one beat per clock).
The first version (no overlap, 16-MAC attention) took 3.05M clocks per MiniLM layer;
overlapping the linear engine's stages and moving attention onto the shared array
brought it to 1.40M. These are simulated clock counts, independent of the Ethernet
link.

### Sized for the chip (2026-10-05)

* **Buffers.** `encoder_layer` takes `MAX_TOKENS` and `MAX_HIDDEN`: X, Q, K, V and CTX
  hold MAX_TOKENS rows of MAX_HIDDEN INT8, R and A twice that (INT16). G, the FFN
  intermediate (up to 4 x MAX_HIDDEN), has no storage of its own: G word a is word
  a / 4 of Q + (a mod 4), because Q, K, V and CTX are dead from the output
  projection to the end of the layer. At 128 tokens the buffers alone take 72 RAMB36 for bert-mini
  (MAX_HIDDEN 256), 108 for MiniLM-L6 (384), against 135 on the xc7a100t.
* **Arithmetic widths** follow the value ranges instead of 64 bits, so each
  multiplier is one or two DSP48E1: requant multipliers are 17-bit (compile_image now
  refuses larger ones and shifts the narrow rounding cannot hold), linear drain
  INT32 x 17, softmax index (max - s) x 17 with |s| <= head_dim * 127^2, context
  INT23 x 17 on 4 requantisers (a word every 4 clocks), LayerNorm c (18 bits) x inv
  (29) and z (21 bits, bounded by 2.83 sqrt(n) 2^12) x gamma. Expected DSP48E1:
  192 (array) + 2 + 12 + 4 + 16 = 226 of 240; the ADD_SKIP products, the LayerNorm
  squares and the softmax probabilities are kept in LUTs (`use_dsp = "no"`).
* **Attention storage:** score and exponential rows are block RAM (one word per key,
  whole-word writes); the exp table is loaded one entry per clock into one
  distributed-RAM copy per lane (12 lookups per clock).
* Still bit-exact: the three layer tests above pass unchanged; per-layer clocks at
  128 tokens are 695k (bert-mini) and 1,412k (MiniLM-L6), the 4-requantiser
  context write-out adding ~5k / ~7k.

**Out-of-context implementation** (not yet run; Vivado is not available in the cloud
workspace):

    vivado -mode batch -source scripts/v2/synth_encoder.tcl                      # both, 75 MHz
    vivado -mode batch -source scripts/v2/synth_encoder.tcl -tclargs minilm      # MiniLM only
    vivado -mode batch -source scripts/v2/synth_encoder.tcl -tclargs bert-mini 10.0

Synthesises, places and routes `encoder_layer` alone on the xc7a100t (configurations
`both` = MAX_HIDDEN 384 + head_dim 64, `minilm`, `bert-mini`) and writes
`build/v2/encoder_ooc/<config>/summary.txt` (LUT, FF, DSP, BRAM, WNS/WHS) plus full
utilisation and timing reports. The MIG, Ethernet link and clocking add a few BRAM
tiles and a few thousand LUTs on top.

Not done yet:
* EMBED (token ids -> rows) and the heads run on the host side of the testbench;
  they come with the v2 request protocol in step 5.
* The GELU table in the linear engine is still written 16 entries per beat (flip-flops,
  2 Kbit); the attention accumulators (12 x 64 x 23 bits) are flip-flops.

## The encoder datapath (planned, after the model study fixes the model)

Everything below is parameterised so the same RTL fits a 240-DSP Artix-7 and a
1,248-DSP Zynq UltraScale+.

* **Weight streamer.** Reads each layer's INT8 weight tiles in order from external
  memory into a double-buffered on-chip tile store. A tile is applied to *every*
  token of the chain before the next one is needed, so weight traffic per pass is
  fixed and the token count only adds compute.
* **Matrix engine.** A ROWS x COLS INT8 MAC array (Nexys 4 DDR ~16 x 12 = 192 DSPs;
  KR260 ~32 x 32), weight-stationary per tile, tokens streaming through. Built on the
  same ideas as `dense_engine` (lane-parallel MACs, `PIPELINED` one input per clock),
  but with a writable tile buffer instead of a ROM.
* **Activations** stay on chip: tokens x hidden INT8 plus a wider residual stream
  (128 x 384 x INT8 = 48 KiB for MiniLM at 128 tokens). The FFN intermediate is
  produced and consumed tile by tile so it is never stored whole.
* **Nonlinear units**, integer-only so the RTL can be bit-exact against a Python
  reference, as in v1: GELU on an INT8 input is a 256-entry table; softmax uses
  max-subtraction, an exp table and one reciprocal per row; LayerNorm needs a mean,
  a variance and an inverse-square-root table; requantisation reuses
  `channel_requantizer` (per-channel multiplier + bias, round, clamp).
* **Attention.** Q K^T and P V for up to 256 tokens are small next to the
  projections; they run on the same MAC array with K and V read from the on-chip
  activation buffer.
* **Heads.** Segment pooling (mean of a segment's token states) plus the head
  matrices: tens of kilobytes of weights, negligible time.
* **Control.** A small sequencer runs a per-model *layer program* (tile addresses,
  shapes, requant parameters) written into memory next to the weights by a Python
  compiler. Changing the model or the board changes the program and a few
  parameters, not the RTL.

## Integer reference (bit-exact target for the RTL)

`src/sysone/v2/int_encoder.py` runs the trained chain model with integer arithmetic
only — INT8 x INT8 -> INT32 matmuls, per-channel requantisation, a 256-entry GELU
table, a table-based softmax with one reciprocal per row, an integer LayerNorm with
an integer square root and one reciprocal per row, an INT16 residual stream, and
table-based segment pooling. `scripts/v2/int_reference.py` checks it: the NumPy
float encoder matches PyTorch to 3.5e-6, and on 500 test chains per dataset the
integer bert-mini loses at most about a point anywhere (CLINC in-scope 0.922 ->
0.922, ATIS intent 0.958 -> 0.956, slot F1 0.811 -> 0.813, SICK 0.768 -> 0.764,
multi-sentence 0.925 -> 0.916, SGD intent 0.892 -> 0.886, SGD slot F1 0.452 -> 0.429).
On MiniLM-L6 (2026-10-05, same check, `results/v2/chain/minilm-l6_int.json`) the
loss is at most about half a point except SGD slot F1: CLINC in-scope 0.964 -> 0.964,
ATIS intent 0.948 -> 0.946, slot F1 0.779 -> 0.775, SICK 0.850 -> 0.852, MSRP
0.738 -> 0.732, multi-sentence 0.949 -> 0.946, SGD intent 0.900 -> 0.894, SGD slot F1
0.481 -> 0.462; 96% of integer decisions equal the float ones.
This is the model the encoder RTL will be checked against, beat for beat.

## Host side

The host — a PC over Ethernet on the Nexys 4 DDR, the Zynq's ARM cores on the KR260
— tokenises (WordPiece), keeps the dialogue history, builds the chain, and turns the
returned logits into probabilities, slot spans and decisions. A v2 request carries
token ids, segment boundaries and which heads to run on which segments; the reply
carries the head logits. Weights are loaded once into DDR over the same link.

## Scaling across boards

| | Nexys 4 DDR | KR260 (K26) | larger (ZU9EG class) |
|---|---|---|---|
| external memory | DDR2 16-bit, 1.2 GB/s (MIG) | PS DDR4 64-bit, ~10 GB/s to PL | PS DDR4 |
| MAC array | ~200 DSPs @ 100 MHz | ~1,000 DSPs @ 250 MHz | ~2,000 DSPs @ 300 MHz |
| host | PC over 100 Mb/s Ethernet | ARM A53 on chip (AXI) | ARM on chip |
| MiniLM-L6, 128 tokens | ~96 ms | ~8 ms | ~3 ms |
| BERT-base, 128 tokens | ~745 ms | ~60 ms | ~25 ms |

(`scripts/v2/chain_hw_estimate.py`; first-order, compute- or memory-bound,
whichever is slower.) On the Nexys 4 DDR every pass is compute-bound, so chaining
buys accuracy from context rather than time; on the bigger parts short passes are
memory-bound and extra chained segments are nearly free up to ~32–64 tokens.

## Bring-up plan

1. DDR2 read/write and bandwidth on the board (`ddr_test` top). Done: 128 MiB, 0 errors,
   write 1005 MB/s, read 1107 MB/s.
2. Load weights into DDR2 over Ethernet and read them back (`link` top). Done: 1 MiB at the bottom and
   top of DDR2 written and read back identical over a USB 100 Mb/s adapter; board
   counters 4096 accepted / 4096 replied.
3. Integer reference model (done: bert-mini and MiniLM-L6 lose at most ~2 points) and the
   DDR image compiler (done: bit-exact in Python; the bert-mini-slots4 image
   written to the board's DDR2 and read back identical, 11,309,056 bytes).
4. Matrix engine + one encoder layer, bit-exact in simulation (done: bert-mini and
   MiniLM-L6 layers, every buffer after every instruction), then on the board.
5. Full encoder, heads, v2 request/reply protocol and host client.
6. KR260 port: AXI memory adapter, PS-side host, larger MAC array.
