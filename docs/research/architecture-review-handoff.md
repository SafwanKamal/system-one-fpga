# Architecture review handoff

## New-chat start here (handoff prepared 2026-10-16)

Continue the separate typed-output AMP candidate toward qualified deployment.
The user explicitly authorized working toward deployment AND deploying once
readiness gates pass. Do not ask for that same authorization again. The present
candidate is NOT ready for typed inference; the completed deployment was only
a diagnostic probe, followed by verified stock restoration. This handoff update
performed no new board access: all board state below is last verified evidence.

Read in this order:
1. This start section and the latest state section immediately below it.
2. docs/research/2026-10-16-typed200-amp-target-probe.md and its CSV.
3. build/v2/typed200-amp-deployment-v1/target-milestone-v1/readiness.json
   and failed-attempt-ledger.json.
4. docs/research/2026-10-16-typed200-amp-ownership.md and its readiness/experiment
   records for the unfinished ATF/PMU/R5/firewall composition.
5. docs/research/2026-10-16-typed200-amp-target-probe-validation.json:
   verify BOTH hash maps and preserve the anchor itself before new mutations.
   It preserves 10,007 previous files/anchors and seals 81 new artifacts.

Immediate next work:
- Recheck existing processes and saved-key SSH before any target action. Last
  working endpoint: ubuntu@192.168.0.239. Saved Ed25519 SHA256 fingerprint:
  EGYkdZirFAYH1XOF2uPZYSzmLMOj7obcj/xAeHIW/Qc. DHCP can change; never replace
  known_hosts or autoaccept another key. Use available credentials securely;
  no password is recorded in these handoff files.
- Audit a NEW guarded RPU-only diagnostic setup/rollback candidate. Establish
  actual RPU power/reset/clock/mode and Linux ownership, set a private halted
  entry, and arm board-local recovery before release. Preserve A53/GEM/PLL/ADMA
  and live ATF OCM. The SDK AMBA reset mask is 0x4. Avoid opaque rst-processor:
  the reviewed SVF implementation writes OCM and a broad reset value. Do not
  assume every native helper has that same write set; audit the actual path.
- Existing R5 image (do NOT rebuild):
  build/v2/typed200-amp-deployment-v1/r5-probe-build-v1/r5_probe.elf
  SHA256 79ed1f7178027011252d3b31ae8b9a098c6db444843243f3cf7f0e2bc6944e12.
  It uses 0x63f00000..0x63f0ffff no-map DDR; save fresh contents before use and
  restore only after R5 is definitively stopped/reset. Result at 0x63f0f000;
  success status 0xd00d0001; four marker slots 4..7. Debug startup is not a
  qualified reset path or timing proof. R5 tags have NOT been measured yet.
- Existing reviewed diagnostic package (do NOT rebuild):
  build/v2/typed200-amp-deployment-v1/probe-package-v1/sysone-amp-origin-probe.
  The same app is already installed additively on the board. A future controller
  must hash-check and reuse it, not fail blindly on its existing directory.
  Physical artifact probe-physical-v2: +4.346 ns setup, +0.031 ns hold at 10 ns.
- Before another trial, implement a NEW controller with the reviewed clock-gate
  recovery semantics. Do not rerun amp_probe_target_trial.py unchanged: its
  complete-register recovery assertion rejected Linux clearing CLKACT when
  the probe consumer was removed. Preserve that failed service and separate
  successful recovery review. Do not force an unused clock on by raw PS write.
- Measure R5 AR/AW source metadata, then finish trusted ATF/PMU/R5 session
  activation, quiescent firewall installation, integrated pre-conversion source
  filtering, relocated hidden outputs and protected startup. Finally run exact
  numerical/output/counter/cycle/fault/drain regression, new physical checks,
  and target negative-access/stress qualification before inference deployment.

Timing contract: canonical LOCAL PL typed terminal by D AFTER admission,
conditional on protected uninterrupted clock/reset. Preserve Accepted, Clarify,
Abstain, Fault, Deadline and Invalid semantics. Do not claim Accepted-by-D,
SSH-delivery WCET, Linux ingress WCET, or 300 MHz from this diagnostic. Linux
on A53 may provide SSH/relay; it must not own the admitted FPGA transaction.

Operational constraints: separate candidates; preserve qualified 200 MHz RTL,
package/recovery/numerical baseline and ALL prior sealed evidence. Never apply
boot-only firewall writes to running Linux. One large native job at a time;
inspect and resume existing jobs rather than duplicate them. No new jobs were
running at last handoff; hw_server may remain on TCP3121, JTAG cable
XFL14EBBE1U3A. Preserve S: workspace alias and verify its mapping before use.
No commits/pushes, QSPI/security/fuse writes or automation recreation. Old
predecode overnight automation instructions are historical, not the active task.

Workspace uses PowerShell, uv run --no-sync python, AMD tools 2025.2 under
C:/AMDDesignTools/2025.2, and WSL Ubuntu-24.04. SSH helpers prepend auth-deps
from build/v2/typed200-amp-candidate-v1/auth-deps and build/v2/board-auth-tools.
No subagents unless the user or applicable instructions explicitly request them.

Everything below the latest state section is history. Older no-deploy or
recovery-pending statements do not override the latest authorization/evidence.

## Current: SSH recovered; diagnostic origin probe executed and stock restored (2026-10-16)

User power-cycled; saved-key SSH authentication works at 192.168.0.239.
Read docs/research/2026-10-16-typed200-amp-target-probe.md first and its CSV.
Latest seal: docs/research/2026-10-16-typed200-amp-target-probe-validation.json
PASS preserves10007 previous immutable files/anchors and seals81 new artifacts.
Use both preserved_sha256 and candidate_sha256 plus that anchor for next audit.
Deployment authorization remains active. Full typed-output MVP is NOT READY.
No R5 image executed, boot/flash/security/fuse writes, commits or pushes.

board-readiness-v4 PASS: six stock+qualified-app files and 64KiB no-map DDR
backup, clocks/PS state. Diagnostic probe-target-v1 actually loaded reviewed
100MHz probe via xmutil/dfx-mgr. APU exact lane/address/data/count tests PASS:
64 writes, zero errors, four affinity-pinned A53 cores. Source ARUSER80..83,
AWUSER8c..8f, PROT2. Capture is before USER loss. apu-tag-replay-v2 PASS2325
transactions including136 new measured/secure-bit mutation cases. R5 identity
still unmeasured. This is diagnostic deployment, NOT typed inference.

Original target service FAILED recovery raw-register equality: probe unload
cleared PL0 CLKACT bit24 through Linux clock driver. Stock reloaded correctly.
Separate probe-target-v1/recovery-reviewed-v1 PASS verifies EXACT delta01000000,
unchanged clock rate/parent/dividers/zero references, AFI0xa00, stock operating,
RPU reset13/global50, all six baseline app files and saved DDR unchanged.
Dashboard restarted+verified active. Do not force raw unreferenced clock on.
Diagnostic app remains installed additively; stock k26-starter-kits is active.
No native job running. Do not restart completed trials or overwrite failures.

New artifacts rooted build/v2/typed200-amp-deployment-v1/target-milestone-v1.
Read its readiness.json and failed-attempt-ledger.json. board-readiness-v3
failed because fpgautil absent; v4 uses installed manager. Tag replay-v1 failed
harness argument order; corrected v2 PASS, filter RTL unchanged.

Next: audit guarded RPU-only setup and local recovery before loading R5 ELF.
SDK reset AMBA mask is0x4, NOT0x10. Installed AMD SVF R5 reset helper writes
OCMffff0000 and broad LPD reset: exclude opaque rst-processor helpers on live
Linux unless exact writes audited. No old sole-R5 loader, A53/GEM reset,
PLL/ADMA changes, or boot-only firewall installation on live Linux. Need actual
power state, hardware-halted private entry, stopped/reset DDR restoration,
measured R5 tags, then full trusted closure/filter/startup/memory composition
and exact numerical/cycle/physical/target regression. Preserve frozen baselines.

Earlier Current sections below are historical and may state recovery pending.

## Historical: deployment authorized; origin-probe package ready, stock boot recovery required (2026-10-16)

Latest user explicitly: work toward deployment AND deploy. This supersedes old
no-deploy instructions, but does not waive readiness checks. NO candidate FPGA
or R5 image has been loaded. Qualified200MHz files/package/numerics remain intact.
The live board is currently not reachable over SSH after recovery reset attempts.

Read first:
- docs/research/2026-10-16-typed200-amp-deployment.md
- build/v2/typed200-amp-deployment-v1/deployment-readiness.json
- docs/research/2026-10-16-typed200-amp-deployment-validation.json (PASS:9844
  prior files unchanged;162 new immutable source/evidence artifacts sealed)
- build/v2/typed200-amp-deployment-v1/failed-attempt-ledger.json
Earlier Current sections below are historical.

New root build/v2/typed200-amp-deployment-v1. Started by verifying9844 previous
sealed/evidence files. Diagnostic-only RTL rtl/v2/candidates/typed200_amp_probe:
no encoder, permit, PL DDR master or external I/O. Records real AWUSER/PROT/ID;
read registers expose ARUSER/PROT/ID. probe-sim-v4 PASS2048 exact traces plus
stall/burst/reset checks. probe-physical-v2 routed+4.346ns setup/+0.031ns hold
at10.000ns; zero DRC/check_timing problems, CDC safely timed, full route, only
two exact vendor-reset synchronizer false paths. +0.500ns placement gate passed.
Physical-review.json admits PROBE bitstream only. Bitstream/package completed:
probe-package-v1/sysone-amp-origin-probe. Do not rebuild completed attempts.
No package has been uploaded. v1 physical probe lacks read-tag visibility and
is superseded. No new claim about200MHz inference timing or cycles.

