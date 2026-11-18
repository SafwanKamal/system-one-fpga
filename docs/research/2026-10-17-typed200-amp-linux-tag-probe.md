# Linux R5 AXI metadata diagnostic, 2026-10-17

The corrected Linux-started Cortex-R5 firmware ran on the KR260 and published
all four PL markers. Kernel watchdog cleanup stopped R5 and released both TCM
leases and the additional PL clock reference. Stock PL and the dashboard were
restored. The trial nevertheless remains **FAILED at metadata qualification**:
the checker incorrectly required constant full USER and AXI ID across R5 writes.
Raw observations are preserved; admission policy has not been relaxed.

## Actual target observations

`build/v2/typed200-amp-linux-tag-probe-v1/target-trial-v2/collection-v1`
contains the captured root-private service results. `observation-review-v1`
extracts those results and independently verifies marker addresses, values,
write sequence, untouched APU slots, counters, CPU trace and recorded recovery.
It does not turn the failed target service into a passing qualification.

R5 trace: PASS, SCTLR `00e50878`, CPSR `000001d3`, MIDR `411fc153`.
Read metadata: full tag `00012000`, ARUSER `2000`, ARPROT `1`, ARID `0049`.
Full tag encoding is `(PROT << 16) | USER`.

| Address | Value | Sequence | AWUSER | AWPROT | AWID | USER[9:0] |
|---|---|---:|---|---:|---|---:|
| a0000010 | 52350004 | 64 | 2800 | 1 | 0049 | 0 |
| a0000014 | 52350005 | 65 | 2000 | 1 | 0069 | 0 |
| a0000018 | 52350006 | 66 | 2000 | 1 | 0089 | 0 |
| a000001c | 52350007 | 67 | 2800 | 1 | 00a9 | 0 |

The fresh A53 preamble completed 64 writes, then R5 completed four, for a final
count of 68 and zero probe errors. A53 cores 0..3 had AR full tags
`20080,20081,20082,20083` and AW full tags `2008c,2008d,2008e,2008f`.
These are observations from one controlled workload, not an exhaustive
provenance proof for all system masters or transaction attributes.

## Admission gate

The preserved requester filter deliberately requires USER[15:10] to be zero;
its default ENABLE_R5 is also zero. All observed R5 USER values violate that
upper-field condition. A new local simulation replayed the four AW metadata
records and one AR record through the unchanged filter with ENABLE_R5=1:
all five were rejected with no downstream request. The full harness passed
2194 transactions, including its existing MID, burst, skew, stall and fault
cases. Replay uses measured IDs/addresses/USER/PROT with synthetic payload,
cache/QoS and strobes; this is not an integrated physical firewall test.

The already preserved AMD UG1085 v2.5 PDF was hash-verified, searched, and page
1091 rendered and visually inspected. That page assigns master identity to
AxUSER[9:0] and allows upper fields to serve other system purposes, including
coherency and poisoning. It does not qualify the precise meaning of observed
bits 11 and 13. No semantic inference or blanket masking of those bits is
admitted by this milestone. Source: `sideband-audit-v1`, preserved PDF under
`build/v2/typed200-amp-ownership-v1/ug1085-v2.5.pdf`.

Next work is a separate filter candidate and explicit upper-field/source
provenance qualification, including negative traffic and all paths before USER
loss. Do not change or rebuild the sealed filter/package to make this trial
pass. Full typed inference still also needs trusted firmware/session, protected
memory, output composition, numerical, cycle, fault/drain, physical and target
qualification. No inference deployment or timing guarantee is claimed.

## Firmware, controller and checks

Separate candidate directory: `firmware/typed200_amp_linux_tag_probe`.
The fixed startup omits unsupported VBAR, uses only private TCM and the fixed
PL diagnostic page, checks CPU state, orders completed PL writes with DSB,
publishes trace and waits using only TCM. No DDR, raw PS/RPU MMIO or IPI access.
ELF SHA256: `bacf61240bffa66a168bf5416aafcf4c1270f0056fbcd44c916ab934d65cc6d0`.
Native module SHA256:
`55e61c3d401126b7e415c7faa5487e8d29082efd2768cc6e99dee65f0ec7692e`.

The module adds a Linux OF clock reference held through execution and uncertain
recovery, on top of the prior two-bank lease/session engine. Reserve verifies
the fixed probe node/range and 95..100 MHz clock. A failed reserve unwinds its
clock reference; an uncertain stop retains resources and the module pin.
Root service staging copies and verifies executable bytes into a private
directory before use, journals attempted access before execution, requires
positive quiet proof before PL unload, and provides independent ExecStopPost.
Recovery compares all 30 runtime application-file hashes and Linux clock
rate/reference counts. It makes no raw PS register equality claim.

Completed host checks: 242 actual-ELF/model scenarios with CP15 allowlist;
25 blocked, 26 prepare and 40 modeled-live adapter scenarios; 2214 policy cases;
12 actual-ELF PL transactions replayed through unchanged diagnostic RTL.
These host models do not prove hardware power/reset/drain behavior. The prior
sealed session engine's 10465 host trajectories remain preserved.

## Failed attempts and recovery

The first target attempt staged native executables under `/run`, which is
mounted noexec. APU helper creation failed with EACCES before execution; R5
was never loaded. Conservative recovery held the probe because no positive
quiet proof was recorded. A separate reviewed recovery verified noexec, the
exact captured exception, unchanged state/staged hashes, and no helper or PL
mapping before restoring stock. The first forensic recovery attempt expected
stderr in the journal, but systemd --pipe sent it to SSH; it made no recovery
mutation. Reviewed recovery v2 used that captured evidence and passed.
The old failed state was retained unchanged.

The second target attempt used executable root-private `/var/lib` staging and
checks noexec before PL mutation. Actual APU/R5 execution and watchdog cleanup
succeeded. The service then rejected changing full AW identity, and its
independent recovery passed. That original checker and failed trial remain
unchanged. Separate observation review is narrower and explicitly leaves
filter admission unqualified. Earlier local adapter v1 lacked a copied header;
v2 passed. Initial packaging syntax failure preceded target actions. All
failed evidence is retained, with later directories recording corrections.

## Last observed board and host state

At 14:27 UTC (09:27 America/Chicago), the same boot ID remained
`6c80ec1a-e7ae-473f-b169-d54f129615d1`, uptime 9h47, CPUs 0..3 online.
Stock k26-starter-kits was operating, dashboard active, R5 module absent,
remoteproc empty, PL0 rate 99999999 Hz with enable/prepare counts 0/0.
All runtime firmware hashes matched baseline. Taint remained 12288 (external
unsigned module O/E), with no additional fault bits. Passive UART completed
at 14:31:18 UTC. Linux emitted overlay-removal memory-leak warnings for
firmware-name/resets and the probe clock symbol; no new hang was observed.
This is a bounded observation, not proof of absence of future failures/leaks.

JTAG/hw_server/XSDB stayed stopped. No raw Linux PS/RPU register probes, RPU
mode changes, PL rebuild, old firmware rebuild, commit or push. No power-cycle
was needed or is pending. Existing unrelated workspace changes are retained.
The S: alias remains mapped to this workspace. HANDOFF.md is mutable;
the companion validation JSON records prior preservation and new file hashes.
