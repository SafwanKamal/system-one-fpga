# R5 observed-profile filter and provenance qualification

2026-10-17. A separate candidate fixes compatibility with the captured R5
metadata and passes host tests. It is **disabled and not deployed**. The
qualification found a second issue: master ID zero is shared with CCI-400 and
SMMU TCU. Neither the original MID-mask rule nor the new observed profile alone
establishes exclusive R5 origin. Full inference deployment remains unqualified.
JTAG stayed stopped; target operations in this milestone were read-only SSH.

## Concrete filter change

New source:
`rtl/v2/candidates/typed200_amp_r5_profile/typed200_r5_profile_filter.sv`.
SHA256 `200fd7866c19d432d85d1b264c27a64229f7c48e03a7c2b2f2b1f4de7ad36242`.
The sealed requester filter and every previous artifact remain unchanged.

The candidate accepts exactly complete USER values `2000` or `2800`, with
PROT exactly `001`, after both ENABLE_R5 and SOURCE_PATH_QUALIFIED are enabled
at build time. Both parameters default to zero. ENABLE_R5 alone still denies
everything. The second parameter is an integration assertion, not evidence or
a security mechanism that can authenticate the upstream by itself.

This is a deliberately narrow empirical profile: only MID zero, privileged
secure data accesses, known upper patterns. It does not open every RPU0 local
ID, assume USER zero, clear upper bits, or infer semantics for bits 11 and 13.
Poison bit 10, all unobserved USER patterns, other PROT values and other MIDs
remain denied. Transaction IDs can vary; each accepted ID is carried to the
downstream and matched to its response independently. Complete USER is
preserved unchanged on accepted transactions.

The address window remains [a0000000,a0002000), with aligned 32-bit,
single-beat, nonexclusive FIXED/INCR operations and lane-bounded strobes.
The transaction engine after the policy function is byte-for-byte identical
to the sealed engine. Its documented fairness, malformed-master stall,
independent-reset and drain limitations still apply. No timeout cancels AXI.

## What the metadata establishes

Captured hardware record remains the previous failed `target-trial-v2`; it was
not rerun or reclassified. Its workload succeeded but its old checker wrongly
required a constant full AW tag and AXI ID. New validator
`scripts/v2/amp_r5_profile_policy.py` checks the workload independently without
that constancy requirement. It returns an explicit scope of observed workload
integrity and leaves source authentication unqualified.

Actual writes have USER `2800,2000,2000,2800`, PROT 1, MID 0, IDs
`49,69,89,a9`, addresses `a0000010..a000001c`, values `52350004..52350007`
and sequence 64..67. The read observation has USER 2000, PROT 1, ID 49.
The new validator accepts the record, permits repeated or varying 16-bit
transaction IDs, and rejects other USER patterns and all captured-state
corruptions tested. This is not qualification of all possible R5 traffic.

## Source-provenance finding

AMD's UG1085 v2.5 table 16-13 assigns RPU0 MID 0000,00,AXI-ID[3:0], and
assigns MID zero to both CCI-400 and SMMU TCU. Page 63 explicitly notes the
TCU/R5_0 collision. Page 1091 places source identity in AxUSER[9:0] and
describes upper fields as available for other system attributes. Those pages
do not establish a unique interpretation of the observed bits 11 and 13.
Relevant preserved pages were hash-checked, extracted, and pages 63 and 411
rendered and visually reviewed under `source-audit-v1`.