R5 diagnostic ELF in r5-probe-build-v1 uses no-map DDR63f00000..63f0ffff (must
save/restore first), not TCM or live ATF OCM. IRQ masked, MPU/cache reset checks,
four source markers, explicit result status. NOT reset-startup/WCET qualified;
RPU-only setup/restore still needs review/testing, no R5 execution yet.

Authenticated board-preflight-v1 succeeded at192.168.0.239, saved host key
EGYkdZirFAYH1XOF2uPZYSzmLMOj7obcj/xAeHIW/Qc. Stock k26-starter-kits overlay
active, no System One inference running, allA53 online, no remoteproc. Later
both Paramiko and native SSH failed pre-auth/KEX/banner. board-readiness-v1/v2
failed BEFORE any commands or backups. No new recovery-app/DDR backup captured.

Agent then issued JTAG rst-system-start and rst-por under new deployment/recovery
authorization. Both returned issued; neither established normal cold boot/SSH.
QSPI mode remains2, no alternate boot. UART1 was reset-blocked after warm reset.
Bounded local/24 port22 scan found none. Brief A53#0 stop/read/resume completed:
PCfffEA16c (stock ATF warm-entry code), PSTATE3cd, explicit con logged. No code
loaded, no flash/security/fuse/bootfile writes. Do not claim actual physical POR
or infer the failure cause. Avoid repeated resets. Current JTAG cable remains
XFL14EBBE1U3A. Local hw_server may run. No native job remains running.

USER ACTION PENDING: async request to unplug/reconnect KR260 power once because
JTAG resets did not restore stock boot. Continue when user confirms, verify saved
host key again before authentication (DHCP may change address). Do not replace
known_hosts. No new board-dependent work until actual recovery is established.

Next: fresh board-readiness-vN via scripts/v2/amp_probe_board_preflight.py; obtain
stock+qualified-app file backups, reserved-DDR snapshot, live clocks/AFI/reset and
actual dashboard service (PID lookup now dynamic). Complete reviewed bounded
probe-load/rollback controller before loading diagnostic package; retain PL0
rate and require <=100MHz,128bit HPM0 AFI and exact ABI/lane tests. Then qualify
RPU-only setup/source tags, restore stock+DDR, and bind real metadata to filter.
Never run old sole-R5 startup: it resets A53/GEM resources. No PLL or ADMA changes
for diagnostic. No loaded probe may be reported as typed-output MVP deployment.
Full ATF/PMU/R5 closure, safe firewall transitions, relocated output, protected
startup, exact regression and new physical evidence still required for MVP.
Preserve all previous sealed files, failed attempts and S: alias; no commits,
pushes or automation recreation.


## Historical: AMP protection, native firmware and private mailbox milestone (2026-10-16)

LATEST continuation: continue the authorized separate AMP candidate toward readiness.
DEPLOYMENT STILL BLOCKED by composition and qualification gates. Earlier Current
sections below are historical. No target programming/halt/reset/reboot or storage
write by this agent. User power cycle restored SSH at192.168.0.239; saved key
verified and authenticated read-only inventory/boot backup captured. No active
native build remains. Local hw_server may remain; preserve S: alias.

Read first:
- docs/research/2026-10-16-typed200-amp-ownership.md
- docs/research/2026-10-16-typed200-amp-ownership-readiness.json
- docs/research/2026-10-16-typed200-amp-ownership-experiments.csv
- docs/research/2026-10-16-typed200-amp-ownership-validation.json (PASS: all8312
  prior sealed files unchanged;1530 new immutable source/evidence files sealed)
- build/v2/typed200-amp-ownership-v1/failed-attempt-ledger.json (post-seal notes)

Work root build/v2/typed200-amp-ownership-v1. Do not restart completed attempts.
Newest PMU: pmu-staged-v6 + pmu-image-v3; 63 units, SHA256
6f6288ded7e79677d52d697d780dcdd0ba8e8b5c866b6ebae98c1932cbb6cc08.
Native image-v2 is REJECTED: inherited idle sleep could lose a deferred close
wakeup. V3 polls instead; power cost unmeasured. New R5-only custom IPI lease
stages a request and closes PMU dispatch at the main-loop boundary with IRQ
mask preserved. Session-bound status ACK only after closure. 1023 unauthorized
sources +160 malformed-field mutations PASS. All-module guard regression PASS.
ATF remains atf-staged-v3; actual PM/raw-IPI wrappers and retained trusted commit
build PASS. ATF/R5 activation still unjoined; PMU ACK alone must never admit.

New mailbox-v1 PASS: 5120 request-bit mutations, nine matched traces against
actual frozen service/driver/head, R5 object. Private R5 service state; finite
160-word untrusted snapshot, separate 32-word R5-write/APU-read result. One-shot
session, no ingress reads after submission, no cancellation/reuse. Captured word
vector defines request; seqlock recheck does NOT prove atomic capture. Software
trace matching is NOT FPGA cycle equivalence or WCET. Six outcomes unchanged.

protection-plan-v4 remains boot-only,774writes; NEVER apply to live Linux.
Host-v5 PASS plus firewall-v2 encoded oracle:253952FPD +20480OCM +1642496XPPU
cases with deliberate permission/parity mutations. Actual source/security tags,
peripheral TZ configuration, enable-time master quiescence still unqualified.

New ps-profile-v4 generates SOM+carrier PS outputs with GEM0 SGMII and GEM1/MDIO;
no synthesis/place/bitstream/XSA/package. Generated nominal PL0=199.998001MHz,
PL1=99.999001MHz,R5=533.328003MHz, unlike stock live RPLL. native-audit-v2
passes ELF/source/critical PS checks but records18derived MIO direction/drive/
slew differences (electrical compatibility OPEN). Audit-v1 failed strict full
property equality; do not suppress differences or claim full match.

Next: compose trusted ATF closure+PMU ACK+R5 startup; establish trusted initial
state and exact image identities. Define safe pre-Linux/final-lease firewall
transitions; integrate requester filter before USER loss for CSR AND permit;
new hidden-output address62200000 in separate RTL/R5 composition, matched exact
output/counter/cycle/error/drain regression. Actual source tag binding and new
physical setup/hold/DRC/CDC/exceptions at unchanged5/10ns constraints. Build
Linux-compatible startup and finite R5 service with correct mappings/clock
parents; prepare permit-low volatile qualification and recovery. No old sole-R5
boot profile/certificate reuse, no gate bits substituted for proof. Local PL
terminal-by-D after admission is conditional; Accepted-by-D and SSH latency
remain unproved. Preserve qualified200MHz sources/package/recovery/numerics,
all prior seals, failed attempts; no commits/pushes/automation recreation.


## Historical: SSH recovered; native AMP PMU and ATF guards built (2026-10-16)

Continue the authorized separate memory/clock/reset ownership candidate until
readiness gates pass. NOT READY; no deployment, target write, reset or programming.
User physically power-cycled the KR260; SSH recovered at 192.168.0.239 with saved
host-key match. Authenticated read-only inventory confirms KR260 revB, Ubuntu
kernel 6.8.0-1036-xilinx, GEM0 eth1, sysone no-map 60000000..6fffffff and PMU
7ff00000..7fffffff. Prior boot shows CPU2 soft lockups; not a proved outage cause.
UART control 0x114 has RX enabled (corrects earlier interpretation).

New work: build/v2/typed200-amp-ownership-v1. Initial preservation-before.json
verifies 8,312 prior sealed files. Final verification/seal PENDING while work runs.
Read native receipts: pmu-image-v1/receipt.json, atf-staged-v3/receipt.json,
host-v5/receipt.json, protection-plan-v4/plan.json. Completed attempts must not
be restarted. PMU native image: 62 units, prints disabled, commit retained;
ATF 2025.2 pinned 894ecd0737173617c91748dfbcfa1deca7971439 builds natively.
Both guard activation hooks are NOT composed into a trusted boot handshake.
Stock boot A/B read-only backups are identical SHA256
6b8bd7b57656e2ed80b51687bb25e2cc0eacb623f628480ae3ecaa9a2abb8216.
Stock FSBL/PMU2022.1, ATF2.6 ec5dccc32, U-Boot2022.01; do not replace casually.

Candidate sources firmware/typed200_amp_ownership and new scripts/v2 AMP helpers.
Host-v5: 921600 PM API cases, 860160 DDR oracle cases, 775 observable fault
injections PASS; native R5/PMU objects PASS. PMU bridge all-module IPI/event/
scheduler guard and IRQ-preserving main-loop commit PASS. ATF PM + raw IPI
wrappers close direct RPU/TCM IOCTL bypass; 65536 FIDs +9216 IPI cases PASS.
Next strengthen FPD/XPPU semantic tests, audit native linked guards, implement
trusted serialized activation/ACK, Linux-compatible boot/PS startup and bounded
R5 mailbox. Full protection plan is boot-only with all affected masters quiescent;
NEVER apply its 774 writes to live Linux. Caller-set gate bits are not proof.

