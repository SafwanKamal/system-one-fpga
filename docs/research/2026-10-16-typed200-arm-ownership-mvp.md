# Typed-output MVP: separate ARM startup and ownership candidate

Implemented and locally verified on 2026-10-16. **Not deployed or executed on
ARM hardware; no bitstream, boot image or package created.** No RTL changes,
Vivado builds, board access, programming, reboot, commit or push occurred.
The hardware-qualified 200 MHz encoder remains the recovery baseline. The
routed carry-save typed successor remains a separate, unqualified artifact.

The new candidate is `firmware/typed200_mvp`. The final local run is
`build/v2/typed200-mvp-host-v5/validation.json`; the additional native ELF/source
review and preservation seal are under `build/v2/typed200-mvp-review-v1` and
`2026-10-16-typed200-arm-ownership-mvp-validation.json`. Both handoffs point here.

## Implemented profile

The MVP uses R5_0 as the only active application core during the request. A53_0
performs a trusted cold-boot handoff, then resets all four A53 cores, including
itself. R5_1 is held reset and halted. No Linux, network client or concurrent
A53 producer runs during admission. One request is preloaded in OCM by a trusted
producer, then R5 performs the frozen encoder/head/typed-publication service and
parks with permit low after the first terminal record.

This is a deliberately limited supervised MVP, not the final concurrent product
architecture. It replaces reliance on an unsupported software exclusivity
attestation with explicit reset/clock controls **under a declared trusted-boot
profile**. It does not install a hardware firewall against malicious PMU, CSU,
DAP/debug, privileged R5 or an unenumerated PL master. Those actors must be
trusted/quiescent. XMPU/XPPU resource ownership, a live A53 client and concurrent
Linux require a separate reviewed profile. A register readback cannot establish
continuous exclusion against a master capable of changing that register.

### A53 startup and handoff

The new AArch64 reset-entry ELF resides in OCM, entry `0xfffc0000`. Assembly
checks EL3, A53 core index 0 and disabled MMU/I/D caches, selects SP_EL3, installs
exception vectors and clears private BSS. A failed entry precondition parks
before attempting handoff; trusted initial permit-low remains a prerequisite.
Exceptions after vector installation attempt permit-low, record a fault and park.

The actual handoff C performs these ordered operations:

1. Clear/read back PL deployment permit. Require a cold POR history, matching
   typed ABI, inactive/unconfigured endpoint and drained native memory state.
   Warm reset is rejected: this code is not a safe takeover of a running Linux
   system with potentially outstanding traffic.
2. Check the existing PLL/divider/clock and EMIO PL-reset profile. Halt both R5
   cores, assert their resets, release RPU AMBA reset, select split TCM, ARM and
   little-endian entry, ungated/no-wait TCM, and low R5_0 vectors.
3. Hold A53 peers and competing DMA-capable peripherals in reset. The policy
   covers GEM0–3, ADMA, GDMA, USB0/1 core/hibernation/APB, SDIO0/1, NAND, QSPI,
   GPU/PP0/PP1, SATA and PCIe controller/bridge/config. DisplayPort is reset and
   the DPDMA reference clock disabled. Cold boot with no outstanding traffic is
   essential; this is not a protocol for draining arbitrary previously running
   display or DMA traffic. Preserve encoder AFI FM0 and PS GPIO reset release.
4. Temporarily release ADMA under sole A53 ownership to zero each complete
   64 KiB TCM bank through the vendor-style write-only DMA path for ECC. Check
   programmed DMA registers, poll with a finite iteration limit, reject errors,
   then reassert ADMA reset on completion/error/timeout. RPU power, stable clock
   and access permissions must already have been supplied by trusted PS init.
5. Load the exact newly linked R5 ELF segments embedded by the build helper.
   Validate segment ranges, zero NOLOAD/BSS, copy bytes and read back the full
   loaded memory. Write session/request/PMU/boot config **after** zeroing. Config
   has no nonzero default session and does not itself authorize admission.
6. Release only R5_0 and set its NCPUHALT. Record HANDOFF ISSUED, then assert all
   four A53 core resets. That status is not OWNERSHIP COMPLETE. If self-reset is
   denied, R5's independent check fails; no permit is granted.

The producer's 448-byte OCM input structure is defined in the candidate README.
The loader bounds its generated ELF segments and trusts their build-time
manifest; it is not an untrusted executable-file parser or authenticated-boot
implementation. Session freshness across boots is the trusted producer's job;
matching nonzero sessions reject mismatches, not deliberate replay.

### R5 execution and exclusive access

R5 assembly initializes banked stacks, low vectors, the existing erratum/predictor
policy, VFP and BSS. It additionally enables TCM ECC checks and abort-on-parity
policy after the A53 ECC scrub. MPU/caches must be off on reset entry.

R5 keeps permit low, validates config/session, waits a bounded number of polling
iterations for **all A53 resets**, then independently checks 20 ownership,
clock/reset and GPIO rules. The policy checks R5_1 halt/reset, R5_0 run/released
reset, RPU split/ARM/endian/TCM-clock settings, competing-master reset/clock
states, PLL lock/fractional mode/source/dividers and EMIO reset direction,
enable and deasserted level. Unexpected bits cause a sticky ownership fault.

