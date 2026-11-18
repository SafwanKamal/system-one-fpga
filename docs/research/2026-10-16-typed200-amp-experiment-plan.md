# AMP investigation: ranked implementation and qualification plan

2026-10-16. Preparation only. Companion report:
`2026-10-16-typed200-amp-feasibility.md`; machine policy draft:
`2026-10-16-typed200-amp-policy-draft.json`; allocation/enforcement matrix:
`2026-10-16-typed200-amp-ownership-matrix.csv`.

Effort estimates are relative engineering judgments, not delivery dates:
S = narrow host/software change; M = several interacting components;
L = hardware/boot/security composition and target qualification. Benefit/risk
rankings are informed by source evidence; physical outcomes are unmeasured.

| Order | Experiment/change | Evidence strength | Expected benefit | Effort | Principal risk | Required success/stop evidence |
|---|---|---|---|---|---|---|
| 0 | Pin actual board/kernel/DT/ATF/PMU, PS clock graph and wired network controller using read-only inventory when target work is authorized | High need: actual HWH disables all GEM; actual running kernel unpinned | Prevents building an AMP boot on the standalone PS configuration | S–M | Wrong network/MIO or boot assumptions lose SSH | Hashes/versions and full resource map; do not boot/reconfigure to discover them |
| 1 | Define executable ownership manifest and per-API/resource/argument policy; new Linux-compatible PS configuration | High: frozen reset/PMU rules explicitly conflict with Linux | Makes the AMP preconditions concrete and reviewable | M–L | Shared PLL/reset/register aliases bypass a partial allowlist | All paths assigned; Linux leaf operations vs protected parent resources; unknown operation denied; no placeholder mailbox address becomes deployable |
| 2 | Requester-aware filter protecting CSR, permit and its own configuration before metadata loss | High: 16-bit USER upstream, 0 downstream in actual HWH; AMD XAPP1353 mechanism | Required for enforced R5 control and trusted numerical proposals while Linux runs | M–L | AW/W mixing, ID decode errors, bypass after reset, timing loss | Source-level assertions and protocol/fault tests: non-R5 effects absent, allowed R5 behavior correct, bounded errors, all lock/reset states explicit |
| 3 | Protect R5 TCM/global aliases and inference DDR; boot carveouts; Linux DMA restricted to private buffers | High: actual shared HP0 DDR and external TCM aliases | Preserves numerical inputs/state despite Linux/GEM activity | M–L | No-map mistaken for firewall; a DMA/alias/secure path remains open | Negative access tests for A53 and each enabled DMA; correct allowed accesses; no stale A53 cache writebacks; actual XMPU/XPPU coverage/locks reviewed |
| 4 | New one-shot R5 AMP startup and bounded mailbox broker, preserving exact numerical routines and six outcome values | High: frozen service parks and assumes all A53 reset | Smallest useful coexistence candidate and reproducible first functional result | M | TOCTOU ingress, IPC flood, shared cache bugs, old certificate reuse | Malformed/replayed/torn/full/backpressured input cases; private snapshot identity; no post-admission Linux dependency; exact outputs on numerical fixtures |
| 5 | Compose final guard/control/isolation proofs, then synthesize/place/route the new candidate under unchanged timing targets | High local guard evidence; new physical impact unknown | Establishes local terminal bound independent of memory/CPU delay | M–L | Inserting filtering/IPC breaks control semantics or tight 200 MHz closure | After actual admission test D=1,2 and maximum budget boundary; arbitrary memory/IPC stall, exact-D proposal priority, unauthorized ACK/proposal, reset exclusions; positive final STA and complete DRC/CDC/exception review |
| 6 | Supervised one-shot AMP boot and passive timing capture, with Linux/SSH kept configured | Target evidence missing | First actual demonstration of protected typed terminal with management alive | M | Boot policy or PS settings remove recovery; shared fault affects host | Independent serial/JTAG recovery first; staged permit-low checks; verify source identities and protected controls before admission; do not deploy until separate readiness review passes |
| 7 | SSH/GEM/DDR/IPC stress matrix; report Accepted rate and timing separately | AMD shared-resource mechanism plus actual HP0 path | Measures usefulness and exposes interference bottlenecks | M | A finite stress run mistaken for WCET proof | Matched requests/models/budgets; SSH idle/active, CPU memory streaming, full-duplex Ethernet, enabled DMA/storage, flood/replay, Linux stalled/crashed; local terminal age always within D under valid clock/reset; numerical equality for Accepted |
| 8 | AFI/interconnect/DDR regulation and R5-control service experiments | Mechanism documented; bound not discharged | Improves Accepted rate; potential basis for a service envelope | L | QoS priority/bandwidth average mistaken for maximum latency | Actual register provenance/locks, traffic envelopes, refresh/burst/outstanding limits and service analysis; compare both Linux responsiveness and inference outcomes |
| 9 | Multi-request timeout recovery or stronger Accepted-by-D claim | Not currently established | Sustained useful service | L | Timeout returns before AXI drain; buffer reuse corrupts epochs; unbounded ARM/MMIO delay | Verified drain/reset/new-session protocol; buffer ownership through outstanding responses; composed successful completion bound; retain conditional outcome guarantee if assumptions cannot be discharged |