New hidden output allocation 62200000 requires new RTL/R5 pointer composition
and exact-output/cycle regression; parent 62101000 remains frozen. Need requester
filter integration before USER loss, actual R5/HP0 source/security binding, timing/
DRC/CDC/exceptions, and target negative-access qualification. Existing sole-R5
PS configuration disables Ethernet; existing 533328000 Hz R5 timing certificate
is incompatible with observed stock RPLL. Do not reuse either for AMP. No new
bitstream/package, board action, commit/push or automation recreation. Local
terminal-by-D is conditional on uninterrupted protected guard clock/reset;
Accepted-by-D and SSH-delivery timing remain unproved. No native build running;
local hw_server may remain active. Preserve S: workspace alias.


## Historical: separate AMP access-filter candidate verified; JTAG connected (2026-10-16)

Latest user confirms Ethernet connected to router, board IP unknown. JTAG is
now available; proceeding with read-only inventory and separate local AMP
candidate. NO target halt/reset/program/reboot/deployment or persistent write.
No commits/pushes; automation remains PAUSED. Qualified 200 MHz baseline and
all prior sealed evidence preserved. Prior feasibility section below is historical.

Read first:
- docs/research/2026-10-16-typed200-amp-candidate.md
- docs/research/2026-10-16-typed200-amp-candidate-readiness.json
- docs/research/2026-10-16-typed200-amp-candidate-validation.json (new anchor)
- build/v2/typed200-amp-candidate-v1/preservation-before.json

New separate RTL: rtl/v2/candidates/typed200_amp/control/typed200_requester_filter.sv.
Default deny-all; optional secure RPU0 32-bit single-beat CSR+permit access.
Full AXI before USER/PROT metadata loss; independent AW/W capture, complete
declared rejected bursts, sticky faults, no timeout cancellation. NOT integrated.
2,189 simulation transactions PASS including all1024 low source IDs read/write.
New induction proofs PASS for ENABLE_R5=1 and0, length2: access restrictions,
AW/W/AR stalled stability, exact rejected burst counts, sticky fault and local
response properties. First sampled reset assumed; source provenance, downstream
compliance, liveness, physical isolation/timing are NOT established. Formal v1
frontend failure preserved; v2 fixed lowering, no assertions weakened. New
scripts scripts/v2/{check,prove}_typed200_amp_filter.py. Do not rerun completed
attempts; use a fresh numbered directory for changed work. No Vivado build yet.

JTAG cable XFL14EBBE1U3A enumerates xck26/arm_dap; XSDB A53#2 Running, R5s
No Power, A53#3 debug APB error; no cause/fault inferred. Enumeration is NOT
tested recovery. Local hw_server TCP3121 launched; PID/log receipt in candidate.
COM9 passive115200 and CR-only probe silent. Historical192.168.0.239 replies
Ubuntu SSH banner then stalls at key exchange; no saved host-key match, password
authentication or remote commands. Only port22 found in bounded local subnet
scan. Native stuck SSH client terminated locally. PC192.168.0.152/24. Actual
board kernel/DT/ATF/PMU/PS/GEM still unpinned. Never authenticate to an unverified
new address or force target reset to obtain inventory. Candidate inventory helper
uses saved known_hosts and fixed read-only commands; candidate cffi fixes Python
ABI mismatch without modifying frozen helpers. No credential saved.

Next: authenticated live platform inventory/recovery; Linux-compatible PS
topology and actual R5 USER/PROT review; integrate filter without bypass; enforce
DDR/TCM/DMA and selective PMU/secure/MMIO clock/reset ownership; separate bounded
R5 one-shot mailbox/service; compose matched numerical/control regressions and
new physical STA/DRC/CDC/exception evidence; then supervised readiness review.
Existing sole-R5 PS init disables Ethernet and blanket PMU seal conflicts with
Linux; DO NOT deploy that image for AMP or remove checks/reuse its certificate.
Local canonical typed terminal byD after admission is the intended conditional
guarantee. Accepted-byD, SSH delivery and timeout buffer reuse remain unproved.
No native build or remote command remains running; only local hw_server daemon.
Preserve S: alias; do not recreate old experiments or automation.

Prepared after the 200 MHz hardware milestone, reviewed 2026-10-15 UTC.

## Historical: A53 Linux/SSH + R5 ownership feasibility reviewed (2026-10-16)

Latest user asks whether Linux/SSH can remain on one A53 while R5 exclusively
owns FPGA inference with typed-output timing; investigate, preserve baseline,
DO NOT DEPLOY. Investigation COMPLETE; no AMP firmware/RTL candidate implemented.
No board contact, native FPGA/toolchain build, proof/simulation restart, image,
programming, deployment, reboot, commit or push. Automation remains PAUSED.

Read next:
- docs/research/2026-10-16-typed200-amp-feasibility.md
- docs/research/2026-10-16-typed200-amp-experiment-plan.md
- docs/research/2026-10-16-typed200-amp-ownership-matrix.csv
- docs/research/2026-10-16-typed200-amp-policy-draft.json (NONDEPLOYABLE)
- build/v2/typed200-amp-feasibility-v1/source-audit.json
Final preservation anchor:
`docs/research/2026-10-16-typed200-amp-feasibility-validation.json`.
All8204 previously sealed repository files verified unchanged before/after.
Prior K26 boot-chain anchor/evidence is preserved and remains NOT target-ready.

Finding: coexistence is architecturally feasible for the conditional LOCAL PL
terminal deadline after admission. Unbounded DDR/R5 delay can yield Deadline
without extending D, given uninterrupted guard clock/reset and protected state.
This does NOT guarantee Accepted-by-D, pre-admission/Linux queue latency, SSH
result delivery, or SSH recovery through every shared-system fault. Exact
Accepted inference needs encoder/drain/hidden-copy/head/proposal service bounds.
Deadline quarantines; does not cancel AXI or permit early buffer reuse.

Current v5 explicitly requires all A53/GEM resets and one preloaded request.
Existing PMU seal denies every normal IPI; not a Linux-compatible selective
resource policy. Actual HWH control SmartConnect has16-bit AR/AWUSER at full
AXI input, ZERO USER at both Lite outputs; actual wrapper has no origin check.
Need requester filtering BEFORE conversion for CSR AND permit/config/ACK.
Actual standalone HWH disables ENET0..3. New AMP cold boot needs a real Linux/
network/boot-device PS configuration; loading a PL-only overlay is distinct
from running this standalone PS initialization. No cause of prior outage inferred.

Audit confirms final gate logic matches existing proved source modulo comments/
whitespace. Existing RTL proof is NOT a new physical/AMP isolation proof.
Pinned inspected primary Linux sources at AMD linux-xlnx commit
31626ef92ff11f9d3dee01926720572666fcc65a (2025.2 reference; live board kernel UNKNOWN).
Actual remoteproc can stop/release R5/TCM; FPGA manager can reload PL; no-map is
allocation, not a firewall. AMD XAPP1353 documents preserving MasterID/AxUSER
and PL protection; reference archive attempt returned HTML, no VHDL audit.
All source hashes/lines, snapshots and failed attempts retained in new build dir.

Recommendation: separate ONE-SHOT AMP candidate first. One A53 Linux/SSH;
R5_0 trusted startup/service/head; hardware-protected inference/control and
platform policy; bounded ingress/private snapshot; independent result mailbox.
Do NOT simply remove all-A53/GEM reset checks or reuse old certificates.
Ranked plan: actual PS/kernel/network inventory; explicit ownership/PM policy;
requester filter; memory/TCM/DMA enforcement; R5/mailbox adaptation; composed
proof + new STA/DRC/CDC; then supervised passive-capture AMP qualification.
Accepted rate/interference bounds follow; external network delivery remains
outside the frozen deadline contract. Cooperative Linux bring-up must be
labelled diagnostic/Linux-trusted, not enforced exclusive ownership.

No current deployment readiness. Independent JTAG/serial recovery remains
unverified (user previously had SSH only); dedicated boot/management policy
still needs a verified launch route. AMP keeps management configured after
startup but does not resolve fixed-QSPI/cold-POR provisioning by itself.
All policy-draft enforcement/address/allowlist fields deliberately unverified.
No native job is running or needs resuming. Preserve the existing S: repo alias
and all completed experiments; do not recreate automation or old jobs.

## Prior local milestone: K26 boot chain built; physical launch gates open (2026-10-16)

Latest user authorized dedicated FSBL/PMU/configuration builds and relay memory
validation, preserving the baseline and working toward deployment only after
readiness passes. All work is local; no board contact, deployment, reboot,
persistent-media/security write, commit or push. Automation remains PAUSED.

Read next:
- docs/research/2026-10-16-typed200-k26-boot-chain.md
- docs/research/2026-10-16-typed200-target-qualification-profile-v3.json
- build/v2/typed200-k26-boot-chain-v1/preparation-assessment-v3.json
- docs/research/2026-10-16-typed200-k26-boot-chain-validation.json
  (new final preservation anchor; verify it exists and all hashes before resuming)

New sources firmware/typed200_k26_boot; generated candidate
build/v2/typed200-k26-boot-chain-v1. Actual FSBL/PMU ELFs/maps, effective macros,
linked 1744-byte PM config, final disassemblies and local typed bitstream built.
Read-only XSA PS init/HWH exactly match frozen typed hardware metadata. Native
builds use actual cwd S: (existing repository alias; DO NOT remap), AMD 2025.2
Vivado empyro with matching Vitis embeddedsw, candidate-local checksum-verified
Arm GNU13.3.rel1. Vitis platform RPC/path/missing-compiler failures retained.
Do not restart failed platform generation, old RTL experiments or automation.

