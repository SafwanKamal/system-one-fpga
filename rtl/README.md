# Phase 2 RTL — sysone_core

SystemVerilog for the whole on-chip inference path: raw text bytes in, calibrated
integer logits and a decision out. The MLP head is built from Genome-Classifier's
`dense_engine`, and the code follows that repository's conventions.

**Bit-exact against the Phase 1 golden model on all 5,500 CLINC150 test utterances
plus 15 edge cases**: every table index, all 832,765 logits, every decision. The
same holds end to end through the RMII pins: requests in as raw Ethernet frames,
results out as frames, decoded by the host's own decoder.

```
bytes -> feature_generator -> embedding_bag -> classifier_head -> logits, argmax, top two
         FNV-1a words,         16384 x 64 INT4   2 x dense_engine (PIPELINED, 64 lanes)
         1/2/3-grams,          sum, Q16 mean,    2 x channel_requantizer
         char 3-5 grams        pool_gain         logit_argmax
```

## Layout

```
rtl/
  sysone_top.sv             Nexys 4 DDR top: clocking, PHY reset, LEDs (Genome's arrangement)
  sysone_ethernet_core.sv   RMII in -> request parser -> sysone_core -> result frame -> RMII out
  rmii_RX.sv                RMII receive: preamble/SFD strip, CRS_DV toggle, falling-edge capture
  ethernet_RX.sv            FCS and minimum-length check (uses ethernet_CRC32)
  ethernet_RX_buffer.sv     holds a frame until its FCS is known; mirrors ethernet_TX_buffer
  sysone_request_parser.sv  MAC/EtherType/version filter, feeds the text to sysone_core
  sysone_result_packet.sv   result frame: class, top two logits, all 151 logits
  sysone_core.sv            feature_generator -> embedding_bag -> classifier_head
  feature_generator.sv      tokenizer, word hashes, n-gram order, 256-feature cap
  feature_hash_pipeline.sv  salted FNV mixes, 4 stages, one index per clock
  embedding_bag.sv          table lookup, sum, mean pool with pool_gain
  classifier_head.sv        hidden and output dense_engines, requantisers, argmax
  channel_requantizer.sv    per-channel multiplier + bias, round, clamp, streamed out
  logit_argmax.sv           running argmax and runner-up
  model_parameters.svh      generated MODEL_* constants (do not edit)
  from Genome-Classifier:   dense_engine.sv (with ROM_STYLE and PIPELINED), ethernet_CRC32.sv,
                            rmii_TX.sv, ethernet_TX.sv, ethernet_TX_buffer.sv (unchanged)
constraints/sysone_top.xdc  pins and RMII timing
memory/                     generated ROM images (scripts/rtl_pack.py)
simulation/
  sysone_core_tb.sv         bit-exact testbench for the core
  sysone_ethernet_tb.sv     end-to-end testbench through the RMII pins
  Makefile                  vectors, sim, metrics, ethernet, lint
scripts/
  rtl_pack.py               export -> memory/, model_parameters.svh, core vectors
  ethernet_vectors.py       request frames for the Ethernet testbench, and the response checker
  sysone_ethernet_client.py host tool: classify text on the board, accuracy and latency runs
  build_sysone.tcl          Vivado non-project build (board or core alone)
  rtl_metrics.py            Phase 1 metrics on the RTL's own logits
src/sysone/ethernet_protocol.py   request/result encoder and decoder, shared by all of the above
```

## Running it

```
cd simulation
make vectors    # pack the export and write the test vectors (~4 s)
make sim        # full test set + edge cases (~1.5 min)
make metrics    # score the RTL's own logits
make ethernet-vectors
make ethernet   # full test set through the RMII pins, then the host decoder checks it (~4 min)
make lint       # Verilator -Wall on the synthesisable RTL
```

To build for the board, from the repository root in a Vivado 2025 shell:

```
vivado -mode batch -source scripts/build_sysone.tcl                 # sysone_top, bitstream
vivado -mode batch -source scripts/build_sysone.tcl -tclargs core   # sysone_core alone, 100 MHz
```

Needs `uv sync` in the repository root (the Makefile runs Python through `uv run`)
and **Verilator 5.040 or newer**. Verilator 5.020 cannot
compile `dense_engine.sv` (BLKLOOPINIT), and Icarus 12 cannot elaborate it
(whole-array assignment). `make vectors` refuses to run if the export fails its
SHA-256 manifest check, if the golden model does not reproduce the manifest's
in-scope accuracy, or if any tensor falls outside the RTL's register widths.

## Results

| | |
|---|---|
| test messages | 5,500 CLINC150 + 15 edge cases |
| index mismatches | **0** |
| logit mismatches | **0** of 832,765 |
| decision mismatches | **0** |
| simulator | Verilator 5.040 |
| latency at 50 MHz (the board clock) | mean 1,692 cycles = 33.8 µs |
| latency, message end → decision | min 1,519 / **mean 1,692** / max 1,990 cycles |
| at 100 MHz | **16.9 µs** mean |

