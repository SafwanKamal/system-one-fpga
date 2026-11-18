# Dedicated K26 boot-chain candidate

This directory contains new policy/hooks and local verification tools. It does
not replace the frozen typed MVP, DDR relay or qualified 200 MHz encoder.

Current generated/build artifacts are under
`build/v2/typed200-k26-boot-chain-v1`. The final layout image is
`image-layout-v2/BOOT.bin`. It is **local layout evidence, not deployment-ready**.
Read `docs/research/2026-10-16-typed200-k26-boot-chain.md` before using artifacts.

`stage.py` applies exact-anchor patches to **pristine generated** app sources;
do not rerun it against the existing staged app. It records the initial patch
provenance. Later host-test conditional/volatile-state changes are retained in
the attempt snapshots and final source hashes. For reproduction generate fresh
BSPs/apps at new paths, adapt the output path in a new script copy, then stage
the current sources. Do not overwrite the present attempts or firmware SDK.

The successful flow uses AMD 2025.2 Vivado `empyro`, the matching Vitis
embeddedsw repository, exact exported XSA/SDT, and the candidate-local Arm GNU
13.3.rel1 toolchain. Native commands need the existing `S:` repository alias as
their actual working directory; paths with spaces broke Lopper include handling.
The Vitis RPC platform-generation failures and earlier toolchain/path failures
remain in the build directory. Do not recreate them.

Host tests use installed Clang 16 with `-fsanitize=undefined
-fsanitize-trap=undefined`, strict warnings and assertions. `test_seal.c` tests
the state machine, `test_pmu_integration.c` executes the actual PMU hook with
mocked hardware, and `test_fsbl.c` executes the actual final FSBL hook with
mocked ASM/MMIO/SDK calls. They do not execute either target processor.

`audit.py` inspects actual boot ELFs/config/macros; `audit_image.py` independently
decodes the actual Bootgen headers, checks checksums, compares file-backed ELF
bytes/model/input, checks the sole application entry and allocation ranges.
`prepare_image.py` creates a **new** fresh-session layout directory; existing
images/sessions must not be reused for a new target campaign. Its one-cycle
deadline case is a first diagnostic fixture, not accepted-inference evidence.

The PMU seal is irreversible until reset. It is committed at a main-loop
boundary with interrupts masked, after active callbacks have returned; ISR/main
state is volatile under LTO. All normal IPI dispatch and scheduled callbacks
are blocked afterward. Only EM physical error events retain dispatch. K26
overtemperature shutdown remains active. Safety faults invalidate the run.

SSH-only access cannot recover this sole-R5 profile once A53/GEM resets occur.
The stock carrier starts from QSPI; the standard volatile SD/JTAG override uses
system reset, conflicting with the frozen cold-POR prerequisite. No target
script, reset-history clearing, QSPI writer, bitstream programmer or deployment
command is provided here. Resolve and review the physical launch/recovery route
first. Timing qualification also needs a reviewed passive observer and measured
service bounds. No WCET or hardware qualification follows from these local files.