Final FSBL hook validates cold-POR, A53_0 EL3/64, exact DDR relay entry,
permit-low/drained ABI, RPU power/reset/AMBA and CSU idle. Waits PMU common
completion, then fresh-session one-way seal. PMU commits only after active
scheduler callbacks return, masks interrupts for commit/ACK, uses volatile ISR/
main state under LTO; rejects ordinary IPIs/events/callbacks afterward. K26 EM/
90C thermal shutdown remains active. Trusted boot/debug scope, NOT adversarial
hardware isolation; startup vendor power-up poll unbounded before admission.

479 policy cases + transition checks PASS; actual PMU C integration PASS;
actual FSBL hook success +23 fault cases PASS (ASM/MMIO/SDK mocked);
474 existing typed capture/trace/PMU/MVP/qualification tests PASS.
Bitstream export ONLY from frozen routed DCP: unchanged5/10ns clocks,
+.048ns setup/+.011ns hold, zero DRC errors. No physical implementation edits.
Final local layout image image-layout-v2/BOOT.bin SHA256
c93796b59f58f41e0f34d8492e6e4821037a3fe9e243dfb9d36bd9540c4c559b,
41996956B; independent actual-header/checksum/payload/range audit PASS.
All artifact roles now present; local static reviews do not authorize hardware.
The relay [10000000,10100000) allocation is statically validated for this exact
image. No claim of measured target access permissions or hardware reservation.
Retain image v1 and initial binary/sealing snapshots as superseded attempts.

DEPLOYMENT NOT READY. User says SSH ONLY now; will arrange JTAG at home.
No independent recovery is verified. KR260 preset QSPI primary boot means an SD
BOOT.bin alone does not launch this dedicated chain. AMD volatile SD/JTAG mode
override uses system reset, rejected by frozen cold-POR predicates. Establish
and review a real cold-POR debug interception/launch route on actual hardware;
do NOT clear reset history, relax predicates, chain from Linux/U-Boot, write
QSPI or infer physical readiness. Physical power/permissions/debug checks remain
open; current profile has no target run receipts. Need passive completion
observer and measured bounds before clean timing/WCET claims. Debug snapshots
remain diagnostic. No claim of 300MHz or target-qualified typed MVP.

Next: verify preservation anchor; await connected independent recovery and
identify exact target/cold-POR interception before any target action. Then stage
functional diagnostics under the qualification procedure, with fresh sessions.
Current local image uses [101,102], pool0/count1,budget1: Deadline-if-admitted
fixture, NOT successful classification. No new native build needs resuming.

## Completed: boot ownership review, qualification plan and local DDR relay (2026-10-16)

Latest user authorization: review FSBL/PMU/CSU/debug ownership, prepare exact
target qualification, preserve baseline and progress toward deployment once
prerequisites ready. Review/procedure COMPLETE; also implemented/tested a separate
DDR relay to address the discovered FSBL/OCM overlap. Deployment remains NOT
READY. No target contact/execution, FPGA build/bitstream, boot image/package,
board programming/reboot, QSPI/eFuse/security lock write, commit or push.
Overnight automation remains PAUSED; no old jobs/reports restarted/overwritten.

Read, in order:
- docs/research/2026-10-16-typed200-boot-ownership-review.md
- docs/research/2026-10-16-typed200-target-qualification-procedure.md
- docs/research/2026-10-16-typed200-ddr-relay-preparation.md (follow-up supersedes
  earlier statement that no relay exists and changes producer input to DDR)
- docs/research/2026-10-16-typed200-target-qualification-profile-v2.json

FINAL current preservation anchor:
`docs/research/2026-10-16-typed200-boot-preparation-validation.json`.
Prior review seal `2026-10-16-typed200-boot-ownership-validation.json` preserved.
All prior sources/package/recovery/numerical/route/MVP/review evidence verified
unchanged. Do not edit mapped files; handoffs remain editable.

Concrete review findings: both frozen A53 LOAD segments overlap installed FSBL
reserved OCM [fffc0000,fffe9e00); ordinary direct application load prohibited.
Actual dedicated FSBL/PMU binaries/macros/config missing. PMU has wake/reset/
clock/FPGA/CSU-DMA paths; source defaults are not the target policy. Preserve
K26 EM/overtemperature/board protection. Generated protection-lock function has
no lock writes; no hostile-master isolation claim. CSU must be drained AND
prevented from starting new work. Debug snapshots/breakpoints are diagnostic;
no reviewed passive completion marker currently exists for clean timing runs.
Ethernet/SSH WILL be intentionally lost when GEM/A53 are held reset in this
profile; independent serial/debug recovery is prerequisite, not yet demonstrated.
No assertion about the cause of the user's earlier board outage.

Review evidence `build/v2/typed200-boot-ownership-review-v1`:24 pinned installed
AMD primary files; source-default macro examples explicitly stub/nondeployable;
actual frozen C20-rule/131-bit table exported; both OCM overlaps detected from
actual ELF. Offline artifact/review completeness gate added with stale/foreign/
diagnostic evidence rejection.510 tests PASS; never claims hardware authority,
provenance, continuous ownership or WCET from metadata.

Separate relay `firmware/typed200_boot_relay`, build
`build/v2/typed200-boot-relay-v1/relay.elf`, SHA
8dd7e84b00637220bf7d3e488c6c57c73cb24d6cf5764eef536c3e44aa7f08b5.
Entry10000000, RX35548B; RW/NOLOAD16KiB stack100c0000; proposed DDR reservation
[10000000,10100000) NOT yet proven against actual FSBL/scratch/partition maps.
Producer448B input100f0000, status100f1000. Relay installs unchanged A53 input
fffee000 only AFTER final same-core FSBL exit; no returning/resuming FSBL.
Checks cold POR/peer resets/permit/typed idle/CSU idle/PCAP/input identity,
validates all OCM ranges/overlaps before copying, byte-verifies frozen A53 payload
and zero stack/input, DSB/IC IALLU/ISB then branches to frozen A53fffc0000.
No PS clock/reset/security writes. Status2 means copy/transfer issued only.
Actual relay C UBSan host tests PASS70 single-bit precondition faults,
786432 range checks, malformed/warm/permit/corrupt-copy rejection. Cross-linked
ELF no W+X/unresolved or linker warnings; privileged instructions NOT executed.
Original v5 R5/A53 payload/numerics/cycles unchanged; no target/WCET claim.

Current profile-v2 offline gate still FALSE with SEVEN missing artifact roles:
FSBL, PMU, actual FSBL macros, actual PMU macros, PM config object, typed bitstream,
and volatile boot recipe. All real preparation/target acceptance receipts open.
NEXT LOCAL: build/audit dedicated K26 FSBL/PMU/BSP/config, verify complete memory/
scratch map admits relay reservation and final handoff peer/cache conditions;
close ordinary PMU mutation/CSU/permissions policy and recovery/passive-observer
requirements. Then prepare exact recoverable volatile target images and execute
staged qualification. User's conditional deployment intent persists; do not ask
again merely to do authorized reversible preparation, and do not touch the board
before readiness/recovery conditions are actually met. No deployment underway.

## Completed locally: typed-output ARM ownership MVP (2026-10-16)

Latest user request COMPLETE within the authorized no-deployment boundary.
Separate candidate: `firmware/typed200_mvp`; final local build/test
`build/v2/typed200-mvp-host-v5`; native ELF/source/preservation review
`build/v2/typed200-mvp-review-v1`. No ARM target execution, bitstream, boot image,
package, board access/programming/deployment/reboot, RTL edit, Vivado build,
commit or push. Overnight automation remains PAUSED, not recreated/restarted.

Implemented A53_0 EL3 OCM startup/handoff and R5_0 reset-entry supervisor with
split TCM/ECC, low vectors/banked stacks/VFP, narrower MPU permissions, owned
full-rate PMU initialization and the frozen typed service/head. Selected profile
is COLD BOOT, R5_0 sole active application core, one preloaded request then
terminal park/permit low. All A53 cores self/peer-reset, R5_1 reset/halted,
competing DMA peripherals held reset, DPDMA clock gated. Preserve encoder AFI
and PL reset/clock. R5 independently observes all A53 resets and20 ownership/
clock/GPIO rules before any admission and before each service poll. Sticky
fault attempts permit-low/park; no automatic healing. PMU/CSU/trusted producer/
debug/other PL masters remain explicit trusted-quiescent prerequisites.
This is NOT malicious-master isolation, a live A53/Linux client, or WCET.

Final local evidence PASS: actual portable ownership/supervisor C under ASan/
UBSan; all131 monitored bit inversions sticky rejected,786432 segment checks,
DMA done/error/timeout and reset/config faults. Frozen head647 fixtures reproduce
all51760 golden output bytes exactly. Frozen service/driver/PMU regressions pass;
467 Python tests pass including new parked-MVP snapshot consistency gate.
Actual A53 handoff C executed with mapped mock TCM/OCM plus UBSan verifies load/
NOLOAD/config ordering, payload readback, R5 release-before-self-reset, denied
self-reset and malformed/session-mismatched/warm boot failures. Neither host
model executes privileged ARM instructions. Actual R5/A53 ELFs audited: correct
entries0/0xfffc0000, no unresolved or W+X load segments, exact TCM/OCM fit and
shared/config/evidence symbols. Four documented intentional PROGBITS->NOLOAD
NOBITS linker warnings retained; no warning suppression. Failed harness attempts
v1-v3 retained; superseded passing v4 sources recovered exactly against hashes.