## Recommended first candidate

Implement a new **one-shot AMP** configuration after steps 0–4 are reviewable.
Linux/SSH runs on one A53; R5_0 alone writes authoritative inference registers;
Linux sees only a bounded request/status interface. Preserve frozen v5 and the
dedicated sole-R5 boot chain. Do not call a software-only removal of A53/GEM
reset checks this candidate's ownership proof.

The first qualification objective is one valid typed terminal under controlled
Linux/network load. Include a deliberate short-deadline run and a budget that
allows a real Accepted inference in the measured workload. Test those as
different claims. One successful terminal that is always Deadline demonstrates
timeout handling, not useful classification.

If desired, a cooperative Linux/remoteproc bring-up can precede enforcement,
but label it **diagnostic, Linux trusted, no exclusive-owner guarantee**. Standard
remoteproc may load/reset/stop R5/TCM and standard FPGA manager may reconfigure
PL; deny these effects before claiming protected operation. Do not unbind
remoteproc after launch without reviewing its power/TCM release callbacks.

## Explicit measurements and acceptance rules

Record board/boot/kernel/DT/PMU/ATF/firmware/bitstream/model/policy hashes, fresh
session, captured input bytes, request ID, shape, budget, workload, clocks and
instrumentation identity for every run. Compare from the **PL admission edge**,
not the SSH command timestamp or when R5 first observes ACTIVE. D=1 can expire
before ARM observes ACTIVE. Store local outcome/label/PL age, core/request
cycles, drain evidence, R5 phase counts and later Linux/client timestamps as
separate fields.

For every Accepted result, require exact numerical and label agreement with
the frozen reference, complete successful matching epoch and live drain. For
failure variants require canonical empty payload. For local deadline runs,
measure the local publication edge with a reviewed passive observer, not a
breakpoint or a delayed SSH read. Report SSH latency distributions as transport
measurements, never use a network timestamp as the PL publication time.

For stress, use the same input set, budgets, timing definition and traffic
envelope on both candidates. Linux may change memory-response timing, so a
different external core-cycle count is expected; do not require equal cycles
across unmatched bus traffic or advertise a speedup from such runs. Prove or
regress numerical/cycle correspondence under **matched** responses when
separating filter/control changes from workload interference.

Do not use a finite maximum as a universal service bound. Accepted-by-D needs
an explicit bound on encoder, memory drain, hidden copy, integer head and
proposal commit under the permitted interference. The hard typed terminal
claim can remain useful before that successful-completion claim is justified.

## Stop gates

- No target deployment is authorized by this investigation.
- Retain independent recovery for first AMP boot; SSH coexistence does not make
  Ethernet a guaranteed recovery channel after a shared PS/DDR/PL fault.
- Do not reuse the current standalone PS initialization for a network boot.
- Do not reuse a timeout-owned buffer or reset a bus with live outstanding
  traffic merely because the local Deadline record is available.
- No production Linux permission, scheduling option, no-map carveout, QoS value
  or historical proof receipt alone satisfies hardware exclusivity or WCET.
- Any missing physical or source-identity gate leaves readiness false.

This plan intentionally leaves implementation experiments unrun. The current
request authorizes investigation and preservation, not promotion of an AMP
deployment. The next concrete engineering work is steps 0–4 in a separate
candidate; it need not revisit the completed 300 MHz probes or change numerics.
