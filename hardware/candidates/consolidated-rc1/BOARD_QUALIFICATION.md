# Consolidated RC1 board qualification — 2026-11-08

**Later follow-up:** RC1 is now the default launcher and automatic boot startup.
See `BOOT_STARTUP.md` for the completed reboot verification and current running
service. This report preserves the earlier qualification session.

**Passed. RC1 is deployed and idle on the KR260.** The final live observation
identifies `sysone-qwen-decoder-v9e`, the sealed ABI2 DMA driver, the pinned
639,446,688-byte Qwen3-0.6B Q8_0 model and the qualified 125/250 MHz clocks.
The persistent service was stopped after testing; no test or inference process
remains. Canonical board ownership was released after recording the result.

Installed package: `/var/lib/sysone/hardware-consolidated-rc1-20261108`.
Boot ID: `43277fd8-b0f4-479c-9b50-c73df5ab2027`.
Archive SHA256:
`7ebe1a5ca5571cc71f8a05d60c41a39d3e9abf39d58173976119485e50700eac`.
The package/bitstream bytes are unchanged from the reviewed RC1 archive.

## Results

| Check | Result |
|---|---|
| Causal fixtures before and after service testing | 4,112 checks each; **8,224 total, worst absolute error 0** |
| Short cold CLI controls | Three system-file queries; correct tool name and arguments |
| Timed persistent-service calls | **18/18 exact prompt/generated-ID/text/call matches** to cold controls |
| Cache behavior | Conversation switch, identical prompt, explicit reset and changed prefix passed |
| Exclusive ownership | Ten actual driver negative checks plus competing-owner rejection passed |
| Model transition | Same pinned model reloaded and SHA-verified; generation advanced **4 → 6**, new services verified startup bytes |
| Capacity handling | Over-context requests rejected with service remaining READY |
| Runtime boundaries | Negative position, position2048, out-of-vocabulary token, batch crossing context end and empty batch rejected; **zero FPGA commands issued by rejected operations** |
| Long prompt | **1,454 tokens**, exact cold/persistent/repeated output parity; 1,448 tokens reused on repeat |
| Final integrity | **2,113 package files** verified; idle hardware, sealed model, no owner or VMAs |

The causal fixtures exercise layer 0 across all 2,048 positions, partial batches
and tile boundaries against the BF16 reference. The full-model tool generations
exercise all decoder layers. These are distinct scopes; the fixtures are not an
exhaustive all-layer numerical proof or a semantic-quality study.

Independent local validation rechecked all 28 full-generation records and both
causal case lists, expected short-query tool arguments, actual boot-ID results,
verification byte counts, physical prefill work, generation transition and final
identity. All 129 collected target evidence files passed their checksum seal.

## Bounded timings

Three short queries, six timed requests per mode on this boot:

| Persistent service mode | Mean client process time |
|---|---:|
| Full per-request SHA, cache disabled | 5.564 s |
| Startup SHA, cache disabled | 3.856 s |
| Startup SHA, prefix reuse enabled | 3.105 s |

The cached arm includes its first cold request. It measured 44.19% less client
time than the diagnostic arm on this bounded set. Startup verification covers
every resident model byte; it is not skipped. One-time process startup is separate
and retained in the raw ready records. Timings are not throughput, worst-case or
broad reliability results.

For the 1,454-token prompt, cold CLI wall time was 76.496 s. Persistent client
time was 73.827 s initially and 5.397 s on the exact-prefix repeat. Generated
answers were recomputed and matched exactly. This establishes this prompt's
capacity and reuse behavior, not general long-context semantic quality.

## Deployment and recovery

Live preflight found a **new boot running the stock starter image**, with no DMA
driver or resident model. The original 256 MiB `no-map` scratch reservation was
present, and the already-qualified ABI2 module matched the running kernel.
Under the canonical reservation and Linux inference lock, deployment verified
the installed v9e bitstream/overlay, programmed v9e, loaded the pinned ABI2
module, completed its negative checks, then loaded/sealed/verified the model.
The installed v9d and stock starter recovery images remain preserved.

The initial external qualification harness launch failed on an import path
before issuing test commands. Its source and logs were retained; the corrected
harness passed. The deployed candidate needed no code or package change.

The legacy global launcher and boot startup configuration are unchanged. Use
the explicit candidate runtime with ABI2; the legacy writable-mapping v8 runtime
is incompatible. Hardware programming, driver residency and model loading are
for this boot; a reboot needs the documented initialization procedure again.
No automatic service or boot migration was installed.

After reserving the canonical board status and verifying live identity, start
the service from a terminal on the board:

```sh
P=/var/lib/sysone/hardware-consolidated-rc1-20261108
sudo python3 "$P/scripts/v2/qwen_arm_service_candidate.py" serve \
  --package "$P" --socket /run/sysone-rc1.sock --ready /run/sysone-rc1-ready.json
```

It holds `/run/lock/sysone-inference.lock` itself. Send requests using the matching
`qwen_arm_service_candidate.py request` CLI; shut down through `--op shutdown`
and record final state before releasing canonical ownership. The full historical
benchmark sweep remains stopped.

Machine-readable attestation: `board-qualification.json`.
Raw evidence, test tools, failed attempt, independent validator and seal:
`build/v2/hardware-consolidated-rc1-board-20261108/` in the original checkout.
Remote raw evidence: `/var/lib/sysone/qualifications/rc1-20261108/`.
