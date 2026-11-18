# R5 inference control and classifier heads deployed with Linux running

2026-10-17. The live KR260 now uses R5 to issue encoder requests and compute
the model's classifier/slot heads. Linux continues running and handles
tokenization, request transport and formatting of the R5-produced labels.
The qualified PL app and loaded model were reused without reconfiguration or
reload. JTAG stayed stopped.

The existing command now uses R5:

```sh
sysone-infer "show me flights from denver to boston tomorrow"
```

`--dataset atis` is the default; clinc, hwu, sgd, multi, msrp and sick select
the other explicit dataset paths. `--json` includes R5 integer logits, chosen
label indices, encoder cycle counts and completion/cleanup information.
This client returns labels and logits; probability/confidence reporting and
the previous Python automatic routing policy are not implemented here.

## What runs where

- Linux tokenizes text and supplies token IDs and selected-row descriptions.
  It does not issue the operational PL RUN or compute operational head logits
  or winning labels. NumPy head computation in the validation runner is only
  the independent reference comparison.
- Fixed R5 firmware in private 64KiB ATCM checks the encoder identity/build,
  writes token IDs and the encoder descriptor, issues RUN, waits for DONE and
  checks status. It then computes pooled/token/pair head logits from the
  existing DDR model and performs binary64 scaled argmax with first-index ties.
- PL remains `sysone-v2-attention-context-capture` at199999998Hz. Model SHA256
  remains4129baded344729ccc7ef6a3f0a2b34799280a91d88173ae1c0b197cdef8c3bb.
- The mailbox is a bounded512KiB region at62400000 within the existing256MiB
  Linux no-map reservation. IDs62100000, hidden62101000 and program60000400
  retain the working deployment's layout. No BTCM or RPU mode change was needed.

This is still the trusted-Linux path; no new exclusive-owner firewall or hard
deadline claim is made. The generated head table is tied to the existing model.

## Actual validation

All350 frozen cases were run through the live R5-controlled encoder and R5
heads while Linux stayed running. All1798 head jobs and191401 integer logits
matched the frozen reference, as did every scaled winning label. Coverage
includes ATIS, CLINC, HWU, multi-CLINC, SGD, MSRP and SICK. This establishes
numerical agreement, not perfect ground-truth model accuracy.

The complete target comparison took77.393seconds including Linux supervision,
TCM preparation and reference checks. It is not a latency bound. The installed
CLI was subsequently exercised independently and returned `atis_flight` and
the expected slot labels for the Denver/Boston/date example.

Before hardware execution, the native C heads matched the same350 cases and
191401 logits. The actual ELF passed Cortex-R5F emulation of startup, VFP,
encoder register transactions and head output against a modeled completed
encoder response. The original non-FPU Cortex-R5 emulator selection rejected
VFP; selecting the correct R5F model resolved this without changing firmware.
The old unsupported VBAR instruction is absent.

## Linux-managed lifetime and current state

The separate fixed-image module reuses the tested two-bank ATCM lease/session
engine. It holds a Linux PL clock reference, initializes and verifies the full
private64KiB TCM, and starts R5 through normal firmware PM APIs. Each request
finishes with a fresh `R5: INFERENCE PASS` trace and DONE mailbox before Linux
stops R5 and confirms release. R5 is idle/off between requests; the module
stays loaded for the next request. A30second kernel recovery timer bounds the
R5 lease lifetime. An uncertain encoder RUN never triggers a blind PL unload.

`sysone-infer` serializes requests with the existing flock lock. Root stage:
`/var/lib/sysone/r5-inference/deploy-v2`. The exact prior A53 entry script is
preserved there as `sysone-infer-a53.before`. The previous A53 client and all
model/PL assets are unchanged. This is a current-boot CLI deployment; no boot
configuration or network service was installed.

Final health: same boot6c80ec1a-e7ae-473f-b169-d54f129615d1, CPUs0-3online,
taint12288 (unchanged O/E), FPGA operating, both PL clocks199999998Hz with
enable/prepare1/1. R5 session pinned/reserved/mapped/may_run/loaded/quarantine
all0, leases0, errors0. UART closed; no new observed kernel fault. Dashboard
remains stopped because the encoder owns PL. No power-cycle is pending.

Firmware ELF SHA256:
e5dcdf1c863c917bb4c591b9820216c5beea81883a70af60044b735eee2492f4.
Module SHA256:
e6f834a35a9c73c1bf768aa2ff05b049b52b418e9b1eb0c204f4e1db338965a0.

Evidence and source candidates are under
`build/v2/typed200-linux-r5-inference-v1` and
`firmware/typed200_linux_r5_inference`. The first deployment staging attempt
sent an oversized inline module payload and SSH closed before the separate
R5 launch command was sent. Corrected staging copied the already-built module
into the root-private directory with hash verification. Failed attempts and
their plans remain retained. Earlier host checks needed a Windows-only import
fix and a checked fread return; both corrected host runs passed.

No JTAG, raw Linux PS/RPU MMIO, PL/model/kernel rebuild, reboot, commit or push.
All11056 prior sealed files are preserved. The companion validation JSON seals
new code and successful evidence; HANDOFF.md remains mutable.
