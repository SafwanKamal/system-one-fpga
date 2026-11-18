# Encoder RTL optimization

The current work prioritizes KR260 computation. Nexys is a compatibility
regression target; its resource limits must not constrain optional KR260
optimizations. The working board bitstreams are retained as baselines. A faster
clock is accepted only after routed
setup **and hold** checks, followed by board validation. Simulation correctness
and a clock constraint alone do not establish a hardware speedup.

## Measured starting point

- KR260 baseline: 99,783 LUTs (85.20%), 606 DSPs (48.56%), 59 BRAM tiles
  (40.97%). The Linux deployment currently runs at 71.428571 MHz, with an
  implemented timing ceiling checked at 80 MHz.
- Its original 100 MHz report has setup slack -0.497 ns. The worst path starts
  at `instruction_reg[7]`, crosses operand selection, and ends at the shared
  multiplier DSP. Routing contributes 7.882 ns of its 10.407 ns data delay.
- Nexys uses the shared encoder at 75 MHz. Its board clock is also tied to the
  MIG interface; a faster isolated encoder does not establish a faster board.

## Candidate 1: registered multiplier operands

`MAC_INPUT_REGISTERS=1` enables one operand stage in `mac_array`, before its
existing product stage. Both plain and packed DSP layouts support it. The array
still accepts a new set of operands each clock. The default remains zero for
established builds.

`linear_engine` carries the accumulator value, token, bank and last tags through
the extra stage. The minimum spacing between short accumulation passes increases
from four to five clocks. `attention_engine` separately aligns score accumulation
and P.V writes with the new product latency and includes that latency in its
pipeline flush.

Validation completed so far:

- All 98,304 supported operand pairs, including differently signed adjacent
  packed lanes, match between packed/plain arrays at both latencies.
- KR260 BERT-mini: baseline and candidate both match all 3,504 words across
  1, 2, 3, 4, 5, 12, 64 and 128 tokens, with random AXI stalls.
- Nexys encoder layer: all 39,216 intermediate/final words match for 1 and 128
  tokens, including attention and linear instructions.
- KR260 MiniLM-L12: baseline and candidate both match all 5,256 words across the
  same eight request lengths, with random AXI stalls.
- First full KR260 routing passes its 125 MHz constraint: setup slack +0.011 ns,
  hold slack +0.010 ns, zero unconstrained internal endpoints. Qualification
  of both PL clocks at the Linux runtime rate and bitstream packaging passed.
  The board comparison below verifies its correctness and measured speed.

The Nexys isolated candidate has completed routing at a 100 MHz constraint:
setup slack -1.043 ns, hold slack +0.041 ns. It does not meet 100 MHz. Its worst
path now crosses attention address generation and activation-buffer address
selection, rather than the original instruction-to-multiplier path. This is a
useful regression observation, but the KR260 routed report will determine the
next optimization. No additional Nexys frequency work is planned in this phase.

Reproduce the full KR260 regression after generating model vectors:

```bash
python scripts/v2/kr260_vectors.py --name minilm-l12-v1-kr260 --tokens 1 2 3 4 5 12 64 128
PATH=/opt/verilator-5.040/bin:$PATH bash simulation/v2/run_kr260_pipeline.sh
```

The runner snapshots RTL, vectors and source hashes onto the Linux filesystem
to avoid GNU Make's restriction on paths containing spaces. It saves logs in
`build/v2/rtl-pipeline-check`. Verilator 5.040 or newer is required for the AXI
behavioral model.

Candidate implementation commands:

```text
vivado -mode batch -source scripts/v2/kr260/create_project_kr260.tcl -tclargs build optimized 125
vivado -mode batch -source scripts/v2/synth_encoder.tcl -tclargs both-pipe 10 0
```

These write `build/v2/kr260-opt` and `build/v2/encoder_ooc/both-pipe` respectively.
They leave the baseline build directories untouched. After KR260 routing
completes, `scripts/v2/kr260/report_clock_candidates.tcl` checks the same placement
at several clock rates without exporting or deploying hardware.

On Windows, invoke Vivado through a short path to avoid its internal path-length
limit. For example, map an unused drive with `subst S: <repository-path>` and use
`S:/scripts/v2/kr260/create_project_kr260.tcl`. The optimized project snapshots its
RTL inputs. `resume_optimized_build.tcl` can retry failed runs through the short
path; its export currently describes the 125 MHz candidate.

After timing passes, `package_app.py --optimized` includes
`validate_pipeline.sh`. On the KR260, invoke that script from the extracted
bundle. It runs the same MiniLM-L12 image, eight token lengths and frozen
350-request suite first on `sysone-v2`, then on `sysone-v2-pipe`. The client
reads the live clock for each app. Reports, app manifests and logs are kept in
a new timestamped directory; the pipeline app remains loaded after success.
The board comparison completed on 2026-10-10. Both profiles pass all eight
token lengths and all 350 frozen MiniLM-L12 requests. Suite and image hashes,
token hashes, reference hidden hashes, predictions and integer logits match;
accuracy/slot counts are identical. The candidate app manifest matches the
packaged build. Evidence is in `build/v2/eval/kr260-pipeline-125/` and
`comparison.json` alongside the original reports.

