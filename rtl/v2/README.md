# v2: a chained, multi-task encoder on FPGA

**RTL optimization (2026-10-10):** optional registered MAC operands have passed
bit-exact KR260 BERT-mini and MiniLM-L12 regressions at eight request lengths,
plus the Nexys instruction-by-instruction layer test. Candidate timing builds
are separate from the working bitstreams. See [OPTIMIZATION.md](OPTIMIZATION.md)
for the measured bottleneck, pipeline/control changes, validation and build commands.

**Dual-board bring-up (2026-10-08):** the KR260 revB boots Ubuntu 24.04.2 with
kernel 6.8.0-1036-xilinx. A 64 MiB boot reservation at 0x60000000 survives FIT
regeneration and reboot. The 32-lane design is fully routed but fails 100 MHz
setup timing. It passes an 80 MHz timing ceiling, with an app bundle requesting
75 MHz from Linux. Board deployment passed on 2026-10-09 at 71,428,571 Hz with
correct SYS2/BUILD registers. DDR image readback is exact and encoder hidden
states are bit-exact at 1/12/64/128 tokens. At 128 tokens: 1,386,238 encoder clocks,
19.41 ms at the measured clock; full request 19.56 ms, host round trip 20 ms.
See `scripts/v2/kr260/README.md` for first boot, Vivado prerequisites,
memory allocation, separate board images and matching verification runs. Nexys
remains available for regression; both boards now have a verified bert-mini baseline.

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
* **And for MiniLM-L6** (`minilm-l6-slots4`, `--slot-weight 4`, lr 5e-5, 3 epochs,
  2026-10-06; test): ATIS slot F1 0.782 -> **0.868**, SGD slot F1 0.496 -> **0.582**,
  SGD intent with context 0.879 -> 0.882 (without 0.511), CLINC in-scope 0.953 -> 0.951,
  SICK 0.862 -> 0.863, MSRP 0.751 -> 0.753, multi-sentence in-scope 0.944 -> 0.944, but
  **ATIS intent 0.959 -> 0.920** (bert-mini-slots4 kept it at 0.959). Integer reference
  (max range, 500/dataset): every task within 0.6 points except SICK 0.850 -> 0.830
  (ATIS slot F1 0.864 -> 0.864, SGD slot F1 0.590 -> 0.591, CLINC in-scope 0.956 -> 0.954);
  97% of decisions equal to float. Image `export/v2/image/minilm-l6-slots4` (22,811,648 B,
  `check`: 600 chains, 0 mismatches; same widths as before), also `-t24`; the encoder RTL
  runs it bit-exact (whole program and a whole request through the Ethernet pins).
  Choice between minilm-l6 and minilm-l6-slots4 depends on whether slots or ATIS intent
  matter more; the image swaps without any RTL change.
* **v3: wider coverage and an embedding head** (`minilm-l6-v3b`, 2026-10-07; trained on
  the user's laptop CPU, ~1.7 h for 2 epochs; test). Adds HWU64 (64 home-assistant intents
  over 18 scenarios: alarms, calendar, email, IoT, music, news, lists, Q&A, transport...,
  with slots) and an **embedding head** (384-d, an intent-kind head on the board: one more
  matrix on the host) trained with a cosine classifier over every intent set plus
  distillation (weight 10) towards the pretrained all-MiniLM-L6-v2 sentence encoder, also
  on the SICK/MSRP sentences. Warm start from `minilm-l6`; heads at lr 1e-3, encoder 4e-5.

  | test | minilm-l6 | minilm-l6-v3b |
  |---|---|---|
  | CLINC in-scope (argmax) | 0.953 | **0.961** |
  | ATIS intent / slot F1 | 0.959 / 0.782 | **0.976 / 0.876** |
  | HWU64 intent / slot F1 | - | **0.916 / 0.696** |
  | SGD intent (context) / slot F1 | 0.879 / 0.496 | 0.868 / 0.506 |
  | multi-sentence in-scope | 0.944 | **0.959** |
  | SICK / MSRP | 0.862 / 0.751 | 0.858 / **0.713** |
  | unseen intents, nearest centroid of k examples: Banking77 1 / 5 / 10-shot | - | 0.526 / **0.760** / 0.800 |
  | SNIPS 1 / 5 / 10-shot | - | 0.809 / **0.900** / 0.934 |

  For reference, the pretrained sentence encoder itself (`embed_eval.py --teacher`):
  Banking77 0.537 / 0.764 / 0.808, SNIPS 0.722 / 0.865 / 0.905; so the board's embedding
  is as good as the off-the-shelf model on unseen intents while the task heads improved.
  INT8 (fake-quant) costs at most ~0.8 points anywhere (Banking77 5-shot 0.758). The one
  regression is MSRP (-3.8 points). ATIS slots now match `minilm-l6-slots4` without its
  ATIS-intent loss.

  **Image** (built and checked on the laptop, 2026-10-07): `export/v2/image/minilm-l6-v3b`,
  23,035,904 bytes (sha256 91331a85...; 36 s to build). `check`: 1,400 chains (200 per
  dataset, 40,999 tokens), hidden state and all 1,274,135 head logits identical between
  ImageMachine and IntEncoder. Widest values: linear accumulator 19 bits (18 before),
  attention scores 18, P.V 16, LayerNorm sum of squares 34, LayerNorm affine 29: inside
  the RTL's widths, so the same bitstream runs it. Out-of-scope threshold 0.48 (table
  below, combined 0.9025, the best so far); HWU threshold see problem 21. Few-shot on the
  integer image (`embed_eval.py --image`, i.e. what the board computes): SNIPS 1 / 5 /
  10-shot 0.799 / 0.905 / 0.930 (float 0.809 / 0.900 / 0.934), Banking77 0.516 / 0.752 /
  0.795 (float 0.526 / 0.760 / 0.800): the integer embedding loses under a point.
  (Banking77 on ImageMachine took 5.7 h on the laptop - NumPy integer arithmetic, ~5k
  sentences; the same run through the board or the KR260 would take minutes.)

  The first attempt (`minilm-l6-v3`, 1 epoch, one learning rate,
  distillation weight 1) is kept for the record: HWU slot F1 0.277, Banking77 5-shot 0.548
  (see "Problems hit", 16-17).
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

**Out-of-context implementation** (run by the user on the laptop, Vivado 2025.2):

    vivado -mode batch -source scripts/v2/synth_encoder.tcl                      # both, 75 MHz
    vivado -mode batch -source scripts/v2/synth_encoder.tcl -tclargs minilm      # MiniLM only
    vivado -mode batch -source scripts/v2/synth_encoder.tcl -tclargs bert-mini 10.0

Synthesises (with retiming), places and routes `encoder_layer` alone on the xc7a100t
(configurations `both` = MAX_HIDDEN 384 + head_dim 64, `minilm`, `bert-mini`) and
writes `build/v2/encoder_ooc/<config>/summary.txt` (LUT, FF, DSP, BRAM, WNS/WHS),
`timing_groups.txt` (failing setup paths grouped by start and end block) and the
full utilisation and timing reports. The MIG, Ethernet link and clocking come on top.