The model is SHA-256 checked before service, against the frozen
`4129baded344729ccc7ef6a3f0a2b34799280a91d88173ae1c0b197cdef8c3bb` image.
R5 initializes its own full-rate PMU once, then binds the frozen read-only
PMU trace provider. No PMU-control writes occur during the service. The PMU
rejects invalid controls, overflow and equal/backward samples; no wrap repair.

`mvp_step` checks ownership and prior PMU fault before every frozen-service
poll, including the poll that raises permit. It prevents service MMIO on a
detected ownership fault, attempts permit-low and parks without healing/retry.
All canonical terminal outcomes, including Deadline, HardwareFault and Invalid,
are preserved when the one-shot service parks. Final boot status becomes 2.
Exceptions attempt permit-low and preserve the diagnostic exception reason.

The old service's exclusivity flag remains for ABI compatibility; it is not
the authorization mechanism. R5's independent observed ownership check must
succeed before service initialization/admission. The MPU makes PS clock/reset
registers read-only for R5, so service code cannot casually alter that policy.

| R5 region | Candidate permission / purpose |
|---|---|
| ATCM `0x00000000–0x0000efff` | Code/constants, privileged RO/executable |
| ATCM `0x0000f000–0x0000ffff` | Banked exception stacks, RW/XN overlay |
| BTCM `0x00020000–0x0002ffff` | Private work, SVC stack and shared evidence, RW/XN |
| DDR `0x60000000–0x63ffffff` | Model/hidden, privileged RO/XN, noncacheable |
| DDR `0x62100000–0x62100fff` | IDs only, RW/XN overlay; hidden starts `0x62101000` |
| PL `0xa0000000–0xa0001fff` | CSR/permit Device RW/XN |
| CRL/CRF/RPU/PS-GPIO 64 KiB blocks | Device RO/XN |
| BTCM `0x2f180` / `0x2f1c0` | PMU config 32 B / boot config 64 B, RO/XN overlays |
| BTCM `0x2f000` / `0x2f300` | Legacy shared 384 B / owner evidence 12 B |

### Clock/reset ownership and guarantee boundary

The generated CSA PS configuration declares PSS reference **33.333 MHz**;
IOPLL FBDIV60/div2 and RPLL FBDIV64/div2 yield nominal PL0 199,998,000 Hz,
PL1 99,999,000 Hz and R5 533,328,000 Hz (generated floating values differ by
rounding). These are configuration-derived rates, not measurements. The
qualified baseline's measured 199,999,998 Hz is separate evidence and must not
be silently assigned to this candidate. The checked divider/source configuration
implies an R5:PL0 ratio of 8:3 under their shared stable reference assumptions.

The handoff does not reprogram PLLs, reset PL during a request, or relax PL timing
constraints. R5 cannot write the PS clock/reset mappings after its MPU starts.
PMU/CSU/debug must preserve these settings. A 1,000,000-iteration wait is finite
software work, **not a bounded wall-time timeout when MMIO or clocks can stall**.
Permit-low failure handling assumes responding MMIO and a working permit path;
it cannot physically turn off a stuck-at-one permit or recover a stopped clock.
An independent supervisor/watchdog remains a separate requirement for that
stronger fault model.

The frozen PL contract gives conditional terminal-by-D in running PL cycles.
This work does not establish successful-inference WCET, ARM result-delivery
latency, a stopped-clock wall-time guarantee, or a network-delivery deadline.
Additional ownership polling changes ARM execution cost. **No unchanged ARM
cycle claim is made.** No RTL/pipeline/deadline-budget change was made here;
the earlier exact RTL output/counter/cycle proofs remain preserved evidence.

## Local verification and actual artifacts

Final `typed200-mvp-host-v5` passed:

- Address/undefined sanitizer tests of actual portable ownership/supervisor C.
  Every one of **131 monitored register bits** independently inverted causes
  sticky rejection and permit-low in the responding-MMIO model. Tests also cover
  denied prepare writes, bad ABI/activity/drain/cold-POR, owner-counter overflow,
  DMA done/error/timeout, invalid scrub addresses and **786,432 segment checks**.
- The actual supervisor prevents frozen-service MMIO on a detected ownership
  fault and preserves Accepted/Fault/Deadline/Invalid records while parking.
  Frozen service, driver and PMU fault regressions pass.
- The frozen integer head's **647 fixtures**, including 640 valid and 7 invalid,
  reproduce the complete 51,760-byte golden output exactly. This preserves model
  numerics; it is not a new model-quality or target-performance measurement.
- **467 Python tests** pass, including the separate parked-MVP consistency gate.
  That gate requires matching boot session/config, owner established/no-fault,
  permit zero, parked/no-exception final mailbox, matching pre-ACK trace and
  valid frozen PMU/typed-record checks. Original raw captures are retained;
  only an explicit local copy normalizes boot_status for the legacy decoder.
  The gate always declines to certify hardware provenance, continuous ownership,
  measured frequency, useful-success bounds or WCET from file bytes.