AMD also documents the CCI/R5_0 collision as a known isolation limitation, with
alternatives involving R5_1 or the protected region's coherency policy.
These are architectural options, not changes made to the running board.
Sources: [UG1085](https://docs.amd.com/api/khub/documents/xzMsp_c5sG9J6A3u7NkJYQ/content?Ft-Calling-App=ft),
[XAPP1320 isolation limitations](https://docs.amd.com/api/khub/documents/o7UpBPL5dy8b1slLrXVABg/content).
[PG201 port descriptions](https://docs.amd.com/r/en-US/pg201-zynq-ultrascale-plus-processing-system/Port-Descriptions)
identify HPM address IDs and USER signals but do not supply a unique source
decoder for the observed ID suffix. No ID-mask authentication rule is inferred.

The host test includes an indistinguishability witness: a request bearing the
same interface signals is accepted regardless of a testbench's claimed origin.
Thus copying the profile to a CCI/TCU-labelled stimulus cannot prove exclusion.
Nonzero upper bits or an observed AXI ID suffix are not source credentials.

## Validation

Artifacts under `build/v2/typed200-amp-r5-profile-filter-v1`:

| Check | Result and scope |
|---|---|
| filter-check-v1, admission | All 524288 complete USER/PROT combinations across four gate configurations; disabled/partially enabled gates admit none; fully enabled admits exactly two combinations |
| filter-check-v1, transport | 4407 transactions; both profiles across all 1024 MIDs, all upper patterns, all PROT values, AW/W skew, stalls, denied bursts, bounds, strobes, reset and response faults |
| Measured metadata replay | Four observed AW records and one AR record pass the enabled candidate with recorded IDs; synthetic data/cache/QoS for this transport harness |
| APU secure/profile mutations | 32 read/write cases remain denied even after changing PROT and upper fields to admitted values |
| policy-check-v1 | 262233 validator cases, including 262204 rejections; original failed target qualification unchanged |
| composition-check-v2 | Candidate connected directly before unchanged observer RTL, every channel through filter, no bypass; 64 APU writes denied; four actual marker values/addresses and recorded metadata preserved; nine poison/source/PROT mutations have no downstream marker effect |

The composition fixture first sends 64 writes using the accepted profile to
establish the old diagnostic ELF's expected count through the filter. It then
replays the 12 saved ELF address/data events, substituting the measured read
metadata values and measured AW tags/IDs. That fixture is **not** a bootable
filtered smoke firmware. The old APU preamble would be blocked by this filter,
so a future filtered diagnostic needs a new zero-count R5 self-test and a
separate negative-APU observation mechanism. No APU bypass should be added.

The first composition generator attempt expected 43 interface signals; the
interface has 39. It stopped before compile or target action. Corrected v2
passes; v1's directory and this failure record remain. The first read-only
health plan queried a nonexistent dashboard alias and reported inactive.
A separate query of the correct snap unit returned active; no service was
started/stopped. Both original plans and results remain preserved.

## Deployment requirements and next work

| Requirement | Current evidence | Work still needed |
|---|---|---|
| Observed R5 compatibility | Narrow profile and changing IDs pass host tests | New filtered zero-count firmware, actual filtered diagnostic |
| Poison/unknown fields fail closed | Complete USER enumeration, transport and composition negatives | Physical integration and broader legitimate-workload qualification |
| Exclusive source provenance | Documented MID0 alias and indistinguishability witness | Account for CCI and TCU for this endpoint using a reviewed boot policy/topology or a distinct R5 source architecture; do not set SOURCE_PATH_QUALIFIED from a caller boolean |
| USER survives until checked | Direct connection in simulation | Netlist/topology audit before conversion or any alternate CSR/permit path |
| R5-only enforcement while Linux runs | Not qualified | Join trusted boot/ATF/PMU, memory/firewall/output and reset/drain composition; prevent mutable configuration bypasses |
| Physical/timing and target behavior | No new synthesis/route/package/target run | Qualify a separate composition after source-policy review; preserve the 200 MHz implementation |

The next architecture audit should resolve the shared-ID sources against the
actual protected endpoint and threat model. Empty Linux IOMMU groups and an
unbound SMMU driver are observations, not proof the TCU cannot later issue a
matching transaction. Moving to R5_1 would change the current lockstep
arrangement and requires its own boot/session/recovery qualification; it is
not a live fallback command. No raw PS register reads/writes or live coherency
changes were used to bypass these requirements.

## Current board and preservation

Pinned-key SSH at 14:59:43 UTC (09:59:43 America/Chicago) reported same boot
`6c80ec1a-e7ae-473f-b169-d54f129615d1`, uptime 37181 seconds, CPUs 0..3 online,
stock k26-starter-kits operating, remoteproc empty, no sysone_r5_smoke module,
PL0 clock 99999999 Hz with enable/prepare 0/0, taint 12288 (expected O/E).
Correct dashboard unit was active at 15:00:20 UTC. Dmesg retained boot warnings
and earlier overlay-removal warnings, with no newly observed fault after the
previous trial. This is a bounded read-only health observation.

No target PL/firmware/kernel/boot modifications, R5 execution, JTAG connection,
power-cycle, commit or push in this milestone. No JTAG processes were present
at the final host inventory. Previous UART capture stayed closed. S: still
maps this workspace. No physical intervention is pending. Earlier deployment
authorization remains valid when applicable gates pass.

Both prior hash maps plus their original anchor are reverified: 10910 unique
preserved files. The companion validation JSON seals the new candidate and
evidence. HANDOFF.md remains mutable and points here first.
