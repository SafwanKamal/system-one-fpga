# Persistent ARM service v15

Targets the existing v9d image and package. All neural arithmetic remains on
FPGA. Every generation hashes all 639,446,688 resident weight bytes, before
issuing any request neural command. Startup also retains the original runtime's
full verification. Tokenizer, mappings, page table and RoPE initialization persist.
Prefix caching is deliberately disabled for this first comparison.

Run from a separately versioned source bundle; preserve historical packages.
After claiming canonical BOARD_STATUS.json and reconciling live identity:

```sh
python3 scripts/v2/qwen_arm_service_v15.py serve \
  --package /var/lib/sysone/qwen-fpga-decoder-v9d-candidate1 \
  --socket /run/sysone-arm-v15.sock --ready /run/sysone-arm-v15-ready.json
python3 scripts/v2/qwen_arm_service_v15.py request \
  --socket /run/sysone-arm-v15.sock --query 'Read /proc/uptime'
python3 scripts/v2/qwen_arm_service_v15.py request \
  --socket /run/sysone-arm-v15.sock --op shutdown
```

The daemon holds `/run/lock/sysone-inference.lock` until shutdown. Stop/drain it
before any deployment or direct hardware client. One worker serializes requests;
the Unix socket is mode 0600. Requests and responses are newline-delimited JSON,
bounded to 128 KiB. Client disconnect does not cancel an in-flight generation.
Invalid inputs leave READY intact; verification/inference failures enter FAULTED
and reject further generation. Health and shutdown remain available. A shutdown
requires idle hardware. SIGTERM drains and retains ownership until idle, without
resetting the FPGA. Never remove an existing socket without reconciling its owner.

The provided systemd unit is an optional installation template for the exact
benchmark bundle location. It is not automatically installed or enabled. Its
stop policy avoids SIGKILL while hardware may still be executing. Explicit
board ownership coordination remains required for unattended operation.

Finite benchmark (six standalone calls bracketing six service requests, three
prompts, two repeats per arm; same hardware/boot, no cache):

```sh
python3 scripts/v2/benchmark_arm_service_v15.py \
  --package /var/lib/sysone/qwen-fpga-decoder-v9d-candidate1 \
  --out /path/to/new-results-directory
```

The benchmark runs causal fixtures before/after, checks exact prompt/output IDs,
text and generated calls, checks byte-verification coverage, measures client
process wall time for both arms, and reports one-time service startup separately.
It leaves the service stopped. Queue delays/load, energy, long prompts and
multi-client throughput need separate measurement. No FPGA resources change.

Local checks:

```sh
python -m pytest tests/test_qwen_arm_service_v15.py -q
python3 tests/test_arm_service_linux_v15.py
```
