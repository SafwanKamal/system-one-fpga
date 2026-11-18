# Counter300: separate telemetry timing candidate

User authorization: implement the measured performance-counter timing fix in a separate candidate, verify exact counts and unchanged outputs/cycles, then synthesize and place. Preserve the qualified 200 MHz baseline. Typed timing-guaranteed outputs are the primary architectural priority; see [the ARM/PL assurance plan](2026-10-15-typed-timing-contract-plan.md).

## Change and preservation boundary

`rtl/v2/candidates/counter300/` derives from the sealed locality300 candidate. Its manifest pins the parent manifest and all 25 RTL source hashes. Relative to its parent, only `platform/kr260/kr260_encoder.sv` changes and `common/performance_telemetry.sv` is added. The qualified 23 RTL sources, qualified frozen snapshot, numerical fixtures, packages, recovery and previous rejected implementation remain intact. Existing runtime/package guards are unchanged and reject the experimental feature family `0x5397ffff`. No candidate package or deployment is produced.

The measured parent path was linear load-state decode through AXI request control into 32-bit outstanding-beat arithmetic. The new module captures signed burst-minus-transfer deltas and event inputs before applying them to outstanding-beat/event counters. This removes the global issue/ready decode from the same-cycle 32-bit counter update. It has **no control feedback to encoder or AXI**. Arithmetic, request launch, AXI transfer timing, output data and core cycle counters are unchanged.

Read deltas use signed 10 bits (-1 through 256); write deltas use signed 17 bits (-1 through 65535). They are sign-extended into the modulo-2^32 outstanding counters. Diagnostic events that depend on outstanding beats are evaluated with the correspondingly delayed ready/valid flags and the old outstanding count. This preserves the original event ordering; simply delaying ready/valid while testing the undelayed outstanding count would be incorrect.

## Snapshot semantics

Telemetry observes the original busy-qualified event stream one cycle later. The last sample drains on the first idle clock edge. Counters must not be treated as a completed snapshot before that drain. The experimental AXI-Lite register at `0x70` reports:

| Bit | Meaning |
|---|---|
| 0 | telemetry sample pending |
| 1 | normal core DONE latched and telemetry snapshot ready |
| 31:2 | zero |

Normal counter addresses remain unchanged. A new RUN clears counters and pending telemetry together, matching the original reset-on-RUN semantics. The consumer must own the encoder exclusively and await bit1 before a final snapshot. An independent deadline result can precede core completion/drain and must not be confused with a completed telemetry snapshot. This interface change is isolated in the experimental feature family.

## Equivalence checks and preserved failed attempts

- `performance_telemetry_tb.sv` compares all ten counters and both outstanding-beat registers against independent original equations at the documented one-cycle observation offset on every checked edge. It exercises maximum bursts, simultaneous issue/receive, negative deltas, busy drain, restart/reset and modulo-2^32 rollover. The unit run passes 12,014 edges.
- `run_counter300.sh` stages candidate RTL and original vectors/testbench in WSL temporary storage, with Verilator assertions enabled. It runs the same 50 cases as the parent and checks snapshot readiness passively.
- `build_counter300.py` refuses synthesis until all numerical words/statuses, request/core cycle counts and **all 500 performance-counter values** match the frozen qualified regression. It also checks frozen fixture hashes, compiled candidate hashes, directed telemetry source/test hashes and deadline/quarantine checks.
- The first integration attempt in `build/v2/counter300-regression/` is preserved with status143. An added AXI-Lite snapshot read shifted the global random-stall phase between cases. Its first request matched; later outputs remained correct but cycle counts were incomparable. The process was stopped and the testbench instrumentation changed to a passive readiness check. The candidate RTL did not change. Successful comparable evidence belongs only under `counter300-regression-v2/` after it completes.
- Host contract/candidate/timing tests passed 67 cases, with evidence in `build/v2/counter300-contract-tests-final.xml`.

The previous candidate and tests remain untouched. Changes to source seals or test stimulus require new evidence rather than replacing a successful or failed run in place.

## Physical experiment and decision rule

`build_counter300.py --profile encoder384 --stage synth` uses the same board setup, lane widths, H384 capacity, 300 MHz target and default tool flow as the parent. Mapped telemetry delta-register cuts, query replicas, MAC selectors and supervisor state must survive synthesis. A hash-bound synthesis review is required before one diagnostic placement. The tool cannot route, write a bitstream, export, package or deploy.