Final report `docs/research/2026-10-16-typed200-arm-ownership-mvp.md`.
FINAL preservation anchor:
`docs/research/2026-10-16-typed200-arm-ownership-mvp-validation.json`.
All2811 prior files, including prior route seal, verified unchanged; sources,
ELFs, snapshots, tests, failed attempts and report hashes bound. DO NOT edit
mapped files or rerun completed directories. Both handoffs remain editable.

MVP final mailbox boot_status=2, permit0; frozen legacy decoder expects status1.
Use separate `sysone.v2.typed200_mvp.assess_mvp` with final shared/boot/owner/
permit plus pre-ACK trace/PMU evidence. It checks consistency only, never target
provenance/continuous hardware exclusion/frequency/WCET. Configuration-derived
R5 nominal533328000Hz and PL0199998000Hz follow declared33.333MHz reference;
qualified board's measured199999998Hz is separate evidence, not calibration for
this candidate. Extra ownership polls change ARM cost; no unchanged ARM-cycle
claim. Software loop limits do not bound a stuck MMIO or stopped clock.

NEXT: review exact trusted FSBL/PMU/CSU/debug/power/permission profile and later
obtain separately authorized recoverable target qualification: ARM startup/ECC/
MPU/reset/master captures, fault campaign, clock calibration, target head goldens,
phase captures and justified DDR/MMIO/ARM service bounds. No target gate is
closed by local evidence. No new deployment/build/automation is authorized or
pending from this completed local task; do not infer permission to deploy.
The routed carry-save typed design remains unqualified on hardware; the original
qualified 200MHz baseline/package/recovery/numerics are untouched.

## Completed: timing-only carry-save routing (2026-10-16)

Latest user request COMPLETE. Reviewed CSA checkpoint routed in a new standalone
directory with unchanged constraints. Final 200 MHz STA **+0.048 ns setup /
+0.011 ns hold**, all123430 routable nets fully routed, zero unrouted/overlap/
routing-error nets. All12 check-timing categories zero; CDC safely timed.
No bitstream/package, hardware deployment/programming/reboot, commit or push.
Qualified baseline sources/package/recovery/numerical and every prior seal intact.
Overnight heartbeat remains PAUSED; no automation restart. No native job remains.

Input: `build/v2/typed200-row-range-csa-physical-v1/place/placed.dcp`, SHA256
c5ebe28f029ba9490fb146bac93a9139fbee403c5b78a94ed9a76fbbf7f2eb5e.
The reviewed +0.506 ns placed setup cleared unchanged +0.500 ns gate by6 ps.
Exact copy opened standalone in `build/v2/typed200-row-range-csa-route-v1/input`;
sealed project never opened/saved. Default phys_opt_design then route_design,
max4 threads, no retiming/clock/source edits. New final output route-v1/routed.dcp.

Exact scoped timing-command multiset and timing properties match input/output:
two5 ns/10 ns clocks and39 vendor XPM reset/synchronizer false paths; vendor
source/scope records unchanged. All2770 prior preserved paths reverified unchanged.
DRC has ZERO errors/critical warnings, NOT zero warnings:644 DPIP-2 +6 DPOP-3 +575
DPOP-4, plus one RTSTAT-10 warning covering197 no-routable-load nets (only first15
listed). All routable nets routed; these are not unrouted loads. Methodology64
DPIR-2 DSP asynchronous-driver advisories, no LUTAR-1; FIFO async-reset FF count0.
No RTL/reset/pipeline change was made to silence warnings.

Final routed resources63192LUT/52748FF/579DSP/50BRAMtiles/36URAM, same as placed.
Router summary setup+0.046 ns was provisional; final full STA and path query both
+0.048ns. Hold+0.011ns. Versusplace, setup-0.458ns/hold+0.084ns. Tight single-run
closure only, NOT Fmax/300MHz, board qualification or useful-success WCET.
Actual routed setup worst now memory SmartConnect read-state[3] -> linear
weight_reg[1][7][12][5],4.728nsdata (0.196logic/4.532wire,95.855%wire), oneLUT2,
skew-0.139ns/uncertainty0.129ns. State netfanout142 then m_axi_rdata[101]fanout156,
last wire3.498ns. Placement softmax-shift worst is NOT routed worst.
Hold worst attention query-distribution group2 data[68] -> query[11][1][8][4],
0.245nsdata, zero logic levels,0.131nsclockskew. Do not assume arithmetic depth
alone is the next timing limit; AXI data distribution/locality now has evidence.

Run/review session30266 COMPLETEexit0. Original route-review.json preserved;
review-final receipt is `route-review-final.json`. First sealer found reviewer's
self-console hash taken before final print; ONLY metadata repaired separately.
Original helper/receipt unchanged, all native evidence unchanged. Failed sealer
snapshot/hash mismatch saved route-v1/sealing-attempt-v1; finalizer and v2sealer
preserve it. No reroute or check weakened. Final v2 sealer COMPLETEexit0.

Read FINAL frozen `docs/research/2026-10-16-typed200-row-range-csa-route.md` and
`docs/research/2026-10-16-typed200-row-range-csa-route-validation.json`.
All route artifacts/helpers/report/prior hashes are bound. DO NOT edit mapped
files; handoffs remain editable. Do not restart any completed runner/proof/build.

NEXT recommendation ONLY: target startup/reset/clock/master ownership and
justified DDR/MMIO/ARM service bounds plus typed-output captures for the MVP.
Routed closure is not target qualification or permission to create a bitstream.
Prior deployment inventory is a sealed historical draft, not a promoted CSA
profile. Any future AXI-locality/capture change must explicitly prove handshake,
outputs/counters/cycles and revise deadline budgets if latency changes.
No additional experiment, bitstream, deployment or ARM target action started.

## Completed: typed row-range narrowing (2026-10-16)

Latest human request COMPLETE: separate candidates, all raw valid/invalid input
proofs, unchanged outputs/cycles, matched timing probes, conditional full
synthesis/placement and native audit. No active native job or pending pipeline.
Overnight heartbeat `system-one-overnight-predecode` remains PAUSED; not restarted.
No routing, bitstream/package, board programming/deployment/reboot, commit or push.
Qualified 200 MHz sources/package/recovery/numerical and previous seals preserved.

Preferred characterized candidate: `rtl/v2/candidates/typed200_row_range_csa`,
independent descendant of sealed predecode. ONLY contracts/typed_intent_axil.sv
changes: explicit raw high-bit rejection, XOR/majority carry-save A+B+~T test
preserving BOTH high carries, no new state/cache/cycles or live permission.
Actual-source SAT proof covers ALL2^64 raw shape/count encodings, no legal-input
assumptions. Full endpoint temporal induction PASS in2steps: external outputs,
bank/written masks/bus/guard state/profile flags/shape match under arbitrary
AXI addresses/data/strobes/split writes/commands/backpressure/core signals and
later resets. Only first sampled reset/single clock/two-state assumptions.

Independent frozen-parent ADD_SKIP AND encoder_layer full regression PASS:
5400goldenwords/14pairedcompletions/14launches, exact outputs/counters/AXI/busy/
donecycles, normalT1..128 and faults. T1287961537encoder/7966029request cycles,
emulated publicationage7966096. Hostsimulation444.320s is NOT ARM timing/WCET.
Matched whole endpoint probe overall+1.595->+1.743ns (+0.148), shape-source
+1.595->+2.313ns (+0.718); levels11->7, LUT1026->1009/FF1815unchanged.

Full synthesis/source-clock review COMPLETE: 30staged/28compiled hashes, explicit
5ns OOC clock beforeoptimization, actual5ns/10nsfullclocks/noOOCleak. Full
68296LUT/53376FF/579DSP/50BRAMtiles/36URAM, estimatedsetup/hold+0.624/-0.087ns.
Versuspredecode -203LUT/-11FF, setup-0.004ns: no global synthesis timing gain.
Full placement/native audit COMPLETE: **+0.506/-0.073ns** setup/hold,
63192LUT/52748FF/579DSP/50BRAM/36URAM. Versuspredecode setup+0.057ns,
hold+0.081ns, -191LUT/-64FF. Setup clears unchanged+0.500ns route gate by ONLY
0.006ns. Gate review route_approved=true means timing-only eligibility;
**routed=false**, negative placed hold unresolved, no routed closure/qualification.
Single-run comparison is not robust margin, throughput gain, WCET or300MHz proof.

Actual global worst: instruction bit130 (softmax_shift[2], word1) -> attention
lane11 e_index[24], 4.285nsdata (1.147logic/3.138estimatedwire,73.232%wire),
9levels/4CARRY8, skew-0.124ns/uncertainty0.129ns. Shape-source worst now+1.010ns,
no longer global bottleneck. Native selected minima: predecode+1.996,
product+0.965, rounding+0.819, output FROM clampedskip+0.916, profileflags+1.080.
Output query source-restricted, not all residual/control sources. All12 timing
checks0, CDCsafe,39vendorXPMexceptions only, epoch/publication/permit/GPIO and
32profileflags/128clampedskip/bias/product retained, no LUTAR/FIFOasyncreset issue.