Results, configuration `both`, 13.333 ns (the MIG's 75 MHz):

| run (2026-10-06) | LUT | LUTRAM | FF | BRAM tiles | DSP | WNS |
|---|---|---|---|---|---|---|
| first fit | 42,135 | 6,068 | 17,751 | 127 | 235 | -21.4 ns |
| pipelined | 38,781 | 4,995 | 20,987 | 133 | 235 | +0.226 ns |
| squares in 2 clocks, exp tables in LUT RAM | 40,847 | 6,243 | 21,569 | 127 / 135 | 235 / 240 | +0.252 ns |

The first fit failed timing on whole-function single-clock paths (worst: buffer
block RAM -> the LayerNorm output, 34 logic levels). The pipelining:
* **Buffer reads take `READ_LATENCY` = 3 clocks** (`encoder_pkg`): the mapped address is
  registered at each buffer, then the block RAM, then each port's data is registered
  after the physical-buffer multiplexer. Writes are mapped and registered too. Every
  engine delays its issue flags by READ_LATENCY; the host port reads in 3 clocks.
* **LayerNorm** output in 6 stages (c, c x inv, z, z x g, + b and rounding, shift and
  clamp); the squares pass as |c| -> partial products h^2, h*l, l^2 (|c| = h 2^9 + l)
  -> c^2 -> sum of 8 -> accumulate.
* **Attention**: score dot products registered before the accumulate and max;
  exponentials in 5 stages; P.V probabilities registered (exponent row read a clock
  early); the context write-out in 4 stages, with a WRITE_FLUSH state before done.
* **Linear**: the accumulator read and the weight-tile release moved to the clock
  before the source data; requantisation in 6 stages. **Add-skip** in 3.
* The 12 exp-table copies are forced to LUT RAM (`ram_style = "distributed"`):
  Vivado had moved them to 12 RAMB18, leaving 2 of 135 block RAM tiles.

Cost: 711k -> 718k clocks per bert-mini layer at 128 tokens, 1,436k -> 1,444k per
MiniLM layer. Still bit-exact on all four layer tests. The worst paths left are pure
routing (a buffer address register fanning out to 24 block RAMs, 12.0 of 12.4 ns in
the wires) at 94% block RAM and 98% DSP; in the board top those registers can be
replicated (max_fanout) before anything else.

### Step 5, part 1: EMBED, the whole encoder from token ids (2026-10-06)

`embed_engine.sv` runs the EMBED instruction: the per-dimension type, Mw and Mp
vectors are fetched once; for every token, the id (an INT16 element of buffer X,
written by the host before the run), the word row (`word + id * stride`, H / 16 beats)
and the position row are fetched and two elements per clock go out to R
(4 products in LUTs; `compile_image` now refuses Mw, Mp >= 2^17 or shifts > 24).
Memory-bound by design: 26k clocks for 128 tokens, under 1% of the encoder.

    make encoder-vectors ENCODER_MODEL=bert-mini-slots4 ENCODER_VECTORS=--full
    make encoder

`--full` single-steps the whole program (EMBED, the embedding LayerNorm, every layer)
and compares every destination buffer, then runs it in one go and compares the final X.

| image, whole program | cases | words compared | mismatches | clocks, 128 tokens |
|---|---|---|---|---|
| bert-mini-slots4 (46 instructions) | 9 | 514,368 | 0 | 2.95M (39 ms at 75 MHz) |
| MiniLM-L6 (68 instructions) | 9 | 1,137,024 | 0 | 8.76M (117 ms at 75 MHz) |

### Step 5, part 2: the heads, two versions (2026-10-06)

The image's program ends with the encoder; the heads (`intent.*` and `pair.*` pool rows
then one linear layer, `slots.*` one linear layer per token, all raw INT32 logits with
float per-class scales) can run in either place. One RTL source, parameter
`FPGA_HEADS` of `encoder_layer`:

* **Heads on the host (`FPGA_HEADS = 0`, the version developed further).** The board
  returns the final X (n x H INT8); the host computes `ImageMachine.head_logits`, which is
  bit-exact with `IntEncoder`. No head hardware.
