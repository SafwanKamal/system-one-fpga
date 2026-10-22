# Claude -> Codex: v9a integration handoff (2026-10-21)

Results: docs/research/2026-10-21-v9a-hardware-candidate.md. v9a is not active;
the board runs sealed v8 and the launcher is unchanged. Nothing in Codex's
evaluation files, datasets, gold answers or results was edited.

## What you need to adopt v9a

- Package on the board: /var/lib/sysone/qwen-fpga-decoder-v9a-candidate3
  (archive sha256 1a0317cb…5c64f2, 99 files, package-sha256.json inside).
- FPGA app: sysone-qwen-decoder-v9a-b3 (installed in /lib/firmware/xilinx).
  Overlay compatible string: xlnx,qwen-decoder-v9a-1.0.
- Runtime adapter: src/sysone/v2/qwen_fpga_runtime_v9a.py. It differs from
  runtime_v7 only in APP and the compatible string. Register offsets, scratch
  layout (PAGES/DESCRIPTOR/OUTPUT/ROTARY/CACHE), commands 0-10 and the 256-token
  context are unchanged. OUTPUT, ROTARY and CACHE must stay 32-byte aligned.
- Command runner: scripts/v2/run_qwen_fpga_command_v9a.py (same prompt, parser
  and timer boundaries as v7; takes the inference lock non-blocking).
- Swap and rollback: scripts/v2/deploy_qwen_fpga_v9a.py --direction
  candidate|restore (writes its record to --out, never into a package).

## Proposed, not done (your call)

1. Point a versioned launcher at the v9a package. The current global launcher
   (/usr/local/bin/sysone-qwen-fpga) checks for the v8 image and will refuse
   while v9a is loaded; I did not change it.
2. The KV cache is now head-major. Prefix-cache identity includes the kernel
   hash, so v8 prefix state is never reused by v9a; no action needed unless you
   copy cache contents between images.
3. Numerics differ from v8 in two FP32 summation orders (documented). Exact
   generated IDs matched v8 on the milestone command; broader quality checks
   belong to your evaluation methodology.

## v9c (validated; recommended)

- Package: /var/lib/sysone/qwen-fpga-decoder-v9c-candidate1 (archive sha256
  42f4c1c7…c00dc, 359 files). App sysone-qwen-decoder-v9c, compatible
  xlnx,qwen-decoder-v9c-1.0.
- Runtime adapter src/sysone/v2/qwen_fpga_runtime_v9c.py, runner
  scripts/v2/run_qwen_fpga_command_v9c.py, deploy scripts/v2/deploy_qwen_fpga_v9c.py.
- The package's model-manifest.json differs from v8's only in max_context = 1024.
  rope.bin has 1024 rows; the first 256 are bit-identical to v8's. KV cache for
  1024 tokens needs ~239 MB of the 256 MB scratch reservation; the runtime
  checks this.
- Measured: 7.08–7.22 s on the milestone command (v8 9.14 s); a 410-token
  prompt completed correctly in 21.1 s. Startup is ~0.25 s slower than v9a,
  likely from the 4-byte-at-a-time copy of the 512 KB RoPE table. A runtime
  change (write once per boot, or wider aligned copies) should recover it.
- Prompt-length limits in your harness can rise to 1024 total tokens. Whether
  longer histories help the 0.6B model is an evaluation question for you.

## v9d (validated 2026-10-22)

Same host interface, manifest and RoPE as v9c; only the app name differs:
sysone-qwen-decoder-v9d (compatible xlnx,qwen-decoder-v9d-1.0), package
/var/lib/sysone/qwen-fpga-decoder-v9d-candidate1 (archive e4e920f5…e6fda3),
adapter src/sysone/v2/qwen_fpga_runtime_v9d.py, runner and deploy scripts with the
_v9d suffix. Bit-identical to v9c. Long prompts are 13% faster (410 tokens:
18.3 s vs 21.1 s on the same boot); short commands are about the same.

Final recommendation: docs/research/2026-10-21-claude-hardware-recommendation.md.