Pipeline session52782 COMPLETEexit0 (seven commands); sealer6713 COMPLETEexit0.
Physical `build/v2/typed200-row-range-csa-physical-v1`; orchestration receipts
`build/v2/typed200-row-range-csa-pipeline-v1`. Read FINAL immutable report
`docs/research/2026-10-16-typed200-row-range-csa.md` and final seal
`docs/research/2026-10-16-typed200-row-range-csa-validation.json`.
All2604 prior preserved paths unchanged; actual WSL staging rehashed. DO NOT edit
mapped candidate/helpers/report/evidence. Handoffs remain editable.

Earlier direct-sum attempt `typed200_row_range` also fully proved/regressed:
5400words/14cases, but probe+1.595->+1.292ns (-0.303ns); fewer carry cells but
wire delay outweighed logic improvement. NO fullbuild; rejected and sealed,
2491priorpaths unchanged. Its arithmetic-v1 missing chformal-lower tool failure
is preserved; v2 passed. Read frozen -row-range.md / -row-range-validation.json.
The CSA report clarifies the direct report's ambiguous closing "no native job"
sentence means no FULL implementation job: native probes/regression did run.

NEXT recommendations ONLY: timing-only route of exact reviewed DCP (narrow6ps
margin, require routed setup/hold/DRC/CDC/exception checks), then prioritize target
startup/clock-reset-master ownership/service bounds and typed-output captures.
All13 existing deployment gates unresolved. No target ARM/WCET/external-delivery
claim. A future softmax shift/rounding predecode/fanout experiment must prove
word1 freshness/history/alignment and exact finite-width rounding; not implemented
or scheduled here. Do not reuse ADD_SKIP word0 assumptions for word1.

## Completed predecode experiment; overnight follow-up paused

[Detailed predecode report](2026-10-16-typed200-predecode.md) and immutable
`2026-10-16-typed200-predecode-validation.json` record the COMPLETE experiment.
Proof of actual sequencer/cache/freshness/stability/valid history and wiring
composition PASS; whole-domain arithmetic / 886 conditional engine points PASS.
Independent frozen-parent ADD_SKIP and encoder_layer regression PASS: 5400 words,
14 paired completions/launches, unchanged outputs/counters/AXI/busy/done cycles.
All 2291 prior preserved paths unchanged; actual staged inputs rehashed.
All mapped sources/report/evidence are frozen. HANDOFF remains editable.

Matched all-stage probe gain +0.015 ns admitted requested full synthesis/placement.
Exact source/clock review PASS. Full placed setup/hold **+0.449/-0.154 ns**,
63383 LUT / 52812 FF / 579 DSP / 50 BRAM tiles / 36 URAM.
Setup gains 0.032 ns versus profile_cache, but misses +0.500 ns routing gate by
0.051 ns; hold worsens 0.082 ns. **Route held; never route/promote this checkpoint
or relax constraints.** Single-run estimated placement is not 300 MHz closure.
Native checkpoint audit COMPLETE: all 12 timing checks zero, CDC safe, 39 vendor
XPM exceptions only, all required register retention checked. Selected predecode/
product/rounding paths +1.572/+0.700/+0.640 ns; output query FROM skip-clamped
registers +1.373 ns, not a minimum over every output source.

Actual global critical path is typed row-range shape/admission, bank5 first-row
bit1 to encoder-system state CE: 4.153 ns data, 13 levels/4 CARRY8, 60.679% wire.
Next recommendation ONLY: narrow bounded row-range arithmetic with explicit
high-bit rejection; prove equality across every raw valid/invalid/overflow
encoding and endpoint partial/split writes/reset before regression/physical work.
No next candidate started. Timing-guaranteed typed outputs still require target
startup, clock/reset/master ownership and justified service/delivery bounds.

Pipeline-v2 session23019 and final sealer69155 exited0; no native jobs remain.
Heartbeat `system-one-overnight-predecode` PAUSED upon completed experiment before
08:00 Central cutoff. Do not restart v1/v2 or repeat proof/probe/simulation.
Qualified 200 MHz baseline/package/recovery/numerical and all previous seals
preserved. No board IO, new bitstream/package, reboot, commits or pushes.
See HANDOFF.md for exact continuation state and report for failed attempts.

## Earlier completed experiments (historical next-step notes superseded above)

NEW [stage-clamp experiment](2026-10-16-typed200-stage-clamp.md):proofPASS
all26bitproducts/64shifts/16bitresiduals andfullengine/stagerelation, noexternal
cyclechange. BOTH-stageprobeCOMPLETEwithregisteredinputcontrolshell:outputslack
+1.872->+2.840ns butroundingslack+2.159->+1.259ns;overall+1.872->+1.259ns.
**DoNOTfullbuild/promote**;incoming shiftcontrol isnewlimit. Fullindependent
regressionCOMPLETEPASS5400words/14pairedcompletions/14launches,allnormal/fault
casesandexactoutputs/counts/cycles. Pipeline6270COMPLETE,probeheld,no fullbuild.
Nojobs/boardIO/automation. Immutable2026-10-16-typed200-stage-clamp-validation.json
bindsproof886points/regression/actualstagedrehash/probe/report/MVPnote andall
priorsealedpreservation. SeeHANDOFFfornextinstruction-localpredecodeexperiment;
needssequencerstability/compositionalproof,NOTimplemented. Don'teditmappedfiles.
[MVP readiness](2026-10-16-typed200-mvp-readiness.md) recordsconditional5–10
focusedengineeringdayplanningestimateforsupervisedboarddemo,lowconfidence;
successful-inferenceWCETnotdateduntilservicebounds/ownershiparejustified.

Current separate experiment: [same-stage ADD_SKIP clamp](2026-10-16-typed200-clamp.md).
Entire26bitrounded/16bitresidual domain proven; fullengine966equivalencepoints
proven. Newreference separatelyrenamesfrozenparentADD_SKIP/encoder_layer. Full
regressionCOMPLETEPASS5400words/14pairedcompletions/14launches,allnormalT1..128
andfaultcases, exacteverycyclecounts/AXI/outputs. Nojobsremain.
Matched5nswholeengineprobeCOMPLETE:slack+1.872->+1.698ns, LUT2867->2739,
FF877unchanged,CARRY8cells192->152. Worstdata2.964->3.137ns; logicimproves
0.104ns butestimatedwireworsens0.277ns. **DO NOTPROMOTE; NOFULLPHYSICALBUILD**.
Preservefailedproof/toolattempts. PipelineCOMPLETEexit0,probehelddecision;
nofullsynth/place/route/bitstream/package/targetIO. Immutable
`2026-10-16-typed200-clamp-validation.json` bindscompletedexperimentanddraftprofile;
actualstagedinputs rehashed,allpriorsealedpaths unchanged. DoNOTeditmappedfiles.

Concrete [deployment inventory](2026-10-16-typed200-deployment-profile-draft.json)
bindsactualqualifiedencoderarchiveanddistinctunqualifiedtypedplacedDCP/R5ELF,
sources/ABI.13targetgatesexplicitlyunresolved,deployment_ready=false.
Nextarchitecturalprobe: movefirstclampintoexistingroundingregisterstage, preserving
26bitroundingandcycles, provechangedstagerelation, checkbothstagecriticalpaths.
ThisnextvariantNOTimplemented. Targetownership/bounds/captures remainfirstproduct
priority; inventoryisnotcombinedqualification/WCETevidence.

COMPLETE architecture experiment: [bank-local profile cache](2026-10-15-typed200-profile-cache.md).
SeparateAXIL/guard changes mirror full256bitSHA with32byteequalities. Fullendpoint
sequentialproofPASS;5400word/14pairedcompletion fullmodelregression PASS with
every-cyclecounts/AXI/outputs unchanged; actualstagedinputs rehashed. Immutable
functionalrecord fixesexactcandidate/proof/sim. Fullsynthesis/source-clockreview
COMPLETE:68510LUT/53430FF/579DSP/50BRAM/36URAM, estimated+0.589/-0.087ns.
Comparedcontrol+12LUT/-221FF, no overallsynthesisgain; newestimateAXI deliverycounter
toSmartConnect AWFIFO in synthesis only. Fullplacement/audit now COMPLETE:
**+0.417/-0.072ns**,63456LUT/52768FF, unchanged579DSP/50BRAM/36URAM.
Single-run setup gain0.046ns overmatchedcontrol; routeHELD below+0.500ns.
32cachedFF retained,rawprofilebankFF0;cache-originworst+1.243ns. Newactualworst
ADD_SKIP rounded->out saturation,10levels/6CARRY8,4.219nsdata(65.2%estimatedwire).
All12checks0/CDCsafe/39vendorXPMexceptions/noLUTAR/FIFOasyncreset0. Nojobsremain.
Finalimmutable `2026-10-16-typed200-profile-cache-validation.json` fixesphysical
sources/report/evidence andpreservespriorrecords. User's "restart" clarifiedas
resumeourwork; no board/build/apprestart orhardwareprogramming occurred.

Next [ranked experiments](2026-10-16-typed200-next-experiments.md): typed deployment
profile/master exclusion/targetcaptures/bounds first; preserve-stage ADD_SKIP
clamp candidate andfullengineproof/mappedprobe beforeanotherfullphysicalrun.
IndependentparentADD_SKIP/encoder_layer mustbeaddedtoregressionreferenceforan
arithmeticchange; currentAXIL-onlyrunner appropriatelyshares thosemodules.
Noarithmeticcandidateimplementedyet; doNOTclaim300MHz,targetWCET ornewqualification.

