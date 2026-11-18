# Typed200 physical composition and R5 service candidate

This continuation prioritizes typed, timed encoder outputs. The original 200 MHz
system remains the only hardware-qualified implementation. The new work adds an
isolated PS/PL composition and a linked reset-entry R5 executable. Neither is
deployed, and neither establishes successful-inference WCET or external delivery
latency. Read the [native integration](2026-10-15-typed200-integration.md) and
[corrected C/RTL transport](2026-10-15-typed200-transport-review.md) for the sealed
functional evidence inherited here.

## Physical composition and evidence

[`build_typed200_physical.py`](../../scripts/v2/kr260/build_typed200_physical.py)
creates independent `build/v2/typed200-physical-v1`. The 28 sealed RTL sources are
copied, with a new plain-Verilog
[`typed200_encoder_wrapper.v`](../../rtl/platform/typed200/typed200_encoder_wrapper.v).
The qualified encoder's large-capacity parameterization remains intact. No
qualified source, numerical contract or packaged artifact is edited.
The complete staged inventory has 29 RTL files including the added wrapper;
the actual compiled snapshot has 27. The staged legacy kr260_encoder top and
legacy wrapper are deliberately excluded in favor of the typed top/wrapper.
The validation seal checks this exact set difference and every compiled hash.

The PS preset, 128-bit HP0 DDR path and core arithmetic configuration come from
the existing KR260 project generator. Typed control is at `0xa0000000/4 KiB`;
a programmable AXI GPIO at `0xa0001000/4 KiB` supplies deployment_ready, reset to
zero. Core, GPIO, control/memory SmartConnects and PS AXI endpoints use PL0 at
200 MHz with the shared reset controller. GPIO is a trusted deployment interlock;
it does not itself implement master-access security. The PS also declares its
unused PL1 clock at 100 MHz. GPIO's out-of-context 100 MHz synthesis default is
not the composed clock constraint; top timing explicitly uses a 5 ns PL0 period.

Synthesis completed under Vivado 2025.2, xck26-sfvc784-2LV-c. Its estimate is
WNS -0.577 ns, TNS -73.576 ns (395 endpoints), WHS -0.087 ns. Resources before
physical optimization: 69,527 LUTs, 53,651 registers, 579 DSPs, 50 BRAM tiles and 36 URAMs.
The worst setup path is within the inherited encoder, from linear request-tile
state through request/beat arbitration into the system FSM enable, 17 logic
levels. Its 5.224 ns estimated data delay includes 3.791 ns estimated interconnect;
this is not evidence that the new publication gate is the limiting path.
Synthesis reports no unconstrained internal endpoints or multiple-clock pins and
eight no-clock pins. The completed placed design reports zero no-clock pins,
unconstrained endpoints, missing I/O delays, multiple-clock pins or timing loops.
The synthesis no-clock warnings therefore do not remain in the optimized placed
design; no added clock/false-path exception was used to suppress them.

Placement completes at WNS **+0.228 ns**, TNS 0, WHS **-0.103 ns** (186 hold
endpoints). Resources are 64,398 LUTs, 52,785 registers, 579 DSPs, 50 BRAM tiles,
36 URAMs. CDC reports all defined-clock paths safely timed; clock interaction
shows the single active PL0 domain. The extracted checkpoint XDC and classified
exception receipt show 39 vendor XPM reset/synchronizer false paths, with no
user-added exception through the typed gate. The placed netlist retains 192
epoch-tracker cells, 2,687 publication cells and 92 deployment-GPIO cells; the
GPIO output register and its deployment_ready fanout are present.

The worst placed setup path is now **inside publication/admission logic**:
staged contract word bank[6][2] to gate result_outcome[0] clock enable, 25 logic
levels including 21 CARRY8 cells. Its estimated 4.432 ns data delay consists of
2.339 ns logic and 2.093 ns interconnect. Thus this composition adds a concrete
typed-boundary timing target beyond the encoder's existing bottlenecks.

Placement DRC has no errors; the critical warning is RTSTAT-13 because routing
is incomplete, alongside 612 DSP input-pipeline, 6 PREG and 575 MREG advisories.
Methodology adds 64 asynchronous DSP-driver advisories and **one LUTAR-1 reset
glitch warning**. The latter is in the inherited result_streamer FIFO: its
`reset || start` signal drives asynchronous pointer resets in sync_fifo. Clean
defined-clock CDC does not resolve that warning. It must be analyzed or repaired
in a separate candidate, with flush/start/FIFO equivalence and reset/fault tests,
before stronger temporal-assurance signoff. The baseline's recorded hardware
qualification is preserved.

