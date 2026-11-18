# Source-row / LINEAR BRAM candidate contract

Candidate: source-row-bram-large. App: sysone-v2-source-row-bram.
Exact fully grouped feature word: 0x53597fff (family 0x53594000).
New default-off parameters: INCREMENTAL_SOURCE_ROW and LINEAR_ACCUMULATORS_IN_BRAM.
Partial feature words are experimental and must not be admitted for deployment.

The first cut substitutes a modular source row recurrence for the token-times-stride
multiply. Clear on reset, launch and pass restart; correct token-width wrap. The
second cut selects a separate explicit block-RAM accumulator branch, preserving
one-clock read-first behavior, bank selection, drain/tag alignment and PASS_GAP.
Old distributed and implicit memory branches remain selected with both flags off.
Attention asynchronous read/modify/write storage is unchanged.

Admission requires the grouped private proof, production 32 KR260 cases, six
partial-tile cases and two Nexys defaults with exact outputs and encoder/request
cycles, plus current source/fixture hashes. Freeze 22 RTL sources only afterward.
Synthesis must retain all prior dot, probability input/PREG, local embedding,
UltraRAM output, physical capture, FIFO flag and drain stages. Additionally audit
LINEAR RAMB inference, READ_FIRST on both ports, DOA/DOB_REG zero, incremental
row registers and absence of LINEAR distributed accumulator cells. Fit must be
measured across the full design; isolated savings do not prove placement relief.

No route until candidate-specific hash-bound placement review with at least
0.5 ns setup margin and measured hold/congestion/packing. Export/package only
with legally routed positive setup AND hold. Runtime/package/deploy support recognizes only the exact new full profile.
The admission suite rejects stale/partial profiles and old apps claiming the
new options; see source-row-bram-admission-tests.json. No package exists.
Keep the qualified 125 MHz app and recovery package intact. No SYS3, high-DDR
executor, decoder generation, quality or hard timing guarantee is advertised.
