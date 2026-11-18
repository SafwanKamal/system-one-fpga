# Persistent ARM service v16

Uses unchanged v9d hardware with a versioned ABI2 DMA driver. Defaults are
startup/transition-only weight verification and exact-prefix caching. The
per-request diagnostic mode retains a full SHA256 before every generation.

## Ownership boundary

`sysone_qwen_dma_v2` permits one open owner for the complete model. A loader
explicitly enters BEGIN_LOAD (generation advances), closes all mappings, then
seals the model (generation advances again). Sealing is refused while **any**
mapping remains, including mappings retained after their originating fd closes.
A sealed mapping cannot request writes or regain them with mprotect. Each
module instance has a random identity in addition to the generation counter.

An inference descriptor claims a lease that cannot perform loading/unsealing.
It pins the module and blocks concurrent device opens. The service hashes the
complete sealed model at startup, then checks its lease/generation and hardware
identity for every request. A mismatch faults the session and invalidates cache;
the operator must drain/stop, perform the transition and restart. It never tries
to continue an old session through changed weights or hardware. A controlled
reload performs full post-seal verification as well as the next service's
startup verification. Loading failure leaves weights unsealed and unusable.

This controls access through the DMA device and the coordinated deployment
lifecycle. Administrators able to use raw /dev/mem, reprogram the FPGA, alter
kernel memory or issue unrelated DMA remain trusted. It does not turn off
physical memory corruption or provide adversarial root isolation. Per-request
hashing remains available when that additional detection is required.

The service holds the existing inference lock for its lifetime; loading and
deployment take the same lock and check AP_IDLE. No hardware reset is issued
automatically. Existing v1 packages, bitstreams and source remain preserved.
Legacy runtimes that require writable weight mappings cannot use sealed ABI2;
use qwen_fpga_runtime_v16 with this driver. Do not invoke the old v8 launcher.

## Run

From the versioned source bundle, after canonical board ownership and preflight:

```sh
python3 scripts/v2/qwen_arm_service_v16.py serve \
  --package /var/lib/sysone/qwen-fpga-decoder-v9d-candidate1 \
  --socket /run/sysone-arm-v16.sock --ready /run/sysone-arm-v16-ready.json
```

Add `--verification per-request` to retain per-request hashing. Add
`--no-prefix-cache` for an uncached control. All modes verify startup bytes.

```sh
python3 scripts/v2/qwen_arm_service_v16.py request \
  --socket /run/sysone-arm-v16.sock --query 'Read /proc/uptime' \
  --conversation-id device-session-1
python3 scripts/v2/qwen_arm_service_v16.py request \
  --socket /run/sysone-arm-v16.sock --op reset-cache
python3 scripts/v2/qwen_arm_service_v16.py request \
  --socket /run/sysone-arm-v16.sock --op shutdown
```

There is one physical KV bank: switching conversation IDs discards reuse.
Reuse checks exact token prefix, kernel/model/runtime/boot/ownership identity
and physical scratch tag, rounds down to eight tokens, and recomputes final
logits. Generated answers are always fresh. Caching neither enlarges context
nor reduces allocated KV storage. Failed transactions discard pending metadata.

## Transition

Stop/drain the service first. The new loader refuses a busy inference lock,
non-idle hardware or concurrent DMA owner. It checks the source model, loads
all bytes, closes writable VMAs, seals, and verifies the resident bytes:

```sh
python3 scripts/v2/load_sealed_qwen_v16.py \
  --package /var/lib/sysone/qwen-fpga-decoder-v9d-candidate1 \
  --model /home/ubuntu/sysone-generation/Qwen3-0.6B-Q8_0.gguf \
  --out /path/to/new-transition-proof.json
```

Restart the service afterward. The optional systemd unit is supplied separately
and is not enabled automatically; it drains on SIGTERM without forcing SIGKILL.
Canonical BOARD_STATUS.json ownership still applies to hardware sessions.

## Validation

`tests/test_arm_service_v16.py` covers verification modes, proof requirements,
prefix invalidation, conversations and generation failure. The stdlib Linux
tests check the actual read-only hash path, byte corruption and socket lifecycle.
The target-only driver qualification runs before loading model bytes and issues
no neural commands. It checks exclusive opens, existing-VMA sealing rejection,
sealed write/mprotect rejection, inference transition rejection and VMA pinning.

The finite benchmark compares diagnostic/no-cache, startup/no-cache, then
startup/cache with bracketing diagnostic and startup controls. It measures
identical generated IDs, physical skipped work, controlled reload generation
change, new startup proofs and causal fixtures before/after. Historical v15
results remain separate: the diagnostic control here uses the same read-only
ABI2 path as production so verification policy is the intended variable.