Newest milestone: [timed PMU diagnostic provider](2026-10-15-typed200-timed-provider.md),
immutable `2026-10-15-typed200-timed-validation.json`. Separate platform/loaderconfig
binds checked fullrate R5counter, stickyfaults and72B evidence; noPMUwrites.
396tests plus PMUsanitizerfaultcases pass;49pairedpollrecords exactlyfrozencontrol.
ARMELF18160Bcode/51216BBSS/2032Bspare; original384Bmailbox+32Bconfig NOLOAD416B.
Offline phaseobservations are mock-tested conditionalcycles/nominalns, NOT target
measurements/WCET.1683preservedpaths unchanged; no jobs/targetIO/programming/Vivado.
HANDOFF.md details next typedphysicalmargin experiment and remainingtargetgates.

Newest milestone: [separate owner-local R5 trace](2026-10-15-typed200-owner-trace.md),
immutable `2026-10-15-typed200-owner-trace-validation.json`. Fixed1488B privateTCM
trace preserves rawterminal preACK and mailbox serialization preDONE; bounded
eventslots/one-shot freeze.364tests and5sanitized hostcases pass;49pairedpollrecords
exactly match independently compiled frozenservice. Separate diagnosticARM ELF
fitsTCM (17416Bcode/51144BBSS,2104Bworkspare). Order-only default; noPMUprovider,
targetexecution or overhead/WCET bound.1442preservedpaths unchanged. No jobs active,
targetIO, programming or new Vivado run. HANDOFF.md details remaining prerequisites.

Newest local milestone: [executable capture qualification](2026-10-15-typed200-capture-qualification.md),
with immutable `2026-10-15-typed200-capture-validation.json`. Exact R5/PL ABI
decoder and offline checker implemented;332tests plus5sanitized frozen-service/
mock-MMIO captures pass, ARM/host offset assertions compile, independent model
zero-hidden label matches.1398preservedpaths unchanged. No target execution/WCET
claim. PreACK capture needs owner-local instrumentation because v8 immediately
ACKs reusable terminals. HANDOFF.md gives next local implementation boundary.
No jobs remain active; all qualified/previously sealed files stay frozen.

Read [current timing work record](2026-10-15-typed200-timing-continuation.md).
Matched OOC synthesis control/5ns-clock experiment COMPLETE in
`build/v2/typed200-synthesis-clock-v3/`: clean 5ns clock during synthesis,
same-period estimated setup -0.387 -> +0.855ns, LUT66758 ->65679; not physical
closure. Both separate observation and LUT-capture siblings PASS full5400-word/
14-completion regression with exact every-cycle counters/AXI/outputs and negative
deadline/error/drain cases. Counter and universal-byte capture inductions pass.
Full unchanged-RTL clock-flow synthesis COMPLETE `typed200-clock-physical-v1`:
68498LUT/53651FF/579DSP/50BRAM/36URAM, setup+0.624/hold-0.087ns estimated;
real5ns/10ns full clocks preserved and no OOC clock leakage. Exact source/clock
review passes. Placement/audit COMPLETE: final+0.371/-0.087ns, all12checks0,
CDCsafe/39vendorXPM exceptions/noLUTAR; routeREJECTEDbelow+0.500ns margin.
New limit is typed SHA-to-admission,24levels/21CARRY8. A separate same-cycle
full256bit profile tree passes sequential guard equivalence and full5400-word/
14-completion regression; small mapped probe reduces25->17levels/21->10carry.
Extra parallel decision KEEP refinement is also equivalent and regresses cleanly
but gives no further probe gain; retain it without promotion.
Profile-tree full synthesis/placement/audit COMPLETE: +0.358/-0.106ns versus
control +0.371/-0.087ns; no whole-design gain, do not promote. All12checks0,
CDCsafe/39vendorXPM exceptions/noLUTAR/FIFOasyncFF0. Route held below+0.500ns.
Separate physical-only Explore of the original control COMPLETE: +0.371/-0.087ns;
Vivado skips setup optimization with positive WNS, so no gain is credited.
Hash-bound postplace review passes audits but holds routing below+0.500ns. No jobs
remain active. Final continuation validation binds preservation and all reviews.
New [target qualification plan](2026-10-15-typed200-target-qualification-plan.md)
defines loader/ownership, exact ARM goldens, phase bounds and fault/delivery gates.
New immutable validation functional/probe record and HANDOFF.md give exact jobs.
Continue the authorized local work without another proceed. Only local work is authorized; board
and all qualified/sealed sources remain unchanged. HANDOFF.md has exact jobs.

## Newest completed milestone: synchronous result FIFO (2026-10-15)

Read [synchronous FIFO report](2026-10-15-typed200-synchronous-flush.md) and
[immutable validation](2026-10-15-typed200-flush-validation.json) first.
Separate sealed typed200_flush candidate removes the inherited LUTAR-1 path;
full routed mapping has no async-reset FIFO flops.65,673unitcycles across actual
L3/4/5, actual8x128 induction,5,400goldenwords/14pairednativecompletions pass;
outputs, AXI traces andnativecounts unchanged. Final200MHz routedSTA reports
0.000ns setup/+0.010ns hold: zero reported setupmargin, NOT hardware qualification.

Native OOC clock audit finds zero stored encoder-synthesis clocks; fulltop has
its correct5ns constraint. Next controlled flow experiment should explicitly
constrain OOC synthesis, then assess response-data locality (routedcriticalpath
90.8%interconnect) andobservationalcounter timing. No 300MHz benefit claimed.

Board SSH recovered; stockstarteroverlay loaded, qualifiedpackage filesmatch
originalarchive. No board/R5 programming, remoteconfig change orautomation.
All602protectedfiles, qualifiedarchive andfourpriorseals rehashedunchanged.
R5v8/typeddeployment/WCET gates remain as below; HANDOFF.md has exactevidence paths.

## Current completed physical/R5 continuation (2026-10-15)

Read [physical/R5 review](2026-10-15-typed200-physical-r5.md),
[immutable evidence seal](2026-10-15-typed200-physical-r5-validation.json) and
[R5 loader/service contract](../../firmware/typed200_r5/README.md).
Isolated typed200 synthesis, placement and route complete. Final recomputed
200MHz STA: +0.008ns setup/+0.010ns hold; no unconstrained endpoints, zero unrouted
nets/overlaps, CDC safely timed and no routed DRC errors/critical warnings.
An inherited LUTAR-1 derived async FIFO reset warning remains unresolved for
stronger assurance signoff. Read-only completion observation and staged profile
validation are the next timing-margin targets; qualified baseline stays frozen.

R5 reset-entry ELF v8 fits entirely in TCM, passes host policy sanitizers and
full model SHA, and has a parsed ELF/symbol/stack audit. Shared terminal padding
is explicitly canonicalized. No target execution, ownership enforcement, WCET,
external-delivery guarantee or hardware qualification is claimed. All602 protected
files and all previous sealed sources/docs/evidence rehashed unchanged. No live
build jobs or board programming; HANDOFF.md records a user-observed board link/
status-LED outage and failed read-only network checks separately from local work.

## Current ARM transport successor (2026-10-15)

Read the [C/RTL transport correction](2026-10-15-typed200-transport-review.md) and
[sealed interoperability validation](2026-10-15-typed200-transport-validation.json)
first. Active software is `firmware/typed200_v2/`; older SHA transport helpers are
preserved but superseded because canonical digest bytes and numeric register-word
order were mismatched. Actual compiled C frames now pass RTL admission/proposal
and digest readback: 668 writes/91 reads/15 admissions. Native RTL, numerical
contract, prior seals and 602 protected baseline files remain unchanged. No target
R5 execution, hardware qualification or WCET guarantee is claimed.

## typed200 native integration milestone (2026-10-15)

Current entry point: [typed200 integration](2026-10-15-typed200-integration.md)
and [sealed validation](2026-10-15-typed200-validation.json). Separate 28-source
candidate binds live memory drain, sticky response/core faults and native epoch
identity to typed publication. All 5,400 golden words and 14 paired completions
match the qualified core/original memory port under identical response streams.
Delayed/error/late B/R responses, timeout/quarantine, stale sessions, shape and
legacy-bypass tests pass. Two new scoped inductive proofs and additive ARM driver
host/R5-object checks pass. No new FPGA physical build, CDC signoff, BSP/TCM map,
target WCET or hardware guarantee is claimed. All 602 protected files and prior
sealed evidence remain intact. HANDOFF.md lists next physical/ARM assurance gates.
The earlier sections below describe prior completed stages.

## Typed assurance implementation milestone (2026-10-15)

Current entry point: [typed intent implementation/evidence](2026-10-15-typed-intent-implementation.md)
and [sealed validation](2026-10-15-typed-intent-validation.json). Frozen 18-label ATIS
contract, exact bounded C head/bridge/MMIO, Cortex-R5 relocatable object, standalone
AXI-Lite publication endpoint and three scoped inductive proofs are complete.
No encoder/CDC/TCM integration, target WCET, new physical build or hardware
qualification is claimed. All 602 protected files and sealed physical candidates
remain intact. HANDOFF.md lists final attempt directories and the next P0:
live memory drain/error/epoch binding, since encoder run_done can precede final
AXI B responses. Preserve the sole qualified 200 MHz package and recovery.