| Measure | Baseline | Registered MAC candidate |
|---|---:|---:|
| Live clock | 71,428,571 Hz | 124,999,999 Hz |
| Encoder mean | 29.9905 ms | 17.1598 ms |
| Encoder p95 | 62.6210 ms | 35.8147 ms |
| Encoder maximum | 100.6720 ms | 57.5716 ms |
| Host round-trip mean | 30.5011 ms | 17.6470 ms |

Encoder speedup is 1.7477x (42.7825% lower latency). Mean encoder cycle count
increases 0.1305%, so the gain principally comes from the higher operating
frequency. These measurements cover the frozen suite and retain separate
CPU-head timing; they do not measure generated-answer latency. The BRAM variant
is still undergoing implementation and has not been tested on board.

## Next decisions from timing evidence

The first KR260 candidate's worst routed setup path is now activation-data
distribution: `port_data_reg[0][87]` to a replicated MAC operand register. Its
7.830 ns data delay contains 7.635 ns of routing (97.5%); the source net fans
out to 160 sinks. The former instruction-to-DSP path is no longer the worst.
The next changes should reduce congestion and distribute buffer-read data
near its consumers, then measure routed timing rather than adding arithmetic
pipeline stages to a path dominated by wiring.

A KR260-specific softmax-table inference probe completed on 2026-10-10. The
current 32-lane distributed-memory form uses 3,332 LUTs (2,560 LUTs as memory)
and 512 fabric registers. A synchronous block-RAM lookup with a parallel
registered zero flag uses 768 LUTs, 32 fabric registers and 32 RAMB18E2s (16
block RAM tiles). Both forms have one clock of lookup latency. Reports and the
isolated sources are under `build/v2/ram-inference/` (`table_probe_original.rpt`
and `table_probe_block.rpt`). This suggests freeing 2,564 LUTs in that isolated
subsystem. A Verilator check passed 38,400 lane lookups, including saturated
and high-bit indices, with matching one-cycle outputs (`block-check.log`).
The option is now integrated as `EXP_TABLE_IN_BRAM=1`, propagated through the
encoder and KR260 wrapper. Its default remains zero. The lookup retains its
existing one-clock latency, including the registered zero for saturated indices.
The integrated LUT and BRAM variants match all eight token lengths for both
BERT-mini (3,504 words) and MiniLM-L12 (5,256 words), with identical cycle counts
and random AXI stalls. The default Nexys layer also passes 39,216 words.
Evidence and staged RTL hashes are in `build/v2/rtl-bram-check/summary.json`.
Reproduce with `simulation/v2/run_kr260_bram.sh` and summarize with
`simulation/v2/summarize_kr260_bram.py`; BERT vectors can be generated separately
using `kr260_vectors.py --output` to retain the L12 vectors.

The full BRAM build has now completed: 89,085 LUTs versus 93,586 for the first
pipeline candidate (4,501 fewer, including full-design optimization effects),
50,436 FFs, and routed 125 MHz setup +0.016 ns / hold +0.010 ns. The same
placement fails 150 MHz at -1.317 ns. The package is `kr260-app-bram.tar.gz`;
board correctness and performance validation remain pending. The KR260 baseline has
sufficient block RAM capacity for the experiment; Nexys does not. Build this
variant with `create_project_kr260.tcl -tclargs build optimized 125 bram`, which
writes `build/v2/kr260-opt-bram` and freezes its RTL inputs. After implementation,
`finish_pipeline_build.ps1 -Bram` checks clock candidates, validates both PL
clocks, and packages only a passing profile as `kr260-app-bram.tar.gz`.
The application is separate from both the baseline and first pipeline candidate.

1. Inspect the new worst paths and DSP register mapping. If operand-selection
   routing remains limiting, register and replicate the engine selection closer
   to the multiplier lanes.
2. If dot-product reduction becomes limiting, split the reduction into registered
   groups and extend its tags/accumulator hazard spacing together.
3. Use hierarchical area reports to identify the largest LUT consumers. The KR260
   has spare DSPs, so move suitable fabric arithmetic into DSPs where the measured
   area/timing tradeoff is favorable. Put board-specific tradeoffs behind
   parameters so Nexys can retain its established resource profile.
4. Measure cycles, live clock, encoder latency and full request latency on board
   using the same models, token counts and frozen suites. Faster compute does not
   automatically remove external-memory stalls.
5. Where buffer address arithmetic limits KR260 timing, evaluate registered row
   cursors and head offsets before adding another buffer-read latency stage.
   Preserve issue/tag alignment and test short accumulation passes as well as
   long requests.
