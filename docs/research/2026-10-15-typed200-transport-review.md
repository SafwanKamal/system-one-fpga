# typed200 transport interoperability correction

This addendum supersedes the ARM transport recommendation in the earlier
[typed200 report](2026-10-15-typed200-integration.md). The RTL candidate, numerical
contract, all qualified sources and earlier evidence are unchanged. Use
[`firmware/typed200_v2`](../../firmware/typed200_v2/README.md) for the active ARM
transport. The earlier `typed200` and `typed_intent` transport sources remain
frozen; they must not be used for SHA-bearing transactions with this RTL ABI.

The final cross-language review identified a serialization mismatch. The old C
helper interpreted the first four conventional digest bytes as a little-endian
word and wrote it to register index zero. The RTL and its directed testbench use
the numeric SHA256 value with its least-significant word at index zero. Separately
consistent C layout tests and RTL tests had not checked this boundary. A real
submission through the old helper would fail the contract identity check; a
terminal digest read through that helper would likewise decode incorrectly.
Fail-closed identity validation prevents acceptance under a wrong profile, but
does not make that unusable transport interoperable.

The corrected version explicitly maps the canonical 32 digest bytes to numeric
register words and back for request submission, active identity observation,
proposal commit and terminal observation. For the unchanged contract, offsets
`0x20..0x3c` and `0x50..0x6c` carry these values in ascending address order:

```text
5b2752d2 ba36026c fccb4b4f a3801d00 9e95e7ac 322ecac4 15487f8f 81336333
```

Session/request IDs retain their ordinary low/high UINT64 word order. Labels,
shape, budgets and typed failure semantics are unchanged. Explicit conversion
avoids depending on the CPU's native byte order or on C array layout.

The host test uses independent known numeric words, checks SHA reconstruction
from terminal registers, and exports the **actual compiled C driver's** request
and proposal fields to `wire-frames.hex`. The RTL test then stages those words
through AXI-Lite, admits the request, commits the proposal, requires Accepted
label17 and checks all eight published digest words. This closes the previously
missing C/RTL representation check. It does not substitute for target R5/BSP
execution, DDR ownership, CDC/physical timing or successful-inference WCET.

Final host/R5 attempt: `build/v2/typed200-transport-v4/`. Final C-generated frame
replay: `build/v2/typed200-c-transport-v2/`. The
[transport validation](2026-10-15-typed200-transport-validation.json) binds those
artifacts and rechecks all earlier sealed source/evidence hashes. The original
full-core result remains 5,400 golden words and 14 paired completions; no RTL
change or additional FPGA physical build was needed for this correction.

The active R5 relocatable service has no unresolved symbols. It is not a bootable
image and still needs a qualified startup/linker/TCM/cache/interrupt environment.
The BSP must call the versioned SHA operations, even though the linked historical
helper symbols remain available. Numerical head/bridge identity, label decisions
and earlier frozen regression baselines remain unchanged.
