# Operand capture candidate admission

This is the next integration contract, not an admitted hardware profile.
Preserve `pipeline-cuts-large` and the qualified 125 MHz `dot7-large` package.

Use separate default-off `PROBABILITY_INPUT_CAPTURE` and
`LOCAL_EMBED_CONTROLS` parameters. Keep `PROBABILITY_PIPELINE` semantics intact:
zero uses the legacy arithmetic, one uses the existing two-stage kernel.
Input capture requires probability pipeline enabled and read latency at least
five. Its three-stage kernel fetches the exponent at L-4; the existing kernel
keeps L-3 and the legacy implementation keeps L-2. Reject invalid combinations
at elaboration. Both new defaults must retain Nexys output and cycle equality.

Reserve feature family `0x53591000` for either new parameter enabled. Retain
existing low eight feature bits, probability bit 8 and drain bit 9; use bit 10
for probability input capture and bit 11 for local embedding controls. The
fully enabled grouped candidate therefore reports `0x53591fff`. Preserve the
old `0x535907ff` word when both new parameters are zero. This family is distinct
from the experimental SYS3 relative-address ABI `0x53590300`.

Use candidate `operand-capture-large`, app `sysone-v2-operand-capture` and a
separate archive. Runtime, deploy and package admission must require the exact
feature word and all profile parameters, rather than interpreting the
experimental prototypes' stale feature word as an admitted profile.

Before integration, require completed experimental input-only and combined
input/embedding regressions: 32 frozen KR260 cases, two Nexys defaults and
output/encoder/request cycle equality against `pipeline-cuts-large`. Preserve
their snapshots and source manifests. Component arithmetic, attention alignment,
embedding whole-engine and BRAM-to-DSP composition evidence must remain bound
to the exact integrated implementations.

Then rerun the parameterized production hierarchy against these prototypes,
including default output/cycle equality and partial linear tiles. Freeze the
complete source inventory, adding the input kernel. Require full synthesis to
retain all 32 probability DSP AREG1/BREG2/PREG1 stages, 256 drain capture FF,
36 UltraRAM output registers, 896 local read capture FF and FIFO flag stages.
Inspect embedding local controls and actual area/inference changes.

Launch one 200 MHz synthesis, review it, then one placement diagnostic.
Do not route the older rejected placements. Review the new candidate's actual
200 MHz critical paths, hold, packing and congestion; the existing 0.5 ns
placement setup admission margin remains. Only legally routed positive setup
and hold with exact source/fixture/XSA/bit evidence permits packaging and
hardware validation. No fallback frequency may be described as a 200 MHz result.
