# typed200: isolated service integration candidate

Target: 200 MHz. No new physical timing or hardware qualification is claimed.
The qualified baseline/package/recovery, locality300, counter300 and the original
typed prototype are preserved. This candidate derives directly from the 23-file
qualified RTL snapshot, rather than a rejected 300 MHz implementation.

Read the [integration report](../../../../docs/research/2026-10-15-typed200-integration.md),
[validation record](../../../../docs/research/2026-10-15-typed200-validation.json)
and [ARM companion/register map](../../../../firmware/typed200/README.md).

`platform/kr260/typed200_encoder.sv` is the service top. It instantiates the original
encoder arithmetic, a memory port with a read-only live-drain observer, the native
epoch tracker and typed AXI-Lite control/publication. The copied legacy top is
provenance and regression support, not another instantiated control interface.
Compile only this candidate's RTL namespace; its contract module names deliberately
match the copied standalone prototypes and must not also be compiled from those
other directories in the same design.

H=384, T=1..128, one positive contiguous selected row slice inside T. Program/ID/
result buffer addresses are elaboration constants. The ABI `0x54590201` requires
shape staging and exposes native completion/owned shape and raw clock counters.
The numerical contract/profile remains unchanged. The native `deployment_ready`
input is a trusted boot/environment permission; it is not model authentication.
Keep it asserted through an owned interval and isolate model/input/result buffers.

For the tested core configuration, use `candidate.json`'s `baseline_profile`:
MAX_HIDDEN=1024, attention lanes16 and all qualified arithmetic pipeline options.
The top's legacy-compatible parameter defaults alone do not establish that profile.
The service intentionally omits legacy performance telemetry from its control ABI;
raw encoder/request cycles remain measured at the qualified completion edge.
Do not treat a requested target frequency as timing closure.

All arithmetic source hashes match the qualified snapshot. Only the copied memory
port adds an observation port/predicate; new service control lives in new files.
`candidate.json` freezes the complete RTL inventory after verification. To change a
sealed source, create another candidate rather than resealing it.
