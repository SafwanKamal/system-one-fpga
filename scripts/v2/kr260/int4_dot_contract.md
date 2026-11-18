# Experimental pipelined INT4 dot primitive — October 13, 2026

int4_dot16.sv consumes sixteen raw signed INT8 activations and sixteen signed
two's-complement INT4 weights. Weight packing matches int4_reference.pack:
consecutive values occupy low then high nibbles. It returns a signed INT16 sum.
Product/pair/quad/octet/final widths are 12/13/14/15/16 bits, with explicit signed
extensions. Full raw-byte products span -1016..1024 and sixteen-term sums span
-16256..16384, so the positive -128 * -8 edge requires the final sixteenth bit.
The existing model reference still requires symmetric activations [-127,127];
supporting raw -128 arithmetic here does not change that calibration contract.

Five registered arithmetic stages with global elastic backpressure preserve
packet order and stall the complete pipeline if a valid output cannot advance.
Input ready is suppressed during reset; reset cancels pending valid results.
No output is meaningful without out_valid. Unstalled logic accepts one vector
per clock, but no synthesized clock target or resource result is established.

6145 vectors from the independent Python packing/matvec reference passed:
a known lane-order example, exhaustive symmetric byte/INT4 uniform vectors,
2048 deterministic random lane patterns and 16 raw -128 width-edge vectors
checked by scalar Python arithmetic. The scoreboard covers backpressure,
held-output stability, reset with pending results and packet order. A second
coverage pass drove consecutive inputs (maximum observed run 10 accepts).
Native simulation wall 0.016s. Sources/vector hashes and compile elapsed are
recorded in build/v2/int4-dot16/summary.json; first sparse-stream result retained.

This module is separate from the frozen dot7 build and deployed encoder. It
does not implement matrix accumulation, partial-lane masking, DDR streaming,
per-block scales, bias/requantization, a calibrated model or a full decoder.
This is signed symmetric INT4 packing, not GGUF Q4_K decoding. A packed
16-weight vector occupies eight raw bytes instead of sixteen INT8 bytes;
metadata, scales, buffers and total model footprint require separate accounting.
No quality, throughput or deployed memory-capacity improvement is claimed.

Next gates after the active heavy route: isolated synthesis/inference review,
selected model quantization/calibration and scale format, bounded matrix
accumulation/partial tiles, and instruction/stream integration with numerical
oracles before a full FPGA build. Preserve Nexys/default model behavior.