Metrics computed from the RTL's own logits (`make metrics` →
`results/rtl_sim.json`) are identical to the golden integer model: in-scope 0.9071,
OOS recall 0.4470, Brier 0.2575, ECE 0.0244, OOS AUROC 0.9202.

**The test catches real faults.** Corrupting the low nibble of one INT8 weight in
`dense_output_weights.mem` gave 5,128 logit mismatches and no decision changes. A
check on decisions alone would have passed it; comparing every logit is also what
protects calibration, which lives in the logits.

The edge cases cover empty input, punctuation only, upper case, non-ASCII bytes,
one-letter words, the 256-feature cap (30 real test utterances hit it too), more
than 256 words, a 400-byte single word, and tab/newline separators.

## dense_engine

`rtl/dense_engine.sv` is Genome-Classifier's engine with two parameters added,
both defaulting to the original behaviour. The change is on the
`dense-engine-rom-style-pipelined` branch of the local Genome Classifier repo:

* `ROM_STYLE` — `""` (tool's choice, as before), `"block"` or `"distributed"`.
  A synthesis attribute cannot take a parameter's value, so the weight ROM is
  declared in one of three generate blocks.
* `PIPELINED` — `0` is the original READ_DATA → LOAD_DATA → MAC schedule, 3 clocks
  per input. `1` overlaps the three steps: `groups × inputs + 2` clocks. The bias
  travels with its group through the pipeline, because the last MAC of one group
  shares a clock with the load of the next group's first word.

On that branch, Genome's own `dense_engine_tb` and `variant_triage_core_tb`
(1,000 bit-exact vectors) pass in both modes with unchanged results: 18 → 8 and
122 → 46 cycles. A new `dense_engine_equivalence_tb` runs both schedules side by
side against a reference model on 200 random inputs, for three shapes (including
this head's 64 → 151 × 64 lanes) and all three ROM styles.

How this head uses it, and what did not line up:

| | `dense_engine` | this model | resolution |
|---|---|---|---|
| lanes | output-parallel, one weight word per (group, input) | same | used as is |
| packing | lane 0 in the MSBs | — | `rtl_pack.py` writes that order |
| bias | preloaded into the accumulator | added after the ×M multiply (B = b/s·2²⁰, not divisible by M) | engine biases zero; `channel_requantizer` adds B |
| requantiser | `ReLU_quantizer`: one power-of-two shift | per-channel multiplier, signed logits | `channel_requantizer` |
| widths | parameterised | 10-bit pooled input, 25-bit accumulators | set per instance |
| W1 placement | — | must be LUTRAM for BRAM to fit | `ROM_STYLE = "distributed"` |
| schedule | 3 clocks per input | — | `PIPELINED = 1` |

## Ethernet

Raw Ethernet II frames, EtherType 0x88B5, as in Genome-Classifier's result packets,
with their own message types (0x10 request, 0x11 result). The protocol is
documented in `src/sysone/ethernet_protocol.py`, which the testbench vectors, the
checker and the host tool all use, so the simulation also checks the host software.

| | |
|---|---|
| request | version, type, sequence number, text length, text |
| result | version, type, sequence number, class, flags, feature count, top two logits, **all 151 logits** |
| board MAC | 02:00:00:00:00:02 (Genome's board is ...:01) |
| accepted | destination = board MAC or broadcast, good FCS, ≥ 64 bytes, EtherType, version and type match |

All the logits go back, not just the class, because calibration lives in them: the
host computes softmax(logits × s_out) and gets the calibrated probabilities.

**Receive path, new:** `rmii_RX` captures the pins on the falling edge (the PHY's
next rising edge, as RMII requires, since the reference clock is forwarded
inverted), strips preamble and SFD, and handles the LAN8720A's CRS_DV toggle at the
end of a frame with one dibit of lookahead. `ethernet_RX` checks the FCS with
Genome's `ethernet_CRC32` (a good frame leaves the fixed residue 0x2144DF1C).
`ethernet_RX_buffer` holds the frame until the FCS is known, so the parser never
sees a byte of a bad frame.

**Transmit path:** Genome's `ethernet_TX_buffer`, `ethernet_TX`, `rmii_TX` and
`ethernet_CRC32`, unchanged. `sysone_top` copies the clocking and reset of Genome's
`ethernet_test_top_hardened`, the arrangement verified on this board.

Everything runs on the 50 MHz RMII clock, so there is no clock-domain crossing. That
doubles the core's compute time to about 34 µs; moving it to 100 MHz behind a
crossing is a later optimisation.

**Simulation results** (`make ethernet`, all 5,500 test utterances + 15 edge cases
+ 9 protocol cases):

| | |
|---|---|
| frames sent | 5,524 |
| answered | 5,519 of 5,519 expected |
| ignored as required | bad FCS, IPv4 EtherType, other destination MAC, runt, Genome's message type |
| answered corner cases | broadcast destination, length field longer than the frame, 1,391-byte message, CRS_DV toggle (also on every 7th test frame) |
| payload check | every result decoded by the host decoder, FCS good, sequence numbers in order, **all 833,369 logits bit-exact** |
| end of request → first result bit | mean 41.9 µs (min 37.6, max 70.6) |
| end of request → last result bit | mean 69.3 µs (min 65.0, max 98.0) |

Add the ~6 µs the request itself takes on the wire and the board answers a typical
request in about 75 µs, wire to wire. That is half of the 146 µs Phase 1 assumed
for Ethernet transport alone.

## Cycle budget

| stage | cycles |
|---|---|
| feature generation | 1 per index (≤ 256) + ~3 per word byte for the character pass |
| embedding lookup + sum | overlapped with generation |
| pool, one dimension per clock | 64 |
| hidden dense_engine, 4 groups × 64 inputs | 256 + 3 |
| hidden requantiser | 256 + 1 |
| output dense_engine, 3 groups × 256 inputs | 768 + 3 |
| output requantiser + argmax | 151 + 3 |

The serial requantisers (407 clocks) are the largest remaining cost. Running them
with more lanes or overlapping them with the next group's MACs would bring the
mean to about 12.9 µs. Not worth it yet: Ethernet transport is ~146 µs.

## Resources

Not measured for this version: Yosys 0.33 cannot parse `dense_engine.sv`, and via
sv2v it did not finish in 50 minutes. The numbers below come from the previous
native head and from construction, and **need Vivado**:

* Block RAM: the embedding table maps to 114 RAMB36 (Yosys confirmed this for the
  252 + 4 split). W2 in BRAM is ~15.5 RAMB36; W1 in LUTRAM (~2,000 LUTs) takes none.
  About 130 of 135, leaving ~5 for Ethernet buffers.
* DSP48E1: 128 for the two engines' lanes, plus pooling and the two requantisers.
* Flip-flops: `dense_engine` holds its whole input and output vectors, about 13k
  FFs for the two engines — roughly 10% of the part.
* Ethernet: one RAMB18 each for the receive and transmit frame buffers (2 KiB each),
  and the 151 × 16-bit result logits in LUTRAM. That uses about 1 of the ~5 RAMB36
  left after the model.

## Conventions

The RTL follows Genome-Classifier: SystemVerilog, `logic`, asynchronous active-high
`reset`, `_reg`/`_next` pairs with an `always_ff` for registers and an
`always_comb` for next-state with defaults at the top, `typedef enum` states,
ROM reads in their own clocked block without reset so they infer as BRAM,
`*_inst` instance names, aligned port maps, `parameter string` file names, and a
generated `model_parameters.svh` of `MODEL_*` localparams included by the
testbench. The testbench drives on falling edges and uses `$error` / `$fatal`.

One deliberate difference: the testbench counts and reports every mismatch before
failing, rather than stopping at the first, because a bit-exact regression is
easier to diagnose from the pattern of mismatches (for example, all logits of one
class) than from the first one. Verilator stops on `$error` by default, so `make
sim` passes `+verilator+error+limit+1000000`.

## Interface

| port | dir | meaning |
|---|---|---|
| `data_in[7:0], valid_in, message_end_in, ready_out` | in | one byte per beat; a beat with `message_end_in = 1` ends the message (its data is ignored), which also allows an empty message |
| `logit_valid_out, logit_class_out, logit_out` | out | all logits in class order; probability = softmax(`logit_out` × `s_out`) |
| `decision_valid_out, decision_class_out, top_logit_out, second_logit_out` | out | argmax (first maximum wins) and the two largest logits |
| `feature_count_out, overflow_out` | out | features used (≤ 256); the message exceeded the 2 KiB word-byte buffer |
| `feature_valid_out, feature_index_out` | out | the index stream, for the testbench |

## Not done yet

* **Vivado**: `scripts/build_sysone.tcl` is written but has not been run here (no
  Vivado in this environment). Its reports answer the open questions: block RAM
  (target about 130 of 135 RAMB36), whether W1 went to LUTRAM, and timing at 100 MHz
  for the core and 50 MHz for the board. Likely critical paths: the character pass
  (LUTRAM read → FNV multiply → lane select) and the single-cycle requant
  multiply-add-clamp. Either can take a register without changing results.
* **On the board**: the receive pins (C11, D10, D9, C10) come from the Digilent
  master XDC, not from a tested design, and the RMII input delays in
  `constraints/sysone_top.xdc` are the RMII specification's 2–14 ns. First bring-up:
  LEDs 0 and 1 on, then `sysone_ethernet_client.py` with one utterance; LED 2 toggles
  per result, LED 4 lights on any bad frame.
* **Measurement**: latency with `sysone_ethernet_client.py --test-set` (host-measured
  round trip) and power with the inline USB meter.