The hash-bound placement review approves a **timing-only route experiment** to
repair hold and assess final setup; it does not waive LUTAR-1 or approve deployment.
Routing has now completed. The **final recomputed timing report** (rather than
the router's intermediate +0.001 ns estimate) is **WNS +0.008 ns, WHS +0.010 ns,
TNS/THS 0** at a 5 ns PL0 period. All user timing constraints pass; all 12
check_timing categories are zero, CDC remains safely timed, and there are zero
unrouted nets or node overlaps. The routed default DRC has no errors/critical
warnings. DSP pipeline advisories remain, plus one RTSTAT-10 warning covering
130 nets without routable loads (the listed examples are SmartConnect reset-pipe
nets). The separate LUTAR-1 methodology issue is retained as an assurance gate;
default DRC passing does not waive it. Resources are unchanged from placement.

The final setup limit moves again: linear out_tiles[0] through encoder completion
logic into epoch complete/done_seen reset controls, 16 logic levels, 4.594 ns data
delay (1.747 ns logic, 2.847 ns interconnect). Subsequent paths feed inherited
total_clocks counter enables. Therefore a new candidate should evaluate a
**registered read-only completion/quiescence observation boundary**, with explicit
added publication latency and sticky fault/identity retention, as well as the
already identified profile-match path. Neither change may delay or pause the
independent deadline. Combining the previously verified counter fix with typed
integration is a separate candidate/regression, not an edit to these sealed inputs.

This is a narrow 8 ps setup pass under the declared device/clock constraints;
it demonstrates no 300 MHz headroom and is not board qualification. See the
[placed review](../../build/v2/typed200-physical-v1/placement-review.json),
[route review](../../build/v2/typed200-physical-v1/route-review.json),
[final timing](../../build/v2/typed200-physical-v1/route/timing.rpt) and
[physical input proof](../../build/v2/typed200-physical-v1/input-proof.json).

For context, the preserved baseline's saved placed utilization is 63,609 LUTs,
51,942 registers, 579 DSPs, 50 BRAM tiles and 36 URAMs. The new placed totals are
789 LUTs and 843 registers higher. These are descriptive counts from independent
placements: the saved baseline placement targeted 300 MHz and subsequently routed
at 200 MHz, while this candidate is placed at 200 MHz. Replacement of the legacy
CSR interface and fixed profile also changes optimization opportunities. Do not
attribute the entire delta solely to assurance logic or claim a controlled area
overhead result. A matched fresh-copy baseline build would be a separate experiment.
The original routed 200 MHz report has +0.101 ns setup and +0.010 ns hold slack;
comparing that routed result with new *placed* slack cannot establish improvement.
No new power measurement or model-quality evaluation is reported here.

No bitstream generation, hardware-manager action, package export, deployment,
remoteproc change or automation recreation occurs in these scripts.

## R5 implementation and actual ELF audit

[`firmware/typed200_r5`](../../firmware/typed200_r5/README.md) is the new privileged
service candidate. Build v8 passes strict host compilation and ASan/UBSan policy
tests, ten SHA-256 boundary-length fixtures plus the complete 33,916,928-byte model
image. The resulting image hash is
`4129baded344729ccc7ef6a3f0a2b34799280a91d88173ae1c0b197cdef8c3bb`.
The model hash occurs before admission is enabled, outside any admitted deadline.
It detects initial corruption; enforced immutability is still required afterward.

The service provisions a fresh session against a previously unconfigured PL,
validates all IDs and shape, copies IDs before admission, owns monotonic request
IDs, and checks native admission identity/shape. It waits for native completion
and live drain, copies the bounded hidden buffer, runs the frozen scaled head,
submits through corrected typed200_v2 transport and validates the authoritative
PL terminal. Duplicate sequence, invalid token, wrong identity, wrong Accepted
label, native memory fault and deadline before software observes ACTIVE are
covered by the host tests. Fault/deadline stops reuse. Non-Accepted results have
empty payloads; CPU rejections/faults are explicitly distinguished from PL records.
The host MMIO-array tests exercise service policy, not an R5 or AXI bus emulator.
Review also found that copying a C terminal structure wholesale could expose
uninitialized tail padding in shared memory. The final service explicitly zeros
the entire result and serializes its members. Tests poison the destination and
verify zero padding on normal, deadline and rejected-terminal publication. This
is additive software outside every earlier seal; the RTL record format is unchanged.

[`audit_typed200_r5.py`](../../scripts/v2/audit_typed200_r5.py) parses the actual ELF,
not just the linker script: ARM ELF32, entry zero, five TCM LOAD segments, no
writable executable segment, no unresolved symbols, and no legacy ti_mmio_*
SHA transport helpers. Both host and target compilers assert a 384-byte shared
structure with result at offset 312. The reviewed v8 executable uses:

| Allocation | R5-local location | Bytes | Evidence/limit |
|---|---|---:|---|
| Code, vectors, constants, unwind table | ATCM 0 | 16,080 | Below private 61,440-byte region |
| Banked exception stacks | ATCM 0xf000 | 1,280 | Five 256-byte stacks |
| Work BSS, including hidden buffer | BTCM 0x20000 | 49,640 | 3,608-byte work-region margin |
| SVC stack | BTCM 0x2d000 | 8,192 | Main/poll/bridge/head compiler frame sum 2,112 bytes |
| Shared command/result | BTCM 0x2f000 | 384 | 4 KiB region reserved |

The frame sum is static compiler evidence for this call chain, not a stack
high-water measurement, exception-path proof or timing bound. SHA boot frame
chain is separate. Link output and disassembly are retained in
`build/v2/typed200-r5-elf-v8`; parsed audit and vendor source snapshots are in
`build/v2/typed200-r5-audit-v3`.

Disassembly also exposes an immediate performance experiment: the sealed
ti200_copy_hidden implementation executes one volatile LDRB and STRB per hidden
byte (up to 49,152 of each), not a wide CPU copy. Those are instruction counts,
not a claim of 49,152 independent physical DDR transactions. A separately
versioned aligned word-copy path is worth testing before adding PL pooling.
Measure its bus behavior and exact output equivalence; do not modify the sealed
transport or assume bandwidth proportional to transfer width.

Startup sets banked stacks, masks IRQ/FIQ, selects low vectors, initializes VFP
and FPSCR, clears private BSS, and enables MPU regions. Code/constants are RO;
work/stack/shared and DDR/MMIO are execute-never. DDR is noncacheable shared and
MMIO Device shared. It explicitly follows AMD's normal branch-history/return-stack
policy and DBWR erratum mitigation; it does not claim prediction-independent cost.
The installed AMD 2025.2 standalone_v9_1 boot.S, MPU definitions and implementation
are snapshotted with hashes. These local snapshots are not claimed identical to
the previously inspected upstream commit.

Primary implementation references: AMD's
[RPU memory overview](https://docs.amd.com/r/2020.2-English/ug1137-zynq-ultrascale-mpsoc-swdev/Memory-Overview-for-APU-and-RPU-Executables)
documents split ATCM/BTCM layout; AMD's
[software developer guide](https://www.amd.com/content/dam/xilinx/support/documents/user_guides/ug1137-zynq-ultrascale-mpsoc-swdev.pdf)
describes RPU memory/software setup. The author-maintained
[standalone startup](https://github.com/Xilinx/embeddedsw/blob/master/lib/bsp/standalone/src/arm/cortexr5/gcc/boot.S)
provides low-vector selection, FPU initialization and ACTLR erratum handling.
This candidate implements a smaller explicit startup and still requires trusted
PS initialization, R5 split/TCM/ECC setup and reset-entry loading.

## What timing-guaranteed typed outputs mean

| Claim | Current evidence | Remaining prerequisite |
|---|---|---|
| A canonical local terminal record by budget D | Existing scoped PL proofs and deadline/fault simulation; inherited unchanged | Physical closure, uninterrupted minimum-rate PL clock/reset assumptions, deployed implementation checks |
| Accepted identifies this request/profile and matches the frozen selected-label computation | Sealed numerical fixtures, C/RTL identity interoperability and native integration; new service policy tests | Actual R5 golden-vector execution, full trusted deployment/ownership chain |
| Useful inference succeeds by D | No certified WCET yet | Bounded encoder+DDR/drain+R5 transfer/head+commit under declared contention and clock envelope |
| The application observes a result within a wall-time deadline | Not established | Bounded observation/delivery, clock minimum, reset/fault model and independent supervisor path |

The design can return DeadlineExceeded instead of Accepted on time; that is a
useful typed guarantee, not a guarantee that useful inference always finishes.
Clarify/Abstain tags are representable but this frozen 18-label ATIS head does
not implement calibrated confidence or OOS detection. Raw generated-token or
decoder throughput is unrelated to these encoder request guarantees.
The start of D is validated PL admission, not command staging, tokenization or
the external API call. A future API must expose that distinction explicitly;
otherwise a bounded admitted interval could be misrepresented as an end-to-end
request deadline. Boot/model hashing and pre-admission queuing are separate costs.

R5 is useful because it can keep the frozen head, ownership state and buffers in
TCM with no operating-system preemption in the admitted path. A53/Linux can handle
tokenization and the external API outside that boundary. The current executable
still polls unbounded MMIO/DDR: a stalled fabric can stall the R5, and a late
COMMIT can fault. The PL deadline must therefore remain independent of ARM
progress. An R5 fault report in shared memory is not a bounded external response.
The loader must establish A53/other-master exclusion; an attestation flag and R5
MPU are not substitutes for platform access protection. The shared TCM address
is R5-local and requires correct system-address translation by a future loader.

## Prioritized next experiments

| Priority | Experiment | Benefit and acceptance evidence | Effort/risk |
|---|---|---|---|
| 1 | Address derived FIFO reset in a separate candidate; increase typed-boundary timing margin | Current route passes narrowly; synchronous flush/reset candidate must preserve exact outputs, native cycles and drain semantics. Register read-only completion observation and stage profile validation with explicit latency/proofs | Medium/high; physical and reset correctness must both pass |
| 2 | Prepare a reviewable target loader/ownership profile without changing the qualified boot path | Explicit PS/RPU clocks, split TCM/ECC, fresh sessions, model/program/buffer ownership and MMIO access restriction | Medium/high; platform assumptions currently not enforced |
| 3 | Run v8 on R5 as a separate candidate after loader review | Startup/MPU/FPU readback and exact frozen golden outputs, stack canaries, typed negative cases including late COMMIT abort | Medium; target FP/bus behavior untested |
| 4 | Instrument PMU plus PL timestamps for all supported dimensions and explicit contention/fault envelope | Separate encoder, drain, hidden-copy, head and commit costs; derive a conservative service bound with architectural bus assumptions | High; observed maxima alone are not WCET proofs |
| 5 | Compare a versioned aligned word-copy path with current LDRB copy | Same bytes/labels for every supported shape, unchanged gate semantics; measured R5 time and bus transactions under contention | Low/medium; preserve ordering, alignment and memory attributes |
| 6 | Certify one narrow shape/deadline profile and independent observer | Typed Accepted or explicit failure by D plus a separately justified delivery bound; fault injection and clock/reset tests | High; depends on 1–4 |
| 7 | Evaluate bounded PL pooling/classifier assistance | Potentially reduce 49,152-byte transfer; prove exact scaled-label equivalence before changing frozen numerical path | Medium/high; reduced byte count alone does not prove lower service time |

Reaching 300 MHz remains separate. The actual placed typed-boundary path now
justifies a staged contract/identity validation candidate, alongside inherited
encoder request/control cuts. Capture the complete submitted frame before
validation to prevent bank-mutation races; define validated admission explicitly,
retain a free-running deadline, and prove canonical invalid/deadline behavior.
Any extra pre-admission or proposal stage must be reflected in the API and
service timing, never hidden by shifting the deadline counter. Compare balanced
profile-match reductions and registered validation using actual mapped critical
paths, scoped proofs, C/RTL interoperability and exact native output/cycle checks.
No 300 MHz architecture change should delay establishing the typed 200 MHz
assurance boundary, and no current timing estimate qualifies a new clock rate.

For deadline sizing, the sealed native-integration log records T128 request
count 7,966,029 and publication age 7,966,096 in its particular fixture/response
stream. The latter includes testbench-controlled proposal timing, not execution
of the R5 executable. Neither count is a board WCET or sufficient evidence to
certify D. A deployment certificate needs the complete bounded memory-service,
drain, transfer, head and commit envelope, converted using the minimum permitted
PL frequency and worst supported ARM/PL clock ratio. The host unit test's tiny
synthetic budgets are protocol tests, not recommended inference deadlines.
