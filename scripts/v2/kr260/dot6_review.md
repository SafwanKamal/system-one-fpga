# Dot6 focused optimization — October 12, 2026

Dot5-large failed legal routing (6236 node overlaps, 3h19m32s).
Failed routing reached south congestion level 6 and east level 5;
8262 signals failed to route. Preserve its checkpoints and frozen RTL.

This candidate batches three changes before any complete implementation:

* Residual saturation/add uses signed 26-bit comparisons, a signed 16-bit
  clamped skip and a signed 17-bit sum. The sum range is [-65535,65534].
  No added stages or changes to valid/address alignment.
* Dot reduction uses 18/19/20/21-bit levels, capped by the requested WIDTH.
  Full signed 17-bit products and WIDTH-bit modular semantics are preserved.
  Four clocks of latency and initiation interval one remain unchanged.
* Experimental LOCAL_ACCUMULATOR_CONTROLS=2 uses dynamic writes to distributed
  RAM, with two asynchronous reads and existing P-1 local tags. Mode 1 retains
  localized flip-flop banks; mode 0 retains the Nexys legacy structure.
  Data is unreset, as before; first-key initializes each consumed accumulator.
  The experiment targets the mux/write-enable/storage structures present in
  failed-route overlap examples. RAM inference, resource savings and physical
  improvement must be measured; none is presumed from the attribute.

Focused arithmetic checks passed:
49152 residual writes compared against the frozen original engine, including
all shift encodings, saturation endpoints and randomized residual/input data;
4096 consecutive dot vectors at every WIDTH 1..32, full signed-17-bit extrema
and random values. These tests check unchanged tags/control and pipeline latency.
Evidence: build/v2/rtl-dot6-arithmetic/{residual.log,dot.log,source-sha256.txt}.

The base numerical gate passed: 32 KR260 cases (wide/L12/control/one-word/H1024
boundary), 2 Nexys cases and 64 streamer chunks. The 21 extra H1024-profile cases
also passed: 53 KR260 cases total. Encoder cycle counts match dot5 in every
base and large profile. Both source/hash summary gates passed. All jobs finished.
The 17 tested RTL sources are preserved in build/v2/kr260-opt-dot6-large;
completion-status.json is numerical_ready, not full implementation qualification.

Measured OOC utilization (CLB LUT counts account for LUT combining):

| Module | CLB LUTs old/new | Registers old/new | Estimated setup ns old/new |
|---|---:|---:|---:|
| Residual | 3434 / 2978 | 864 / 864 | -0.327 / +0.185 |
| Dot, 32 lanes | 9088 / 8512 | 9472 / 8992 | +2.400 / +2.454 |
| Attention, 4 lanes | 8996 / 8944 | 10099 / 4108 | +0.374 / +0.374 |

Residual CARRY8 count fell 264 -> 208. The attention experiment inferred RAM;
memory LUT use increased 200 -> 3144 while total CLB LUTs slightly decreased.
Both attention profiles use 13 actual DSP tiles and 6 BRAM primitives. Broad
get_cells DSP* includes internal DSP subcells on Vivado 2025.2; use utilization
DSP tile counts rather than the raw 117-cell inventory. Register reduction is
59.3% at four lanes; do not extrapolate these totals to a placed 32-lane design.
The new SLICEM demand is a physical-placement consideration, despite available
device capacity. OOC estimates and RAM inference do not establish route closure.
Evidence: build/v2/dot6-ooc-summary.json and both dot6-*-ooc directories.

Full numerical evidence uses the frozen snapshot recorded in
build/v2/rtl-dot6-check/snapshot.txt (accumulator mode 2, pipelined dot enabled).
Both focused synthesis comparisons completed successfully, one Vivado process
at a time. No complete encoder synthesis, placement, routing or board deployment
has started. These results support keeping the width reductions and further
reviewing RAM banks before spending another complete implementation run.

Additional cheap targets before a full build (not implemented yet):
* The new residual worst OOC path is row_words_reg -> s_address. A sequential
  word cursor can replace token*row_words; for legal even row_words, x_address
  equals a_address>>1. Check instruction restart, row transitions and tags.
* Attention accumulation and output phases do not intentionally overlap. Review
  whether one shared asynchronous read address can replace the current two RAM
  read ports, reducing memory-LUT use. Prove the last weighted update drains
  before the first context read; register local phase controls to avoid creating
  a new global selector fanout. Do not edit RTL under the current frozen tests.

The deployed KR260 app and boot memory are unchanged; last hardware validation
remains the 125 MHz memory app with 350/350 frozen L12 cases bit-exact.
