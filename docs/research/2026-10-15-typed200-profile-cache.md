# Bank-local full-profile validation experiment

This separate candidate targets the measured typed request-profile-to-admission
critical path. It continues directly through functional verification and full
synthesis/placement; the qualified 200 MHz design/package/recovery, numerical
baselines, reviewed R5 candidates and earlier evidence remain frozen. No board
programming or recurring automation is part of this work.

`rtl/v2/candidates/typed200_profile_cache/` changes only typed_intent_axil and
typed_intent_guard from frozen typed200_flush. Thirty-two byte-equality registers
replace the wide request-profile equality at admission. Each flag resets to the
equality of its constant byte and the zeroed shadow byte. It updates on the exact
same execute edge/address/byte strobe as that shadow byte. Commands do not clear
flags because they do not clear bank values; the existing written-byte masks
still require a fresh full frame. All 256 digest bits remain checked.

The invariant is `flag[i] == (stored_request_byte[i] == expected_byte[i])` after
every sampled edge. No extra admission cycle, delayed permission, digest
truncation, numerical change or deadline pause is introduced. Live quiet/error,
shape, session/request, epoch and ownership checks are not cached. The new guard
input is internal to this endpoint; a standalone guard supplied by an untrusted
caller is not an authorized alternative.

Full endpoint sequential equivalence passed in
`build/v2/typed200-profile-cache-formal-v3/`. Outputs, raw shadow banks, written
masks, captured AXI state, private guard history/limits and all 32 flag invariants
match the frozen endpoint at every sampled edge. Inputs include arbitrary
addresses/data/byte strobes, split AW/W arrival, response backpressure, current
core/quiet/environment values and resets. No AXI master behavior is assumed.
Assumptions are a first sampled reset, one sampled clock and two-state formal
semantics; this is not an analog/physical or whole-encoder proof.

Earlier proof attempts are preserved: v1 needed memory lowering before SAT;
v2's direct unoptimized mapping reached 2.79 million variables/7.33 million
clauses at induction two and was stopped after verifying its own process identity.
v3 uses Yosys's complete memory optimization/mapping pass, reducing that problem
to approximately 298 thousand variables/831 thousand clauses. The RTL and all
assertions are unchanged. No functional counterexample was observed.

The full integration run is `typed200-profile-cache-integration-v1`, with an
independent frozen encoder reference and every-cycle AXI/output/busy/done and raw
counter checks. A single local pipeline waits on that existing run, then invokes
synthesis, exact source/clock review, placement and native audit sequentially.
It never duplicates the simulation, creates a scheduled automation, changes the
5 ns clock or lowers the preserved +0.500 ns route-admission requirement.

The existing pipeline has completed through native placement and audit. No
routing was admitted. Functional and physical evidence follow; physical results
are placed estimates, not routed timing or a new hardware qualification.

Full integration completed: **5,400 golden words / 14 paired completions / 14
launches**, all eight T1/2/3/4/5/12/64/128 shapes and negative cases pass. Every
sampled raw counter, driven AXI/output/busy/done cycle, native completion count
and emulated publication age match. This does not measure R5 execution or WCET.
All actual WSL staged input files were rehashed against their original manifest;
no drift. The first hash-check command lost shell positional arguments and failed
before reading inputs; its log remains preserved, and direct sha256sum verification
passed. The immutable functional record fixes exact sources and proof/sim evidence;
all **1,907 prior preserved paths** remained unchanged at the functional freeze.

Full synthesis and exact source/clock review completed: **68,510 LUTs / 53,430 FF /
579 DSP / 50 BRAM / 36 URAM**, versus control 68,498 / 53,651 with identical hard
resources. This is +12 LUTs and -221 FF. Composed estimated setup is **+0.589 ns**,
hold **-0.087 ns**, versus control +0.624/-0.087 ns; no overall synthesis timing
gain. The new synthesized limit is delivery count bit7 through the AXI interface
into SmartConnect AW FIFO almost-full state: 13 LUT levels, 4.181 ns data
(1.212 logic / 2.969 estimated interconnect, 71.0%), skew -0.145 ns. These are
estimated paths, not routed measurements. Placement establishes a different
limit, so the AXI estimate alone does not justify the next RTL change.

## Completed placement and decision (2026-10-16)