* **Heads on the FPGA (`FPGA_HEADS = 1`).** Two additions: a POOL instruction
  (`pool_engine.sv`: rows [first, first + count) of X -> one INT8 row,
  `(sum * recip[count] + 2^15) >> 16`, recip from the image's table; one DSP48E1) and a raw
  INT32 mode for LINEAR (4-byte elements, rows of ceil(out / 4) words) with an optional
  `rows` field (0 = the run's token count) so pooled rows can go through a head. The host
  builds a per-request head program (`ddr_image.head_program`: POOL per segment, then the
  head's LINEAR; pooled rows in CTX, logits in A), writes it next to the image and runs it
  after the encoder. `make encoder-vectors ENCODER_VECTORS=--heads` + `make encoder`: all
  seven heads, segments split at [SEP]:

| image | cases | words compared | mismatches | clocks for all 7 heads, 128 tokens |
|---|---|---|---|---|
| bert-mini-slots4 | 9 | 41,189 | 0 | 62k-67k (0.9 ms at 75 MHz) |
| MiniLM-L6 | 9 | 43,029 | 0 | 92k-98k (1.3 ms at 75 MHz) |

Compared (128 tokens, MiniLM-L6):

| | heads on the host | heads on the FPGA |
|---|---|---|
| board time | 0 | ~1% of the encoder (98k of 8.76M clocks), memory-bound weight streaming |
| reply | X: n x H = 48 KB | ATIS: intent 18 x 4 B per segment + slots n x 128 x 4 B = 64 KB; CLINC: 151 x 4 B per segment |
| host work | pooling + small matmuls: all seven heads on 128 rows 6.5 ms in NumPy int64, 1.7 ms as float64 (exact here: every sum < 2^53), 2-core cloud VM; a request needs two or three heads | read logits |
| hardware | none | 1 DSP48E1 + a few hundred LUTs (POOL), raw-mode muxes in LINEAR |
| flexibility | any head, any rows, change without touching the board | head program per request |

Nothing here argues for the FPGA version on the Nexys: the slot logits are larger than
X itself, the integer argmax is not the float argmax (the per-class scales differ), and
the host work is trivial. It would matter for a board with no host behind it, or a
much larger head set. So the heads stay on the host; the FPGA version is kept,
tested, behind the parameter.

### Step 5, part 3: one request end to end, heads on the host (2026-10-06)

The memory link gets a RUN command; nothing else changes on the link, and the encoder
is a parameter of the existing top (`nexys4ddr_link_top`, `ENCODER = 1`; the Vivado
project's `encoder` top).

    host                                   board (sysone_v2_core)
    WRITE ids (n UINT16) -> request area   memory_link_core writes DDR2
    RUN descriptor (one beat)              executor hands the memory port to encoder_system:
                                             ids DDR2 -> buffer X, program 0..END,
                                             X -> DDR2 result area
    <- RUN DONE (one beat)                 encoder clocks, request clocks, status, END index
    READ X (n x H INT8), 64 beats/frame    memory_link_core reads DDR2
    heads, labels (NumPy)

* `rtl/v2/link`: parser accepts type 0x24 (exactly one beat), the command word gains an
  `is_run` bit (121 bits), the executor passes the descriptor out and waits
  (`run_active` = the memory port belongs to the encoder), puts the result beat in the
  read-data FIFO; the responder sends it as 0x25. `make link` (now with a RUN, answered by
  a no-encoder stub with status 0x80, and a two-beat RUN that must be ignored): PASS.
* `rtl/v2/encoder/encoder_system.sv`: descriptor `<IHHII` (program, n, H, ids address,
  result address), checks it, reads the ids into X through the host port, starts
  `encoder_layer` (first 0, until END), writes X back in 64-beat bursts, counts clocks.
* `rtl/v2/system/sysone_v2_core.sv`: the link plus, with ENCODER = 1, encoder_system and the
  memory-port multiplexer; with ENCODER = 0 a RUN gets status 0x80 at once.
* Host: `src/sysone/v2/memory_protocol.py` (RUN / RUN DONE), `encoder_client.py` (request
  area after the image at the next 1 MiB: ids, X 4 KiB above; `EncoderBoard`,
  `LocalEncoder` = ImageMachine), `wordpiece.py` (BERT uncased WordPiece in plain Python:
  identical to the Hugging Face tokenizer on all 210,462 test segments), `host_heads.py`
  (chain building identical to training on all 56,842 test chains; heads and labels; the
  decisions equal `int_reference.py`'s), `scripts/v2/sysone_v2_client.py` (`load`, `check`,
  `run`, `eval`; `--local` without a board). NumPy and scapy only.

**Simulation through the RMII pins** (`make system-vectors` + `make system`;
`encoder_system_tb.sv`: sysone_v2_core, mig_memory_port and the behavioural MIG preloaded
with the image, frames built by the host code, replies decoded by the host decoder):

| image | requests | result | board clocks, 128 tokens |
|---|---|---|---|
| bert-mini-slots4 | 9 (128, 64, 12, 1 random ids + 5 real test chains) | X bit-exact, status 0, stopped at END | encoder 2,952,317; request 2,963,767 = 39.5 ms at 75 MHz |
| MiniLM-L6 | 8 (128, 12, 1 random ids + 5 real test chains) | X bit-exact, status 0, stopped at END | encoder 8,767,175; request 8,784,307 = 117.1 ms at 75 MHz |

A request costs the encoder plus ~0.4% (reading the ids, writing X). Reading X back
over the link and the heads are host-side.

**On the board** (needs the user: Vivado and the Nexys 4 DDR):

    vivado -mode batch -source scripts/v2/create_project_v2.tcl -tclargs build encoder
    vivado -mode batch -source scripts/v2/program_board_v2.tcl -tclargs encoder
    uv run python scripts/v2/sysone_v2_client.py -i "Realtek USB FE Family Controller" load
    uv run python scripts/v2/sysone_v2_client.py -i "Realtek USB FE Family Controller" check
    uv run python scripts/v2/sysone_v2_client.py -i "Realtek USB FE Family Controller" run --dataset atis "show me flights from denver to boston tomorrow morning"

`check` compares the board's X with ImageMachine for random chains of 1, 12, 64 and 128
tokens and prints the board's own clock counts.

**On the board (2026-10-06): bit-exact.** Full build (`encoder` top: MIG, link, encoder)
in Vivado 2025.2: WNS +0.187 ns, WHS +0.013 ns, 0 failing endpoints at 75 MHz; LUT
50,185 / 63,400 (79%), LUT as memory 8,388, FF 27,116 (21%), block RAM 128 / 135 (95%),
DSP 236 / 240 (98%). bert-mini-slots4 loaded (11,309,056 bytes, identical after
read-back, 15 s host path), then `check`:

| tokens | X | board: encoder clocks | encoder ms @ 75 MHz | request ms (board) | host round trip (host path, includes Ethernet) |
|---|---|---|---|---|---|
| 1 | bit-exact | 232,870 | 3.10 | 3.11 | 6 ms |
| 12 | bit-exact | 291,527 | 3.89 | 3.90 | 8 ms |
| 64 | bit-exact | 1,441,377 | 19.22 | 19.29 | 30 ms |
| 128 | bit-exact | 2,951,462 | 39.35 | 39.49 | 60 ms |

The 128-token count is within 0.03% of the simulation (2,952,317; the difference is
real DDR2 latency against the behavioural MIG). Speed figures are the board's own clock
counts; the host round trip is reported only as a host-path number.

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

### Faster option: two products per DSP (2026-10-06, simulation; not yet synthesised)

At 128 tokens the linear layers are ~83% of a MiniLM-L6 pass and the 16 x 12 array runs
them at 98% of its peak, so the only way to go faster on the Nexys 4 DDR is more
multipliers. Every DSP48E1 is in use, but the array's products always share one
operand per input row (b[r]: the token's input, or the key / value), and the operands
are small (INT8 weights and queries, probabilities 0..255), so one DSP48E1 can compute
two of them: P = (a1 * 2^16 + a2) * b through the pre-adder, a2 * b = P[15:0],
a1 * b = P[42:16] + P[15]. Exact for a in [-128, 255], b in [-128, 127] (exhaustive
check in Python; 200k random operand sets against the plain array).

Parameters (all default to the proven configuration):

| parameter | default | packed option | what |
|---|---|---|---|
| `mac_array` / `encoder_layer` MAC_PACK | 0 | 1 | two products per DSP48E1 |
| TILE_OUT | 12 | 24 | 16 x 24 tiles: 384 products on 192 DSPs |
| ATTENTION_LANES | TILE_OUT | 12 | attention keeps 12 queries at a time (its per-lane softmax DSPs) |
| ACCUMULATORS_IN_LUTS | 0 | 1 | LINEAR's accumulator banks (128 x 24 x 32 bits x 2) in LUT RAM: frees ~10 RAMB36 |
| DRAIN_LANES | 1 | 2 | requantisers, so the drain keeps up with 24 channels |

Images for it: `compile_image.py build --tile 16x24 --reuse-calibration --suffix=-t24`.
Board build: `create_project_v2.tcl -tclargs build encoder_packed` (top parameter
ENCODER_PACKED = 1); the default `encoder` build is unchanged.

| 128 tokens, simulated, bit-exact | 16 x 12 | packed 16 x 24 | |
|---|---|---|---|
| bert-mini-slots4 | 2.95M clocks, 39 ms | 1.88M, 25 ms | 1.57x |
| MiniLM-L6 | 8.76M, 117 ms | 5.20M, 69 ms | 1.69x |

`make encoder-t24` (whole programs and head programs) and `make system-t24` (whole
requests through the Ethernet pins: bert-mini-slots4-t24 8 requests, minilm-l6-t24 6,
X bit-exact; the board reports 1,883,605 / 5,201,468 encoder clocks at 128 tokens;
short chains are unchanged, e.g. 1 token 3.6 ms / 11.5 ms, because they are bound by
streaming the weights from DDR2, not by the multipliers). Resources are estimates until Vivado runs it
(`synth_encoder.tcl -tclargs both-t24`): DSP ~238 of 240, block RAM ~117 of 135, LUTs
+~8k (accumulators in LUT RAM, 12 more lanes of adder trees, the split adders), so
~58k of 63.4k with the MIG and the link: tight. Timing risk: the split adder sits
between the DSP output register and the engines' adder trees.

### Out-of-scope rule for the CLINC head (2026-10-06)

The v2 CLINC head has "oos" as a 151st class; plain argmax finds few out-of-scope
queries. `scripts/v2/oos_threshold.py` applies v1's host-side rule (oos when the top
probability is below tau, tau with the best out-of-scope recall on validation within
1 point of in-scope accuracy) to the integer model the board runs (ImageMachine on
every CLINC validation and test utterance) and writes
`export/v2/image/<name>/decision.json`, which `host_heads.Heads` and the client apply.

| CLINC test (5,500) | tau | in-scope | OOS recall | combined |
|---|---|---|---|---|
| bert-mini-slots4, argmax | - | 0.931 | 0.270 | 0.811 |
| bert-mini-slots4, threshold | 0.46 | 0.923 | 0.698 | 0.882 |
| MiniLM-L6, argmax | - | 0.952 | 0.294 | 0.832 |
| MiniLM-L6, threshold | 0.475 | 0.944 | 0.712 | **0.902** |
| MiniLM-L6-slots4, argmax | - | 0.950 | 0.272 | 0.827 |
| MiniLM-L6-slots4, threshold | 0.395 | 0.945 | 0.666 | 0.894 |
| MiniLM-L6-v3b, argmax | - | 0.956 | 0.394 | 0.854 |
| MiniLM-L6-v3b, threshold | 0.48 | 0.947 | 0.703 | **0.9025** |
| v1 board model (distilled, for reference) | 0.38 | 0.929 | 0.743 | 0.890 |

### v3 on the host: routing, your own intents, long inputs (2026-10-07)

No RTL change: everything here is host code around the same RUN request.

* **`run --dataset auto`** (`host_heads.route`): one encoder pass, then in order:
  custom intents (embedding head, nearest centroid above `--threshold`, default 0.6);
  CLINC with its out-of-scope rule; a flight intent -> ATIS intent + slots; a service
  intent (restaurants, hotels, cars, rides, music, weather, banking...) -> SGD intent +
  slots unless SGD says NONE; otherwise HWU64 when its own probability clears its
  threshold; otherwise the CLINC intent. The ATIS / SGD / HWU heads have no "none of
  these" class, so they are only consulted after CLINC (or HWU's threshold) accepts the
  request. Before this, an off-topic question to `--dataset atis` came back as an
  airline intent with nonsense slots.
* **Your own intents** (`--intents my_intents.json`, `{"name": ["example", ...]}`,
  example `examples/v2/custom_intents.json`): the examples are encoded once by the
  board, their mean embeddings cached next to the file per image; a request goes to the
  nearest centroid (cosine). No retraining, no new bitstream. Accuracy to expect on
  unseen intents: the few-shot rows of the v3 table (5 examples each: 0.76 over 77
  banking intents, 0.90 over 7 assistant intents).
* **Long inputs** (`doc --file text.txt`, also `--query "..."` to rank the sentences by
  similarity). The encoder's limit stays 128 tokens per pass (see below); the host splits
  the text into sentences and sends them as requests, so any length works. Each
  sentence gets the `auto` routing. Measured on documents built from CLINC test
  sentences (`scripts/v2/longtext_eval.py`, MiniLM-L6 image on ImageMachine = the
  board's integer result), per-sentence accuracy:

  | sentences per 128-token request | 100 words | 300 words | 1000 words |
  |---|---|---|---|
  | 1 (each alone, default) | 0.830 | 0.939 | 0.905-0.919 |
  | at most 2 | | | 0.886 |
  | at most 4 | 0.830 | 0.851 | 0.876 |
  | as many as fit | 0.698 | 0.757 | 0.790 |

  Sentences sharing a request attend to each other and that costs accuracy, so the
  default is one sentence per request (`--max-segments` to trade accuracy for speed).
  Board time for the encoder, from the measured clocks per request length (bert-mini on
  the board; MiniLM-L6 from simulation; 75 MHz):

  | 1000 words (~1,350 tokens) | 1 per request | at most 4 | as many as fit |
  |---|---|---|---|
  | bert-mini | ~0.50 s (125 requests) | ~0.38 s | ~0.37 s (10 requests) |
  | MiniLM-L6 | ~2.4 s | ~1.4 s | ~1.1 s |

  Packing saves only the per-request weight streaming (~3 ms bert-mini, ~11.5 ms
  MiniLM-L6), which is why bert-mini barely gains from it.
* **Why not a longer window in hardware.** At 128 tokens the activation buffers take
  108 of the 135 RAMB36 (MAX_HIDDEN 384; 72 for a bert-mini-only build) and they scale
  with the window, so 256 tokens needs ~216: it does not fit the xc7a100t, for either
  model. Attention's share grows with the square of the length (MiniLM-L6 at 512 tokens:
  attention ~0.2G of ~1.1G multiply-adds per layer, so still mostly linear). The KR260
  (K26: 144 RAMB36 + 64 UltraRAM = ~18 Mbit more) could hold MiniLM-L6 buffers for ~512
  tokens; the models would then need training on longer chains. A cheaper step on the
  Nexys: a per-segment attention mask in the attention engine (keys of other segments
  masked off) would let packed sentences behave like separate requests at the packed
  speed; not done.

### KR260: the same encoder as a PL block (2026-10-06, simulation only)

* `rtl/v2/platform/kr260/kr260_encoder.sv`: AXI4-Lite control registers (descriptor =
  the RUN descriptor, start / done / irq, status, clock counts, ID "SYS2", build
  parameters), `encoder_system` (unchanged), `axi_memory_port` to the PS DDR4.
  `TILE_OUT = 32`.
* Images for it: `compile_image.py build --board kr260 --base 0x60000000 --suffix=-kr260`
  (tile 16 x 32; the RTL's tile input is fixed at 16, so the `kr260` profile is now
  16 x 32 instead of the planned 32 x 32; absolute addresses in a reserved PS DDR region).
* `make encoder-kr260` (encoder_layer at TILE_OUT 32, 32-bit addresses, image at
  0x60000000; whole program, 1 and 128 tokens; head programs too): bit-exact. With one
  requantiser in the linear engine's drain it took 2.01M clocks at 128 tokens for
  bert-mini (2.95M at TILE_OUT 12): at 32 output channels the drain (n x 32 clocks per
  output tile) is slower than the MACs (n x in_tiles). New `DRAIN_LANES` parameter
  (linear_engine, 1 on the Nexys, unchanged and still bit-exact there; 4 on the KR260,
  2 DSP48E1 each): 1.46M clocks, Q/K/V 35k -> 17.6k each. What is left at 128 tokens is
  LayerNorm (51k each, 9 per pass, ~31%): its three 48-bit sequential divisions per token
  and 2 elements per clock; the next KR260 step is more LayerNorm lanes and dividers
  overlapped across tokens.
* `make kr260-vectors` + `make kr260` (`kr260_encoder_tb.sv`: AXI4 slave model of the PS
  DDR, preloaded with the image, random stalls; runs started through the registers as the
  ARM would): ID and BUILD registers, irq, X bit-exact for 1, 12 and 128 tokens.
* Block design: `scripts/v2/kr260/create_project_kr260.tcl` (Zynq PS with the board
  preset, HPM0_FPD -> registers at 0xA000_0000, encoder -> S_AXI_HP0_FPD 128-bit, pl_clk0
  100 MHz, irq -> pl_ps_irq0) and `kr260_encoder_wrapper.v` (Verilog wrapper for the
  module reference). Written before the board arrived and not run: a starting point.
* ARM side: `src/sysone/v2/kr260_link.py` (`Kr260Link`: the same write / read / run
  interface as the Ethernet link, on /dev/mem, uncached), so the whole host client runs
  on the board: `sysone_v2_client.py --kr260 --image bert-mini-slots4-kr260 check`.
  Not run on hardware (the block design script above is untested; Linux also needs a
  reserved-memory node for the region).

## Problems hit and how they were solved

The significant failures on the way to the board run, in the order they appeared.
Each one: what was seen, the cause, the fix, and where it lives.

**Hardware and RTL**

1. **Encoder timing failed by 21 ns** (first out-of-context fit, WNS -21.4 ns at
   13.333 ns). Cause: whole operations in one clock; the worst path went buffer
   block RAM -> LayerNorm output through 34 logic levels. Fix: pipelining everywhere:
   buffer reads take `READ_LATENCY` = 3 (address register, block RAM, register after
   the physical-buffer multiplexer) and every engine delays its issue flags to match;
   LayerNorm output in 6 stages, attention exponentials in 5, the context write-out in
   4, linear requantisation in 6, add-skip in 3 (`encoder_pkg.sv`, all engines).
   Result +0.226 ns. Cost ~1% more clocks per layer; still bit-exact.
2. **Block RAM ran out (133 of 135)** after pipelining. Cause: Vivado moved the 12
   exp-table copies into 12 RAMB18. Fix: `(* ram_style = "distributed" *)` on the
   tables, and the LayerNorm squares split as |c| = h 2^9 + l over two clocks so they
   stay in LUTs (`attention_engine.sv`, `layernorm_engine.sv`). 127 / 135, +0.252 ns.
3. **Remaining paths were pure routing** (a buffer address register fanning out to 24
   block RAMs, 12.0 of 12.4 ns in wires). Fix: `(* max_fanout = 8 *)` on the read address
   register (`encoder_layer.sv`) so Vivado replicates it. +0.341 ns out of context,
   +0.187 ns in the full board build.
4. **DSPs at the limit** (238 of 240 with EMBED's 3 multipliers). Fix: EMBED kept in
   LUTs (`(* use_dsp = "no" *)`, `embed_engine.sv`); 236 / 240 in the board build.
5. **RUN result word was 176 bits wide** in `encoder_system.sv` (a padding field too
   wide in the concatenation of the 128-bit result). Caught as a Verilator width
   error. Fix: 32'd0 padding, so the result beat is exactly 128 bits.
6. **Packed DSP (two products per DSP48E1) failed at a = -256.** Cause: outside the
   operand range the pre-adder trick is exact for. Fix: the documented and tested
   range is a in [-128, 255], b in [-128, 127], which covers every operand the encoder
   produces (`mac_array.sv`, `tests/test_mac_packing.py`, exhaustive).

**Build and tools**

7. **Vivado could not generate the MIG for the encoder project**: "Path length exceeds
   260-Byte maximum allowed by Windows" (263 bytes under OneDrive for a MIG
   example-design file). Cause: the longer project names `nexys4ddr_encoder/
   sysone_v2_nexys4ddr_encoder` on top of a deep repo path. Fix: the encoder projects are
   `build/v2/enc/enc.xpr` and `build/v2/encp/encp.xpr` (~225 bytes worst case);
   bitstreams still land in `build/v2/nexys4ddr/` (`create_project_v2.tcl`). If it ever
   recurs: `subst R: "<repo path>"` and build from R:.
8. **The LINEAR activation table (`lut_reg`, 256 x 8) is built from registers** (Synth
   8-4767, "RAM has multiple writes"): it is loaded 16 bytes per clock. Not an error:
   ~2k flip-flops plus a read multiplexer, already inside the timing and LUT numbers.
   Could become one byte per clock in LUT RAM if LUTs ever run short.

**Host software**

9. **`check` failed on the board at once: "write at 0xb00000: board wrote 1 beats"**.
   Cause: a host bug, not the board. A 1-token request writes one 16-byte beat; the
   frame (26-byte header + 16) is padded to Ethernet's 60-byte minimum, and the client
   computed the beats it had sent from the frame length, (60 - 26) // 16 = 2, against
   the board's correct 1. Writes of 2+ beats are never padded, so the 11 MB image
   load had passed. Fix: count beats from the data, not the frame
   (`scripts/v2/memory_link_client.py`). The same check then passed for 1-128 tokens.
10. **Head vectors for the KR260 image ignored the image base** (0x60000000), so head
    programs pointed at the wrong addresses. Fix: head programs are built relative to the
    image base (`scripts/v2/encoder_vectors.py`, `ddr_image.head_program`).
11. **A float64 matmul in `ImageMachine.hidden` made the reference much slower**
    without changing results. Fix: kept only where it matters (`head_logits`, exact
    host-side logits); the integer encoder stays as before (`ddr_image.py`).
12. **The out-of-scope smoke test overwrote a real threshold**:
    `oos_threshold.py --limit 30` wrote bert-mini-slots4's decision.json with tau 0.
    Fix: restored tau 0.46 from `results/v2/chain/bert-mini-slots4_oos.json`; `--limit`
    now writes nothing.

**Models and evaluation**

13. **CLINC out-of-scope queries mostly missed** with plain argmax over 151 classes
    (OOS recall 0.27-0.29). Fix: v1's max-probability rule, tau tuned on validation at
    <= 1 point of in-scope accuracy: OOS recall 0.70-0.71, combined accuracy up to
    0.902 for MiniLM-L6 ("Out-of-scope rule" above, `decision.json` per image).
14. **Slot F1 was weak** (ATIS 0.78, SGD 0.50 for MiniLM-L6). Fix: slot loss weighted x4
    (`train_chain.py --slot-weight 4`): 0.87 / 0.58, at a cost of ATIS intent
    (0.959 -> 0.920) ("Model study").
15. **Long runs in the cloud workspace were killed by container restarts** (training,
    out-of-scope evaluation). Fix: `train_chain.py --resume` with a checkpoint every
    200 batches; `oos_threshold.py` caches probabilities every 250 chains
    (`logs/oos_cache/`) and resumes.

**Models and data, v3 (2026-10-07)**

16. **HWU64 slot F1 was 0.28** in the first v3 run (`minilm-l6-v3`), against ~0.7-0.8
    expected. The data parsed correctly; the cause was the optimiser: the new heads (HWU
    intent and slots, embedding, prototypes) started from random weights and trained at
    the encoder's learning rate (4e-5) for one epoch, so the slot head barely left
    "everything is O". Fix: `train_chain.py --head-lr` (heads at 1e-3, encoder at 4e-5,
    two parameter groups) and 2 epochs: HWU slot F1 0.696, intent 0.850 -> 0.916.
17. **The embedding head was worse than the model it started from** on intents it never
    saw (Banking77 5-shot 0.548 against 0.764 for the pretrained all-MiniLM-L6-v2). The
    task fine-tuning had moved the encoder away from a general sentence embedding (the
    plain `minilm-l6` chain model already scores 0.529) and a distillation weight of 1
    could not pull it back. Fix: `--distill-weight 10`, and distillation also on the
    SICK/MSRP sentences (they carry no intent label): Banking77 5-shot 0.760, SNIPS 0.900
    (above the pretrained model's 0.865), with the task heads better than before.
18. **Training on the laptop failed at once**: "Couldn't instantiate the backend
    tokenizer". The laptop's `models/all-MiniLM-L6-v2` held only weight files (PyTorch,
    TF, Rust, OpenVINO) - no `config.json`, no tokenizer. Fix: the three missing files
    copied (same weights, md5-checked); `scripts/v2/fetch_models.py` now downloads a
    complete copy for a new machine. Training also moved off the 2-core cloud workspace:
    `pyproject.toml` group `train` (CPU PyTorch + transformers), `--threads` defaults to
    every core; the laptop took ~1.7 h for 2 epochs against ~2.5 h in the cloud.
19. **Packing many sentences into one request cost up to 15 points** of per-sentence
    accuracy on long texts (sentences attend to each other; training only had 2-4 per
    chain). Fix: one sentence per request by default (`doc --max-segments 1`); numbers
    in "v3 on the host".
20. **Work done twice**: an interrupted session had already added HWU64, the embedding
    head, few-shot evaluation and custom-intent / long-text client code to the cloud
    workspace, unknown to the next session, which started on the same features. Caught
    by duplicate argparse options (`--intents` defined twice); the earlier, more complete
    client code was kept and the duplicates removed. Lesson: list recently changed files
    before starting on a request.

21. **The HWU router statistics were wrong** (`oos_threshold.py --extra hwu`, first run
    on minilm-l6-v3b): "OOS rejected" 0.405 with CLINC alone, against 0.703 OOS recall
    from the threshold rule on the same probabilities. Cause: the statistic treated a
    sentence as in scope whenever CLINC's top probability cleared tau, but CLINC's top
    class can itself be "oos" (it is the 151st class), which the real router
    (`host_heads.route`) rejects. The same error went into choosing tau_hwu (0.515).
    Fix: the statistic now mirrors the router exactly. Rerun completed on 2026-10-09,
    including uncached tail queries: corrected HWU tau is 0.480, CLINC-only OOS
    rejection 0.703 and CLINC+HWU OOS rejection 0.292. Both image variants use
    the corrected decision file; results are in minilm-l6-v3b_oos.json.

22. **KR260 preparation gaps (2026-10-08).** The client used 75 MHz even with
    `--kr260`, and it accepted an incompatible image before attempting PS-memory
    writes. Fix: KR260 defaults to 100 MHz (override for other builds); the driver
    checks image tile/dimensions against BUILD and checks image plus request space
    against the mapped region. Failed probes now close mappings/file descriptors.
    Board variants record their source model and copy its decision rule. The local
    Vivado 2025.2 project-creation attempt found missing KR260 SOM board files;
    the script reports the install prerequisite before creating a project.
    Driver guards are tested without hardware; block-design validation and physical
    reserved-memory setup remain pending.

23. **KR260 Linux and Vivado preflight (2026-10-08).** First boot succeeds on
    Ubuntu 24.04.2, KR260 revB; Python 3.12 and NumPy 2.4.4 work. Doctor shows
    only the PMU boot reservation: 0x60000000 lies in System RAM, so the current
    image allocation must be reserved before loading. Local Vivado also has no
    installed xck26 parts. The build script now checks device support first and
    can use a local official Board Store checkout. Device installation, boot-time
    memory setup and the custom PL build remain pending; no encoder hardware run
    has been attempted on this board.

    The owner subsequently installed Kria device support. Project creation now
    succeeds in Vivado 2025.2: PS preset, address assignment, block-design validation
    and wrapper generation pass (`build/v2/kr260-create.log`). This is not yet an
    implemented bitstream. Local board shadowing, initial clock metadata and HP0
    AXI USER-width warnings remain to be reviewed before implementation.

    Follow-up: the board now runs kernel 6.8.0-1036-xilinx. A 64 MiB no-map
    reservation at 0x60000000 is verified in the live DT and iomem after normal
    FIT regeneration and reboot. Early kernel/initramfs hooks patch the source
    revB DTB before flash-kernel generates the FIT. The optional local board
    repo is only used when installed Kria boards are absent; generated AXI-Lite
    and AXI4 connections and tied-off HP0 USER inputs were inspected.
    Encoder IP synthesis in Vivado 2025.2 passes with no errors/critical warnings:
    110,190 LUTs (94.08% of K26), 47,377 registers, 606 DSPs, 59 BRAM tiles
    and 18 UltraRAMs. This is encoder-only synthesis, not full-design fit or
    timing. Placement/routing remains pending. The Ubuntu overlay is derived
    from SDTGen and compiles; Linux reports the required fclk and AFI drivers.
    Packaging and deployment helpers are prepared but not yet exercised on
    a completed implementation or hardware app.

24. **Runtime overlay bus layout (2026-10-08).** The first prepared overlay
    wrapped clock, AFI and encoder nodes in a new simple-bus below amba. Linux's
    dynamic OF notifier creates devices only when their parent is already a
    populated bus, so this extra layer can leave the required drivers unbound.
    Caught before deployment. Fix: add the uniquely named clock/AFI nodes and
    encoder directly to the existing amba bus, matching
    [AMD's KR260 overlay layout](https://github.com/Xilinx/kria-apps-firmware/blob/main/boards/kr260/bist/kr260-bist.dtsi).
    The updated overlay compiles without dtc warnings. The deployment helper
    checks driver binding and enabled PL0 before probing registers; actual
    overlay loading passed on 2026-10-09, with clock/AFI drivers bound and SYS2/BUILD
    registers correct. Subsequent runs verified PL DDR and encoder hidden states
    against the integer reference at 1/12/64/128 tokens.

25. **KR260 routing congestion and 100 MHz timing (2026-10-08).** The 32-lane
    encoder fits and routes, but high LUT use causes level-6 congestion. The
    router resolved 188,091 overlaps to zero and completed routing in 66 minutes.
    Final 100 MHz setup WNS is -0.497 ns, TNS -2642.742 ns; hold WNS +0.002 ns,
    with no unconstrained internal endpoints. The build correctly refused the
    final hardware export. `validate_runtime_clock.tcl` rechecks the same routed
    design at an 80 MHz ceiling for a Linux runtime request of 75 MHz. It changes
    clock constraints, not RTL, placement, routing, false paths or hold checks.
    The XSA PS preset remains 100 MHz; Linux must apply the lower runtime clock.
    Package metadata records the requested and validated ceiling, and deployment
    refuses a live clock above the ceiling before MMIO. Lower-clock validation
    passed: setup WNS +2.003 ns, hold +0.002 ns, no setup/hold/pulse-width failures
    and no unconstrained endpoints; all 176,601 routable nets are routed with zero
    errors. Final XSA/bitstream export and bootgen/dtc packaging passed, producing
    `build/v2/kr260-app.tar.gz`. Final SDT IDs/AFI/register settings match the
    overlay, with the explicit lower runtime clock. App loading and register/clock
    checks passed on 2026-10-09: SYS2 0x53595332, BUILD 0x20801804, live clock
    71,428,571 Hz. Image readback and 1/12/64/128-token encoder checks subsequently
    passed bit-exact; 128 tokens takes 1,386,238 encoder clocks / 19.41 ms;
    do not treat the 100 MHz operating point as passing.

26. **Silent KR260 evaluation and kernel CPU stalls (2026-10-09).** The owner
    observed no evaluation output for four minutes, then serial-console RCU CPU2
    stall and timer/starvation warnings. Exact cause is unconfirmed; the complete
    stack and active app/process state are not available yet. The kernel log's
    timestamp is about 472 seconds after boot, making a recently restarted board
    a plausible context. Do not infer OOM or a bad model from the warning text.
    Inspection found the client probed MMIO ID before confirming the app, drivers
    and clock. A polling timeout only protects code reached after those reads;
    it cannot recover a CPU blocked on a register bus transaction. Fix:
    `kr260_runtime.py` checks live overlay/firmware name, manager state, bound
    fclk/AFI drivers, enabled clock within the app timing ceiling and exact no-map
    reservation before /dev/mem opens. The client then checks the full DDR image
    before RUN, uses the live clock, and prints flushed startup stages. Tests
    cover absent app, disabled/overspeed clocks, missing AFI/reservation, no-MMIO
    on rejection and a missing model; 46 relevant tests pass. The evaluation
    bundle was rebuilt with the same frozen suite hash. Recovery and guarded hardware execution subsequently passed: app reload,
    exact DDR readback, 1/12/64/128-token checks, then 300/300 frozen evaluation
    cases. The imported report matches Nexys hidden states, predictions/logit
    hashes and score counts on every case. No stalls recurred during this run;
    the original stall cause remains unconfirmed. Do not unload PL while a
    stalled MMIO process is active. Reboot recovery requires reloading app and DDR image.

27. **MiniLM HWU evaluation scoring raised KeyError (2026-10-09).** After
    exact image readback and 1/12/64/128-token hardware checks, the frozen
    run completed ATIS and CLINC then failed on the first HWU slot prediction.
    The client hardcoded slot labels for ATIS/SGD, omitting HWU. Fix: use
    `heads.labels[p.head]` for the active slot head. Regression tests exercise
    intent/slot counts for ATIS, SGD and HWU: 10 suite tests pass. Replaying
    all 350 frozen hidden states through CPU task heads/scoring completes;
    this validates scoring, not new FPGA execution. A client-only patch and
    refreshed full MiniLM archive were transferred. Hardware rerun completed
    350/350 bit-exact; imported report matches frozen hidden states, task-head
    logits/predictions and CPU scoring counts. Mean encoder 15.139 ms at
    71,428,571 Hz. This client scoring issue is resolved.

28. **L12 checkpoint replacement failed on Windows (2026-10-09).** Near the
    end of epoch1, checkpoint.tmp was serialized successfully but replacement
    of checkpoint.pt raised WinError5 in the OneDrive checkout. Exact lock
    source unconfirmed. Recovery validated both files and selected the newer
    epoch0/batch3000 candidate, preserving the older batch2800 checkpoint.
    Copied it with SHA256 readback to local AppData/SysoneCheckpoints and resumed
    with the same training arguments. Added --checkpoint-dir and bounded retry
    of atomic replacement; permanent failure retains previous and new candidate.
    Tests cover ordinary replacement, transient lock and permanent lock with
    both recovery files preserved: 3 pass. New progress log is
    build/v2/eval/minilm-l12-v1-resume.log; training and final validation pending.

29. **KR260 CPU answer generation misses latency and quality targets (2026-10-10).**
    Pinned llama.cpp/Qwen3-0.6B Q4 and Q8 both run on four Cortex-A53 cores,
    but 0/16 requests produce first words within one second. Median first word
    5.138s(Q4)/5.046s(Q8); uncached prompt processing accounts for almost all
    delay. Q8 is slightly faster in this build despite higher RAM use.
    Both models contradict yes/no negation and fail the supplied technical
    context probe. Open acceptance failure, not a deployment crash. See
    build/v2/eval/kr260-generation-review.md and summary.json. Larger capacity
    alone cannot be assumed to meet latency; decoder acceleration or a separately
    chosen backend needs new measurements. Current FPGA encoder cannot execute
    Qwen's causal decoder. No backend switch or FPGA generation claim made.

## Matched bert-mini hardware results (2026-10-09)

Matched hardware evaluation completed and compared (2026-10-09): both boards
passed 300/300 integer-reference checks. Case-by-case token IDs, hidden-state
hashes, task predictions/logit hashes and accuracy counts match. KR260 runtime
preflight and DDR verification passed after recovery, app reload and model reload.
Mean encoder time: Nexys 10.072 ms at 75 MHz, KR260 5.755 ms at 71,428,571 Hz,
about 1.75x faster overall. KR260 maximum was 18.36 ms (121 tokens); mean input
length was 33 tokens. These are board counter timings, with CPU heads and host
round trips recorded separately. The 16x12 Nexys and 16x32 KR260 variants use the
same trained model and frozen seed-0 subset, not the same hardware configuration.
Reports: build/v2/eval/nexys.json, kr260.json, comparison.json and comparison.md.
Suite SHA256: 4f557315887fdc140bc7028ee329038c8ecbf6c207f97a3d5ca57a42fca7c75b.
Accuracy covers supervised task heads on 50 requests per dataset; automatic
routing and full-corpus accuracy are not scored here.

Matched 300 requests; hidden states, predictions and accuracy counts identical.

| Dataset | Accuracy | Slot F1 | Nexys encoder mean ms | KR260 encoder mean ms | Speedup |
|---|---:|---:|---:|---:|---:|
| atis | 0.980 | 0.963 | 4.295 | 3.646 | 1.18x |
| clinc | 0.920 | — | 3.960 | 3.551 | 1.12x |
| msrp | 0.620 | — | 15.839 | 7.945 | 1.99x |
| multi_clinc | 0.875 | — | 9.744 | 5.223 | 1.87x |
| sgd | 0.909 | 0.622 | 19.293 | 9.720 | 1.98x |
| sick | 0.880 | — | 7.304 | 4.445 | 1.64x |

MiniLM KR260 automatic-routing smoke tests passed (owner output, 2026-10-09):

| Request | Route / result | Encoder ms | Request ms | Host round trip ms | CPU heads ms |
|---|---|---:|---:|---:|---:|
| show me flights from boston to denver tomorrow morning | ATIS: book_flight 0.894, atis_flight 0.999; both cities/date/time slots correct | 10.80 | 10.82 | 12 | 34.3 |
| how should I build a h-bridge circuit? | out of scope; CLINC oos 0.355, no specialist head | 10.90 | 10.92 | 12 | 26.2 |
| turn off the lights in the kitchen | HWU: smart_home 0.835, iot_hue_lightoff 0.988; kitchen B-house_place | 10.59 | 10.60 | 11 | 32.1 |
| book me a table for two at an italian restaurant tomorrow evening | SGD: restaurant_reservation 0.983, ReserveRestaurant 0.957; cuisine/date tagged, party size absent, orphan I-time | 11.11 | 11.13 | 12 | 35.9 |

Live clock 71,428,571 Hz; encoder/request times use FPGA counters. CPU heads
and host round trips are separate measurements. These four requests validate
specific routing branches, not corpus-level routing accuracy. SGD routing passed on the restaurant smoke test, but its slots are imperfect:
"two" is untagged and "evening" is I-time without a preceding B-time. Model
quality must be assessed separately from the bit-exact hardware checks.
Custom-intent/document paths have not yet been checked with MiniLM on the KR260.

## Matched MiniLM hardware results (2026-10-09)

Matched MiniLM hardware comparison completed (2026-10-09): programmed the
existing 75 MHz Nexys encoder through JTAG; 23,035,904-byte MiniLM image
read back exactly in 34 s (host path). Both boards passed 350/350 frozen
integer-reference checks. Per-case token IDs, hidden-state hashes, task-head
predictions/logit hashes and score counts match exactly. Suite SHA256:
f89ce2428293503f0458e98e5f5aebe29e5be08f7f9b3c36012c7d2e5428109e.
Nexys encoder mean 26.441 ms at 75 MHz, maximum 112.36 ms;
KR260 mean 15.139 ms at 71,428,571 Hz, maximum 50.94 ms.
Overall encoder speedup 1.747x. Mean input 28.39 tokens, maximum 123.
Nexys tile 16x12, KR260 16x32; same trained checkpoint and calibration.
Host transport/CPU heads remain separate; this is a seeded 50-request-per-dataset
supervised subset, not full-corpus or automatic-router accuracy.
Reports: build/v2/eval/nexys-minilm.json, kr260-minilm.json and minilm-comparison.*.
Both boards currently have their respective MiniLM image loaded in volatile DDR.
To return to bert-mini, use that board variant's load command; files/reports remain.

Matched 350 requests; hidden states, predictions and accuracy counts identical.

| Dataset | Accuracy | Slot F1 | Nexys encoder mean ms | KR260 encoder mean ms | Speedup |
|---|---:|---:|---:|---:|---:|
| atis | 0.960 | 0.920 | 12.927 | 10.953 | 1.18x |
| clinc | 0.900 | — | 11.954 | 10.783 | 1.11x |
| hwu | 0.920 | 0.659 | 11.674 | 10.718 | 1.09x |
| msrp | 0.640 | — | 45.772 | 21.048 | 2.17x |
| multi_clinc | 0.892 | — | 25.786 | 13.650 | 1.89x |
| sgd | 0.933 | 0.449 | 55.728 | 26.236 | 2.12x |
| sick | 0.820 | — | 21.244 | 12.583 | 1.69x |

## MiniLM-L6-v3b on KR260: hardware evaluation verified (2026-10-09)

MiniLM-L6-v3b KR260 hardware evaluation verified (2026-10-09).

All 350 frozen requests match cached integer hidden states and CPU task-head predictions/logit hashes. Live clock: 71,428,571 Hz.

Encoder mean 15.139 ms; maximum 50.942 ms. Mean input 28.39 tokens; maximum input 123. Timings use FPGA counters.

| Dataset | Accuracy | Scored intents/pairs | Slot F1 | Encoder mean ms |
|---|---:|---:|---:|---:|
| atis | 0.960 | 50 | 0.920 | 10.953 |
| clinc | 0.900 | 50 | — | 10.783 |
| hwu | 0.920 | 50 | 0.659 | 10.718 |
| msrp | 0.640 | 50 | — | 21.048 |
| multi_clinc | 0.892 | 139 | — | 13.650 |
| sgd | 0.933 | 45 | 0.449 | 26.236 |
| sick | 0.820 | 50 | — | 12.583 |

50 requests per dataset, seed 0; supervised task heads. Automatic routing and full-corpus accuracy are not scored.
The 350-case MiniLM suite includes HWU and differs from the 300-case bert-mini suite; their mean times are not a matched model comparison.
Nexys MiniLM hardware evaluation subsequently passed on the same suite; see matched comparison above.

Suite SHA256: `f89ce2428293503f0458e98e5f5aebe29e5be08f7f9b3c36012c7d2e5428109e`.

Preparation completed: both image variants match on all 350 frozen test requests
(50 each: ATIS, CLINC, HWU, MSRP, multi-CLINC, SGD, SICK; seed 0), including
integer hidden states and task-head integer/float logits and labels. The embedding
head also passed a separate exact smoke comparison. Suite SHA256:
`f89ce2428293503f0458e98e5f5aebe29e5be08f7f9b3c36012c7d2e5428109e`.
Ready archive: `build/v2/kr260-minilm.tar.gz` (23,967,804 bytes). Every archived
file was read back and matched to its workspace source by SHA256; no training
checkpoint is included. Hardware MiniLM load/check/evaluation subsequently passed; see results above.

Compiled the existing checkpoint with reused calibration into
`export/v2/image/minilm-l6-v3b-kr260/`: 23,087,104 bytes at `0x60000000`,
tile 16x32, hidden 384, six layers, 12 heads of dimension 32, FFN 1536,
128-token window. The existing deployed BUILD 0x20801804 accommodates it;
no bitstream change is needed. Image and request/result buffers fit the
64 MiB reservation (maximum result end `0x6170d000`). CRC verification passed.
Image SHA256: `0cf8d009e9fc55367a3fa53e853a9b498227daf91aa669206e4389ec5931eea1`.
The original 16x12 image had zero hidden/head mismatches over 1,400 chains
against IntEncoder. The prepared suite checks both image variants on the
same seed-0 test requests, including HWU; FPGA verification must follow loading.

Reran corrected router statistics (problem 21): CLINC threshold remains 0.480;
HWU threshold changes from 0.515 to 0.480. Both variants carry the same decision
rule. The CLINC+HWU router rejects 29.2% of CLINC OOS test queries and accepts
96.97% of HWU test queries, compared with 70.3% OOS rejection using CLINC alone.
These CPU integer-reference routing results differ from supervised head accuracy.
The relocated image's CPU flight-request smoke test selected ATIS and correctly
tagged both cities, departure date and time. Measured MiniLM FPGA latencies are recorded above.
Transfer/load/check/evaluation commands are in `scripts/v2/kr260/README.md`.

## Scaling across boards

KR260 MiniLM-L12-v1 hardware evaluation (2026-10-10): report
`build/v2/eval/kr260-minilm-l12.json` completed350/350 bit-exact cases at
71,428,571Hz. Report suite/image/token/hidden hashes verified against the frozen
suite. Identical requests and token IDs to the L6 evaluation. Encoder mean29.9905ms,
p95 62.6209ms,max100.6720ms (123tokens), compared with L6 mean15.1387ms.
L12 accuracy: ATIS.980,CLINC.920,HWU.920,MSRP.800,multiCLINC.94245,
SGD.93333,SICK.740. Slot F1: ATIS.94444,HWU.77108,SGD.48889. SICK
regressed from L6.820; subset scores do not establish universal improvement.
Summary `build/v2/eval/kr260-minilm-l12-summary.json`. L12 Nexys, automatic
routing regression and generated answers are not validated by this report.

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

KR260 RTL optimization now includes optional registered MAC operands
(`MAC_INPUT_REGISTERS=1`) and synchronous BRAM softmax tables
(`EXP_TABLE_IN_BRAM=1`). Both preserve bit-exact BERT-mini and MiniLM-L12
results across eight request lengths; the BRAM option preserves LUT-variant
cycle counts. Established profiles retain zero defaults. Full routed timing,
area measurements and board comparisons determine which candidate to adopt;
see `OPTIMIZATION.md` for evidence and reproduction commands.

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
5. Full encoder, heads, v2 request/reply protocol and host client: done in simulation
   (whole requests through the RMII pins bit-exact, heads on the host) and **on the
   board (2026-10-06)**: the encoder bitstream meets timing (WNS +0.187 ns) and
   bert-mini-slots4 runs bit-exact for 1-128 tokens, 39.35 ms of encoder at 128 tokens
   (board clocks). Next: `run` / `eval --verify` on real text, then MiniLM-L6.
6. KR260 port: AXI memory adapter (done), the encoder as a PL block with AXI4-Lite
   control and the ARM-side link (done in simulation, TILE_OUT 32); next: requantiser
   lanes, the block design, the board.


### Offline KR260 address and H1024 candidate (2026-10-12)

The experimental PIPELINED_DOT profile now uses registered attention head,
query-group/query-row and key-row cursors in place of per-read runtime products.
Indices and cursors advance together on FSM transitions, so buffer latency and
issue tags retain their schedule. The default profile retains legacy addresses.
53 frozen KR260 cases, two Nexys cases, stalled output and ten focused address
profiles pass. Existing-image cycle counts match the previous candidate in the
frozen simulations. These are numerical checks, not hardware timing evidence.

`preflight_dot4_large_candidate.ps1` synthesizes an isolated H1024 configuration
after base and larger-profile numerical/source-hash gates. It preserves T128 and
head dimension64. Resource fit, timing and eventual board validation are required
before raising deployed limits; no bitstream is exported by this preflight.
The deployed H768/125MHz app and its model-memory reservation remain preserved.


### Registered KR260 request arbitration (2026-10-12)

The experimental PIPELINED_DOT profile enables one elastic read descriptor
and one elastic write descriptor in axi_memory_port. Valid, address and beat
count are captured together; reset clears validity. Core arbitration sees stored
requests, isolating upstream write readiness from current encoder read validity.
Default REGISTERED_REQUESTS=0 retains the direct interface. Burst splitting and
write-data handshakes are unchanged; a newly arriving descriptor adds a stage
when it cannot be hidden behind a preceding operation.

53 frozen KR260 cases, Nexys, stall/reset/concurrent AXI traffic and low/high
burst tests pass. Small OOC synthesis confirms one valid-to-write-ready path
in direct mode and zero in registered mode. Full candidate timing and eventual
hardware validation are separate gates; no 300MHz closure is established.
