# AMP candidate: requester filter and read-only recovery inventory

2026-10-16. Separate from the qualified 200 MHz implementation, the frozen
typed routed checkpoint, and the sole-R5 MVP/boot chain. This is an implemented
and locally verified **component candidate**, not an AMP deployment or a new
timing certificate. Latest user supplied JTAG and authorized proceeding;
hardware inventory remained read-only. No target halt, reset, programming,
reconfiguration, reboot, deployment, persistent-media write, commit or push.

## Target findings

The PC's active Wi-Fi interface is 192.168.0.152/24. A bounded TCP/SSH identity
scan of that subnet found port 22 at the historical 192.168.0.239 address but
did not complete SSH key exchange or identify a matching saved host key. The
native OpenSSH probe received `OpenSSH_9.6p1 Ubuntu-3ubuntu13.20`, then stopped
at `SSH2_MSG_KEXINIT sent`. That hung local client was terminated; no remote
command, password authentication or host-key override occurred. The neighbor
cache reported MAC 00-0A-35-0F-62-C7, stale; this is supporting discovery data,
not authenticated board identity. User confirms wired Ethernet to router but
does not know the current board address. No cause of the SSH problem inferred.

JTAG cable XFL14EBBE1U3A enumerates xck26 (04724093) and arm_dap (5ba00477).
XSDB reports A53 #2 Running, other A53/R5 debug power/reset states and an A53 #3
APB transaction error. These observations do not establish a board fault or
justify forcing debug power/reset. No `stop`, `rst`, `dow`, `mrd` or `mwr` was
issued. hw_server on local TCP 3121 is available; its launch receipt is in the
candidate directory. JTAG enumeration establishes connectivity, **not a tested
recovery procedure**.

COM9 (FTDI interface B) was opened at 115200, no handshake, DTR/RTS false.
Passive capture and then a single carriage return each produced zero bytes.
No serial break or command was sent. No live kernel, DT, ATF, PMU, PS clock
graph, boot medium or wired GEM inventory was obtained. The next target step
is authenticated read-only inventory using the saved host key, or a responsive
serial console. Do not replace the Linux PS configuration with the standalone
Ethernet-disabled PS initialization to obtain that inventory.

Target receipts/scripts:
`build/v2/typed200-amp-candidate-v1/{jtag-inventory.tcl,jtag-inventory.log,
hw-server-start.json,serial-passive.log,serial-blank-line-probe.log,
openssh-readonly-probe.log,ssh-discovery.json,inventory_board.py,find_board.py}`.
The inventory helper has fixed read-only commands, requires the saved host
key, prompts for the credential without saving it, and cannot deploy. Its
candidate-local cffi dependency fixes a Python 3.12/3.13 ABI mismatch without
changing the frozen board-auth helper. No target inventory receipt is implied
by the existence of this helper.

## Implemented filter

Source: `rtl/v2/candidates/typed200_amp/control/typed200_requester_filter.sv`.
Input/output are full AXI4, 40-bit address, 128-bit data, 16-bit ID and 16-bit
request USER. The intended insertion is upstream of the actual control
SmartConnect's full-AXI-to-Lite conversion, protecting **both** the CSR and
permit pages at [0xa0000000, 0xa0002000). It is not yet connected to that design.

Policy defaults to **deny all** (`ENABLE_R5=0`). A reviewed build-time enable
allows only secure RPU0-origin, aligned 32-bit, single-beat accesses inside the
window, FIXED or INCR burst, no exclusive lock. The prototype accepts source
MID bits [9:0] masked by 0x3f0 equal to zero and requires USER[15:10] zero.
Write strobes must be within the addressed four-byte lane; partial and zero
strobes are legal. There is no software-writable bypass/configuration path.

