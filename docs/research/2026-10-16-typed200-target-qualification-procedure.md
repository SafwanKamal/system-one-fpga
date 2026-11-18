# Exact target qualification procedure: sole-R5 typed MVP

Prepared 2026-10-16. **Preparation only; no step below has been executed on the
board.** The reviewed v5 firmware is not a directly bootable FSBL application:
its OCM code/stack overlap FSBL. Follow the blocking local gates first. User
intent is to progress toward deployment once the required artifacts and
ownership policy are ready; this document does not bypass those conditions.

Companion review:
[`2026-10-16-typed200-boot-ownership-review.md`](2026-10-16-typed200-boot-ownership-review.md).
Machine-readable artifact/review inventory:
[`2026-10-16-typed200-target-qualification-profile.json`](2026-10-16-typed200-target-qualification-profile.json).
All experiments require separate new output directories. Never overwrite a
qualified source, recovery image, prior receipt or failed attempt.

## 0. Preserve and bind the exact experiment

Start from the final review seal
`2026-10-16-typed200-arm-ownership-mvp-validation.json` and this review's final
`2026-10-16-typed200-boot-ownership-validation.json`. Verify every mapped file
before any target preparation and again afterward. Preserve the original
hardware-qualified encoder recovery archive:

`build/v2/kr260-app-attention-context-capture-large.tar.gz`

SHA256 `ecd320163baa3c289c64e069186497974d4703039df4a455bc8620d357d7ec99`.

Existing candidate identities:

| Artifact | Exact path / SHA256 |
|---|---|
| Reviewed routed typed DCP | `build/v2/typed200-row-range-csa-route-v1/routed.dcp`; `2d24f5f04d94c17299a32a04190c32118526221f1ab76888baf814fb733cfc88` |
| A53 v5 ELF | `build/v2/typed200-mvp-host-v5/a53.elf`; `63558ce920b53d32078c866fa223149f151f98cd41e3dbf54e37e9b92861ebb2` |
| R5 v5 ELF | `build/v2/typed200-mvp-host-v5/r5.elf`; `1385d94776229eebf2dc468db2d15882a4c376623cb5eed9037fbb9aade746f4` |
| Encoder model image | `export/v2/image/minilm-l12-v1-kr260/minilm-l12-v1-kr260.img`; `4129baded344729ccc7ef6a3f0a2b34799280a91d88173ae1c0b197cdef8c3bb` |
| Typed numerical contract identity | `8133633315487f8f322ecac49e95e7aca3801d00fccb4b4fba36026c5b2752d2`; this is the contract identity, not the JSON file hash |

Each run needs its own directory, host UTC start/end, device identity/serial,
boot mode, exact programmed artifact hashes, cold-boot/reset history, fresh
nonzero 64-bit session, request sequence, token IDs/pool shape/budget, expected
result, test-case ID and instrumentation classification. A bare-metal boot has
no Linux `/proc` boot ID: assign an explicit host run ID and retain cold-POR
evidence and the request's fresh session. Do not reuse a historical Linux boot
ID as evidence for this experiment.

Use `sysone.v2.typed200_qualification.assess_preparation(profile, repo_root)`
for offline artifact/receipt completeness. Current assessment is saved as
`build/v2/typed200-boot-ownership-review-v1/preparation-assessment.json`: all
three completion stages are false. The checker never contacts hardware or
authorizes deployment and cannot authenticate a supplied capture.

For aggregate qualification receipts, the profile's `target_run_id` identifies
the qualification campaign for this exact artifact set. Each scope receipt uses
that same ID; its hashed evidence separately lists every cold-boot run ID/session
and any diagnostic-image identity. This permits multiple required cold boots
without treating them as one uninterrupted execution or mixing artifact sets.

## 1. Close local boot-chain blockers before a candidate boot

1. Build a separate DDR relay or nonoverlapping replacement candidate. Prefer
   preserving v5 and placing only a relay in a reviewed DDR reservation. The
   relay may replace FSBL's OCM **only after final FSBL exit**. Its compiled
   memory map must exclude live FSBL code/data/stack, loader/authentication/PL
   scratch, model/result buffers and all other boot partitions. Review source,
   segment bounds/overlap, copy/zero/config ordering, readback and barriers.
   Test a corrupted payload, overflow/overlap and wrong-entry rejection locally.
   Do not invent a ready BIF pointing directly at the overlapping v5 OCM ELF.
2. Build/pin the dedicated K26 FSBL and PMU, generated BSP/PS init, PM config
   object, link maps, compiler commands and **actual** effective macro dumps.
   Do not substitute source-default macro examples or Linux overlay BIFs.
   Require final EL3/AArch64 A53_0 handoff, no early R5/peer application release,
   completed partition/DMA writes, cleaned caches and reviewed watchdog state.