## Successor implementation task

Current successor: [counter telemetry timing experiment](2026-10-15-counter300-implementation.md)
and [typed timing contract/ARM partition plan](2026-10-15-typed-timing-contract-plan.md).
HANDOFF.md records the active/completed physical run. Preserve the qualified
200 MHz system and all earlier rejected evidence; typed-output assurance at
200 MHz is the primary follow-up after the requested counter experiment.

The user subsequently authorized isolated changes toward 300 MHz and a checked
timing/typed-output contract. Read [the implementation record](2026-10-15-locality300-implementation.md)
and current HANDOFF.md before continuing. The review below remains a historical
record of the completed review-only scope; it is not the successor build status.

## Review completed: 2026-10-14 America/Chicago

Read the [completed report](2026-10-14-system-one-architecture-review.md),
[comparison matrix](2026-10-14-system-one-comparison-matrix.md),
[ranked experiment plan](2026-10-14-system-one-experiment-plan.md),
[primary/artifact registry](2026-10-14-system-one-sources.json),
[saved-counter analysis](2026-10-14-system-one-profile-analysis.json), and
[preservation audit](2026-10-14-system-one-preservation.json).

The review distinguishes short-request input bandwidth, longer-request compute
and nonlinear scheduling, actual routed activation/query distribution timing,
and the separate generative execution contract. Ten primary publications and six
pinned repositories were examined; source/table inconsistencies are documented.
No new hardware observation, build, baseline modification or automation was made.
Future experiments remain unexecuted proposals requiring a separately scoped task.
HANDOFF.md is still the entry point; the original brief below is retained for context.

## Original review scope (completed)

Perform a thorough architectural review of System One against existing embedded
FPGA language-model solutions. Start with the two Kria papers below, then search
for other relevant primary sources and author artifacts. The objective is to
identify defensible architectural improvements and research contributions, not
to change RTL or launch another implementation run automatically.

## Authoritative project state

- `attention-context-capture-large` is hardware-qualified at actual 199,999,998 Hz.
  App: `sysone-v2-attention-context-capture`; exact feature `0x5377ffff`.
- There are 23 frozen RTL sources. Independent review verified eight H1024
  fixtures, four head32 query-group cases, eight real MiniLM-L12 smoke cases and
  350 frozen L12 evaluation cases, all bit-exact. H1024 is a validated hardware
  capacity; it is not the hidden width of the deployed MiniLM-L12 model.
- Legal routed setup/hold: +0.101/+0.010 ns; all 122,669 routable nets routed.
  Full synthesis: 68,765 LUT, 52,552 FF, 50 BRAM tiles, 36 URAM, 579 DSP.
  State the implementation stage when comparing resources from different systems.
- Sixteen attention lanes parallelize query tokens, not heads; linear lanes=32.
  The selected architecture has a scheduling tradeoff versus 32 query lanes.
- Deployed inference is an integer transformer encoder with CPU task heads.
  No FPGA autoregressive decoder, deployed KV-cache executor, or generation
  throughput has been established. Offline SYS3/KV/RoPE proofs are not deployment.
- Qualified 125 MHz recovery files and 256 MiB boot reservation were preserved.
  The L12 model was restored and read back exactly after tests. Last recorded
  state has the 200 MHz app loaded; this is not a fresh live-board observation.
- The overnight automation was deleted after milestone completion. No further
  300 MHz work was launched. No active auth/Vivado session was left at completion.
- Seven older placements were rejected for routing. Preserve the unchanged
  >=0.5 ns placed setup admission for any future candidate. Never reroute those
  rejected snapshots or replay integration scripts.

Evidence to read before relying on older narrative entries:

1. `build/v2/kr260-opt-attention-context-capture-large/hardware-qualification.json`
2. `build/v2/context-capture-board-validation/receipt.json`
3. `build/v2/context-capture-board-validation/final-state.json`
4. `build/v2/context-capture-board-validation/performance-comparison.json`
5. `build/v2/context-capture-board-validation/app.json`
6. Candidate synthesis/placement/route reviews and source snapshots under
   `build/v2/kr260-opt-attention-context-capture-large/`.

The immutable tested archive is
`build/v2/kr260-app-attention-context-capture-large.tar.gz`, SHA256
`ecd320163baa3c289c64e069186497974d4703039df4a455bc8620d357d7ec99`.
Its packaged build metadata predates board qualification; the separate hash-bound
hardware qualification receipt establishes the completed hardware tests.

## Matched measured performance

Same 350 frozen inputs, image, outputs, predictions and aggregate accuracy:

| Metric | Qualified 125 MHz | Qualified 200 MHz |
|---|---:|---:|
| Mean encoder latency | 17.27168 ms | 11.01110 ms |
| Encoder p95 | 36.08026 ms | 23.24372 ms |
| Observed maximum encoder latency | 57.98782 ms | 38.25647 ms |
| Mean host round trip plus CPU heads | 19.26884 ms | 13.00962 ms |

Mean encoder speedup is 1.56857x, latency reduction 36.2477%; average measured
encoder cycles increased 2.00375%. CPU heads remain approximately 1.53 ms.
Host round trip plus heads excludes tokenization and model loading. These are
saved measured runs, not confidence intervals or worst-case execution bounds.
Do not convert encoder request throughput into decoder generated-token throughput.

## Initial literature targets

The other chat was **Review Reliable Edge LLM Literature**, thread
`01a12a79-ed12-7a93-a408-f068b74fdc0f`. It produced:

- `docs/research/2026-10-11-edge-language-models-review.md`
- `docs/research/2026-10-11-edge-language-models-sources.json`
- `docs/research/2026-10-11-edge-language-models.bib`

That review predates the final 200 MHz milestone. Its old project-status statements
must not supersede the current evidence above.

1. **Pushing up to the Limit of Memory Bandwidth and Capacity Utilization for
   Efficient LLM Decoding on Embedded FPGA**:
   https://arxiv.org/html/2502.10659v1
   KV260, LLaMA2-7B, W4/FP16, reported 300 MHz and 4.9 generated tokens/s.
   Four 128-bit AXI streams form a 512-bit stream. Bare-metal deployment uses
   93.3% of 4 GiB; reported 6.57 W is a Vivado estimate. This is not our workload.
2. **TeLLMe v2**: https://arxiv.org/html/2510.15926v2
   Author artifact: https://github.com/UCI-CORSA/TeLLMe_FPGA_2026
   KV260, BitNet 0.73B, ternary weights/INT8 linear operations with FP16 operations,
   reported 250 MHz, up to 25 generated tokens/s, and 0.45-0.96 s TTFT for
   64-128 token prompts. ARM NEON LM-head time is included. Inspect publication
   versions, artifact contents and exact measurement boundaries afresh.

Both use KV260, not KR260. Establish actual SoM/device, DDR, available fabric,
host/runtime and measurement differences before claiming equivalence.

## Review questions and deliverables

- Inspect our actual RTL, software, model format, numerical specification,
  hierarchy, memory map, AXI datapaths and measured timing reports. Trace complete
  execution and data movement; distinguish implemented behavior from proposals.
- Analyze compute organization, buffering, DDR traffic/bandwidth, port widths,
  packing, reuse, burst efficiency, pipeline boundaries, fanout, placement density,
  attention scheduling, normalization and embedding. Identify measured evidence
  and missing instrumentation for every alleged bottleneck.
- Read the two papers deeply and inspect available source/artifacts. Search for
  additional integer encoder and embedded decoder work, as well as relevant
  larger-FPGA techniques. Include negative results and approaches that do not fit.
- Build a source-linked comparison matrix: model/task, precision, device/memory,
  clock, resources with stage/units, prefill/decode/encoder latency scope, host
  work, energy measurement method, quality, reproducibility and limitations.
- Keep encoder optimization, 300 MHz closure, and generative decoder development
  as separate workstreams. A published 300 MHz design is feasibility evidence,
  not proof our current datapath will close at that clock. Our last placement
  sweep had -1.164 ns setup at 300 MHz; do not add isolated probe gains to it.
- Rank concrete recommendations by evidence, benefit, implementation effort,
  numerical/compatibility risk and validation cost. Separate immediate changes,
  experiments and major redesigns. Do not invent speedup estimates without a model.
- Propose matched benchmarks, profiling and ablations; identify which model and
  task comparisons can be fair. Assess paper novelty as a hypothesis needing
  evidence, not merely a higher clock or more tests.
- Save a detailed Markdown report, source registry and prioritized experiment
  plan under `docs/research/`; update HANDOFF.md with findings and next steps.

## Operational boundaries

This task authorizes read-only architecture/research inspection and writing review
documents, not hardware deployment, RTL edits or new expensive builds. Preserve
the qualified package, snapshots, numerical baselines, recovery and Nexys defaults.
Never replay integration scripts. Do not rerun completed qualification helpers.
Do not commit/push, buy compute, change boot memory, start unrelated training or
recreate the completed automation. Never copy credentials from chat into files,
reports, tool arguments or new-chat prompts. No credentials are needed for review.

S: is a Windows `subst` alias to this physical repository on C:, created for short
Vivado paths; it is not a disk or partition. Do not modify it for this review.
WSL commands must use the physical repository path, not S:.

Maintain HANDOFF.md as the current entry point. Historical progress entries below
its authoritative summary are an audit trail, not current active-job instructions.
