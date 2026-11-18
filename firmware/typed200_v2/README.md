# Active typed200 transport successor: explicit digest register encoding

Use this version for SHA-bearing submission, proposal and observation. It
supersedes the transport operations in `firmware/typed200/` and the frozen v1
`ti_mmio_start`, `ti_mmio_propose` and `ti_mmio_observe` helpers. All older files
remain preserved as historical artifacts. The numerical head and software bridge
remain unchanged. The existing session-only provision and ACK operations have
no SHA field and remain compatible.

Read the [transport review/evidence](../../docs/research/2026-10-15-typed200-transport-review.md)
and [native RTL integration report](../../docs/research/2026-10-15-typed200-integration.md).
The candidate RTL is unchanged: ABI `0x54590201`, contract
`8133633315487f8f322ecac49e95e7aca3801d00fccb4b4fba36026c5b2752d2`.

Digest byte arrays use conventional SHA256 display order. Hardware registers
carry the numeric 256-bit digest's least-significant 32-bit word first. Thus
register index i packs bytes `[28-4i,29-4i,30-4i,31-4i]` as one big-endian numeric
word. The first register value for this contract is `0x5b2752d2`, not the little-
endian interpretation of its first four display bytes. Ordinary session/request
UINT64 fields still use low word then high word. Do not apply one byte rule to
these different representations implicitly.

Use `ti200_start`, `ti200_admission_observe`, `ti200_copy_hidden`,
`ti200_propose` and `ti200_terminal_observe` from this directory. Submission and
proposal assemble the numeric digest words explicitly; observations reconstruct
the original 32 digest bytes. Terminal records stay held until eligible ACK.
Return values distinguish staging, active identity observation and terminal
observation; staging success is not proof of admitted or successful inference.

All prior ownership, Device-MMIO, coherent/noncacheable DDR, immutable deployment,
FPU/TCM/interrupt, token/segment validation and WCET prerequisites still apply.
The functions are finite and non-polling, but a bus load/store can stall. This is
not target firmware execution or a successful-inference deadline certificate.

The host test checks known numeric digest words independently, exports the
actual C-generated request/proposal frames, and checks inverse terminal decoding.
The RTL suite replays those exported words through the real AXI-Lite endpoint.
The linked R5 object also contains preserved legacy helper symbols; the future
BSP must use the versioned SHA operations above, not those legacy symbols.