3. Review normal-operation PMU/CSU ownership: no core wake/restart, clock/reset
   change, DDR-management DMA, PL reload/readback or pending IPI mutation during
   admission. Retain K26 thermal/board protection. Review actual API permissions,
   scheduler/error callbacks and config object, not just compile-time recovery
   flags. Emergency shutdown invalidates the run; it does not resume old work.
4. Review RPU power/TCM/AMBA availability and PS/PL/ADMA access permissions.
   Actual FSBL protection settings must permit the candidate's required accesses
   without claiming an unimplemented hostile-master firewall.
5. Recheck the exact routed DCP's prior setup/hold/DRC/CDC/exceptions receipts
   and unchanged 5 ns/10 ns clocks. It has +0.048 ns setup/+0.011 ns hold, tight
   single-run closure. Once boot dependencies are closed, any bitstream export
   must use that exact DCP into a new candidate directory, record commands and
   hashes, and make no RTL/constraint/physical edits. A change requires renewed
   review/regression; do not reuse the qualified encoder bitstream as typed RTL.
6. Prepare a volatile boot/loading recipe with exact partition destinations and
   rollback path. No QSPI/eMMC boot firmware replacement, eFuse operation,
   JTAG/security-lock change or persistent boot-default change is part of this
   supervised qualification. Keep stock boot media and the qualified recovery
   archive intact. No boot image or new bitstream exists from this review.

Eight artifact roles remain missing: FSBL, PMU, relay, actual FSBL/PMU macros,
PM config object, typed bitstream and boot recipe. Preparation review receipts
must be scoped, passed and bound to the complete artifact hash set before the
offline artifact-review stage can become complete. A source review of the v5
candidate alone is not such a receipt.

## 2. Establish recovery and baseline target inventory

Before choosing a cold-boot window, verify physical access, known serial console
and trusted debug adapter/target identity. Historical board address
`192.168.0.239` and the 2026-10-15 Linux recovery receipt are context only; do not
assume current connectivity/firmware. Record fresh board/model/boot/temperature
and recovery inventory using a read-only session where available. Pin actual
boot binaries or record that their identity is unknown; unknown current firmware
must not silently satisfy the dedicated-chain requirement.

Confirm recovery independently of Ethernet: this profile resets GEM0–3 and all
A53 cores, so Ethernet links and SSH are expected to disappear. Serial/debug
access must remain available through the declared trusted path. Do not diagnose
that planned loss as permission to repeatedly reboot. Preserve thermal/fan
management; a fan/power or thermal abnormality is an abort, not normal behavior.
These are prospective effects, not an explanation of an earlier board outage.

Keep an explicit tested route back to stock boot, followed by verification of
the retained qualified encoder package using its existing documented loading
procedure. The existing Linux recovery archive is an FPGA application package,
not a replacement FSBL/PMU/whole-board boot image. Preserve the original boot
firmware and boot media separately. Do not execute old preflight/controller
scripts: some launch Vivado or overwrite historical output directories.

## 3. Cold boot and diagnostic startup qualification

Only after Stage1 preparation and Stage2 recovery are ready, start a fresh
controlled cold POR with the reviewed volatile chain. A warm Linux takeover,
remoteproc launch or debugger reset is not a cold-POR substitute. Keep permit
low through all loading; never load model bytes while any request is active.

Load the exact model at `[0x60000000,0x62058800)`; IDs occupy the RW overlay
`[0x62100000,0x62101000)`, hidden output begins `0x62101000` and up to128×384
bytes ends at `0x6210d000`. Preserve the full existing model/buffer reservation.
The producer writes exactly448 bytes of `mvp_input` at `0xfffee000`: boot magic
`0x4d565031`, version1, fresh nonzero session, nominal R5 Hz533328000, eleven
reserved words0, then the 384-byte legacy request. Request magic`0x54594331`,
version1, matching session, READY state1, sequence1, explicit IDs/shape/budget.
Zero unused fields/IDs/padding. No default session or synthetic result is valid.

Instrumented startup run, separate from timing:

1. At final FSBL-to-relay handoff record actual PC/SP/CurrentEL, cache state,
   loader completion, power/permission state and no peer application execution.
   Prove FSBL is no longer executing before relay OCM replacement. Ensure no
   PMU flow will return to the replaced FSBL. Cache clean/disable cannot be
   inferred merely from a zero SCTLR cache-enable bit.
