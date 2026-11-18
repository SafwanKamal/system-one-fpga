# Embedding requantization audit — October 13, 2026

Read-only analysis while dot7 placement runs. No RTL under test was edited.

The measured dot7 300 MHz synthesis path is instruction_reg[284] ->
embed_inst/p_term_reg, with 13 logic levels, six CARRY8 stages and 3.923 ns data
delay. Encoder wiring maps position_shift to instruction bits 280..285; bit 284
is a shift control, not the embedding multiplier. Do not optimize a presumed
multiplier path without matching the actual report.

Stage 3 currently combines dynamic rounding-bias construction, 26-bit addition,
arithmetic right shift and generic signed-64-bit saturation in one clock.
Word and position shifts remain direct instruction-register inputs. This is the
next focused optimization once the current frozen placement has completed:

1. Capture local six-bit shifts and precompute signed 26-bit rounding biases
   at instruction start, before vector/row reads. Control fields are stable for
   a complete instruction. Keep a legacy/default option so Nexys semantics and
   standalone callers are preserved. The existing four compute stages need not
   gain latency merely to precompute instruction-constant values.
2. Preserve exact 26-bit modular rounding. Shift 0 bypasses addition; shift 26
   produces a signed bias with bit 25 set; larger shifts yield zero bias once
   the literal is truncated. Do not silently replace this behavior with a wider
   mathematical rounding operation. Check every six-bit shift encoding.
3. Compare rounded terms at signed 26-bit width, then clamp to signed 16 bits
   with bounds [-32767,32767]. Word and position terms need no 17th value bit.
4. Preserve the full signed INT32 type term. Adding two clamped terms gives a
   total range [-2147549182,2147549181], which fits signed 33 bits. Use explicit
   signed extensions; do not narrow type data to INT16 based on current models.
5. Clamp the final 33-bit sum directly to INT16, retaining output masks, tags,
   four-stage valid alignment, DDR backpressure and restart/reset behavior.

Before a full build: frozen-original embedding equivalence across all shifts,
INT8 extrema, 17-bit multiplier bounds, full signed INT32 type boundaries,
non-power-of-two widths, DDR stalls and restart/reset; isolated synthesis;
then the full numerical/default regressions. Registering instruction controls
and narrowing arithmetic are proposed changes, not measured improvements yet.

Evidence: dot7 preflight-critical.rpt / preflight-timing.rpt; encoder_layer.sv
word_shift/position_shift wiring; embed_engine.sv compute stages 1..4.

## Arithmetic prerequisite verified October 13

simulation/v2/embed_requant_contract_tb.sv passed 786432 arithmetic cases in
Verilator 5.040 (native simulation wall 0.024s). Every word/position shift pair
0..63 was checked with signed 26-bit extrema, real INT8/17-bit-product extrema,
clamp boundaries and signed INT32 type boundaries, plus deterministic random
26-bit products/INT32 types. The original stage-three/four expressions agree
with precomputed signed-26-bit biases, signed-16-bit term clamps and a signed
33-bit final sum. Evidence/source hashes in build/v2/embed-requant-contract.

This only validates arithmetic transformations. No start-captured registers,
whole-engine equivalence, valid/tag alignment, DDR stalls, reset/restart or
timing/resource improvement is demonstrated. Production RTL is unchanged.
The next embedding step still needs an isolated candidate and complete engine
equivalence before synthesis. The runner uses a preserved /tmp workspace since
GNU Make rejects spaces in the Windows repository path; the initial failed
build log remains available. Do not rerun this arithmetic test unchanged.
