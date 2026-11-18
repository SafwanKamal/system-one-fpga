# R5 smoke deployed and passed under trusted Linux

2026-10-17, 15:06 UTC. Following the user's direction to prioritize deployment,
the existing qualified PL probe, corrected R5 ELF and Linux module were reused
with the already tested workload validator. No new PL build or filter
integration was required. Linux is trusted for this diagnostic; exclusive
R5 ownership and full inference are not claimed.

The root-private service `sysone-trusted-r5-smoke-trial-v1` completed with
result success, exit 0. Observed service runtime was 9.372 seconds, not a WCET
measurement. All 64 A53 preamble writes and four R5 markers completed, for 68
writes and zero probe errors. R5 trace was PASS, SCTLR00e50878, CPSR000001d3,
MIDR411fc153, AR full tag00012000 and ARID0109. Four R5 writes used USER
2800/2000/2000/2800, PROT1, IDs0189/01a9/01c9/01e9. The varying IDs passed
the corrected check. Previous failed trials remain unchanged.

The kernel watchdog stopped R5 and released both TCM leases and its extra PL
clock reference. Independent recovery unloaded the module, restored stock
k26-starter-kits and restarted the dashboard. All runtime application file
hashes matched baseline; PL0 clock returned to99999999Hz, enable/prepare0/0.
At15:06:10UTC the same boot6c80ec1a-e7ae-473f-b169-d54f129615d1 remained,
uptime10h26, CPUs0-3online, taint12288 (expected O/E). UART retained the
known overlay-removal warnings and was closed after the successful run.
No power-cycle or JTAG connection was needed. No raw PS/RPU MMIO, boot changes,
new module build, commit or push occurred.

Evidence: `build/v2/typed200-amp-trusted-r5-smoke-v1/smoke-trial-v1/target`.
The only controller behavior change was replacing the incorrect constant-ID
qualification with the tested workload/profile validator. Recovery and resource
ownership mechanics were reused. Root staging is under executable `/var/lib`.
The ELF and module hashes remain the qualified prior values:

- ELF: bacf61240bffa66a168bf5416aafcf4c1270f0056fbcd44c916ab934d65cc6d0
- Module: 55e61c3d401126b7e415c7faa5487e8d29082efd2768cc6e99dee65f0ec7692e

The diagnostic completed and restored stock; it is not a persistent running
R5 inference service. The profile filter remains a separate disabled candidate.
Further trusted-Linux inference deployment can proceed without claiming source
isolation; firmware/model memory integration and actual inference execution
remain work to do. Exclusive-owner enforcement is deferred, not certified.