2. At A53 candidate entry verify EL3/A53_0, cache/MMU off, intended OCM payload
   bytes/hash, input structure and permit0. A53 fault code is recorded at
   `0xfffef000`; `0x48414e44` means handoff issued only, not ownership complete.
3. At R5 `ty_r5_main` / first `mvp_step`, record reset entry, split TCM, enabled
   ECC checks, banked/SVC stacks, VBAR0, MPU attributes and PMU controls. R5_1
   stays reset/halted. All A53 cores must actually be reset before ownership
   establishes; self-reset issue alone is insufficient. Breakpoints make this
   run diagnostic; retain timestamps but do not use them as clean phase bounds.
4. Validate all20 exported runtime rules in
   `build/v2/typed200-boot-ownership-review-v1/runtime-register-checks.csv`.
   These are compiled from the actual frozen C table, not a retyped model. An
   additional CSU/PMU/debug audit is required because those controls are not in
   v5's R5 monitor. Require CSU source/destination `STS & 0x1fff == 0`, PCAP reset
   asserted, PL_DONE set, no pending PMU IPI0–3 status. Record debug/security
   registers without writing them. Prove no queued software mutation remains.
5. Validate MPU behavior using a separately identified diagnostic harness:
   attempts to write model/hidden and PS clock/reset/config regions must abort;
   intended ID and CSR writes work. Check stack/BSS boundaries and ECC error
   handling separately. A host link map does not prove hardware permissions.
   Never inject TCM ECC errors into the only recovery/boot firmware.

The diagnostic harness, any modified firmware and corresponding images get
distinct hashes. They do not qualify the timing of the unmodified v5 image.
Restore pristine state through a new cold POR after each destructive/fault run.

## 4. Functional typed-output qualification

Run the following as separate cold boots/fresh sessions with exact IDs, hidden
goldens and expected typed records saved before launch. For initial valid-request
bring-up, IDs may be deterministic `(101,102,...)`, first0/countT. Save the
reference encoder/head output for those exact inputs first. Initial **experimental**
budgets may be10,000,000 PL cycles for T1 and20,000,000 for T128; these are generous
bring-up choices informed by simulation, not certified successful budgets.
An observed Deadline at either budget must be retained and investigated, not
renamed Accepted or used to claim success. All valid terminal records satisfy
the exact numerical/identity contract; never compare unmatched encoder requests
to generated tokens or prefill throughput.

| Case | Stimulus / distinct image if needed | Required result |
|---|---|---|
| F01 | Frozen model, valid T1, then T2/3/4/5/12/64/128 in fresh boots | Exact hidden/head result and canonical Accepted where completed; correct session/request/contract/sequence, PL provenance; retain actual cycles/Deadline if any |
| F02 | Dedicated ARM head harness with all647 frozen head fixtures, counts1–128, ties and scaled-vs-raw argmax differences | Exact51,760 golden output bytes, including640 valid and7 invalid cases; separate diagnostic firmware identity |
| F03 | Invalid shape/token ID/zero budget/nonfresh sequence, each in separate fresh boot | Canonical CPU Invalid where frozen service rejects; origin0, no PL-admission claim; confirm no unintended encoder launch |
| F04 | Valid request with tiny nonzero budget (initial trial1) | Deadline for an admitted expiry under the frozen contract, label/reserved score0; no late success; confirm the actual branch with raw pre-ACK capture |
| F05 | Controlled native/core/AXI fault in a reviewed diagnostic image | Canonical HardwareFault or contract-defined Deadline/quarantine, no Accepted fallback; profile identifies injected mechanism and modified image |
| F06 | Bad model byte, boot config/session mismatch, wrong clock/reset profile, R5_1 unheld or A53 self-reset denied before admission | No admission/permit grant; startup/ownership fault recorded where MMIO works; distinguish this from a request's typed terminal |
| F07 | PMU overflow/control fault or attempted reset/clock release during a diagnostic request | Sticky fault/permit-low attempt and no reuse of prior Accepted record; retain whether request already terminal; snapshots alone are not continuous-exclusion proof |
| F08 | Warm boot attempt, stale mailbox/result, then genuine fresh POR/session | Warm takeover rejected; old result never passes new identity; fresh boot recovers without modifying baseline |

Do not claim the monitor covers arbitrary brief changes between polls. Faults
involving a stuck MMIO/permit path, stopped clock, power loss or trusted-controller
misbehavior are outside its conditional fail-closed proof. Classify those
explicitly; never expect a timed ARM response when the responding-clock/MMIO
assumption has been removed. Emergency safety shutdown is an invalidated run.

## 5. Capture without destroying the evidence