The [placement review](../../build/v2/typed200-profile-cache-physical-v1/placement-review.json)
records **+0.417 ns setup / -0.072 ns hold**, confirmed by reopening the actual
placed checkpoint. The preserved routing admission threshold is +0.500 ns setup;
this candidate misses it by 0.083 ns. **Do not route or promote this checkpoint.**
Negative placed hold also requires routing and final verification in any future
admitted candidate. There is no new bitstream, package or deployment.

| Same full-design flow, 200 MHz | Placed setup / hold, ns | LUT / FF | Decision |
|---|---:|---:|---|
| Corrected-clock unchanged-RTL control | +0.371 / -0.087 | 63,331 / 53,055 | Below routing margin |
| Previous full-profile reduction tree | +0.358 / -0.106 | 63,494 / 53,173 | No whole-design improvement |
| Bank-local full-profile cache | **+0.417 / -0.072** | **63,456 / 52,768** | Best of these placed experiments; below routing margin |

All retain 579 DSP / 50 BRAM tiles / 36 URAM. Relative to the matched control,
the cache uses +125 LUT and -287 FF after placement, and improves worst setup
slack by **0.046 ns**. These are single-run implementation observations, not a
guaranteed repeatable gain or a 300 MHz result. The hardware-qualified encoder
is a distinct deployment and remains unchanged.

The [native mapping audit](../../build/v2/typed200-profile-cache-physical-v1/placement-audit/profile-cache-mapping.txt)
confirms **32 retained equality flip-flops** and **zero retained raw request-profile
bank flip-flops**. Full endpoint proof covers their replacement semantics. The
[cache-origin timing report](../../build/v2/typed200-profile-cache-physical-v1/placement-audit/profile-cache-paths.rpt)
has worst reported slack **+1.243 ns**, with 3.411 ns data delay, 15 levels and
10 CARRY8s. This supports the intended removal of the old profile-bank bottleneck;
it does not establish every other admission check has that slack.

The actual [full-design worst path](../../build/v2/typed200-profile-cache-physical-v1/place/critical.rpt)
is now `add_skip_inst/rounded_reg[6][3]` to `out_data_reg[96]/S`:
**4.219 ns data = 1.467 ns logic + 2.752 ns estimated interconnect** (65.2%),
10 levels including six CARRY8s, clock skew -0.117 ns. This is residual
requantized-skip saturation, residual addition and final saturation within the
existing output stage. Another ADD_SKIP path appears at +0.515 ns. Instruction
fanout, a non-profile request-bank check and SmartConnect paths also appear
near +0.503 to +0.509 ns. Fixing one path may immediately reveal those limits.

All 12 check-timing categories are zero; defined-clock CDC paths are safely timed.
All 39 false-path exceptions are the existing vendor XPM synchronizer/reset
exceptions. The audit retains the deadline/epoch/publication/permit structure,
finds no LUT asynchronous reset and no asynchronous FIFO reset mapping. DRC
scope remains a placed, unrouted design with routing and DSP-pipeline advisories.

## Typed-output implications and next experiments

The cache preserves the full 256-bit identity comparison and fresh-byte mask,
request/session/shape ownership, live quiet/error veto and independent deadline.
There is no added admission cycle or changed arithmetic. This is useful progress
toward implementing the typed contract at a practical clock, not evidence that
useful inference always finishes by a wall-clock deadline.

The next performance candidate should target the measured ADD_SKIP saturation
chain in a separate namespace, initially preserving all stage boundaries and
the asymmetric [-32767,32767] clamp. Prove the transformation for all signed
26-bit rounded values and all INT16 residuals, then prove the full engine's
cycle correspondence and run the full numerical/cycle regression using an
independent parent ADD_SKIP implementation. A shared modified arithmetic module
in DUT and reference would not independently test this change. Use a mapped
probe to reject a non-improvement before committing another full physical run.
Do not lower the routing gate or assume the synthesis AXI path remains limiting.

Typed-output qualification remains the first product objective. The
[follow-on plan](2026-10-16-typed200-next-experiments.md) separates the ARM/PL
ownership and timing evidence needed for that objective from later 300 MHz work.
No R5 target execution, ARM/DDR WCET, successful-inference bound, external delivery
bound or measured power has been established by this experiment.

The immutable final record is
`2026-10-16-typed200-profile-cache-validation.json`; it binds this report,
functional record, physical inputs/checkpoints/reviews, failed proof attempts,
pipeline completion and preservation hashes. HANDOFF files remain editable.