AMD documents PS-generated MasterID in AxUSER, RPU0's MID/mask, and preserving
metadata through SmartConnect in [XAPP1353](https://docs.amd.com/r/en-US/xapp1353-pl-isolation/Master-IDs)
and its [master-ID appendix](https://docs.amd.com/r/en-US/xapp1353-pl-isolation/Appendix-A-Master-ID-List).
[UG1085 v2.5](https://docs.amd.com/api/khub/documents/xzMsp_c5sG9J6A3u7NkJYQ/content?Ft-Calling-App=ft)
also describes upper USER bits as potentially carrying coherency/poison
attributes. Requiring those bits zero is a deliberate fail-closed prototype
restriction, **not** a claim that every legitimate R5 transaction uses zero.
Actual R5 USER/PROT/bus shape and PS provenance still need target/design review.
An arbitrary upstream master that can forge those tags defeats this policy;
source authenticity is an integration assumption, not proved inside the filter.

One transaction per direction is outstanding. AW and W are buffered
independently, including W-before-AW, and never forwarded until both are
eligible. Downstream AW/W handshakes remain independent. Rejected writes
consume exactly the declared LEN+1 beats before returning one DECERR. Rejected
reads return LEN+1 zero-data DECERR beats. Full 256-beat denied bursts are
handled; early/missing WLAST sets a sticky protocol fault while declared
rejected beats continue draining. New AW/AR admission then blocks until reset.
Wrong downstream response ID or missing read LAST similarly faults; responses
are surfaced as SLVERR. Fault does not cancel an already issued transaction.

No timeout frees the bus or buffers. A malformed master withholding the rest
of a declared burst can stall that direction indefinitely. A malicious denied
master can also occupy the single outstanding slot: this prototype provides
access exclusion, **not fair/bounded R5 control service**. Admission/configure
operations need service consideration; the local PL terminal deadline after
admission must not depend on a subsequent R5 response.

Reset is synchronous. Independent filter reset with live downstream AXI is
unsafe without a composed drain/reset protocol. Existing accepted operations
can finish after another direction faults. Existing W-before-AW partial input
can remain quarantined if a fault blocks the missing AW. These are explicit
quarantine/liveness limits, not cancellation or next-request guarantees.

## Verification and preserved failures

RTL SHA256: `d5ed2005fd24c78d1adb438db7339c01b856faa200125d858b2e2fa7a6d6d905`.

`scripts/v2/check_typed200_amp_filter.py`, attempt `filter-sim-v1`: **2,189
transactions pass** using Icarus and an independent backpressured AXI target.
Tests cover every one of 1,024 low source IDs for reads and writes, AW/W skew,
response stalls, secure/nonsecure and upper USER restrictions, lane strobes,
address bounds/alignment/high aliases, transfer size/burst/lock restrictions,
1/15/255 LEN bursts, concurrent read/write, downstream error propagation,
partial-input reset, and malformed LAST/response-ID fault quarantine. Reset
tests reset the target model too; they do not establish independent reset
safety. Simulation is not exhaustive platform verification.

`scripts/v2/prove_typed200_amp_filter.py`, attempt `filter-formal-v2`: Yosys
two-state induction proves the assertions for **ENABLE_R5=1 and 0**, both at
induction length 2. Only explicit environment assumption: first sampled edge
asserts reset. Inputs and backpressure may change arbitrarily afterward.
Proved: forwarded access restrictions; default no forward; valid/payload
stability for stalled downstream AW/W/AR; buffered upstream B and locally
generated rejected-R stability; sticky fault/new-address block; exact declared
write-beat accounting before B; exact rejected-read count/LAST; final denied
write beat produces a response on the following step. Ghost counters strengthen
the induction and are absent from implementation. Pass-through read response
stability requires a compliant downstream; no downstream compliance or global
liveness assumption is silently substituted for the proved safety properties.

Formal v1 failed during frontend lowering because edge-triggered check cells
needed `async2sync` before `chformal -lower`. Logs are retained. v2 adds that
required normalization; no assertion, RTL policy or input constraint was
weakened. No completed baseline proof/simulation was restarted.

Artifacts are under `build/v2/typed200-amp-candidate-v1/filter-{sim-v1,
formal-v1,formal-v2}`. Receipts identify the exact RTL hash. There has been no
Vivado synthesis, placement, routing, resource measurement or physical timing
claim for this filter. It adds control latency/buffering; unchanged encoder
numerics are preserved by leaving frozen sources untouched, not by claiming
unintegrated control-path cycle equivalence. Composition requires a fresh
matched-response regression and new physical timing evidence.

## Readiness and next work

Machine-readable gates: `2026-10-16-typed200-amp-candidate-readiness.json`.
Deployment readiness remains false. Work proceeds in this order:

1. Recover authenticated read-only PS/kernel/DT/boot/network inventory and
   qualify a recovery route. Preserve current boot and do not force reset to
   replace missing inventory.
2. Review a Linux-compatible PS topology, actual tag propagation and all
   alternate CSR/permit/reset/configuration paths; integrate this filter in a
   new hardware candidate. Enabling it requires matching actual R5 attributes.
3. Implement selective PMU/secure/direct-MMIO ownership of R5/PL clocks,
   resets, TCM, memory protections and reconfiguration. The frozen blanket IPI
   seal is not a Linux policy. Unknown arguments/resources must fail closed;
   PM API numbers alone cannot establish separation.
4. Enforce model/IDs/hidden/TCM and active-buffer protection against privileged
   Linux and each Linux-controlled DMA. Allocate mailbox/result memory only
   from an audited reservation. Linux no-map and R5 MPU alone are insufficient.
5. Adapt a separate one-shot R5 startup/mailbox service with bounded private
   snapshot, replay/flood handling, no post-admission Linux dependence, and
   independent result copy. Preserve six typed outcomes and numerical routines.
6. Compose guard/access/ownership proofs, matched numerical/control regression,
   then new 200 MHz STA/DRC/CDC/exceptions and supervised target qualification.
   A new certificate must bind the new artifacts and environment.

The useful guarantee remains a canonical **local typed terminal by D after PL
admission**, conditional on protected uninterrupted clock/reset/power and the
reviewed ownership contract. Delay can produce Deadline, with empty label and
score. It does not guarantee Accepted by D, bound SSH delivery or prove drain
and buffer reuse after timeout. SSH is management transport, outside this
critical timing interval. The qualified 200 MHz sources, package, recovery and
numerical baselines remain frozen; the overnight automation remains paused.
