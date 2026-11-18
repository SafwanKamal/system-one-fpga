# Dot7 KR260 hardware qualification

## Milestone completed: deployed dot7 H1024, October 13, 22:46 UTC

This entry supersedes the historical active/export/unreachable entries below.
Dot7-large is packaged, legally routed at 125 MHz, deployed on KR260 revB and
hardware qualified. All 17 frozen RTL source hashes and packaged firmware hashes
were rechecked. Final archive: build/v2/kr260-app-frontier-dot7-large.tar.gz;
SHA256 1fe8bd802b0de4559e808e587138ff67139c0911904cca3e54fe680fc8279d8d.
Canonical bit SHA256 4b0dae37b8b343a8c7267949cd2a44eb5acaa837592020930ce1e29c6d59430a;
FPGA payload SHA256 e68abfa721671f840d9653cf0c038fc2e02cae434cb491fe8ac7cd72cff270ab.
Exact XSA/bit match was retained after checking timestamp-only differences.

Hardware: 350/350 frozen L12 cases and eight synthetic H1024 cases at lengths
1,2,3,4,5,12,64,128 are bit-exact. Eight L12 smoke lengths also passed.
Matched-suite comparison verified identical image/suite hashes, hidden tensors,
case IDs, predictions and accuracy counts. Mean L12 encoder time 17.27168 ms
versus baseline 17.18768 ms (0.49% slower); maxima 57.98782 versus 57.65258 ms.
This expands supported hidden width to 1024; it is not a measured speed/quality gain.
H1024 is a synthetic one-layer/FFN4096 test, not a trained large-model evaluation.
H1024 encoder times range 6.422 ms (1 token) to 29.644 ms (128 tokens).
Reports: build/v2/eval/kr260-dot7-hardware/{comparison,qualification}.json and
its two hardware report directories. Both board validation-status files passed.

Current board app sysone-v2-frontier, live clock 124999999 Hz; L12 image restored
with identical DDR readback. Recovery app sysone-v2-memory remains installed.
Native SSH session closed after confirming current app. No credentials saved,
no boot-memory changes. Live dedicated low-DDR reservation is 256 MiB at
0x60000000. SYS3 high-DDR addressing and decoder/INT4 production integration
remain incomplete; this does not exhaust 4 GB DDR or generate answers on FPGA.

Route: WNS +0.401 ns, WHS +0.010 ns; all 164277 routable nets fully routed,
zero routing errors. Native synthesis 31m24s and route 25m21s. Placed resources:
90278 LUT / 64513 FF / 59 BRAM / 36 URAM / 610 DSP, 98.18% CLB occupancy.
300 MHz remains unclosed. Routed critical path is URAM output distribution:
7.250 ns data, 5.263 ns routing, final DOUT net fanout24 / 5.167 ns.
All36 URAM OREG_A/B true; REG_CAS_A/B false. Next grouped optimization should
shorten/register per-buffer output distribution, prove cascade latency changes,
and combine independently verified linear drain/embedding cuts before another
expensive full build. Preserve this qualified package and frozen sources.

Failures retained: original route export label guard, inherited PYTHONHOME,
spaced-path XSA export, and first board deployment's outdated mode1 guard.
Deployer/runtime now require controls3 only for recorded dot7-large; mode1
legacy profiles retained. 45 runtime/deploy tests plus 12 deployment tests passed.
Software-only retry left RTL/bit payload unchanged. Original archive and failure
logs preserved. Export wall time included confirmed laptop lid standby; do not
claim uninterrupted execution or attribute standby to Vivado computation.

Independent verified experiments remain outside this frozen build: relative
read adapter/AXI contract (including max65535 beats), raw INT4 dot16 elastic
primitive, per-bank linear drain selection and embedding arithmetic equivalence.
They are not integrated capabilities or demonstrated frequency improvements.
No hard request/first-word timing guarantee is claimed. No Vivado jobs remain.
The specified package-and-hardware milestone is complete. The app confirmed
kr260-overnight-optimization PAUSED at this boundary, as instructed for milestone
completion. The 300 MHz goal and full high-DDR/generation work remain open.