Inspect the old performance-counter path and the new worst paths, not just overall WNS. The unchanged route admission remains **at least +0.5 ns placed setup**. Setup/hold closure and hardware qualification remain separate. A tool exit code of zero only says the tool flow completed. Frequency diagnostics rescale timing constraints on the same placement; they are not independently optimized or routed designs.

Physical progress and final decision will be recorded below and in HANDOFF.md. Do not launch duplicate work or modify sealed candidate sources used by an active build.

## Completed verification and current build

The full comparable regression completed: all 50 cases and all 500 performance-counter values match the frozen reference exactly, with unchanged outputs and request/core cycles. Verilator assertions, passive snapshot readiness and independent deadline/quarantine checks pass. The [validation receipt](2026-10-15-counter300-validation.json) records preservation and source hashes. It also confirms the earlier candidate's hash-bound placement evidence is unchanged.

H384 300 MHz synthesis completed in `build/v2/counter300-encoder384/`. All 27 telemetry delta registers survive, along with 512 query-data FFs, 128 local MAC selects and 70 supervisor FFs. Synthesis uses 67,627 LUTs and 53,266 FFs (+29/+39 versus the matched parent), with BRAM46, URAM18 and DSP579 unchanged. Worst synthesized setup remains -0.591 ns and hold -0.087 ns, led by the same layernorm-address path. The diagnostic placement and reporting-only endpoint audit have also completed.

The separate typed-publication prototype's successful simulation and limitations are recorded in [its receipt](2026-10-15-typed-publication-prototype-validation.json), with [pinned ARM primary artifacts](2026-10-15-typed-arm-sources.json). It remains independent of this counter candidate.

## Final placement and endpoint audit

| Diagnostic clock | Setup slack | Hold slack |
|---|---:|---:|
| 200 MHz | +0.886 ns | -0.071 ns |
| 250 MHz | -0.114 ns | -0.071 ns |
| 300 MHz | -0.781 ns | -0.071 ns |

These are unrouted timing analyses of one 300 MHz-targeted placement, with the same clock-rescaling diagnostic as the parent; they are not three separately optimized builds or new qualified clocks. The placer first estimated -0.708 ns; the final timing report supersedes that estimate. Setup at 300 MHz improves 0.230 ns from the matched H384 parent's -1.011 ns. This is one implementation comparison, with placement perturbation and no hardware measurement; it does not establish a repeatable Fmax distribution or an encoder throughput speedup.

Placed resources are 63,568 LUTs, 52,157 FFs, 78.16% occupied CLBs, 46 BRAM tiles, 18 URAM and 579 DSPs. Physical optimization can change register counts, so the placed FF difference is not the logical cost of the new stage. The worst full-design path is layernorm `root_reg[9] -> root_reg[46]`: data 3.872 ns, logic 1.963 ns, estimated route 1.909 ns, 15 logic levels including 12 CARRY8 elements.

The separate `audit_counter300_timing.tcl` reads the original 300 MHz placed checkpoint without optimization, placement, routing or checkpoint rewrite. It reports:

| Endpoint group | Registers | Worst data delay | Setup slack at 300 MHz |
|---|---:|---:|---:|
| read outstanding count | 32 | 1.275 ns | +1.852 ns |
| write outstanding count | 32 | 1.105 ns | +2.038 ns |
| registered read delta | 10 | 3.565 ns | -0.415 ns |
| registered write delta | 17 | 3.071 ns | +0.010 ns |
| event counters | 320 | 1.005 ns | +2.189 ns |

The old parent read-due endpoint had a 4.216 ns path from load-state control. Its new update stage is 1.275 ns from a registered delta. **The input work has not disappeared:** the new read-delta stage still takes 3.565 ns, from `memory_port_inst/read_address_reg[6]` to delta bit7, including 2.439 ns estimated routing. Therefore the counter update was split successfully, but the entire telemetry path is not closed at 300 MHz. A future raw-event/burst-field cut could reduce this front-end path, with a correspondingly longer diagnostic lag and exact event/snapshot alignment proof. It is deferred; do not silently introduce more stages into this sealed candidate.

`build/v2/counter300-encoder384/placement-review.json` binds final reports, checkpoint, audit and source manifest and explicitly **rejects 300 MHz route admission**. The unchanged +0.5 ns placed setup threshold is not met, and hold is unresolved. No route, bitstream, package, deployment or new board qualification followed. All requested simulation/synthesis/placement work is complete; no process remains active.

The next priority is the typed-output protocol and bounded ARM bridge at 200 MHz, as described in the assurance plan. Further root-arithmetic or telemetry-front-end Fmax work is recorded as future work rather than launched automatically.