- Both reset-entry ARM ELFs link with no unresolved symbols and no writable
  executable load segments. R5 entry0, five TCM LOAD segments; A53 entry
  `0xfffc0000`, code in OCM plus a 16 KiB RW stack. R5 program uses 19,464 bytes
  of code/constants, 51,216 bytes of private BSS, 8 KiB SVC stack and five 256 B
  banked stacks. Compiler frame sums are recorded separately, not measured
  high-water marks or a proof against arbitrary exception nesting.
- A host test executes the **actual A53 handoff C** using fixed-address mapped
  TCM/OCM and mocked MMIO/DMA, with undefined-behavior sanitizer. It verifies
  payload/NOLOAD/config ordering and readback, R5 release before self-reset,
  denied self-reset, stuck DMA, malformed/session-mismatched config and warm
  reset rejection. AddressSanitizer is intentionally used for portable tests,
  not the fixed-address boot mapping that conflicts with ASan shadow memory.
  Neither host harness executes ARM privileged instructions.

Four known linker warnings remain: input `.shared`, `.clock_config`,
`.boot_config`, `.owner_evidence` are PROGBITS while the intentional NOLOAD
output is NOBITS. Actual ELF file size0/memory sizes, symbol addresses, zeroing
and config-after-load behavior are audited/tested. They are not unresolved
symbols, W+X memory or lost configuration. No warning was hidden/suppressed.

Attempts v1–v3 are retained: missing test stdio include, missing driver output
argument and omitted head-test mailbox link unit respectively. v4 passed, then
source review added TCM clock/wait/entry-endian checks and the parked-MVP gate;
v5 reran the full suite and ARM links. All v4 source bytes were recovered into
the review directory and verified against v4's recorded hashes. No completed
old experiment, native build or automation was restarted.

## Remaining acceptance gates, in priority order

| Priority | Target-only experiment / required evidence | Why it remains open |
|---|---|---|
| 1 | Review trusted FSBL/PMU/CSU/debug policy, resource permissions, cold-POR and no-outstanding-traffic procedure | Reset readback alone cannot exclude a trusted controller later releasing a master; no adversarial-master claim |
| 1 | Exact artifact recovery/boot inventory and target startup captures of EL3/R5 entry, TCM ECC, low vectors, MPU faults, clocks/resets and all master controls | ELFs are cross-linked and host-tested, never executed on ARM |
| 1 | Target reset/self-reset-denied/invalid-clock/abort/permit-failure campaign; show permit cannot rise before actual ownership | Mocked register semantics are not the physical reset fabric, posted writes or PS permissions |
| 1 | Calibrate clocks/PMU and capture frozen head goldens, ties/scaled-vs-raw differences and all typed outcomes on ARM | Native instructions, DDR/MMIO behavior and actual model quality are unmeasured for this profile |
| 2 | Measure native/drain/copy/head/proposal/publication phases under sole-R5 profile, derive DDR/MMIO/ARM service bounds and revised margin | Polling overhead changes CPU cost; sampled maxima are not WCET |
| 2 | Trusted post-park capture/recovery for repeated fresh-session demonstrations | This MVP has no live A53/Linux/network producer; observer access is after terminal freeze |
| 3 | Separate concurrent A53 ingress profile with reviewed XMPU/XPPU/ownership and bounded handoff | Reset-based sole-R5 ownership does not authorize concurrent Linux |

No target gate above was discharged, and this report grants no permission to
deploy. The next concrete milestone is review and later target qualification of
this exact ownership profile, before increasing clock rate or adding generation.

## Primary implementation sources

Numeric definitions and startup policy are pinned from the actual installed AMD
2025.2 `embeddedsw`, including standalone_v9_4; hashes and original paths are in
`firmware/typed200_mvp/reference/sources.json`. This is not assumed identical to
an arbitrary upstream commit. In particular, the installed FSBL's
`xfsbl_handoff.c` provides split/halt/clock/reset ordering and
`xfsbl_initialization.c` supplies its DMA-based TCM ECC procedure. The generated
CSA `psu_init.c` and reviewed `.xci` supply the actual PS clocks/GPIO reset path.

Public primary counterparts:
[AMD FSBL handoff](https://github.com/Xilinx/embeddedsw/blob/master/lib/sw_apps/zynqmp_fsbl/src/xfsbl_handoff.c),
[AMD FSBL initialization](https://github.com/Xilinx/embeddedsw/blob/master/lib/sw_apps/zynqmp_fsbl/src/xfsbl_initialization.c),
[AMD Cortex-R5 startup](https://github.com/Xilinx/embeddedsw/blob/master/lib/bsp/standalone/src/arm/cortexr5/gcc/boot.S).
The explicit TCM-clock/wait/ARM/endian checks were reviewed against
[AMD UG1087 RPU_GLBL_CNTL](https://docs.amd.com/r/en-US/ug1087-zynq-ultrascale-registers/RPU_GLBL_CNTL-RPU-Register).
The difference between local MPU protection and inter-master isolation follows
[AMD isolation configuration](https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18842442)
and [XAPP1320](https://www.origin.xilinx.com/support/documents/application_notes/xapp1320-isolation-methods.pdf).