The frozen R5 service saves a pre-ACK PL snapshot and shared terminal in its
trace, acknowledges the endpoint, then the MVP parks with permit0/boot_status2.
Reading live PL CSRs afterward cannot reconstruct that pre-ACK terminal. Save
the firmware's raw snapshot. The exact v5 symbols/lengths are:

| File | Local R5 address | R5_0 split global debug alias | Bytes |
|---|---|---|---|
| `final.shared.bin` | `0x2f000` | `0xffe2f000` | 384 |
| `trace.bin` | `0x20010` | `0xffe20010` | 1488 |
| `pmu.bin` | `0x205e0` | `0xffe205e0` | 72 |
| `pmu-config.bin` | `0x2f180` | `0xffe2f180` | 32 |
| `boot.bin` | `0x2f1c0` | `0xffe2f1c0` | 64 |
| `owner.bin` | `0x2f300` | `0xffe2f300` | 12 |
| `permit.bin` | Device | `0xa0001000` | 4 |

Prove the debug alias on the diagnostic boot; do not assume it under a different
TCM mode. These symbol addresses are v5-specific. Any relink or instrumentation
change requires regeneration from its actual ELF manifest.

For a properly parked, coherent capture, retain raw files and their SHA256s,
raw read-only register snapshots, debug/serial host logs and exact programmed
hashes. Feed `trace.bin`, `pmu.bin`, `final.shared.bin`, `boot.bin`, `owner.bin`,
`permit.bin` and independently prepared `ExpectedCapture` to
`sysone.v2.typed200_mvp.assess_mvp`. It requires boot_status2, owner established/
fault0/checks≥2, permit0, no exception, PMU validity and exact agreement with the
saved pre-ACK typed record. The old v1 mailbox decoder expects boot_status1;
do not mutate the original capture to satisfy it. The MVP adapter explicitly
normalizes only a local copy and still does not certify target provenance.

If a startup fault occurs, save the A53 fault word and whatever coherent R5
fault evidence exists; do not force it through the successful parked-output
decoder. Missing output is a retained failed run, not a passing zero record.

For strict timing runs, acquisition resumes only after a reviewed passive
completion/park notification. The current v5 firmware lacks that reviewed
notification. A fixed host delay followed by debugger reads does not prove
traffic started after execution ended. Until resolved, such captures are
functional/diagnostic and their timing observations retain that limitation.
Do not halt PMU or R5 during the admitted window to improve apparent timing.

## 6. Timing qualification and claims

Only after functional gates pass on the exact deployment profile:

1. Calibrate deployed PL/R5/PMU rates against a reviewed independent reference;
   bind oscillator tolerance and clock-source/divider stability. The v5 declared
   R5 rate533328000Hz/PL0199998000Hz is nominal. The earlier qualified encoder's
   measured199999998Hz is not a measurement of this boot profile. Record raw
   processor ticks and PL cycles independently of wall-time conversions.
2. Obtain noninterfering phase evidence for admission, native compute, memory
   drain, hidden copy, head, proposal, publication and final capture. Include
   new ownership polling and instrumentation costs. Do not add overlapping
   intervals or treat the host's simulation runtime as ARM performance.
3. Derive defensible DDR/MMIO service bounds for the active PL/R5 masters,
   refresh/controller behavior, pending traffic, arbitration and exceptional
   stalls. Sole-R5 ownership removes competitors; it does not bound every
   memory transaction or prove head execution time.
4. Combine disjoint phase bounds with a minimum R5:PL ratio, clock tolerance
   and explicit margin. Use experiments to falsify/refine the proposed bound;
   an observed maximum, repeated success or a small STA margin is not WCET.
5. Demonstrate conditional terminal-by-D and distinguish that from useful
   Accepted-by-D, ARM consumer delivery, stopped-clock recovery and external
   network delivery. No live network client exists in this profile. Confidence/
   OOS quality, Clarify and Abstain behavior require their own calibrated model
   policy; existing Accepted/Fault head logic does not establish them.

## 7. Abort, recovery and promotion

On any mismatch: retain raw data and host logs, mark the run failed/incomplete,
and stop promotion. Do not relax timing constraints, suppress failed checks,
patch captures, silently enlarge budgets or rerun into the same directory.
After the run is safely stopped through the reviewed physical procedure, return
to known stock boot, verify its identity and recover the qualified encoder app
using its preserved package if needed. Verify recovery numerics/clock/status
using the existing qualified method; do not rebuild or rewrite its frozen files.

Promote only the exact artifact/profile combination that actually passed the
applicable target gates. Preserve the separate baseline and failures. Functional
MVP qualification can precede a stronger useful-success timing guarantee; report
which has been achieved. This review has achieved neither target milestone.
