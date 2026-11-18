# CURRENT BASELINE: RC1 — ADOPTED 2026-11-08

RC1 is now the supported **KR260 hardware/runtime baseline**, including the default
launcher and automatic boot startup. This section supersedes older current-state
claims below about a v8 default launcher, v9d active image, stopped service or
unmigrated boot setup. The dated research history, owner rules and separate
software capability work remain preserved. Read [hardware/BASELINE.md](hardware/BASELINE.md)
and [hardware/baseline.json](hardware/baseline.json) before changing the baseline.

## Current operational reference

- **FPGA/model:** v9e (`hls/qwen_decoder_v9e/`), Qwen3-0.6B Q8_0,
  639,446,688 bytes; model SHA256
  `9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`.
- **Profile:** hidden1024, FFN3072, 28 layers, 16 query/8 KV heads, head128,
  vocabulary151936, context2048 total, prefill batch8; 125/250 MHz clocks.
- **Precision:** INT8 block32 matrix activations/INT32 dots; FP32 scaling,
  norm/attention/residual arithmetic; BF16 RNE K/V storage. No CPU NN fallback.
- **Package:** `/var/lib/sysone/hardware-consolidated-rc1-20261108`;
  local archive `build/v2/hardware-consolidated-rc1/deployment-r2.tar`, SHA256
  `7ebe1a5ca5571cc71f8a05d60c41a39d3e9abf39d58173976119485e50700eac`.
- **Boot bundle:** `/var/lib/sysone/rc1-default-v1`; source/configuration and units
  in `firmware/rc1_default/`, installer `scripts/v2/install_rc1_default.py`.
- **Default command:** `/usr/local/bin/sysone-qwen-fpga`, now a client for the
  persistent RC1 service, retaining `--query`, `--out`, `--max-tokens` and flat
  output records. Default result path is outside immutable packages:
  `/var/lib/sysone/rc1-results/last-command-result.json`.
- **Boot:** `sysone-rc1-init.service` runs after DFX manager readiness, checks
  hashes/reservation/kernel/module, programs v9e, loads/seals/verifies all model
  bytes. Enabled `sysone-rc1.service` then verifies startup bytes independently
  and must report READY. Kernel/module pin: `6.8.0-1036-xilinx`.

Last verified boot/default receipt:
[boot-startup.json](hardware/candidates/consolidated-rc1/boot-startup.json).
It records the service enabled/running/READY on boot
`e887c9d8-df37-494c-b1e5-7b45eac4be0d`. That is historical verification evidence,
not live ownership authority: always use the **one canonical original checkout's
`BOARD_STATUS.json`** and `scripts/v2/board_status.py` for new sessions. Never use
an archived observation or a second status-file copy as a coordination lock.

## Use and board ownership

Reserve/reconcile the board first; credentials belong in a local secure prompt,
never chat, arguments or logs. On the board:

```sh
sudo sysone-qwen-fpga --health
sudo sysone-qwen-fpga --query 'Read /proc/uptime' \
  --out /var/lib/sysone/rc1-results/uptime.json --max-tokens 64
systemctl status sysone-rc1-init.service sysone-rc1.service
sudo journalctl -b -u sysone-rc1-init.service -u sysone-rc1.service
```

Startup SHA and exact-prefix reuse are defaults. `--no-prefix-cache` forces one
cold request; `--conversation-id` / `--reset-cache` control the single KV bank.
The service intentionally owns the Linux inference lock and exclusive sealed
DMA lease. Its nonzero `owner_tgid` matching the service PID is expected while
running. Stop/drain it before programming, raw fixtures or model changes:
`sudo systemctl stop sysone-rc1.service`. Require owner/VMAs released, then let
lock-aware tools acquire the lock themselves; do not nest acquisitions. Restore
with `sudo systemctl start sysone-rc1.service`, verify health/inference, record
actual state and release canonical ownership. Failures with uncertain identity
must be recorded unknown. No forced kill, reset or stale-owner takeover.

## Verified results and limits

- Consolidated qualification: **8,224 causal checks, worst error 0**; 28 full
  generations checked, including 18 timed service calls with exact token/text/call
  parity to cold controls. Driver negatives, competing owner, reload generation
  4 → 6, cache/reset and context/boundary checks passed.
- Short-request means (six/mode, cached arm includes its first cold request):
  per-request SHA/no-cache **5.564 s**, startup SHA/no-cache **3.856 s**,
  startup SHA/prefix reuse **3.105 s**. A 1,454-token persistent request measured
  **73.827 s → 5.397 s** on its identical repeat, reusing 1,448 prompt tokens.
- Actual reboot: automatic model load/seal/full SHA, changed boot and module
  identity, **12 default-launcher generations checked** with exact generated-output
  parity across boot. Then **4,112 post-reboot causal checks, worst error 0**;
  default service restored, enabled and READY. Initialization took 72.274 s plus
  3.008 s service startup, excluding earlier OS/network boot time.
- Causal fixtures cover layer 0 through 2,048 positions/tile boundaries; full-model
  generations exercise all layers. One board/one reboot, bounded development
  evidence. Keep timing boundaries, numerical profiles and semantic-quality
  limitations with the results; do not add component speedups or relabel old runs.

Reports: [hardware qualification](hardware/candidates/consolidated-rc1/BOARD_QUALIFICATION.md)
and [boot/default verification](hardware/candidates/consolidated-rc1/BOOT_STARTUP.md).
Raw/sealed evidence: `build/v2/hardware-consolidated-rc1-board-20261108/` and
`build/v2/rc1-default-boot-20261108/`. Adoption references commits `667cd39`
(consolidation), `2893614` (qualification) and `1969bdd` (default/reboot).

## Rollback and future changes

[hardware/BASELINE.md](hardware/BASELINE.md) contains the full operator procedure.
First reserve/mark the board and preserve a fresh evidence directory. To remove
RC1 automatic defaults without reprogramming:

```sh
sudo systemctl disable --now sysone-rc1.service
sudo systemctl stop sysone-rc1-init.service
sudo cat /sys/class/misc/sysone_qwen_dma/ownership
```

Require `sealed=1 loading=0 owner_tgid=0 vmas=0`. Use the explicit RC1 cold CLI on
this boot while the socket service is stopped; re-enable with
`sudo systemctl enable --now sysone-rc1.service` and verify health/inference.
The guide also gives the preserved v9d image / v16 ABI2 service recovery commands
and return-to-RC1 procedure. That rollback sequence was not executed during this
adoption; its components retain their prior qualification evidence.

The original launcher backup is
`/var/lib/sysone/qualifications/rc1-default-20261108/rollback/sysone-qwen-fpga.original`.
Do not restore/invoke its v8 runtime alone: it requires a matching image and
writable-mapping driver/model setup. The current baseline and v9d/v16 recovery
use sealed ABI2. Preserve old bitstreams, packages, module copies, model bytes,
failed attempts and all seals. Candidate filenames remain unchanged for hash
fidelity. New hardware/runtime/kernel changes need separate versioned artifacts
and appropriate qualification against RC1. The full historical sweep stays
**STOPPED**; adopting RC1 does not restart it.

---

## Preserved research and earlier handoff history

# INTERACTIVE MAINTENANCE SOFTWARE RETEST — COMPLETED 2026-11-04

The pinned Qwen3-1.7B Q4 checkpoint now has a software-only interactive
proposal path with a supervised action head over its frozen hidden states.
The centered head scored 41/120 fresh and 4/64 conditional, compared with
15/120 and 0/64 for the previous one-shot baseline. Incorrect schema-valid
plans rose from 67 to 102. The independent general route replay scored
170/200 BFCL and 9/12 simulated episodes. Keep maintenance at the proposal
stage. The software results use the existing template-derived cases.

Recommended narrower demonstration is exact-prefix reuse on the existing
KR260 Qwen decoder. Reanalysis of the two sealed runs pairs 224 structured
requests and finds 70.71% fewer evaluated prompt tokens, 65.0% less mean
prefill time and 26.2% less mean request wall time. The earlier study
verified 328/328 exact generated-ID sequences across both representations.
For an RTL-focused demonstration, the existing four-lane prefill result
provides a shared-weight-streaming baseline.

Report and external hardware references:
docs/research/2026-11-04-interactive-maintenance.md.
Local runner: scripts/v2/interactive_maintenance_20261104.py.
Evidence and fitted heads: build/v2/interactive-maintenance-20261104/.
The new tests ran on the host. The historical hardware sweep stays STOPPED.

# SOFTWARE CAPABILITY COMPARISON — COMPLETED 2026-11-02

User-authorized quantized software comparison is complete. Report:
docs/research/2026-11-02-quantized-model-capability-comparison.md.
Compact evidence/seal: docs/research/model-capability-2026-11-02/.
Raw outputs, prompts/token IDs, source snapshots, protocols and earlier attempts
remain under build/v2/model-capability-20261102*. No inference jobs remain.

Nine pretrained quantized profiles were screened. Larger-set results at 2,048
total context / 256 output, greedy, thinking disabled:

| Profile | Fresh /120 | Conditional /64 | BFCL /200 | Simulated two-turn /12 |
|---|---:|---:|---:|---:|
| Qwen3-1.7B Q4 | 15 | 0 | 172 | 9 |
| Qwen3-4B Q4 | 32 | 4 | 170 | 4 |
| Qwen3-8B Q2_K | 28 | 6 | 171 | 12 |

Decision: defer a new FPGA port for the combined objective. Qwen3-1.7B Q4 is an
economical next SOFTWARE baseline, not an established strongest deployable
model. The 8B profile has the highest four-axis mean but only a narrow unproven
DDR margin; its 12 successful toy episodes do not establish reliability.
All tested complete-plan configurations perform poorly. Memory estimates do not prove
allocation, arithmetic equivalence or routed fit.

Matched precision totals: 1.7B Q4=12/32, Q8=12/32; 4B Q4=12/32, Q8=13/32.
Four paired 32-case reasoning
ablations at 4,096 context / 1,024 output did not improve total correctness.
Qwen3.5 maintenance answers exhausted that output budget; publisher-sampled,
larger-budget reasoning remains untested. Do not infer a global capability
ceiling. Thresholds remain undecided. Further software directions are a simpler
interactive tool/plan interface with matched adaptation, or a separately scoped
larger-budget reasoning study if its latency could be useful.

Verification: 2,716 saved task records re-scored without discrepancies; 13 model
file hashes and stage/data IDs verified; 23 focused tests passed; 210 positive
BFCL fixtures pass. Existing adapted checkpoint and base weights are unchanged.
This is public/template-derived development evidence, not a blind reliability
qualification. No board access, new FPGA build, paid compute, new training or
real external tool execution occurred. Execution-enforcement work remains
deferred, and the historical full hardware sweep stays STOPPED.

# PROJECT PRIORITY — 2026-11-02

User directs capability-first research for BOTH maintenance planning and general
tool use. First establish the most capable model/profile feasible on the KR260;
then measure whether it offers useful bounded reliability. User has not set
error, latency or context thresholds: research feasible tradeoffs first, then
discuss thresholds. Defer the proposed maintenance execution/enforcement layer
until capability/reliability evidence justifies it. Do not treat the current
Qwen3-0.6B baseline or the previously proposed 1.7B candidate as an established
capability ceiling. Preserve historical benchmark evidence and board protocol.

Initial source/implementation research is saved in
docs/research/2026-11-02-model-capability-feasibility.md, with 15 pinned public
metadata snapshots and seven analytic tensor/cache budgets under
docs/research/model-envelope-2026-11-02/. No new candidate inference, hardware
build, board access or model selection occurred in that research. Larger-model
fit and capability remain to be measured. Full historical sweep stays STOPPED.

# SHARED BOARD AUTHORITY — 2026-10-21 (takes precedence over older board-use restrictions)

The user grants BOTH Claude and Codex authority to program the KR260. Board
activity must remain serial. The single authoritative live coordination file is
BOARD_STATUS.json at this original checkout's absolute path (canonical_path
inside the file). All agents/worktrees must use that SAME physical file. Do not
maintain a second board-status copy or use historical notes below as live status.

Use scripts/v2/board_status.py [--file <canonical absolute path>] show/reserve/
begin/record/release. Read the protocol embedded in BOARD_STATUS.json. Reserve
before any board session; keep the returned claim for the complete operation.
Only the owner uses that claim. The helper serializes file updates with an OS
lock; persistent reservations prevent simultaneous owners between commands.
Actual hardware commands must also hold /run/lock/sysone-inference.lock on the
board. Offline RTL/synthesis/CPU work can proceed without board ownership.

Verify live identity/processes after reserving. begin marks the board changing
before operation; record verified identity/evidence afterward, then release.
On failure record unknown; never leave an old ready identity after programming.
No automatic timeout/takeover. Coordinate stale ownership rather than stealing
it. Current status was initialized from v5 verification evidence, not a new live
probe; the next owner must reconcile live state before use. Do not store secrets.

Either agent may program a separately versioned candidate. Preserve sealed v8
baseline packages and all existing benchmark evidence. Keep the full sweep
STOPPED; shared programming authority does not restart that campaign. The JSON
file holds current board identity/ownership; the material below is historical
project and experiment context, not an alternative live board-status ledger.

---

# SEALED OWNERSHIP AND PREFIX SERVICE v16 - COMPLETE 2026-10-22

User-authorized v16 implemented/deployed and benchmark COMPLETE. Live DMA driver
is sysone_qwen_dma_v2 ABI2, pinned639446688-byte Q8 model SEALED. Same v9d FPGA,
boot, clocks/profile/legacy packages and launcher. New runtime REQUIRED:
/var/lib/sysone/benchmarks/persistent-arm-service-v16/bundle-r2.
Legacy writable-mapping runtimes cannot use sealed ABI2. Do not invoke old v8
launcher or old runtime_v9d/v15 on this driver. New runtime_v16 uses read-only
mappings, exclusive inference lease and startup full SHA. Modes:--verification
startup(default) or per-request(diagnostic), prefix caching default enabled;
--no-prefix-cache for control. Single cache bank; conversation changes reset.

18 timed calls,6/mode,3 short prompts,2 repeats:mean client wall diagnostic5.5990s,
startup/no-cache3.8894s,startup/cache3.1553s. Saves1.7095s verification+0.7341s cache;
combined43.65%. Includes first cache-cold request. Startup2.957-2.996s separate.
All exact IDs/text/calls match each other AND preserved v15.10 actual driver
negative tests,4 cache checks,capacity rejection,controlled load generation4->6,
full startup proofs,616 causal checks before+after all PASS.14 focused local
checks+2 Linux integration checks pass. No FPGA-resource/energy claim.

Services STOPPED, no unit installed/enabled; current ABI2/model residency is for
this boot. Original boot startup NOT migrated. Target driver/module/context
ownership final:sealed1,loading0,owner_tgid0,vmas0. New systemd template and
instructions:firmware/arm_service_v16. Canonical BOARD_STATUS.json remains live
state authority; final identity recorded and reservation released.
Evidence build/v2/persistent-arm-service-v16/evaluation,102-file evidence-seal,
independent-validation.json,driver+rollback binaries and source snapshots.
Report docs/research/2026-10-22-sealed-verification-prefix-v16-results.md.
First candidate refused existing DMA VMA ops; automatic rollback+full verification
passed. Corrected r2 preserves kernel callbacks. Original failed attempt retained
under attempt1 and deployment; successful receipt under deployment-r2. Never
overwrite failures or old seals. Full sweep remains STOPPED.

---

# PERSISTENT ARM SERVICE - 2026-10-22

V15 implemented and hardware benchmark COMPLETE. Full per-request resident SHA
retained; no prefix reuse or CPU NN. Three short tool prompts, two repeats/arm:
mean client process wall 6.9267s standalone -> 5.5772s service (-1.3495s,19.48%).
One-time service startup2.9854s separate.12/12 exact prompt/generated-ID/text/call
parity;616 causal cases before+after each passed. Same v9d boot/image/clocks/DMA.
Candidate service STOPPED; no systemd unit installed/enabled or launcher change.
Source bundle additive at /var/lib/sysone/benchmarks/persistent-arm-service-v15/bundle.
Sources: qwen_arm_service_v15.py (src + scripts), qwen_weight_verification_v15.py,
benchmark_arm_service_v15.py; unit/instructions in firmware/arm_service_v15.
Evidence:build/v2/persistent-arm-service-v15/evaluation,62-file evidence-seal.json.
Report:docs/research/2026-10-22-persistent-arm-service-v15-results.md.
Canonical BOARD_STATUS.json remains live ownership authority; no FPGA resource
change or energy claim. Full sweep STOPPED. Runtime remains explicitly v9d.

---

# BENCHMARK STATUS — 2026-10-22 (latest benchmark context)

Prefix-cached comparison v14 COMPLETE and SEALED at build/v2/v9d-prefix-comparison-v14.
Same frozen v13 logical prompts/workloads,224 tasks/arm. Full sweep STOPPED.
Canonical BOARD_STATUS.json only live authority; Codex prefix-comparison-v14
reservation released after verified final identity. Consult canonical status for
later ownership. v9d remains active; no programming/launcher/package changes.
FPGA in-memory metadata only, identity/tag checked, reuse rounded down to8-token
prefill boundary with final logits recomputed. Reset between case+arm and causal
fixtures. All328 cached FPGA generated-ID sequences must match sealed v13 cold
controls. New live12-request cold/cached qualification must pass before evaluation.
CPU persistent single-slot localhost llama-server, exact frozen IDs, raw responses
and cache_n/prompt_n telemetry. Fresh same-server cold+cached controls (896 records,
656 executions+240 overflows); FPGA cached448 records328exec+120overflows. CPU
qualification12/12 exact IDs,2865 reused/1389 evaluated tokens.16 focused tests pass.
Sources/inputs frozen: do not edit during runs. Prompts/reducer/scorer unchanged.
One physical cache bank: process each case+arm sequentially. No cross-chain reuse.
CPU model/server startup separate from warm latency; do not compare CPU v13 cold
process wall to new server request wall as a cache-only speedup. FPGA historical
v13 cold latency comparison is across matching-identity runs, not interleaved.
Methods: docs/research/2026-10-22-v9d-prefix-comparison-v14.md.
Scripts: prepare_prefix_comparison_v14.py, run_prefix_comparison_v14.py,
ssh_prefix_comparison_v14.py; cpu_prefix_server_v14.py; prefix_cache_v14.py.

CPU completed896 records/656 inferences, server closed and CPU phase sealed.
Original status is ATTENTION: frozen strict bit-exact gate found16 differences,
all JSON formatting only. All328 cached pairs preserve parsed outcomes/correctness;
CPU NOT bit-exact. cpu-validation.json and cpu-output-differences.json retain audit.
Supplemental cold/cold/cache/cache/cold first-token probe reproduces shape-dependent
logit/template changes, consistent with official llama-server batch-size warning.
Do not overwrite raw attention status or claim all original validation gates pass.
FPGA completed all328 exact generated-ID matches against sealed v13 cold controls.
No relaxation of FPGA gate. Both cached backends:JSON224/224;history84/104 fitting
correct+120 rejected (same per-length counts as v13). Cached CPU312/328 exact IDs,
16 formatting-only differences, all semantic outcomes preserved; original strict
CPU gate FAILED and raw attention status preserved. Overall passed=false reflects
that gate; semantic_and_cache_validity_passed=true. Do not claim CPU bit identity.
Common-fit104-step mean warm CPU cold JSON0.963s/history2.327s, cached0.696/0.711s.
FPGA v13 cold7.921/22.107s; cached5.889/6.275s. History/JSON latency gap shrinks
2.79x to1.07x FPGA;1.02x cached CPU. Decode unchanged; FPGA prefill JSON3.195->1.163s,
history18.329->2.497s. Full history latency advantage largely recovered by cache;
JSON context/accuracy benefits remain. All-executed FPGA evaluated8464 JSON tokens
(20432 reused) and6202 history tokens (50088 reused); denominators differ224/104.
Common-fit evaluated4144 JSON vs6202 history. Full logical demand unchanged.
All16 causal checkpoints2656 vectors passed, worst2.384185791015625e-7. Source/
binary/package/live identities and prior seals passed; v13 baseline identity
matched. Board ready/released, SSH and CPU servers closed. Full sweep STOPPED.
Root seal, independent CPU seal, comparison-summary.json and requests-comparison.csv
retain evidence. CPU formatting/logit probe and original failed status preserved.



---

## Previous v13 benchmark context (preserved)

JSON-state versus full reference conversation comparison v13 is COMPLETE and SEALED at
build/v2/v9d-retention-comparison-v13/evaluation. User explicitly authorized v9d.
Codex reservation released after final v9d verification; consult canonical
BOARD_STATUS.json for subsequent live ownership/identity.
Live v8 preflight passed; authorized swap to existing v9d candidate1 completed.
Boot/DMA/launcher/clocks/services preserved. v8 package immutable; launcher still
expects v8 and MVP/full-sweep services remain inactive. Do not invoke launcher
on active v9d. Use explicit candidate package and new runtime for this experiment.
Full sweep STOPPED. Do not touch frozen v13 source/inputs during execution.

Same sealed v12 six workloads, known data reused intentionally for representation
comparison:224 tasks per arm,448 records/backend, context1024/output48. JSON129
input tokens. Entire prior observation/query + canonical correct assistant reply
history, no truncation, no current gold answer. Teacher-forced retention, not
closed-loop.328 executions +120 explicit history capacity rejections/backend.
CPU matched context1024; separate CPU4096 diagnostic ran only120 overflow
inputs. Disable prefix reuse; CPU actual CLI IDs verified using corrected LF
framing. Latency comparisons within backend and common-fit steps; do not compare
CPU process wall to warm FPGA as speedup. Retain separate prefill/decode timings.

Development first attempt24/24 interrupted by packaging-source change, separately
sealed. Development-r2 35/36; cross-entity count error. General entity-separation
instruction revised; development-r3 fresh values35/36 (JSON18/18,history17/18),
all parsed and actual IDs verified. Freeze history semantic errors as outcomes,
not a perfect-accuracy gate.12 protocol/framing/ownership tests passed.
Worker holds board kernel lock; causal block and300-position before/after checks,
block checks after each chain, before/after package/live inventories. Collector
records verified v9d status and releases only once finite unit ends and lock is
free. No persistent service/launcher update. On uncertainty retain claim.
Scripts: prepare_retention_comparison_v13.py, run_retention_comparison_v13.py,
ssh_retention_comparison_v13.py, report_retention_comparison_v13.py.
Methods: docs/research/2026-10-22-v9d-retention-comparison-v13.md.

All audit gates passed. CPU and FPGA identical counts:JSON224/224;history84/104
fitting correct+120 context rejections. Length16:26/32 history correct;length32:
29/36 correct+28 rejected;length64:29/36+92 rejected. History limit step19 onward;
JSON129 tokens throughout. Required all-task inputs275251 versus28896 (JSON89.5%
fewer); common-fit104 steps56290 versus13416 tokens. History19 semantic errors
(15 status,7 count,3 both)+1 budget/extraction failure; JSON no errors.327/327
both-parsed CPU/FPGA pairs agreed, including wrong answers; raw text311/328.
Common-fit mean CPU prompt+decode2.038s JSON vs3.536s history; CPU wall3.551 vs5.028s.
FPGA warm request7.921 vs22.107s (history2.79x); prefill3.195 vs18.329s (5.74x).
CPU4096 overflow diagnostic114/120 correct; all6 errors missing/error -> ok.
Not uniform4096 rerun or cached-history benchmark. All8 causal checkpoints1328
vectors passed, worst2.384185791015625e-7. Before/after v9d live/package matched;
boot/DMA/launcher/services preserved. v8/old seals verified; CPU phases sealed1554
and482 files, final root seal saved. Final canonical ready record, release, SSH
close verified. v9d LEFT ACTIVE, launcher remains v8 and inactive: use explicit
v9d package/runtime; do not blindly invoke original launcher. Full sweep STOPPED.


---

## Previous v12 benchmark context (preserved)

Fresh paired long-chain retention v12 is COMPLETE and SEALED, separate at
build/v2/v8-json-retention-v12. Six mixed/long-gap sequences16/32/64 steps,
224 primary+12 exact repeats per backend. New seeds202610211300–305 and
state/query freshness checks against prior data. Frozen v10-r3 prompt/parser,
corrected v11-r2 CPU framing; all actual CLI input IDs verified,129 input tokens,
output48/context256, prefix reuse disabled.37 focused tests passed.
CPU and FPGA each passed224/224 primary+12/12 repeat controls. All six chains
survived completely;177/177 distinct primary inputs per backend. Status results
ok87/87, missing75/75, error62/62. All236 actual input-ID sequences matched across
CPU/frozen inputs/FPGA;236 semantic pairs agreed. Raw text205/236 exact; all31
differences independently verified as JSON whitespace/Markdown fences only.
All12 FPGA repeated generated-ID sequences exact; CPU repeat text also exact.
All8 causal checkpoints/128 vectors passed, worst abs7.152557373046875e-7.
All source checks, prior seals and269-file v8 seal passed. New evidence sealed;
preserve frozen sources/inputs/raw data. Host-managed state/read-only answers:
these64 steps do not demonstrate long model context or closed-loop robustness.

Initial board read found Claude owning v9c testing. CPU work proceeded offline.
Claude restored v8/released at revision16; Codex then reserved and verified live
v8 under the kernel lock. Consult canonical BOARD_STATUS.json for current live
ownership; no alternative status ledger. No programming/package/launcher/service
changes. FPGA causal checks run before, after each chain and after the complete
experiment. Before/after deployment/live inventories matched; SSH closed and
reservation released at revision20 after verified-ready record. Consult canonical
status for later ownership changes. Full sweep remains STOPPED, closed-loop
excluded. paired-summary.json/comparisons CSV+JSON/repeat-checks.json retain gates
and detailed results; independent CPU-phase seal also preserved.
Scripts: prepare_v8_json_retention_v12.py, run_v8_json_retention_v12.py,
ssh_v8_json_retention_v12.py, report_v8_json_retention_v12.py.
Methods: docs/research/2026-10-21-v8-json-retention-v12.md.

---

## Previous v11 paired qualification context (preserved)

Small fixed-prompt paired CPU/FPGA qualification v11-r2 COMPLETE, separate at
build/v2/v8-json-retention-v11-r2. Always consult canonical BOARD_STATUS.json for
ownership/live identity. No programming/launcher/service changes; v8 preserved,
FULL SWEEP STOPPED. Two fresh8-step observation traces+4 repeats=20/backend,
all129 input tokens/output48, same v10-r3 instruction/parser. CPU20/20 passed.
FPGA executes only this finite unit with kernel lock; before/after causal fixtures
and deployment/live inventories required. Source/runtime snapshot from sealedv8.
34 focused tests passed. Docs 2026-10-21-v8-json-retention-v11-fpga.md.
All gates passed: CPU20/20 and FPGA20/20 parsed/correct (16primary+4repeats each),
all20 actual input-ID sequences matched and20 semantic records agreed. Raw text
19/20 matched; one pretty-object versus fenced-object difference, same values.
All4 FPGA repeat generated-ID sequences exact. Both16-case causal checks passed,
worst abs7.152557373046875e-7. Full resident model SHA verified during startup.
Before/after v8 package/launcher/image/boot/clocks/DMA/services unchanged. Final
kernel lock free, SSH closed, shared status recordedready and ownership released
(revision12 at completion; consult canonical file for later ownership changes).
qualification-summary.json, paired-comparisons.csv/json, repeat-checks.json and
CPU/FPGA/board evidence sealed separately. Prior269 v8 and all recent benchmark
seals verified unchanged. This qualifies only the small FPGA workload, not the
CPU64-step result or closed-loop. No full-sweep restart or programming occurred.

IMPORTANT input-parity finding: actual llama.cpp verbose token logging found
the CLI removes one trailing LF from prompt files. Prior CPU records contained
nominal host-tokenized IDs; equal counts129 hid final-token198 versus271.
Historical CPU quality scores remain observations for their actual CLI prefix,
but prior nominal IDs do not prove exact CPU/FPGA input parity. Preserve their
sealed evidence. V11 diagnostic1CPU request stopped before any scored commit or
board access and was sealed25files at build/v2/v8-json-retention-v11.
V11-r2 compensates with one file-framing LF, unchanged logical prompt; validates
all actual CLI IDs from verbose stderr against frozen IDs, then FPGA IDs.
Do not use the old CPU helper alone for future exact input-parity claims.

---

## Previous v10 CPU retention status context (preserved)

Status-copy retention v10-r3 fresh CPU evaluation COMPLETE. Scripts/module:
run_v8_json_retention_v10.py, report_v8_json_retention_v10.py,
src/sysone/v2/v8_json_retention_v10.py. Docs:
docs/research/2026-10-21-v8-json-retention-v10.md. Preserve frozen source/inputs
and sealed results. Parser/scorer/reducer unchanged; no missing-field/default/status repair.

36 fresh development tasks cross all A/B status pairs and both target entities.
Original baseline29/36; first candidate0/36 because user query omitted entity
requirement, second35/36 with one missing-to-ok error. Both failed strict36/36
gate and remain separately sealed at build/v2/v8-json-retention-v10/development
and v8-json-retention-v10-r2/development. Final r3 generic instruction preserves
stored status and names State.<entity>.status/count explicitly; passed36/36.
Development reused its own cases for revisions; no evaluation tuning.54 tests
passed. Baseline outputs reused for analysis only, not counted as new calls.

Final sources frozen unchanged between r3 development and fresh evaluation at
build/v2/v8-json-retention-v10-r3/{development,evaluation}. New fixed seeds,
entity orientations and error-state long-gap case;224 primary+12 repeats,
16/32/64-step mixed/long-gap sequences, all129 input tokens. No state/query
overlap with prior experiments or development. Raw v9/v10 scores are not paired.
Fresh evaluation224/224 correct and parsed, distinct inputs179/179. All six
chains error-free, both64-step chains64/64. Status ok87/87,missing75/75,error62/62.
All12 explicit repeats matched; all57 repeated-input groups text-identical.
Independent report replayed224 observations and verified matching selected
development/evaluation sources and paired original-development inputs.
Total380 CPU calls:144 development across three attempts+236 evaluation.
Seals: initialdev235 files,r2dev127,r3dev127,r3eval728. Separate sealed report
build/v2/v8-json-retention-v10-report (analysis, CSV, README, reporting source).
54 focused tests passed. Selected prompt costs27 extra input tokens versusv9.
Use as CPU retention baseline for this two-entity workload; no universal, FPGA
or closed-loop reliability claim. Do not tune against completed evaluation.
Closed-loop excluded, no board session or BOARD_STATUS write, sealed v8 baseline
unchanged, FULL SWEEP STOPPED. Do not tune against final evaluation responses.

---

## Previous v9 retention expansion context (preserved)

Expanded CPU JSON retention v9 COMPLETE as a separate bounded evaluation.
Evidence build/v2/v8-json-retention-v9. Six fresh mixed/long-gap sequences at
16/32/64 steps:224 primary+12 exact repeats=236 requests. Frozen v6-r2 retention
prompt/parser unchanged, JSON-only, context256/output48, all inputs102 tokens.
Trusted simulated observations update state; replies read-only. Long-gap queries
reach62 steps since A's last observation. There are179 distinct primary inputs;
deduplicated metrics separate repeated snapshots. No prior v6/v7 prompt overlap.
49 focused tests passed. Primary210/224 correct (93.75%),216/224 parsed;
distinct inputs167/179 correct. Mixed16/32/64:15/16,29/32,58/64; long-gap:
16/16,31/32,61/64. All216 parsed records have correct entity/count. Six status
errors returnedok; eight complete EOS JSON replies used invalid status latest
(not punctuation/truncation failures); no semantic repair. Longest correct run30,
neither64-step sequence all-correct. All57 age8+ queries correct but workload
confounded; not a causal age claim. Input remains102tokens throughout.
12 explicit repeats matched;57 repeated-input groups all text-identical.
Raw725-file seal verified; report separate at build/v2/v8-json-retention-v9-report
with analysis, CSV, README and reporting source, independently replaying224
primary observations. Prior269 v8 +432 v6 +279 v7 +88 v7-r2 files unchanged.
Do not tune against this completed evaluation set. Status fidelity is the next
development issue; no reliable64-step or cross-model claim established.
Scripts: run_v8_json_retention_v9.py (--run resumes only
an exact frozen prefix) and report_v8_json_retention_v9.py (completed sealed runs).
Docs docs/research/2026-10-21-v8-json-retention-v9.md. Closed-loop excluded,
no board use/BOARD_STATUS update, sealed v8 unchanged, FULL SWEEP STOPPED.

---

## Previous v7 closed-loop diagnosis context (preserved)

JSON closed-loop diagnosis / development fixes implemented separately in
src/sysone/v2/v8_json_diagnostics_v7.py and
scripts/v2/run_v8_json_diagnostics_v7.py. Details:
docs/research/2026-10-21-v8-json-closed-loop-diagnostics-v7.md.
V6 audit found no independent-oracle or reducer mismatches. JSON16 requests:
4 correct,8 parsed new local errors (4 copies,1 add,3 conditionals),3 output-budget
extraction failures,1 inherited-only error. Drift present before13 but changed
the target answer on7; new errors and drift overlap. No arithmetic gold repair.

Fresh v7 development-only paired run completed88 CPU inferences. Generic
single-target prompt clarification, explicit copy/conditional instructions;
parser unchanged. Parsing versus commit acceptance separated. Admission checks
only target and requested missing/error count preservation; raw errors remain
errors and wrong arithmetic still commits. Original/clarified: dependent global
2/16 versus2/16, local3/16 versus8/16; ideal-state controls3/16 versus9/16.
Closed-loop reliability remains inadequate despite better local handling.
Evidence build/v2/v8-json-diagnostics-v7, sealed with frozen original sources.

Review found one new primitive copy probe had equal target/source counts, a
non-discriminating copying test. V7-r2 fixes source/target initialization and adds
a regression against accidental no-op copying. Separate corrected primitive-only
development run uses fresh source counts/deltas; no chain retuning or heldout
run. Corrected primitive24 calls: original1/12, clarified10/12; clarified
add/subtract/copy3/3 each, conditional1/3. Not a general arithmetic guarantee.
Both runs complete and sealed (v7:279 files, r2:88); final hashes clean. Each
verified432 v6-r2 plus269 v8 files unchanged. Total112 CPU inferences.
Evidence build/v2/v8-json-diagnostics-v7-r2. Current source VERSION is r2;
use frozen snapshots to reproduce v7. Focused regression suite66 tests passed.
Keep retention separate from reasoning; qualify any expanded closed-loop claims
on fresh heldout data after freezing prompt/admission. No board access or
BOARD_STATUS updates, sealed v8 baseline unchanged, FULL SWEEP STOPPED.

---

## Previous v6 state pilot context (preserved)

v8-state-pilot-v6-r2 CPU pilot COMPLETE. Separate evidence at
build/v2/v8-state-pilot-v6-r2; methods and results at
docs/research/2026-10-21-v8-state-pilot-v6.md. No board access or board-status
updates. Sealed v8 baseline unchanged; FULL SWEEP remains STOPPED. Live board
identity belongs exclusively to BOARD_STATUS.json, not these historical notes.

Fresh development/heldout cases compare H=full raw history, J=readable JSON state,
C=named compact state. Retention uses actual simulated tool observations to
update host state; model replies never alter that world. Closed-loop commits
actual accepted model proposals and preserves state after rejection; no gold
repair. One eight-step sequence per mode/split, greedy Qwen3-0.6B Q8_0 CPU,
context256/output reserve48. Prompts contain no demonstrations or prompt search.

136 inferences (72 dependent +64 snapshot controls), four capacity stops, 82
focused tests passed. Heldout retention H2/2 then capacity before3, J7/8, C3/8;
heldout closed-loop H1/2 then capacity before3, J2/8, C0/8. Development retention
H2/2 then capacity, J7/8, C4/8; closed-loop H2/2 then capacity, J2/8, C1/8.
Both state arms fit all8, but compact only saved about9 retention input tokens
versus JSON. Prefer readable JSON for the next baseline; compact stays an
ablation. Bounded context is demonstrated here, reliable closed-loop reasoning
is not. Do not equate censored H2/2 with eight-step reliability.

64 frozen control prompts verified, 38 exact control-input matches (all32
retention state-arm requests), 40 repeated identical prompt checks with zero
raw-text mismatches. Sources verified before/after; prior v8/v2/v3/v4/v5 seals
and preserved parser-development seal verified unchanged. Final results sealed.

Preliminary v6 parser run stopped after51 durable development records, zero
heldout responses. Preserved separately at build/v2/v8-state-pilot-v6 with
167-file development seal. R2 adds only generic singleton-object-list unwrap
and name-to-entity alias before heldout; no missing-field/value repair. Prompts
and case values unchanged. Final heldout was run once; do not tune against it.

---

## Previous v5 pilot context (preserved)

v8-chain-pilot-v5 COMPLETE. User shifted focus from exact typed-format tuning to
dependent-chain comparison; compact representation is frozen and treated as
model-specific evidence, not universal compression. V8 unchanged; FULL SWEEP
STOPPED. RAM-only SSH session closed, baseline inactive/dead, no benchmark jobs.

Frozen generic prompt, no demonstrations/prompt search or output repair. Two
eight-step chains (retrieval/status and arithmetic), H=full raw history versus
C=observed named compact state. Fixed tolerant parser accepts arrays, unambiguous
objects/aliases, fences and declared EOS text records; semantic values are never
corrected. Wrong proposals propagate; rejected output keeps prior state. Separate
16 oracle-input one-step controls NEVER update rolling state. First failure,
local versus global correctness, recovery and capacity censoring all recorded.

Each backend36 NN requests +2 capacity stops. Both accepted35/36; legacy strict
array conformance0/36 (objects are allowed by the new prompt). Identical dependent
outcomes: simple H1/2 correct then capacity before3, C4/8 correct with first
failure2; arithmetic H2/2 then capacity before3, C2/8 with first failure2. Inputs
C113–132 tokens; Hthird224/234 exceeds208 input allowance (context256 minus48
output reserve). Capacity benefit is NOT a semantic reliability/retention result.
Controls CPU10/16, FPGA9/16; controls omit acknowledgement and are diagnostic,
not an identical-prompt causal ablation. No per-model compaction tuning planned.

All38 input-ID sequences matched;34/35 valid parsed outputs matched, plus1 both
unparseable. Four exact repeated FPGA input checks passed. Fixtures, original
MVP exact IDs and deployment/boot identity passed. All269 v8 sealed files plus
487 v2,1233 v3,1156 v4 evidence files verified. 62 focused tests passed.
Evidence build/v2/v8-chain-pilot-v5/{pilot-summary.json,pilot-seal.json,
comparisons.csv,semantic-failures.json,cpu/,fpga/,snapshot/,board/}. Remote
/var/lib/sysone/benchmarks/v8-chain-pilot-v5. Methods/interpretation:
docs/research/2026-10-21-v8-chain-pilot-v5.md. Do not replay queue jobs, restart
the full sweep, or recycle these pilot cases for prompt tuning without new scope.

---

## Previous v4 qualification context (preserved)

Separate v8-protocol-v4 qualification COMPLETE. V8 UNCHANGED and FULL SWEEP
STOPPED. Authenticated session closed; final audit unit inactive/dead and no
benchmark processes. Do not replay queues or reuse qualification for tuning.

Focus: compact state/string-status JSON only. Development tested no examples,
format-only examples, prefilled metadata, paired operation examples and named
compact state; pilots preserved separately. Selected two-named: A:count,status;
B:count,status with two fixed examples per operation covering both targets and
opposite conditional branches. Full record is freely generated; no header
prefill, host arithmetic, output repair or grammar constraint in selected arm.
Paired development21/28 correct versus unchanged v3 prompt16/28 on same new
cases. Conditional development0/8 to4/8; some copy/error regressions retained.

Fresh qualification28 unique cases plus4 repeats per backend. Both CPU and
FPGA28/28 format,19/28 correct. Per-op set4/4,add4/4,copy2/4,conditional4/8,
missing2/4,error3/4. Both semantic gates FAILED. This partly addresses the
failures; conditional arithmetic, source/count retrieval and example copying
remain unreliable. New cases cross entities/branches, include50/51 and prior
non-ok statuses; raw scores are not directly comparable with old v3 cases.

All32 paired input IDs matched;4 FPGA repeat checks exact generated IDs. Causal
fixtures, original MVP exact-token generation and deployment identities passed.
All269 v8 sealed files,487 v2 and1233 v3 evidence files verified unchanged.
42 focused tests passed. New separate evidence: build/v2/v8-protocol-v4/
{qualification-summary.json,qualification-seal.json,semantic-failures.json,
development-comparison.json,cpu/,cpu-pilot1/,cpu-pilot2/,cpu-pilot3/,
cpu-qualification/,fpga/,board/}. Remote /var/lib/sysone/benchmarks/v8-protocol-v4.
Details: docs/research/2026-10-21-v8-protocol-v4-qualification.md.

---

## Previous v3 qualification context (preserved)

Separate v8-protocol-v3 qualification COMPLETE. Deployed v8 UNCHANGED; full
sweep remains STOPPED by user instruction. No benchmark processes remain and
the RAM-only authenticated session is closed. Do not replay queue jobs.

Development compared three compact state/output candidates on 216 requests;
an earlier 98-response development pilot is preserved separately. Frozen winner:
tuple state [Acount,Astatus,Bcount,Bstatus], numeric JSON output alternative,
operation-specific matching demonstrations and explicit event-status rules.
Fresh qualification: CPU72/72 format,47/72 correct; FPGA69/72 format,45/72 correct.
Both overall gates FAILED. Compact state/string status scored CPU9/12 and
FPGA10/12 correct, but compact/numeric status scored only4/12 and3/12. Conditional
accuracy0/12 on both. Do not reuse qualification cases for prompt tuning.

All72 paired input IDs matched;24 duplicate H/J inputs had zero FPGA output-ID
mismatches. Causal fixtures passed, deployment identities and boot matched;
original MVP control reproduced previous62 prompt/16 output IDs with no tool
execution. All269 sealed v8 artifacts and487 sealed v2 evidence files verified.
Compact state11 versus23 tokens; complete prompt savings6.64% on these initial
single-step cases. These are not dependent-chain or sustainable-depth results.
33 focused tests passed. Evidence: build/v2/v8-protocol-v3/qualification-summary.json,
qualification-seal.json,semantic-failures.json,state-size-analysis.json,
cpu/ (development/selection),cpu-qualification/,fpga/,board/. Remote private
snapshot /var/lib/sysone/benchmarks/v8-protocol-v3. Details:
docs/research/2026-10-21-v8-protocol-v3-qualification.md.

---

## Previous qualification context (preserved)

The deployed under-ten-second v8 system below is UNCHANGED. All 269 sealed v8
artifacts verified. No model/bitstream/launcher/overlay changes or Linux reboot.

v8-baseline-v1 sweep STOPPED after 44 development requests for protocol diagnosis;
no historical/fixed/application/held-out phases reached. Traces preserved under
build/v2/v8-diagnosis-v1. Do not restart that campaign or replay old queue jobs.

Separate v8-protocol-v2 qualification COMPLETE: CPU 69/72 format,44/72 correct;
FPGA65/72 format,40/72 correct. Overall admission gates FAILED; FULL SWEEP NOT
RESTARTED. New JSON prompts + one development-selected demonstration and EOS-aware
enum framing tested. 22 focused tests passed. Gates were frozen before fresh
qualification; no vocabulary mask, grammar constraints or output repair.

All72 paired input token sequences matched. 24 repeated-input H/J checks had
zero FPGA output-ID mismatches. Pre/post causal fixtures passed and deployment
identities matched. Original MVP command generation reproduced the exact sealed
62 prompt/16 output IDs; no real tool executed in qualification. Board remains
the same Linux boot, v8 FPGA and 639446688-byte model residency.

Evidence: build/v2/v8-protocol-v2/{README.md,qualification-summary.json,
qualification-seal.json,comparisons.csv,cpu/,fpga/,mvp-control.json,board/}.
Docs: docs/research/2026-10-21-v8-protocol-v2-qualification.md. Remote snapshot:
/var/lib/sysone/benchmarks/v8-protocol-v2. Original deployment remains
/var/lib/sysone/qwen-fpga-decoder-v8-startup-v2. No long benchmark is running.
Use a NEW benchmark version for future prompt/protocol changes; preserve v1/v2
evidence and the sealed deployment. Do not store credentials in files/arguments.

---

# UNDER-10-SECOND COLD TOOL CALL DEPLOYED — 2026-10-21

## New-chat start here (latest; overrides older active-build notes below)

The user's requested MVP milestone is achieved for one focused command.
Cold-call timer: **9.227829901 s**, versus sealed v7 18.928106882 s
(2.0512x faster, 51.25% less time).
Full SSH job: **10.063 s**; distinguish that transport/process time from the
consistent cold-call timer. This is not a worst-case or general capability claim.
No benchmark sweeps were run. Two v8 commands ran: the first was correct at
12.045177907 s and failed promotion; after concrete startup changes, the final
9.227829901 s command passed and was promoted. Do not rerun for more samples.

LIVE BOARD: ubuntu@192.168.0.239, same Linux boot
`e9728928-307d-485b-b40b-63fa29d9296d`. Linux never rebooted. Active FPGA app
`sysone-qwen-decoder-wide-int8`, decoder clock 124999999 Hz, memory clock
249999998 Hz. Owned DMA residency unchanged: 639446688 bytes, 39x16MiB segments,
pinned Qwen3-0.6B Q8_0 model SHA256
`9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`.
All model arithmetic runs on FPGA; ARM performs tokenization, transfers, hashing,
JSON validation and the generated Linux file read only. No CPU NN/FP32 correction,
output replay or vocabulary mask. ARM NN service remains stopped; R5 absent.

PROMOTED `/usr/local/bin/sysone-qwen-fpga` invokes
`/var/lib/sysone/qwen-fpga-decoder-v8-startup-v2/scripts/v2/run_qwen_fpga_command_v7.py`
with that package. It generated and executed
`read_linux_file('/proc/sys/kernel/random/boot_id')`, returning the current boot.
Exact v7 prompt and generated IDs matched. 62 prompt/16 output tokens, zero prefix
reuse, 8 prefill groups, 644 layer weight passes, full 151936-row vocabulary.
Cold timing includes all-byte resident SHA256 and tokenizer/setup; boot-time
model loading is separate, same definition as v7. Prefill 3.054299173 s, decode
3.494615595 s, startup 2.673104527 s, ordered SHA 1.712556345 s, vocabulary .749926805 s.

FPGA v8: B8 prefill, 256-bit weights, 125MHz core/250MHz memory via 128-bit HP0
clock/width converter; one Q8 block/cycle, paired query-head SIMD and causal
K/V head reuse per batch; quantized-input reuse Q/K/V and gate/up. Weight bytes
are unchanged, but MATRIX INPUT PRECISION CHANGED to symmetric INT8 per32,
INT32 dots and FP32 scaling/partials. Norm/RoPE/attention/KV/residuals remain FP32.
Do not claim original FP32 numerical equivalence. Independent reference Csim and
16-case board causal fixture passed (worst board error 7.152557373e-7).
Routed setup .468ns/hold .010ns positive; clock-converter bus skew min2.462ns;
zero unconstrained internal endpoints. Methodology's vendor CDC warning is
retained in the report; no claim of zero methodology warnings.

STARTUP REVISION: `src/sysone/v2/qwen_tokenizer_v1.py` loads hashed compiled BPE
merge/piece tables (official source preserved), uses native pinned tokenizers
NFC/Split/ByteLevel, and performs ordered ranked merges in Python. Avoids full
native BPE construction holding the GIL. Eight focused exact-ID cases plus prior
prompt/output bytes passed. `compile_qwen_tokenizer_v1.py` produces the tables.
Runtime v7 now stages weight reads through a four-buffer ring, refilling after
ordered SHA consumption; maps outlive native readers and all bytes verify BEFORE
any NN command. No validation was dropped from the cold timer.

DEPLOYMENT RECOVERY: initial `08-deploy-wide-int8` failed before NN because an
external package/service restart had left dfx-mgr bookkeeping stale while the old
baseline overlay remained applied. Verified idle/no MMIO clients, stopped only
dfx-mgr, removed the exact orphan configfs overlay, restarted dfx-mgr, reloaded
baseline, then deployed candidate successfully. Original failure/recovery logs
preserved. No model buffers or Linux boot were lost. Hardware fixture was reused
for startup-only revision after asserting identical bitstream and idle state.

EVIDENCE: `build/v2/qwen-fpga-decoder-v8/README.md`, deployment-proof.json,
real-command-result.json, first-command-result.json, hardware-block-smoke.json,
seal.json (269 files), board/results and queues. Prior v2-v7 release seals ALL
verified unchanged. `deployment-first` and `qwen-fpga-deployment-first.tar` retain
initial v8 package; `deployment` and `qwen-fpga-deployment.tar` hold promoted startup
revision. New doc: docs/research/2026-10-21-under10-qwen06b-fpga-tool-command.md.
Hardware source/IP/actual-import hashes checked. Do not edit sealed files;
use a new version for future changes. No commit or push made.

SSH session41420 is CLOSED (99-close-session passed). Build53500 and completion
95318 finished. No background board jobs or running builds remain. Credentials
must never enter files or shell arguments; use RAM-only getpass in future windows.
Board access/live FPGA manager changes were authorized by the user; preserve Linux.
No JTAG/reboot/paid compute. FPGA/model residency lasts for this Linux boot only;
files/launcher persist, no automatic model autostart was enabled.

LARGER-MODEL TRANSFER: profile-driven shapes and generic matrix core retained;
capacity6144 with columns2048/6144/1056 passed Csim. No larger model deployed.
Larger models still need their own routed fit, precision/quality validation and
memory sizing; current DMA table remains 64x16MiB (1GiB), current CMA800MiB and
scratch256MiB unchanged. Do not promise drop-in larger-model fit or latency.

---

## Earlier handoff history (superseded where it conflicts with the section above)

# UNDER-10s CANDIDATE PHYSICAL BUILD ACTIVE - 2026-10-21

## New-chat start here (ACTIVE overrides older sections)

User: getcoldtool<10s, Linuxlive,0.6BFPGA,no sweeps,largermodeltransfer.
BaselineSEALEDv7 18.928106882s. BoardSAMEboote9728928-307d-485b-b40b-63fa29d9296d,
ACTIVEv7buffered99999999Hz, same639446688B/39DMAresident. NoLinuxreboot/modelreload/
PLswitchyetthisturn. SSH41420OPEN(memoryonlypassword), runner_v7workv8/board,
only00inventoryPASSEDcurrently. Credentials are supplied through RAM-only getpass; never put them in files.

FINALv8HARDWARE hls/qwen_decoder_v8 frozenhardware-source-sha256.json. PinnedQ8
weightbytesunchanged; NEWblock32symmetricINT8activationdotproducts INT32sum+FP32
scales/partials; FP32norm/RoPE/attention/KV/residuals. Precisionchangeannounced.
B8prefillvs4, modelAXI256vs128,scratch128sameCSRABI. core125MHz/memoryHP0 250MHz
(SmartconnectNUM_CLKS2with256to128converter); Tclvalidatedandphysicalbuildrunning.
FinalexplicitpairedquerySIMD2, perbatchK/Vheadreusecausalbounds, QKVandgate/up
quantized-inputreuse; shareddeepURAMbanks(no tokenpartitionmux). DotcoreII1.
HLS82775LUT/116187FF/227BRAM18K/334DSP/40URAM. Actualroutedfitpending.
IndependentorderedNumPyINT8reference8/full8and1+7CsimPASS max7.15256e-7,
finalnorm3.8147e-6/top32argmax4/scatterboundary; genericcap6144cols2048/6144/1056PASS.
Threshold2e-5, no relaxednumericgate. FINAL Csim+csynth+export SAMEprocess31973done.
103RTLfiles strictsyn/IP/ZIP AND actualVivadoimports auditedPASS by
scripts/v2/check_qwen_hls_export_v2.py. IPzipSHA96adb9c1ebc7374457756ccacaea2b4ad663aca8142624cb76915a29a9578bfc.
Predecessorbuilds/failurelogs preserved; no oldv2-v7sealedfileedited.

CURRENT physicalVivadotoolsession53500, logbuild/v2/qwen-fpga-decoder-v8/
vivado-console.log; OOCcoresynthstartedhost00:44, currentlytimingoptimization.
Tclhls/qwen_decoder_v8/create_kr260.tcl includesAggressiveFanoutOpt andpostroute
physopt. Clock8ns/4ns; mustqualifyBOTHsetup+holdbeforedelivery. No clockbench.

AUTO COMPLETION toolsession95318 runs scripts/v2/complete_qwen_fpga_v8.py,
waitingQWEN_FPGA_ROUTED_READY. Thenstrictauditagain,package_v7, autoqueues05baseline/
06upload-qualified-wide-int8/07extract-qualified-wide-int8/08deploy-wide-int8/
09causal-hardware-smoke/10ONEcold-real-command/11promote-faster-deployment/
12collect-deployment-evidence. DO NOT queuesecondcommand. Runnerstopsanyfailure.
Promotionfinish_v7 requiresREALcorrectcall, sameprompt/currentboot/pinnedweights,
fullvocab, elapsed<10.0, noCPU/hostNN/correction. GeneratedIDsMAYdiffer dueINT8act,
exactequivalenceNOTrequiredorclaimed. NewAPPsysone-qwen-decoder-wide-int8,
compatiblexlnx,qwen-decoder-wide-int8-1.0. Runtimechecks125MHzPL0+250MHzPL1/B8/
32bytealignment; DMAtable1GiBlimitunchanged. KeepLinuxrunning/noreboot/JTAG.

HostsoftwareNEW runtime_v7 andscripts_v7 (oldv6sealeduntouched). Fourboundednative
copyworkersfullorderedSHA EACHcoldcallINSIDEtimer; Rusttokenizers0.23.2 byte-level
BPEonly noNN replacingllamahelper. Exactprior62promptIDs andoldoutputbytesmatched.
Officialtokenizerrevisionc1899de289a04d12100db370d81485cdf75e47ca, SHAaeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4;
ARMabi3wheelofficialPyPI SHAchecked, vendoredintoPACKAGE/tokenizer-runtime;
provenancefiles token*-correctness/wheel-source.json. No globalsystempipinstall.
Newpackagechecksallfilehashes, compiledmodelprofileB8/ACTINT8, bit/XSA/timing/ABI.
Modelresidency+currentLinuxbootretained; oldlauncheronlypromotesifUNDER10tested.

After12success inspectproof/result, queue99close, awaitSSHclose, then run
scripts/v2/collect_qwen_fpga_v8.py. It requires<10andrealcommand, allv2-v7seals
unchanged, writes134+fileproofseal andREADME/researchdoc. It matchesbaselineLinuxLF
proofSHAtonormalizedWindowsCRLFcopy whileverifyingoldrawsealedbytesunchanged.
Thenwritefinalhandofftop. IfphysicalorNNjobfails, repaircause; don'tunloadinflight
hardwareontimeout. Don'tfinalbeforeunder10actualcommandunlesshardexternalblocker.
Currentnewv8modelsourcepythonref scripts/v2/prepare_qwen_fpga_v3.py independently
quantizesints; initialreferenceorderingfixandunsupportedram_t2p/lutramdirective
repairsweredoneBEFOREhardware. EarlierhandoffactiveplansbelowareSTALE.

---

# UNDER-10s FPGA WORK ACTIVE - 2026-10-21

## New-chat start here (active)

User requires coldtool<10s, Linuxlive,0.6BFPGA,no sweeps, transferablecore.
BaselineSEALEDv7 18.928106882s, allv2-v7seals MUSTremainunchanged.
Board SAMEboot e9728928-307d-485b-b40b-63fa29d9296d, v7bufferedoperating,
639446688B/39DMAsegmentsresident, PL0/PL1both99999999Hz. No restore/rebootneeded.
SSHsession41420 OPEN RAMcredentials, runnerqwen_fpga_board_window_ssh_v7.py,
workbuild/v2/qwen-fpga-decoder-v8/board. Only00inventoryqueued/PASS. No PLchange yet.

NEWunsealedv8 hardware hls/qwen_decoder_v8: pinnedQ8weightsUNCHANGED, newdynamic
INT8activationsper32block (roundtiesaway,clamp[-127,127]), int8xint8accum int32,
FP32blockscales/partials,norm/RoPE/attention/KV. PrecisionDIFFfromv7FP32dots,
explicitlyannouncedtous er. WholeNNstillFPGA/nohostcorrection. B8vs4,256bitmodelbus
vs128,scratch128ABIunchanged; modelrowalignment32(runtimehidden%512). NativeFP32
dotinputbankingreduced4cyclicbecausequantizerreadsserial; quantizedinputs32banks
lutramram_s2p. Initialinvalidram_t2p+lutram directive correctedbeforehardware.
Real8tokenFULL8 and1+7 causal Csim independentNumPyINT8golden PASS max7.15256e-7,
finalnorm3.8147e-6/top32argmax4, genericcapacity6144cols2048/6144/1056PASS.
IndependentreferencewasfixedtosameFP32RMS/attentionORDER beforequantization;
originalNumPyBLAS orderproducedquantthresholdjumps. Failurelogs preserved.

HLSactive1480 (firstusableintegerbuild), freshhls-release csynth+export SAMEprocess;
logbuild/v2/qwen-fpga-decoder-v8/hls-release-console.log. Clock8ns/uncert1.0=125MHz.
create_kr260.tclconfig125MHzcorePL0,250MHzHP0/SmartconnectmemoryPL1,NUM_CLKS2,
256to128widthconverter. Linuxoverlayclock0=125M,clock1=250M; ONLYafterroutepass.
IMPORTANT: plannedFINAL hardwarechange NOTYETINSTALLED: explicit2-headSIMD
attention source saved build/v2/qwen-fpga-decoder-v8/attention-pair-source.txt;
replaceattentionfunction AFTERcurrentHLSexits, addquantized-inputreuse op1/2/5
(QKV+gate/up), rerunCsimthenfreshcsynth+exportsameprocess. Currentbuildouterquery
headloopunrollfactor2islessclear, finalexplicitSIMDneededfortargetconfidence.
No physicalbuildyet. Freezehardware-sourcehashes onlyafterfinalsourceinstalled.

Newruntime/scripts v7 (newfil es): runtime_v7 B8/32bytealignment/125MHzPL0 +250MHz
PL1guards,4nativecopyworkersfullSHA(eachcommand), noARMNN. runcommand_v7 uses
pinnedRusttokenizers0.23.2 insteadllamahelper; byte-levelrawdecoderpreservesUTF8
pieces. OfficialQwen/Qwen3-0.6B tokenizer revisionc1899de289a04d12100db370d81485cdf75e47ca,
SHAaeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4. Offlinechecks
EXACT62promptIDs andoldgeneratedbytes match. ARMcp310abi3manylinuxaarch64wheel
inbuild/deps, downloadSHAverifiedofficialPyPI, provenancejson; packagedvendored,
no globalpipinstall. Hostvenvhasnopip, usedurllibPyPIJSON/downloadSHAverification.

package/deploy/smoke/finish_qwen_fpga_v7.py prepared NEEDREVIEWbeforeuse. Package
B8,profileactivationquantized,DTclock125/250; newAPPsysone-qwen-decoder-wide-int8,
compatiblexlnx,qwen-decoder-wide-int8-1.0. deploybaselinebuffered; finishbaselinev7,
requires<10beforelauncherpromotion, sameprompt/correctcall/currentboot/fullvocab,
notidenticalgeneratedIDsbecauseprecisionchanged. No autoqueue/completionrunnerforv8
YET. check_qwen_hls_export_v2.py auditsinteger_dotwrapper(syn/IP/ZIP/actualVivado).
smoke8/full8/1+7 threshold2e-5 vsindependentINT8golden (tightmatchesobservedCsim).
Need newcollect/sealhelpers ratherthanmutatingsealedv7 helpers. Preserveallprior
artifacts. No benchmarksweeps or modelsizeincrease. Do not restoreMiniLM.
User askedUNDER10, continueuntilrealtoolcommandtested; don'tclaimachievedyet.

---

# 18.93-SECOND QWEN0.6B FPGA TOOL COMMAND DEPLOYED - 2026-10-20

## New-chat start here (latest)

User: optimize toward10sMVP, Linuxlive,0.6BFPGA, skipbenchmarksweeps, transfercore
tolargermodel. COMPLETE increment: ONE cold-prefill realcommand **18.928106882s**,
fullSSHjob19.594s, historicalv6baseline27.430389467s:1.449188x/30.99585%lesstime.
10-secondtarget NOTyetmet. Same62prompt/16outputIDs, sameQ8_0weights, FP32sumorder,
full151936vocab, no prefixreuse, same77inputs/2156semanticlayers/868weightpasses,
1221commands/2430976vocabrows. Realread_linux_file('/proc/sys/kernel/random/boot_id')
executedcorrectly. AllNNmathFPGA; noARM/hostNN, noargumentrepair/replay/vocabnarrowing.

Timings: prefill8.122159470s (v6:11.8253), decode7.417083695s (v6:8.4290),
startupWALL3.067637962s; SHA2.863593999995s andvocab2.375105598s OVERLAPPED,
notadditive. Everyresidentweightbyte verifiedINSIDEcoldtimer. No warmrepeat/sweep.
Currentcolddefinition=modelalreadyresident, freshfullprefill; bootmodelloadnotincluded,
sameasv6. FullSSHjobalso19.594s (containsprocess/networkoverhead).

ACTIVE APPsysone-qwen-decoder-buffered,compatiblexlnx,qwen-decoder-buffered-1.0,
clock99999999Hz, decoderidleaftercommand, FPGAoperating. Launcher
/usr/local/bin/sysone-qwen-fpga nowpoints /var/lib/sysone/qwen-fpga-decoder-v7/
scripts/v2/run_qwen_fpga_command_v6.py; nextoutpackage/last-command-result.json.
Entry: sudo sysone-qwen-fpga --query "Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'."
--no-prefix-cache acceptedcompatibility; profilealwayscold. Previouslauncherbytes
savedpackage/sysone-qwen-fpga.previous; previousapps/packages/seals retained.

IMPORTANT BOOT: boardhadALREADYrebooted beforethissession! ArrivedstarterFPGA,
noDMA. CurrentLinuxboot **e9728928-307d-485b-b40b-63fa29d9296d**.
RestoredexistingDMAmodule/samepinned639446688Bweights39segments/fullsource+resident
SHA, thenqualifiedv6appbeforecandidate. NoLinuxrebootbythissession. Historicalv6
proofboot6c80...differs, so comparisonisSINGLEhistoricalcommands acrossboots,
notcontrolledsamebootbenchmark. RecoveryevidenceNEW /var/lib/sysone/
qwen-fpga-decoder-v7-boot-recovery andlocalboot-recovery.json. ModelresidencyandPL
CURRENTBOOTonly; files/launcherpersist; noautostart. ARMmodelstopped/disabled,
R5unloaded. Existing800MiBCMA/scratch256MiBunchanged. NoJTAG/reboot/paidcompute/
commit/push. SSH32187CLOSED99queue; credentialsRAMonly/no secretsaved.

CODE: hls/qwen_decoder_v7/{qwen_decoder.cpp,matrix_q8.hpp,model_profile.hpp}.
GammaH/H/HD/HD vectorsburstloadedONCEperdecoderbatch intoFPGA RAM, splittingDMA
16MiBboundaries. RoPE512Byterowoncepertoken reusedacrossallQ/Kheads. Proven
inplaceelement-disjoint dependencies: normoutputII1vs7, RoPEII2vs9. Sumorder
unchanged. NormsquaresremainsserialII3. Q8matrixstreamcoreunchangedfromv6,
profilederivedbuffers transfer; no larger-model fit/deployment claim.
Runtime src/sysone/v2/qwen_fpga_runtime_v6.py: fullSHAuses2nativecopyworkers,
4reusable4MiBstagingbuffers, orderedSHA/bytecoverageexact, allreadersjoinedbefore
unmapevenexception; noNNmathonCPU. Newwide-tensoralignmentguard. Commandpoll50us
vs500us,120shardwaretimeoutunchanged. run_qwen_fpga_command_v6.py overlapsvocab
helperstartup andmodelverification underglobalinference lock INSIDEcoldtimer.

QUALIFICATION: finalCsimreal4lanes/full4/partial1+3/causal/firstlayer/finalnorm/
argmax13/scatterboundary PASS, worst5.7220458984375e-6. Same8boardfixturecases
PASSwithsameerrors. Matrixgeneric6144capacity2048/6144/1056Csimretained. Onecold
fullrealcommandexactIDsmatchedv6. Routed100MHzsetup+0.852ns/hold+0.010ns; bit/XSA
match. HLS93860LUT/82081FF/218BRAM18K/507DSP/24URAM. ActualOOC95553LUT/77534FF/
95BRAMtiles/507DSP/24URAM. 88RTLfiles strictsyn/IP/ZIP/actualVivadoimportauditPASS.
Initialbuffer-onlyHLSrevealedfalsealiasII7/9, preservedhls-release.buffer-only;
FINALfreshhls-release csim+csynth+exportSAMEprocess. Use release.tcl forrebuild.

Evidence build/v2/qwen-fpga-decoder-v7/{README.md,deployment-proof.json,
real-command-result.json,hardware-block-smoke.json,seal.json,traffic-bound.json,
hls-performance.json,hardware-source-sha256.json,ip-rtl-consistency.json}.
Doc docs/research/2026-10-20-buffered-qwen-decoder-design.md.
DeploymentpackageSHA36c36b49befa4c58fa609fc17ccb9afe0f4d08d05549b371e40c7b158322fe98.
NEWSEAL134files; oldv2(100)/v3(80)/v4(75)/v5(41)/v6(118) allverifiedUNCHANGED.
Boardjobs00historicalbootassertfailedBEFOREMMIO;01inventory02allocate03weights
04v6restore succeeded;04validatefixedonlynewlineinNEWrecoveryJSONwithbackup;
05refresh06upload07extract08livePLdeploy09fixture10ONEcoldcommand11promote12collect
99close ALLPASS. Staleattention.json refersONLYresolved00. No pendinglogin/build/
deploymentjobs. Physical63768, HLS54823, completion32311 finishedsuccessfully.
collect_qwen_fpga_v7.py normalized ONLYbaselineWindowsCRLFforremoteLFproofSHA
comparison; oldoriginalsealedbytesunchanged; allpackagefilesbyteverified.

NEXTTARGET: 10s requiresmoreweightbandwidth orfewerweightpasses. StaticUNCHANGED
commandmatrixtraffic17,150,640,128B / current128bit100MHz1.6GB/s = **10.71915008s**
idealminimumMATRIXONLY, excludingattention/norm/tokenizer/hash/polling. Thisis
analysisNOTbenchmark. Moreminorstartupchangescannotaloneget10. Nextsubstantial
reusablecorestep:wider/fasterweightpath + matchingmatrixthroughput ormorebatchreuse.
Keep0.6BFPGA/Linuxlive, no sweeps. Largerprofile remainsQ8/head128; DMA64x16MiB1GiB
limitNOTextended. Largeractualmodelneedsownquant/memory/fit/numericproof. Do not
restoreMiniLM. Do not reruntimingjusttoverifyagain. Activeworkhistorybelow.

---

# FPGA 10-SECOND TARGET OPTIMIZATION IN PROGRESS - 2026-10-20

## New-chat start here (active work)

User: toward10s MVP, Linuxlive, Qwen0.6B FPGA, no sweeps, transferablecore.
Baseline sealedv6 is27.430389467s. New unsealedv7 hls/qwen_decoder_v7 burst-loads
normweights onceperbatch and RoPE oncepertoken for allQ/Kheads. It also declares
proven disjoint per-element dependencies for inplaceRMS/RoPE, retaining sumorder.
Initialbuffer-only Csim passed worst5.72205e-6, argmax13; HLScompleted butrevealed
false pointerloop dependencies still II7/9. Savedinitialbuild as
build/v2/qwen-fpga-decoder-v7/hls-release.buffer-only; now rebuildingFINAL source
fresh hls-release via release.tcl csim+csynth+export SAMEprocess. No physicalbuildyet.
New runtime/scripts v6 overlap tokenizer and fullresidentSHA INSIDEcoldtimer.

IMPORTANT: board ALREADYrebooted before thissession. CurrentLinuxboot
 e9728928-307d-485b-b40b-63fa29d9296d, historicalproofboot6c80... differs.
InitialstarterFPGA/noDMA. We restored SAMEpinnedQ8 639446688B/39segments, checked
FULLsource+residentSHA. Restoredsealedv6APPsysone-qwen-decoder-stream100MHzidle,
operating, noARMNN. LinuxwasNOTrebooted byus. Newrecoveryevidence under
/var/lib/sysone/qwen-fpga-decoder-v7-boot-recovery, oldproofsunmodified.
SSH32187open RAM-only via scripts/v2/qwen_fpga_board_window_ssh_v6.py --work
build/v2/qwen-fpga-decoder-v7/board. Jobs00assertfailedBEFOREMMIO;01inventory,
02allocate,03weights,04v6restore PASSED. Queuepaused00 then explicitlyresumed.

CURRENT UPDATE: FINAL HLS/Csim/export passed. Norm output II1 vs7; RoPE II2 vs9.
Resource93860LUT/82081FF/218BRAM18K/507DSP/24URAM. 88RTLfiles audited vs IP/ZIP
AND actual physicalimports. Physical Vivado session63768 is running, core synth
since17:46local; logvivado-console.log. HLSsession54823 finished. Sourcehashesfrozen.
Runtimealso stagesfullSHA through2nativecopyworkers/4x4MiBbuffers; orderedSHA
stillchecksEVERYbyte. Verify latencyinboardsmoke; no priorphysicalclaim changed.
Statictraffic17.15064GB ->10.719s ideal128bit100MHz weightbusminimum before
otherwork, so10needsfuturebandwidth/reuse increase, not justoverheadremoval.

AUTOMATED ACTIVE COMPLETION: scripts/v2/complete_qwen_fpga_v7.py runs in local
execsession32311, waiting for QWEN_FPGA_ROUTED_READY. It audits exactRTL again,
packagesqualifiedhardware, then AUTOqueues05baseline/06upload/07extract/08deploy/
09causalfixture/10ONEcoldrealcommand/11promoteifcorrect+faster/12collectevidence.
Do NOT queueanother realcommand. Runner32187 executessequentially/stopsanyfailure.
CurrentVivado63768: OOC+topsynthPASSED, opt_designPASSED, placementstarted18:08.
ActualOOC95553LUT/77534FF/95BRAMtiles/507DSP/24URAM, still100MHzprofile.
No candidateboardlatencymeasuredyet. Runtimev6 parallelSHA2workers+4x4MiBbuffers,
startupoverlap,50uscommandpolling. Allnewsoftwareparses; fullSHAgatesNNcommands.

Afterjob12success, inspectproof/result, queue99close, awaitSSHclose, then run
scripts/v2/collect_qwen_fpga_v7.py. It collectsproofs, verifiesv2-v6seals unchanged,
writesREADME/researchresult andseal.json. Finallyrewritehandofflatesttop tofinal.
Ifphysicalorjobfails, fixcausebeforeexplicitresume; preserveinflightHWontimeout.
04-validate-recovery-json passed: fixedonlyliteral-newlineformat in NEWrecovery
JSON withoriginalbackedup; modelbytesandoldproofsunmodified.

Next: finishphysicalbuild, strictcheck_qwen_hls_export_v1.py explicitv7paths; sourcehashes
frozen; create_kr260.tcl100MHzphysicalbuild; auditactualRTL; package_v6/deploy_v6;
onecausalboardsmoke, ONErealcoldcommand, finish_v6 promotesonlyif fasterthan27.43s
and identicalgeneratedIDs. Historicalbootdiff: comparecall/path/IDs, toolboottext
mustmatchCURRENTboot/deployment. No sameboot-speedupclaim. Preservev2-v6seals.
No CPU NN/prefixreuse/hostFP32correction. Do notrestoreMiniLM. Target10notachieved.

---

# UNDER-30s QWEN0.6B FPGA DECODER DEPLOYED - 2026-10-19

## New-chat start here (latest)

USER requested coldtool<30s, Linuxlive,0.6BonFPGA,nosweeps, transfer tolargermodel.
COMPLETE: one cold realcommand **27.430389467s** vs42.208968752s,
1.53877x/35.0129% less. Full SSHjob28.047s, also<30. Same62prompt/16outputIDs,
sameweights/precision/prompt/protocol/full151936vocab. Zero prefixreuse.
Actual read_linux_file('/proc/sys/kernel/random/boot_id') executed, returned same
Linuxboot6c80ec1a-e7ae-473f-b169-d54f129615d1. AllNNmathFPGA, noARM/hostNN/correction.
Prefill11.8253s vs19.5789; decode8.4290s vs15.5048; fullmodelhash4.747s and
vocabsetup1.919s included. Workunchanged77inputs/2156semanticlayers/868weightpasses,
1221commands/2430976vocabrows. One coldrun only, no warmrepeat or benchmark sweep.

Read docs/research/2026-10-19-under30-qwen06b-fpga-tool-command.md,
docs/research/2026-10-19-streaming-qwen-decoder-design.md,
build/v2/qwen-fpga-decoder-v6/{deployment-proof.json,README.md,seal.json}.

ACTIVE APPsysone-qwen-decoder-stream,99999999Hz,leftoperating/idle.
/usr/local/bin/sysone-qwen-fpga nowpoints /var/lib/sysone/qwen-fpga-decoder-v6/
scripts/v2/run_qwen_fpga_command_v5.py. Entry:
sudo sysone-qwen-fpga --query "Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'."
Alwayscoldprofile,--no-prefix-cache acceptedcompatibility. Nextout package/
last-command-result.json. Previouslauncher saved package/sysone-qwen-fpga.previous;
oldapps/packages retained. ARMmodelservicestopped-disabled/R5unloaded. Same39DMA
segments639446688B/scratch256MiB/context256. No reboot/JTAG/memoryincrease/paidcompute/
commit/push. Currentboot model/FPGAresidency; files/launcher persist, noautostart.
SSH86182 closed99queue; credentialRAMonly/no secretsaved.

CODE: hls/qwen_decoder_v6/{matrix_q8.hpp,model_profile.hpp,qwen_decoder.cpp}.
Stagedload/unpack/flataccumulate/rowreduce, static8registerrotation preservesFP32
sumorder. II2accumulator/II16rowreducer, SRLFIFOs preserveBRAM. Genericmatrixcap6144
passedcols2048/6144/1056 andargmax; realfirstlayer4tokens/full4/partial1+3/causal/
norm/argmax13 passedmax5.72205e-6. Boardfixtureall8casesmatchedsameerrors.
HLS82553LUT/74231FF/194BRAM18K/453DSP/24URAM. Final100MHzroutedsetup+0.896ns,
hold+0.010ns, bit/XSApass. No arithmeticthroughputclaim beyondmeasuredonecommand.

Runtime src/sysone/v2/qwen_fpga_runtime_v5.py derives/checkscompiledshapevsweights,
embeddingstride/KVwidth/layers/vocab/RoPE/context, optionaluntiedoutput_projection,
alignment/scratchguards. Actualcompiledconstantsparsedbypackage frompreprocessed
source, supportsprofileoverrideswithout silentmetadata mismatch. Q8only/head128,
4tokenlanes; futurelargermodel requiresownweights/memory/quant/fit/numericalcheck.
CurrentDMA/table64x16MiB=1GiBlimit NOTextended; largermatrixsimulation !=largermodel
fit/deployment. Corechangestransfer; no modelsizeincreased.

IMPORTANT FINALHASH: retainedoriginalboundedcachedcopySHAeverybyte4.747s.
Directmemoryviewhash measured9.621s inboardfixture, discardedBEFOREcoldrun.
Initialarchive00380ede... recordedinqueue03; finalarchiveSHA
036a8fdaf9c93a4f95589c4ffe7a91f5821e96f5d87525c523c11d3805d427c7.
Jobs07/08 guardedtwo-filehash-runtimeupdate only, FPGAimageunchanged. Numericfixture
proofincludesinitialhash timing; NNcore/layoutunchanged andallresidentbytesverified.

REBUILD: use release.tcl csynth+export SAMEprocess in cleanhls-release project.
Separateexport afterresynth reusedoldimpl RTL; caughtbeforedeployment, oldbuild
stopped/archivedvivado-stale-export. Final71RTLfiles audited vsIP/zip andactual
Vivadoimport bycheck_qwen_hls_export_v1.py; ip-rtl-consistency.json recordsPASS.
HLSfinal hls-release-console.log, physicalvivado-console.log. Frozenhardware-source-
sha256.json. Do NOT reuse oldimpl. CorrectIPrepo hls-release/solution/impl/ip.
Preparedscripts package/deploy/smoke/run/finish_qwen_fpga_v5.py; runner_v5.
Priorsealsv2(100)/v3(80)/v4(75)/v5(41) verifiedunchanged.

Requested<30s milestone achieved. No interactive10s/generalquality/WCETclaim.
Do not rerun benchmarks justtoverifyagain. Historicalsectionsbelowdescribeprevious
42s/66s/92s deployments andarenotcurrentlauncher.

---

# COMPACT TYPED FPGA CALL DEPLOYED - 2026-10-19

## New-chat start here (latest)

User asked nexttarget/why slow then "ok. go quick". Target discussed: next30s,
MVP10s, eventualinteractive3s. One focused software speed increment COMPLETE.
Same0.6B model/batchFPGA, ONEcold realcommand **42.208968752s**, down66.183s:
1.568x faster/36.224% reduction. No sweeps. Linuxsameboot and no PL reprogramming.

Read docs/research/2026-10-19-compact-qwen06b-fpga-tool-command.md and
build/v2/qwen-fpga-decoder-v5/{deployment-proof.json,real-command-result.json,seal.json}.
All modelmath stillFPGA; sameQ8weights, FP32arithmetic/full151936vocab. Runtimev3
unchanged. This is reduced work/output and startup, NOT increasedkernelthroughput.
Newprompt62tokens vs67; output16 vs35; prefill19.579s/decode15.505s;
vocabularysetup1.917s and FULLresidentmodelhash4.699s included in42.209s.
16prefillgroups,868weightpasses,2156semanticlayers,1221kernelcommands.
Zero cachedprefix. Allfullvocab2430976rows=16*151936 projected.

Model wireoutput is JSON [function_name,path], bothstrings generated verbatim on
FPGA. Host validates and structurallyexpands into same API object; no host
inference, argumentrepair, logitsrestriction or replay. Stop atcomplete typedJSON
insteadEOS. ActualmodelprefixedMarkdown despiteinstruction; parseracceptsopening
fence and stops afterarray beforeclosingfence/EOS. No EOS/exactID equivalenceclaim.
Same query and actualcall read_linux_file('/proc/sys/kernel/random/boot_id'),
same actualtoolresult and Linuxboot6c80ec1a-e7ae-473f-b169-d54f129615d1.

ACTIVE launcher /usr/local/bin/sysone-qwen-fpga nowpackage
/var/lib/sysone/qwen-fpga-decoder-v5/scripts/v2/run_qwen_fpga_command_v4.py.
Profilealwayscoldprefill; --no-prefix-cache acceptedcompatibility. Entry:
sudo sysone-qwen-fpga --query "Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'."
Nextoutput package/last-command-result.json; previouslauncherbytes saved package/
sysone-qwen-fpga.previous. Previousv4launcher/package/firmware retained.
SameACTIVE sysone-qwen-decoder-batch 99999999Hz, idle. Same39DMAsegments639446688B,
context256/scratch; ARMmodelservice remainsstopped-disabled/R5unloaded.
No reboot/JTAG/newmemory/paidcompute/commit/push. Currentboot residency, no autostart.
SSHrunner79574 closed99queue, secretRAMonly/no credentialsaved.

Newsource scripts/v2/{run,package,finish}_qwen_fpga_*v4.py,
qwen_fpga_board_window_ssh_v4.py; hls/qwen_decoder_v5/qwen_vocab_session.cpp is
vocab-only native SOFTWARE helper, NOT a newhardwarekernel. Helpercompiledonboard
againstexistingllama.cpp; loads once/servesencode+piece decoding inoneprocess,
no inferencecontext. NewPython syntaxchecked andtypedparserpartial/valid/framing/
wrongtype checked. Priorv2/v3/v4seals remainunchanged. Proof records helperbinarySHA.

Next hardware speed work should focus actualmatrix datapath/DDR throughput;
no new HLS build started in this compact-call increment. Still42s, above30s/10s
milestones; no interactive, generalquality or WCETclaim. Historicalsections below.

---

# BATCHED COLD PREFILL DEPLOYED - 2026-10-19

## New-chat start here (latest)

User requested batched prefill/weight reuse, Linux live, no sweeps, no model-size
increase yet. IMPLEMENTED, built, DEPLOYED and tested ONE real cold command.
Cold elapsed **66.183381559s**, previous **92.031362451s**: 1.39055x, 28.086% less.
Prefix caching disabled, zero reused tokens. Same prompt67/output35, exact same
IDs and actual read_linux_file('/proc/sys/kernel/random/boot_id'). Same Linuxboot
6c80ec1a-e7ae-473f-b169-d54f129615d1. All Qwen0.6B math on FPGA; no host/ARM
inference/correction. Linux executes tool. Prefill21.119s, subsequentdecode35.655s,
fullresidentmodelhash4.732s included. 17prefillgroups(last3),1428weightpasses vs2828,
2828semanticlayers unchanged,2181kernelcommands vs3630, full151936vocab unchanged.

Read docs/research/2026-10-19-batched-qwen06b-fpga-tool-command.md and
build/v2/qwen-fpga-decoder-v4/{deployment-proof.json,README.md,seal.json}.
HLS hls/qwen_decoder_v4 (4token URAM/weightbroadcast,II3). Runtime
src/sysone/v2/qwen_fpga_runtime_v3.py; helper scripts/v2/*qwen_fpga*v3.py.
100MHz routed setup+0.833ns/hold+0.010ns; finalbit/XSA PASS. CSimfull4/partial1+3/
norm/argmax PASS. ONE boardfixturealllanes PASS maxerror5.72205e-6. ONEcoldtoolPASS.
No warm repeat, extra baseline or benchmark sweep.

ACTIVE app sysone-qwen-decoder-batch 99999999Hz leftidle. Promoted launcher
/usr/local/bin/sysone-qwen-fpga points /var/lib/sysone/qwen-fpga-decoder-v4/
scripts/v2/run_qwen_fpga_command_v3.py. Command:
sudo sysone-qwen-fpga --no-prefix-cache --query "Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'."
Nextoutput /var/lib/sysone/qwen-fpga-decoder-v4/last-command-result.json.
Oldlauncher package/sysone-qwen-fpga.previous; oldfastapp/package retained.
R5unloaded, ARMmodelservice stopped/disabled. Same39DMAsegments639446688bytes,
same256MiBscratch0x60000000/context256. No memoryincrease/reboot/JTAG.
Currentboot deployment; files/launcher persist, no bootautostart installed.
SSHrunner71451 closed via99queue afterpromotion; no credentialsaved.
Priorv2(100files)/v3(80files) seals checkedunchanged. No paidcompute/commit/push.

Requested optimization complete. Latency still66s; no interactive/WCET/general
quality claim. Next speed work can use measuredprefill/decode budgets. No model
size increase performed. Older sections below are historical, not active launcher.

---

# FASTER QWEN0.6B FPGA DEPLOYED — COLD92.0s / CACHED44.6s

## New-chat start here (latest, 2026-10-18)

Latest user:233s too slow; optimize FPGA keeping Linux live, no benchmark sweeps.
Also asked about larger/capable model before locking timing/typed constraints.
Focused speed candidate IMPLEMENTED, DEPLOYED, MEASURED and left active.

Same model/prompt/real tool command:
- Original baseline 232.991s, decoderblocks205.774s,vocab17.554s.
- New COLD 92.031s (2.53x speedup,60.5% time reduction).
- Cached identical prompt 44.580s (5.23x vs original cold).
Both new runs generated same35output tokens as baseline and executed real
read_linux_file('/proc/sys/kernel/random/boot_id'). Result/unchangedLinuxboot:
6c80ec1a-e7ae-473f-b169-d54f129615d1. All NNmath FPGA, no ARM/host inference/correction.
Warm is KV prefix reuse, NOT output replay:66of67prompt tokens reused,
final prompt token rerun;35output tokens regenerated/full151936vocab eachstep.
Cold101input/2828layercalls; warm35input/980layercalls.

Read docs/research/2026-10-18-faster-qwen06b-fpga-tool-command.md and
build/v2/qwen-fpga-decoder-v3/{deployment-proof.json,README.md,seal.json}.
Previous50MHz233s deployment below is historical baseline, not active entrypoint.

DEPLOYED /usr/local/bin/sysone-qwen-fpga, now points package
/var/lib/sysone/qwen-fpga-decoder-v3/scripts/v2/run_qwen_fpga_command_v2.py.
On KR260: sudo sysone-qwen-fpga --query "Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'."
Optional --no-prefix-cache forces fresh prefill. Nextresult last-command-result.json.
ActivePL sysone-qwen-decoder-fast at99999999Hz; idle aftersuccess.
R5 unloaded, ARMmodel service stopped/disabled. Prior50MHz app+package andlauncher
bytes(sysone-qwen-fpga.previous innewpackage) retained. No MiniLM restoration now:
new request wants decoder active. Its sourcefiles/calibratedR5module stay ondisk.
Current boot ONLY for DMA/FPGA residency; files/launcher persist, no autostart.

Kernel hls/qwen_decoder_v3/qwen_decoder.cpp: target100MHz, matrixII3was4,
32word burst KV-head load to8URAM, reuse2GQAheads. Routed setup+1.927ns,
hold+0.010ns. CSim andrealhardware2token fixture PASS maxerrors2.14577e-6,
6.85453e-7. Cold blocks74.054s,vocab8.201s. Combined changes, no ablation/sweep.
Same639446688-byte officialQ8 model in39ownedDMAsegments, no new model allocation.

Runtime src/sysone/v2/qwen_fpga_runtime_v2.py has aligned scratchcopies,
percommandtimers,prefix cache guarded byboot/overlayinode/DMAinode/modelSHA/
kernelSHA/runtimeSHA/ropeSHA/manifestSHA,32byteownershiptag at scratch0x80.
Tag invalidated before request, metadata committed atomically only on success;
normal nonpreserving QwenFpga init clears tag. Cachefile prefix-cache.json.
CPU only tokenizes,copies/schedules,tracksIDs,decodes/validates/executes tool.
No CPU floating model ops, no vocab/reference replay. Pinned weights verified
by full hash on every call. Maxcontext256; same3read-onlyprocfiles registry.

New build helpers scripts/v2/{package,deploy,smoke,finish}_qwen_fpga_v2.py,
run_qwen_fpga_command_v2.py, qwen_fpga_board_window_ssh_v2.py. Fixed v3 package SHA
91264d139f1abb2855889f0a07fa8f98fe83aa3d968d139a2d9f7703e6441ae0.
Queue build/v2/qwen-fpga-decoder-v3/board:00baselineprofile,01upload,02extract,
03load,04hardwarefixture,05cold,06warm,07promote allPASS.99closed SSH98094.
Password stayed inRAM, not files. No reboot/JTAG/paidcompute/commit/push/sweeps.
Prior seals untouched. Do not rerun just to reestablish this evidence.

Model question: docs/research/2026-10-18-qwen-model-envelope-before-lock.md;
model-capacity-budget.json. Official1.7B H2048/F6144,28layers,Q16/KV8/head128.
Calculated uniformQ4_0 tensor bytes968249344(~923MiB) plusmetadata; not aQ4_K_M
size claim. Exceeds800MiBCMA; needsQ4kernel,widerworkspaces,revisedDMAaddressplan.
Current64segment/32bitlowDDR/Q8-only guards do not support it.4GBboardmemory makes
shortcontextquant1.7B plausible, not deployed/provenbetter. Compute grows3.2x
nonembedding even withQ4. No larger model downloaded/trained inthis task.
Recommend targeted0.6Btooltraining first, sizeincreaseonlywithlatencyheadroom;
version/freeze typedtoolABI independently; qualify timing on chosenmodel,
precision,context/memory/scheduling envelope. Onecommand/clocktimingpass is notWCET.

NEXT substantial latency lever: batched prefill/weight reuse, then lower-bit
weights/moreparallelcompute.92s cold/44.6s cached remain far from interactive.
No absolute deadline/general capability claim. User may steer next size/quality
work; current new deployment is ready for the current boot.

---

# FPGA DECODER SPEED OPTIMIZATION ACTIVE — 2026-10-18

## New-chat start here (latest)

UPDATE2: New100MHz image PHYSICALLY PASSED (setup+1.927ns,hold+0.010ns),
bit/XSA complete. Package v3 SHA91264d139f1abb2855889f0a07fa8f98fe83aa3d968d139a2d9f7703e6441ae0.
Uploaded/extracted /var/lib/sysone/qwen-fpga-decoder-v3; ACTUALLY LOADED
sysone-qwen-decoder-fast at99999999Hz, Linuxsameboot,APCTRL4idle.
Hardware2tokenfixturePASSsame2.14577e-6maxerror. Queue01..04PASS.
Queue05-fast-cold-command RUNNING, cachemissingso0reuse. After05PASSqueue06
samequery --out /var/lib/sysone/qwen-fpga-decoder-v3/warm-command-result.json
(nootherQwenFpgainitbetween; warmshouldreuse66of67prompttokens).
Then finish_qwen_fpga_v2.py --package /var/lib/sysone/qwen-fpga-decoder-v3
promotes launcheronlyifbothPASS/coldfaster. Capturestdoutproofhost/seal/updatehandoff
andcloseSSH. Newfullcommand success/latency notknownyet.


UPDATE: Vivado now ROUTING100MHz, post-place+1.889ns/intermediate route+2.020ns
setup, hold repair pending. No new PL load yet; wait final timing/XSA.
Runtime v2 now includes KV prefix caching: reserved scratch32-byte tag@0x80,
identity boot/overlayinode/DMAinode/weightSHA/kernelSHA/runtimeSHA/ropeSHA/manifestSHA,
invalidates tag before request, commits metadata only after success. Default
QwenFpga constructor clears tag (e.g. fixture), CLI preserve_prefix=True and
begin_prefix computes matching prompt IDs, capped atlen(prompt)-1 so final
prompt hidden/logits are recomputed. All output tokens ALWAYS generated onFPGA.
Cold/warm must be reported separately. --no-prefix-cache disablesreuse/commit.
Finish script scripts/v2/finish_qwen_fpga_v2.py added to package, requires
real-command-result.json(cold prefix0), warm-command-result.json(reuse66),
same67prompt/35outputs andrealtoolboth. Install launcher only ifcold speedup.
Need ONEcold+ONEwarm fixedcommand to validate this cache feature, not a sweep.
Keep identical prompt/model/fullvocab; save all evidence, no output replay.
New docs model envelope docs/research/2026-10-18-qwen-model-envelope-before-lock.md.


USER:233s too slow. Continue optimizing FPGA, keep Linux live, no benchmark
sweeps. Also assess larger/capable model before timing/typed constraints lock.
Prior 0.6B FPGA command success remains baseline, not completion of this speed task.

New target build: hls/qwen_decoder_v3, build/v2/qwen-fpga-decoder-v3.
Single candidate100MHz, matrix block II3 instead of4, KV-head URAM buffering
(8URAM) + explicit32-beat bursts, reuses each head for2queryheads.
HLS PASSED114BRAM18K/109DSP/32101FF/39449LUT/8URAM, matrixII3 achieved.
Real2token CSim PASSEDmax2.14577e-6; norm+argmaxalsoPASS.
Vivado physical build RUNNING exec57004, vivado-console.log and
vivado/qwen_decoder_kr260.runs/system_decoder_0_synth_1/runme.log.
HLSexec26971 andCSim68239 done. Do not deploy unless routed setup/hold passes.

One fixed-command baseline profiling run PASSED233.69s receipt,~233s internal:
205.774s in2828decoderblocks,17.554s in665vocabchunks; host is a small fraction.
Saved baseline-profile.json. No benchmark sweep. Baseline still deployed50MHz;
no PL change yet. Linuxsameboot6c80ec1a-e7ae-473f-b169-d54f129615d1.

SSH runner98094 authenticatedRAM-onlypassword,4h queue
build/v2/qwen-fpga-decoder-v3/board;00-profile-fixed-command PASSED.
Successor scripts/v2/qwen_fpga_board_window_ssh_v2.py fixed-upload allows
build/v2/qwen-fpga-decoder-v3/qwen-fpga-deployment.tar ONLY.
No password saved; user already authorized password earlier.

Prepared NEW scripts/v2/{package_qwen_fpga_v2,deploy_qwen_fpga_v2,
smoke_qwen_fpga_v2,run_qwen_fpga_command_v2}.py and
src/sysone/v2/qwen_fpga_runtime_v2.py. New app sysone-qwen-decoder-fast,
node qwen-decoder@a0000000 sameCSR compatible. Runtime enforces99..100MHz,
aligned32bit scratchcopy and command timing stats. Packaging requires final
routedXSA/bit/timing and CSR ABI match before it copies old model/rope metadata.
Deploy baseline=sysone-qwen-decoder(50MHz), verifies idle, usesxmutil liveLinux,
restores oldapp if loading fails beforekernelrequests. Do not overwrite v2seal.
Old userlauncher still points originalruntime until newfullcommand passes.

NEXT: finish physical100MHzbuild. Package with package_qwen_fpga_v2.py;
upload withrunner; extract /var/lib/sysone/qwen-fpga-decoder-v3 (fresh).
Run deploy_qwen_fpga_v2.py --package thatdir, then smoke_qwen_fpga_v2.py
(one2tokenfixture), then same67prompt/35output command using
run_qwen_fpga_command_v2.py. No hostNNinference. Record actual speedup, then
update existing launcher to newroot, preserving baseline. Capture clocks/app,
boot/modelhash/correcttool/proof, closeSSH, document/seal. No clock/benchmark sweep.
If timing fails, repair targeted path rather than deploy out-of-profileclock.

Model capacity: model-capacity-budget.json contains calculated 0.6B vs1.7B
weights/traffic (excludesGGUFmetadata,Q4_0NOTQ4_K_M). Official1.7Bconfig
https://huggingface.co/Qwen/Qwen3-1.7B/raw/main/config.json H2048/F6144,
28layers,Q16/KV8/head128. IdealQ4tensors~968MB plusmetadata, exceedscurrent800MiBCMA.
CurrentkernelQ8only,H1024/F3072;64DMAsegments/32bitlowDDR. Larger modelneeds
Q4decoder+largerwidth+revised DMAaddress/memory plan; cannotjustallocateRAM.
Advised user capabilityfinetune0.6first, then1.7BQ4iflatencyheadroom; freezetoolABI
separately; timingenvelopequalifiedaftermodel/precision/contextchosen.
No new larger model downloaded/trained yet. No paidcompute/reboot/JTAG/commit/push.

---

# QWEN3-0.6B FPGA TOOL COMMAND PASSED; LINUX STILL RUNNING

## New-chat start here (latest, 2026-10-18)

USER GOAL ACHIEVED: Qwen3-0.6B generated a real tool command with ALL model
math on KR260 FPGA. Linux executed read_linux_file('/proc/sys/kernel/random/boot_id')
and returned6c80ec1a-e7ae-473f-b169-d54f129615d1, unchanged Linux boot. No ARM/host
model inference or host FP32 correction. Q8 weights, FP32 activations ON FPGA.

Read docs/research/2026-10-18-qwen06b-fpga-tool-command-mvp.md and
build/v2/qwen-fpga-decoder-v2/{deployment-proof.json,real-command-result.json,
hardware-block-smoke.json,README.md,seal.json}. Prior ARM-success descriptions
below are historical and NOT this completion evidence.

DEPLOYED /usr/local/bin/sysone-qwen-fpga. On KR260:
sudo sysone-qwen-fpga --query "Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'."
Sources/package /var/lib/sysone/qwen-fpga-decoder-v2. Next invocation result:
last-command-result.json. Current proof real-command-result.json/deployment-proof.json.
Active PL sysone-qwen-decoder at50MHz; idle after completion, APCTRL4.
R5 unloaded; old sysone-qwen06b-mvp.service STOPPED AND DISABLED. MiniLM and
calibrated R5 files retained on disk; active FPGA is now decoder, not encoder.
Files persist, resident DMA+FPGA state CURRENT BOOT ONLY. No autostart/reboot flow.

Actual67prompt/35output tokens inclEOS,101inputtokens,2828blockcalls,
3630acceleratorcommands,5317760full-vocabulary rows.232.887s runtime,
233.469s SSH receipt. Correctness MVP, no latency/generalquality claim. All tokens
and generated text match separate pinned Q8 CPU reference; runtime never uses it.
No vocab masking, reference replay, host hidden/logit correction or CPU forward pass.
Linux only tokenizer/byte-copy/descriptor scheduling/token decode/tool dispatch.

Memory increased without reboot: firmware/qwen_dma_v1 owns639446688bytes in39
coherent DMA segments from existing800MiB CMA. Full official Q8 SHA verified
9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031.
Existing256MiB no-map reserved scratch includes56MiB KV (context256).
MemAvailable2664616kB,CmaFree20240kB after command. No another model allocation.
Model /home/ubuntu/sysone-generation/Qwen3-0.6B-Q8_0.gguf.

HLS v2 all28layers,H1024,FFN3072,Q16/KV8/head128. Full embedding/finalvocab151936.
Shared GEMV. Sources hls/qwen_decoder_v2, src/sysone/v2/qwen_fpga_runtime_v1.py,
scripts/v2/{package,deploy,smoke,run}_qwen_fpga* (run actual name run_qwen_fpga_command_v1.py).
Physical build PASSED50MHz, setup+6.408ns,hold+0.010ns,64052/64052nets,0routeerrors.
Bit/XSA build/v2/qwen-fpga-decoder-v2/vivado. Generated scratchCSR0x78 (not0x18).
Hardware2token first-layer maxerrors2.145767e-6,6.854534e-7. CSim also passed.

First scratch page-table memcpy caused user SIGBUS BEFORE launching decoder.
Aligned32-bit scratch transfers fixed it. Failed logs05/06, repair07, hardware
PASS08, realcommandPASS09, launcher/proofPASS10, idleproofPASS11 retained.
Initial upload tar preserved qwen-fpga-deployment-initial.tar SHA
b075e52b8f5b0fbc3e6cf4bf4c1765abbbc54f764cacfc51ade8f28d62a989bf.
Final corrected tar qwen-fpga-deployment.tar SHA
ef0b7c14e9235ddea20daa55318ba9523cf97df1546f52e355ac262b0c9b8ae1.
Final board installed file hashes match corrected package.

SSH runner86763 queue build/v2/qwen-fpga-decoder-v2/board closed via99 job.
No credentials saved. Board ubuntu@192.168.0.239 pinSHA256
EGYkdZirFAYH1XOF2uPZYSzmLMOj7obcj/xAeHIW/Qc. User authorized password use earlier.
No JTAG/reboot/paidcompute/commit/push/benchmark sweeps. Prior seals untouched.
Do NOT rerun hardware/benchmarks merely to reestablish these facts.

---

# QWEN0.6B FPGA DECODER BUILD IN PROGRESS; LINUX LIVE

## New-chat start here (latest, 2026-10-18)

UPDATE: Full physical build PASSED at50MHz: setup+6.408ns, hold+0.010ns,
64052/64052 nets routed,0routingerrors. Bitstream/XSA exported. Packaged8MB archive
SHA b075e52b8f5b0fbc3e6cf4bf4c1765abbbc54f764cacfc51ade8f28d62a989bf.
Uploaded/verified/extracted /var/lib/sysone/qwen-fpga-decoder-v2 on KR260.
ACTUALLY LOADED sysone-qwen-decoder via xmutil; FPGAoperating,50MHz,APCTRL4idle,
clock/AFI bound. Linux SAME boot. R5 safely unloaded, ARMgenerator stillstopped.
Boardrunner86763, queue00..04 PASSED. Queue05 hardware-block-smoke running
(hash model again, then real first-layer2tokens vs independentreference).
After05PASS, queue full real command. No FPGA command success claimed yet.
Logs build/v2/qwen-fpga-decoder-v2/board/results. Earlier build-in-progress
paragraphs below are previous phases. Current runtimefiles staged/deployed.


USER: Qwen3-0.6B must execute on FPGA, not ARM. Keep Linux running. Continue
until one real generated tool command executes; skip benchmark sweeps.
User also explicitly permits increased model memory. Previous ARM success is
NOT completion of this new goal. The old ARM service is now STOPPED (still enabled).

Current: hls/qwen_decoder_v2/qwen_decoder.cpp implements every model operation
on PL (Q8_0 weights, FP32 activations): embedding, all 28 decoder blocks,
RMSNorm/QK norm, RoPE, GQA KV attention, SwiGLU, final norm, full-vocab argmax.
Linux runtime only tokenizes/copies bytes/schedules FPGA/executes generated tool.
No ARM/host inference fallback. Native vocab-only helper uses no llama_context.

Memory limit resolved without reboot: firmware/qwen_dma_v1 module allocated
639446688 bytes in 39 coherent DMA segments from existing Linux800MiB CMA.
Full official pinned Q8 model copied and resident SHA verified
9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031.
~2.6GiB remains available to Linux; CmaFree45MiB. DO NOT allocate another model.
DMA module/model remain loaded. /dev/sysone_qwen_dma and its sysfs buffers table
own these pages. Existing256MiB no-map reservation is scratch/KV, separate.
Linux boot still6c80ec1a-e7ae-473f-b169-d54f129615d1.

Build v2: build/v2/qwen-fpga-decoder-v2. HLS synthesis/export PASSED, estimated
37487LUT/28668FF/114BRAM18K/103DSP. Actual Vivado decoder synthesis PASSED0errors.
Physical implementation currently running at one50MHz target, no timing sweep.
Main exec session74271; vivado-console.log; vivado/qwen_decoder_kr260.runs/impl_1/runme.log.
No new bitstream deployed yet. Existing BERT PL + calibrated MiniLM still intact.

Real-weight CSim two-token first-layer fixture PASSED (maxerror2.15e-6), including
scatter segment crossing, causal attention, QK norm/RoPE, SwiGLU. Norm and argmax
fixture also passed. These are simulations, NOT FPGA command completion.
One local CPU Q8 reference command (separate validation only) produced JSON
read_linux_file('/proc/sys/kernel/random/boot_id'), firsttoken73594,67prompttokens.
Reference result build/v2/qwen-fpga-decoder-v2/cpu-reference-command.json.
Never force these tokens or mask vocab during FPGA inference.

New sources: scripts/v2/{package_qwen_fpga_v1,deploy_qwen_fpga_v1,
smoke_qwen_fpga_v1,run_qwen_fpga_command_v1,qwen_fpga_board_window_ssh_v1}.py,
src/sysone/v2/qwen_fpga_runtime_v1.py. Packaging waits for final routed timing+XSA,
bootgen locally, dtc on board. Runtime uses generated registers.json (scratch CSR
0x78, not requested0x18), full-vocab151936 rows, context256, cache56MiB.

SSH successor runner86763 authenticated, idle queue build/v2/qwen-fpga-decoder-v2/board. Old runner82985 closed.
Successor expires4h. Old results00..04 succeeded. Old runner only uploads an old QAT
archive. Successor qwen_fpga_board_window_ssh_v1.py accepts fixed new deployment
tar,4h lifetime. Need launch successor with new work folder and RAM-only password
(user explicitly authorized earlier), close old runner. No password saved in files.
Board ubuntu@192.168.0.239, pinnedSHA256EGYkdZirFAYH1XOF2uPZYSzmLMOj7obcj/xAeHIW/Qc.
Root board staging /var/lib/sysone/qwen-fpga-decoder-v1; qwen_vocab built in runtime/;
model-residency.json proves full Q8 hash. Prior dashboard already stopped, ARM
service stopped, R5module loaded idle (actual status /sys/class/misc/sysone_r5_smoke/status).

NEXT: finish route/bit/XSA, package, upload, safely unload idle R5 and old PL,
load sysone-qwen-decoder via xmutil keeping Linux live; verify clock/AFI bindings
before MMIO. Run ONE two-token hardware fixture, then full prompt real tool command.
Keep decoder deployed if successful. If hardware numeric issue, repair focused
path. No benchmark sweeps/reboot/JTAG/paidcompute/commit/push. Prior seals untouched.
User says do not stop until FPGA command works. Update this header after progress.

---

# LIVE TOOL EXECUTION PASSED; QWEN0.6B DEPLOYED ON ARM; LINUX RUNNING

## New-chat start here (latest, 2026-10-18)

Latest user: integrate INT8 candidate, real tool execution without host FP32,
keep Linux running, no benchmark sweeps; do not stop until0.6B deployed/tested.
A real ONBOARD pipeline is now deployed and tested:
FPGA INT8 parser -> R5 integer heads -> real Linux file tool -> resident
Qwen3-0.6B-Q4_K_M response. NO laptop/host FP32 encoder correction.
IMPORTANT: Qwen generation is on KR260 ARM CPU, NOT FPGA. Existing FPGA supports
BERT only; causal decoder/0.6B FPGA deployment remains unbuilt. Do not conflate
this deployed/tested ARM model with FPGA decoder completion.

Actual query read /proc/sys/kernel/random/boot_id. FPGA inferred exact path;
Python read actual file; Qwen returned actual ID
6c80ec1a-e7ae-473f-b169-d54f129615d1 (32output/140prompt tokens, finishstop).
Shell receipt36.422s; internal24.822s; Qwen20.582s. No one-second target claim.
Read docs/research/2026-10-18-live-mvp-qwen06b-deployment.md and
build/v2/mvp-live-integration-v1/{README.md,result.json}.

DEPLOYED /usr/local/bin/sysone-mvp-int8 (sudo CLI). On KR260:
sudo sysone-mvp-int8 --query "Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'."
Sources /opt/sysone-mvp/v2; candidate
/var/lib/sysone/mvp-live-v1/encoder-registry-v2; last-result.json and
integration-proof.json in /var/lib/sysone/mvp-live-v1.
Qwen service sysone-qwen06b-mvp.service ENABLED/ACTIVE, localhost127.0.0.1:8016,
healthok. Q4 modelSHA15e434d8ddf0af38fe3f7003af6ce6eac4edada6df34324aa45979f9cc79f02e.
Pinned llama.cpp b11540, native ARM CPU,0GPU layers, context1024,4threads,
RSS574372KiB. Service stays resident after SSH closes.

Registry imageSHA4cd8502e5b065cdbf1892c22c59605c8accca9f8d15481663c4a61391a378f30.
First new-tool run returned no calls, no action executed, receipt retained.
Focused adaptation:48 fixed synthetic requests(36reads3procpaths,12denials),
84INT8trainingjobs,80epochs/560headupdates,no benchmark/checkpoint sweep.
Onlycount0/1+span changed; QAT encoder unchanged byte-exact. Newhead weights,
features,patch,image in build/v2/mvp-live-integration-v1/registry-training.
MVP handler allows only /proc/{sys/kernel/random/boot_id,uptime,version} reads.
No arbitrary shell/externalAPI. General tool quality not established.

MiniLM BYTE-VERIFIED restored after command, original R5 module/ELF restored,
R5idle pinned/mapped/may_run/quarantine/reserved0,leases0. Linux SAME boot ID,
FPGAoperating199999998Hz. SSH CLOSED; credentials not stored; no jobs running.
Existing dashboard/default MiniLM entrypoints unchanged. Each CLI loads parser,
restores MiniLM in finally, then Qwen remains resident afterward.
No JTAG/programming/reboot/dashboard restart/paidcompute/commit/push.

Evidence seal build/v2/mvp-live-integration-v1/seal.json. Prior seals retained.
Do not rerun training/hardware smoke/benchmark sweeps just to reestablish these
facts. User can now invoke deployed command directly. 0.6B FPGA decode is still
separate unfinished work; keep the ARM vs FPGA distinction explicit.

---

# ONBOARD INT8 ARGUMENT REPAIR PASSED; MINILM RESTORED — 2026-10-18

## New-chat start here (latest)

Latest user: fix INT8 argument correctness fully on FPGA without host FP32;
MVP focus, no benchmark sweeps. COMPLETED one correct fresh hardware proposal:
songs_v2_get_details(is_id="45077244", l="en-US"). R5 controlled 3 H768 FPGA
passes and computed integer heads; Linux did ordinary existing decoding only.
NO host FP32 model/correction ran. NO external API/tool executed. This is one
engineering fixture success, not broad model qualification or deadline proof.

Read docs/research/2026-10-18-onboard-int8-argument-repair.md and
build/v2/general-tool-int8-board-v4/{result.json,results/03-verify-restored/stdout}.
Candidate build/v2/general-tool-int8-mvp-v3/qat-bundle/candidate.img SHA256
f96d65f5bfb6996fdbe96dda05d32b4d220b1359a3554cf0fa3e19d67cf0ea0c.
Uses existing R5 ELF943478a490f8bcd04937e163600ab0b1b1a18e8ab364f571a25d95dcc93f19bb.
QAT adapts last2 encoder blocks +span only, 128 training jobs (64 schema+64query),
3epochs/96updates, no eval-based checkpoint choice. Fixture absent from training.
Embeddings+first10 encoder block image sections BYTE-IDENTICAL to original;
meta head and all original activation scales unchanged. No new benchmark sweeps.
Span-only adaptation and attention compensation failed and were not promoted.

MiniLM byte-verified restored, original R5 module/ELF identity restored, R5 idle
pinned/reserved/mapped/may_run/quarantine=0, leases0. Linux same boot ID
6c80ec1a-e7ae-473f-b169-d54f129615d1; FPGA operating, clock199999998Hz.
All board SSH sessions CLOSED; credentials not stored; no active jobs remain.
No JTAG/programming/reboot/dashboard change/permanent deployment occurred.
Do not automatically repeat completed board windows. Candidate remains staged
at /var/lib/sysone/r5-inference/general-encoder-int8-qat-v6; baseline deployed.

Training features/partial-image capture receipts are in general-tool-int8-board-v3.
Final staging01 failed after SHA-verifying/appplying patch (system Python lacked
numpy) BEFORE any switch; resumed bringup02 used target venv, reverified SHA and
completed smoke/restore03. Never-executed proposed CRC repair is cancelled/.
Runner resumes its existing sorted snapshot after pause: don't assume newly
queued earlier-numbered jobs run before already enumerated later jobs.
All failure logs retained. Prior sealed artifacts unchanged.

New seal: build/v2/general-tool-int8-board-v4/seal.json; preserves training and
candidate evidence, source snapshots and report. No paid compute/commit/push.
Next MVP work can use this fully onboard inference candidate; actual external
tool dispatch/permanent integration and broader quality remain separate gaps.

---

# POSITIVE HYBRID CALL PROPOSAL COMPLETE; MINILM RESTORED — 2026-10-18

## New-chat start here (latest)

User authorized using the supplied credential for the prepared temporary smoke.
It was used transiently through getpass; no credential was saved. SSH CLOSED.
No need for further login or repeated board smoke for this completed window.

Fresh R5-controlled FPGA inference + explicit host FP32 argument correction
produced songs_v2_get_details(is_id="45077244", l="en-US"). This is a correct
CALL PROPOSAL; no external API/tool executed. Pure INT8 still returns l=ID;
host correction is explicit, not a claim that INT8 accuracy is repaired.
Read docs/research/2026-10-18-mvp-argument-correction.md and
build/v2/general-tool-encoder-mvp-board-v2/{result,hybrid-result}.json.
Fresh hardware receipt is request/image/firmware bound; evidence_mode live_board_smoke.

MiniLM image byte-verified restored, original R5 ELF identity restored, R5 idle
pinned/reserved/mapped/may_run/quarantine=0, leases0. Linux SAME boot ID
6c80ec1a-e7ae-473f-b169-d54f129615d1, FPGA operating, clock199999998Hz.
Restored ELF SHA1ff1f09d422492f7e3d3af3632ed9ffb1e3268ff5d1bfd699d57486e6eee3b95.
No JTAG/programming/reboot/dashboard change/permanent deployment occurred.
No new benchmark sweeps, paid compute, commit/push or automation.

Scripts/v2/general_encoder_mvp_hybrid_v1.py validates bound physical receipt,
recomputes unchanged FP32 model on local HOST, rejects call-selection mismatch,
validates schema and logs every argument change. Actual change was only l.
Joint decoding alone and one training-only median64 calibration candidate failed
and were NOT promoted; preserve traces under general-tool-argument-fix-v2.

New evidence seal: build/v2/general-tool-encoder-mvp-board-v2/seal.json.
Prior seals and source versions unchanged. All board and finish processes EXITED.
Next MVP gap is runtime/dispatch and standalone integer quality; do not describe
this as a fully autonomous FPGA command executor or terminal-by-D-qualified.
User prioritizes MVP speed; do not restart benchmark campaigns.

---

# MVP ARGUMENT CORRECTION: HOST BRIDGE CHECKED; FRESH BOARD LOGIN PENDING

## New-chat start here (2026-10-18, latest)

Latest user: fix argument correctness and get one positive end-to-end command;
MVP focus, no benchmark sweeps. Read docs/research/2026-10-18-mvp-argument-correction.md.

Root diagnosed quantization drift on the SAME song fixture. Joint-span decoding
alone and one median64 training calibration candidate both still choose ID as
language; neither was promoted. Preserve all prior sealed sources/artifacts.
New rejected candidate and traces: build/v2/general-tool-argument-fix-v2.

Explicit temporary bridge scripts/v2/general_encoder_mvp_hybrid_v1.py recomputes
arguments with the unchanged FP32 model on the HOST after physical inference.
Call selection must agree, request/image/firmware receipt must match, both
structures validated. Reports every correction; executes no external tools.
Fresh FP32 computation on PRIOR hardware result returns correct ID=45077244,
l=en-US. hybrid-replay.json explicitly marks old physical evidence replay.
This does NOT fix pure INT8 argument quality or finish the standalone FPGA MVP.

Fresh same-request hardware->host-check queue prepared:
build/v2/general-tool-encoder-mvp-board-v2. User has been asked to run:
.\.venv\Scripts\python.exe scripts\v2\mvp_board_window_ssh_v1.py --work build\v2\general-tool-encoder-mvp-board-v2
Password stays in terminal/RAM. Prior login was CLOSED. No new board commands
have run yet. Queue clones old target stage to general-encoder-mvp-v3, runs
request-bound v3 target script, restores and byte-verifies MiniLM, closes SSH.
No JTAG/programming/reboot/dashboard changes. User latest action request is the
scope; no further permission question was added, only necessary authentication.

A finite local finishing process (exec session 65650) waits up to 15 minutes
for results/02-verify-restored/receipt.json, then runs the host correction and
writes hybrid-result.json/result.json. It cannot initiate SSH or touch board.
Inspect its process/session and queue results before starting duplicates. If it
has timed out, rerun build/v2/general-tool-argument-fix-v2/finish_window.py once
auth is available. No model training or benchmark jobs run.

When physical window finishes: inspect result, receipt/rollback/status; update
this top block/report to actual completed status and seal new evidence. Until
then the only positive proposal is explicit prior-hardware replay + fresh FP32.
MiniLM stays restored from the prior completed smoke; original ELF SHA
1ff1f09d422492f7e3d3af3632ed9ffb1e3268ff5d1bfd699d57486e6eee3b95.

---

# H768 BOARD SMOKE COMPLETE; MINILM RESTORED — 2026-10-18

## New-chat start here

User authorized one temporary H768/R5 hardware smoke with MiniLM restoration.
That exact window is COMPLETE; do not rerun automatically. R5 controlled three
H768 FPGA passes and computed logits; Linux reconstructed the call proposal.
Calibrated MiniLM image was restored and byte-verified, original R5 module/ELF
identity restored, Linux same boot, FPGA operating. SSH closed. No JTAG,
FPGA reprogramming, reboot, permanent entrypoint change or dashboard restart.

Read docs/research/2026-10-18-h768-board-smoke.md and
build/v2/general-tool-encoder-mvp-board-v1/result.json. Physical proposal matches
CPU INT8 reference but has WRONG language argument: songs_v2_get_details with
is_id="45077244", l="45077244" (expected en-US). This is real integration proof,
not semantic success, finished MVP, benchmark improvement or terminal-by-D proof.
No tools were executed. R5 idle: pinned/mapped/may_run/quarantine=0, leases 0.
Restored firmware SHA 1ff1f09d422492f7e3d3af3632ed9ffb1e3268ff5d1bfd699d57486e6eee3b95.
Linux boot 6c80ec1a-e7ae-473f-b169-d54f129615d1 unchanged; final clock 199,999,998 Hz.

User's priority: DON'T OVERTEST; bring MVP ASAP. Next work should target the
smallest argument-correctness fix and a positive end-to-end command, not more
benchmark grids/audits/optimization. Existing MiniLM is the deployed baseline.
Encoder head refinement epoch1 selected on 40 dev with larger audit deferred;
FunctionGemma v3 selection gains did not generalize to paired audit. No family
winner. General decoder FPGA port is still incomplete; do not conflate it with
this physical BERT-base encoder/R5 smoke.

All prior seals remain preserved. New board evidence seal is
build/v2/general-tool-encoder-mvp-board-v1/seal.json. Authorization is recorded
there. Native SSH requires transient terminal login; no credential is stored.
Earlier staging03 failed BEFORE model/module switching; corrected stage04
normalized manifest paths, v2 target normalized source identity. Logs retained.

---

# AUTHORIZED: one temporary H768 board smoke, then restore MiniLM

## New-chat start here (2026-10-18)

Current board-window progress: inventory/upload/tokenizer setup done. Stage03
failed BEFORE any model/module switch due Windows path separators. Fixed retry
is queued as04 in a fresh directory; user must rerun same local SSH command and
enter password in terminal. No credential saved. Queue05-08 then runs one
preselected engineering request, restores MiniLM, verifies restoration and closes
SSH. Runner now skips recorded jobs and pauses with login retained on failure.
Read board-work progress.json/results before any new action. CPU INT8 reference
proposes correct song ID but incorrect language; do not call it semantic success.

The USER EXPLICITLY APPROVED the async question: temporarily switch KR260 to the
built H768/R5 candidate, run ONE hardware smoke, restore calibrated MiniLM.
This overrides the earlier no-board restriction ONLY for this window. Do not ask
for that permission again. Linux stays running; NO JTAG, FPGA programming,
reboot, dashboard restart or permanent CLI replacement.

MVP priority remains: don't overtest; no new model/benchmark sweeps.
Candidate: build/v2/general-tool-encoder-mvp-v1 and .tar. Local preparation,
image/export checks and one R5-head ABI smoke are done. Candidate readiness and
limitations are in its README. No physical H768 inference has run yet.

Native BatchMode SSH authentication FAILED (board reachable). No credentials
are saved. User has been asked to run the interactive local command:
.venv/Scripts/python.exe scripts/v2/mvp_board_window_ssh_v1.py --work
build/v2/general-tool-encoder-mvp-board-v1
Password must be entered in their terminal, never chat/files. The runner pins
SSH host key and retains auth only in process memory for this single window.
Inspect connected.json, results/* and live processes before starting duplicates.
Queue00 inventory(read-only) and01 fixed-candidate upload prepared. Wait for
inventory results, confirm actual baseline image/module identity, then stage
package in a fresh root-owned private directory and run the target bring-up
script. Keep rollback proof and health results. Do not execute while another
copy is active. Root client respects /run/lock/sysone-inference.lock.

Existing seals remain unchanged. New board work root:
build/v2/general-tool-encoder-mvp-board-v1. Authorization scope saved there.
No paid compute, commit/push or automation. No hardware services started.

---

# MVP PRIORITY - hardware candidate ready, board window pending

## New-chat start here (2026-10-18)

Latest user instruction: continue FPGA integration and both models in parallel,
but DON'T OVERTEST; bring the MVP as soon as possible. Stop new benchmark grids,
larger audits and optimization sweeps. Focus R5-controlled FPGA inference with
Linux running and typed result. No claim the complete MVP works yet.

Read docs/research/2026-10-18-fpga-mvp-progress.md and
build/v2/general-tool-encoder-mvp-v1/README.md. Candidate bundle contains 132.8MB
INT8 v4 BERT-base image, H768 linked R5 firmware, relocated ABI, Linux module
candidate and ingress, one R5-head smoke: 19 logits exact. CPU ingress runs but
sample addition request returns no calls; no semantic success claimed.
Package build/v2/general-tool-encoder-mvp-v1.tar. All work OFFLINE so far.

An async question is PENDING: may we temporarily switch KR260 to this candidate,
run one hardware smoke and restore calibrated MiniLM? Existing NO BOARD
COMMANDS/CHANGES remains in force until user explicitly answers. No SSH/probes,
JTAG, reboot, module unload or model reload without that exception. Once granted,
do not ask again for that exact window. Script
scripts/v2/bringup_general_encoder_mvp_v1_target.py prepares target kernel module,
checks baseline/rollback identity and candidate firmware, one request then restore.
Confirm actual baseline image and rollback module paths/identity before executing.
No PL bitstream rebuild, dashboard restart or permanent CLI changes planned.

Parallel finite work complete: encoder heads epoch1 selected 11/40 vs 10/40 parent,
wrong accepted 17 vs 19. Fresh v6 audit DEFERRED for MVP speed. FG completed before
latest stop-testing steer: selected v3 dev 28/40 vs 22/40, but audit 50/72 vs 52/72
original; do not claim an improvement or promote from this evidence. Full BFCL
not repeated. Frozen manifests under general-tool-encoder-improvement-v5 and
functiongemma-development-v5. No model jobs remain running.

FPGA fetch/unpack/dot receipts: functiongemma-packed-fetch-v5 and
functiongemma-packed-fetch-synthesis-v2. 10,719 rows + 72 fault/reset checks; 3 widths
synthesized. No full decoder/routed timing. New packed_weight_row_descriptor_v1.sv
is UNFINISHED/UNQUALIFIED, defer rather than launching another large test sweep.
32-bit prompt boundary/C compile is under functiongemma-token-wire-v1.

Preserve ALL earlier seals plus general-tool-parallel-report-v5/seal.json and
MVP bundle-manifest.json. No paid compute/commit/push/automation. Calibrated
MiniLM PL/model/R5 remains unchanged; Linux running; hardware services stay stopped.
No family winner, new hardware inference result or terminal-by-D proof yet.

---

# Current continuation - expanded general-tool reference complete

## New-chat start here (expanded software evidence and offline Gemma foundations)

Latest user steering: advance FPGA implementation alongside CPU capability work.
Packed-weight RTL simulation and isolated synthesis are now complete. Continue
offline DDR fetch/unpacker and executor integration in parallel with model
quality work; the existing restriction on board commands/changes still applies.

Read docs/research/2026-10-18-general-tool-expanded-reference.md and
build/v2/general-tool-expanded-report-v4/comparison.json. User domain remains
GENERAL TOOL/FUNCTION CALLING. No family winner or new hardware qualification.
Corrected encoder training v4 is COMPLETE: 2,048 original requests + 256 denials,
two epochs, selected epoch1, dev selection 6/20,
separate component-disjoint audit 19/72.
No span-target round-trip failures. Full 1,240-request BFCL results:
encoder 165/1240; frozen official FunctionGemma
654/1240. Always-Reject 240/1240.
This is not matched task training/compute or a human blind test. Full v3 tuned
FunctionGemma evaluation, adequate training and calibration remain pending.

Run roots: build/v2/general-tool-expanded-training-v4/encoder and
build/v2/general-tool-expanded-evaluation-v4/(encoder-full,encoder-parity,
functiongemma-official-full,functiongemma-batch4-parity). Reference retains 527
completed single-request records plus 713 batch 4 results. 25 exact saved-output
parity checks passed. One administrative in-flight interruption retained and
reissued; no completed failure retried. Original single-request root is stopped,
not complete. All completed failures remain in the full benchmark denominator.

OFFLINE only: functiongemma_float_ops/streaming_float provide an independent
18-layer float reference; all 17 generated tokens matched stock eager FP32 on
one fixture. Six block fixtures, 24 RMS fixtures, 4 Q16 attention fixtures and 9
packed-code fixtures pass. No whole-model integer accuracy, integrated image or board
qualification is claimed. A separate packed_weight_row16 RTL block passes
3,988 simulated rows and isolated KR260 synthesis at 6/7/8 bits;
records are under functiongemma-packed-rtl-v2. No routing/timing/executor or
board integration yet. Numerical/codecs/resource records are under functiongemma-float-ops-v1,
functiongemma-decoder-float-v1,functiongemma-integer-ops-v1,functiongemma-storage-v2.
Uniform INT8 weights+KV do not fit the current 256MiB region. Conditional 7-bit
embedding estimate has 666,482 bytes margin; 6-bit has 21,638,002. Accuracy and actual
layout are unqualified. Token IDs need a new 32-bit transport, with text embedding
range checks; tokenizer added image IDs 262144/262145 are unsupported. All 1,240
declared text inputs pass preflight. Do not load any of these through current ABI.

Preserve all old seals and new build/v2/general-tool-expanded-report-v4/seal.json.
No model/evaluation job is left running. No paid compute, commit/push, automation
or BOARD COMMANDS/CHANGES. Calibrated MiniLM PL/model/R5 remains untouched;
JTAG/hw_server/XSDB/cs_server stay stopped, Linux running, no raw probes/power
cycle/stock restore/module unload/dashboard restart. Keep credentials out of logs.
Next: assess full results; improve adequate task capability/calibration before
choosing a family, then qualify whole-model integer path and both R5-controlled
FPGA ports. General-call payload typing/publication and terminal-by-D integration
remain distinct from inference correctness and from Linux delivery.

---

# Current continuation — general tool/function calling, 2026-10-17

## New-chat start here (clean training complete; checked-target successor prepared)

User domain remains GENERAL TOOL/FUNCTION CALLING. The goal remains a stronger
encoder versus FunctionGemma, eventually BOTH with R5-controlled FPGA inference
and Linux running, then a checked typed terminal result by D. No family winner,
adequate full training, full external evaluation or new board qualification is
claimed. Read `docs/research/2026-10-17-general-tool-clean-training.md` and
`build/v2/general-tool-clean-report-v3/comparison.json` first.

Finite clean-split v3 training is COMPLETE under
`build/v2/general-tool-clean-training-v3/encoder` and `/functiongemma`. Both restart their pinned
official checkpoints; same 512 xLAM originals + 64 synthetic explicit denials,
two epochs, final 2 transformer blocks. Encoder updates 774; generator 1098.
These are issued requests; effective training counts/failures are in the report.
Dev-only selection 20 requests (16 original + 4 denials); separate audit 72
(64 original + 8 denials), original shuffled dev offset 80. No train/selection/audit
record overlap; different denial wording families. This is NOT a blind test.
Selection/audit share four complete-schema components but no exact normalized
prompts. Future v4 audit excludes all components from the inspected dev prefix.
Both retain epoch 1 because epoch 2 tied. Encoder selection 5/20, audit
12/72, correct accepted
4/41.
FunctionGemma selection 14/20, audit 55/72,
correct accepted 47/62.
Always-Reject gets 8/72. Incorrect accepted calls remain a material
problem. Do not equate denials with accepted-command capability or clarification.

The stopped v2 clean-training attempt is diagnostic only: 207 annotations such
as str,optional were unsupported. Journals/partial checkpoints remain under
build/v2/general-tool-clean-training-v2; no final audit claimed. The v3
general_schema_annotations adapter lowers record reference failures 218 to 27;
unknown types and invalid values still fail. Optional is not nullable.

IMPORTANT ENCODER TARGET FIX: v3 still trained on 37 span targets that fail an
exact value round trip (case changes). The audit and corrected preparation are
in the v3 root. Successor src/sysone/v2/general_encoder_targets.py repairs 37
targets (31 exact alternate spans, 6 unrepresentable); all 1109 corrected span
targets round trip exactly. Reported v3 weights/predictions were NOT changed.
Use scripts/v2/train_general_comparison_v4.py for future training: checked
targets, general_call_matching exact matcher (no lossy large-int float cast),
default audit offset 144 to avoid the prior audit. v4 CLI/compile and target
preparation verified; NO v4 model training was launched. Do not call v3 weights
label-corrected. Use adequate data/training and development calibration next.

Evaluation-only adapter: scripts/v2/evaluate_general_clean.py supports partial
checkpoints, audit parity, and BFCL (--per-category 0 means all 1,240). Existing
build/v2/general-tool-clean-evaluation-v3/ contains
8-request parity checks and repeated 25-case BFCL pilots, NOT the full benchmark.
All failures remain in denominators; BFCL checker/registry receipt verified and
verdicts rescored. Small public/reused pilots cannot select a model family.
Encoder 256 per-pass vs generator 2048 context/256 output, max 8 tools/4 calls; different
compute budgets. No A53 speed, energy, WCET or hardware timing result is claimed.

33 relevant tests pass. The prior 252-file artifact seal was
verified unchanged; new seal is `build/v2/general-tool-clean-report-v3/seal.json`. Preserve all
sealed sources/artifacts. HANDOFF itself is deliberately mutable, with this
prefix and its prior bytes saved separately. No model/evaluation job remains
running after this continuation. No commit/push or automation was created.

OPERATIONAL: NO BOARD COMMANDS OR CHANGES were made. Preserve calibrated MiniLM
PL/model/R5 deployment; JTAG/hw_server/XSDB/cs_server stay STOPPED and Linux stays
running. No raw PS/RPU probes, power cycle, stock restore, module unload or
dashboard restart. H768 image ABI/buffer relocation and FunctionGemma PL port
remain unqualified. Never load through the current H384 deployment ABI.
Hugging Face access works; never print credentials or request tokens in chat.
No paid compute was authorized or used. Host CPU-only Torch remains the working
resource; the earlier optional GPU/resource question does not block local work.

---

# Current continuation — general tool/function calling, 2026-10-17

## New-chat start here (general domain selected; first CPU pilot complete)

This block supersedes the older provisional maintenance-task direction below.
The user explicitly chose **GENERAL TOOL/FUNCTION CALLING**. Keep the overall
goal: compare a stronger encoder and FunctionGemma, work toward deployment of
BOTH with R5 control and Linux running, then select the base from real evidence.
Selection, adequate full task training, on-board comparison and the complete
typed timing contract are NOT complete. No model-family winner has been chosen.

Read `docs/research/2026-10-17-general-tool-comparison-pilot.md` and
`build/v2/general-tool-pilot-report-v1/comparison.json` first.

Both official checkpoints/tokenizers downloaded and hashed:
- BERT-base-uncased: `86b5e0934494bd15c9632b12f734a8a67f723594`.
- FunctionGemma270M-it: `39eccb091651513a5dfb56892d3714c1b5b8276c`.
Hugging Face model and xLAM access now work; user logged in locally and accepted
publisher access steps. Never print/read credentials or ask for tokens in chat.
No paid compute was authorized or used. Host has CPU-only Torch, ~14GB RAM,
16 logical CPUs. Optional CPU/existing-GPU/resource preference was asked; it is
not permission to purchase compute, and does not block authorized local work.

GENERAL DATA: initial pinned sources under `build/v2/general-tool-comparison-v0`.
1,240 BFCL Python single/multiple/parallel/parallel-multiple/irrelevance requests;
upstream revision `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`.
xLAM revision `26d14ebfe18b1f7b524bd39b404b50af5dc97866`; five exact normalized
BFCL prompt overlaps excluded before splitting. The old schema-set-only split
had train/dev duplicate prompts. Those dev files were NOT used for this pilot.
Use **`build/v2/general-tool-data-v1`** for future work: 42,197 train / 5,120 dev /
12,678 diagnostic, connected components of shared normalized prompts or identical
full schema sets; zero cross-split exact prompt/full-schema-set overlaps.
Individual-tool/paraphrase/pretraining overlap remains possible; no human blind
test exists. RESTART FROM OFFICIAL CHECKPOINTS for clean-split training: old
128-record pilot weights have trained on some records now in clean dev/diagnostic.

FINITE GENERAL PILOT: same 128 issued xLAM records and 25 BFCL cases, all requests
and failures retained. Official FunctionGemma FP32 11/25; 128-record last-block
tuning 9/25; its dynamic CPU INT8 5/25. Legacy BERT extractor FP32 2/25, dynamic
INT8 3/25, actual FPGA-arithmetic HOST reference 3/25. Encoder and INT8 generator
have zero correct accepted calls. Always-Reject gets 5/25. Not a selection-grade
or matched-final-capability benchmark: legacy encoder max2 calls/tool versus
generator max4, 128-token per-pass versus generator2048 context, extractive heads
untrained initially, tiny/different training budgets and some CPU overlap.
Latest encoder source supports max4 calls/tool for new training, handles legacy
checkpoint cap explicitly, retains all profile failures, and never truncates.
BFCL checker functions are pinned/unmodified, with an explicit local model registry
adapter and Python-only scope; not a leaderboard submission or timing proof.

GENERAL INTEGER IMAGE (offline only):
`build/v2/general-tool-comparison-v0/bert-base-fpga-integer-v4`.
Reused FloatEncoder/IntEncoder/ImageMachine; paired token types explicitly folded
into two vocabulary banks (61,044 uint16 IDs), not silently discarded. Float
fixtures max hidden diff 1.24e-5; two image fixtures exactly match132,096 hidden
codes and370 logits. Image132,817,920 bytes, SHA
`d64801f880316a12c788db98056cd44e3251c91db834975c008ac4f10fc9dd89`.
Proposed IDs67eb0000 / hidden67ec0000 / mailbox67ee0000 fit256MiB but overlap
deployed buffers. Requires separately qualified H768 R5/module/client/tokenizer
ABI; MUST NOT load through current fixed H384 deployment. Not a hardware pass.
FunctionGemma head256/32-bit IDs/KV/causal/norm/gating/vocabulary PL path still
requires implementation and numerical/resource qualification. Do not drop it
based on the weak pilot or call A53-only work FPGA/R5-controlled inference.

Scripts: `prepare_general_tool_comparison.py`, `prepare_general_tool_splits.py`,
`prepare_bfcl_python_checker.py`, `run_general_encoder.py`,
`run_general_functiongemma.py`, `finalize_model_comparison_pilot.py` under scripts/v2.
Core helpers `general_tools.py`, `general_tool_encoder.py`, `general_tool_integer.py`,
`general_tool_eval.py` under src/sysone/v2. Checkpoint/source/data hashes and source
snapshots are in run roots. Earlier maintenance pilot under
`build/v2/command-comparison-pilot-v0` is diagnostic history, NOT the selected task.
Its long generator run was stopped at step287 after the domain choice; journal
retained, no final checkpoint claimed. Superseded preparations/stopping-token
bug/28-section compile failure are retained. Final listed pilots are complete;
no board or model job is left running by this continuation.

NEXT: adequate matched-profile general-task tuning on clean data, development-only
choices/calibration, full declared external evaluation and new human tests for
arguments, negation, clarification, rejection and composition/conditions. Keep
original FunctionGemma as a reference: tiny tuning regressed. Dynamic INT8 loss
needs investigation before hardware quantization. Obtain tuned A53 and actual
board references later. Reuse existing typed-result gate/formal/integration work;
the core goal remains a checked terminal outcome by D, distinct from correct
successful inference and from Linux delivery. Schema/compiler work supports it.

OPERATIONAL: **NO BOARD COMMANDS OR CHANGES IN THIS CONTINUATION.** Preserve the
calibrated MiniLM PL/model/R5 deployment and all prior seals. JTAG/hw_server/XSDB/
cs_server must stay STOPPED; Linux stays running. No raw PS/RPU probes, power
cycles, stock restore or routine module unload. Do not restart dashboard. Last
known operational status is the COMPLETE calibrated R5 block below; it was not
re-probed here. No commit/push, recurring automation or new physical action.

---


# Handoff: System One on FPGAs â€” v2 runs on Nexys 4 DDR and KR260

## New-chat start here (model comparison and deployment priority, 2026-10-17)

## ACTIVE USER GOALS: stronger encoder versus FunctionGemma

This section supersedes earlier research recommendations about model order and
old diagnostic continuation instructions below. The user explicitly requested:
first determine our base model by deploying and benchmarking (1) a stronger
encoder and (2) FunctionGemma; consider (3) a typical small LLM afterward.
Do not select the encoder as the winner in advance or substitute more calibration
of the existing MiniLM for the requested new-model capability comparison.
This turn updated the handoff only; no new model was trained or deployed.

Next chat should execute the comparison, not repeat the broad literature review:

1. Inspect available checkpoints, datasets, toolchains and compute. Freeze a
   concrete stronger-encoder candidate and FunctionGemma 270M checkpoint. Existing
   research suggests ModernBERT-base as a quality reference/teacher and a
   BERT-base-shaped model as the more compatible FPGA candidate; the encoder
   checkpoint is NOT yet selected. Explain any choice between these clearly.
2. Define one shared command task, canonical typed output and evaluator. The
   bounded maintenance-command task in the research report is a starting proposal,
   not a user-approved immutable application specification. Compare complete
   commands and arguments, negation, conditions/composition, clarification and
   rejection; intent labels alone do not measure the requested capability.
3. Establish matched software references, task fine-tuning and quantized quality
   before expensive hardware changes. Use separate train/dev/blind test data,
   equal task/schema information and recorded training budgets. Preserve all
   issued requests, failures and configuration/checkpoint hashes.
4. Work toward deployment and on-board benchmarks of BOTH candidates. Stage
   software references and new hardware paths separately; do not silently call
   A53-only execution FPGA inference or R5-controlled inference. Production PL
   paths keep R5 in control and Linux running. The user's two-model comparison
   is the priority; previous proposed generator accuracy gates are guidance,
   not authority to drop FunctionGemma without presenting concrete evidence.
5. Report full-command accuracy, argument/slot scores, accepted error/coverage,
   structural validity, latency p50/p95/p99, startup versus resident latency,
   generator prefill/decode/full completion, memory and measured energy when
   instrumentation exists. Include a tuned A53 software baseline, current MiniLM
   regression and quantization loss. Percentiles are not hard time guarantees.
   Choose the base from observed capability, timing/resource cost and integration
   feasibility; report any blocked deployment honestly with the next concrete step.
6. Only afterward consider a general small LLM, such as Qwen3-0.6B non-thinking,
   if the first comparison leaves a capability gap worth its additional cost.

Preserve the CENTRAL PROJECT GOAL: typed, time-guaranteed local output. Function
calling is an application and constrained decoding is supporting machinery.
The intended contract is one checked canonical terminal outcome by D after
admission: Accepted(payload), Clarify, Reject, Deadline or Fault, with no late or
stale proposal becoming actionable. A failure outcome by D is distinct from
successful inference by D, semantic correctness, or Linux/network delivery.
The schema compiler is optional supporting work, not a replacement for this goal.
Existing typed-gate RTL/formal/integration evidence must be reused; do not
reinvent it. The working R5 classifier deployment does NOT yet qualify the full
typed timing contract on the board. Integrating and qualifying that mechanism
remains the central systems milestone after/alongside the model selection work.

Prior-art correction: inspected the complete public tree at revision
c8ba8e7fdbe0b7c5f694060f47c0c6abdb07f974 of
https://github.com/Ewo8om3/deadline-typed-inference . It contains a concept paper,
figures/site/docs and external evidence notes, no implemented compiler/checker,
simulator, RTL or executable test suite in that tree. BUILDING.md builds the
paper; the manuscript describes implementation as future work. Cite conceptual
overlap without treating it as an implemented competing hardware system. This
does not itself establish our novelty. Our candidate contribution is a specific
implemented/verified typed-result deadline mechanism, integrated with real
inference and evaluated under stalls, invalid/stale proposals and recovery.

Operational constraints persist: KEEP JTAG/hw_server/XSDB/cs_server STOPPED;
Linux stays running; trusted Linux deployment path; no raw PS/RPU register probes
or routine power cycles. Preserve the working calibrated MiniLM package and all
sealed artifacts. Use separately qualified successor images; no unverified
weight-file swap. Larger models require new layouts/buffers/firmware and decoder
support as detailed in the research report. Current accelerator reservation is
256MiB, attention head dimension max64, token IDs uint16 and R5 H384/class384;
FunctionGemma is not compatible with those limits without implementation work.
No paid compute was authorized by this handoff update. No commit/push requested.

Read next:
- docs/research/2026-10-17-encoder-vs-generator-direction.md and sources.json
- docs/research/2026-10-17-typed200-r5-calibrated-results.md
- docs/research/2026-10-15-typed-timing-contract-plan.md
- Latest COMPLETE operational block below; later IN PROGRESS blocks are history.

RESEARCH2026-10-17 MODEL/PROJECT DIRECTION REVIEW COMPLETE:
User requested research comparing stronger encoder and small generator onKR260
for usefulness/novelty. Read docs/research/2026-10-17-encoder-vs-generator-direction.md
and companion sources.json (28primary/author sources, one unverified lead).
Recommendation: local maintenance-command compiler,12APIs/boundedtypedplan;
encoder-first hardware, ModernBERT-base softwarequalityreference/teacher and
compatibleBERT-base-shapedstudent; fine-tunedFunctionGemma270M challenger.
Provelearned commandcapability onnewhumanreviewedblinddata beforedecoderport.
FunctionGemma needshead256/vocab262k/32bitIDs/KV/newops; Qwen0.6B W4nominal300MB
exceeds256MiBreservation. ExistingR5fixedH384 and384classABI cannotjustloadthem.
No modeldownloads/training/boardchanges/JTAG/paidcompute occurred thisreview.
Calibration remainsdeployed asbelow. Noveltyhypothesis: schema-derived
work/state/resultcontract with controlledquality/risk/energy/deadline experiments,
not firstencoder/generator/grammar/router/watchdog. Public deadline-typed-inference
concept and grammarsparseprojection priorart explicitlyacknowledged. Proposed
engineeringgates/targets are NOT measuredresults. Nextimplementation suggested:
12APItaskspec, canonicalAST/evaluator,humanpilot and matchedtaskfine-tuning.
No newbuild/deployment wasstarted bythisresearch itself.

CURRENT2026-10-17 R5 CALIBRATED CLASSIFIER HARDWARE TRIAL COMPLETE:
Read docs/research/2026-10-17-typed200-r5-calibrated-results.md first.
Accepted=True; current ELF 1ff1f09d422492f7e3d3af3632ed9ffb1e3268ff5d1bfd699d57486e6eee3b95.
Baseline55261 complete, zero errors; candidate350 reference+6580 paired requests
complete, zero errors. Tau0.36 fit only ondev. Paired dataset results in
build/v2/typed200-linux-r5-calibrated-v1/paired-summary.csv. Linux sameboot,
JTAG stopped, PL/model/CLI unchanged, onlyfixed R5 image/module changed if
accepted. Model weights unchanged, classifier calibration improved. UART closed.
App/model/module stay loaded; R5 idle, all resources released. Dashboard stays
stopped. Do NOT restore stock or unloadmodule as routine cleanup. No pending
board job or required physical action. Earlier runner states below historical.

CURRENT2026-10-17 CALIBRATED R5 HARDWARE TRIAL IN PROGRESS:
Latest checked22:17:29UTC:1250/6580 paired requests, zero errors. Same-input
CLINC1008:86.41%->90.48%; multi242requests/705decisions:86.81%->91.49%.
Median CLINC188.49->188.12ms; multi209.79->209.67ms. Multi p95226.41->230.82ms.
Snapshot build/v2/typed200-linux-r5-calibrated-v1/snapshot-1/paired-summary.md.
Live calibratedELF andsameboot/CPUs/FPGA verified, local+targetJTAG processes0.
Full-run promotion stillpending; do not duplicate/stop the existing unit.
User asked status and actual model improvement, thencontinue. Baseline remaining
55261 DONE+sealed, zero errors. Current new candidate root
build/v2/typed200-linux-r5-calibrated-v1; source
firmware/typed200_linux_r5_calibrated_inference. Ported missing CLINC softmax
OOS rule into R5, fitted tau0.36 ondev totalaccuracy only (not held-out labels).
Dev2965/3100->2977/3100, OOS52%->73%; in-scope97.1%->96.8%. Weights unchanged.
Oldtau.48 artifact and faileddevtotalaccuracy criterion preserved. Newpolicy
passes3100dev native labels,350cases191401 exactlogits, changed R5F emulation.
ELF1ff1f09d422492f7e3d3af3632ed9ffb1e3268ff5d1bfd699d57486e6eee3b95.
Target root /var/lib/sysone/r5-inference/calibrated-v1; unit
sysone-r5-calibrated-v1. Session12440 holds pinned SSH creds onlyinmemory;
upload/stage/modulebuild then350 hardware reference cases and6580 paired
CLINC+Multi-CLINC requests. Root driver gatespromotion: neither datasetmay
regress and combinedcorrect mustincrease, else idle rollbackoldmodule.
Kernelmodule source/session unchanged; onlyfixedR5image differs. Existing
CLI client, model and PL stay untouched. Same Linuxboot; JTAG stays stopped.
Passive UART COM9 session32424. DO NOT stop/overlap/restart currentjob.
Local pipeline closes UART, downloadsarchive, runs finish_r5_calibration_deployment.py
to verify/export pairedCSV/report/seal/HANDOFF. Currentreport
docs/research/2026-10-17-typed200-r5-calibrated-results.md is RUNNING.
Check unit/progress before action; progress-plan.json innewbuild. Onuncertain
R5run never blindunload; kernelwatchdog/quarantine remains. No physicalaction
required. Model quality change is classifiercalibration, not newtrainedweights.

CURRENT2026-10-17 REMAINING HELD-OUT RUN COMPLETE:
Read docs/research/2026-10-17-typed200-r5-remaining-results.md first.
All55261 new requests completed, zero runtime errors. Prior700 excluded.
R5 controls inference/heads; Linux running; JTAG stopped. No model/PL/client
changes. Dataset accuracy/latency in summary.csv; combined700+remaining in
combined-summary.json. Same boot/200MHz PL; all R5 resources released.
Module/app/model stay deployed, dashboard stays stopped. UART closed.
No recurring collection or pending board action. Preserve newly sealed files.

CURRENT2026-10-17 REMAINING HELD-OUT RUN IN PROGRESS:
User requested all remaining held-out cases excluding700, R5 control/Linux/JTAGoff.
Selected55261 eligible inputs; build/v2/typed200-r5-heldout-remaining-v1.
Root stage /var/lib/sysone/r5-evaluation/remaining-test-v1; unit
sysone-r5-heldout-remaining-v1, bounded8hours. Prediction journal flush each
request, summary each250. TTY exec session88065 holds pinned SSH/sudo password
in memory only; uploads archive, waits for unit, fetches gzip results, closes
UART via .stop, invokes scripts/v2/finish_r5_remaining_eval.py automatically.
UART COM9 passive session16689 remains open during run. No JTAG processes.
Read current unit/summary before restarting anything. Do NOT rerun entire suite
or stop the active run due to a new chat; no overlapping inference requests.
Host controller writes build/.../target logs. Progress plan in same build;
SSH helper can poll it in a separate connection. Model/PL/client/firmware unchanged.
Future final report docs/research/2026-10-17-typed200-r5-remaining-results.md;
currently RUNNING. Finalizer checks every R5 result/cleanup, excludes prior700,
recomputes metrics, exports CSV and combined summary, preserves prior seals,
then prepends COMPLETE here. If SSH disappears, board unit is independent,
so reconnect/check before rerun. No reboot/powercycle/rawPSMMIO authorized or needed.

CURRENT2026-10-17 FRESH HELD-OUT ACCURACY/LATENCY COLLECTION COMPLETE:
Read docs/research/2026-10-17-typed200-r5-heldout-results.md and validation JSON
FIRST. User requested fresh held-out existing-dataset examples with R5 control,
Linux running, JTAG stopped. First finite batch DONE:700 requests,100/group,
ZERO runtime errors. This is ground-truth accuracy collection, not another
bit-exact replay. No training/model/PL/firmware/client changes were made.
New root build/v2/typed200-r5-heldout-eval-v1, seed20261017. Exact encoded
train/dev and prior350 inputs excluded; prior350 text segments and duplicate
selected inputs excluded too. All label tables matched model. Corpus existing
test splits; freshness is relative to previous350, not a new sourced dataset.

Label accuracy: ATIS98/100=98%; CLINC89/100=89%; HWU92/100=92%; MSRP73/100=73%;
multi-CLINC255/306=83.3% (segment decisions); SGD73/82=89.0% (18 unseen/unscored
intents excluded); SICK80/100=80%. Slot spanF1: ATIS.890, HWU.843, SGD.528.
Overall on-board per-request latency p50=208.889ms,p95=277.684ms,p99=332.435ms.
PL encoder-only p50=8.545ms,p95=22.654ms. Request timing includes tokenization,
runtime checks, TCM/PM R5 prepare/start, PL, R5heads, result copy and stop; it
excludes lockwait, initialprocess/model/suiteload, SSH, scoring and logwrite.
Single sequential long-lived process, no isolated R5head timer or WCET claim.

Local summary.json/summary.csv, requests.jsonl/requests.csv, metadata.json,
cases.json,selection.json preserve all predictions/gold labels/timings/logit
hashes and R5trace/cleanup evidence. Remote /var/lib/sysone/r5-evaluation/fresh-test-v1.
All700 fresh R5 PASS completions and full resource release checked. Same boot
6c80ec1a-e7ae-473f-b169-d54f129615d1 at15:42:17UTC, CPUs0-3,taint12288 O/E,
FPGA operating, PL0/1 199999998Hz enable/prepare1/1. R5module stays LOADED,
sessionidle/off between requests. sysone-infer remains ready, dashboardoff.
UART CLOSED; no JTAG processes, reboot, rawPSMMIO, commit/push or physical
intervention. No recurring collection automation installed; first700 batch
finished. Future fresh batches must also exclude these700 input hashes.
11140priorfiles +50newfiles sealed. Preserve earlier current-state constraints
below: do NOT unloadmodule/restorestock as routine cleanup.

CURRENT2026-10-17 R5 CONTROLS INFERENCE AND COMPUTES HEADS; LINUX STILL RUNNING:
Read docs/research/2026-10-17-typed200-linux-r5-inference.md and validation JSON
FIRST. User explicitly requested R5 control+heads, existing PL/model reuse and
JTAG stopped. DONE on hardware, trusted Linux path. New root
build/v2/typed200-linux-r5-inference-v1; firmware/typed200_linux_r5_inference.
All350 frozen requests on REAL R5 passed1798 head jobs/191401 integer logits
and scaled winning labels. Independent installed CLI request also passed.
Linux only tokenizes/transports/formats; R5 issues PL RUN and computes pooled,
token/slot and pair logits+binary64 scaled argmax. Nine classifier/slot heads
covered by seven dataset groups. No A53 operational classifier arithmetic.
Same command: sysone-infer "show me flights from denver to boston tomorrow"
Explicit --dataset atis(default)/clinc/hwu/sgd/multi/msrp/sick, --json for logits.
New R5 CLI does not implement probability reporting or Python auto routing.

Reused loaded sysone-v2-attention-context-capture and exact existing MiniLM L12
model; NO PL reconfiguration/model reload. PL0/1 remain199999998Hz enabled1/1.
Mailbox62400000 size512KiB within no-map256MiB, IDs62100000 hidden62101000,
program60000400. Only private64KiBATCM used, noBTCM/modechange. Corrected startup
NO VBAR; actualR5F VFP and allnumerics passed. ELF SHAe5dcdf1c863c917bb4c591b9820216c5beea81883a70af60044b735eee2492f4.
Module SHAe6f834a35a9c73c1bf768aa2ff05b049b52b418e9b1eb0c204f4e1db338965a0.
Normal Linux firmware PM/two-lease engine, extra PL0clockref,30sec recovery.
Each request prepares/starts R5, returns PASS/DONE, stops R5/releasesleases.
R5 is idle/off between requests; kernel module MUST STAY LOADED for CLI readiness.
Do NOT restore stock/unloadmodule as routine cleanup. Dashboard stays stopped.
Root stage /var/lib/sysone/r5-inference/deploy-v2; prior A53 entry script backup
there in sysone-infer-a53.before. No boot service/network server installed.
Same boot6c80ec1a-e7ae-473f-b169-d54f129615d1, CPUs0-3online, taint12288 O/E;
final R5 pinned/reserved/mapped/may_run/loaded/quarantine/leases/error all0.
UART CLOSED; no JTAG processes, rawLinuxPSMMIO, reboot, commit/push. No physical
action pending. Trusted Linux remains assumed; no exclusive-owner/harddeadline
claim. Previous source-authentication audits are not blockers to this path.
11056priorfiles+83new files sealed. Earlier failed host/emulator/staging attempts
retained; emulator needed R5F rather than non-FPU R5, inline700KBmodule staging
was replaced with20KB plan+verified board-local modulecopy. Current CLI ready.

CURRENT2026-10-17 FULL INFERENCE DEPLOYED, READY THROUGH TRUSTED LINUX:
Read docs/research/2026-10-17-typed200-trusted-linux-inference.md and validation
JSON FIRST. User explicitly requested full inference via trusted Linux, JTAG OFF.
SUCCESS: build/v2/typed200-trusted-linux-inference-v1/deploy-v3; root service
sysone-trusted-inference-deploy-v3 exit0 runtime32.390sec (observation only).
Qualified sysone-v2-attention-context-capture app LEFT LOADED, model LEFT inDDR.
Live PL0/PL1 both199999998Hz enable/prepare1/1. MiniLM-L12 model33916928bytes at
60000000 fully loaded/readback identical SHA4129baded344729ccc7ef6a3f0a2b34799280a91d88173ae1c0b197cdef8c3bb.
Backend is PL encoder + on-board Linux A53 tokenization/classifier/slot heads.
R5 NOT involved in this inference run; exclusive-owner enforcement is deferred.
350/350 frozen encoder hidden-state checks bit-exact, seven dataset groups,
all predictions recorded. This does NOT mean350/350 correct ground-truth labels.
Example flight request yielded atis_flight p0.999 with Denver/Boston/date slots.
Installed /usr/local/bin/sysone-infer, tested independently; sudo+flock serializes
requests. On board: sysone-infer "show me flights from denver to boston tomorrow"
Defaults ATIS intent+slots; --dataset clinc etc can select existing other heads.
Repo/home assets unchanged; /home/ubuntu/system-one-fpga and sysone-venv reused.
Dashboard intentionally STOPPED while encoder owns PL. Do NOT restore stock or
restart dashboard as routine cleanup: user requested usable deployed inference.
No automatic boot reload/network server installed; current-boot CLI ready.
Client refuses absent app or mismatched/unloaded DDR after reboot.

Root target stage /var/lib/sysone/trusted-inference/deploy-v3; result/eval/logs
collected locally. Failed v1 stock filename underscore/hyphen and v2 Windows
path separator preflights retained; both stopped before hardware change.
New controller/helper scripts handle real Linux paths. Recovery avoids unloading
after uncertain DMA RUN. No target PS/RPU rawMMIO, JTAG, R5, reboot, RTL/model/
kernel/module rebuild, commit or push. No physical intervention pending.
Same boot6c80ec1a-e7ae-473f-b169-d54f129615d1, CPUs0-3online, taint12288 O/E,
manager operating. UART CLOSED. Prior10996files +59new evidence files sealed.
This supersedes earlier smoke-only and stock-restored current-state blocks below.

CURRENT2026-10-17 TRUSTED-LINUX R5 SMOKE DEPLOYED AND PASSED:
Read docs/research/2026-10-17-typed200-amp-trusted-r5-smoke.md and validation
JSON FIRST. User says prioritize deployment and reduce overengineering; keep
JTAG stopped. Took the scoped trusted-Linux diagnostic path, deferring exclusive
owner enforcement. Do not restart source-authentication research as a prerequisite
to further trusted-Linux diagnostic progress; do not claim isolation is certified.
New build/v2/typed200-amp-trusted-r5-smoke-v1 preserves10963 prior files +32new.
Reused qualified PL/ELF/module, corrected workload checker (no constant-ID rule).
Actual smoke-trial-v1 unit success exit0,9.372sec observedruntime. R5 PASS,
4exactmarkers; final68writes/errors0. ARtag12000 ID109; AWUSER2800/2000/2000/2800,
PROT1, AWIDs189/1a9/1c9/1e9. Kernel watchdog stopped R5 and released TCM/clock.
Recovery PASS: module unloaded, stockk26/dashboard active, all runtimefilehashes
unchanged, PL0 99999999Hz enable/prepare0/0. Sameboot6c80ec1a-e7ae-473f-b169-
d54f129615d1 at15:06:10UTC uptime10h26, CPUs0-3, taint12288 O/E unchanged.
UART closed. No JTAG/rawPSMMIO, reboot, newPL/modulebuild, commit/push.
No physical action pending. Diagnostic ran and restored stock; no persistent
R5 inference service. NEXT work is trusted-Linux firmware/model memory integration
and actual inference execution. Filter is NOT deployed. Full inference NOT yet
deployed, exclusive-owner enforcement deferred and unqualified. Prior failed
tag trials stay unchanged. Preserve all artifacts and VBAR warnings below.

CURRENT2026-10-17 R5 OBSERVED-PROFILE FILTER FIXED LOCALLY; SOURCE GATE CLOSED:
Read docs/research/2026-10-17-typed200-amp-r5-profile-filter.md and its validation
JSON FIRST. New build/v2/typed200-amp-r5-profile-filter-v1; all10910 prior files
plus52new files sealed. No prior sources/artifacts changed. JTAG stayed stopped.
Separate rtl/v2/candidates/typed200_amp_r5_profile/typed200_r5_profile_filter.sv
SHA200fd7866c19d432d85d1b264c27a64229f7c48e03a7c2b2f2b1f4de7ad36242.
Accepts only USER2000/2800, PROT1, MID0 and old bounded transaction shape.
ENABLE_R5=0 and SOURCE_PATH_QUALIFIED=0 by default; enable alone denies all.
Entire transport engine after policy function unchanged. No inferred ID mask.

CRITICAL NEW PRIMARY-SOURCE FINDING: UG1085 table16-13/page411 and page63
document RPU0 MID0 shared with CCI-400 and SMMU TCU. XAPP1320 explicitly warns
of CCI/R5_0 isolation collision. Upper bits11/13 remain semantically unqualified.
Host witness proves identical signals cannot be distinguished by origin label.
Do NOT flip SOURCE_PATH_QUALIFIED merely because the R5 workload passes.
Next architecture audit must account for shared sources for actual endpoint,
protected region/coherency/trust policy or distinct R5 source topology. R5_1
would change current lockstep and needs separate boot/session/recovery review;
no live PS/coherency/register shortcut. Empty IOMMU groups are not proof.

PASS524288 USER/PROT combinations x4 gate configs;4407 AXI transactions;
262233 new workload-validator cases allowing varying/repeated IDs. Original
failed target-trial-v2 stays failed/unmodified. composition-check-v2 PASS:
64APU writes denied, actual4 marker values and observed metadata preserved,
9negative mutations blocked. Composition uses64 synthetic accepted-profile
fixture writes for old ELF precondition; NOT a bootable filtered diagnostic.
Need separate zero-count R5 self-test and negative APU observation, no bypass.
No new synthesis/route/package/deployment/R5 execution occurred this milestone.

Read-only pinned SSH health14:59:43UTC same boot6c80ec1a-e7ae-473f-b169-
d54f129615d1, uptime37181sec, CPUs0-3online, stockk26 operating, moduleabsent,
remoteprocempty, PL0 rate99999999 enable/prepare0/0, taint12288 O/E unchanged.
Correct snap.kria-dashboard.service.service active15:00:20UTC. Initial wrong
dashboard alias query retained; no service stop/start. UART remained closed.
No rawPS/RPU MMIO, JTAG process, powercycle, commit/push. No intervention pending.
Full inference NOT READY; deployment authorization persists once gates pass.

CURRENT2026-10-17 LINUX R5 PL MARKERS OBSERVED; FILTER ADMISSION STILL CLOSED:
Read docs/research/2026-10-17-typed200-amp-linux-tag-probe.md and its validation
JSON FIRST. This supersedes smoke-only status below. New root
build/v2/typed200-amp-linux-tag-probe-v1; separate firmware candidate.
JTAG/hw_server/XSDB stayed stopped; no raw PS/RPU MMIO, no PL rebuild.

Actual corrected R5 ran: PASS CPU trace, four exact PL markers, final68writes
zero errors. Kernel watchdog stopped R5, freed both TCM leases and extra Linux
PL clock reference. Target-trial-v2 service remains FAILED at full AW identity
constancy check: AWUSER2800,2000,2000,2800; AWID49,69,89,a9; PROT1; MID0.
ARUSER2000 PROT1 ID49. Do not overwrite/reclassify the failed trial or loosen
admission. Separate observation-review-v1 PASS verifies marker/counter evidence
and negative simulation: unchanged ENABLE_R5=1 filter rejects all five measured
R5 metadata cases because USER[15:10] is nonzero. Upper bits11/13 need explicit
qualification. UG1085 p1091 only generally allows upper system attributes.
Next: separate source/upper-field qualification + negative filter integration;
full inference remains NOT READY. Prior deployment authorization persists.

Target-trial-v1 hit /run noexec before native APU helper execution; R5 never
loaded. Conservative recovery held PL. Separate reviewed-recovery-v2 proved
no access and restored stock, preserving original failed state. V2 stage uses
executable root-private /var/lib and prechecks noexec before PL changes.
V2 independent recovery PASS: stock k26-starter-kits/dashboard restored, module
absent, remoteproc empty, all30 runtime app-file hashes unchanged, Linux PL0
clock99999999Hz enable/prepare0. No raw register-equality claim.
Last health14:27UTC same boot6c80ec1a-e7ae-473f-b169-d54f129615d1 uptime9h47,
CPUs0-3online, taint12288 expected O/E only. UART closed14:31:18UTC; expected
Linux overlay-removal leak warnings retained. No powercycle needed or pending.
No JTAG processes; no commit/push. Preserve all old maps/candidates and old
VBAR startup warnings below. Host checks242 firmware,25/26/40 adapter,2214
policy,12-transaction diagnostic RTL replay; observation filter harness2194.



CURRENT2026-10-17 LINUX R5 SMOKE PASSED: read
docs/research/2026-10-17-typed200-amp-linux-r5-controller.md and its validation
JSON FIRST. This supersedes the earlier LIVE GATED smoke status below. User
asked for lease/failed-start fixes and authorized progress toward smoke deployment,
keeping JTAG stopped. User was available for fallback; NO powercycle was needed
or is pending. No hw_server/XSDB/JTAG connection or raw Linux PS/RPU MMIO.

New root build/v2/typed200-amp-linux-r5-controller-v1. Prior BOTH maps verified
10368files plus original anchor copied. New separate Linux misc module/session
engine tracks two ATCM leases15/17 independently, reconciles ambiguous request/
release, retains resources+module pin after failed stop, and never auto-re-wakes.
One mapping, full aligned64KiB write/readback, firmware blocking stop+OFF check,
5s requested kernel watchdog and root service ExecStopPost. PM suspend veto
while pinned. Existing lockstep mode preserved; no mode/TCM-config writes.
Host PASS10465 session trajectories +25blocked/26prepare/35modeled-live adapter
cases with sanitizers. Exact installed kernel headers build PASS.

prepare-trial-v1 hardware PASS: acquire both leases, stopped TCM load/readback,
watchdog cleanup without SSH stop, re-audit both unowned, normal module unload.
smoke-trial-v1 FAILED with R5 undefined ERROR1, recovered completely and unloaded.
Cause supported by correction: Cortex-R5 has NO VBAR; old smoke and other saved
startup candidates wrongly write it. AMD BSP VBAR code is ARMR52-conditional.
Unicorn allowed it, so old164-case PASS did not prove CPU compatibility. NEVER
execute preserved typed200_r5/start.S, typed200_mvp/start.S, or old probe startup
unchanged. Do not rebuild sealed old probe ELF/package; make separate corrected
candidates. New negative regression rejects original VBAR opcode explicitly.

Corrected firmware/typed200_amp_linux_r5_controller/smoke-v2.S built separately
as newroot/smoke-build-v1/sysone-r5-smoke.elf SHA256
65033cebee9df86b202f0b86206302eb639768bd389884f22be3c891eaf23b53.
PASS164 emulation +CP15 allowlist and old-image negative test. module-build-v7
contains corrected embedded image. Actual .ko SHA256
9edf6bd825660bb65d7774d57c94ce175bd5a6c4cfc35e448ae42289ea63aeba,
vermagic6.8.0-1036-xilinx. Native compiled on board, copied/hashed locally.

smoke-trial-v2 hardware PASS on current lockstep mode: fresh R5: PASS,
SCTLR00e50878 CPSR000001d3 MIDR411fc153. Kernel watchdog stopped R5 then released
both ATCM leases/mapping, re-audit RPU0/1FORCEDOFF, normal module unload. Unit
runtime6.183s is observation, NO WCET claim. No DDR/PL/IPI/inference access.
Post-health9h09 same boot6c80ec1a-e7ae-473f-b169-d54f129615d1, CPUs0-3online,
remoteproc empty, smoke module absent. Taint NOW12288 =O/E from unsigned external
module; persists until reboot, NO additional fault bits. Do not mislabel as taint0.
Stock Linux/boot/PL unchanged; no commit/push. UART capture closed, no processes
running for this work; S: mapping verified. Additive user build files retained.

smoke-replay-v1 is a NEW UNEXECUTED hardened plan: exact .ko copied+hashed into
fresh root-private /run stage before insmod, addressing check/load race from
trusted user build paths used by earlier runs. Script/service/hash/recovery are
reviewable. Re-inventory and arm UART before replay, no automatic repeated runs.
Generic firmware debugfs IOCTL still forbidden; kernel's getter/debugfs fixes
were NOT installed, narrow module avoids both. Full inference deployment NOT
READY: separate corrected startup/tag probe, firmware/firewall/filter/output
composition, numerical/cycle/fault/drain/physical/target qualification remain.
Earlier authorization to deploy when the relevant gates pass remains valid.

CURRENT2026-10-17 LINUX R5 AUDIT: read
docs/research/2026-10-17-typed200-amp-linux-r5.md and its validation JSON FIRST.
User explicitly says continue Linux-compatible startup toward deployment and
KEEP JTAG STOPPED. No hw_server/XSDB/hardware connection, raw PS/RPU MMIO,
new target firmware/overlay/kernel installation or R5 execution was performed.
Previous CURRENT block below is historical context, not a request to powercycle.

New root build/v2/typed200-amp-linux-r5-v1 preserves prior seal BOTH maps
(10112+80) plus original anchor. Exact Ubuntu source6.8.0-1036.37 reconstructed
from checksum-verified archives, kernel-source-v3 PASS16 files. DSC signature
NOT verified. Actual installed vendor zynqmp_r5_remoteproc module copied/hash
checked/disassembled; this is OLD binding, not modern upstream R5FSS.
ATF advertised ec5dccc32 resolved full commit in stock-atf-abi-v1; source ABI
audit does not prove running firmware binary equivalence.

Separate firmware/typed200_amp_linux_r5 TCM-only smoke ELF build-v2 SHA256
dd9b3eb2d18006a15acd1d2806f02bc2a89781eb5a89fbd000087656a26b9bc5.
entry0, one private64KiBTCM, only RSC_TRACE, no DDR/PL/PSMMIO/IPI. PASS164
actual-ELF Cortex-R5 emulation cases; PASS226 actual vendor callbacks; PASS7
actual TCM lease/mapping scenarios. overlay-check-v1 local dry apply preserves
ALL properties of227oldnodes, adds3nodes+2symbols; NEVER applied on target.
Old DDR R5 diagnostic ELF/package MUST NOT rebuild; vendor low/high-vector
selection cannot directly start arbitrary DDR entry63f00000.

LIVE GATED: exact kernel getter reads mode from STATUS slot0 rather than1;
generic firmware debugfs IOCTL caller gives4words to helper writing7. DO NOT
use generic debugfs PM_IOCTL. Local kernel-fixes-v1 stages two-line correction,
6mode/error+buffer regressions, NO kernel/module built/installed. Not sufficient:
TCM partial request leaks lease before carveout registration, duplicate devm
mappings persist until unbind; prepare failure skips generic cleanup. Startup
NOACK/error cleanup lacks proven stopped ownership; subdevice-error stop return
ignored. Must implement/qualify corrected Linux interface with full lease/error
rollback and retained ownership on failed stop, actual powered-down entry/TCM
ECC/mode/PMU closure and independently armed board-local recovery BEFORE bind.
Driver probe mutates mode/TCM even auto_boot=false. No JTAG/MMIO shortcut.

post-audit-health-v2 PASS2 read-only SSH queries, same stable boot as below,
taint0, CPUs0-3online, remoteproc empty, stock active. v1 health succeeded but
xmutil listapps lacked root and exited1; failed attempt preserved, v2 corrected
read-only query with sudo. All earlier download/extraction failures retained.
No active build/debug/SSH/serial process; S: mapping verified. README remains
sealed and untouched by this audit. No commit/push. Full typed inference still
NOT READY; earlier authorization to deploy once gates pass persists.

CURRENT2026-10-17: read docs/research/2026-10-17-kr260-debug-coexistence.md and
its validation JSON FIRST. The latest user steering is to investigate recurring
outages while continuing toward authorized deployment. Strong leading cause:
low-level debug/register interaction with Linux CPU idle/power management.
AMD UG1137 documents this incompatibility; exact kernel enables all five listed
settings. Current UART captured blocked jbd2/sda2+cron and machine-check taintM
before the second user-confirmed restart. Exact triggering read remains UNPROVED.

Stopped local hw_server and performed NO more JTAG or direct MMIO. Captured
second boot on COM9 (existing FTDI channelB; earlier WMI check missed the port).
linux-diagnosis-v1 PASS6 commands; linux-stability-v1 PASS25 samples/360s; fresh
post-isolation-v1 PASS4 commands at4h32m uptime ON SAME BOOT
6c80ec1a-e7ae-473f-b169-d54f129615d1. Kernel taint0, A53s0-3 online, root USB
storage running, stock app/dfx-mgr/dashboard active. SSH endpoint192.168.0.239,
saved Ed25519 fingerprint unchanged. No pending request for another powercycle.
No active build/debug/SSH-monitor/serial-capture process. S: mapping preserved.

KEEP hw_server/XSDB/Vivado hardware connections CLOSED on stock power-managed
Ubuntu. UART COM9,115200 8N1,no flow control remains a safe separate channel.
Do NOT run amp_probe_rpu_inventory.py OR amp_probe_guarded_target.py unchanged:
both contain PS/RPU /dev/mem reads; their seals/offline tests are retained but
live admission is now BLOCKED by debug coexistence. Use amp_probe_saved_ssh.py
with Linux-only plans for logs/sysfs/files/manager checks. No debug gate bits
are proof; any future compatible power/debug setup needs its own exact audit,
UART capture and recovery before R5 entry. Do not deliberately recreate the
crash or replace boot/flash/kernel files merely to test the hypothesis.

New root build/v2/typed200-amp-rpu-recovery-v1 includes diagnosis.json, prior
anchor/maps, all retained failed attempts and SDK AIB snapshots. Typed-output
deployment remains NOT READY: R5 tags and safe startup, trusted firmware closure,
firewall/filter/output-memory composition and exact/physical/target qualification
remain open. No FPGA/R5 load, explicit PS writes, boot changes, commit or push.
Earlier pending-cycle/capture session descriptions below are HISTORICAL.

LATEST STEERING: user asks why outages repeat. Investigate Linux/debugger
interaction before further AMP target work. Read
docs/research/2026-10-16-typed200-amp-rpu-recovery.md. New root
build/v2/typed200-amp-rpu-recovery-v1 preserves prior seal+anchor. User confirmed
first powercycle; SSH authenticated and Linux-only inventory-v1 PASS4 commands:
stock active, A53 0-3 online, manager/dashboard active, remoteproc empty.
inventory-v3 combined command failed without usable output; retained. Subsequent
read-only JTAG still showed powered-down/reset R5s, then SSH/TCP became unreachable
again. No port22 endpoint in bounded local/24 scan. No images loaded or explicit
target power/clock/reset writes. Fresh DDR backup/live rollback NOT completed.

USB console IS ALREADY CONNECTED: broader PnP finds FTDI XFL14EBBE1U3 channel B
COM9. Earlier Win32_SerialPort check missed it.115200 8N1 no flow,DTR/RTS off.
UART log uart-boot-v1.txt receives current Linux jbd2/sda2 and cron blocked>122s,
kernel taint M (machine-check), preceding cause unknown. Old saved logs show
CPU2/systemd BPF/cache-flush cross-CPU waits and soft lockups. Strong hypothesis:
JTAG vs CPU-idle/PM interaction; AMD UG1137 explicitly warns of incompatibility
and exact saved kernel config enables CPU_IDLE/PM/SUSPEND/FREEZER/PERF_EVENTS.
This is NOT yet a proved root cause; current M taint/storage stall needs full logs.

Stopped verified local hw_server PID24808 to remove debugger polling; NO target
reset. DO NOT restart hw_server/JTAG/MMIO probes during UART-only isolation.
USER ACTION PENDING: second powercycle requested WITH console capture armed to
collect boot and test Linux-only stability. Console capture exec session28724
runs four minutes from approx23:36 America/Chicago; inspect session/log before
opening COM9 again. If completed start new uniquely named passive capture.
Prepared linux-diagnosis-plan-v1.json for saved-key SSH script
scripts/v2/amp_probe_saved_ssh.py; captures kernel logs/storage/network/idle,
NO /dev/mem or target settings changes. Credentials stay hidden/process memory.
SDK AIB audit finds timeout in void XPfw_AibEnable only prints; require explicit
ACK checking before any eventual RPU power-down. Details in new report.

The older USER ACTION PENDING/next inventory-v3 instructions below are historical.

Continue the authorized separate typed-output AMP candidate toward qualified
deployment. Read docs/research/2026-10-16-typed200-amp-rpu-diagnostic.md and its
validation JSON first, then the preceding target-probe/ownership reports below.
Do not rebuild the existing diagnostic package or R5 ELF. No commits/pushes.

New root: build/v2/typed200-amp-rpu-diagnostic-v1. Prior target-probe seal BOTH
maps verified (10007+81); original anchor copied and hashed before mutations.
New controller-check-v2 PASS72 offline recovery/policy fault cases. Separate
scripts/v2/amp_probe_guarded_target.py corrects clock-gate recovery, reuses the
hash-checked installed app, requires root-controlled systemd staging/ExecStopPost
and rechecks recovery. It is APU-only, has NOT run on target, and implements NO
RPU power/reset/load/release or DDR restoration. Original failed trial preserved.

Read-only JTAG confirms actual R5 power bits BOTH CLEAR (PMU state00ff008f),
R5 clock01000200 (core gate clear), reset13, global50, cfg4/4 (NCPUHALT low),
PL0=00010a00 and AFI=a00. No halt/reset/download/resume or PS writes issued.
SDK snapshots: RPU AMBA reset mask4, PGE mask10. PMU power-up calls ROM then
changes four AIBs; exact stock PMU/ROM/ownership/rollback remains unaudited.
Do NOT attempt reset-only startup of the powered-down cores. R5 tags unmeasured.

SSH initially reached authentication but no unattended credential was available.
User supplied password in current chat; use only hidden terminal/process memory,
never files/logs/handoff. Credentialed inventory-v1 FAILED during SSH handshake;
inventory-v2 FAILED waiting for banner. Neither reached a remote command or tested
the password. Native SSH also stalled after TCP; exact local process terminated.
USER ACTION PENDING: asked to power-cycle KR260 once and confirm boot. No JTAG
reset issued. After confirmation recheck saved host key at192.168.0.239 (DHCP may
change); next fresh read-only command is:
uv run --no-sync python scripts/v2/amp_probe_rpu_inventory.py --attempt inventory-v3
Preserve failed v1/v2 directories. Do not replace known_hosts or autoaccept keys.

Then obtain fresh Linux ownership/backups, qualify the NEW APU recovery controller
in a new attempt, and audit powered-down-to-halted RPU entry plus board-local
stopped/reset recovery before using existing ELF. Full ATF/PMU/R5/firewall/filter/
relocated-output/startup composition and exact/physical/target qualification
remain OPEN. Typed-output deployment NOT READY. No PL programming/R5 execution,
DDR/clock/reset/power/boot writes, commit or push in this continuation. README is
sealed by prior map; new issues recorded in report without altering that baseline.
No build jobs remain; existing hw_server may remain. S: mapping verified.

## Previous start section (2026-10-16, historical SSH availability)

Continue the separate typed-output AMP candidate toward qualified deployment.
The user explicitly authorized working toward deployment AND deploying once
readiness gates pass. Do not ask for that same authorization again. The present
candidate is NOT ready for typed inference; the completed deployment was only
a diagnostic probe, followed by verified stock restoration. This handoff update
performed no new board access: all board state below is last verified evidence.

Read in this order:
1. This start section and the latest state section immediately below it.
2. docs/research/2026-10-16-typed200-amp-target-probe.md and its CSV.
3. build/v2/typed200-amp-deployment-v1/target-milestone-v1/readiness.json
   and failed-attempt-ledger.json.
4. docs/research/2026-10-16-typed200-amp-ownership.md and its readiness/experiment
   records for the unfinished ATF/PMU/R5/firewall composition.
5. docs/research/2026-10-16-typed200-amp-target-probe-validation.json:
   verify BOTH hash maps and preserve the anchor itself before new mutations.
   It preserves 10,007 previous files/anchors and seals 81 new artifacts.

Immediate next work:
- Recheck existing processes and saved-key SSH before any target action. Last
  working endpoint: ubuntu@192.168.0.239. Saved Ed25519 SHA256 fingerprint:
  EGYkdZirFAYH1XOF2uPZYSzmLMOj7obcj/xAeHIW/Qc. DHCP can change; never replace
  known_hosts or autoaccept another key. Use available credentials securely;
  no password is recorded in these handoff files.
- Audit a NEW guarded RPU-only diagnostic setup/rollback candidate. Establish
  actual RPU power/reset/clock/mode and Linux ownership, set a private halted
  entry, and arm board-local recovery before release. Preserve A53/GEM/PLL/ADMA
  and live ATF OCM. The SDK AMBA reset mask is 0x4. Avoid opaque rst-processor:
  the reviewed SVF implementation writes OCM and a broad reset value. Do not
  assume every native helper has that same write set; audit the actual path.
- Existing R5 image (do NOT rebuild):
  build/v2/typed200-amp-deployment-v1/r5-probe-build-v1/r5_probe.elf
  SHA256 79ed1f7178027011252d3b31ae8b9a098c6db444843243f3cf7f0e2bc6944e12.
  It uses 0x63f00000..0x63f0ffff no-map DDR; save fresh contents before use and
  restore only after R5 is definitively stopped/reset. Result at 0x63f0f000;
  success status 0xd00d0001; four marker slots 4..7. Debug startup is not a
  qualified reset path or timing proof. R5 tags have NOT been measured yet.
- Existing reviewed diagnostic package (do NOT rebuild):
  build/v2/typed200-amp-deployment-v1/probe-package-v1/sysone-amp-origin-probe.
  The same app is already installed additively on the board. A future controller
  must hash-check and reuse it, not fail blindly on its existing directory.
  Physical artifact probe-physical-v2: +4.346 ns setup, +0.031 ns hold at 10 ns.
- Before another trial, implement a NEW controller with the reviewed clock-gate
  recovery semantics. Do not rerun amp_probe_target_trial.py unchanged: its
  complete-register recovery assertion rejected Linux clearing CLKACT when
  the probe consumer was removed. Preserve that failed service and separate
  successful recovery review. Do not force an unused clock on by raw PS write.
- Measure R5 AR/AW source metadata, then finish trusted ATF/PMU/R5 session
  activation, quiescent firewall installation, integrated pre-conversion source
  filtering, relocated hidden outputs and protected startup. Finally run exact
  numerical/output/counter/cycle/fault/drain regression, new physical checks,
  and target negative-access/stress qualification before inference deployment.

Timing contract: canonical LOCAL PL typed terminal by D AFTER admission,
conditional on protected uninterrupted clock/reset. Preserve Accepted, Clarify,
Abstain, Fault, Deadline and Invalid semantics. Do not claim Accepted-by-D,
SSH-delivery WCET, Linux ingress WCET, or 300 MHz from this diagnostic. Linux
on A53 may provide SSH/relay; it must not own the admitted FPGA transaction.

Operational constraints: separate candidates; preserve qualified 200 MHz RTL,
package/recovery/numerical baseline and ALL prior sealed evidence. Never apply
boot-only firewall writes to running Linux. One large native job at a time;
inspect and resume existing jobs rather than duplicate them. No new jobs were
running at last handoff; hw_server may remain on TCP3121, JTAG cable
XFL14EBBE1U3A. Preserve S: workspace alias and verify its mapping before use.
No commits/pushes, QSPI/security/fuse writes or automation recreation. Old
predecode overnight automation instructions are historical, not the active task.

Workspace uses PowerShell, uv run --no-sync python, AMD tools 2025.2 under
C:/AMDDesignTools/2025.2, and WSL Ubuntu-24.04. SSH helpers prepend auth-deps
from build/v2/typed200-amp-candidate-v1/auth-deps and build/v2/board-auth-tools.
No subagents unless the user or applicable instructions explicitly request them.

Everything below the latest state section is history. Older no-deploy or
recovery-pending statements do not override the latest authorization/evidence.

## Current: SSH recovered; diagnostic origin probe executed and stock restored (2026-10-16)

User power-cycled; saved-key SSH authentication works at 192.168.0.239.
Read docs/research/2026-10-16-typed200-amp-target-probe.md first and its CSV.
Latest seal: docs/research/2026-10-16-typed200-amp-target-probe-validation.json
PASS preserves10007 previous immutable files/anchors and seals81 new artifacts.
Use both preserved_sha256 and candidate_sha256 plus that anchor for next audit.
Deployment authorization remains active. Full typed-output MVP is NOT READY.
No R5 image executed, boot/flash/security/fuse writes, commits or pushes.

board-readiness-v4 PASS: six stock+qualified-app files and 64KiB no-map DDR
backup, clocks/PS state. Diagnostic probe-target-v1 actually loaded reviewed
100MHz probe via xmutil/dfx-mgr. APU exact lane/address/data/count tests PASS:
64 writes, zero errors, four affinity-pinned A53 cores. Source ARUSER80..83,
AWUSER8c..8f, PROT2. Capture is before USER loss. apu-tag-replay-v2 PASS2325
transactions including136 new measured/secure-bit mutation cases. R5 identity
still unmeasured. This is diagnostic deployment, NOT typed inference.

Original target service FAILED recovery raw-register equality: probe unload
cleared PL0 CLKACT bit24 through Linux clock driver. Stock reloaded correctly.
Separate probe-target-v1/recovery-reviewed-v1 PASS verifies EXACT delta01000000,
unchanged clock rate/parent/dividers/zero references, AFI0xa00, stock operating,
RPU reset13/global50, all six baseline app files and saved DDR unchanged.
Dashboard restarted+verified active. Do not force raw unreferenced clock on.
Diagnostic app remains installed additively; stock k26-starter-kits is active.
No native job running. Do not restart completed trials or overwrite failures.

New artifacts rooted build/v2/typed200-amp-deployment-v1/target-milestone-v1.
Read its readiness.json and failed-attempt-ledger.json. board-readiness-v3
failed because fpgautil absent; v4 uses installed manager. Tag replay-v1 failed
harness argument order; corrected v2 PASS, filter RTL unchanged.

Next: audit guarded RPU-only setup and local recovery before loading R5 ELF.
SDK reset AMBA mask is0x4, NOT0x10. Installed AMD SVF R5 reset helper writes
OCMffff0000 and broad LPD reset: exclude opaque rst-processor helpers on live
Linux unless exact writes audited. No old sole-R5 loader, A53/GEM reset,
PLL/ADMA changes, or boot-only firewall installation on live Linux. Need actual
power state, hardware-halted private entry, stopped/reset DDR restoration,
measured R5 tags, then full trusted closure/filter/startup/memory composition
and exact numerical/cycle/physical/target regression. Preserve frozen baselines.

Earlier Current sections below are historical and may state recovery pending.

## Historical: deployment authorized; origin-probe package ready, stock boot recovery required (2026-10-16)

Latest user explicitly: work toward deployment AND deploy. This supersedes old
no-deploy instructions, but does not waive readiness checks. NO candidate FPGA
or R5 image has been loaded. Qualified200MHz files/package/numerics remain intact.
The live board is currently not reachable over SSH after recovery reset attempts.

Read first:
- docs/research/2026-10-16-typed200-amp-deployment.md
- build/v2/typed200-amp-deployment-v1/deployment-readiness.json
- docs/research/2026-10-16-typed200-amp-deployment-validation.json (PASS:9844
  prior files unchanged;162 new immutable source/evidence artifacts sealed)
- build/v2/typed200-amp-deployment-v1/failed-attempt-ledger.json
Earlier Current sections below are historical.

New root build/v2/typed200-amp-deployment-v1. Started by verifying9844 previous
sealed/evidence files. Diagnostic-only RTL rtl/v2/candidates/typed200_amp_probe:
no encoder, permit, PL DDR master or external I/O. Records real AWUSER/PROT/ID;
read registers expose ARUSER/PROT/ID. probe-sim-v4 PASS2048 exact traces plus
stall/burst/reset checks. probe-physical-v2 routed+4.346ns setup/+0.031ns hold
at10.000ns; zero DRC/check_timing problems, CDC safely timed, full route, only
two exact vendor-reset synchronizer false paths. +0.500ns placement gate passed.
Physical-review.json admits PROBE bitstream only. Bitstream/package completed:
probe-package-v1/sysone-amp-origin-probe. Do not rebuild completed attempts.
No package has been uploaded. v1 physical probe lacks read-tag visibility and
is superseded. No new claim about200MHz inference timing or cycles.

R5 diagnostic ELF in r5-probe-build-v1 uses no-map DDR63f00000..63f0ffff (must
save/restore first), not TCM or live ATF OCM. IRQ masked, MPU/cache reset checks,
four source markers, explicit result status. NOT reset-startup/WCET qualified;
RPU-only setup/restore still needs review/testing, no R5 execution yet.

Authenticated board-preflight-v1 succeeded at192.168.0.239, saved host key
EGYkdZirFAYH1XOF2uPZYSzmLMOj7obcj/xAeHIW/Qc. Stock k26-starter-kits overlay
active, no System One inference running, allA53 online, no remoteproc. Later
both Paramiko and native SSH failed pre-auth/KEX/banner. board-readiness-v1/v2
failed BEFORE any commands or backups. No new recovery-app/DDR backup captured.

Agent then issued JTAG rst-system-start and rst-por under new deployment/recovery
authorization. Both returned issued; neither established normal cold boot/SSH.
QSPI mode remains2, no alternate boot. UART1 was reset-blocked after warm reset.
Bounded local/24 port22 scan found none. Brief A53#0 stop/read/resume completed:
PCfffEA16c (stock ATF warm-entry code), PSTATE3cd, explicit con logged. No code
loaded, no flash/security/fuse/bootfile writes. Do not claim actual physical POR
or infer the failure cause. Avoid repeated resets. Current JTAG cable remains
XFL14EBBE1U3A. Local hw_server may run. No native job remains running.

USER ACTION PENDING: async request to unplug/reconnect KR260 power once because
JTAG resets did not restore stock boot. Continue when user confirms, verify saved
host key again before authentication (DHCP may change address). Do not replace
known_hosts. No new board-dependent work until actual recovery is established.

Next: fresh board-readiness-vN via scripts/v2/amp_probe_board_preflight.py; obtain
stock+qualified-app file backups, reserved-DDR snapshot, live clocks/AFI/reset and
actual dashboard service (PID lookup now dynamic). Complete reviewed bounded
probe-load/rollback controller before loading diagnostic package; retain PL0
rate and require <=100MHz,128bit HPM0 AFI and exact ABI/lane tests. Then qualify
RPU-only setup/source tags, restore stock+DDR, and bind real metadata to filter.
Never run old sole-R5 startup: it resets A53/GEM resources. No PLL or ADMA changes
for diagnostic. No loaded probe may be reported as typed-output MVP deployment.
Full ATF/PMU/R5 closure, safe firewall transitions, relocated output, protected
startup, exact regression and new physical evidence still required for MVP.
Preserve all previous sealed files, failed attempts and S: alias; no commits,
pushes or automation recreation.


## Historical: AMP protection, native firmware and private mailbox milestone (2026-10-16)

LATEST continuation: continue the authorized separate AMP candidate toward readiness.
DEPLOYMENT STILL BLOCKED by composition and qualification gates. Earlier Current
sections below are historical. No target programming/halt/reset/reboot or storage
write by this agent. User power cycle restored SSH at192.168.0.239; saved key
verified and authenticated read-only inventory/boot backup captured. No active
native build remains. Local hw_server may remain; preserve S: alias.

Read first:
- docs/research/2026-10-16-typed200-amp-ownership.md
- docs/research/2026-10-16-typed200-amp-ownership-readiness.json
- docs/research/2026-10-16-typed200-amp-ownership-experiments.csv
- docs/research/2026-10-16-typed200-amp-ownership-validation.json (PASS: all8312
  prior sealed files unchanged;1530 new immutable source/evidence files sealed)
- build/v2/typed200-amp-ownership-v1/failed-attempt-ledger.json (post-seal notes)

Work root build/v2/typed200-amp-ownership-v1. Do not restart completed attempts.
Newest PMU: pmu-staged-v6 + pmu-image-v3; 63 units, SHA256
6f6288ded7e79677d52d697d780dcdd0ba8e8b5c866b6ebae98c1932cbb6cc08.
Native image-v2 is REJECTED: inherited idle sleep could lose a deferred close
wakeup. V3 polls instead; power cost unmeasured. New R5-only custom IPI lease
stages a request and closes PMU dispatch at the main-loop boundary with IRQ
mask preserved. Session-bound status ACK only after closure. 1023 unauthorized
sources +160 malformed-field mutations PASS. All-module guard regression PASS.
ATF remains atf-staged-v3; actual PM/raw-IPI wrappers and retained trusted commit
build PASS. ATF/R5 activation still unjoined; PMU ACK alone must never admit.

New mailbox-v1 PASS: 5120 request-bit mutations, nine matched traces against
actual frozen service/driver/head, R5 object. Private R5 service state; finite
160-word untrusted snapshot, separate 32-word R5-write/APU-read result. One-shot
session, no ingress reads after submission, no cancellation/reuse. Captured word
vector defines request; seqlock recheck does NOT prove atomic capture. Software
trace matching is NOT FPGA cycle equivalence or WCET. Six outcomes unchanged.

protection-plan-v4 remains boot-only,774writes; NEVER apply to live Linux.
Host-v5 PASS plus firewall-v2 encoded oracle:253952FPD +20480OCM +1642496XPPU
cases with deliberate permission/parity mutations. Actual source/security tags,
peripheral TZ configuration, enable-time master quiescence still unqualified.

New ps-profile-v4 generates SOM+carrier PS outputs with GEM0 SGMII and GEM1/MDIO;
no synthesis/place/bitstream/XSA/package. Generated nominal PL0=199.998001MHz,
PL1=99.999001MHz,R5=533.328003MHz, unlike stock live RPLL. native-audit-v2
passes ELF/source/critical PS checks but records18derived MIO direction/drive/
slew differences (electrical compatibility OPEN). Audit-v1 failed strict full
property equality; do not suppress differences or claim full match.

Next: compose trusted ATF closure+PMU ACK+R5 startup; establish trusted initial
state and exact image identities. Define safe pre-Linux/final-lease firewall
transitions; integrate requester filter before USER loss for CSR AND permit;
new hidden-output address62200000 in separate RTL/R5 composition, matched exact
output/counter/cycle/error/drain regression. Actual source tag binding and new
physical setup/hold/DRC/CDC/exceptions at unchanged5/10ns constraints. Build
Linux-compatible startup and finite R5 service with correct mappings/clock
parents; prepare permit-low volatile qualification and recovery. No old sole-R5
boot profile/certificate reuse, no gate bits substituted for proof. Local PL
terminal-by-D after admission is conditional; Accepted-by-D and SSH latency
remain unproved. Preserve qualified200MHz sources/package/recovery/numerics,
all prior seals, failed attempts; no commits/pushes/automation recreation.


## Historical: SSH recovered; native AMP PMU and ATF guards built (2026-10-16)

Continue the authorized separate memory/clock/reset ownership candidate until
readiness gates pass. NOT READY; no deployment, target write, reset or programming.
User physically power-cycled the KR260; SSH recovered at 192.168.0.239 with saved
host-key match. Authenticated read-only inventory confirms KR260 revB, Ubuntu
kernel 6.8.0-1036-xilinx, GEM0 eth1, sysone no-map 60000000..6fffffff and PMU
7ff00000..7fffffff. Prior boot shows CPU2 soft lockups; not a proved outage cause.
UART control 0x114 has RX enabled (corrects earlier interpretation).

New work: build/v2/typed200-amp-ownership-v1. Initial preservation-before.json
verifies 8,312 prior sealed files. Final verification/seal PENDING while work runs.
Read native receipts: pmu-image-v1/receipt.json, atf-staged-v3/receipt.json,
host-v5/receipt.json, protection-plan-v4/plan.json. Completed attempts must not
be restarted. PMU native image: 62 units, prints disabled, commit retained;
ATF 2025.2 pinned 894ecd0737173617c91748dfbcfa1deca7971439 builds natively.
Both guard activation hooks are NOT composed into a trusted boot handshake.
Stock boot A/B read-only backups are identical SHA256
6b8bd7b57656e2ed80b51687bb25e2cc0eacb623f628480ae3ecaa9a2abb8216.
Stock FSBL/PMU2022.1, ATF2.6 ec5dccc32, U-Boot2022.01; do not replace casually.

Candidate sources firmware/typed200_amp_ownership and new scripts/v2 AMP helpers.
Host-v5: 921600 PM API cases, 860160 DDR oracle cases, 775 observable fault
injections PASS; native R5/PMU objects PASS. PMU bridge all-module IPI/event/
scheduler guard and IRQ-preserving main-loop commit PASS. ATF PM + raw IPI
wrappers close direct RPU/TCM IOCTL bypass; 65536 FIDs +9216 IPI cases PASS.
Next strengthen FPD/XPPU semantic tests, audit native linked guards, implement
trusted serialized activation/ACK, Linux-compatible boot/PS startup and bounded
R5 mailbox. Full protection plan is boot-only with all affected masters quiescent;
NEVER apply its 774 writes to live Linux. Caller-set gate bits are not proof.

New hidden output allocation 62200000 requires new RTL/R5 pointer composition
and exact-output/cycle regression; parent 62101000 remains frozen. Need requester
filter integration before USER loss, actual R5/HP0 source/security binding, timing/
DRC/CDC/exceptions, and target negative-access qualification. Existing sole-R5
PS configuration disables Ethernet; existing 533328000 Hz R5 timing certificate
is incompatible with observed stock RPLL. Do not reuse either for AMP. No new
bitstream/package, board action, commit/push or automation recreation. Local
terminal-by-D is conditional on uninterrupted protected guard clock/reset;
Accepted-by-D and SSH-delivery timing remain unproved. No native build running;
local hw_server may remain active. Preserve S: workspace alias.


## Historical: separate AMP access-filter candidate verified; JTAG connected (2026-10-16)

Latest user confirms Ethernet connected to router, board IP unknown. JTAG is
now available; proceeding with read-only inventory and separate local AMP
candidate. NO target halt/reset/program/reboot/deployment or persistent write.
No commits/pushes; automation remains PAUSED. Qualified 200 MHz baseline and
all prior sealed evidence preserved. Prior feasibility section below is historical.

Read first:
- docs/research/2026-10-16-typed200-amp-candidate.md
- docs/research/2026-10-16-typed200-amp-candidate-readiness.json
- docs/research/2026-10-16-typed200-amp-candidate-validation.json (new anchor)
- build/v2/typed200-amp-candidate-v1/preservation-before.json

New separate RTL: rtl/v2/candidates/typed200_amp/control/typed200_requester_filter.sv.
Default deny-all; optional secure RPU0 32-bit single-beat CSR+permit access.
Full AXI before USER/PROT metadata loss; independent AW/W capture, complete
declared rejected bursts, sticky faults, no timeout cancellation. NOT integrated.
2,189 simulation transactions PASS including all1024 low source IDs read/write.
New induction proofs PASS for ENABLE_R5=1 and0, length2: access restrictions,
AW/W/AR stalled stability, exact rejected burst counts, sticky fault and local
response properties. First sampled reset assumed; source provenance, downstream
compliance, liveness, physical isolation/timing are NOT established. Formal v1
frontend failure preserved; v2 fixed lowering, no assertions weakened. New
scripts scripts/v2/{check,prove}_typed200_amp_filter.py. Do not rerun completed
attempts; use a fresh numbered directory for changed work. No Vivado build yet.

JTAG cable XFL14EBBE1U3A enumerates xck26/arm_dap; XSDB A53#2 Running, R5s
No Power, A53#3 debug APB error; no cause/fault inferred. Enumeration is NOT
tested recovery. Local hw_server TCP3121 launched; PID/log receipt in candidate.
COM9 passive115200 and CR-only probe silent. Historical192.168.0.239 replies
Ubuntu SSH banner then stalls at key exchange; no saved host-key match, password
authentication or remote commands. Only port22 found in bounded local subnet
scan. Native stuck SSH client terminated locally. PC192.168.0.152/24. Actual
board kernel/DT/ATF/PMU/PS/GEM still unpinned. Never authenticate to an unverified
new address or force target reset to obtain inventory. Candidate inventory helper
uses saved known_hosts and fixed read-only commands; candidate cffi fixes Python
ABI mismatch without modifying frozen helpers. No credential saved.

Next: authenticated live platform inventory/recovery; Linux-compatible PS
topology and actual R5 USER/PROT review; integrate filter without bypass; enforce
DDR/TCM/DMA and selective PMU/secure/MMIO clock/reset ownership; separate bounded
R5 one-shot mailbox/service; compose matched numerical/control regressions and
new physical STA/DRC/CDC/exception evidence; then supervised readiness review.
Existing sole-R5 PS init disables Ethernet and blanket PMU seal conflicts with
Linux; DO NOT deploy that image for AMP or remove checks/reuse its certificate.
Local canonical typed terminal byD after admission is the intended conditional
guarantee. Accepted-byD, SSH delivery and timeout buffer reuse remain unproved.
No native build or remote command remains running; only local hw_server daemon.
Preserve S: alias; do not recreate old experiments or automation.

## Historical: A53 Linux/SSH + R5 ownership feasibility reviewed (2026-10-16)

Latest user asks whether Linux/SSH can remain on one A53 while R5 exclusively
owns FPGA inference with typed-output timing; investigate, preserve baseline,
DO NOT DEPLOY. Investigation COMPLETE; no AMP firmware/RTL candidate implemented.
No board contact, native FPGA/toolchain build, proof/simulation restart, image,
programming, deployment, reboot, commit or push. Automation remains PAUSED.

Read next:
- docs/research/2026-10-16-typed200-amp-feasibility.md
- docs/research/2026-10-16-typed200-amp-experiment-plan.md
- docs/research/2026-10-16-typed200-amp-ownership-matrix.csv
- docs/research/2026-10-16-typed200-amp-policy-draft.json (NONDEPLOYABLE)
- build/v2/typed200-amp-feasibility-v1/source-audit.json
Final preservation anchor:
`docs/research/2026-10-16-typed200-amp-feasibility-validation.json`.
All8204 previously sealed repository files verified unchanged before/after.
Prior K26 boot-chain anchor/evidence is preserved and remains NOT target-ready.

Finding: coexistence is architecturally feasible for the conditional LOCAL PL
terminal deadline after admission. Unbounded DDR/R5 delay can yield Deadline
without extending D, given uninterrupted guard clock/reset and protected state.
This does NOT guarantee Accepted-by-D, pre-admission/Linux queue latency, SSH
result delivery, or SSH recovery through every shared-system fault. Exact
Accepted inference needs encoder/drain/hidden-copy/head/proposal service bounds.
Deadline quarantines; does not cancel AXI or permit early buffer reuse.

Current v5 explicitly requires all A53/GEM resets and one preloaded request.
Existing PMU seal denies every normal IPI; not a Linux-compatible selective
resource policy. Actual HWH control SmartConnect has16-bit AR/AWUSER at full
AXI input, ZERO USER at both Lite outputs; actual wrapper has no origin check.
Need requester filtering BEFORE conversion for CSR AND permit/config/ACK.
Actual standalone HWH disables ENET0..3. New AMP cold boot needs a real Linux/
network/boot-device PS configuration; loading a PL-only overlay is distinct
from running this standalone PS initialization. No cause of prior outage inferred.

Audit confirms final gate logic matches existing proved source modulo comments/
whitespace. Existing RTL proof is NOT a new physical/AMP isolation proof.
Pinned inspected primary Linux sources at AMD linux-xlnx commit
31626ef92ff11f9d3dee01926720572666fcc65a (2025.2 reference; live board kernel UNKNOWN).
Actual remoteproc can stop/release R5/TCM; FPGA manager can reload PL; no-map is
allocation, not a firewall. AMD XAPP1353 documents preserving MasterID/AxUSER
and PL protection; reference archive attempt returned HTML, no VHDL audit.
All source hashes/lines, snapshots and failed attempts retained in new build dir.

Recommendation: separate ONE-SHOT AMP candidate first. One A53 Linux/SSH;
R5_0 trusted startup/service/head; hardware-protected inference/control and
platform policy; bounded ingress/private snapshot; independent result mailbox.
Do NOT simply remove all-A53/GEM reset checks or reuse old certificates.
Ranked plan: actual PS/kernel/network inventory; explicit ownership/PM policy;
requester filter; memory/TCM/DMA enforcement; R5/mailbox adaptation; composed
proof + new STA/DRC/CDC; then supervised passive-capture AMP qualification.
Accepted rate/interference bounds follow; external network delivery remains
outside the frozen deadline contract. Cooperative Linux bring-up must be
labelled diagnostic/Linux-trusted, not enforced exclusive ownership.

No current deployment readiness. Independent JTAG/serial recovery remains
unverified (user previously had SSH only); dedicated boot/management policy
still needs a verified launch route. AMP keeps management configured after
startup but does not resolve fixed-QSPI/cold-POR provisioning by itself.
All policy-draft enforcement/address/allowlist fields deliberately unverified.
No native job is running or needs resuming. Preserve the existing S: repo alias
and all completed experiments; do not recreate automation or old jobs.

## Prior local milestone: K26 boot chain built; physical launch gates open (2026-10-16)

Latest user authorized dedicated FSBL/PMU/configuration builds and relay memory
validation, preserving the baseline and working toward deployment only after
readiness passes. All work is local; no board contact, deployment, reboot,
persistent-media/security write, commit or push. Automation remains PAUSED.

Read next:
- docs/research/2026-10-16-typed200-k26-boot-chain.md
- docs/research/2026-10-16-typed200-target-qualification-profile-v3.json
- build/v2/typed200-k26-boot-chain-v1/preparation-assessment-v3.json
- docs/research/2026-10-16-typed200-k26-boot-chain-validation.json
  (new final preservation anchor; verify it exists and all hashes before resuming)

New sources firmware/typed200_k26_boot; generated candidate
build/v2/typed200-k26-boot-chain-v1. Actual FSBL/PMU ELFs/maps, effective macros,
linked 1744-byte PM config, final disassemblies and local typed bitstream built.
Read-only XSA PS init/HWH exactly match frozen typed hardware metadata. Native
builds use actual cwd S: (existing repository alias; DO NOT remap), AMD 2025.2
Vivado empyro with matching Vitis embeddedsw, candidate-local checksum-verified
Arm GNU13.3.rel1. Vitis platform RPC/path/missing-compiler failures retained.
Do not restart failed platform generation, old RTL experiments or automation.

Final FSBL hook validates cold-POR, A53_0 EL3/64, exact DDR relay entry,
permit-low/drained ABI, RPU power/reset/AMBA and CSU idle. Waits PMU common
completion, then fresh-session one-way seal. PMU commits only after active
scheduler callbacks return, masks interrupts for commit/ACK, uses volatile ISR/
main state under LTO; rejects ordinary IPIs/events/callbacks afterward. K26 EM/
90C thermal shutdown remains active. Trusted boot/debug scope, NOT adversarial
hardware isolation; startup vendor power-up poll unbounded before admission.

479 policy cases + transition checks PASS; actual PMU C integration PASS;
actual FSBL hook success +23 fault cases PASS (ASM/MMIO/SDK mocked);
474 existing typed capture/trace/PMU/MVP/qualification tests PASS.
Bitstream export ONLY from frozen routed DCP: unchanged5/10ns clocks,
+.048ns setup/+.011ns hold, zero DRC errors. No physical implementation edits.
Final local layout image image-layout-v2/BOOT.bin SHA256
c93796b59f58f41e0f34d8492e6e4821037a3fe9e243dfb9d36bd9540c4c559b,
41996956B; independent actual-header/checksum/payload/range audit PASS.
All artifact roles now present; local static reviews do not authorize hardware.
The relay [10000000,10100000) allocation is statically validated for this exact
image. No claim of measured target access permissions or hardware reservation.
Retain image v1 and initial binary/sealing snapshots as superseded attempts.

DEPLOYMENT NOT READY. User says SSH ONLY now; will arrange JTAG at home.
No independent recovery is verified. KR260 preset QSPI primary boot means an SD
BOOT.bin alone does not launch this dedicated chain. AMD volatile SD/JTAG mode
override uses system reset, rejected by frozen cold-POR predicates. Establish
and review a real cold-POR debug interception/launch route on actual hardware;
do NOT clear reset history, relax predicates, chain from Linux/U-Boot, write
QSPI or infer physical readiness. Physical power/permissions/debug checks remain
open; current profile has no target run receipts. Need passive completion
observer and measured bounds before clean timing/WCET claims. Debug snapshots
remain diagnostic. No claim of 300MHz or target-qualified typed MVP.

Next: verify preservation anchor; await connected independent recovery and
identify exact target/cold-POR interception before any target action. Then stage
functional diagnostics under the qualification procedure, with fresh sessions.
Current local image uses [101,102], pool0/count1,budget1: Deadline-if-admitted
fixture, NOT successful classification. No new native build needs resuming.

## Completed: boot ownership review, qualification plan and local DDR relay (2026-10-16)

Latest user authorization: review FSBL/PMU/CSU/debug ownership, prepare exact
target qualification, preserve baseline and progress toward deployment once
prerequisites ready. Review/procedure COMPLETE; also implemented/tested a separate
DDR relay to address the discovered FSBL/OCM overlap. Deployment remains NOT
READY. No target contact/execution, FPGA build/bitstream, boot image/package,
board programming/reboot, QSPI/eFuse/security lock write, commit or push.
Overnight automation remains PAUSED; no old jobs/reports restarted/overwritten.

Read, in order:
- docs/research/2026-10-16-typed200-boot-ownership-review.md
- docs/research/2026-10-16-typed200-target-qualification-procedure.md
- docs/research/2026-10-16-typed200-ddr-relay-preparation.md (follow-up supersedes
  earlier statement that no relay exists and changes producer input to DDR)
- docs/research/2026-10-16-typed200-target-qualification-profile-v2.json

FINAL current preservation anchor:
`docs/research/2026-10-16-typed200-boot-preparation-validation.json`.
Prior review seal `2026-10-16-typed200-boot-ownership-validation.json` preserved.
All prior sources/package/recovery/numerical/route/MVP/review evidence verified
unchanged. Do not edit mapped files; handoffs remain editable.

Concrete review findings: both frozen A53 LOAD segments overlap installed FSBL
reserved OCM [fffc0000,fffe9e00); ordinary direct application load prohibited.
Actual dedicated FSBL/PMU binaries/macros/config missing. PMU has wake/reset/
clock/FPGA/CSU-DMA paths; source defaults are not the target policy. Preserve
K26 EM/overtemperature/board protection. Generated protection-lock function has
no lock writes; no hostile-master isolation claim. CSU must be drained AND
prevented from starting new work. Debug snapshots/breakpoints are diagnostic;
no reviewed passive completion marker currently exists for clean timing runs.
Ethernet/SSH WILL be intentionally lost when GEM/A53 are held reset in this
profile; independent serial/debug recovery is prerequisite, not yet demonstrated.
No assertion about the cause of the user's earlier board outage.

Review evidence `build/v2/typed200-boot-ownership-review-v1`:24 pinned installed
AMD primary files; source-default macro examples explicitly stub/nondeployable;
actual frozen C20-rule/131-bit table exported; both OCM overlaps detected from
actual ELF. Offline artifact/review completeness gate added with stale/foreign/
diagnostic evidence rejection.510 tests PASS; never claims hardware authority,
provenance, continuous ownership or WCET from metadata.

Separate relay `firmware/typed200_boot_relay`, build
`build/v2/typed200-boot-relay-v1/relay.elf`, SHA
8dd7e84b00637220bf7d3e488c6c57c73cb24d6cf5764eef536c3e44aa7f08b5.
Entry10000000, RX35548B; RW/NOLOAD16KiB stack100c0000; proposed DDR reservation
[10000000,10100000) NOT yet proven against actual FSBL/scratch/partition maps.
Producer448B input100f0000, status100f1000. Relay installs unchanged A53 input
fffee000 only AFTER final same-core FSBL exit; no returning/resuming FSBL.
Checks cold POR/peer resets/permit/typed idle/CSU idle/PCAP/input identity,
validates all OCM ranges/overlaps before copying, byte-verifies frozen A53 payload
and zero stack/input, DSB/IC IALLU/ISB then branches to frozen A53fffc0000.
No PS clock/reset/security writes. Status2 means copy/transfer issued only.
Actual relay C UBSan host tests PASS70 single-bit precondition faults,
786432 range checks, malformed/warm/permit/corrupt-copy rejection. Cross-linked
ELF no W+X/unresolved or linker warnings; privileged instructions NOT executed.
Original v5 R5/A53 payload/numerics/cycles unchanged; no target/WCET claim.

Current profile-v2 offline gate still FALSE with SEVEN missing artifact roles:
FSBL, PMU, actual FSBL macros, actual PMU macros, PM config object, typed bitstream,
and volatile boot recipe. All real preparation/target acceptance receipts open.
NEXT LOCAL: build/audit dedicated K26 FSBL/PMU/BSP/config, verify complete memory/
scratch map admits relay reservation and final handoff peer/cache conditions;
close ordinary PMU mutation/CSU/permissions policy and recovery/passive-observer
requirements. Then prepare exact recoverable volatile target images and execute
staged qualification. User's conditional deployment intent persists; do not ask
again merely to do authorized reversible preparation, and do not touch the board
before readiness/recovery conditions are actually met. No deployment underway.

## Completed locally: typed-output ARM ownership MVP (2026-10-16)

Latest user request COMPLETE within the authorized no-deployment boundary.
Separate candidate: `firmware/typed200_mvp`; final local build/test
`build/v2/typed200-mvp-host-v5`; native ELF/source/preservation review
`build/v2/typed200-mvp-review-v1`. No ARM target execution, bitstream, boot image,
package, board access/programming/deployment/reboot, RTL edit, Vivado build,
commit or push. Overnight automation remains PAUSED, not recreated/restarted.

Implemented A53_0 EL3 OCM startup/handoff and R5_0 reset-entry supervisor with
split TCM/ECC, low vectors/banked stacks/VFP, narrower MPU permissions, owned
full-rate PMU initialization and the frozen typed service/head. Selected profile
is COLD BOOT, R5_0 sole active application core, one preloaded request then
terminal park/permit low. All A53 cores self/peer-reset, R5_1 reset/halted,
competing DMA peripherals held reset, DPDMA clock gated. Preserve encoder AFI
and PL reset/clock. R5 independently observes all A53 resets and20 ownership/
clock/GPIO rules before any admission and before each service poll. Sticky
fault attempts permit-low/park; no automatic healing. PMU/CSU/trusted producer/
debug/other PL masters remain explicit trusted-quiescent prerequisites.
This is NOT malicious-master isolation, a live A53/Linux client, or WCET.

Final local evidence PASS: actual portable ownership/supervisor C under ASan/
UBSan; all131 monitored bit inversions sticky rejected,786432 segment checks,
DMA done/error/timeout and reset/config faults. Frozen head647 fixtures reproduce
all51760 golden output bytes exactly. Frozen service/driver/PMU regressions pass;
467 Python tests pass including new parked-MVP snapshot consistency gate.
Actual A53 handoff C executed with mapped mock TCM/OCM plus UBSan verifies load/
NOLOAD/config ordering, payload readback, R5 release-before-self-reset, denied
self-reset and malformed/session-mismatched/warm boot failures. Neither host
model executes privileged ARM instructions. Actual R5/A53 ELFs audited: correct
entries0/0xfffc0000, no unresolved or W+X load segments, exact TCM/OCM fit and
shared/config/evidence symbols. Four documented intentional PROGBITS->NOLOAD
NOBITS linker warnings retained; no warning suppression. Failed harness attempts
v1-v3 retained; superseded passing v4 sources recovered exactly against hashes.

Final report `docs/research/2026-10-16-typed200-arm-ownership-mvp.md`.
FINAL preservation anchor:
`docs/research/2026-10-16-typed200-arm-ownership-mvp-validation.json`.
All2811 prior files, including prior route seal, verified unchanged; sources,
ELFs, snapshots, tests, failed attempts and report hashes bound. DO NOT edit
mapped files or rerun completed directories. Both handoffs remain editable.

MVP final mailbox boot_status=2, permit0; frozen legacy decoder expects status1.
Use separate `sysone.v2.typed200_mvp.assess_mvp` with final shared/boot/owner/
permit plus pre-ACK trace/PMU evidence. It checks consistency only, never target
provenance/continuous hardware exclusion/frequency/WCET. Configuration-derived
R5 nominal533328000Hz and PL0199998000Hz follow declared33.333MHz reference;
qualified board's measured199999998Hz is separate evidence, not calibration for
this candidate. Extra ownership polls change ARM cost; no unchanged ARM-cycle
claim. Software loop limits do not bound a stuck MMIO or stopped clock.

NEXT: review exact trusted FSBL/PMU/CSU/debug/power/permission profile and later
obtain separately authorized recoverable target qualification: ARM startup/ECC/
MPU/reset/master captures, fault campaign, clock calibration, target head goldens,
phase captures and justified DDR/MMIO/ARM service bounds. No target gate is
closed by local evidence. No new deployment/build/automation is authorized or
pending from this completed local task; do not infer permission to deploy.
The routed carry-save typed design remains unqualified on hardware; the original
qualified 200MHz baseline/package/recovery/numerics are untouched.

## Completed: timing-only carry-save routing (2026-10-16)

Latest user request COMPLETE. Reviewed CSA checkpoint routed in a new standalone
directory with unchanged constraints. Final 200 MHz STA **+0.048 ns setup /
+0.011 ns hold**, all123430 routable nets fully routed, zero unrouted/overlap/
routing-error nets. All12 check-timing categories zero; CDC safely timed.
No bitstream/package, hardware deployment/programming/reboot, commit or push.
Qualified baseline sources/package/recovery/numerical and every prior seal intact.
Overnight heartbeat remains PAUSED; no automation restart. No native job remains.

Input: `build/v2/typed200-row-range-csa-physical-v1/place/placed.dcp`, SHA256
c5ebe28f029ba9490fb146bac93a9139fbee403c5b78a94ed9a76fbbf7f2eb5e.
The reviewed +0.506 ns placed setup cleared unchanged +0.500 ns gate by6 ps.
Exact copy opened standalone in `build/v2/typed200-row-range-csa-route-v1/input`;
sealed project never opened/saved. Default phys_opt_design then route_design,
max4 threads, no retiming/clock/source edits. New final output route-v1/routed.dcp.

Exact scoped timing-command multiset and timing properties match input/output:
two5 ns/10 ns clocks and39 vendor XPM reset/synchronizer false paths; vendor
source/scope records unchanged. All2770 prior preserved paths reverified unchanged.
DRC has ZERO errors/critical warnings, NOT zero warnings:644 DPIP-2 +6 DPOP-3 +575
DPOP-4, plus one RTSTAT-10 warning covering197 no-routable-load nets (only first15
listed). All routable nets routed; these are not unrouted loads. Methodology64
DPIR-2 DSP asynchronous-driver advisories, no LUTAR-1; FIFO async-reset FF count0.
No RTL/reset/pipeline change was made to silence warnings.

Final routed resources63192LUT/52748FF/579DSP/50BRAMtiles/36URAM, same as placed.
Router summary setup+0.046 ns was provisional; final full STA and path query both
+0.048ns. Hold+0.011ns. Versusplace, setup-0.458ns/hold+0.084ns. Tight single-run
closure only, NOT Fmax/300MHz, board qualification or useful-success WCET.
Actual routed setup worst now memory SmartConnect read-state[3] -> linear
weight_reg[1][7][12][5],4.728nsdata (0.196logic/4.532wire,95.855%wire), oneLUT2,
skew-0.139ns/uncertainty0.129ns. State netfanout142 then m_axi_rdata[101]fanout156,
last wire3.498ns. Placement softmax-shift worst is NOT routed worst.
Hold worst attention query-distribution group2 data[68] -> query[11][1][8][4],
0.245nsdata, zero logic levels,0.131nsclockskew. Do not assume arithmetic depth
alone is the next timing limit; AXI data distribution/locality now has evidence.

Run/review session30266 COMPLETEexit0. Original route-review.json preserved;
review-final receipt is `route-review-final.json`. First sealer found reviewer's
self-console hash taken before final print; ONLY metadata repaired separately.
Original helper/receipt unchanged, all native evidence unchanged. Failed sealer
snapshot/hash mismatch saved route-v1/sealing-attempt-v1; finalizer and v2sealer
preserve it. No reroute or check weakened. Final v2 sealer COMPLETEexit0.

Read FINAL frozen `docs/research/2026-10-16-typed200-row-range-csa-route.md` and
`docs/research/2026-10-16-typed200-row-range-csa-route-validation.json`.
All route artifacts/helpers/report/prior hashes are bound. DO NOT edit mapped
files; handoffs remain editable. Do not restart any completed runner/proof/build.

NEXT recommendation ONLY: target startup/reset/clock/master ownership and
justified DDR/MMIO/ARM service bounds plus typed-output captures for the MVP.
Routed closure is not target qualification or permission to create a bitstream.
Prior deployment inventory is a sealed historical draft, not a promoted CSA
profile. Any future AXI-locality/capture change must explicitly prove handshake,
outputs/counters/cycles and revise deadline budgets if latency changes.
No additional experiment, bitstream, deployment or ARM target action started.

## Completed: typed row-range narrowing (2026-10-16)

Latest human request COMPLETE: separate candidates, all raw valid/invalid input
proofs, unchanged outputs/cycles, matched timing probes, conditional full
synthesis/placement and native audit. No active native job or pending pipeline.
Overnight heartbeat `system-one-overnight-predecode` remains PAUSED; not restarted.
No routing, bitstream/package, board programming/deployment/reboot, commit or push.
Qualified 200 MHz sources/package/recovery/numerical and previous seals preserved.

Preferred characterized candidate: `rtl/v2/candidates/typed200_row_range_csa`,
independent descendant of sealed predecode. ONLY contracts/typed_intent_axil.sv
changes: explicit raw high-bit rejection, XOR/majority carry-save A+B+~T test
preserving BOTH high carries, no new state/cache/cycles or live permission.
Actual-source SAT proof covers ALL2^64 raw shape/count encodings, no legal-input
assumptions. Full endpoint temporal induction PASS in2steps: external outputs,
bank/written masks/bus/guard state/profile flags/shape match under arbitrary
AXI addresses/data/strobes/split writes/commands/backpressure/core signals and
later resets. Only first sampled reset/single clock/two-state assumptions.

Independent frozen-parent ADD_SKIP AND encoder_layer full regression PASS:
5400goldenwords/14pairedcompletions/14launches, exact outputs/counters/AXI/busy/
donecycles, normalT1..128 and faults. T1287961537encoder/7966029request cycles,
emulated publicationage7966096. Hostsimulation444.320s is NOT ARM timing/WCET.
Matched whole endpoint probe overall+1.595->+1.743ns (+0.148), shape-source
+1.595->+2.313ns (+0.718); levels11->7, LUT1026->1009/FF1815unchanged.

Full synthesis/source-clock review COMPLETE: 30staged/28compiled hashes, explicit
5ns OOC clock beforeoptimization, actual5ns/10nsfullclocks/noOOCleak. Full
68296LUT/53376FF/579DSP/50BRAMtiles/36URAM, estimatedsetup/hold+0.624/-0.087ns.
Versuspredecode -203LUT/-11FF, setup-0.004ns: no global synthesis timing gain.
Full placement/native audit COMPLETE: **+0.506/-0.073ns** setup/hold,
63192LUT/52748FF/579DSP/50BRAM/36URAM. Versuspredecode setup+0.057ns,
hold+0.081ns, -191LUT/-64FF. Setup clears unchanged+0.500ns route gate by ONLY
0.006ns. Gate review route_approved=true means timing-only eligibility;
**routed=false**, negative placed hold unresolved, no routed closure/qualification.
Single-run comparison is not robust margin, throughput gain, WCET or300MHz proof.

Actual global worst: instruction bit130 (softmax_shift[2], word1) -> attention
lane11 e_index[24], 4.285nsdata (1.147logic/3.138estimatedwire,73.232%wire),
9levels/4CARRY8, skew-0.124ns/uncertainty0.129ns. Shape-source worst now+1.010ns,
no longer global bottleneck. Native selected minima: predecode+1.996,
product+0.965, rounding+0.819, output FROM clampedskip+0.916, profileflags+1.080.
Output query source-restricted, not all residual/control sources. All12 timing
checks0, CDCsafe,39vendorXPMexceptions only, epoch/publication/permit/GPIO and
32profileflags/128clampedskip/bias/product retained, no LUTAR/FIFOasyncreset issue.

Pipeline session52782 COMPLETEexit0 (seven commands); sealer6713 COMPLETEexit0.
Physical `build/v2/typed200-row-range-csa-physical-v1`; orchestration receipts
`build/v2/typed200-row-range-csa-pipeline-v1`. Read FINAL immutable report
`docs/research/2026-10-16-typed200-row-range-csa.md` and final seal
`docs/research/2026-10-16-typed200-row-range-csa-validation.json`.
All2604 prior preserved paths unchanged; actual WSL staging rehashed. DO NOT edit
mapped candidate/helpers/report/evidence. Handoffs remain editable.

Earlier direct-sum attempt `typed200_row_range` also fully proved/regressed:
5400words/14cases, but probe+1.595->+1.292ns (-0.303ns); fewer carry cells but
wire delay outweighed logic improvement. NO fullbuild; rejected and sealed,
2491priorpaths unchanged. Its arithmetic-v1 missing chformal-lower tool failure
is preserved; v2 passed. Read frozen -row-range.md / -row-range-validation.json.
The CSA report clarifies the direct report's ambiguous closing "no native job"
sentence means no FULL implementation job: native probes/regression did run.

NEXT recommendations ONLY: timing-only route of exact reviewed DCP (narrow6ps
margin, require routed setup/hold/DRC/CDC/exception checks), then prioritize target
startup/clock-reset-master ownership/service bounds and typed-output captures.
All13 existing deployment gates unresolved. No target ARM/WCET/external-delivery
claim. A future softmax shift/rounding predecode/fanout experiment must prove
word1 freshness/history/alignment and exact finite-width rounding; not implemented
or scheduled here. Do not reuse ADD_SKIP word0 assumptions for word1.

## Completed: instruction-local rounding predecode (2026-10-16)

Final result: proofs, independent regression, matched all-stage probe, full synthesis,
placement and native checkpoint audit COMPLETE. Pipeline-v2 session 23019 exited 0;
final sealer session 69155 exited 0. No native jobs remain. The overnight heartbeat
`system-one-overnight-predecode` is PAUSED after experiment completion, before its
08:00 America/Chicago cutoff. Do not restart v1/v2 or replay proof/simulation/probe.

Read `docs/research/2026-10-16-typed200-predecode.md` and immutable final record
`docs/research/2026-10-16-typed200-predecode-validation.json`.
All 2291 prior preserved paths unchanged; actual WSL staged inputs rehashed.
Candidate, helpers, report, functional/physical evidence and failed attempts are
hash-bound: DO NOT edit mapped files. Handoffs remain editable.

Separate `rtl/v2/candidates/typed200_predecode` captures 26-bit rounding bias on
exactly the instruction word0 capture edge; no new externally observable cycles.
Sequencer/cache/freshness/stability/valid-history induction and actual instance
composition PASS. Full-domain finite-width arithmetic and 886 conditional engine
equivalence points PASS. Independent frozen-parent ADD_SKIP AND encoder_layer
regression PASS: 5400 golden words / 14 paired completions / 14 launches, exact
outputs, counters, AXI, busy/done cycles across normal T1..128 and fault cases.
T128 encoder/request cycles 7961537/7966029; emulated publication age 7966096.
Assumptions and startup/history scope are explicit in report; no arbitrary
untrusted bias or arbitrary-changing-shift detached equivalence claim.

Matched registered-input probe overall +1.872 -> +1.887 ns (+0.015 ns).
Positive gain admitted full synthesis/placement per latest user authorization;
previous +0.050 ns experiment-cost threshold superseded only for this request.
The +0.500 ns placed setup routing gate remains unchanged.

Full synthesis: 68499 LUT / 53387 FF / 579 DSP / 50 BRAM tiles / 36 URAM,
estimated setup/hold +0.628/-0.087 ns; exact 30 staged / 28 compiled sources and
5 ns / 10 ns clocks reviewed. Full placement: 63383 LUT / 52812 FF, same memories
and DSPs; setup/hold **+0.449/-0.154 ns**. Setup improves 0.032 ns versus
profile_cache (+0.417), but remains 0.051 ns below routing gate; hold worsens
0.082 ns. **ROUTING HELD. Do not route/promote this checkpoint or relax constraints.**
Single-run comparison is not repeatability, 300 MHz, routed closure or qualification.

Native audit: all 12 check-timing categories zero, CDC safe, only 39 vendor XPM
reset/synchronizer exceptions. Predecode/product/rounding selected minima
+1.572/+0.700/+0.640 ns; output FROM skip-clamped registers +1.373 ns (source-
restricted query, not all output sources). Bias/product/clamp/profile registers
retained; no LUT asynchronous resets/FIFO reset mapping issue.
Actual global worst now typed selected-row shape/admission: publication bank5 bit17
(first-row bit1) to encoder-system state CE, 4.153 ns data, 13 levels/4 CARRY8,
60.679% estimated wire. Exact reports under
`build/v2/typed200-predecode-physical-v1/{place,placement-audit}`;
complete orchestration receipts under `build/v2/typed200-predecode-pipeline-v2`.

NEXT RECOMMENDATION ONLY, not implemented/started: narrow typed selected-row shape
validation using tokens <=128, explicit high-bit rejection and a carry-preserving
narrow sum. Prove equality over ALL raw token/first/count/reserved encodings,
including invalid inputs/overflow; prove full endpoint behavior with arbitrary
WSTRB, split writes, masks, commands and reset. Then exact full regression and
matched physical experiment. Do not cache live permission. Keep target startup,
clock/reset/master ownership and service bounds first for timing-guaranteed typed
outputs; placement is not successful-inference WCET or external delivery proof.

Qualified 200 MHz sources, package, recovery, numerical baseline and every prior
seal remain intact. No bitstream/package generation, board programming/deployment/
reboot, commit or push. Failed formal v1/v2 and replaced waiting pipeline-v1 policy
snapshots retained. Experiment ended with documented routing rejection; new work
is not started by this completed overnight heartbeat.

## Completed: first-clamp stage move, timing rejected (2026-10-16)

FINAL: all26bitproducts/64shifts/16bitresiduals proofPASS;886fullengine/stage
equivalencepoints PASS; independentfullregressionPASS5400goldenwords/14paired
completions/14launches, allnormalT1..128 andfaultcases, exactoutputs/counters/
AXI/busy/donecycles. Sim443.939s/build120.786s. T1287961537/7966029,
emulatedpublicationage7966096 unchanged. Sessions25310/6270exit0,NOJOBSremain.

Outputstagegain+0.968ns,roundingstageloss-0.900ns,OVERALLLOSS-0.613ns
(parent+1.872ns->new+1.259ns,matched5nsregistered-inputprobe). Newshiftcontrol
limitshowsdirectclampmoveisnotaspeedup. **DO NOTPROMOTE/FULLBUILDCANDIDATE**.
Pipelinecompletedphysical_build_admitted=false,no fullphysicaldirectory.
NoVivadojob/route/bitstream/package/boardIO/automation. Allqualifiedbaseline
sources/package/recovery/numerical andpreviousseals remainunchanged.

ReadFINAL `docs/research/2026-10-16-typed200-stage-clamp.md` andimmutable
`2026-10-16-typed200-stage-clamp-validation.json`. Source/helpers/report/probe/
proof/regressionevidence andMVPreadinessnote arefrozenbyfinalseal;don'teditmapped
files. ActualWSLstagedfilesrehashed;allpriorsealedmapschecked. HANDOFFeditable.

NEXT: instruction-local shift/rounding predecode candidate, ONLYafterdischarging
actualsequencer stability andvalidoutputalignment throughreset/abort/nextinstr.
encoder_layer onlywritesinstruction_reg inFETCH_RECEIVE;dispatchthenEXECUTEholds
untilengine_done. ADD_SKIPshiftbits101:96. Thisisanalysisevidence,NOTacomposed
proofyet. Arbitrarychanging-shift standaloneengineequivalencemustNOTbeclaimed
ifpredecodereliesoninstructionstability. Provecomposition/stability andprobeall
stages,keepindependentparentarithmeticreference. RefinementNOTimplemented.
Extraarithmeticstageisanexplicitlycyclechangingseparateoptionwithnewbudgets.

MVPanswergiven:lowconfidence5–10focusedengineeringdaysforsupervisedboarddemo,
conditionalontypedroutedclosure/R5startup/enforcedownershipwithoutplatform
redesign. NOTpromisedate/schedule. Useful-successWCETundateduntilboundedDDR/MMIO
andphasecomposition. ReadMVPreadiness.md(dated2026-10-16). No targetdeployment
authorizationimpliedbythisestimateorlocalexperiment. Typedoutputqualification
andownership/capture/bounds remainfirstproductpriority.

### Completed stage-move chronology

User explicitly authorized newcandidate, exactoutputs/cycles proof, BOTHstage
probe andfullsynthesis/placementIFtimingimproves. AlsoaskedMVPestimate.
New`typed200_stage_clamp` fromsealedprofile_cache,onlyADD_SKIPchanges.
INT26rounding/overflow/shift remains exact; firstclampbeforeexistingL+2register
whichnowholdsINT16skip_clamped. Noextracycle;final17bitadd/clampunchanged.

FormalCOMPLETEPASSv1 (`scripts/v2/prove_typed200_stage_clamp.py`):all26bitproducts/
64shiftencodings/16bitresiduals;publicengineequivalenceandexplicitstage relation
new.skip_clamped==clamp(old.rounded), correspondinginitialstate/two-state/single
clock. Actualsource hashesrecorded. DoNOTassumerawold/newroundedstateequal.

MatchedBOTHstageprobeCOMPLETE`typed200-stage-clamp-ooc-v1`,session47344exit0.
Identicalregisteredinputshellmodelsupstreamcontrol/data,includingshiftlaunch,
NOTcandidateextrastages. Control rounding+2.159ns/output+1.872ns/overall+1.872ns.
Newrounding+1.259ns/output+2.840ns/overall+1.259ns. OUTPUTgain0.968ns but
roundingloss0.900ns/overallloss0.613ns. Newworstin_shift_reg[3]->skip_clamped[0][0]/D,
3.738nsdata(1.691logic/2.047estimatedwire),13levels6CARRY8. Parent2.838nsrounddata.
128vs208stageFF; totalLUT2938vs2866/FF1096vs1177. **NOFULLPHYSICALBUILD**:
probeoverallgain fails. DoNOTpromoteorrelaxgates. Parentbaseline remainsfrozen.

Completedfullindependentregressionsession25310 (`run_typed200_stage_clamp.sh`)
andoneforegroundpipeline6270waitedEXISTINGsim/probe,thenrecordedhelddecision.
ReferencehasseparatefrozenparentADD_SKIPandencoder_layer,allcycles/counterschecked.
NoVivadojobremains,nootherbuild/targetIO/automation. DoNOTrestartexistingattempts.
Newphysicalhelperspreparedbutwon'texecuteifprobeheld. Initialflowpreparation
assertionclose_projectvsclose_designpreservedunderflow-preparation-v1; resumed
onlyidenticalpartialoutputs+missinghelpers. NoRTL/nativejobchangedbyrepair.

ReadFINAL `docs/research/2026-10-16-typed200-stage-clamp.md`. Finalsealer
`seal_typed200_stage_clamp.py`, runONLYafterregression/pipeline/finalreportfinish;
itchecksallpriorsealedmaps,actualstagedinputsandproof/probe/evidence.
NewMVPreadiness.md:lowconfidenceplanning5–10focusedengineeringdaysforsupervised
boardMVP,conditionalontypedphysicalclosure/R5startup/enforcedownershipwithout
platformredesign. NOTpromise/schedule; useful-successWCETcannotbedatedbefore
DDR/MMIObounds/phasecomposition. Existingencoderalreadyhardwarequalified.
Boardprogramming/deploymentnotpartofthisauthorizedlocalexperiment.

## Completed: same-stage ADD_SKIP clamp experiment (2026-10-16)

FINAL: whole-domain arithmetic PASS;966wholeengineequivalencepoints PASS;
fullindependentreference regression PASS5400words/14completions/14launches,
exactalloutput/AXI/busy/done/rawcountercycles. T1287961537/7966029,
publicationage7966096 unchanged. Sim417.314s/build125.779s. Nojobsremain.

Matchedprobe REJECTS rewrite:parent+1.872ns ->new+1.698ns at5ns;data2.964->3.137ns.
Logic1.381->1.277ns butestimatedwire1.583->1.860ns; levels10unchanged,CARRY8
depth6->2; totalcarry192->152;LUT2867->2739,FF877same. Reducingcarrycountalone
losttiming. DO NOTPROMOTE orfullbuildthiscandidate. Pipeline68375 COMPLETEexit0,
physical_build_admitted=false. NewphysicalhelperspreparedbutNOTnativevalidated.
No fullphysicaldirectory,route,bitstream,package,deploymentorboardIO.

ReadFINAL `docs/research/2026-10-16-typed200-clamp.md` andimmutable
`2026-10-16-typed200-clamp-validation.json`:allpriorsealedfilesverified, actual
WSLstagedfilesrehashed; sources/helpers/report/profiledraft/evidence nowfrozen.
DoNOTeditmappedfiles. HANDOFF/architecturehandoff remaineditable. Noautomation.
Newtypeddeployment-profile-draft snapshotsactualartifactidentitiesandsixABI
outcomes,13unresolvedtargetgates,deployment_ready=false; no combinedqualification.

NEXT separatearchitectureexperiment: moveFIRSTclampintotheEXISTINGrounded-skip
registerstage(storeINT16clampedskip),preserve26bitrounding/shiftbeforeclamp and
allcycles. Renamechangedsemanticregister; proveappropriateold/newstagerelation
andpublicenginecyclecorrespondence. ProbeBOTHroundingandoutputstage: movinglogic
mayworsenroundingstage. NOTimplemented. Fullregressionnowhasindependentrenamed
frozenparentADD_SKIP/encoder_layer andcanbeadaptedinnewnamespace.
Typedproductpriority: resolveenforceableglobalmasterownership,load/startup/clock
evidence,targethead/phasecaptures,boundedDDR/MMIO/WCETcompositionandseparate
externaldeliverysupervision. Currentinventoryisnotacertificate. No permission
inthiscontinuation toprogramtarget; qualified200MHzbaseline remainsunchanged.

### Completed chronology for clamp experiment

User said proceed. New separate `rtl/v2/candidates/typed200_clamp`, only
encoder/add_skip_engine.sv differs from sealed profile-cache parent. Both clamps
use sign-extension and low-zero reductions; asymmetric[-32767,32767],26bit
rounding/product,shift,17bit addition,allstage/address/valid/control unchanged.
Creator `scripts/v2/kr260/create_typed200_clamp_candidate.py` verifies inventory.
No priorsealed/qualifiedfile edits or board IO. Fullprofilecache result below
is completed history, not a pending job. No route on its rejectedcheckpoint.

Actual-source entire26bitrounded/16bitresidual arithmetic proof PASS in formalv3.
Wholeengine v3 duplicated-historySAT reached1.41Mvars/4.12Mclauses/~1.54GB atbase8;
exact own solverPID48364 identitychecked thenstopped, preservedresource-rejection
andgenerator. v1 portcount generatorassert failedbeforetool; v2 neededchformal
lowering, noRTLcounterexample. v4 usesYosys equiv_make/equiv_simple/equiv_induct
onactual fullmodules, equivalent internalstatepoints, same sampledclock/two-state.
v4 stoppedexactsolver re-provingidenticalmultiplycones. FINALv5 COMPLETEPASS:
entirearithmeticdomain and966fullengineequivalencepoints/0unproven. Addopt-full
AFTERequiv_make mergedidenticalcones, noRTL/assertionchange. Noformaljobsremain.

`check_typed200_clamp_ooc.py` matched5nswholeengineprobe usesfinalv5proof.
v1 failedTclJSONserializationaftercontrolreports, preservedgenerator/attempt.
Completedv2 probe session2816, sameRTL/constraints, correctbracedformatJSON.
NewLF `simulation/v2/run_typed200_clamp.sh`, generatedby
`prepare_typed200_clamp_regression.py`: independentfrozenparent encoder_layer
ANDADD_SKIP areseparatelyrenamed inreference. Thiscorrects sharingfornewscope;
originalAXIL-onlyrunner staysfrozen. Completedfullregressionsession47153.
Singleforegroundpipeline session68375 waitedEXISTINGregression/probev2;
newfullphysicalhelpers admitbuildonlyif>=0.050nsprobecone gain/no>0.050overall
regression. Pipeline runsfullsynth/review/place/audit andtiming-onlyroute IF
preserved+0.500nsplacementgatepasses. Nojobduplication/bitstream/package/boardIO.
ReadFINAL `docs/research/2026-10-16-typed200-clamp.md`. Finalsealer
`scripts/v2/kr260/seal_typed200_clamp.py`, runafterpipelineandfinalreport;
itrehashesactualWSLstagedinputs andallpriorsealedmaps. DoNOTsealprematurely.
Newconcrete deployment-profile-draft.json hashesactualartifacts/13unresolved
targetgates, deployment_ready=false. Noqualifiedcombineddeploymentclaim.
Keep+0.500nsroutegate,typedliveguards/epoch/deadline,baselinepackages preserved.

## Completed: full profile-cache experiment (2026-10-16)

User clarified "restart" means resume YOUR WORK, not reboot board/build/app.
Existing pipeline session73255 completed normally, exit0. No job was restarted,
no board I/O performed. Synthesis, exact-source/clock review, placement, native
reopened-checkpoint audit and placement review COMPLETE. No native jobs remain.

Final cache placement: **+0.417 ns setup / -0.072 ns hold**, 63,456 LUT / 52,768 FF /
579 DSP / 50 BRAM / 36 URAM. Matched control +0.371/-0.087 ns, 63,331/53,055:
single-run setup improvement 0.046 ns, +125 LUT/-287 FF. **ROUTE HELD**, below
preserved +0.500 ns gate by0.083ns. Never route this rejected checkpoint, relax
the gate, promote it, create a bitstream/package or program the board.

All32 profile-equality FF retained; raw request-profile bank FF pruned to0.
Worst reported cache-origin path +1.243ns. Full-design worst is now ADD_SKIP
rounded_reg[6][3] -> out_data_reg[96]/S:4.219ns data,1.467logic/2.752estimated
interconnect,10levels/6CARRY8,skew-0.117ns. All12timing checks0,CDCsafe,
39vendorXPM exceptions only,noLUTAR/FIFOasyncreset. Other paths near+0.503ns
include instructionfanout and non-profile request-bank validation; synthesized
AXI path is NOT the placedworst. No300MHz or routed/target/WCET claim.

Read finalized `docs/research/2026-10-15-typed200-profile-cache.md` and immutable
`docs/research/2026-10-16-typed200-profile-cache-validation.json` FIRST. Finalseal
binds complete physical evidence and earlier functional seal. DoNOTeditmapped
sources,helpers,reports/checkpoints/evidence. HANDOFF/architecturehandoff remain
editable. Dated follow-on plan `docs/research/2026-10-16-typed200-next-experiments.md`
is an editable supplement; original research matrix remains frozen.

NEXT actual performance experiment: new sibling on cache candidate, preserve-stage
ADD_SKIP clamp decomposition. First prove all26bit rounded/16bit residual values,
then wholeengine cyclecorrespondence; mappedprobe before fullphysical spend.
IMPORTANT regression runner reference currently shares ADD_SKIP (appropriate for
AXIL-only change); independently rename/copy frozen parent encoder_layer and
ADD_SKIP for next arithmetic regression. No new arithmetic candidate exists yet.
Retain exact rounding overflow/shift,asymmetric[-32767,32767]clamps andallcycles.

Typed-output work remains FIRST: concrete exactdeploymentprofile, enforceable
masterownership, targetnumerical/phasecaptures using existing timedR5 provider,
then justified nonoverlappingphasebounds. A53ingress beforeadmission;R5TCMhead;
PLdeadlineauthority. Localterminal-byD != success-byD != externaldeliverybound.
Target execution/deployment still not performed/authorized by this continuation.
Qualified200MHz package/recovery/numerical andallprevioussealedfiles preserved.

## Completed chronology: bank-local full-profile cache (2026-10-15)

User asked to progress more/faster. Continue THIS complete experiment through
full regression, synthesis, placement/audit and evidence; do not stop after proof
or ask another proceed. No board programming/automation/qualified-source edits.
Read mutable `docs/research/2026-10-15-typed200-profile-cache.md`.

NEW namespace `rtl/v2/candidates/typed200_profile_cache`: only AXIL andguard change
from sealedtyped200_flush. 32registeredbyteequalities mirror storedrequestbytes
at the SAME execute/address/WSTRB edge; resetflags reflectzeroedbank. All256bits
checked; existingwrittenfreshframe masks kept. No new admissioncycle or cached
quiet/error/epoch/deadlinepermission. NewinternalguardinputtrustedonlyfromAXIL.
Parent/rawrequestbank mayprune physically; fullbehavior proven, no timingclaimyet.

FULL ENDPOINT SEQUENTIAL PROOF PASS `typed200-profile-cache-formal-v3`: every
externaloutput/rawbank/writtenmask/AXIbuffer/guardprivatehistory+limit andall32byte
invariants match everyedge. Arbitrary AXI inputs/byte strobes/corequiet/reset,
firstsample reset/singleclock/two-state assumptions only. v1 neededmemorylowering;
v2unoptimizedSAT2.79Mvars/7.33Mclauses ownverifiedprocess stopped; preservedreceipt/
resource-rejection/generator. v3complete`memory`optimization298Kvars/831Kclauses
proves unchangedRTL/assertions. No functionalcounterexample observed.

COMPLETE full regression `build/v2/typed200-profile-cache-integration-v1` exit0
viaWSLVerilator5.040:5400goldenwords/14pairedcompletions/14launches; allT1..128 and
negativecases pass. Every-cycle rawcounter/output/AXI comparison toindependent
frozenreference unchanged. DoNOTrestart existingattempts. InitialshellCRLF failure
beforeoutputcreated preserved`build/v2/profile-cache-initial-crlf-script.sh`, fixed
LF runner before actualstaging. AllcandidateRTL unchanged afterstaging.

Historical pipeline session73255 (now complete; see current section above):
`scripts/v2/kr260/run_typed200_profile_cache_pipeline.py`. Waits on EXISTING sim,
then `build_typed200_profile_cache_physical.py --stage synth`, exactnewcache source/
clockreview, placement, nativeaudit andplacementreview SEQUENTIALLY. Logs under
`typed200-profile-cache-pipeline-v1`; physicalbuildname`typed200-profile-cache-physical-v1`.
SYNTHESIS/EXACTSOURCECLOCKREVIEW COMPLETE exit0 (2026-10-16 00:41local):full
68510LUT/53430FF/579DSP/50BRAM/36URAM, estimatedsetup+0.589/hold-0.087ns;
control68498/53651 so+12LUT/-221FF. OOC65744LUT/50827FF,+0.855/+0.036ns.
New synthesizedworstpath deliver_left_reg[7] -> SmartConnect AWFIFOafull/D,
13LUTlevels,data4.181ns(1.212logic/2.969estimatedwire71%), skew-0.145ns. DoNOT
credit overallgain fromsynthesis; placementdeterminesnewcriticalpath/margin.
Historical placement samepipeline session73255, nootherlargejob. Exact28compiled/
30stagedRTL/clocks reviewpassed; explicitencoderOOC5ns beforeoptimization, realPL5/10ns,
newprojectcacheoff/jobs1; existingS: alias kept. Preserve+0.500ns routegate; no
route unlesshashboundactualplacementreviewapproves. Pipeline presently endsafter
placementreview; ifapproved, timing-onlyroute mayfollow, neverbitstream/deployment.
Prepared `review_typed200_cache_route.py` requiresactualapprovedplacement+0.500ns,
completedroute, finalSTA/DRC/CDC/clocks/onlysamevendorXPMexceptions. DoNOTinvoke
route onsubthresholdcheckpoint. Placementaudit nowalso checksall32cachedFFs,
reportsrawrequestbankretention andflag-Q paths; untesteduntilnativeauditfinishes.

NEW IMMUTABLE `docs/research/2026-10-15-typed200-profile-cache-functional.json`:
allactualWSLstagedinputs rehashed;1907priorpreservedpaths unchanged. Fixesexact
candidateRTL/manifest/README/creator/proofgenerator/simrunner+proof/simevidence.
DoNOTeditmappedfiles. First stagedhash invocation lostshell positionalarguments;
failurelog preserved, directWSLsha256sumcheckpassed, noinputdrift. Physicalhelpers
andliveworkreport remaineditable until finalphysicalseal, but DON'Tchange runner
whosehash isalreadyboundinphysicalinput-proof.json.

Original next step (completed; see current section): finish existing nativejobs,
review actualresources/criticalpaths andfinalpreservationseal including ALLmaps in
`2026-10-15-typed200-timed-validation.json` (also historical_evidence_sha256). Keep
HANDOFF/architecturehandoffcurrent. Earlierparagraphs arecompletedhistory, not jobs.
Finalsealhelper `scripts/v2/kr260/seal_typed200_profile_cache.py` (dest2026-10-16...)
ispreparedbutMUSTwaitforplacementand,ifapproved,completedtiming-onlyroute+review.
DoNOTeditphysicalbuilderalreadyboundbyinput-proof or functional-frozenfiles.

## Latest continuation: timed PMU diagnostic successor (2026-10-15)

Read `docs/research/2026-10-15-typed200-timed-provider.md` and IMMUTABLE
`docs/research/2026-10-15-typed200-timed-validation.json` first. All mapped files
are frozen; originalv8/ordertrace/RTL/numerical/package remain unchanged. This
handoff and architecture-review-handoff remain editable. No target programming
authorized and no automation recreated. No jobs remain active.

IMPLEMENTED `firmware/typed200_timed/`: new platform binds checked read-only PMU
provider aftermodelhash/before serviceinit. Fullrate CortexR5 PMCR.E=1,D=0,DP=0,
cycleenabled, cycleoverflowIRQdisabled, overflowclear required; first2samples
mustadvance. Per-event controls/overflow+ISBcounterread+overflowcheck; badstate or
backward/equaltick gives stickyfault. No PMU MCR/config/reset/overflowclear writes.
Loader must supply preconfigured owned PMU and32Bconfig atR5local0x2f180 AFTER
ELF/NOBITS load:magic0x504d5531/version1/freshmatchingsession/declaredCPUHz/
exclusiveattested1/reserved0. Missing/badstate halts exception14 withpermitlow.

Existing384B mailbox ABI unchanged; NOLOAD sharedsection416B includesnewconfig.
Provider evidence72B in privateTCM, freezes withfirsttracecommit. Do not infer
frequency/ownership/provenance from attestations. Debughalt/clockchange/transient
countertamper excludedonlybydeploymentprofile. Longboot/produceridle canoverflow
32bitcounter; strictpolicy rejects entiretimingtrace, no modulo repair/clearing.

FINAL `build/v2/typed200-timed-host-v3/receipt.json`:396pytestPASS,14startup+5
postbind PMUfaultscenarios sanitizerPASS; fivecapturecases and49pairedpollrecords/
55076bytes EXACTfrozencontrolmatch. Hosttickstep100 and500MHz are MOCK testdata,
NOT hardwaretimings. ARM ELF audited:18160BATCM/51216BBSS/2032Bworkspare;
trace1488B@0x20010/evidence72B@0x205e0/config32B@0x2f180. R5local addresses areNOT
A53physicaladdresses. Actual PMUobject MRCreads checked; noMCRwrites. Both input
.shared/.clock_config PROGBITS->NOLOAD warnings documented; actualNOBITS416B checked.

`src/sysone/v2/typed200_timed.py` + offline CLI
`scripts/v2/check_typed200_timed_capture.py` requiresfaultfree matchingPMUrecord,
source/Hz/session/samplecount andstrictlyincreasingticks. Reports instrumented
phase counterdifferences and integer-ceilingnominalns atDECLAREDHz; no overhead
subtraction. AcceptedCLI pass; faultedevidence rejects; existingreportpreserved.
Frequency/PMUownership/target/WCET/usefulsuccess/externaldelivery claims stayfalse.

Derivedrunner generated separately; frozen tracebuilder untouched. v1syntax
escape failure beforeexecution preserved; v2passed exacttestedsource snapshots;
v3finalmetadata/tests. Finalseal rehashes1683preservedpaths unchanged including
qualifiedarchive. No targetIO/PMUsetup/Vivado/hardware/automation this continuation.

Remaining critical path to targetassurance: adequate typed physicalmargin before
recoverable deploymentimage; reviewed loader/TCM/ECC/other-master+PMUownership;
actualclockreadback/nohalt profile; targetgoldens and instrumentation/servicebounds.
All typedplacements remain belowpreserved+0.500ns routeadmission. Strong nextlocal
architectureexperiment is separate bank-local full-byte profileequality flags,
with exact partial-write/reset invariant and fullendpoint sequentialproof before
regression/physicalwork. Preservelivequiet/error/epoch/deadline checks. No300MHz
or targetqualification claim. Continue authorized local work autonomously.

## Latest continuation: separate owner-local R5 trace (2026-10-15)

Read `docs/research/2026-10-15-typed200-owner-trace.md` and IMMUTABLE
`docs/research/2026-10-15-typed200-owner-trace-validation.json` first. All mapped
source/doc/evidence/historical snapshots are frozen. Do not edit reviewed v8 or
qualified FPGA/package/recovery. This handoff and architecture-review-handoff
remain editable. No board programming is authorized; no automation recreated.

IMPLEMENTED separate `firmware/typed200_trace/`: generated service diff plus fixed
1488-byte privateBTCM trace,32eventslots, one-shot commit/freeze. RawPL terminal
captured BEFORE ACK via22definedreadonlyCSR+secondstatusread (23reads). Never read
all64addresses: unmapped/writeonly CSR reads SLVERR. Serialized mailbox captured
BEFORE DONE producerrelease; command_state reflects the exact forthcoming DONE
store, eventloggedafterstore. Never reread sharedbytes after DONE. v1 postDONEcopy
rejected on review; v1/v2 exact source snapshots preserved, v3 final evidence.

FINAL `build/v2/typed200-trace-host-v3/receipt.json`:364testsPASS; original frozen
servicepolicytests and5capturecases sanitizerPASS. New independentlycompiled
frozen control vs trace:49pairedpollrecords/55076bytes exactlysame state/bridge/
proposal/MMIO/IDs/permit/mailbox; finalcapturebytes match prior frozenfixture.
Overflow/one-shot/producer-mutation/defaultclock/mockwrap unitchecksPASS.
No target timing/equivalence claim: extra instructions/MMIO may delay proposals.

Separate linked ARM diagnosticELF `typed200-trace.elf` audited:ATCM17416B,
BTCMBSS51144B (2104Bspare), ty_trace atR5local0x20010 size1488, shared384B unchanged,
stack8192/banked1280 unchanged. No undefined/legacytransport symbols. Inherited
.shared inputPROGBITS->NOLOAD NOBITS warning retained; actualELF NOBITS checked.
Three examined compilerframesums488/2112/480B are NOT exhaustive/highwater/WCET.

Default ELF is ORDER ONLY: no real counter/PMUprovider; clock_valid0/ticks0.
Injectedclock API tested with hostmock only; unreferenced targetconfig may beGCed.
Do not invent/call a target config address. Future timedplatform successor needs
explicit loader/clock/counter provenance/wrap/overhead assumptions and own build.
Observed admission/native events are softwareobservations, not exactPL/AXIedges.

Offline decoder `src/sysone/v2/typed200_trace.py`; CLI
`scripts/v2/check_typed200_trace_capture.py`. Validates commit/ABI/identity/order/
snapshotmarkers/statusstability/typedpayload; CPUfault rawPL remains diagnostic,
not authoritative. AcceptedCLI passes; uncommitted rejects; existingreport kept.
Finalseal rehashes1442preservedpaths unchanged including qualifiedarchive.
No jobs active; no targetIO/PMUsetup/Vivado/boarddeployment in this continuation.

Next prerequisites: timedplatform/counter successor, adequate typed physical
margin before recoverable deploymentpackage, reviewed loader/TCM/ECC/ownership,
target exactgoldens and instrumentationoverhead/servicebound evidence. R5v8,
head/numericalcontract/typedPLdeadline remain unchanged. No300MHz, usefulsuccess
WCET or externaldelivery guarantee. Continue authorized local work autonomously.

## Latest continuation: executable typed capture qualification (2026-10-15)

Read `docs/research/2026-10-15-typed200-capture-qualification.md` and immutable
`docs/research/2026-10-15-typed200-capture-validation.json` first. Do not edit their
source/documentation/evidence maps or any mapped files. Earlier continuation seal
now fixes the old timing work report/target plan/helpers too, despite stale
"mutable" descriptions in historical sections below.

Implemented `src/sysone/v2/typed200_capture.py` + offline CLI
`scripts/v2/check_typed200_capture.py`. Exact384-byte R5 mailbox and256-byte PL CSR
decoder binds full256bitSHA/numericLSW-first words, session/request/sequence,
inputtokenIDs/shape/budget, expectedlabel/outcome. Canonicalpadding/reserved/failure
payloads, terminalconfiguredstate, ownedshape/nativequietsuccesspermit, quarantine,
1..D age/exactDeadlineD enforced. CPUoriginfault/rejection has NO authoritative
PLage/budget claim. No live IO and all guarantee/targetverification flags false.

Final reproducible `build/v2/typed200-qualification-host-v3/receipt.json`:
332pytestPASS, everySHA bit mutated individually;5actualfrozenCservice/mock-MMIO
captures pass address/undefined sanitizers, originalservicepolicytests also run.
Independent frozenimage head zero-hiddenlabel10 matches Accepted fixture.
All decodedlayoutoffsets/sizes staticassert on host AND compiled CortexR5.
R5 object only, never linked into v8. CLI corruption rejects without successfile.
Final seal rehashes1398unique preserved paths including qualifiedarchive; unchanged.
No native builds, simulations or harnesses remain active. No board interaction,
Vivado synthesis/place/route, hardware programming or automation this continuation.

Pre-ACK capture caveat: v8 immediately ACKs reusablePL terminals; a CSRdump after
mailboxDONE may have lost RESULT_VALID. A separate target-instrumentation candidate
must preserve coherent owner-local preACK observation and phase timestamps without
concurrentunownedMMIOreads/deadlinepause. Currentkit is OFFLINE only; mockages91/500
are supplied, not measured. Targetstartup/ownership/goldens/WCET/externaldelivery
remain unpassed. Next local implementation: separately reviewed instrumentation
candidate and host behavior/ABI checks; no silent modification of reviewed v8.

Reproduce only into a fresh unique directory using
`uv run --no-sync python scripts/v2/check_typed200_qualification.py --name typed200-qualification-host-v4`.
v1/v2 are preserved intermediate checker iterations, not final current-source
receipts; exploratory `typed200-capture-host-v1` also remains preserved.

## Current continuation: typed timing and clock-flow experiments (2026-10-15)

LATEST RESULT (supersedes progress snapshots below): profile-tree full synthesis,
placement and native audit COMPLETE. Final setup+0.358/hold-0.106ns versus
unchanged-RTL corrected-clock control+0.371/-0.087ns. Profile logic reduction is
offset by wiring/skew; DO NOT PROMOTE. Resources63494LUT/53173FF/579DSP/50BRAM/
36URAM. Both placement reviews ROUTEFALSE below preserved+0.500ns margin.
All12 timingchecks0, CDCsafe,39vendorXPM exceptions, retainedtypedcontrols,
noLUTAR/FIFOasyncFF0. No profile or validation simulations remain active.

COMPLETE separate physical-only Explore on ORIGINAL CONTROL placed checkpoint:
`typed200-clock-physical-v1/postplace-opt-v1`. Do not restart.
Vivado reports setup optimizations SKIPPED because current WNS+0.371>=0;
do not claim a physical optimization gain. Final review +0.371/-0.087ns,
ROUTEFALSE; all checks pass but unchanged+0.500ns margin is unmet. No jobs active.
Final preservation/evidence seal is
`docs/research/2026-10-15-typed200-timing-continuation-validation.json`.
Do not edit any files in its source/report/evidence maps after creation.
New concrete target qualification plan:
`docs/research/2026-10-15-typed200-target-qualification-plan.md`.
It specifies loader/ownership, ARM exactgoldens, boundedphasecomposition and
fault/delivery experiments; no board authorization/execution is implied.

User's existing proceed authorization covers continuing local implementation.
Do not stop at an intermediate milestone to await another proceed. No board
programming/deployment is authorized. Qualified200/package/recovery and all
prior sealed sources remain frozen. Existing S: alias must not be changed.

Read mutable `docs/research/2026-10-15-typed200-timing-continuation.md` and NEW
IMMUTABLE `docs/research/2026-10-15-typed200-timing-functional-evidence.json`.
The latter fixes both new candidate RTL/manifest/README, creators, proof generators,
regression runners and full test/proof evidence. DO NOT edit its source/evidence
maps. Candidate JSON initial sealed:false metadata is preserved; the external
record freezes exact sources. Physical builders/review helpers and this handoff/
work report are outside the functional seal and remain editable.

FUNCTIONAL WORK COMPLETE:
- `rtl/v2/candidates/typed200_observe/`: encoder_system observational counters only,
  plus observed_cycle_counter. Register events then compensate pending event so
  original counts match at EVERY sampled edge, including clear priority/wrap.
  32-bit arbitrary-event induction PASS `typed200-observe-formal-v1`.
- `rtl/v2/candidates/typed200_lut_capture/`: only linear_engine table-load payload/
  row capture, one-edge internal write delay. Request/load FSMs unchanged. Universal
  byte induction PASS `typed200-lut-capture-formal-v2` for all256 table bytes after
  pending write drain; reset invalidates initialization evidence. Whole-array v1
  hit WASM exception during SAT import; preserved, no functional counterexample.
- BOTH full integration runs PASS: `typed200-observe-integration-v1` and
  `typed200-lut-capture-integration-v1`:5400goldenwords/14pairedcompletions each;
  T1/2/3/4/5/12/64/128; exact every-cycle raw counts/output/AXI traces; late/error
  B/R, deadline/quarantine, stale sessions/shapes. LUT additionally compares all
  256 table bytes during valid drain and asserts no pending capture overlaps it.
  Independent frozen encoder_layer AND linear_engine reference in LUT regression.
  Both actual WSL source trees rehashed against original pre-build manifests.
  No RTL/manifest drift; README-only updates explicitly recorded as noncompiled.
  Proposals emulated; no R5 target/WCET evidence. No simulation still running.

MATCHED OOC CLOCK EXPERIMENT COMPLETE:
`check_typed200_synthesis_clock.py --name typed200-synthesis-clock-v3
--control-from typed200-synthesis-clock-v2`: same28RTL+generated parameter wrapper,
part/order/options; initial602protectedfiles and420prior-seal entries checked.
Unconstrained control checksum aefdbf25 exactly reproduces frozen parent mapping.
Clean5ns XDC parsed before optimization; native clock query exactly one5.000ns
encoder_ooc_200 clock. Zero synth errors/critical warnings. Mapping7764d478;
encoder LUT66758->65679(-1079), FF51048/DSP579/BRAM50/URAM36 unchanged.
Same5ns analysis: control -0.387/+0.036 vs clocked+0.855/+0.036ns. Hash-bound
`typed200-synthesis-clock-v3/clock-experiment-review.json`. OOC estimate lacks
I/O delays/HD.CLK_SRC; no physical/Fmax/WCET claim. Worst becomes read-address
update via burst sizing,16levels/6CARRY8; wait for placement before chasing it.
v1 path alias failure and v2 unsupported XDC if/puts rejection preserved; v2
clocked process tree was verified and terminated. v2 clean control reused exactly.

FULL CLOCK-FLOW CONTROL SYNTHESIS COMPLETE:
`build/v2/typed200-clock-physical-v1/`, unchanged sealed typed200_flush RTL.
Proper OOC-only pre-hook and post-hook clock assertion; project cache disabled
without clearing old caches. Integrated encoder mapping e2d57667,65732LUT,
51048FF/579DSP/50BRAM/36URAM; OOC+0.855/+0.036ns. Slightly different from standalone
mapping; use actual full composition below for physical conclusions.
Full synthesis exit0,68498LUT/53651FF/579DSP/50BRAM/36URAM. WNS+0.624ns vs
frozen FIFO -0.612ns; WHS-0.087ns. Real PL0 5ns/PL1 10ns retained; no artificial
OOC clock leaks into fulltop. Unconstrained internal endpoints/multiclocks zero;
eight synthesis no_clock pins require rechecking after opt as in parent.
`synthesis-review.json` binds exact30staged/28compiledRTL, hooks, clocks and DCP.
Initial review parser expected report_clocks column order rather than timing-
summary waveform/period order; it blocked placement, old parser/rejection receipt
preserved. Corrected exact waveform/period/frequency check passed; no native rerun.

PLACEMENT/AUDIT COMPLETE for typed200-clock-physical-v1: final setup+0.371ns,
hold-0.087ns (do NOT use intermediate placer+0.420). All12 check_timing categories
zero afteropt, CDCsafe, retained epoch/publication/GPIO,39vendorXPM exceptions,
no LUTAR and FIFO asyncflops0. `placement-review.json` ROUTEFALSE: preserved
+0.500ns admission margin not met. No routing, package or board action.
Critical path CHANGED: contractbank[6][2] -> typed gate last_request[24]/CE,
24logic levels/21CARRY8,4.252nsdata(2.277logic/1.975estimatedwire). Typed validation
is now the evidence-led priority, ahead of noncritical counters/LUT capture.

NEW SEPARATE `rtl/v2/candidates/typed200_profile_tree/`: only typed_intent_guard
changes. All256 SHA bits compared in32bytes,4groups,finalreduction; KEEP boundaries
prevent a single serial reduction. NO registers, truncated digest, check bypass,
new latency or deadline/epoch change. Formal sequential equivalence PASS in
`typed200-profile-tree-formal-v2`: all guard outputs/private history/limit state
match at every samplededge for arbitrary frames/proposals/corestatus/quiet/reset.
First harness v1 had unsupported private hierarchical references and missing
check lowering; preserved, no functional counterexample. v2 uses explicit proof-
only observation ports on copied modules, no candidate source instrumentation.

ACTIVE full profile-tree integration `typed200-profile-tree-integration-v1`
via `simulation/v2/run_typed200_profile_tree.sh`, Verilator5.040. Do NOT restart.
ACTIVE small matched registered-contract mapping probe
`check_typed200_profile_tree_ooc.py`, build `typed200-profile-tree-ooc-v1`, control
then tree sequentially. Probe source flops model existing AXIL bank and are NOT
an added candidate pipeline stage. Inspect actual carry depth/KEEP retention.
No other native job is active. Keep LARGE native jobs sequential (13.79GiB RAM).
Probe profile_tree COMPLETE: target contract path25->17levels,21->10CARRY8,
data3.494->3.359ns, slack1.380->1.515ns. Probe only; no full-FPGA/Fmax claim.
NEW separate `typed200_validation_tree` retains that full256bit tree and KEEP
boundaries around existing sequence/zero-budget/empty-contract decisions, preventing
flags being folded serially through wide compares. Only guard+publication_gate
change; no check removed, no new state/latency/deadline pause. Full sequential
old/new GUARD AND GATE equivalence PASS `typed200-validation-tree-formal-v1`.
ACTIVE `typed200-validation-tree-integration-v1` and small mapped probe
`typed200-validation-tree-ooc-v1` (reuses exact verified control/probe, synthesizes
only refined tree). No other native job is active; original profile integration
may still be finishing negative cases. Never restart existing attempt directories.
Validation-tree mapped probe COMPLETE: SAME17levels/10CARRY8/3.359ns/+1.515ns
as simpler profile_tree. No additional mapped timing gain; preserve refinement,
do not choose extra changed gate source without evidence of benefit.
Profile-tree FULL regression COMPLETE:5400words/14pairedcompletions, exactAXI/
output cycles and completion counts/publication ages including negative cases.
Selected profile_tree full SYNTHESIS COMPLETE exit0:68552LUT/53651FF/579DSP/
50BRAM/36URAM. Full estimated setup-0.078/hold-0.087ns, WORSE whole-design
synthesis setup than unchanged clock-flow control+0.624ns despite local probe gain.
New limiting synthesized path is SmartConnect read FIFO empty_r -> encoder status
CE,15levels,4.725ns data/3.667ns estimatedwire(77.6%). Do not claim global gain.
Exact source/clock review PASSED (real5ns/10ns, no OOC leakage,28compiledRTL).
ACTIVE SELECTED PLACEMENT `typed200-profile-tree-physical-v1`
via `build_typed200_profile_tree_physical.py --stage place`. Only this LARGE
native job is active. Validation-tree full integration ALSO COMPLETE:5400words/
14pairedcompletions, normal/negative cases pass with identical counts/cycles.
No simulations remain active. Do not restart completed attempts.
NEW IMMUTABLE `docs/research/2026-10-15-typed200-validation-functional-evidence.json`
fixes profile_tree AND validation_tree sources/creators/proof/probe/integration
runners and receipts. Both actual WSL stage trees rehashed; ALL copied files,
including manifests/README, match pre-build hashes. Do not edit its source/
evidence maps. This is functional/probe evidence only, not physical qualification.
Next: finish selected profile_tree full synthesis/exact source-clock review,
placement and audit on corrected flow. Let measured paths determine remaining counter/
LUT physical priority; their exact functional sources remain sealed. Never claim
300MHz or useful-success bound from OOC/estimated timing. Final preservation/
evidence seal and detailed report/ranked-plan update remain required.

Typed deadline/epoch/live error/quiet checks, contract/head/R5v8 unchanged. Guarantee
remains conditional stable local terminal byD uninterrupted PLcycles; successful
inference, ARM/DDR/MMIO WCET and external delivery remain unproved. Reviewed R5
loader/clock/TCM/ECC/exclusive ownership and target goldens remain required. Board
last observed stock overlay, qualified package intact; no further board actions.
No automation was recreated. Continue authorized local work autonomously.

## Latest completion: reset-safe typed200 FIFO and board checks (2026-10-15)

READ `docs/research/2026-10-15-typed200-synchronous-flush.md` and immutable
`docs/research/2026-10-15-typed200-flush-validation.json` first. This is the newest
candidate milestone. Earlier qualified baseline and sealed prototypes stay frozen.

Board checks: SSH ubuntu@192.168.0.239 authenticated against previously saved
host key. Hostkria/kernel6.8.0-1036-xilinx, boot26b8c4ae-d5b6-4311-b8ef-d986df3156f4,
eth1UP, heartbeat enabled, no failed systemd services. STOCK overlay
k26-starter-kits_image_1 is loaded; System One has NOT been reloaded. Four installed
qualified-package files match original qualified archive SHA
ECD320163BAA3C289C64E069186497974D4703039DF4A455BC8620D357D7EC99 exactly.
Evidence `build/v2/board-readonly-recovery-20261015-v1/`. Only read-only SSH/status/
package hash checks: no reboot, MMIO, remote writes, FPGA/R5 programming or saved
credentials. Earlier outage cause unknown. No further board restart was required.

New SEALED candidate `rtl/v2/candidates/typed200_flush/` clones sealed typed200;
only existing result_streamer.sv changes, plus new common/stream_fifo_sync_clear.sv.
Dedicated FIFO reset/descriptor clear are synchronous; START/reset suppress valid.
Reset must span a sampled edge and release synchronously. Numerical contract,
core arithmetic, deadline/epoch logic andABI unchanged. No old sealed source edited.

Functional evidence COMPLETE:
- Unitv3: actualDEPTH8/WIDTH128, L3/4/5 (5 is composed profile),65673comparedcycles,
  54descriptor replacement/reset scenarios, held/random stalls, subcycle clear,
  sampled clear priority. Immutable parent streamer is the reference.
- Integrationv2:5400goldenwords,14pairedcompletions/launches; every drivenAXIcycle,
  core/request count andoutput unchanged through T1/2/3/4/5/12/64/128 andnegative
  delayed/error/late responses, deadline/quarantine, stale session andshapes.
  Reference uses independent frozen parent encoder_system+streamer explicitly.
- Actualsize8x128 liveFIFO induction PASS in live-formal-v3, arbitrary sampled
  data/read/write/clear INCLUDING reset/clear cycles; only first-edge reset and
  single sampledclock assumptions. No wholeencoder/analogglitch proof claimed.
- ModuleOOC andfullplaced/routed mapping: ZERO async-reset/preset FIFO flops;
  202FIFO cells retained in full design; LUTAR-1 removed.64DSP async-driver
  advisories remain. Earlier failed andweaker attempts preserved andhashbound.

Physical evidence COMPLETE `build/v2/typed200-flush-physical-v1/`:
Synthesis WNS-0.612ns/WHS-0.087ns. Initial placement -0.066/-0.074,4setupendpoints;
originalplacement-review routefalse andDCP preserved. Separate physical-only
Explore optimization ->+0.067/-0.117, postplace-review routeapprovedtrue from
postplace-opt-v1/optimized.dcp. No RTL/clock/exceptionchanges. Admission parser
initially doublecounted reportsummary/details and blocked; correctedto12unique
zero categories, failedemptyattempt preserved. Native route ran only after review.

FINAL ROUTED STA at200MHz: WNS0.000ns, WHS+0.010ns, TNS/THS0, allconstraintsmet
at reportprecision. ZERO REPORTED SETUP MARGIN; NOT hardware qualification.
No unrouted nets/overlaps; all12 check_timing categorieszero, CDCsafe, defaultDRC
no error/criticalwarning (DSP pipeline + RTSTAT-10 advisories retained).
Final64346LUT/52185FF/579DSP/50BRAM/36URAM. No bitstream/package generated.
Routeworstpath: SmartConnect read-state ->linear LUT data,3levels,4.769nsdata;
4.330ns(90.8%)interconnect, m_axi_rdata[11]fanout166/single-netdelay3.289ns.
Nextpath +0.001ns: inheritedrequeststate ->encoder-clocktelemetry,15levels.

NEW TIMING-FLOW EVIDENCE: native Vivado inspection of actual encoderOOC DCP finds
Stored OOC clocks:0. Its synthTcl lacks explicit create_clock/read_xdc and log says
no constraint files. Full composed design DOES have real5ns clock andcomplete
coverage; baseline routedSTA remainsvalid. Evidence encoder-ooc-clock-audit/.
This motivates a controlled explicit OOC-clock synthesis experiment on identical
RTL before claiming benefit or adding broad compute pipelines.

Final seal PASS: all602 protected baseline files,qualifiedarchive,andall FOUR
prior seals' sources/docs/evidence unchanged. R5 v8/head/numerics unchanged;
no target execution, WCET/successful-inference or external-delivery certificate.
All native jobs finished; no live session to resume. Existing S: alias unchanged.

NEXT PRIORITIES (report ranks evidence/effort/risk):
1. Explicit OOC synthesis clock experiment at declared target; prove constraint
   active DURING synthesis, preserve sameRTL andallpriorbuilds.
2. AXI response capture/local load-data replication: finalrouteis90.8%wire.
   Preserve burst/errors/live-drain; measure declared cyclechanges/rebudget D.
3. Observational counter/completion retiming: preserve rawcounts andnativecore
   behavior; retain current live traffic/error veto,never use stalequiet as proof.
4. Reviewed R5 loader,ownership/clockprofile, targetgoldens andbounded DDR/ARM
   service/WCET experiments. Stockboard remainsuntouched untilauthorizeddeployment.
Qualified200 remains the ONLY hardware-qualified implementation; no automation
was recreated. Frozen parent typed200 route remains+0.008/+0.010, with its old
resetwarning documented as historical, superseded only by this unqualifiedfix.

## Latest completed continuation: typed200 route and R5 ELF (2026-10-15)

Read `docs/research/2026-10-15-typed200-physical-r5.md` and its immutable
`2026-10-15-typed200-physical-r5-validation.json` first, plus
`firmware/typed200_r5/README.md` for the loader/service contract.

Independent `build/v2/typed200-physical-v1/` is COMPLETE: synth/place/route exit0.
Final RECOMPUTED routed STA at200MHz: WNS+0.008ns, WHS+0.010ns, TNS/THS0,
zero unrouted nets/overlaps; all12 clock/delay/loop check categories zero. CDC
all defined-clock paths safely timed. Default routed DRC has no error/critical
warning; DSP pipeline advisories and RTSTAT-10 no-routable-load warning retained.
DO NOT confuse router intermediate+0.001ns estimate with final STA+0.008ns.
Resource64398LUT/52785FF/579DSP/50BRAM/36URAM. 29stagedRTL,27compiled: legacytop
and legacywrapper copied for provenance but not compiled. All input/snapshot
hashes and exact exclusion set verified. Typed CSR0xA0000000, deployment GPIO
0xA0001000 reset0, activePL0 200MHz; unusedPL1 100MHz. Existing S: alias must NOT
be recreated/changed. No package/bitstream/hardware programming or automation.

Placed audit retained192epoch/2687publication/92GPIO cells. All39 timing exceptions
are scoped vendor XPM reset/synchronizer constraints. Physical reviews/checkpoints
are hash-bound in placement-review.json and route-review.json. Both approve only
research timing stages, NOT deployment. Final route limit: linear out_tiles[0]
through completion logic into epoch complete/done_seen controls,16logic levels.
The placed critical path was profile match->gate outcome CE,25levels/21CARRY8.

IMPORTANT unresolved assurance gate: methodology LUTAR-1 is inherited
result_streamer FIFO `reset || start` feeding async pointer resets. Not waived;
needs separate synchronous flush/reset candidate, exact data/cycle/drain tests,
and reset/fault review. 64 other methodology advisories are async DSP drivers.
Next timing-margin candidate should register read-only completion/quiescence
observation and stage contract/identity validation, retaining fault identity and
explicit added publication latency. Never delay/pause independent deadline.
Combine verified counter fix only in another candidate, not these sealed sources.

R5 reset-entry ELF v8 COMPLETE: `build/v2/typed200-r5-elf-v8/`. ASan/UBSan policy
and ten SHA length vectors plus full model pass. Parsed audit PASS:
`build/v2/typed200-r5-audit-v3/`; five LOAD segments wholly in split TCM, no RWX,
no unresolved symbols, corrected typed200_v2 transport only. Code/constants16080B,
BTCM work49640B, SVCstack8192B, shared384B; head call-chain compiler frames2112B.
Low vectors/VFP/MPU initialized, normal prediction and AMD DBWR erratum mitigation.
Service validates IDs/shapes, copies IDs before admission, observes native epoch,
runs frozen scaled head, validates canonical terminal; fault/deadline halts reuse.
Final software zeros terminal padding and serializes fields explicitly; poisoned
padding tests pass. Host AND target shared-ABI assertions pass.

No target execution, loader installation, boot/remoteproc changes, successful
inference WCET or external-delivery guarantee. Loader must initialize splitTCM/ECC,
fresh config AFTER ELF load, fresh PL/session, exclusive model/program/buffer/MMIO
ownership, PS clocks and reset privileged ARM entry. R5 MPU/attestation alone does
not enforce other-master exclusion. Byte-load hidden-copy disassembly motivates
a later versioned aligned-word-copy comparison before PL pooling.

Final seal PASS: all602 protected baseline files and all three previous validation
seals' sources/docs/evidence rehashed unchanged. Qualified200 remains the SOLE
hardware-qualified system. All native jobs completed; no live Vivado session to
resume. Next: separate reset/timing-margin candidate, reviewed loader/ownership
profile, R5 golden-vector target run, then bounded DDR/ARM service experiments.
Board network/boot recovery is confirmed above; stock overlay is loaded, with
qualified System One package preserved but not reloaded.

## Latest entry point: typed200 C/RTL transport verified (2026-10-15)

USE `firmware/typed200_v2/` for SHA-bearing service operations. Read
`docs/research/2026-10-15-typed200-transport-review.md` and its sealed transport
validation first, then the native integration entry below. This supersedes older
ARM transport recommendations while preserving every prior sealed artifact.

Final cross-language review found a digest serialization mismatch: the frozen C
helper packed initial canonical SHA bytes little-endian into register 0, while
RTL uses the numeric digest's least-significant 32-bit word first. Earlier tests
checked each representation separately. Wrong profiles fail closed, but the old
SHA transport is NOT interoperable. No frozen file or numerical contract changed.

Versioned successor implements explicit numeric digest conversion for submission,
active identity observation, proposal and terminal readback. Use `ti200_start`,
`ti200_admission_observe`, `ti200_copy_hidden`, `ti200_propose`,
`ti200_terminal_observe` from typed200_v2. Do not use historical ti_mmio_start/
propose/observe or the original typed200 SHA methods. Session-only provision/ACK
remain compatible. Old helper symbols exist in the relocatable library; the
future privileged BSP must bind the versioned SHA methods explicitly.

PASS `build/v2/typed200-transport-v4/`: compiled C known numeric SHA words,
canonical terminal decode, ASan/UBSan and R5 link with no unresolved symbols.
Actual C output `wire-frames.hex` replayed through the REAL RTL endpoint in
`build/v2/typed200-c-transport-v2/`: Accepted label 17, exact eight numeric digest
readback words, 668 writes / 91 reads / 15 valid admissions. Final transport JSON seals
new sources/receipts and rechecks all prior source/evidence hashes and 602 protected
files. Candidate RTL remains identical to its sealed 5400-word/14-completion run.
No active builds/tests, physical build or board actions. Existing target execution,
BSP/TCM/CDC/physical closure and WCET gates below remain open.

## Current entry point: typed200 native integration completed (2026-10-15)

User said proceed with next P0. Completed and SEALED a separate RTL service
candidate in `rtl/v2/candidates/typed200/` directly from the 23-source qualified
snapshot. Read `docs/research/2026-10-15-typed200-integration.md`, its sealed
`2026-10-15-typed200-validation.json`, candidate README and
`firmware/typed200/README.md` first. Earlier entry-point sections are historical.
No new FPGA physical build, board, boot, remoteproc or automation action.

New top: `typed200_encoder`; ABI 0x54590201. Sole typed AXI-Lite start path; fixed
program/ID/result buffer addresses; H384, T1..128, positive contiguous selected
row slice. Native model/deployment permission is a TRUSTED root input that must
remain asserted through the owned interval; model bytes are not authenticated by
request hash. Stage shape at 0x1c/0x78, read admitted shape 0xc4/0xc8, native
status 0xcc and original-edge encoder/request cycles 0xd0/0xd4. Legacy descriptor/
start CSR sequences cannot bypass admission. Deployment/DDR buffer ownership,
valid token IDs and segment semantics still require trusted BSP/software binding.

All 22 unchanged copied sources match the qualified snapshot exactly, including
all arithmetic/pipelines. The copied memory port adds only a read-only live
`drained` output: FSMs, outstanding reads/delivery/FIFO, write responses, pending
request slots, upstream requests and active AXI signals. No diagnostic telemetry
feeds correctness/control. New epoch tracker captures native session/request,
retains core/AXI errors, and waits for raw done + idle + drain before completion.
Original qualified legacy top/memory port/package are unchanged and uninstantiated
by the new service; the copied legacy top remains provenance/regression support.

PASS `build/v2/typed200-integration-v2/`: 5400 golden output words, 14 paired raw
completions/launches (8 normal L12 shapes + 6 repeated T1 fault/drain scenarios).
Candidate and qualified arithmetic/original memory port receive identical memory
response streams; EVERY driven AXI cycle, busy/done and raw completion result
matches. Normal tokens 1,2,3,4,5,12,64,128. Encoder/request counters match at the
original completion edge; terminal age is separately reported and includes testbench
ARM proposal traffic. Do not compare unpaired saved random-stall counts as an
architectural cycle difference or mistake scripted publication age for R5 WCET.
First attempt v1 failed a TB counter comparison sampled after FINISH; corrected
reference-edge capture, no functional RTL fix. Failed evidence remains preserved.

Real-encoder negative tests pass: held final B prevents native completion despite
raw run_done; early Accepted fails closed; late BRESP/RRESP errors prevent Accepted
even when data matches; held-B timeout at exactly 3,000,000 cycles; late B/proposal or
next-request attempts cannot reverse quarantine; stale session and invalid shapes.
ARM proposals are emulated in the RTL test, not executed on an R5.
PASS endpoint-directed-v1: 636 writes / 80 reads / 14 valid admissions, including prior
atomic/backpressure/WSTRB suite plus legacy bypass, environment block, shape
validation and immutable owned shape. New epoch and endpoint inductive proofs
pass in `typed200-epoch-formal-v1/` and `typed200-endpoint-formal-v1/`; pinned
YoWASP package 0.70.0.0.post1259, first-edge reset/single-clock assumptions. Unchanged
inner gate/guard proofs reused ONLY by exact source hash. No whole-core formal,
physical/CDC or ARM WCET proof is claimed.

Additive `firmware/typed200/` driver passes host ASan/UBSan and R5 relocatable link
in `build/v2/typed200-firmware-v2/`. No undefined symbols; .text3712/.rodata7676/
.ARM.exidx120 bytes. New stack reports: submit 40, identity observation 168, copy 16
bytes; prior nested head/bridge 1688 excludes callers/interrupts/BSP. Driver checks
ABI/profile/session/shape, confirms active identity and immutable owned shape,
then requires native complete/success/quiet/environment/no-quarantine before the
bounded hidden copy. DMB barriers order MMIO/status/DDR access. An all-ones count
is rejected without unsigned-wrap or out-of-bounds access. Original frozen
head/bridge/mailbox sources are unchanged. 67 existing host guardrail tests pass.

Candidate has 28 sealed RTL sources; `scripts/v2/kr260/create_typed200_candidate.py
--verify` passes. `scripts/v2/seal_typed200.py` binds staged source hashes, receipts,
reports and sources; validation JSON exists, refuses overwrite. All 602 protected
baseline/package/recovery/numerical files, both prior sealed frequency candidates,
placement evidence and previous typed milestone hashes are unchanged. No active
build/test remains. Never edit/reseal this candidate; create a successor for changes.

NEXT gates: separate block-design/clock/reset/CDC/constraints composition and
physical 200 MHz setup/hold closure; a bare-metal R5 ELF/TCM linker map, FPU/interrupt
policy and Device/noncacheable/coherent mappings; exclusive input/model/result
ownership and token/segment validation in the privileged submit path; actual frozen
head/bridge/terminal consumption/recovery on target; bounded memory service,
transfer/head WCET, clock ratio and guaranteed minimum PL frequency. Terminal
failure by D PL cycles is distinct from guaranteed successful inference, semantic
truth and external delivery. Compare full hidden transfer (49152 bytes maximum)
with existing PL POOL/raw-LINEAR + R5 scaled selection (72-byte logits) using
matched numerical/latency evidence. Sole hardware-qualified system remains the
original 200 MHz package; counter300 still rejects 300 MHz route admission.

## Current entry point: typed intent assurance milestone (2026-10-15)

User said proceed with typed, timing-guaranteed outputs as the primary priority.
Completed a standalone implementation/verification milestone; NOT integrated or
hardware-qualified. Read `docs/research/2026-10-15-typed-intent-implementation.md`,
`docs/research/2026-10-15-typed-intent-validation.json` and
`firmware/typed_intent/README.md` first. Older status sections below are historical.

Frozen service: existing L12 INT8 image, `intent.atis`, 18 labels, exact integer
pooling/logits and original per-class binary64 scaled argmax/first tie. Contract
SHA256 `8133633315487f8f322ecac49e95e7aca3801d00fccb4b4fba36026c5b2752d2`.
No confidence/OOS rule; reserved score must be zero. Only Accepted carries a label.
Profile extraction seals bytes and refuses overwrite. A separate deployment
certificate must bind actual firmware/bitstream/model/environment/boot identity.

New `firmware/typed_intent/` provides bounded head, single-request bridge and
non-polling MMIO transport with ARM barriers. Host sealed-v4: 647 cases, 11520
exact logits, 640 exact decisions, all 128 pool counts, ASan/UBSan and directed
bridge/mailbox checks. 40 fixture decisions differ from raw-logit argmax: retain
per-class scaling. Existing 67 host contract/timing/candidate tests pass.
R5 sealed-v4: clang 16 Cortex-R5 hard-float compile and relocatable link, no
undefined symbols; .text2496/.rodata7676/.ARM.exidx96 bytes. Nested head/bridge
stack 1688 bytes excludes BSP/caller/interrupts. No bootable ELF, TCM map, target
execution or WCET certificate exists; no board/boot/remoteproc changes.

New `rtl/contracts/typed_intent_v1/` contains a fixed-profile/session guard and a
standalone 256-byte AXI-Lite endpoint, in ONE PL clock domain. Atomically staged
full frames, independent AW/W, byte strobes, held result until ACK, monotone
consumed request IDs (including INVALID), fresh session after coordinated reset,
validated encoder-launch pulse, matching successful core epoch and live quiescence
required for Accepted. Fault/timeout quarantines until coordinated recovery;
ACK cannot release it. Proposed MMIO window has NO assigned/deployed base address.
AXI launch-v4 tests pass464 writes / 58 reads / 13 valid launches, including R/B responses
blocked across deadline, missing/partial frames, reserved bits, stale sessions,
core failures/identity, replay, immutable records and late proposals.

Inductive proofs pass:
- `build/v2/typed-formal-gate-final-v5/`: original unchanged publication gate's
  safety, progress, deadline boundary and held canonical records.
- `build/v2/typed-formal-guard-observed-v2/`: session, consumed-ID relation,
  valid launch and accepted-proposal prerequisites. Formal-only observation port
  feeds assertions, not behavior; copies and hashes preserved.
- `build/v2/typed-formal-axil-guarded-v3/`: AW/W capture and held B/R protocol
  properties, not full endpoint functional proof.
Assumptions: first-edge reset, single synchronous clock. No physical/CDC/ARM/DDR
proof or successful-inference/host-delivery deadline guarantee. Failed/intermediate
attempts stay preserved. Early induction failures needed stronger state invariants;
no functional RTL fix was used to conceal a failure. Formal tool package observed locally: yowasp-yosys 0.70.0.0.post1259;
Yosys core version is saved in the adjacent toolchain-query.log. The current runner
resolves the package without a version pin; pin this observed version when archiving
a portable reproduction environment. Final receipts/source hashes
are sealed by `scripts/v2/seal_typed_intent.py` in the validation JSON.

NEXT P0: isolated typed200 integration with trusted memory drain/error/epoch
signals and same-clock publication endpoint. Actual encoder `OUT_BEAT -> FINISH`
on final W beat precedes memory-port `WRITE_RESPONSES` completion. `run_done` or
`!busy` cannot certify drained successful DDR writes. The current candidate's
supervisor checks run_result status while memory_error is a separate sticky output.
Expose memory-port live idle/drain (pending slots, read FSM/outstanding/delivery/
length FIFO, write FSM/responses, output buffers), latch errors/epoch and inject
late/error B/R responses before permitting Accepted. Do not use delayed diagnostic
telemetry counters. Only validated `admitted` may launch encoder ownership;
complete invalid START frames publish INVALID without launch.

The typed controller must exclusively own encoder starts/descriptors, program/model
identity and result buffers; validate shape/rows before admission and prevent legacy
CSR bypass. Core status/epoch inputs must come from trusted hardware ownership logic.
Then link R5/TCM and define interrupts/FPU/device mapping; compare full R5 head
(49KiB hidden transfer maximum) with existing PL POOL/raw-LINEAR plus R5 scaled
selection (72-byte logits). Bound transfer/DDR/WCET, clock ratio and guaranteed
minimum PL frequency before certifying successful inference or wall-clock timing.
Preserve single-request/exclusive buffers and fresh boot sessions; no boot/reset
or board qualification has been performed. Research contribution is scoped typed
terminal availability with explicit success/failure assumptions, not semantic truth.

Preservation audit rechecked all 602 baseline/package/recovery/numerical files,
both sealed candidate source sets and placement-review evidence, prior prototype
and implementation hashes. No FPGA synthesis/place/route was launched this turn.
Qualified original 200 MHz package remains the sole qualified system. counter300
still REJECTED for 300 MHz route; do not merge this standalone prototype into its
sealed sources, change the qualified package, or recreate completed automation.

## Current entry point: counter300 and typed timing contract (2026-10-15)

User authorized a separate performance-counter timing successor, exact counter/
output/cycle verification, synthesis and placement; typed timing-guaranteed
outputs are now the primary architectural priority, including ARM use.

Candidate: `rtl/v2/candidates/counter300/`, feature `0x5397ffff`, 25 sealed RTL
sources. Only the parent top changes and `performance_telemetry.sv` is added.
One-cycle registered telemetry inputs remove global request decode from the
outstanding-beat arithmetic. No encoder/AXI control feedback or arithmetic changes.
Counters drain one idle edge; MMIO 0x70 bit0 pending, bit1 DONE && snapshot_ready.
Existing qualified driver/package guards remain unchanged; no deployment support.

Directed telemetry verification passed 12014 edges, including max bursts,
simultaneous transfers, drain/restart/reset, negative deltas and 32-bit rollover.
Full assertion-enabled regression COMPLETED in `build/v2/counter300-regression-v2/`:
50 cases, all 500 counters, every output word and request/core cycles exactly
match frozen reference. Snapshot readiness and deadline/quarantine checks pass.
First attempt in `counter300-regression/` was stopped/preserved (status143): an
extra testbench MMIO read shifted random-stall phase. V2 is passive; RTL unchanged.
67 host contract/candidate/timing tests pass. Receipt and implementation record:
`docs/research/2026-10-15-counter300-validation.json` and `...-implementation.md`.
602 protected files AND prior placement-review hash-bound artifacts remain intact.

H384 synthesis AND diagnostic placement COMPLETED. Mapping retains all 27 telemetry
input-cut FFs and prior 512 query/128 select/70 supervisor FFs. Synthesis is
LUT67627/FF53266 (+29/+39), same -0.591 ns worst layernorm-address estimate.
Final placed diagnostics (same placement, unrouted): 200 MHz setup +0.886 ns,
250 MHz -0.114 ns, 300 MHz -0.781 ns; hold -0.071 ns throughout. Matched parent
300 MHz setup was -1.011 ns: improvement 0.230 ns, still FAILS target and unchanged
+0.5 ns route-admission gate. Preliminary placer -0.708 ns was an estimate, not
final report. Placed LUT 63568 / FF 52157 / CLB 78.16% / BRAM46 / URAM18 / DSP579.
New worst path: layernorm root[9] -> root[46], data 3.872 ns (logic 1.963 / estimated route 1.909).
No route, bitstream, package or deployment followed.

Read-only checkpoint audit COMPLETED; no active build/audit remains. At 300 MHz:
read_due data1.275 ns/slack+1.852; write_due1.105/+2.038; read_delta3.565/-0.415;
write_delta3.071/+0.010; event counters1.005/+2.189. The old long due path is split,
but the delta-input stage still fails 300 MHz. Do not claim telemetry fully closed.
`build/v2/counter300-encoder384/placement-review.json` explicitly REJECTS routing
and binds reports/checkpoint/audit hashes. Preserve this sealed successor and all
failed attempts. No further Fmax iteration started: typed timing assurance at
200 MHz is now the next priority. The only hardware-qualified system remains the
original frozen 200 MHz package; no R5/boot/remoteproc/board changes were made.

Read `docs/research/2026-10-15-typed-timing-contract-plan.md`. A standalone
`rtl/contracts/typed_publication_gate.sv` prototype (NOT integrated in counter300)
passes 288 deadline-boundary combinations plus identity/enum/score/replay/failure/
quarantine checks in `build/v2/typed-publication-prototype-v2/`. Earlier prototype
compile failure was a dangling-else testbench issue; failed evidence is retained.
Recommended partition: A53/Linux management; R5 bounded head/validator in TCM;
independent PL authoritative typed-result deadline/publication. No R5 firmware,
MMIO/CDC integration, formal proof or hardware guarantee exists yet. Endpoint
availability is distinct from successful inference and Linux/network delivery.
Prioritize a single finite intent head at 200 MHz before broader Fmax iterations.
No board deployment, boot/remoteproc changes or automation recreation authorized
by this local implementation task; preserve baseline/recovery and previous evidence.

## Current entry point: locality300 implementation (2026-10-15 America/Chicago)

The user authorized implementing the strongest path toward 300 MHz and reaffirmed
the distinguishing goal: **timing-guaranteed inference with checked typed outputs**.
Read [the implementation record](docs/research/2026-10-15-locality300-implementation.md).
The earlier review-only restriction applied to that completed task; this task adds
an isolated candidate and verification, never replaces the qualified baseline.

Implemented under `rtl/v2/candidates/locality300/`: consumer-local query-read
replicas, registered local MAC selection, H384/H1024 profiles, and an independent
deadline outcome supervisor. Feature `0x5387ffff`, deadline ABI `0x53595431`.
All 23 public qualified sources and their frozen snapshots remain untouched.
The existing deployment/runtime guards are unchanged; no candidate package exists.
Source origin and sealed hashes: `rtl/v2/candidates/locality300/candidate.json`.
Do not edit/recreate sources in use by a build or replay historical integrations.

`build/v2/locality300-regression/completion-status.json` records completed success:
50 random-stall AXI cases match frozen outputs AND cycles, across H1024 capacity
and H384 actual-model profiles, including partial/query boundaries. The wrapper
also passes an independent deadline interrupt/quarantine check. Standalone
supervisor passes 288 boundary scenarios plus invalid/immutable budget and fault
checks. Host/runtime/package test campaign passed 259 tests (sealed XML). A
separate assertion-enabled H384 run passed all 8 cases with exact outputs/cycles,
including local MAC-select assertions and the wrapper deadline/quarantine check.
The current receipt is `docs/research/2026-10-15-locality300-validation.json`.

The additive `src/sysone/v2/contract_service.py` binds actual model bytes and a
finite output schema; validates enum/segment/BIO/probability/word bounds; emits
accepted/clarify/abstain/deadline/invalid/fault variants; strips prediction payloads
from nonaccepted results and quarantines backend timeout/fault. Schema and model
identities accompany accepted records. Type validity does not establish semantic
truth. Existing `TimingPolicy` and qualified driver remain unchanged.

Deadline distinction: under a running, timing-correct PL clock, the independent
supervisor publishes core completion/fault/timeout at its bounded register channel
without waiting for DDR. Timeout never aborts AXI and remains quarantined until
safe coordinated system recovery. This is not guaranteed successful inference,
Linux/MMIO/network delivery, or proven 300 MHz operation. Successful typed-service
guarantees still require bounded DDR/interconnect, core/head/validator/transport
execution and hash-bound admission evidence; do not substitute measured maxima.

H384 synthesis completed successfully as a tool run, but MISSES 300 MHz timing:
setup -0.591 ns, hold -0.087 ns (unplaced estimates). All intended cuts survived:
512 query-data FFs, 128 local MAC-select FFs, 70 supervisor FFs. Integrated synthesis:
67598 LUT, 53227 FF, 46 BRAM tiles, 18 URAM, 579 DSP. Worst synthesized path is
layernorm width through combinational address multiplication/shared read selection.
Hash-bound `build/v2/locality300-encoder384/synthesis-review.json` admits exactly
one diagnostic placement; it does not admit routing or certify 300 MHz.

The one diagnostic placement COMPLETED (no active build remains). Fixed-placement
diagnostics: 200 MHz setup +0.656 ns, 250 MHz -0.344 ns, 300 MHz -1.011 ns;
hold -0.074 ns at all three. These are unrouted estimates, not qualified clocks.
Placed resources: 63478 LUT, 52253 FF, CLB occupancy 76.93%, BRAM46, URAM18, DSP579.
Worst placed path: linear load-state decode -> performance read_due[31], data
4.216 ns = 1.450 logic + 2.766 estimated routing. Performance-event/counter
retiming is now the first measured follow-on; layernorm row-base addressing is
secondary (synthesis-led). Other paths include AXI readiness and attention.

`build/v2/locality300-encoder384/placement-review.json` explicitly REJECTS 300 MHz
route admission. The unchanged >=0.5 ns placed setup gate was not met. No route,
bitstream or deployment followed. Preserve this rejected evidence and source seal;
a successor revision needs its own manifest/regression and cannot overwrite it.
Tool exit 0 means the diagnostic tool run completed, not timing passed.
No board authentication, deployment, boot-memory change or automation recreation.

## Completed architectural review (2026-10-14 America/Chicago)

The requested documentation-only architecture review is complete. Start with:

- [Detailed architecture review](docs/research/2026-10-14-system-one-architecture-review.md).
- [Source-linked comparison matrix](docs/research/2026-10-14-system-one-comparison-matrix.md).
- [Prioritized experiments, separately scoped future work](docs/research/2026-10-14-system-one-experiment-plan.md).
- [Pinned primary sources and inspected artifact hashes](docs/research/2026-10-14-system-one-sources.json).
- [Reanalysis of saved 200 MHz counters](docs/research/2026-10-14-system-one-profile-analysis.json).
- [Preservation and evidence audit](docs/research/2026-10-14-system-one-preservation.json).

Review findings: the short-request regime nearly fills the existing 128-bit input
interface (2.917 GB/s over requests at 3-8 observed tokens, versus a 3.2 GB/s
ideal interface ceiling); longer requests show near-zero weight-bank wait and
substantial consumer backpressure. These are recomputed saved counters, not a new
board benchmark or physical DDR peak measurement. The final routed critical path
is activation capture to query distribution (4.850 ns data, 4.736 ns routing),
whereas placement exposed opcode selection to DSP input. Routed totals are
63,609 LUT / 51,942 FF / 50 BRAM36 / 36 URAM / 579 DSP, with 81.94% CLBs occupied.
The synthesis totals below remain valid for their stated stage.

The review covers ten primary papers and six pinned repositories, including
actual Scala/HLS/host/configuration artifacts. It flags publication table errors,
estimated/unspecified power boundaries, simulated results and a public decoder
host counter that includes prompt tokens. No unmatched encoder/decode speedup is
claimed. Recommendations separate encoder efficiency, 300 MHz closure and a new
generative executor; numerical exactness is distinct from model quality.

No RTL/software baseline edits, builds, deployment, board authentication,
qualification reruns, training, commits/pushes or automation recreation occurred.
The qualified 200 MHz package, frozen sources, model/numerical baselines and local
125 MHz recovery remain preserved. Future experiments are proposals, not started
jobs. Continue from the experiment plan only under a separately scoped request;
do not replay integration or completed qualification scripts.

## Authoritative hardware milestone and original review brief

The 200 MHz hardware milestone is COMPLETE. Start with
[the architecture review handoff](docs/research/architecture-review-handoff.md).
It consolidates the verified hardware state, matched 125/200 MHz performance,
primary evidence paths, the two KV260 literature targets, review deliverables and
preservation constraints. The architectural review and literature research are now
documented above; no new RTL edits, builds or board deployment have been requested.

Authoritative hardware receipt:
`build/v2/kr260-opt-attention-context-capture-large/hardware-qualification.json`.
Matched performance:
`build/v2/context-capture-board-validation/performance-comparison.json`.
The overnight automation was deleted. Authentication is no longer blocked;
qualification completed and the authenticated connection was closed. No
credentials belong in the new-chat prompt or documentation.

**Historical entries below preserve the chronological audit trail.** Older
statements about pending authentication, active jobs, incomplete qualification or
125 MHz-only operation are superseded by the completed milestone summary and
hash-bound receipts. Recheck actual processes before any future build action.

Overnight automation kr260-overnight-optimization was deleted after verified milestone completion. No Vivado or transient board-authentication process remains active.


## Milestone complete: frozen 200 MHz H1024 candidate hardware-qualified

Human-authorized transient authentication succeeded; credentials never saved in
files/reports. Board initially ran stock k26-starter-kits; guard refused deployment.
Preserved that attempt, verified installed qualified125MHz recovery hashes and
unchanged256MiB reservation, restored125MHz/L12 image and checked all8smoke cases
bit-exact before candidate deployment. Then existing rollback workflow installed
separate sysone-v2-attention-context-capture and confirmed ID53595332/BUILD20804004/
features5377ffff, PL0/PL1 both199999998Hz. All8H1024 lengths1/2/3/4/5/12/64/128,
4head32 query-group lengths1/3/12/128,8realL12smoke cases and350frozenL12evaluation
cases passedbit-exact. Strict local reviewer independently matched hidden/ID
hashes to all350frozen references and allsynthetic output hashes to packaged
fixtures, reverified23RTL hashes and testedarchive SHA. Final33916928byteL12model
restored/readbackexact after tests; candidate remains loaded at200MHz. Qualified
125MHz recovery files remain unchanged and memory recovery app remains installed;
no boot-memory or boot-default changes. Authenticated connection closed afterward.

Legallyrouted200MHz setup+0.101ns/hold+0.010ns;122669/122669netsrouted,0errors.
Hardwareproof: build/v2/kr260-opt-attention-context-capture-large/hardware-qualification.json.
Reports: build/v2/context-capture-board-validation (initial failed attempt also
preserved). Testedarchive build/v2/kr260-app-attention-context-capture-large.tar.gz
SHAecd320163baa3c289c64e069186497974d4703039df4a455bc8620d357d7ec99.
Immutable packaged build.json hardware_qualified:false is preserved as built;
separate hash-bound hardware-qualification.json records completed board evidence
without changing the tested archive. No300MHzclosure/qualityimprovement/hardlatency
claim. Sixteen query lanes still carry measured scheduling tradeoff; no free cycles.

Frozen350suite measured mean11.01110ms/max38.25647ms at actual199999998Hz, descriptive only.
Full200MHz L12smoke128token encoder39.79ms versus restored125baseline60.31ms for
same deterministic check; capacity fixtures and frozen350 results establish exact
outputs, not improved model quality. SlowerARM integer-reference checks account
for validation waiting, separatefrom FPGA execution milliseconds. New auth helper
blocks existing-evidence reruns before remote actions. No commits/pushes/training.
Priority milestone genuinely complete; stop overnight optimization reminder to
avoid further token spend. Preserve all artifacts and seven older rejected builds;
300MHz remains future separately scoped work, not launched.


## Candidate loaded at 200 MHz; larger-capability hardware cases passed

Qualified125baseline restore/readback and all8L12smoke lengths1/2/3/4/5/12/64/128
passedexact. Existing rollbackworkflow thenloaded new separateapp
sysone-v2-attention-context-capture, ID53595332/BUILD20804004/features5377ffff,
PL0/PL1 both199999998Hz,256MiBreserved0x60000000 intact. All8H1024frozencases and
all4head32query-group cases passedbitexact onhardware. L12model33916928bytes
restored/readbackexact; candidateL12smoke through12tokens passedexact,64/128 ARM
integer-reference checks pending, then350frozen-suiteevaluation. Persistent
transientauthsession38613 isactive; do notduplicate/reauth/rebuild. Fullmilestone
notcompleteuntilremainingchecks/retrievedreports reviewed. Remote reports
/home/ubuntu/kr260-context-capture-validation-20261015-024402-retry, consolealsoin
/home/ubuntu/kr260-context-capture-20261015-024402/hardware-qualification.log.
Initialstock-app failure preserved locally, no credentialrecorded. Qualified125
recoveryfiles/model/bootreservation preserved. Currentstageinprogress.json.


## Board authentication succeeded; qualified 125 MHz baseline being restored

Human supplied authentication transiently; never recorded/repeated in files or
reports. Initial helper authenticated/uploaded exact admitted archive but stopped
before changing FPGA: board actually had k26-starter-kits.bit.bin loaded. Initial
failed receipt/console preserved as receipt.initial-stock-app.json and console.
initial-stock-app.log. No cause inferred for changed loaded app. Persistent
transient authenticated tool session38613 now active; no parallel qualifiers.
Known host verified. Qualified125frontier installed file hashes match recorded
bit4b0dae37...59430a; bootreservation60000000-6fffffff intact. Switched stockapp to
qualifiedsysone-v2-frontier, live124999999Hz; L12model33916928bytes restored and
readbackexact. Baselinechecks1/2/3/4/5/12/64tokenbitexact;128tokenARMreferencepending.
This CPU reference calculation, not FPGA execution, is the current wait. Then run
existing uploaded rollback qualification bundle against separate200MHzapp and
retrieve exactH1024/head32/L12smoke/frozen350eval reports. No candidatehardware
claimyet. Auth helper now rejects existing evidence BEFOREauthentication/remote
commands, preventing duplicate deployment on rerun. Frozen RTL/package untouched.


The app terminal snapshot showed a separate PowerShell prompt, not the agent PTY.
Cancelled agent password prompt26150 beforeauthentication toavoidduplicates. User
shouldrun `python scripts/v2/kr260/qualify_context_capture_board.py` in their local
repo terminalandenterthepasswordthere. No credentialsstored/sent, no remotechange.
Thisisa missingauthenticationblock,not anadditionalpermissionrequirement. Script
willauthenticate/uploadexactbundle/validateusingexistingrollback workflow then
writebuild/v2/context-capture-board-validation/receipt.json. Checkreceipt before
anyrepeat; no package/buildduplication. Awaithumanaccess whilepreservingartifacts.


## Legal 200 MHz route and package passed; board authentication pending

Route/export completed23:08:45UTC. Actual200MHz setup+0.101ns/hold+0.010ns,
zero failing endpoints,122669/122669routable nets fullyrouted,zero routingerrors,
zero unconstrainedinternalendpoints; all userconstraints met. Independent strict
check_routed_evidence.py passed. Nativephysopt30.948s/route349.809s. Reviewgap
about19minutes aftercompletion isnotcompute. Matchingcanonicalbit/XSA/source/
fixtures validated bystrictpackage_app.py; separate newarchive created,notuploaded.
ArchiveSHA256 ecd320163baa3c289c64e069186497974d4703039df4a455bc8620d357d7ec99.
BitSHA256 a8c5eb4b21c6209f732cb03a19045bb52768f4d6f51e045c913b103a6a6ada87.
XSASHA256 1da7bdc11e136613a4e0c6591748283ea1cd418b3bc169a0a6302a5f47a93afe.
Route-package-review.json bindsallartifacts. Packagehardware_qualified remainsfalse.

Board192.168.0.239 isreachable butSSHBatchModeavailableauthrejected; no keyavailable.
No boardstate/model/boot change occurred. Preparedqualify_context_capture_board.py
usesgetpass transientmemoryonly,knownhostverification,SFTPexactarchivehash,existing
rollbackdeploy_frontier.sh plusH1024/head32/L12frozen350casevalidationandmodelrestore.
InstalledParamikointoisolatedbuild/v2/board-auth-tools (no repodependencychange);
venvhasnopip,initialmodulechecks/venvpipfailedharmlessly,preservedtooloutputs.
InteractivePTyauthsession26150 iswaitingatgenericpasswordprompt; open_in_codex
terminalrequestqueued. Humanmustenterauthenticationthere,neverrecord/repeatpassword
inchat/files/reports. Do not duplicateauthentication or package/fullbuild. Inspect
existingsession/status beforecontinuation. Nextaftersuccessreviewretrievedhardware
reports/loadedfeatures/clock/exactoutputs/recovery/modelreadback; milestoneisnot
completebeforehardwarequalification. Qualified125MHzrecovery/bootreservationintact.


## Context candidate met placement admission; one 200 MHz route attempt running

Placement completed 22:44:26 UTC. Setup sweep at 125/150/200/250/300 MHz:
+3.503/+2.170/+0.503/-0.497/-1.164 ns. The 200 MHz result meets the unchanged
+0.500 ns admission by only 0.003 ns; this is thin headroom, not routed closure.
Hold is -0.084 ns across 322 endpoints and must be repaired before export.
Packing is 11996/14640 CLB (81.94%); 63609 LUT, 51942 FF, 50 BRAM, 36 URAM,
579 DSP. Congestion report finds no windows above level 5; no legality implied.
Native optimization 74.769 s, placement 631.401 s; total 16m22s including reports.
Completion-to-review gap about 13 minutes is separate from Vivado compute time.

Worst path moved to instruction/opcode selection -> MAC DSP A input, 3 levels,
3.892 ns data (0.400 logic/3.492 route), skew +0.048 ns. Top 30 paths reviewed;
context selection is no longer worst. All 23 current and frozen hashes verified.
Candidate-specific placement/route-review.json approves ONE 200 MHz attempt and
hash-binds checkpoint, sweep, congestion, critical/hold/resource/native reports.
Seven older placements remain rejected; threshold unchanged and no fallback.

Detached PowerShell 7 route controller 2900 launched 2026-10-14T22:58:17.6298737Z with
route_attention_context_capture_large.ps1 -MHz 200. Inspect actual ancestry,
route-200mhz status/console/reports first; never duplicate or edit 23 frozen RTL.
Helper runs physical optimization/routing; legally routed positive setup AND hold
must pass before bit/XSA export, exact package admission and authorized board
qualification. Failure preserves evidence and prevents export/upload. No package,
upload or new hardware qualification exists yet. Qualified 125 MHz recovery/app/
boot reservation preserved. Exact new-profile software passed 293 admission tests.


## Recovered context synthesis gates passed; one placement running

Report-only recovery completed22:09:06UTC, no RTL edit/resynthesis. Allnew/prior
inference/area/fanout gatespassed:68765LUT/52552FF/50BRAM/36URAM/579DSP,
92fabriccontextFF/fourcontextDSPAREG0/BREG1/MREG0/PREG1; all23current/snapshot
hashes verified. Estimated200MHz setup+1.051ns/hold-0.087ns,notrouteclosure.
Worst moved to layernormwidth->bufferread-address DSP/mux3.719ns/10levels;
resetfanout3572/embeddingbeat1390 remainrisks. Encoder native5m57s; original
falseBREG0gate/recoverymissingdotvariable failuresandalloverheadpreserved.
Recoveredready-to-placementreview gapabout19minutes separatefromVivadocompute.

Hash-bound synthesis-review.json approves placementONLY and additionally binds
context-breg-review.json. ONEdetachedPowerShell7 placementcontroller18628 launched2026-10-14T22:28:04.0362689Z,
output kr260-opt-attention-context-capture-large/placement. Inspectactualancestry,
logs/status/completion first,neverduplicate/edit23frozenRTL. Reviewfiveclockpoints,
critical200paths/hold/packing/congestion beforecandidate-specifichashboundroute
review. Allsevenolderplacementsrejected;>=0.5nsplacedsetupadmissionunchanged.
Legallyroutedpositive setupANDhold/finalmatchingXSA-bit/source/fixture evidence
precedepackage/upload/boardtests. Softwareexact5377ffff293tests+Bashsyntax/helper
parsingpassed;newapp/archiveprepared,notpackagedordeployed. Qualified125MHzapp/
recovery/bootreservationpreserved. Automation30minutes,active.


Report-only recovery10540 confirmed corrected context mapping4/4, then stopped
because the extracted report script omitted the dot mode variable. Preserved
preflight-recovery-console.log and controller error; fixed missing variable only,
noRTL/synthesis change. Report-only retry17756 launched2026-10-14T22:05:40.2275500Z with separate recovery2
logs. All flag conditions reviewed for definitions. Inspect actualjobcompletion
before anyplacement; do not duplicate. This recovery overhead is not synthesis
compute. Software293tests/Bashsyntax/helpersparse already passed; no hardwareaction.


## Context BREG hierarchy audit; report-only preflight recovery and software ready

Full RTL synthesis completed, encoder native5m57s, but21:38:51UTC admission failed
because the new gate incorrectly required standalone-OOC BREG0 in full hierarchy.
Actual92fabriccontextFF/fourDSPAREG0/BREG1/MREG0/PREG1. Previous full paired design
already used BREG1: source instruction multiplier capture absorbed into DSP B
register. Linked previous/current audits confirm all72 B data nets identical,
CEB2 instruction-FSM decode and unchanged PREG1/MREG0; only AREG1->0 targeted.
context-breg-review.json binds evidence. Initial failure/inventory preserved;
initial rawtopDCP audit had unresolved blackboxes and emptyinventories, discarded
as evidence; linkedproject/open_run audit corrected this without RTL/resynthesis.
Gate now requires exact wholehierarchy BREG1,stillrejects absorbedAREG/MREG1/
PREG0/missingFF.30preflighttests passed3.50s includingmissingBREG rejection.

Report-only recovery controller10540 launched2026-10-14T22:03:10.3146550Z reuses completed synth_1 and runs
remainingreports/gates; no resynthesis or newfullbuild. Inspect its completion/
errors before placement. RTL23frozen sources remain untouched. Actual resources
68765LUT/52552FF/50BRAM/36URAM/579DSP (+66LUT/+79FF vs paired). Need fulltiming/
fanout/inference review after recovery, hash-bound placement-onlydecision, then
oneplacement ifsupported. Sevenoldercandidates remain route-rejected.

New separate sysone-v2-attention-context-capture app/archive and exact5377ffff
runtime/package/deploy/client preparation implemented. Requiresnewflag1 withall
priorpaired16queryflags,23sources/32frozen+4query/6partial/defaultcycles/fixtures/
schedulingmetadata/generated FABRIC_CONTEXT_CAPTURE1/legalpositivefinalroute/XSA-
bit. Partial5373ffff/5375ffff/5376ffff/stale5363ffff,oldappnewflag/fallback125
rejected. Livefeature checks remain beforeDDRmapping. Newpositive deploymentmock
caught missed uppercase livefeature constant; corrected and verified before any
hardwareaction. Combined293tests passed8.83s plusBashsyntax/PowerShellparsing.
No package/upload/hardwarequalification. Qualified125MHz recovery/bootreservation
preserved. Nextactonrecoveredgates,do not duplicate anyactivejob.


## Context production proof passed; one 200 MHz synthesis running

Fresh parameterized36KR+6partial+2Nexys completed exactprototype/default outputs
and encoder/request cycles, feature5377ffff,23public hashes/fullfixtures/inherited
component proofs validated by freeze_context_capture.py --validate-only. Controller
30828 froze23sources and startedONE200MHz synthesis21:28:32UTC in
kr260-opt-attention-context-capture-large; topVivado15984(parent24876). Inspect
actualancestry/preflight-console/childlogs/completion before any next job, never
edit23sources or duplicate. Newcontext-capture mode configuresFABRIC_CONTEXT_CAPTURE1
and audits>=92fabriccontextFF/fourcontextDSPAREG0/BREG0/MREG0/PREG1 plus allpaired,
16query,distance,probability,URAM,capture,FIFO,drain,dot,row,LINEARreadfirst gates.
29preflight admissiontests passed3.66s, includingmissingFF/missingDSP/stalemapping/
absorbedAREG/extralatency. Hash-bound gate receipt saved. Candidate-specific new
placement/routehelpers prepared, not launched; profile5377ffff/newflag required.

Next actual synthesis resource/inference/fanout/timing review and hash-bound
placement-only approval, then ONE diagnostic placement if supported. Allseven old
placements rejected, unchanged>=0.5ns200setup routing admission and legalpositive
routedsetupANDhold required. New exactprofile runtime/package/deploy/client support
stillpending; currentsoftware rejectsunknown5377ffff. No package/upload/hardware
qualification; qualified125MHz recovery/app/bootreservation preserved.


## Context selection cut supported in isolation; parameterized production proof active

Whole-attention isolated comparison completed20:32:24UTC; reviewed20:59UTC,
completion-to-review gap about27min, not native compute. Baseline/fabric3.333ns
worst slack+0.191/+0.250ns (+0.059), native120.739/122.155s. Targeted context
selection checkpoint audit: +0.770->+1.580ns (+0.810), data1.977->1.750ns.
Actual context mapping0->92fabricFF and four contextDSPAREG1->0,BREG0/MREG0/PREG1.
Whole isolated footprint26642->26871LUT,14794->14887FF,17BRAM/37DSPunchanged.
Worst moved to score maximum update CE (s_word to maximum),2.956ns/9levels.
No full-design or300MHz closure claim; do not add isolated gains to placed slack.
OOC/review.json hash-binds proofs and approves parameterized integration only.

Applied integrate_context_capture.py ONCE: independent default-off
FABRIC_CONTEXT_CAPTURE propagates throughattention/layer/system/KR260/wrapper/TB;
conditional keep/dont_touch on existing w_sum, original expressions/FSM unchanged.
Old defaults/branches/feature5363ffff preserved. Newfamily53700000/full5377ffff,
candidate attention-context-capture-large, intended separateapp
sysone-v2-attention-context-capture. Never replay integration scripts. Previous
frozen23source candidates and private sources preserved. New23public sources under
test now: fresh36KR+6partial+2Nexys parameterized proof controller17932 launched2026-10-14T20:59:28.2874688Z
in rtl-context-capture-parameter-check. Inspect existing logs/completion first;
neverduplicate/edit sources under test. No full synthesis automatically launched.
Fresh prototype/default/cycle/fixture/hash admission, candidate-specific synthesis
mode/register gates, software/app/schema/admissiontests and placement/routehelpers
stillpending. Current software intentionally rejects unknown5377ffff. Need>=92
fabriccontextFF and4contextDSPAREG0/BREG0/MREG0/PREG1 plusallprior gates. Allseven
placements remain rejected; qualified125MHz recovery/boot reservation unchanged.


## Context-capture numerical proof passed; isolated comparison running

Private context-capture full36KR+6partial+2Nexys completed with exact outputs,
encoder/request cycles versus paired production. review.json binds logs and
prototype; all23 public source hashes unchanged. No arithmetic/FSM/cycle change.
Numerical proof does not establish actual fabric mapping or timing improvement.
One isolated whole-attention baseline/fabric comparison launched2026-10-14T20:27:59.5315977Z controller24512
via run_attention_context_capture_ooc.ps1, output attention-context-capture-ooc.
Selected identical16query/FABRIC_SCORE_DISTANCE1 and all prior attention settings;
read frozen baseline versus private prototype. Do not duplicate or edit sources.
Review actual w_sum fabric FF, context DSP AREG/BREG/PREG, resources and all moved
critical paths after completion before selecting or integrating. No full build
or public integration is authorized automatically by this comparison. All seven
placements remain route-rejected; no package/upload/hardware qualification exists.


Private launcher15472 failed before snapshot/test startup because WSL cannot translate subst S:. Preserved original log/error. Launcher now uses verified physical workspace; retry controller16764 started19:59:06UTC, separate retry logs. No tested RTL changed and no duplicate test existed.


## Seventh placement rejected; private context-register proof started

Request-window-embed placement finished19:43:39UTC. Sweep125/150/200/250/300:
+3.468/+2.135/+0.468/-0.532/-1.199ns. 200MHz hold-0.102ns/301 endpoints;
63686LUT/51888FF/50BRAM/36URAM/579DSP,CLB12358/14640=84.41%.
Congestion report finds no windows above level5 (not a claim of routed legality).
Native opt75.923s/place597.322s; total15m48s including reports. Completion-to-
review gap about14min is separate from compute. All SEVEN placements now rejected;
hash-bound placement/route-review.json rejects routing, unchanged0.5ns admission.

Worst path now shared attention accumulator LUTRAM/context selection into
requantizer w_product DSP A input:3.605ns(data0.796logic/2.809route),6levels,
skew-0.291ns. Top nearby paths are same context mux. No Vivado remains active.
Private attention-context-capture/engine-sources/attention_engine.sv adds keep/
dont_touch to existing w_sum selection registers to prevent absorption into DSP
input registers, with no expression/FSM/pipeline-cycle change. This is a hypothesis,
not mapping/timing proof. Public23 sources and frozen prior snapshots untouched.
Private full36KR+6partial+2Nexys runner launched2026-10-14T19:58:19.6816990Z controller15472 in
rtl-attention-context-capture-check. Inspect existing logs/completion/hash first;
never duplicate/edit tested source. Require output/encoder/request cycle equality
versus paired production, then isolated whole-attention inference/timing/resource
comparison before any integration or full build. Prototype still old5363ffff and
is not package ready. Explicit fabric stage may trade DSP input registration for
fabric routing; audit actual mapping and moved critical paths before selection.
Qualified125MHz recovery/boot reservation intact; no package/upload/hardware claim.


## Request window and DSP embedding synthesis passed; placement launched

Full synthesis gates completed at 18:59:58 UTC. Actual resources: 68,699 LUT,
52,473 FF, 50 BRAM, 36 URAM and 579 DSP; versus attention16 this is -120 LUT,
-15 FF and +2 DSP with unchanged memory. All 23 current and snapshot RTL hashes
verified. The 17 window FF and both embedding DSPs AREG1/BREG1/CREG1/MREG0/PREG1
and all prior memory, pipeline and fanout gates passed. Estimated 200 MHz setup
+0.952 ns / hold -0.087 ns is synthesis evidence only. Worst path moved to DDR
burst-boundary/read-address update, 14 levels, 3.818 ns data. Reset fanout 3583
and embedding beat fanout 1390 remain risks. Encoder native synth 8m30s; top
synth 49s. Confirmed 67m08.48s battery sleep remains separate from compute time.

Candidate-specific synthesis-review.json hash-binds six evidence files and
approves placement only. No previous Vivado remained. Detached PowerShell 7
placement controller PID 8844 launched 2026-10-14T19:27:51.1884529Z. Sources and tested helpers untouched.
Synthesis-ready to placement-launch gap was about 29 minutes, including the
30-minute heartbeat interval requested by the user; do not count as Vivado time.
Next review all five frequency points, critical 200 MHz paths, hold, CLB packing
and congestion. No route until meaningful >=0.5 ns placed setup and a separate
hash-bound review; final legal positive setup AND hold required before export,
package and board tests. All six old candidates remain rejected. Qualified
125 MHz app, recovery and boot reservation preserved. Automation every 30 minutes.


## Paired public proof passed; synthesis resumed after battery sleep

Fresh production36KR+6partial+2Nexys proof passed exact outputs and prototype/
default encoder/request cycles. Controller13976 froze23sources/exact5363ffff and
started ONE200MHz synthesis17:34:03UTC; main synth launch17:36:23UTC. All23frozen
snapshot hashes reverified. CurrenttopVivado27408(parent13224),encoder17212 and
interconnect2552 are children of this same job; preserve ancestry and runningjob,
no duplicate or edit. Encoder elaboration is progressing after resume. Actual
resource/inference/timing gates, placement and route qualification stillpending.

This continuation established an actual cause for THIS delay: Windows Kernel-
Power42 reports Battery sleep; Power-Troubleshooter1 reports sleep17:36:42.269UTC
and wake18:43:50.749UTC,4028.480s(67m08.48s). OS event/power evidence saved in
request-window-embed-battery-sleep-audit.json. Native child CPU activity resumed
and queuedencoder started after wake. Laptop is now AC online/charging,5% at
firstread then6%. No power settings changed and no battery protection overridden.
Record this interval separately from Vivado compute/native reports. This evidence
does not establish causes for older unexplained gaps; do not claim uninterrupted
work or attribute67minutes to synthesis execution.

All257software/admission tests and preparedcandidate-specific helpers retained.
Next act on completed synthesis gates: read actual resources/DSP/register/memory/
fanout/timing, hash-bind placement-only review thenlaunchONEdiagnostic placement.
Do not route any of six rejected candidates or relax0.5ns admission. Legalpositive
routed setupANDhold and finalmatching artifacts precede package/upload/boardtest.
Qualified125MHz recovery/app/bootreservation remainunchanged; automationACTIVE.

## Paired software/profile preparation passed257 tests; public regression active

Prepared separate sysone-v2-request-window-embed app/archive with exact5363ffff,
23sources, cached_request_window1/dsp_embed_row_address1 and all earlier16-query
flags. Partial5361ffff/5362ffff,stale535affff,oldapps claimingnewflags,missing23-
source receipt and fallbackclock profiles rejected. Paired package/runtime/deploy
requires requested andqualified200MHz; liveBUILD/features checked beforeDDRmap.
Package checks generated newparameters,fullsource/fixture/query/defaultcycle/
schedulingmetadata and matchingpositiveLEGAL finalroute/XSA/bit evidence. Older
profiles preserved. First software test collection caught malformed firmware-map
entry from scripted edit; corrected before tests, no package/deployment occurred.

Combined runtime/link/deploy/package/preflight/route tests passed257 in19.89s,
including positive new-app install mocks,partial manifest no-install/no-unload
and live stalefeature checks. Bashsyntax and both pairedPowerShell/Tcl helper
parsers passed. New candidate-specific placement/routing helpers require23hashes,
both stages and hash-bound reviews; none launched. Proof/hashes saved in
request-window-embed-admission-tests.json. No archive/upload/hardwarequalification.

Existing13976 public regression continues; completedcases stillmatchprototype.
23RTL sources under test neveredited during this software preparation. Its ready
receipt binds freeze/createproject/preflight scripts; after all36+6+2/source/
fixture/component gates it will freeze and launchONE200MHz synthesis. Inspect
actualprocesses/status/completion before nextstep, no duplicate. All six prior
placements remain rejected; qualified125MHz app/recovery/bootmemory preserved.

## Paired request/DSP-address production integrated; fresh regression active

Private DSP group completed36KR+6partial+2Nexys exact output/encoder/request cycles.
Whole embedding dynamic32bit OOC reused identical baseline wrapper:3.333ns setup
-0.650->+0.185(gain0.835),3973->3483LUT,932->852FF,0->2DSP,native88.594s fornew.
Checkpoint audit confirmed both address DSPs AREG1/BREG1/CREG1/MREG0/PREG1. Worst
moved to local position-bias requantization3.145ns. This is isolated evidence, not
whole KR260 closure. All six previous placed candidates remain route-rejected.

Applied integrate_request_window_embed_dsp.py ONCE after completed private gates;
never replay. Production exposes default-off CACHED_REQUEST_WINDOW and
DSP_EMBED_ROW_ADDRESS through hierarchy, separate common DSP kernel (23sources),
family53600000/full5363ffff, candidate request-window-embed-large; legacy default
branches and535affff preserved. Immutable older snapshots untouched. New enabled
profile must pass fresh fullhierarchy/default/partial/query proofs before freezing.

Fresh parameterized36KR+6partial+2Nexys regression ACTIVE in
rtl-request-window-embed-parameter-check, detachedcontroller13976 at
run_request_window_embed_candidate.ps1,started17:20:33UTC. Never duplicate or edit
its23sources. Controller requires complete output/cycle/source/fixture/component
proof via freeze_request_window_embed.py, then freezes23sources and launches ONE
200MHz synthesis after hash-bound helper receipt. New mode create_project audits
>=17window FF,2DSPAREG1/BREG1/CREG1/MREG0/PREG1 plus all prior16-query/distance/
probability/URAM/capture/FIFO/drain/dot/row/BRAM gates.23preflight tests passed in
8.48s, including missingwindow/missingDSP/unregisteredC/extralatency rejection;
Tcl complete. Hash-bound gate-scripts-ready receipt prepared, no fullbuildyet.

Measured MAC/query/AXIweight/norm secondary routes remain risks requiring actual
newplacement review; isolated gains must not be added to placed slack. Prepare
new exact5363ffff software/profile/app/partialword rejection and candidate-specific
helpers during sustainedjobs. No package/upload/hardwareclaim;0.5ns placement
margin and legalpositive routed setupANDhold remain unchanged. Preserve125MHz
app/recovery/bootmemory. AutomationACTIVE, act on completed gates.

## DSP kernel arithmetic/capture proof passed; grouped regression continues

Actual embed_row_address_dsp RTL passed1,262,146 comparisons across27/32bit
address wrap, every65536stride with maximumunsignedID/base, randomcapture/output
hold and simultaneous enables,246 synchronous resets. There were315635captures
and315771outputs; sourcehash/native times in embed-row-dsp-arithmetic/summary.json.
This complements focusedwholeembedding4097profiles; it does not establish DSP
inference/register mapping or timing. Kernel and active private22source snapshots
were not edited. Existing controller21280/watcher29040 continue; wide8/L12eight
completed output/status/encoder/request cycles match baseline, one-word started.
No duplicate or heavyfullbuild launched. OOC admission remains gated on all36+6+2
numerical/cycle/source checks; inspect existing jobs on next continuation.

## Fabric embedding offset rejected; DSP address prototype under test

Combined window+fabric-offset regression completed36KR+6partial+2Nexys with exact
outputs/encoder/request cycles and unchanged22publicsources. Full dynamic32bit
embedding OOC then rejected fabricoffset: estimated3.333ns slack-0.650->-0.786,
3973->4044LUT,932->982FF,0DSP. Native103.342/94.112s. New worst token selector->
word_offset multiply4.116ns/18levels. Preserve review.json and failed selection;
do not integrate or fullbuild this fabricoffset variant. No heavy job remains.

Acting on measured arithmetic cone, a NEW private request-window-embed-dsp snapshot
uses two synchronous two-stage DSP address kernels: capture ID/stride/base on
existing ID_WAIT acceptance, compute base+unsigned ID*stride on ROW_ADDRESS.
No new FSM cycle; reset suppresses external descriptor while internal DSP resets
synchronously. Focused wholeembedding4097profiles/262096writes passed exact DDR
request/control/data/mask/output cycles,variable32bit bases/strides/wrap,extremeIDs,
stalls/reset/restart; nativecompile9.599s/sim1.061s. This is numerical only; DSP
mapping/register inference/timing still unverified. Production22RTL unchanged,
new standalone simulation kernel is not a deployed FPGA capability.

Full36KR+6partial+2Nexys regression ACTIVE in rtl-request-window-embed-dsp-check,
detachedcontroller21280; gatewatcher29040 at watch_request_window_embed_dsp_gates
waits full exact cycle/output/source proof, then ONE full dynamic embedding DSP
OOC synthesis. Reuse byte-identical baseline fabric wrapper/result-0; do not
resynthesize completed baseline. New wrapper/source hashes in prepared-gatesJSON.
Inspect these actual jobs before acting; never duplicate or edit tested copies.
Review actual DSP A/B/C/P register placement and shifted worst paths/area before
public/default-off integration or anotherfull200MHz build. Existingproposal
53600000/full5363ffff remains unimplemented; source inventory may grow if the
kernel becomes a separate public source. All six placements rejected,0.5ns
route admission unchanged, qualified125MHz app/recovery/boot reservation preserved.

## Grouped request/embedding regression progressing; proposal remains gated

Existing combinedcontroller25472/gatewatcher30764 preserved. Completed wide8,
L12eight, one-word5, boundary3 and firsttwoH1024 cases match baseline output/status/
encoder/request clocks exactly. No heavy Vivado job currentlyactive; watcher
will admit only one isolated dynamic-address embedding comparison after all
36+6+2 gates finish. No duplicate jobs or production changes.

Additional offset/base arithmetic checked3,538,944 combinations:every16bit stride,
27/32bit address wrap, ID/token corners and zero/near-end base addresses. This is
modular arithmetic proof, not a timing or mapping claim. Full engine4097profile
proof and active combined numerical regression cover source/tag/control alignment.
Prepared request_window_embed_integration.md only proposes default-off independent
CACHED_REQUEST_WINDOW/PIPELINED_EMBED_ROW_ADDRESS and a distinct family53600000/
fullword5363ffff, rejecting partial5361ffff/5362ffff. Nothing applied or advertised.
Actual OOC inference/timing and secondary placed cones must support selection
before public integration/freshparameterized proof/full synthesis. Production
22sources and535affff profile unchanged, all six prior route rejections retained.

## Request-window full proof passed; secondary embedding cut under test

Private request-window passed36KR260+6partial+2Nexys exact output/encoder/request
cycle equality; review.json verified unchanged22production sources. Existing
watcher2848 completed isolated request-admission composition:3.333ns estimated
setup+1.026->+1.333(gain0.307ns),176->201LUT,432FF unchanged in wrapper,0DSP;
native114.130/71.928s. Baseline worstload_tile->DDRacceptCE moved to request_tile
comparator. This is isolated mapping, not full clock closure or full-engine FF
cost; the fullengine still needs load_tile and may add17limitFF.

Do not launch window-only fullbuild. Secondary actual placed embedding instruction
->word_row_address is+0.330ns(data4.481ns); nearby attention/query MAC, AXIweight
acceptance and layernorm address paths+0.357..0.369 remain measured concerns.
Private request-window-embed-address snapshot precomputes word/position offsets
on the existing ID_WAIT acceptance edge and adds base in ROW_ADDRESS, keeping
all FSM cycles. Production22RTL and prior prototypes untouched. Focused whole
embedding pair proof passed4097profiles/262096writes at32bit addresses, variable
base/strides with wrap, extremeIDs, full descriptor/control/tag/mask/output cycles,
stalls/reset/restart. Nativecompile9.427s/sim1.138s; summary/sourcehashes recorded.

Combined36KR+6partial+2Nexys regression ACTIVE in rtl-request-window-embed-check,
detachedcontroller25472 started this turn. Existing gate watcher30764 at
watch_request_window_embed_gates.ps1 waits for completed exact output/cycle/source
review, then ONE dynamic32bit instruction-address/stride full-embedding OOC
comparison. No Vivado currentlyactive at this audit; never duplicate eitherjob.
Prepared wrapper/prototype/source hashes in request-window-embed-prepared-gates.
The new source-data->offset multiply stage must be measured; do not infer benefit
or public integration from moving the adder. No new capability/schema yet; private
copies still535affff and not package-ready. All six placements remain rejected;
route threshold0.5 unchanged,125MHz app/recovery preserved. AutomationACTIVE.

## Request-window regression progressing; isolated gate prepared

Existing controller12648 continues the private request-window regression; completed
wide8 and L12eight exactly match baseline output/status/encoder/request clocks.
No repeated simulation or source edit. Private prototype and22production hashes
remain preserved. Fullhead32/partial/default and remaining profiles still required.
Prepared focused loader lookahead -> six-way engine mux -> registered DDR request
acceptance probe with same input registers, modular counters and caller handshake;
its estimates cannot represent full placed route delay. Tcl/PowerShell syntax
passed. Existing gate watcher2848 at watch_request_window_gates.ps1 waits for all
36KR+6partial+2Nexys completion, verifies exact outputs/cycles and unchanged frozen
production hashes through review_request_window.py, then launches ONE isolated
old/cached composition synthesis only if no Vivado job is active. It never launches
full synthesis, placement or routing. Hashes in request-window-prepared-gates.json.
Inspect this watcher and regression first; never duplicate or edit sources under
these tests. Review actual critical paths/resources/inference before publicflag/
capability integration. All six prior route rejections remain; automation active.

## Attention16/distance placement rejected; request-window prototype active

Placement completed16:20:45UTC. Hash-bound placement/route-review.json rejects
routing:200MHz setup+0.269ns below unchanged0.5ns margin,hold-0.068ns/148 endpoints,
congestion5. Sweep125/150/200/250/300 +3.269/+1.936/+0.269/-0.731/-1.398ns.
CLB packing measured80.00%(11712/14640), down from fifth96.68%; congestion remained
level5. Native opt137.983s/place1206.023s, total launch->report31m11s includes
reports andcontroller. No route/export/package/upload. All SIX placements now
rejected; qualified125MHz app/recovery remains intact.

Worst path moved to LINEAR load_tile register through +2 lookahead/compare,
request beats and mux/nonzero acceptance to DDR read_address register CE:
4.582ns data(1.326logic/3.256estimatedroute),12levels,skew+0.059ns. Act on this
measured cone. Private linear-request-window/engine-sources snapshot adds a kept
17-bit request_window_limit register initialized2 and incremented exactly with
load_tile. It removes the combinational+2 without changing request cycles;
production22RTL unchanged. Arithmetic recurrence passed1,935,008 comparisons
covering every17bit load value,threshold boundaries,modularwrap/reset/launch/
bubbles, native0.583s. This is recurrence only, not whole engine/timing proof.
Initial proof driver failed on NumPy unsigned negative offset before runner
creation; corrected signed comparison, initialcontroller error retained.

Private full36KR260+6partial+2Nexys regression ACTIVE in rtl-request-window-check,
detachedcontroller12648(run_request_window_regression.ps1), launched16:20:09UTC.
Inspect actual logs/hash/snapshot/completion first; never duplicate or edit tested
snapshot. Prototype still advertises old535affff; not package-ready. Require
exact outputs and encoder/request cycles versus attention16 production before
isolated actual request-admission composition synthesis; no heavy build now.
Do not introduce a row-only full build or publicfeature integration prematurely.
All software223tests and existing source/fixture proofs retained. AutomationACTIVE.

## Attention16/distance software preparation passed223 tests

Separate sysone-v2-attention16-distance app and kr260-app-attention16-distance-large
archive are now supported by package/deploy/runtime/client. Exact535affff and16
query/fabric-distance parameters, all prior stages, frozen22sources/numeric32+
query4/partial6/default cycle equality and finite scheduling-cost metadata are
required. Package checks generated ATTENTION_LANES16/FABRIC_SCORE_DISTANCE1,
full H1024 and head32 query fixture hashes, matching final XSA/bit and legal
positive routed timing. Partial535a7fff/535abfff/stale53597fff rejected. Older
profiles cannot claim new flags; live BUILD/features checked before DDR mapping.
Prepared archive includes separate four-length query fixture; deployment script
would validate it before restoring and testing L12. No archive generated or upload.

Combined runtime/link/deployment/package/preflight/legal-route tests passed223 in
12.60s, including new-app install mocks, stale feature probes and no-unload/no-
install rejection of partial manifests; Bash syntax passed. Hashes recorded in
attention16-distance-admission-tests.json. Actual hardware/boot memory untouched.
Placement31216 remains active in global place phase1; no duplicate job and no
source edit. Next inspect completed sweep/critical paths/hold/density/congestion
and make candidate-specific hash-bound routing decision; do not relax0.5ns margin.

## Attention16/distance full synthesis reviewed; placement running

Full synthesis finished15:47:35UTC. Whole design uses68,819LUT/52,488FF/50BRAM/
36URAM/577DSP versus fifth89,920LUT/66,043FF/66.5BRAM/36URAM/609DSP:
21,101 fewer LUTs (23.4664%),13,555 fewer FFs,16.5 fewer BRAM tiles,32 fewer DSPs.
No packing/congestion relief claim until placement measures it. Estimated200MHz
setup+0.787ns/hold-0.087ns; worst instruction->embedding row address17levels/
3.983ns persists. Top fanout reset3864,attention lane selector1205,embedding
beat1057. Encoder native synth12m44s/top synth1m33s; earlier49-minute report-to-
completion gap is recorded separately, cause unknown.

Controller17480 failed its inventory gate because Vivado replicated one first-key
FF:512 original accumulator controls plus first_key_reg_reg_rep (35loads), not
missing stages. Original failure log preserved. Corrected admission requires512
unique originals, only replicas of those originals and unchanged fanout limits;
18 tests passed including valid replica, orphan replica and missing-control cases.
All22 frozen sources verified, no RTL/synthesis rerun. Gate-recovery JSON records
this correction. All16 probability DSP input/PREG,16 exponentAREG0/PREG1/352fabric
FF,512query,36URAM OREG,896capture,2FIFOflags,256drain,30LINEAR READ_FIRST RAMBs,
15rowregs/noLINEAR LUTRAM and dot stages passed. Hash-bound synthesis-review.json
approves PLACEMENT ONLY. Detachedcontroller12452/Vivado31216(parent28332) launched
15:49:33UTC; one heavy job in kr260-opt-attention16-distance-large/placement.
Inspect actual ancestry/logs/completion before next action, never duplicate.

Next review all125/150/200/250/300MHz timing, hold, actual density/congestion and
critical routes. Routing requires candidate-specific hash review and >=0.5ns
placed200 setup; legal positive routed setup AND hold before exports. Runtime/
client125tests passed; package/deployment support still pending. No new package,
upload or hardware qualification; qualified125MHz app/recovery unchanged.

## Attention16/distance runtime admission tested; synthesis progressing

Runtime/client preparation now recognizes the separate attention16-distance app
and only exact 0x535affff, with 16 query lanes, fabric distance, numerical32/query4/
partial6 proof, unchanged Nexys default cycles and finite scheduling tradeoff
metadata. Older apps cannot claim the new options. Partial feature words remain
rejected; live BUILD/features are checked before DDR mapping. Runtime/link tests
passed 125 cases in 5.72 s; hashes in attention16-distance-runtime-tests.json.
Package/deployment support and full artifact proof are still pending; no install.

Encoder synthesis completed natively in 12m44s with 66,253 LUT / 50,105 FF in the
encoder submodule, not whole design. The report was timestamped 14:48:23 UTC and
child completion appeared 15:37:54 UTC; this approximately49-minute reporting/
completion gap has an unknown cause and is not added to native synthesis time.
The parent then advanced to whole-design synthesis. One job remains active;
all frozen22 inputs preserved. Full inference/timing/area gates and placement
review remain required before any placement or route.

## Attention16/distance placement and routing helpers prepared

Prepared separate candidate-specific PowerShell/Tcl helpers without launching them.
Both PowerShell parsers and Tcl completeness checks passed; helper hashes are in
build/v2/attention16-distance-placement-helpers.json. They require exact 0x535affff,
16 query lanes, fabric-distance enabled, 32 frozen plus four query-group numerical
cases and six partial tiles. Routing checks the actual 16 probability DSPs,
352 external distance FFs, 512 query/accumulator controls and the full shared
preflight gates; it preserves the 0.5 ns placed margin and legal positive routed
setup/hold admission. All frozen RTL and active synthesis inputs remain unchanged.
Synthesis remains active at this review; encoder log reached technology mapping.
Runtime/package/deploy support is still pending; no placement/route/package launched.

## Attention16/distance production proof passed; full200MHz synthesis active

Integrated default-off FABRIC_SCORE_DISTANCE and defaultATTENTION_LANES=TILE_OUT
through KR260 hierarchy. Selected16query/32linear,H1024,fabricdistance profile
uses DISTINCT0x535affff/family535a0000,candidateattention16-distance-large.
Never rerun integrate_attention16_distance.py or edit22sources underfullbuild.
Privatecore OOC32->16+distance mapping:49626->26642LUT,28209->14794FF,
33.5->17BRAM,69->37DSP; estimated3.333nsminslack+.361->+.191(worstmovedto
heads->headcursorCE). This is area relief, not clockclosure; targetedscore
BRAM/DSP probe gain+.698 retained,16e-productDSPAREG0/PREG1/352externalFF proved.
Nativecorecomparison299.085/180.033s.

Fresh parameterized production regression completed14:11:08UTC:32frozen+4head32
KR260cases,sixpartial,twofreshNexys defaults allbitexact. Prototypecycle gate
caughtonlyL12last3 mismatch because priorresumedrun restartedAXIrandomtimeline.
Preservedthat evidence; reranONLYnecessaryfullL12reference usingoldprivatebinary,
no recompile. Like-for-likecycles nowmatch; allothersalreadymatched. This
reference fixes earlierfalse0.10186%12-token penalty fromresumetimeline.
Actualarchitecturaltradeoff0%..+5.32004% versus32querybaseline, not free speedup.
Freeze records freshreferencehash/cyclecomparison scope and all36cases/fixtures.

15preflightadmissiontests andTclsyntax passed; candidategates require16probability
DSP input/PREG,352externaldistanceFF/16DSPAREG0/PREG1,512query/512acc controls,
allpriorURAM/capture/FIFO/drain/dot/row/BRAM gates and>=10%wholeLUTreliefvsfifth
candidatebeforeplacement. Hash-boundhelperreceipt releasedcontroller17480 at
14:32:39UTC; ONE200MHzfullsynthesis ACTIVE in kr260-opt-attention16-distance-large.
TopVivado14964(parent21640),encoderchild5816 andsamejobchildren only; mainlaunch
14:35:03UTC. Frozen22sourcehashes verified. Inspect actuallogs/ancestry/completion
first; no duplicates or edits. Regressionfinished->fullsynthesis21m31s included
admissionhelpers/tests andneededfreshcyclecheck, not Vivado time. Placementreview,
newexactprofile runtime/package/deploy andhardwarequalification stillpending.
No route/package/upload; allfiveolderplacementsrejected;125MHzrecoveryunchanged.
Detachedcontrollers survive normalturnending; observedWSLrestart andabsentSalias
were recovered, causeunknown. AutomationACTIVE; actoncompletedgates.


## Attention width results reviewed; restart recovered; isolated core comparison active

Correction: ATTENTION_LANES parallelizes QUERY TOKENS, not heads. Private16query
lanes retain32linear/H1024 and head-count support. All32frozen cases+sixpartial
outputs bit-exact; encoder cycle changes0%..+5.32013%, not unchanged. Additional
H1024/head32 lengths1/3/12/128 allbitexact versusbaseline32querylane binary;
cyclechanges0%..+2.39688%. rtl-attention16-check/review.json records allcases,
tradeoffs and explicit2Nexysproofreuse with byte-identical dependencies. No
physicalperformance/quality/capabilityclaim. Do not use unchangedcycle gates.

WSLrestart interrupted originalrun duringL12; causeunknown. Detachedresume
controller14580 reused compiledbinary, preservedcompletedwide8/L12first5,
resumedonlyunfinishedcases and comparednewhead32fixture; now numerical_logs_ready.
Originalsnapshots/partiallog preserved; no recompile orrepeatcompletedprofiles.
The S: workspace alias was also absent; isolatedcomparison firstlaunch failed
beforeVivado. Preservedfirst-attempt error, verifiedexactworkspaceroot and
restorednative substalias. Retrycontroller5820/topVivado21420 withsynthesis
workers isONEactiveisolatedjob inattention16-distance-ooc. Inspectcurrent
ancestry/status/console; neverduplicate or editsources underits test.

Score-distance isolated BRAM/subtract/DSP mapping gained+.698ns at3.333ns,
+.515->+1.213, unchanged704LUT/10BRAM/32DSP,+704fabricFF.32DS AREG1->0,
BREG1/PREG1 retained. Privateattention-engine attribute copy passed11focused
cycle/output/control/address/MACprofiles. Public22RTL unchanged. Currentcore
OOCcompares32querylanes/defaultdistance versus16querylanes/fabricdistance;
reviewactualwholeengine resources/inference/timing beforepublicintegration.
Preparedattention_width_distance_integration.md; newexactfeature/app/schema
andparameterized production/default/partial proof required beforefullbuild.
No routing/package/upload; all5olderplacements rejected;125MHzrecovery preserved.


## Fifth placement rejected; measured score-register and attention-width prototypes

Source-row-bram placement completed12:20:14UTC. Sweep125/150/200/250/300:
+3.447/+2.114/+0.447/-0.553/-1.220ns. Hold-0.079ns/321endpoints,CLB96.68%,
congestion5; opt144.635s/place1422.721s native. Hash-boundroute-review rejects
routing belowunchanged0.5ns gate. ALLFIVEoldplacements rejected; no newroute,
package orhardwareload. Worst scoreBRAM->subtract->DSPinput3.786ns data,
2.034estimatedroute. Nearcriticalqueryselector->MACA+.450,opcode->MACA+.453,
contextLUTRAM->product+.455. Preserve all22frozen source hashes/defaults.

Isolated actual128x704 scoreBRAM/subtract/32DSP comparison: preserve distance
FFs infabric ratherthanDSPAREG. Estimated3.333ns slack+.515->+1.213,gain+.698;
32DSP/704LUT/10BRAM unchanged; fabricFF704->1408. AllnewDSPAREG0/BREG1/PREG1,
704externaldistanceFF; native74.338/62.349s. Private attention-engine attribute
copy passed11focused output/control/address/MACoperand/cycle profiles; no added
pipelinecycle. score-distance-ooc/summary.json and score-distance-engine/review.
No whole-design clockclosure. Public22RTL untouched; integration/profilepending.

Independent private attention16-prototype forces existing encoder_system
ATTENTION_LANES16 whilelinearTILE_OUT32/H1024 unchanged. Targets attention
storage/mux/routing pressure; morethan16querytokens must be grouped, not rejected.
Stillreportsold53597fff, NOTpackage-ready. rtl-attention16-check passedwide8
andfirst5L12cases before WSLrestart interruptedremainingrun. CurrentWSLboot
wasnew/processesgone, causeunknown. Compiledbinary preserved at snapshot
/var/tmp/sysone-capture-regression.G5gO9H; neveredit inputs or duplicate.
Detached controller14580 resume_attention16_controller.ps1 now resumes only
unfinishedcases usingcopiedbinary/privatework, preservingcompletedwide8/L12
first5 and originalsnapshot/log. Reuses identicalNexys dependency source proof
explicitly; no pretendingnewNexysrun. Then compares new H1024/head32 goldens
lengths1,3,12,128 onbaseline/16lane binaries inattention16-head-groups. Vectors
referenceverifiedSHA7dd6f3a41b0f7c05caa903e9f622583da25769f2a79fd18b449294c1dea56d12.
Inspect existingcontrollerstatus/logs beforeaction; no heavyVivadojob active.
Group independently verified distance/attention-width cuts only afterfull
numerical/default/multigroup/cycle review and isolatedresource proof; no new
fullbuild yet. Preserve125MHzrecovery/bootreservation. Automation remainsACTIVE.


## KV logical command composed with retirement and frozen AXI data path

Independent kv-command-axi simulation connects kv_read_command/span/chunker to
relative_read_retire and frozen capture-flags AXI port, both direct/registered
request ports withregisteredFIFOflags. Sixoperations eachconfiguration passed:
orderedreturnedwords,hostconfigchange,1MiB+descriptor splitting,4KiB/256beat
AXIbursts,4GiBwindow/final40bitword,invalidcompletecachebeforeAR,lastbeatfault
insecondchunk/drain/poison/failedchunkexcludedprogress,coordinatedresetrecovery.
summary.json records nativebuildtimes/sourcehashes; sim0.102/0.100s. This advances
simulateddata-path composition, NOT PS mapping/deployedexecutor/decoder/cache
writeback/physicalallocation orhardwareintegration. ExternalAXI reset/drain
fence remains systemresponsibility. None ofthesecomponentfiles is in frozen22.

Placement1376 remains active, progressedthroughGlobalPlacePhase2/physicalopt;
CPU increased on fresh snapshots, no stall inferred from sparse log updates.
No newheavyjob or frozenRTLedit. Finaltiming/congestion reviewstillpending.


## Independent KV command context moved into RTL and verified

Placement1376/controller2944 remains active at PBP global placement; no frozen
RTL or activebuild scripts changed and no duplicate heavyjob. Independent new
kv_read_command.sv captures acceptedmodelbase/window in RTL, allows one logical
slice outstanding, gates localerrors beforechunker and holds context through
ordered controlledchunk completion/finalbackpressure. Original bench-held-context
proof preserved. New8operations/2058descriptors includes2GiB range,40bitendpoint,
configchanges,localfaults,secondchunkfailure and consecutivecommands withoutreset.
Reset tests cancel beforedescriptor and afterissue,blocklateidlecompletion and
allownewcommand. Nativebuild10.630s/sim0.008s; kv-read-command-reset/summary.json
records hashes. Component absent from22frozenencoder sources; noAXIdata/retirement,
deployedexecutor,decoder,cachewriteback orhardwareintegration. RealAXI reset/drain
fence stillrequired; experimental SYS3 ABI notadvertisedby anyapp. Contractupdated.


## Source-row/BRAM synthesis reviewed; placement launched immediately

Full synthesis gates passed11:43:44UTC; encoder native synth_design10m39s.
Controller Stopwatch synthesis-stage delta1507.96s(25m08s); UTCstart/end
11:21:54->11:43:44 is21m50s, so clocks disagree and no cause established.
Preserve both evidence forms rather than equating wall timestamps/nativeelapsed.
Actualresources89920LUT/66043FF/66.5BRAM/36URAM/609DSP. Allprior probability
input/PREG32DSP,64embedcontrols,36URAMOREG,896capture,2FIFOflags,256draincapture,
queryfanout16/accumulator54 anddotstages retained. LINEAR30RAMBprimitives,
READ_FIRST bothports/DOA-DOB_REG0,15rowregisters,0LINEARLUTRAM passed.
Estimated200MHz setup+0.787ns/hold-0.087ns, worst instruction->embeddingrow
address17levels/data3.983ns. Reset5113loads and embeddingbeat~1066 remain.

Hash-bound synthesis-review.json approves PLACEMENT ONLY after actualreview.
No claimedBRAM/packingrelief: priorLINEARalreadyBRAM, LUT+589/FF-39/DSP-1.
AddressDSP removal targets priorplacedworstpath; one diagnostic placement
measures actual newtiming and secondary attentioncontext/MACroutes/packing.
Placement launched11:44:41UTC, controller2944/Vivado1376(parent32964),
build/v2/kr260-opt-source-row-bram-large/placement. About56s synthesis-ready
->placement launch; no repeatfullbuild. Inspect this existing job/status/logs,
never duplicate or edit22sources. Review125/150/200/250/300MHzsweep, hold,
congestion/density beforecandidate-specific hash-bound routingdecision.
Route requires>=0.5ns meaningfulplacedsetup margin and then legalpositive
routedsetup/hold. All4oldplacements remainrejected. No package/upload/hardware
qualification. Preserve125MHz app,recovery,bootreservation; automationACTIVE.


## Full-design memory comparison corrects isolated BRAM estimate

Full source-row-bram synthesis report:89920LUT/66043FF/66.5BRAM/36URAM/609DSP,
versus operand-capture89331LUT/66082FF/66.5BRAM/36URAM/610DSP. Thus oneaddress
DSP removed,+589LUT/-39FF,noadditional BRAM. Prior full encoder log already
inferred LINEAR gen_block accumulator as BlockRAM; explicitblockstyle changes
contract visibility, not migration fromLUTRAM. The isolated forcedLUTRAM->BRAM
5704LUT/2204FF saving DOES NOT apply to full baseline. Earlier expectedpacking
relief was unsupported; preserve evidence and do not claim it. Hash-bound
synthesis-area-comparison.json records actualcomparison/priorbankinference.

32probabilityDSP input/PREG,64localembedding,256draincapture and15source-row
registers reported; LINEARLUTRAM0. Fulltiming/fanout/controlreports stillrunning
under same topVivado20348/controller24344. Report_high_fanout_nets itself took
2m24s elapsed, including timingupdate. Synthesis gates/STA not yet completed.
Placement decision must use actualcriticalpaths/area, not isolated savings.
Qualified125MHz recovery unchanged; no routing/package/upload.


## Synthesis progressing; independent KV range planner verified

At11:32-11:33UTC, existing source-row-bram full synthesis still active under
controller24344/topVivado20348 and encoderchild21956, with same-job synthesis
workers. Mainrun launched11:23:45UTC; encoder technology mapping elapsed8m02s,
renaming8m35s, hierarchy rebuild ongoing. Logs show intended LINEAR forced
block banks and probability operand registers absorbed into DSPs; final full
resource/register/latency gates not complete. No duplicate Vivado job, RTL edit,
placement,route,package or boardload. Preserve frozen22sources.

Independent KvCacheLayout.range_requests now validates bounded token slices
before yielding lazy finite-width descriptors, including empty capacity-end,
padded rows, chunk boundaries, stale/invalid ranges and last40bitword. Existing
prefix API unchanged. Combined layout/window/relativebundle72tests passed.
A2GiB value range produced2049descriptors, peak plannerallocation1304bytes,
native0.016s, endat40bitboundary, no payloadallocation. Hash-bound evidence
kv-cache-range-proof.json. This is offlineplanning, not DMA/executor/cache
writeback/decoder/hardware integration or deterministic timing proof.


## Source-row/BRAM full production proof passed; synthesis running

Production regression completed all32KR260 cases,sixpartial tiles,twoNexys
with bit-exact outputs and prototype/default encoder/request cycle equality.
Controller24344 froze22RTL sources and started ONE200MHz full synthesis at
11:21:54UTC (6:21:54AM Central). Vivado20348(parent32596), samejob children allowed.
Candidate build/v2/kr260-opt-source-row-bram-large,capability0x53597fff;
regression.json and all22frozen source hashes verified. Never edit these inputs
or launch duplicate jobs. Inspect actual ancestry/logs/preflight completion.
Regression wait+compile+simulation856.75s, not full Vivado time.

Once all synthesis gates complete, review memory/read-first/latency/register
inference, area/fanout and actualcritical paths. Prepared placement helper
requires candidate-specific hash-bound synthesis-review.json approving only
placement. Launch placement after meaningful review; route requires new
placement review/margin>=0.5ns and measuredhold/congestion/packing. Four old
rejections remain. ActualBRAM savings,200MHzclosure and hardware performance
unproven. Qualified125MHz recovery/bootreservation unchanged; automationACTIVE.


## Source-row/BRAM software admission prepared during compilation

Runtime/package/deploy/client support separate sysone-v2-source-row-bram,
archive kr260-app-source-row-bram-large.tar.gz, exact0x53597fff and both row/BRAM
options. Old profiles reject these options; stale/partial0x53595fff/0x53596fff
are rejected. Runtime checks liveBUILD/features beforeDDRmapping. Package
requires22source proof,32cases/sixpartial/defaultcycles,fullH1024fixture,
generatedflags,exactXSA-bit and positivelegalroutedtiming. 165combined tests
passed; after adding positive new-app install coverage,45deploy tests passed.
Bashsyntax and prepared PowerShell placement/route helpers parse passed.
Hashes saved in source-row-bram-admission-tests.json. No package/upload/load.

Prepared place_source_row_bram_large_candidate.ps1/.tcl and
route_source_row_bram_large.ps1/.tcl retain candidate-specific hash-bound
reviews,newexactword/flags,allprior pipeline gates and row/BRAM preflight
checks; neither launched. Controller24344 and parameter regression session44778
remain active. Production22RTL untouched since integration. Act on completion;
review actual synthesis before placement. No heavy Vivado job launched yet.


## Source-row/BRAM production integration and regression active

Grouped private prototype completed 11:06:28 UTC: all 32 KR260 cases, six
partial tiles and two Nexys defaults passed exact outputs and encoder/request
cycle equality. Hash-bound review saved in rtl-source-row-bram-check/review.json.
Integrated two DEFAULT-OFF parameters once: INCREMENTAL_SOURCE_ROW and
LINEAR_ACCUMULATORS_IN_BRAM. Separate explicit block branch preserves original
LUTRAM/implicit branches when disabled. Full grouped feature0x53597fff/family
0x53594000, candidate source-row-bram-large; unknown app still rejected by software.
Do not rerun integrate_source_row_bram.py or edit the 22 production sources.

Production parameterized regression ACTIVE: rtl-source-row-bram-parameter-check,
session44778; snapshot includes all22 sources, flags1, 32KR+sixpartial+twoNexys.
Controller24344 run_source_row_bram_after_regressions.ps1 waits for gates,
freeze_source_row_bram.py validates output/cycle/default/hash/component proofs,
then launches ONE200MHz synthesis. Routing is disabled. Inspect actual jobs first.
No heavy Vivado job active yet. New preflight guards for LINEAR RAMB read-first,
DOA/DOB_REG0, row registers/noLINEARLUTRAM plus all prior stages are prepared.
Ten admission tests passed, including stale/missing memory/stage rejection.
Runtime/package/deploy new exact profile support still pending. No package,
upload, hardware qualification or200MHz closure. Preserve all4 route rejections
and qualified125MHz app/recovery/bootreservation. Placement remains evidence-
gated at0.5ns margin; actualfullBRAM/resource relief and secondary context/MAC
cones must be reviewed after synthesis/placement, not inferred from isolated OOC.


## Grouped prototype gate watcher installed

Existing source-row+BRAM regression remains active in rtl-source-row-bram-check
(session27113). Gate watcher33724,watch_source_row_bram.ps1, waits for its existing
completion, verifies32KR260+sixpartial+twoNexys exact output/cycle equality and
prototype source hash via review_source_row.py --bram, then records integration
readiness in source-row-bram-gates-status.json. It launches no full build and
does not edit testedRTL. Inspect existing watcher/regression before acting.


## Source-row full numerics passed; BRAM-bank grouped regression active

Source-row prototype completed all32KR260 cases,sixpartial tiles,twoNexys defaults.
review_source_row.py verified exact outputs and encoder/request cycles against
operand-capture, including current prototype source hash. Review is saved in
rtl-source-row-check/review.json. Production22RTL and rejected placements intact.

Measured LINEAR two-bank128x1024 accumulator inference: forcedLUTRAM5716LUT/
3263fabricFF/0BRAM -> explicitBRAM12LUT/1059fabricFF/29BRAMtiles. Thus isolated
savings5704LUT/2204FF for29tiles; all block primitives READ_FIRST onbothports,
DOA/DOB_REG0(noextra read-register latency). Nativeold62.219s/new45.215s. This
is isolated composition evidence, not full resources/timing or hardware proof.
Current66.5BRAM plus isolated29 fits144tile budget, but fullmapping must be
measured. Evidence:linear-accumulator-ooc/summary.json/inventory/checkpoints.

Created a SEPARATE source-row+BRAM prototype at linear-source-row-bram/engine-
sources/linear_engine.sv. It enables the existing synchronous BRAM branch with
explicit block style, leaving the completed row-only snapshot untouched.
Full32KR260+sixpartial+twoNexys regression now ACTIVE in rtl-source-row-bram-check,
session27113,run_kr260_source_row_bram.sh. Inspect existing snapshot/process/logs;
never duplicate or edit these inputs. It still reports old0x53591fff in the
experimental copy: no new public/default-off parameter/schema or package yet.
No heavy Vivado job remains after bankOOC; no fullcandidate build launched.

This grouping targets both the address multiply and97.10%CLB density. Secondary
attention context LUTRAM route(+0.458ns) and instruction->MAC mux(+0.459ns) still
need placement evidence; BRAM spill may relieve routes but does not prove it.
Do not force asynchronous ATTENTION RMW intoBRAM without retiming/forwarding.
On completed grouped regression, verify outputs/cycles/defaults/partial cases
and source hashes, integrate default-off INCREMENTAL_SOURCE_ROW and explicit
LINEAR_ACCUMULATORS_IN_BRAM preserving legacy branches, use distinct strict
candidate/schema/profile, rerun parameterized proofs before freezing/synthesis.
Keep prior exact-profile deployment guards and runtime BUILD/features-before-DDR
checks. Require all inference/area/placement/legalpositive routedsetup/hold before
packaging or hardwareload.125MHz recovery/bootreservation unchanged; automationACTIVE.


## Operand placement rejected; measured source-row correction under test

Placement completed10:36:53UTC; nativeopt112.243s/place1040.600s, totalstage
26m46s includingopening/reports/closing. Setup sweep125/150/200/250/300:
+3.441/+2.108/+0.441/-0.559/-1.226ns. At200 hold-0.088ns/450endpoints.
CLB14216/14640(97.10%),LUT81749/FF65197,BRAM66.5/URAM36/DSP610,congestion5.
Hash-bound placement/route-review.json rejects routing below0.5ns gate; do not
route this or older candidates. No active fullVivado job or hardware package.

Worst measured path moved to LINEAR source row address: in_tiles register ->
registered physical-buffer read address, DSPmultiply plus selection. Data4.261ns
(logic2.465/estimatedroute1.796), skew-0.213ns. Source is token*row_stride+tile.
Independent linear-source-row/engine-sources snapshot replaces the multiply
with a modular row pointer advanced onC_RUN, cleared onlaunch/passstart/reset,
and corrected at token-width wrap. Production22RTL remains untouched.
Full32KR260+sixpartial+twoNexys prototype regression ACTIVE in rtl-source-row-check,
session70300; widepassed andL12progresses. Preserve it; noduplicate/edit.
Prototype still reports old0x53591fff; no new public parameter/schema/package.

Focused recurrence proof passed16983813comparisons:all65536strides/256tokens,
wrap,clear,bubbles/reset. The same count passed registered read-port-mux
composition. Isolated registered composition synthesis finished:3.333ns estimated
slack+0.734->+2.113(gain1.379),14LUT/37fabricFF/1DSP ->36LUT/73fabricFF/0DSP.
Nativeold62.384s/new48.515s;this is not full-design timing/resource evidence.
Evidence:linear-source-row-probe,linear-source-row-composition,linear-source-row-ooc.

Before another expensive full build, address remaining near-critical cones and
packing. Attention accumulator LUTRAM->context selection has+0.458ns,4.432ns
path (0.954logic/3.478route); instruction->MACoperand mux+0.459ns also remains.
A row-only correction does not prove those cones will pass the route margin.
Evaluate moving LINEAR's already-synchronous128x1024 two-bank accumulator from
forcedLUTRAM to explicitBRAM to relieve97.10%packing: spare77.5BRAMtiles exist,
expected bankcost must be measured by isolated inference,not assumed. Existing
branches have the same one-clock read behavior; preserve read-first/collision,
PASS_GAP and drain bank/tag contracts and numerical evidence before grouping.
Attention shared accumulator is asynchronous RMW; do not blindly force it into
BRAM without retiming/forwarding proof. No full row-only build launched.

Independent KVspan->chunker proof also passed7operations/2057descriptors,
including2GiBprefix/2049chunks,localfault gating and chunk2failure progress;
no AXIdata/executor/cache-writeback/hardware claim. Qualified125MHz app and
bootreservation unchanged. AutomationACTIVE; next is finish prototype gates
and independently measure packing/secondary-cone remedies before grouping.


## Placement reports being generated; KV chunk composition passed

The existing operand-capture job completed main placement and writes diagnostic
reports. Early completed utilization shows81,749LUT/65,197FF,66.5BRAM/36URAM,
CLB14,216of14,640(97.10%). Packing remains worse than the prior97% candidate;
read final200MHz paths/hold/congestion/sweep before any route decision. No route
approval. Preserve running8276/controller27888 and all22frozen sources.

Independent logical KV span -> whole-operation chunker bench passed7operations/
2057descriptors. Includes final40-bit physical word,1MiB/2MiB prefixes, local
range/overflow errors beforeissue, chunk2fault excludingfailedbytes, and2GiB
valueprefix through2049descriptors. Configuration changes/backpressure/stalled
completion checked with captured window context and controlled completionmodel.
Native Verilator build8.573s/sim0.007s. Evidence:kv-chunk-plan/summary.json.
No AXIdata/retirement/executor/cache-writeback/decoder/hardware integration.

Next is finishedplacement review and either an evidence-supported200MHz route
attempt or measured bottleneck correction. Keep125MHz app and bootreservation.
Automation ACTIVE; do not confuse isolated/prototype proofs with clock closure.


## Placement progressing; independent RTL KV span proof passed

Preserved the existing operand-capture placement (Vivado8276/controller27888).
It progressed through global placement and physical synthesis in placer;
reported place phase elapsed about8m59s. No duplicate build or frozen RTL edit.
Final timing sweep/density/congestion are not available yet; do not route.

Added independent kv_cache_span.sv, outside22frozen sources: a two-stage elastic
logical layer/K-or-V/token slice planner using a pre-padded row stride. Complete
layout and query bounds are validated with82bit intermediates before output
truncation. Typed errors produce zero spans and must be rejected before DDR.
Independent Python KvCacheLayout oracle:10013accepted packets,10011compared,
2reset-cancelled. Includes output stalls/stability, config changes, valid matrix
boundaries/final32bit offset/fullwindow, and invalid alignment/range/product
overflow. Native Verilator build4.926s/simulation0.039s. First vector-generation
attempt lacked PYTHONPATH; corrected invocation inserted src, then proof passed.
Evidence:kv-cache-span/summary.json and relative_read_contract.md. No Vivado
inference/timing, executor/AXI/writeback/decoder/hardware integration claim.

Primary next action remains completed placement review, then hash-bound200MHz
route decision or measured RTL correction. Preserve22frozen sources, qualified
125MHz app/recovery and boot reservation. Automation remains ACTIVE.


## Operand synthesis reviewed; placement launched at 10:10 UTC

Full synthesis gates completed at 08:21:35 UTC. Resources: 89,331 LUT,
66,082 FF, 66.5 BRAM tiles, 36 URAM and 610 DSP. Compared with pipeline-cuts,
LUT decreased by 1,191 and FF increased by 31; other resources stayed equal.
All 32 probability DSP AREG1/BREG2/PREG1 stages, 64 local embedding controls,
36 URAM output registers, 896 local capture FF, two FIFO flags and 256 drain
capture FF survived. Query/accumulator control fanout gates passed. Estimated
200 MHz synthesis setup +0.787 ns, hold -0.087 ns. Worst path moved to instruction
register -> embedding word-row address, 17 logic levels, 3.983 ns data delay.
High-fanout reset and embedding beat selectors remain. This is not clock closure.

Native encoder synthesis was 9m16s; full synthesis/report/controller stage was
18m50s. Evidence shows preflight_ready at 08:21:35 but placement review did not
execute until 10:09 UTC: about 108 minutes of review gap, not synthesis time.
No matching sleep/resume events were returned for this interval; cause is not
established. Do not attribute this gap to Vivado or claim uninterrupted agent work.

22 frozen/live source hashes and all numerical/component gates verified. A
candidate-specific synthesis-review.json now approves diagnostic placement ONLY,
binding regression, summary, timing, critical, fanout and synthesized DCP hashes.
Placement controller 27888/Vivado 8276(parent 9916) launched at 10:10:06 UTC.
Inspect this existing placement and logs; do not duplicate it. No route started.
Review the finished 125/150/200/250/300 MHz sweep, hold, density and congestion
before a new route-review.json. Preserve the 0.5 ns 200 MHz admission margin.

During placement, client guards were tightened: the Linux profile provides exact
frontier BUILD and feature expectations, checked after ID and before DDR mapping.
Stale or partial hardware closes the register mapping/FD and cannot map DDR.
131 runtime/link/deploy/profile/preflight tests passed in 4.90s. Updated software
hash evidence: operand-capture-admission-tests.json. No package/upload/hardware
qualification yet. Qualified 125 MHz app and recovery/boot reservation preserved.
Automation remains ACTIVE; next action is placement review and an evidence-led
route attempt or measured RTL correction, not another synthesis of this snapshot.


## Independent KV-cache layout proved while synthesis continues

The existing operand-capture synthesis is still progressing. Encoder child
33340 reached final naming/hierarchy processing at roughly 7m49s native elapsed;
controller6768/top32136 remain the same job. No duplicate build or RTL edit.

Added independent experimental KvCacheLayout for packed INT8 per-layer K/V
matrices, 16-byte padded rows and immutable excluded model/scratch spans.
25 layout tests cover GQA footprint, disjoint matrices, physical40-bit endpoint,
4GiB relative extent, finite beat descriptors, invalid accesses and mutability.
The full second2GiB matrix produces2049descriptors without payload allocation.
A32layer/4KVhead/64head-dim/4096context storage example is64MiB, not a deployed
model configuration. Window/layout/bundle suite:61tests passed8.01s. SYS3 ABI
negotiation now rejects5376legacy/new SYS2 combinations, including all operand
feature families. Evidence:kv-cache-layout-proof.json/relative_read_contract.md.
This has no decoder/writeback/DMA/PSmapping/hardware/timing integration claim.

Next remains actual synthesis gates and resource/timing/fanout review, then
bound placement-only receipt and the prepared placement helper if justified.
Keep22frozenRTL, validated125MHz app/recovery and boot reservation unchanged.
Automation ACTIVE; route qualification/hardware deployment still pending.


## Operand capture frozen; 200 MHz synthesis active and deployment gates tested

Production hierarchy completed32frozen KR260 cases,6partial-tile cases and2
Nexys defaults, exact outputs and encoder/request cycles matching prototypes.
Controller6768 froze22sources and started one200MHz synthesis at08:02:44UTC.
Top Vivado32136(parent14208); encoder child33340 and PS child11236 belong to
that same build. Main launch at08:04:47UTC is waiting for synthesis. Inspect
kr260-opt-operand-capture-large/preflight-console.log and childrunme logs;
never duplicate synthesis or edit22frozen/liveRTL. Their hashes reverified.

Strict runtime/deploy/package profile preparation now supports only the
complete new app sysone-v2-operand-capture/feature0x53591fff and separate
kr260-app-operand-capture-large.tar.gz. It rejects stale/partial feature words,
wrong new parameters, missing five-cycle contract, missing positive finite
routed timing and legacy manifests claiming new stages. Deployer verifies
actual features after loading; client performance counters now recognize exact
pipeline-cuts/operand-capture layouts and reject unknown/partial/SYS3 words.
Package requires22source hashes,32cases/default-cycle equality,6partial cases,
exactfeature,generated parameters,complete eight-length H1024 fixture and final
legal XSA/bit/routed evidence.127tests passed4.12s; bashsyntax passed. Evidence:
operand-capture-admission-tests.json. No package or upload created.

Prepared place_operand_capture_large_candidate.ps1/.tcl require completed
preflight and a candidate-specific synthesis-review.json approving placement
only, with nonempty reason and evidence_sha256 for regression,summary,timing,
critical,fanout and sysone_v2_kr260.runs/synth_1/system_wrapper.dcp. Do not write
approval until actual synthesis reports are reviewed. Prepared route helper
requires completedplacement, >=0.5ns setupmargin, candidate-specific hash-bound
routing review and stage/22-source gates. Both helpers parse; neither launched.
Routing remains200MHz-only, requiring legalpositive setup/hold before export.

After synthesis, inspect actual resources/registers/fanout/critical paths and
write the bound placement-only review, then launch the prepared placement
helper if justified. All older candidates remain rejected for routing. Qualified
125MHz app/recovery and bootreservation remain unchanged; automation ACTIVE.


## Grouped operand capture integrated; production regression and controller active

The combined prototype completed all 32 KR260 cases and two Nexys defaults:
exact outputs and encoder/request cycles equal pipeline-cuts-large. The gate
controller completed successfully; preserve rtl-input-embed-check/review.json.

Production hierarchy now has separate default-off PROBABILITY_INPUT_CAPTURE
and LOCAL_EMBED_CONTROLS. Old probability/drain semantics remain unchanged.
The new family is 0x53591000; the enabled grouped feature word is 0x53591fff.
Input capture requires probability pipeline and read latency >=5; exponent
fetch moves to L-4. Embedding keeps its four stages, uses start-captured shifts
and biases, and preserves the original arithmetic branch when disabled.
The production enabled embedding passed 4097 focused profiles/262096 writes,
including all shift pairs, stalls and reset; simulation native wall 0.634 s.
Evidence: embed-controls-integrated/summary.json. Do not rerun integration.

Full parameterized regression is active in rtl-operand-capture-check,
session60631. Preserve all 22 production RTL sources and its snapshot. It tests
32 frozen KR260 cases, six H48/FFN80 partial tiles and two Nexys defaults.
Controller PID6768, run_operand_capture_after_regressions.ps1, waits for it;
then freeze_operand_capture.py checks prototype output/cycle equality, exact
feature word, golden fixture/source hashes, component/OOC and focused embedding
proofs, freezes22sources and launches ONE 200MHz synthesis. It never auto-routes.
Inspect operand-capture-controller-status.json/log/err and actual ancestry;
never duplicate this controller, regression or synthesis.

create_project_kr260.tcl supports operand-capture mode and audits all32
probability DSP AREG1/BREG2/PREG1, local embedding controls plus existing URAM,
local capture, FIFO flags and drain stages. Four resource admission tests passed
in1.82s, including rejection of stale or missing input and embedding stages.
Runtime/package/deploy admission for the new profile remains to be implemented
before any deployment; current software rejects this unknown app. After full
synthesis gates, review actual resource/fanout/timing, then prepare one placement
job and a candidate-specific routing review. The older rejected placements
remain rejected. No hardware package or 200MHz claim.125MHz app preserved;
automation ACTIVE and boot memory unchanged.


## Input capture numerical gates passed; combined regression continues

At 07:46 UTC the input-only prototype completed all 32 frozen KR260 cases and
two Nexys defaults with exact outputs and identical encoder/request cycles
to pipeline-cuts-large. Six H48/FFN80/TILE32 partial-tile cases also passed
516 exact output words and unchanged cycles. Source and log reviews are in
rtl-probability-input-check/review.json and probability-input-partial-check/summary.json.

The combined embedding/input regression remains active (session 13313); its
wide cases passed and L12 is progressing. Gate controller PID 29368 checks
existing completion files and runs review_operand_cut_prototypes.py once both
finish; status is operand-prototype-gates-status.json. It launches no heavy
build and does not edit tested RTL. Inspect that existing controller and
regression before any new action. On passed gates, integrate the distinct
parameters/profile from operand_capture_integration.md and run the actual
parameterized hierarchy/default/partial regression, then freeze and synthesize
one new 200 MHz candidate. No active Vivado job, route approval or hardware
package yet. The qualified 125 MHz app remains preserved; automation ACTIVE.


## Operand capture and embedding isolated synthesis completed

The actual 512x128 BRAM / 32-lane probability composition improved estimated
3.333 ns setup slack from -0.127 to +1.203 ns (+1.330 ns), retaining 224 LUT,
256 fabric FF, 7.5 BRAM tiles and 32 DSPs. All new DSPs infer AREG1/BREG2/PREG1.
Native synthesis/report stages were 66.154 s old and 54.984 s new.

The registered-instruction embedding comparison improved -0.755 to +0.185 ns
(+0.940 ns), for +33 LUT/+59 FF and unchanged zero BRAM/DSP. Its old worst path
was instruction position shift to p_term; the new path is local position bias
to p_term. Native stages were 95.260 s old and 62.113 s new. These are isolated
synthesis estimates, not full-design clock closure. Source/report-bound
summaries are in probability-input-ooc and embed-controls-ooc. No heavy
Vivado job remains active after these comparisons.

Two experimental numerical jobs remain active: rtl-probability-input-check
(session 20244) and combined rtl-input-embed-check (session 13313). Preserve
their sources and snapshots. The combined run includes independently proven
embedding controls and the input stage, alongside existing drain/capture cuts.
Require all 32 KR260 and two Nexys cases, exact outputs and baseline cycles
before production integration. Prototype feature words remain stale and are
not package admission. operand_capture_integration.md defines distinct
default-off parameters, feature family 0x53591000/full word 0x53591fff and
separate app/candidate admission. Do not edit tested RTL before gates complete.

The previous +0.417 ns placement remains rejected for routing. The qualified
125 MHz app, recovery package and boot memory remain unchanged. Automation
ACTIVE; 200 MHz route and hardware milestone remains incomplete.


## Pipeline placement rejected at+0.417ns; measured probability input cut testing

Completed placement at07:27:40UTC. Nativeopt119.048s/place1041.606s; reports/closing
make totalstage26m53s. Setup sweep125/150/200/250/300:+3.417/+2.084/+0.417/-0.583/
-1.250ns. At200MHz hold-0.105ns,635endpoints. CLB14197/14640(96.97%), LUT82853,
FF64614,BRAM66.5,URAM36,DSP610;congestion5. Despite LUTrelief, packing worsened.
Hash-bound placement/route-review.json rejects routing below0.5ns admission;
do not route this or eitheroldercandidate.125MHzhardware app preserved.

Worst actualplaced200path: exponentRAMB36E2 clock-to-output -> probability
DSPproduct/PREG, data4.038ns (logic3.104/estimatedroute0.934), skew-0.430ns.
The earlier isolated wrapper's inputFF were absorbed intoDSPAREG; fullengine
source isBRAMoutput, so isolatedtiming did not represent this path. Target an
explicit operand capture with exponentfetch oneclock earlier (L-4), not blindly
apply an embeddingcut to this measuredcone. Three-stage probability requires
readlat>=5 and preserves existingMAC operandtiming via earlyrowfetch.

Independent3-stage prototype passed33,557,838arithmetic comparisons(all16x9input
pairs,bubbles/reset) and11focused attentionprofiles (controls/MACoperands/output/
stalls/headgroups/reset). Copies at probability-input-cut/engine-sources.
Full32KR260+Nexys numerical regression now runs in rtl-probability-input-check,
session20244. Preserve snapshot/sourcehashes. It still reports oldfeature in this
experimentalcopy; this is NOT package-ready publicparameter/capability plumbing.
Require distinct candidate/schema proof before deployment integration.

One focused actualBRAM->kernel OOC comparison runs: Vivado12104(parent13116),
session56964, probability-input-ooc.32lanes, same512x128exponentBRAM andlive
reciprocalregisters, old2stage vsnew3stage. Inspect actualDSP/BRAM registers and
criticalpaths/resources before anotherfullbuild. No otherheavyjobactive.
Wholeembeddingcontrol snapshot independentlypassed4097profiles/262096writes;
notintegrated and no measuredtimingbenefityet. Primary21frozenRTL untouched.
AutomationACTIVE;200MHzroute/hardwaremilestone incomplete.


## Whole embedding engine control-cut equivalence passed; placement reports pending

Independent embed-controls snapshot start-captures local shifts and26bit biases,
uses signed16bit term clamps and33bit sum, retaining fourstage valid/tags. Frozen
original comparison passed4097whole-engine profiles/262096destination writes:
all64x64word/position shifts,width16/48/128,tokens1/3,INT32type extremes,INT8/UINT17
corners,DDRrequest/data stalls,compute-phase reset/restart. Controls/descriptors/
source addresses/output masks/data/cycle timing match. Nativecompile8.489s,
sim0.724s. Evidence embed-controls/summary.json. Caller keeps controls stable for
an instruction; no claim about compatibility with midinstruction controlchanges.
No isolatedinference/timing/resource proofyet; not in21sourcecandidate.

Primary pipeline-cuts placement32152 finished mainplacement and writesdiagnostic
reports. PlacedLUT82853/FF64614/BRAM66.5/URAM36/CLB14197of14640 (96.97%). Congestion
level5 remains; packing worsened despite lowerLUT count. Need finished200MHz
setup/hold paths and source-bound review before decidingroute or nextcut.
Preserve activejob and21RTL; no embeddingheavyjob launched whileplacementactive.
No route/deployment;125MHz app/boot reservation unchanged. Automation ACTIVE.


## Independent lazy high-DDR burst planner passed while placement runs

Added MemoryWindow.iter_bursts to stream large-window physical AXI descriptors;
existing bursts list API retained. Full4GiB from physicalpage offset1024 passed
1,048,577 contiguous bursts,<=256beats and4KiB boundaries, plus40bit endpoint,
zero-length compatibility and invalid-request rejection.36memory/relative tests
passed1.73s. SYS3 rejects1,280feature combinations acrosslegacy/newpipelinefamilies.
Measured planner-loop traced allocation/elapsed in high-ddr-stream-planning.json;
no payload or physicalDDR allocation/execution. SYS3 executor/PS mapping pending.

Primary placement32152/controller11648 remains the oneheavy job; noRTLedits.
Review actual finished sweep/congestion before route; preserve21frozen sources,
rejectedolder candidates,125MHzapp andbootmemory. Independent Python planner
changes are not part of the FPGA snapshot/bitstream. Automation ACTIVE.


## Final parameterized partial tiles passed while placement runs

The final compiled0x535907ff candidate also passed syntheticH48/FFN80 partial
output tiles for6lengths1/2/3/5/33/128,516words, with encoder/request cycles
exactlyequal the tested groupedprototype. Baseline rerun also passed. Evidence
pipeline-cuts-partial-check/summary.json plus binary/log hashes; noRTL edits
or recompile during placement. This strengthens final publicparameter/feature
admission for partialtiles; no trainedmodelquality or hardwareclaim.
Automation prompt updated to inspect already-running pipeline-cuts placement,
not completed regression/controller stages. ACTIVE. After actual placement
review, advance one justified route or measured correction; preserve125MHzapp.


## Pipeline cuts synthesis reviewed; placement launched (October14,2AMChicago)

Synthesis/controller gates completed06:59:31UTC,14m44s from06:44:47 launch
(includesreports/admission; native encoder synth_design8m25s). Resources:
90522LUT/66051FF/66.5BRAM/36URAM/610DSP. All36URAMOREG,896localcaptureFF,
2FIFOflagFF,32probabilityDSP/PREG1,256drainbankcaptureFF retained. Dot stages
4608/2432/1280, query/accumulator1024controls withmax16/54loads,23552sharedRAMcells.
Comparedcaptureflags:3078fewerLUT,+213FF,+7.5BRAM,unchangedURAM/DSP. This changed
inference is measured but no causal attribution without deeperhierarchyanalysis.
Synthesized200MHz setup+0.685/hold-0.087ns; embedding shiftcontrol remainsworst.
Highfanout in dividerreset/embedding/control remains. Sourcehashes21verified.
Hash-bound synthesis-review.json approvesplacement only, no route.

Controller11648 launched one placementVivado32152(parent32944) at07:00:47UTC.
Read placementcompletion/console and pipeline-cuts-placement-controller logs;
no duplicate job/RTL edits. Expectednext gate isactual200MHz paths,hold,CLBpacking
andcongestion, with125/150/200/250/300diagnostics. Prepared200MHz routehelper
requires candidate-specific receipt and>=0.5nsplacedmargin; preserve rejected
capture/captureflags receipts. Deployed125MHzapp remains unchanged.

KR260 SSH reachability/authentication rechecked transiently, kernel6.8.0-1036-xilinx.
NoMMIO, upload, FPGAload, modelwrite or bootchange. Batch key-only attempt failed
because passwordauthrequired; authorizedtransientlogin succeeded andsessionclosed.
Credentials are not in files/reports. Hardwarevalidation remains possible after
legalpositive200MHz route/export. No200MHz or300MHz clockqualificationyet.
AutomationACTIVE; currentmilestone incomplete.


## Parameterized21-source candidate admitted;200MHz synthesis active

Final parameterized regression passed32KR260cases plus2Nexys defaults, with
allencoder/request cycles equal the combinedprototype and Nexys defaults equal
capture-flagsbaseline. Controller25720 froze21sources and launched full200MHz
synthesis at06:44:47UTC; parentVivado31112/5436 with IPchildren is oneheavyjob.
All21live/frozen hashes verified afterlaunch. Read controller/preflight/runme
logs before anynewjob; noRTL edits under test. Routing remainsdisabled. Actual
resource/inference/fanout review, placement and positivelegalroute stillrequired.

Independent decoder kernel rope_pair_int8.sv passed49,101accepted packets:
49,098 compared against Python rope_int8,3cancelled by reset,6invalid typed
completions withzerooutputs. Fractions1..15, INT8corners/random andsigned17bit
sin/cos tables including+32768, rounding/saturation, prolongedbackpressure,
packetstability/tags/bubbles/reset covered. Build5.550s, sim0.166s. Evidence
build/v2/rope-pair/summary.json/sourcehashes. Notpartof21candidate, no decoder/
model calibration/inference/clock/hardware claim. No extraVivado joblaunched.
Deployed125MHzapp/recovery/bootmemory unchanged. Automation ACTIVE.


## New candidate deployment admission prepared;81tests passed

New pipeline-cuts-large profile explicitly requires both probability_pipeline1
and pipelined_drain_select1, controls3/readlat5/capture1/FIFOflags1/hidden1024.
Separate sysone-v2-pipeline-cuts app and kr260-app-pipeline-cuts-large archive
preserve existing files. Deployer requires exact hardware feature0x535907ff;
old535901ff and partial535905ff/535906ff are rejected. Runtime rejects missing
cuts, swapped app/candidate, stale latency and absent positive route evidence.
81runtime/deploy/package tests passed3.20s, shellsyntax passed. Evidence
build/v2/pipeline-cuts-admission-tests.json. No package or upload generated.

Package requires21source hashes,32numerical cases equal prototype cycles,
Nexys default cycle equality, complete eightH1024fixture hashes, actual generated
parameter values, exactXSA/bit and legalpositive routed setup/hold. Prepared
place_pipeline_cuts_large_candidate and route_pipeline_cuts_large helpers,
with source/inference/profile gates and candidate-specific review. Do not
launch while controller or another Vivado job active. Routing requires reviewed
>=0.5ns placed setup; no fallbackclock/export if200MHz route fails.

Parameterized regression rtl-pipeline-cuts-check remains active;L12 stage
completed. Controller25720 waits then will freeze/synthesize once afterproofs.
No21RTL edits under test; prior frozen candidates/deployed125MHz preserved.
Automation ACTIVE; next read controller/logs and act on completed gates.


## Grouped prototypes passed; default-off parameterized regression/controller active

Probability+drain prototypes passed all32KR260 cases and2Nexys numerical cases.
Evidence rtl-probability-drain-check/review.json preserves per-profile cycles
and observed cycle changes; this is simulation, not hardware performance.
Prototype snapshots remain unchanged. No heavy fullbuild yet.

Integrated PROBABILITY_PIPELINE=0 and PIPELINED_DRAIN_SELECT=0 defaults through
engines/layer/system/KR260wrapper. Probability option requires readlatency>=4;
default path uses original exponent timing. Drain option sets depth6->7 only
when enabled; original selection/depth remains default. Candidate uses a new
capability family marker0x53590400 plus optionbits8/9: both enabled0x535907ff.
Defaults retain0x535901xx; SYS3 experimental0x53590300 stays distinct. No loader
or board app claims support for newfamily yet; package/runtime work remains.

Parameterized fullregression rtl-pipeline-cuts-check/session41857 runs from a
fresh snapshot. Do not edit its21production sources under test. It must match
prototype32outputs AND encoder/request cycles, and restore Nexys default
outputs/cycles against capture-flags baseline. This repeat is required by new
parameter/capability plumbing, not a repeated unchanged build.

Controller25720 (PowerShell7) waits for that gate, then freeze_pipeline_cuts.py
admits numerical, partialtile/OOC/source proofs and freezes21sources into
kr260-opt-pipeline-cuts-large. It launches only one200MHz synthesis after gates;
routing remains disabled. New synthesis gates require32probabilityDSPs/PREG1
and256per-bank drain FF plus existing36URAM/896capture/2FIFOflag/control gates.
After synthesis review use placement before route. Check controller status/err
and actual process ancestry; do not repeat job or old rejectedroute. All old
frozen candidates/qualified125MHz app preserved. Automation ACTIVE.


## Probability full gate passed; drain OOC and partial tiles verified

Probability-only full regression completed:32KR260 plus2Nexys numerical cases
passed. Every encoder AND request cycle count equals capture-flags across all
32cases; hash-bound review at rtl-probability-check/review.json. No production
RTL change. The experimental probability stage remains separate until final
optional parameter/profile integration is verified.

Drain OOC finished: old/new LUT2192/2391, FF108/444, BRAM29/29, DSP8/8;
isolated3.333ns setup+0.369/+0.909 (+0.540ns), native78.120/68.159s. These
are isolated synthesis estimates, not whole-design margin. Need full packing
review because added336FF/199LUT can affect already95.62%CLB density.

Generated independent synthetic H48/FFN80/head3/headDim16/TILE_OUT32 vectors
for partial output tiles. ImageMachine==IntEncoder confirmed. Baseline and
grouped compiled binaries each passed6lengths1,2,3,5,33,128 /516words; tests
include back-to-back fullprograms and recurrent banks. Evidence drain-partial-check
and drain-partial-vectors hashes. No trainedmodelquality claim. Grouped wide8
also passed; groupedL12 completed exact. One-word/boundary/H1024/Nexys still
run in rtl-probability-drain-check/session71734. No duplicate or heavy fullbuild.

Both measured cones now have independent inference/numerical evidence; finish
allgrouped cases, evaluate cycle changes, then add default-off options and
candidate capability/profile plumbing with source-bound tests before onefull
synthesis. Preserve production19hashes, snapshots and rejectedplacement receipts.
No200MHz route/board replacement yet; validated125MHz app/recovery unchanged.


## Drain engine cut passed first numerical gate; grouped tests/OOC launched

Probability-only wide8 cases passed bit-exact; every encoder and request cycle
count equals capture-flags baseline. L12/one-word/boundary/H1024/Nexys stages
still run in rtl-probability-check, session26726. Preserve its frozen sources.

Independent linear-drain engine snapshot integrates per-bank channel capture
then bank select, with metadata delay and drain depth6->7. Existing Nexys-width
1/128-token numerical cases passed39,216words (compile14.318s, sim5.145s).
Release remains after the final returned accumulator row has been captured;
compute RAM timing is unchanged. This does not establish allshifts/partialtiles/
reset coverage. Production/frozen19sources unchanged; no new default-on feature.

Launched grouped probability+drain full32KR260+Nexys regression at
build/v2/rtl-probability-drain-check, session71734. Separate snapshot, no edits
under either test. Read logs/completion before any repeat or integration.
One focused BRAM->selector->DSP OOC comparison now runs: Vivado20472/session93410,
build/v2/linear-drain-ooc. It uses two128x1024 BRAM rows and4requantization lanes.
Require actual resource/register/timing review; no heavy fullbuild until grouped
numerical/latency gates pass. Deployed125MHz app and both rejectedplacements
preserved. Automation ACTIVE,200MHz route/hardware milestone incomplete.


## Probability OOC cut inferred DSP output registers; full regression active

One isolated32-lane comparison finished: old/new DSPs32/32, fabricFF256/256,
LUT0/224. New product register maps to PREG1 on all32DSPs (MREG0), separating
multiplier output from rounding/clamp. At3.333ns target isolated synthesis
setup improves+0.714 to+1.362ns (+0.648ns). Native comparison stages59.848/61.510s.
This is isolated estimated timing, not full200/300MHz closure. Evidence
build/v2/attention-probability-ooc/summary.json; job14600 exited successfully.
Full32KR260+Nexys regression session26726 remains compiling/running; no heavy
fullbuild launched. Preserve engine-sources/attention_engine.sv and kernel under
this test. Once full suite completes, inspect every numerical output/cycle count
against capture-flags. Then combine near-critical linear-drain selection only
after its own full-engine latency/tag equivalence, avoiding premature fullbuild.
Rejected capture/capture-flags placements and qualified125MHz app preserved.


## Grouped placement reviewed; probability cut under numerical/OOC test (October 14)

Capture-flags placement completed at 05:28:48 UTC. This turn inspected the
completed evidence after 05:58:30 UTC: roughly 30 minutes between completion
and review; this interval is not Vivado compute time. Native opt 107.085 s,
place 1010.635 s. Sweep setup ns:125 +3.221,150 +1.888,200 +0.221,
250 -0.779,300 -1.446. At200 hold -0.083 ns /295 failing endpoints;
CLB13999/14640 (95.62%), LUT86110, FF64943, congestion level5. No route.
Hash-bound placement/route-review.json rejects routing below0.5ns admission.
FIFO cut improved prior200 estimate+0.068 to+0.221, but did not close routing.

Worst measured path moved to attention DSP multiplier/ALU -> probability set:
4.108ns data (2.074 logic/2.034 route), clock skew-0.424ns. Linear drain
RAM-to-DSP selection is also near-critical at+0.227ns. Target both measured
cones; an isolated probability cut alone may not provide whole-design margin.

New attention_probability.sv separates unsigned16x9 product registration from
rounded/clamped probability. 33,557,873 comparisons passed, including exhaustive
all inputs, bubbles and reset. Experimental attention engine fetches exponent
one clock earlier for READ_LATENCY>=4, preserving operand timing; L3 default
retains legacy arithmetic.11 focused control/address/MAC-operand/output profiles
passed, stalls/head-group transitions/reset. Full32KR260+2Nexys frozen numerical
regression now runs in build/v2/rtl-probability-check (session26726); preserve
its snapshot and source hashes. Focused test uses random supplied MAC products
and constant exponent table; full numerical suite is still required.

One isolated32-lane OOC comparison runs (Vivado14600/session49168), no fullbuild:
build/v2/attention-probability-ooc. Inspect DSP MREG/PREG and baseline/cut resources
and timing once it finishes. Do not modify module or experimental engine under
test.19 frozen/current production source hashes remain separate and unchanged.
After proofs, integrate independently verified linear-drain cut with full tag/
latency equivalence before another grouped full build.125MHz app preserved;
no200MHz routing/deployment, SYS3 executor, high-DDR hardware or timing guarantee.


## Measured memory profile identifies short-chain loading limit (October14)

Derived hash-bound token bins from350qualified125MHz dot7 L12 hardware cases.
Across suite: meanrequest17.280ms/effective reads1.255GB/s/weightwait22.24%/
readbackpressure15.86%/AXIservicewait0.693%/MACissue55.98% ofrequestcycles.
Counters overlap; these are not partitions or causal proof/standaloneDDRrate.
Weightwait falls from69.6% for1..8tokens and51.7% for9..16 to0.4% for33..64;
MACissue rises19.5% to72.8%. Short-chain loader/compute overlap deserves attention
alongsidefrequency. Existinglinear already has2weightbanks and2outputtile requests
ahead; addingbankdepth alone cannot increase sustainedDDRbeat rate. Needoccupancy/
request-gap evidence before allocatingmorearea. Report dot7-memory-profile-2026-10-14.md,
JSON build/v2/eval/kr260-dot7-hardware/token-memory-profile.json. NoRTLchanges.

Placement29016 remains in detail-placement fastoptimization; noerrors/duplicate.
All19sourcehashes unchanged. Route onlyafterfinalsweep/congestionreview. Corrected
memory-budgetdoc to distinguishlegacyhidden384fromqualifieddot7hidden1024 without
claimingtrainedmodelquality/highDDR. Deployed125MHz andbootreservation preserved.


## Experimental SYS3 capability collision fixed; placement progresses

Found an actual compatibility error: proposed relative-address bit6 overlapped
SYS2 local capture. Experimental bundles now require separate ABI0x53590300,
mask0xffffff00 plus relative bit0; manifests record all three fields. No deployed
app advertises SYS3. Thirty relative-model/window tests passed7.06s, including
all256SYS2feature combinations rejected and7malformed types/ranges; tiny-model
integer reference preserved. Evidence build/v2/relative-abi-validation.json.
All19 live/frozen production RTL hashes rechecked unchanged.

Placement29016/controller7960 remains active, progressing global placement;
no duplicate Vivado job or routing. Automation prompt updated to inspect this
existing placement and act on timing/congestion evidence before routing; ACTIVE.
Originaldot7/current125MHz deployment and recovery preserved. No SYS3 hardware,
PS mapping or hard timing claim. Read current placement console/status next.


## Placement running after launcher correction (October14,12:03AMChicago)

The initial WindowsPowerShell launcher3240 passed the Python gate but failed
before Vivado on unavailable Get-FileHash. No placement directory/job started;
initial log/err preserved under capture-flags-placement-controller.initial.*.
Retried using available PowerShell7: controller7960 launched actual Vivado29016
(parent2688) at05:03:18UTC. Placement status is placing. This is one heavy job.
Native encoder synth_design8m49s; top synth_design52s; overall synthesis,
diagnostics and controller admission16m26s includes report/gate work.
Read actual placement logs/status, not prior launcher PID3240; no duplicate.
Review placed200MHz setup/hold, congestion/density and critical cones before
any routing admission. Deployed125MHz app remains unchanged. Automation ACTIVE.


## Grouped capture+flags synthesis reviewed; placement launched (October14,12:02AMChicago)

Full synthesis and diagnostics finished05:01:43UTC,16m26s after launch; controller
waiting time is separate. No duplicate heavy job. All19 frozen/live hashes match.
Resource gates:93,600LUT/65,838FF/59BRAM/36URAM/610DSP; all36URAM output registers,
896local captureFF and2lengthFIFO flagFF retained. Query/accumulator controls
1024each with max16/54loads; dot stages4608/2432/1280;23552accumulatorRAMcells.
Synthesized200MHz setup+0.685ns, estimated hold-0.087ns. Worst path is still
instruction[284]->embedding p_term set,13levels/3.923ns, not routed timing.
Embedding/capture-selector high fanout remains; placement must assess packing
and congestion. Synthesis-review.json approves placement only, not routing.

Launched one prepared placement controller3240 at05:02:11UTC. Read placement
completion-status/console, capture-flags-placement-controller logs and actual
process ancestry. Do not launch duplicate, edit19production sources or route
oldcapture's rejected+0.068ns placement. When finished inspect sweep125..300,
critical200 path, hold, CLB density and congestion before hash-bound route review.

Independent whole-operation chunking also passed12cases through the new frozen
capture-flags AXI port, both request modes/FIFOflags1. Originaldot7 proof preserved.
Evidence build/v2/relative-chunk-axi-flags-final. No PS mapping/executor/hardware
integration or guaranteed timing. Deployed125MHz app and recovery unchanged;
200MHz deployment milestone remains incomplete, automation ACTIVE.


## Whole-operation DDR chunking passed frozen AXI-port composition

Both request modes passed six whole operations each through chunker, ordered
retirement, address adapter and frozen dot7 AXI port. Tests check every data
beat, descriptor/page/burst splitting, exact window/physical endpoints, range
rejection before AXI and last-response fault/drain/progress/poison/reset.
Evidence build/v2/relative-chunk-axi/summary.json; frozen port/FIFO hashes match.
This is AXI-slave simulation, not SYS3 executor/PS mapping/hardware integration.
Encoder and top-level capture-flags synthesis completed without errors; parent
Vivado still collects preflight timing/resource/fanout reports. Preserve this
one job, all19 source hashes and deployed125MHz recovery until review completes.


## Chunker plus ordered retirement composed in simulation

Four operations passed the experimental chunker+retire+address-adapter path:
17 descriptors / 4,096 data beats for 65,536 bytes; pre-issue range rejection;
last-beat response fault on chunk3 with full drain, successful-byte accounting
and poison; coordinated reset and final-word recovery. Read last is chunk-local,
whole-operation done is separate. Evidence build/v2/relative-chunk-retire.
This is controlled-memory simulation, not AXI/executor/high-DDR hardware
integration or timing qualification. Capture-flags synthesis still active;
no frozen production RTL changes and no duplicate heavy job.


## Independent 4 GiB chunk planning passed; grouped synthesis continues

The experimental operation chunker passed both descriptor-width profiles,
including full 4 GiB coverage through 4,097 serial descriptors, captured model
configuration, backpressure, whole-range rejection and abort-on-fault progress.
Evidence is in build/v2/relative-read-chunker/summary.json. This is a controlled
completion-model proof, not high-DDR hardware or SYS3 executor integration.
Current capture-flags-large synthesis remains the sole heavy Vivado job;
19 frozen production sources are unchanged. Do not repeat completed regressions.
Review full synthesis gates and then launch prepared placement when it finishes.
No route, package or board change yet; validated 125 MHz deployment preserved.


## Grouped capture+flags numerical gate passed; synthesis active (October 13, 11:45 PM Chicago)

All32KR260cases and2Nexys defaults completed bit-exact, and every grouped encoder
cycle count equals the prior capture baseline. Controller22924 admitted focused
FIFO/AXI/OOC, latency5 streaming, memory proofs and source hashes, froze19sources
in build/v2/kr260-opt-capture-flags-large and launched one200MHz synthesis at
04:45:17UTC. All19snapshot hashes rechecked after launch. Vivado3112 parent15968
is controller's one heavy job; later child processes are the same job, not
separate builds. Read capture-flags-controller* and build preflight logs/status;
do not repeat regressions/freeze/synthesis or edit RTL under this job.

New profile source-of-truth: REGISTERED_FIFO_FLAGS1 and local_capture1, capability
0x535901ff, controls3, readlatency5, maxhidden1024. StandaloneOOC cut cost+2FF/+1LUT
and broke the measured pointer-to-ready cone; whole-design timing remains open.
Synthesis resource/inference/fanout/dot/36URAM/896capture/2FIFOflag gates must pass
before place_capture_flags_large_candidate.ps1 is launched. Read actual placed
critical paths, clock sweep and density; require reviewed margin before the
prepared200MHz-only route helper. Oldcapture+0.068ns placement remains rejected.
No routing, packaging or board changes; deployed125MHz app preserved.

Independent new profile preparation passed67hosttests, including rejecting stale
capture-only hardware feature0x5359017f and swapped candidate/app/FIFOflag. Shell
runner and explicit new app/archive preserve previous files. Actual200MHz
route/XSA/bit/fixture/source evidence still required before packaging. Automation
ACTIVE; grouped200MHz deployment milestone not complete.

## Grouped flags deployment preparation; regression progressing (October 13, 11:42 PM Chicago)

Capture-flags full regression compiled and passed eight wide-model cases with
zero mismatches. RemainingL12/one-word/boundary/eightH1024/Nexys stages are still
running. Controller22924 waits for complete proofs and unchanged cycle counts;
no new Vivado job launched yet. Never edit current/frozen RTL during these jobs.

Independent profile preparation now explicitly distinguishes capture-flags-large
from legacy/capture profiles: FIFOflag1, local_capture1, read latency5, controls3,
and exactfeature0x535901ff. Separate sysone-v2-capture-flags app / archive protects
both existing frontier and previous capture candidates. Legacy profiles require
FIFOflag0, and wrong-candidate/app/latency or a stale0x5359017f hardware capability
is rejected. 67 runtime/deploy/package tests passed2.35s; runner shellsyntax
passed. Packaging requires19source and unchanged-cycle evidence for grouped flags,
plus existing positive route/XSA/bit/fixture gates. No package or board upload.
Evidence build/v2/capture-flags-admission-tests.json.

Prepared candidate-specific route_capture_flags_large.ps1/.tcl, not executed;
explicit200MHz with reviewed placement receipt,19source/profile checks,2registered
FIFOstatus and896capture-register preflight gates, positive setup/hold/legal-route
proof, isolated Python/space-free export and payload-verifiedXSAcanonicalization.
Next priority remains complete full numerical admission and its automatic
synthesis, followed by actual synthesis/placement review. AutomationACTIVE.

## Measured FIFO cut passed OOC; grouped capture+flags regression running (October 13, 11:35 PM Chicago)

Focused AXI synthesis completed: original pointer-to-request-ready cone1path,
registered length-FIFO flags0paths. Resource cost281 ->283FF /381 ->382LUT,
wall62.012s/45.451s; not placed/routed200MHz evidence. Full/empty flags from next
pointers preserve originalFWFT/reset/full-write rejection and add no interface
cycle. Component300153 comparisons and narrow26AXI scenarios passed.

Integrated optional REGISTERED_FIFO_FLAGS default0 in AXI port/KR260 wrapper;
only the depth4 length FIFO switches implementation. Defaults/other FIFOs remain
unchanged. Capability bit7 distinguishes enabled cut; grouped capture+flags has
feature0x535901ff, still read latency5 andH1024 capacity. Current capture frozen
placement and deployed dot7 unchanged. No Vivado active after OOC completion.

Fresh full regression session78414 in build/v2/rtl-capture-flags-check, snapshot
and source hashes frozen before compilation. It repeats32KR260cases andNexys
defaults. Hidden controller22924 (capture-flags-controller*) waits for completion;
freeze_capture.py --flags independently admits proofs, requires every encoder
cycle count unchanged versus capture, freezes19sources, then launches one full
200MHz synthesis in build/v2/kr260-opt-capture-flags-large. No premature build,
placement or route. Never edit RTL under these jobs; inspect logs/ancestry first.

Prepared place_capture_flags_large_candidate.ps1/.tcl for later synthesis review;
route/export/deployment profile integration for the newflags candidate is still
pending physical qualification. Existing capture-specific guards should reject
it meanwhile. Automation prompt updated and confirmedACTIVE to follow this new
candidate, explicitly preserving/rejecting marginal capture200MHz placement.
Next: complete regression, inspect admission/controller (including cycle gate),
then synthesis/resource/flags/memory review before placement. No board changes.

## Capture placement reviewed; correct measured control cone before route (October 13, 11:27 PM Chicago)

Placement completed: native opt105.803s / place1071.586s. Used86167LUT,
64996FF,36URAM,610DSP,CLB13943/14640=95.24% (dot7was98.18%). Congestion still
level5 in attention/linear/dot regions. Sweep estimates125:+3.068,150:+1.735,
200:+0.068,250:-0.932,300:-1.599ns. Placed hold at200MHz:-0.094ns/290endpoints;
route must later resolve and prove positive hold. No routed qualification.

Worst path now length FIFO read pointer -> full/descriptor readiness -> attention
state and local accumulator read_word input. Data4.562ns (logic.812/routing3.750),
8LUTlevels, final control netfanout256 and1.355ns estimated route. Recorded
placement/review.json and hash-bound route-review.json with route_approved=false:
200MHz0.068ns is below0.5ns admission. Do NOT spend route or package this candidate
as200MHz. Frozen capture placement/DCP/source evidence remains intact.

Already acting on measured bottleneck: experimental registered next-pointer
full/empty FIFO flags keep existingFWFT/full-write rejection/async-reset semantics
and add no interface cycle. 300153 comparisons passeddepth4/8/64. Narrow AXI
length-FIFO-only variant (not otherFIFO instances) passed26 retired AXI scenarios
across direct/registered requests; source variants frozen in
build/v2/axi-length-flags-probe/sources. Production/frozen RTL unchanged. A focused
OOC comparison is active: session50327, Vivado32212 parent30320, one heavy job.
Baseline reproduces pointer-to-request-ready path; inspect flags profile result
and completion-status before integrating/launching new full regressions.

If focused cone/fit gate passes, integrate an optional length-FIFO flag cut into
an isolated next grouped capture+flags candidate, preserve defaults and require
full32KR260/Nexys numerical regressions before synthesis/placement. No current
or deployed source edits under test. Automation ACTIVE;200MHz milestone open.

## Independent high-DDR retirement/AXI composition passed (October 13, 11:20 PM Chicago)

Capture placement continues under Vivado9560, in post-placement timing
optimization at last read. No duplicate job, routing or capture-source changes.
Independent retirement scheduler is now composed with frozen dot7 AXI-port/FIFO
RTL:26scenarios (13each direct/registered) passed. Scoreboards verify40-bit
addresses,65535beat maximum,256beat/4KiB AR splitting, every data beat/last,
rejected range/capacity requests, blocked later faults, early/last RRESP full
drain, typed completion/poison and coordinated-reset recovery. Port/FIFO source
hashes match frozen dot7. Evidence build/v2/relative-retire-axi. New runner CRLF
error occurred before simulation, corrected to LF; both profiles then passed.
Still not SYS3 executor/config integration, PS high-DDR mapping, boot reservation
change, hardware validation or a watchdog/timing bound. Updated contract records
these limitations. Primary next action remains completed capture placement
review, followed by evidence-supported200MHz route or measured RTL correction.

## Placement continues; retirement fault coverage strengthened (October 13, 11:13 PM Chicago)

Vivado9560 is actively progressing through global placement/physical optimization;
observedCPU1630s earlier, native Global PlacementCPU20m03/wall9m49 at latest log.
No missing/dormant job was restarted, no capture/frozen RTL changed and no route
launched. Read placement completion/sweep/congestion before the next heavy step.
Independent relative-read retirement test strengthened to99requests and34memory
descriptors: early first-beat fault drains all three beats under backpressure
before completion/poison; late last-edge fault and coordinated-reset recovery
remain passed. Initial98case proof retained. Updated summary/source hashes in
build/v2/relative-read-retire and contract documentation. This is controlled
memory-model testing, not actual AXI composition/executor/high-DDR hardware.
Automation remains ACTIVE toward physically qualified200MHz candidate.

## While placement runs: serialized high-DDR retirement (October 13, 11:09 PM Chicago)

Capture placement remains active in Global Place Phase1 under Vivado9560;
no duplicate job or capture/frozen RTL edits. Advancing independent SYS3 work:
relative_read_retire.sv serializes the previously proven descriptor adapter so
local window/capacity errors cannot overtake an earlier memory read. It drains
response faults, samples sticky response status after last data acceptance,
returns code3 and poisons until coordinated reset. No watchdog/hard bound.
Focused98request simulation passed with exactly33memory descriptors and98
completions, high-address descriptor stability, stalled read data/completions,
blocked later errors, last-edge fault and reset recovery. Summary/source hashes
in build/v2/relative-read-retire. Existing raw adapter/window sources unchanged;
new module is outside frozen18capture sources. No AXI-port composition, SYS3
executor integration, PS high-DDR mapping or hardware claim yet. See updated
relative_read_contract.md. Next priority still completed placement review and
200MHz routing decision using actual physical evidence.

## Capture synthesis passed; placement running (October 13, 11:00 PM Chicago)

Controller completed synthesis and all admission gates at03:59:09UTC. Full
synthesis/project/diagnostic wall20m45s (controller1741.294 minus496.229s waiting;
not a controlled comparison with the older300MHz build). Used93620LUT,
65841FF,59BRAM,36URAM,610DSP; all36URAM output registers present. All896 local
capture FF survived, dot pairs/quads/octets registers4608/2432/1280 present,
query enables1024 with max16loads and accumulator controls1024 with max54loads.
Shared accumulator RAM inventory23552cells retained. Source18hashes passed.

Synthesized200MHz worst setup estimate +0.685ns, instruction register ->
embedding p_term synchronous-set pin. Data3.923ns (logic1.691 / estimated
routing2.232),13logic levels. This is not physical clock closure. High-fanout
review also found new capture selection/decode nets with914loads; inspect their
physical replication/locality along with URAM output distribution during place.
Do not assume DONT_TOUCH fabric capture guarantees local placement.

After reviewing the above timing/resource/pipeline/fanout evidence, launched
place_capture_large_candidate.ps1 session22188. It reran synthesis admission,
hash-checked the frozen sources and is running optimization/placement with a
125/150/200/250/300MHz diagnostic sweep. Check placement/completion-status.json,
console.log and actual Vivado ancestry. One heavy job only; no source edits.
No route started. Prepare a hash-bound route-review receipt only after reading
placed critical paths, density and congestion; require meaningful200MHz margin.

Independent cycle comparison verifies all wide-model fixture bytes against the
older frozen source table. Capture adds0.0173..0.0703% encoder cycles in eight
random-stall simulation cases at the sameH1024 capacity. Report:
cycle-comparison.json. These are cycle costs, not projected hardware speed or
hard bounds; physical DDR waits may change with clock frequency.

Prepared route_capture_large.ps1/.tcl, not executed: explicit200MHz only,
positive setup/hold and legal routing gate, no silent125MHz fallback, space-free
S: export cwd, isolated Python (-I), exact-payload XSA canonicalization with
original header backup. It still requires candidate-specific reviewed placement
receipt and source/report hashes before launch. No new export/board changes.

## Capture packaging preparation (October 13, 10:47 PM Chicago)

Synthesis is still active under controller12592 / Vivado32700. Ancestry confirms
encoder Vivado14468 and parallel-synthesis children15468/27652 belong to this
same project/job; they are not duplicate full builds. Current encoder synthesis
is inferring/mapping memories. No additional heavy Vivado job launched and no
RTL or frozen source edited.

Independent deployment preparation: package_app.py now has capture-large
profile/latency5 and a separate sysone-v2-capture app and
kr260-app-capture-large.tar.gz output. Packaging verifies all frozen eight-H1024
fixture bytes and requires32case/latency5 evidence, generated pipeline flags,
all18frozen source hashes, exact final XSA/bit match and positive legal route
proof as before. Actual frozen fixture hash was checked against regression.
No package/bitstream was produced: early packaging attempt correctly refused
missing implemented bitstream. 58 package-profile/runtime/deploy tests passed
3.36s, including tampered/missing golden-case rejection; deployment runner shell
syntax passed. Runner selects the capture directory, preserves current frontier
as a valid recovery app, and restores original software/model on failure.
No board upload or memory change. Evidence capture-packaging-preparation.json.

Next action remains full synthesis/resource/pipeline review, then prepared
place_capture_large_candidate.ps1. Do not route based only on synthesized/OOC
estimates. Capture runtime-clock identity/export helpers must be written from
actual legally routed200MHz evidence before packaging; no timing qualification
has been set by these preparatory edits.

## 200 MHz full synthesis started (October 13, 10:38 PM Chicago)

Frozen capture regression completed: all32KR260 cases +2Nexys default cases
bit-exact; latency5 streaming96chunks and240000 seven-memory reference checks
passed. Controller12592 automatically admitted evidence and froze18RTL sources;
all18snapshot hashes rechecked after Vivado launch. New candidate:
build/v2/kr260-opt-capture-large, feature0x5359017f, read latency5, maxhidden1024.
Vivado32700 parent788 is the one full synthesis job (children same job allowed),
target200MHz. Controller status/log in build/v2/capture-controller*; build-local
completion-status now synthesizing. Never edit sources under this run or launch
a second heavy job. Preserve dot7-large deployed125MHz and all frozen evidence.

Prepared and tested separate sysone-v2-capture firmware admission offline:
55 runtime/deploy tests passed2.04s; capture-large requires latency5/capture1/
shared-controls3, legacy profiles still latency4/capture0, finite positive routed
setup/hold and enabled matching PL0/PL1 clocks. New app directory is distinct
from installed sysone-v2-frontier; no board change was made. Packaging support
and actual200MHz route/hardware qualification remain pending. See
capture-200-review.md / build/v2/capture-admission-tests.json.

Next: controller reviews synthesized resource/URAM/dot/control/local-capture
count gates. Read full preflight timing/packing/fanout and controller status when
completed; only then run place_capture_large_candidate.ps1. Prepared script
hash-checks frozen sources and obtains200MHz placement plus125/150/200/250/300
estimates/congestion; no auto-route. Inspect actual placed bottleneck and density
before route. A positive isolated synthesis estimate is not200MHz closure.
The local capture stage was the only new integrated arithmetic/memory cut;
linear-drain and embedding prototypes remain outside this candidate pending
full engine tag/latency proofs. Do not claim they are already grouped/integrated.

## Resumed: prioritize 200 MHz capture candidate (October 13, 10:30 PM Chicago)

User continued work and then explicitly requested a 200 MHz candidate. That is
now the next deployment target; 300 MHz remains longer term. Automation confirmed
ACTIVE with the updated milestone. Preserve deployed dot7-large at 125 MHz.

New optional LOCAL_READ_CAPTURE defaults0 across encoder layer/system/KR260
wrapper. Enabled adds one aligned read cycle (4 -> 5), local per-physical-buffer
capture before the shared mux, delayed physical selector, and capability bit6.
Both engine reads and result-streamer/host wait latency were updated together.
Production option is experimental until full regression and route/hardware gates.
No deployed firmware or frozen dot7 sources changed.

Focused results: 32768 port comparisons; seven actual activation memories with
240000 independent reference comparisons including masked writes, read-first
collisions, 4K cascade boundaries, selector collisions/invalid7. Result streamer
passed96 chunks at latency3/4/5 under initial prolonged and random backpressure.
First standalone streamer run lacked sync_fifo dependency; failed log preserved,
runner dependency corrected and retest passed. No data-path fix was needed.

Focused synthesis: baseline36URAM /641FF /1036LUT primitives, capture36URAM /
1525FF /1036LUT primitives; all896 local capture FF preserved. Baseline native
wall77.872s, capture53.933s. Synthesized URAM path estimated data2.657 ->2.367ns
and final output fanout4 ->1 in the isolated probe. These are not placed/routed
full-system improvements. The deployed net had fanout24 after replication and
5.167ns routing; full placement/congestion remains critical with CLB98.18%.

Integrated frozen regression session39947: build/v2/rtl-capture-check and its
snapshot.txt. H1024 maximum capacity, feature5359017f, wide/L12/one-word/boundary/
eight-H1024 fixtures, then unchanged Nexys defaults. Planned32KR260 cases +2Nexys.
Compiler consumed one core for several minutes; actual numerical cases started
passing, so do not kill/recompile merely for quiet compiler output.

Hidden follow-through controller PID12592: run_capture_after_regressions.ps1,
status build/v2/capture-controller-status.json, log/err alongside. It waits for
completion, independently gates32cases, current/frozen source hashes, memory and
latency5 streamer evidence and OOC inference, freezes18RTL sources in
build/v2/kr260-opt-capture-large, then launches one full synthesis at200MHz.
No automatic placement/route. Inspect completion and actual child process ancestry
before launching jobs; preserve failed attempts. Do not edit RTL while frozen
regression or synthesis runs. Next action after synthesis: review capture count,
resource/URAM/control/pipeline gates and measured critical paths, then placement
at200MHz and clock sweep; route only after review supports it.

## Milestone completed: deployed dot7 H1024, October 13, 22:46 UTC

This entry supersedes the historical active/export/unreachable entries below.
Dot7-large is packaged, legally routed at 125 MHz, deployed on KR260 revB and
hardware qualified. All 17 frozen RTL source hashes and packaged firmware hashes
were rechecked. Final archive: build/v2/kr260-app-frontier-dot7-large.tar.gz;
SHA256 1fe8bd802b0de4559e808e587138ff67139c0911904cca3e54fe680fc8279d8d.
Canonical bit SHA256 4b0dae37b8b343a8c7267949cd2a44eb5acaa837592020930ce1e29c6d59430a;
FPGA payload SHA256 e68abfa721671f840d9653cf0c038fc2e02cae434cb491fe8ac7cd72cff270ab.
Exact XSA/bit match was retained after checking timestamp-only differences.

Hardware: 350/350 frozen L12 cases and eight synthetic H1024 cases at lengths
1,2,3,4,5,12,64,128 are bit-exact. Eight L12 smoke lengths also passed.
Matched-suite comparison verified identical image/suite hashes, hidden tensors,
case IDs, predictions and accuracy counts. Mean L12 encoder time 17.27168 ms
versus baseline 17.18768 ms (0.49% slower); maxima 57.98782 versus 57.65258 ms.
This expands supported hidden width to 1024; it is not a measured speed/quality gain.
H1024 is a synthetic one-layer/FFN4096 test, not a trained large-model evaluation.
H1024 encoder times range 6.422 ms (1 token) to 29.644 ms (128 tokens).
Reports: build/v2/eval/kr260-dot7-hardware/{comparison,qualification}.json and
its two hardware report directories. Both board validation-status files passed.

Current board app sysone-v2-frontier, live clock 124999999 Hz; L12 image restored
with identical DDR readback. Recovery app sysone-v2-memory remains installed.
Native SSH session closed after confirming current app. No credentials saved,
no boot-memory changes. Live dedicated low-DDR reservation is 256 MiB at
0x60000000. SYS3 high-DDR addressing and decoder/INT4 production integration
remain incomplete; this does not exhaust 4 GB DDR or generate answers on FPGA.

Route: WNS +0.401 ns, WHS +0.010 ns; all 164277 routable nets fully routed,
zero routing errors. Native synthesis 31m24s and route 25m21s. Placed resources:
90278 LUT / 64513 FF / 59 BRAM / 36 URAM / 610 DSP, 98.18% CLB occupancy.
300 MHz remains unclosed. Routed critical path is URAM output distribution:
7.250 ns data, 5.263 ns routing, final DOUT net fanout24 / 5.167 ns.
All36 URAM OREG_A/B true; REG_CAS_A/B false. Next grouped optimization should
shorten/register per-buffer output distribution, prove cascade latency changes,
and combine independently verified linear drain/embedding cuts before another
expensive full build. Preserve this qualified package and frozen sources.

Failures retained: original route export label guard, inherited PYTHONHOME,
spaced-path XSA export, and first board deployment's outdated mode1 guard.
Deployer/runtime now require controls3 only for recorded dot7-large; mode1
legacy profiles retained. 45 runtime/deploy tests plus 12 deployment tests passed.
Software-only retry left RTL/bit payload unchanged. Original archive and failure
logs preserved. Export wall time included confirmed laptop lid standby; do not
claim uninterrupted execution or attribute standby to Vivado computation.

Independent verified experiments remain outside this frozen build: relative
read adapter/AXI contract (including max65535 beats), raw INT4 dot16 elastic
primitive, per-bank linear drain selection and embedding arithmetic equivalence.
They are not integrated capabilities or demonstrated frequency improvements.
No hard request/first-word timing guarantee is claimed. No Vivado jobs remain.
The specified package-and-hardware milestone is complete. The app confirmed
kr260-overnight-optimization PAUSED at this boundary, as instructed for milestone
completion. The 300 MHz goal and full high-DDR/generation work remain open.

Written 2026-10-08 for whoever continues this project (person or AI agent). It is meant
to be read without any earlier conversation. Read this first, then `rtl/v2/README.md`:
it has every result and design decision, and a log of problems hit and how they were
solved (29 entries, generation acceptance criteria remain open).

**Active priority (2026-10-10): KR260 FPGA RTL optimization and larger models.**

## Current export stage: XSA-only space-free retry (October 13)

Legal routed netlist and bitstream exist. First recovery failed on Vivado's
inherited PYTHONHOME; isolated child Python (-I) was verified against mismatched
libraries, then recovery2 generated bitstream successfully. Its XSA failed on
Vivado internal .Xil path spaces. All failed attempts are retained, including
sysone_v2_kr260.failed-spaced-path.xsa when present. Do not reroute/regenerate
the completed build from scratch. XSA-only export session1591 uses explicit
space-free Tcl cwd in route-125mhz/xsa-export from the qualified DCP. Inspect
that status/process, not the previous export-recovery-2 failed status.

Final routed worst path is now URAM cascade/output -> shared port register:
7.250ns data, 5.263ns route, fanout24. Read routed_memory_timing_review.md for
next memory hierarchy cuts; OREG inference alone did not guarantee short routes.
Bitgen reported CPU4m03s/elapsed1h40m50s; Windows records lid standby15:13:56
to16:53:05 America/Chicago. Do not attribute that interval to active build cost.
Board remains unavailable; no upload. Package once XSA/bit checks pass; automatic
continuation remains ACTIVE and no production RTL was edited under the builds.

## Route passed; export recovery ACTIVE (October 13, 19:57 UTC)

Dot7 route completed legally in native 25m21s: 164277/164277 routable nets fully
routed, zero routing errors. Final report setup +0.401ns, hold +0.010ns, both
PL clocks 125MHz; all constraints met. Original export guard incorrectly expected
"Fully Routed" instead of Vivado's "Routed" label. Failed attempt/log/guard script
preserved. Corrected validator checks actual net counts and positive setup/hold;
14 gate tests passed. Do NOT reroute or overwrite original failure evidence.
Export-only recovery session 32551 / Vivado PID 25688 parent16268 is active from
the existing routed checkpoint, in route-125mhz/export-recovery. Read that status
instead of interpreting the original route directory's failed status as a new
routing failure. No synth/place/route repeated. Dot7 packaging support prepared
(15 targeted tests passed), but do not package until bit/XSA export completes.
Hardware validation remains unavailable after SSH TCP timeout. Automation ACTIVE.

## Latest stage October 13, 19:30 UTC: dot7 125MHz route ACTIVE

Heartbeat 19:52: isolated two-stage per-bank drain selector passed 24576 packet
comparisons across channel counts 12/32 and lanes 1/2/4. It targets the measured
BRAM-to-DSP path without copying full rows; full-engine integration and timing
proof remain pending. See linear_drain_timing_review.md and the source-hashed
build/v2/linear-drain-select/summary.json. Route iteration 2 reached zero overlaps
with intermediate setup +0.401ns; hold is unresolved (last reported -0.047ns,
later N/A). No final route qualification. Board SSH TCP probe timed out; no
authentication/deployment attempted. Keep the job and automation ACTIVE.

Heartbeat 19:42: independent int4_dot16.sv arithmetic primitive passed 6145
Python-oracle vectors, stream/stall/reset checks and consecutive requests.
It is NOT in the frozen build or model; synthesis/calibration/integration remain
pending. See int4_dot_contract.md and build/v2/int4-dot16/summary.json. Route
PID 15460 remains in rip-up/reroute; overlap counts fell 126607 -> 33605 during
iteration 1, still partial/incomplete routing. No export or hardware replacement.

Heartbeat 19:32 continued independent translator-to-frozen-AXI simulations:
24 scenarios passed in direct/registered profiles, including maximum beat count,
page splits, rejected requests, reset and RRESP faults. A later local fault can
precede earlier memory data: executor integration needs serialized retirement
or request IDs. Evidence build/v2/relative-read-axi/summary.json. Routing PID
15460 reached Rip-up And Reroute, global iteration 1 (native elapsed 4m35s).
Global/short congestion is level 5 and timing congestion level 6; no final
setup/hold qualification yet. Preserve this job and do not duplicate it.

Placement finished and all five clock/congestion reports were reviewed. One
conservative route started in session 44811, Vivado PID 15460 under 32956.
Preserve build/v2/kr260-opt-dot7-large/route-125mhz and its frozen placed DCP.
Do not repeat placement, launch another heavy job or edit the tested RTL.
Route receipt and review: placement/route-review.json, dot7_placement_review.md.
Estimated WNS at 125/150/200/250/300: +2.921/+1.588/-0.079/-1.079/-1.746ns.
Placed LUT 90278, FF 64513, CLB sites 98.18%, congestion level 5. Legal routing
remains uncertain. Actual 300MHz worst path is linear BRAM-to-DSP selection,
not the synthesized embedding path; see linear_drain_timing_review.md.
Require fully routed positive setup/hold before packaging, then board tests.
The validated 125MHz memory app remains unchanged; automation stays ACTIVE.

Independent SYS3 relative read descriptor adapter passed 542 SV cases (beat
widths 16/8) plus 30 Python memory-window/relative-model tests. It filters
window/beat-count truncation faults before memory and supports a separate
backpressured error completion. Lazy descriptor chunking covers 4GiB without
allocating a model. It is NOT in the dot7 project/deployed executor, and no
high-DDR/PS/board integration or new boot memory is established. Evidence:
build/v2/relative-read-request/summary.json; relative_read_contract.md.

## Heartbeat October 13, 19:16 UTC: host standby delay; placement progressing

PID 25692/controller ancestry remains the same one job. Placement is now in
Phase 4.1.1 post-placement optimization. Last logged native elapsed 2h25m18s,
CPU 52m28s; elapsed includes about two hours of Modern Standby, confirmed by
Windows Kernel-Power lid/standby events (12:10..14:10 America/Chicago).
Do not attribute that inactive period to RTL congestion or change power settings
without user steering. Evidence: build/v2/dot7-placement-power-events.json.

Independent embedding arithmetic prerequisite passed 786432 SV cases (all
64x64 shift pairs, signed product/type boundaries and randoms). Production RTL
unchanged; full engine/timing equivalence still pending. Separate dot7 routing
scripts prepared with active-job, frozen-hash, profile and review-receipt gates;
no route receipt exists and no routing launched. See continuation report and
embedding_requant_review.md. Existing package_app.py still targets dot5 for
--frontier; adapt dot7 packaging only after its route qualifies. Automation ACTIVE.

## Sustained follow-through restored (October 13)

Heartbeat review at 17:06 UTC: dot7 placement PID 25692 remains active in
Physical Synthesis In Placer, last native placement elapsed 14m12s before that phase.
No completion checkpoint or frequency sweep exists yet; no route launched.
Independent timing-policy/profiling validation fixes passed 50 targeted tests.
See continuation-2026-10-13.md and build/v2/timing-profile-validation.json.
Do not rerun those tests unless changing the software again. No RTL was edited.

User explicitly called out failure to sustain work between build stages. The
existing kr260-overnight-optimization heartbeat is now verified ACTIVE every
ten minutes; expired October 12 cutoff removed. Continue acting on authorized
next stages without waiting for update requests. Do not pause at status-only
milestones. Quiet notifications for unchanged progress. No persistent Goal was
created; scheduled follow-through is the actual configured mechanism.

Placement remains active in session 72255 (PID 25692 observed through CIM).
No RTL under test was edited. Independent embedding path/width audit saved in
scripts/v2/kr260/embedding_requant_review.md. See continuation-2026-10-13.md for
the acknowledged five-hour gap, restored scheduling and concrete next actions.
Historical statements below that automation is paused are superseded here.

## Latest result: dot7 full synthesis passed; placement active (October 13)

Full synthesis/resource/RAM/fanout gates passed in 1884.097 seconds (31m24s).
Actual resources: 96555 CLB LUTs, 64795 registers, 59 BRAM tiles, 36 URAM,
610 DSPs. Versus failed dot5: 5894 fewer LUTs (5.8%) and 48440 fewer registers
(42.8%). All 36 URAM outputs registered; query/accumulator max loads 16/54.
300 MHz unplaced setup WNS remains -0.957 ns; worst instruction_reg[284] ->
embed_inst/p_term. No 300 MHz closure or new hardware performance is proven.

Queue/preflight completed successfully; regression session 89075 completed.
One full optimization/placement diagnostic is now active in session 72255:
scripts/v2/kr260/place_dot7_large_candidate.ps1. Status/logs/checkpoints in
build/v2/kr260-opt-dot7-large/placement. Review congestion and estimates at
125/150/200/250/300 MHz before routing. Do not duplicate or edit frozen RTL.
No routing or upload launched; old 125 MHz board app unchanged. Automation ACTIVE.

## Previous work: dot7 address cursor and shared attention read (October 13)

User authorized proceeding. Residual read addresses now use a sequential cursor
with a carry retained before halving for INT8 reads. Focused equivalence passed
281736 writes across widths 16..1024, non-power-of-two rows, 128-token boundary,
reset/restart and all shift values. Attention mode 3 shares a registered RAM read
address; it switches to output addressing only after weighted updates drain.
Modes 0/1/2 and frozen dot6 evidence are retained. No new FPGA app/boot changes.

Frozen full regression runs in session 66766, snapshot in
build/v2/rtl-dot7-check/snapshot.txt (mode 3, pipelined dot). Session 89075 reuses
its H1024 executable for extra cases after the base completes. Both isolated
OOC comparisons completed. Residual CLB LUTs 2978 -> 2865; four-lane shared-read
attention CLB LUTs 8944 -> 7513 (-16.0%), memory LUTs 3144 -> 1672 (-46.8%).
All 32 base KR260 cases, two Nexys cases and streamer stress passed; base/source
summary verified. Eleven extra focused shared-read equivalence profiles passed
against frozen dot6 with nonzero data, dim=48, head/group transitions, stalls and
weighted-phase reset/restart; current/reference hashes verified. Base session
66766 and focused session 28458 completed. The 21 extra H1024-profile cases in
session 89075 subsequently passed. All 53 KR260 cases passed with unchanged
encoder cycle counts; 17 sources are frozen in kr260-opt-dot7-large/rtl-snapshot.
Full synthesis started at 2026-10-13 11:01 UTC (06:01 America/Chicago). Queue
session 7009 is running_preflight; candidate state is synthesizing. The main
encoder optimization completed without errors; netlist translation/top reports
are still pending. Do not edit RTL or duplicate this build. No routing/deploy.

Local dependency session 7009 is active: run_dot7_after_regressions.ps1 waits
for complete 53-case/source/OOC gates, then starts one synthesis-only preflight
at an exploratory 300 MHz constraint. It detects test failure and times out at
two hours. Queue status/log: build/v2/dot7-queue-status.json / dot7-queue-console.log.
Require resource/RAM/fanout gates and 5% LUT relief versus failed dot5 before
placement. No routing/upload is queued; automation stays paused. See dot7_review.md.
Do not edit RTL under these tests or duplicate any job. Review failures before
more synthesis; require numerical/source and OOC gates before full placement.

## Previous result: dot6 numerical and focused synthesis gates passed

User-authorized width/congestion follow-up is implemented and tested. All 53
KR260 cases, 2 Nexys cases and streamer stress checks passed; encoder cycle
counts match dot5. Residual equivalence passed 49152 writes; dot WIDTH 1..32
passed 4096 full-signed-input vectors. Frozen 17 RTL sources and regression
hashes: build/v2/kr260-opt-dot6-large/rtl-snapshot and regression.json.
No jobs remain active; sessions 10651, 65862, 13494 and 84182 completed.

Focused synthesis CLB LUT counts: residual 3434 -> 2978, dot32 9088 -> 8512.
Dot registers 9472 -> 8992. Four-lane attention RAM mode inferred successfully:
registers 10099 -> 4108, total CLB LUTs 8996 -> 8944, memory LUTs 200 -> 3144.
Residual OOC setup estimate at 3.333 ns improved -0.327 -> +0.185 ns. These are
isolated synthesized estimates, not full-design routed timing or resource totals.
See scripts/v2/kr260/dot6_review.md and build/v2/dot6-ooc-summary.json.

No complete dot6 synthesis/placement/routing or hardware upload has started.
Keep deployed 125 MHz memory app intact. Before another expensive full build,
review residual address cursors and sharing attention RAM reads across drained
accumulation/output phases; these additional changes are NOT implemented yet.
Retain legacy/localized-register modes 0/1 and frozen failed dot5 evidence.
Automation remains paused. Entries below are historical snapshots.

## Latest completed result: dot5-large routing failed (October 12, 2026)

The 150 MHz H1024 candidate failed legal routing after 3h19m32s of native
Vivado elapsed time: Route 35-2 reported 6236 node overlaps. No qualified
bitstream or XSA was exported, and no replacement FPGA app was uploaded.
The intermediate setup WNS -0.482 ns was not a final timing qualification.
The 125 MHz fallback was never reached because route_design itself failed.
There are no active Vivado jobs. Preserve the frozen RTL, placed/physopt
checkpoints and route-150mhz logs; do not repeat the same expensive route.

The last verified board state remains sysone-v2-memory at 125 MHz. The
requested software upload passed 350/350 frozen L12 cases, with unchanged
hidden outputs, integer logits, predictions and accuracy. Evidence:
build/v2/eval/kr260-frontier-software-hardware/comparison.json.

The blocker is physical congestion/connectivity, beyond clock slack alone.
Placement reported congestion level 5 and dense DSP regions. Failed routing
examples include attention local accumulator storage/control nets. Before
another full build, investigate these structures and batch width reductions:
the measured residual path uses unnecessary 64-bit clamp/add arithmetic,
and dot reduction stages can use proven narrower intermediate widths.
Require numerical regressions and resource/OOC evidence before a new heavy job.
Automation remains paused. Earlier entries below are historical snapshots.

## Previous result: requested software upload verified; routing left intact

The updated programs are uploaded to the current KR260 and independently
verified against the prior frozen baseline: 350/350 bit-exact, identical hidden
outputs, integer logits, predictions and accuracy counts. Current 125 MHz
sysone-v2-memory remains active. Software transfer is complete; see
build/v2/eval/kr260-frontier-software-hardware/comparison.json.

The new H1024 RTL has NOT been deployed. Route session 46850/PID31044 remains
active and was explicitly left running. The passive monitor was stopped, not
Vivado. Authenticated SSH shell 50922 was closed after completed board tests.
Route native elapsed reached 2h00m59s at the end of global iteration 1;
intermediate 150 MHz setup WNS -0.482 ns, not qualified. Global iteration 2
started with overlaps 212896 -> 135884. Counts reset between iterations and
are not an overall percentage or ETA. Final routing/hold results remain pending.
Do not duplicate this heavy job, modify frozen RTL, or upload its bitstream
before routed qualification. Review the planned 125 MHz fallback, final export,
--frontier packaging and hardware validation when routing finishes.
Automation remains paused; no new recurring schedule was created.

## Software uploaded and independently verified; new RTL still pending

Compatible programs were uploaded over SSH to the existing KR260. Archive
build/v2/kr260-software-verified.tar.gz SHA256
5022c9b69ea87f928083ddd15a5e63154c59a339d463663dfe11cbeaa932ab8d
matched on the board before extraction. install_software.sh backed up and
updated the client, kr260_runtime.py, kr260_link.py and timing_policy.py.
No FPGA app or boot memory was changed. One-token check passed, followed by
350/350 frozen L12 cases bit-exact. Downloaded evidence:
build/v2/eval/kr260-frontier-software-hardware/{eval.json,comparison.json,
check.log,eval.log,status.txt,before/}. Independent comparison confirms identical
image/suite hashes, hidden outputs, integer logits, predictions and accuracy.
Mean encoder 17.1876844 ms at 124999999 Hz; effectively unchanged from baseline.
This is a software upload, not a newly deployed RTL candidate.

Pre-upload live old-app checks passed at 1/128 tokens: 1394686/7495795 encoder
clocks (11.16/59.97 ms). Evidence kr260-frontier-predeployment.json. The 128-token
Python integer reference took minutes, while hardware took ~60 ms; the uploaded
client now prints that reference-computation stage explicitly.

Dot5-large route session 46850/PID31044 remains active in congestion cleanup,
latest overlaps 199513 -> 85674 -> 41491 -> 23078 -> 14545. No new bitstream
has been exported or uploaded yet. Preserve the running job and continue routed
setup/hold qualification, --frontier packaging, transfer and hardware validation.
Authenticated SSH shell 50922 is idle in ~/system-one-fpga. Do not repeat the
completed software upload or full synthesis/placement. H1024 package now also
requires fixture manifest equality with the frozen regression reference, and
validator records expected/hardware output hashes. Never store credentials.

## Current authorization: verify and upload dot5-large to KR260 (October 12, 2026)

The user confirmed the current KR260 and authorized verification followed by SSH
upload/deployment. Read-only SSH verified sysone-v2-memory active, PL0 clock
124999999 Hz and dedicated no-map DDR reservation 0x60000000..0x6fffffff (256 MiB).
Keep that app available for recovery; no boot-memory change is needed.

Dot5-large synthesis completed: 102449 LUT, 113235 FF, 59 BRAM, 36 URAM
(all output-registered), 610 DSP. Estimated unplaced 300 MHz setup -0.957 ns,
versus dot4 -2.084 ns. This does not qualify 300 MHz.
Full placement completed: optimization 118.148 s, placement 1138.261 s.
Placed margins: 125 MHz +2.952 ns, 150 +1.619 ns, 200 -0.048 ns,
250 -1.048 ns, 300 -1.715 ns. Congestion level 5. The worst path at
150 MHz is add_skip rounded -> out_data, 14 levels, 4.849 ns.
Routing at reviewed 150 MHz is ACTIVE exec session 46850, output
build/v2/kr260-opt-dot5-large/route-150mhz. No second heavy job.
Only one heavy Vivado job. Do not edit the 17 frozen RTL sources.

Prepared route_frontier.ps1/.tcl: require reviewed placed margin >=0.5 ns;
reuse the placed DCP, physical optimization and routing, setup/hold gate before
bitstream/export. Slower 125 MHz fallback may reuse routing but must pass both.
Prepared package_app.py --frontier, runtime/deployer clock and feature guards,
deploy_frontier.sh recovery, and validate_h1024.py. 53 host guard/comparison
tests passed; evidence build/v2/eval/kr260-frontier-host-tests.txt.
The bundle now updates/backups the client and timing-policy module too.
Board VENV has no installed sysone package: validator explicitly adds the
selected repository src path. Host validation decoded all three frozen
H1024 cases and verified the 15,029,248-byte image SHA256.
Persistent SSH shell exec session 50922 is authenticated and idle; never
store credentials. Route session 46850 is active, PID 31044; cleanup overlaps
199513 -> 85674 -> 41491. A read-only memory-pressure sample is recorded
in route-150mhz/memory-pressure-sample.json. No applications were closed
and no global WSL or system settings were changed.
Package, upload and hardware tests are pending routed qualification. Hardware
plan: three frozen synthetic H1024 cases, reload L12, eight input lengths and
350 frozen L12 cases. Synthetic capacity is not pretrained model quality.
Preserve old app, helpers and numerical baselines. Automation remains paused.

## Dot5 request-arbitration fix verified; full synthesis active

All53KR260 numericalcases pass (base32+H1024extra21), plusNexys2 andoutput64
stallchunks. RegisteredAXI protocoltests pass low/high requests,300beatburst
splits/4KiB boundaries,backpressure,clean0errors/injected1error,32simultaneous
reads/writes,descriptorreplacement andresetcancellation. Sources/hashes locked.
Small nativeAXI OOCsynthesis proves read_request_valid ->write_request_ready
combinationalpath: directmode1path,registeredmode0paths. 68.213s/55.341s for
two OOCprofiles. This is astructuralgate, not fullclockclosure: OOCclocksource/
skew nottop-qualified. Firstharnessrunfailed unsupportedremove_from_collection;
corrected Vivadoget_portsfilter, failurepreserved infailed-constraint-setup.
Evidencebuild/v2/axi-request-register-ooc andeval/axi-request-registers.

FullH1024 synthesis-only started via preflight_dot5_large_candidate.ps1,
exec8760, isolatedbuild/v2/kr260-opt-dot5-large. Includes numerical53cases,
protocolsourcehash andOOCpath-cut gates beforelaunch. Oneheavyjobonly.
Do notedit17frozenRTLfiles duringbuild; preserve olddot4artifacts. No
placement/routing/boardwork queued. Review completion-status/preflightreports
before selecting furtherRTL orplacement. Board unavailable peruser; validated
125MHzdeploymentfiles/Linuxreservation unchanged. Overnightautomationpaused.


## Registered AXI requests implemented; numerical qualification active

User authorized fixing request-arbitration timing. Board remainsunavailable.
Added optionalREGISTERED_REQUESTS toaxi_memory_port: oneelasticdescriptor
register perread/write direction, with simultaneousconsume/replacement and
resetcancellation. Upstreamread/write admission nowdepends onstoredpending
flags/core arbitration, notcurrentenginevalid. Corearbitration reads registered
valid/address/length, preservingreadpriority andwrite-data/burst behavior.
KR260PIPELINED_DOT1 enablesoption; default0directAXI andNexys preserved.
PayloadFFs do not reset; validbits reset. No newmodelABI/capacitybit required.
This cuts the traced engine-readvalid ->writerready ->streamerCE dependency;
actualtimingimprovement stillrequires synthesis/placement evidence.

Focused assertion-enabled testpasses32simultaneousread/write requests each,
replacement/backpressure, resetcancellation, highaddresses andorderedresponses.
AXIselftest passes directlow,registeredlow andregisteredhigh0x800000ff0;
300beatrequests/4KiB/256beat splitting/randomstalls,50read_last perrun,
clean0errors anddeliberatecorruption exactly1error. Evidence:
build/v2/eval/axi-request-registers/summary.json.

Fullnumericalregression ACTIVEexec57344, frozen
/var/tmp/sysone-batch-regression.z3L0hA, outputbuild/v2/rtl-dot5-check;
wide8cases alreadybitexact. H1024extra21cases queuedexec69202,
build/v2/rtl-dot5-large-check, reusesboundarybinary oncebasefinishes.
Do notedit17RTLfiles undertest. NoVivadosynthesis/placement/routing queued.
Preparedpreflight_dot5_large_candidate.ps1 (NOTlaunched): requiresbase32and
large21summary/sourcehashgates beforeisolatedkr260-opt-dot5-large synthesis.
Large runner/summarizer nowaccept explicitcandidate evidencepaths; defaults
preserve prior dot4 workflow. Detailedreports remaininloadedpreflight.
Preservepreviousdot4DCPs/reports/validated125MHzapp andLinuxreservation.


## Dot4 H1024 synthesis complete ï¿½ October 12, 2026

Synthesis-only gates passed; no jobs active. Launcherwall35m35s, encoder
synth_design17m36s. All17frozen sourcehashes match H1024 testedsummary.
102422LUTs (87.45%),113140FF,59BRAM,36URAM,610DSP. Compared dot3H768:
2187fewerLUTs,74moreFF,4moreURAM,onefewerDSP. This is anobservedcandidate
comparison, not a controlled attribution of LUT reduction. All36URAM outputs
registered; queryfanoutmax16,accumulatormax54; sharedreductionstages retained.
H1024 resourcefit is verified in synthesis, not yet timing/deploymentqualified.

Estimated300MHz setup-2.084ns; worstLINEARload_tile ->streamerleftCE through
requestarbitration,18logic levels,5.089ns total(1.691logic/3.398routeestimate).
Addresscursorpathisnot theworst reportedpath. Actualplaced improvement
remainsunmeasured; no placement orrouting queued. NativeDSP_*attributes now
recorded duringloadedpreflight, avoiding a secondinspectionload.
UltraRAMcascade warnings remain fordeeperbuffers; inspectphysicaltimingbefore
addinglatency. Prioritize breaking request-arbitration/ready control paths
and reducingattentioncongestion before another expensivebuild.
Preserveallcandidateevidenceandvalidated125MHzapp. Boardaccessunavailable;
noSSH/deployment attempted. LargerDDRwindow/decoderintegration remainopen.


## Dot4 H1024 numerical gates complete; synthesis active

Board unavailable peruser; no SSH/deployment. Attention hot read/output
address products replaced by FSM-alignedregistered cursors forPIPELINED_DOT1,
with no additional read latency. Default0legacyNexysaddressbehavior preserved.
All32baseKR260cases,Nexys2andoutput64stallchunks pass. Additional21cases
(wide8,L12eight,one-word5) pass onH1024profile; separate assertion-enabled
cursor test passes10profilesincluding48dimheads/tails/consecutivechangedshapes.
Total53KR260cases. Basewide/L12/one-word encoder cycle counts match dot3
exactly in frozen random-stall simulations; nohardware speed claim.

Started synthesis-only preflight_dot4_large_candidate.ps1, exec30302,
isolatedbuild/v2/kr260-opt-dot4-large. MAX_HIDDEN1024 vsdeployed768;
MAX_TOKENS128/MAX_HEAD_DIM64 unchanged. Target300MHz remainsdiagnostic.
Physicalresourcefit/URAMpipelineinference/fanout/timing remainPENDING.
No placement/routing/boardchanges queued; neveredit17RTLsources duringbuild.
Tclnowreports30criticalpaths,hierarchy andnativeDSP_*attributeinventory while
designisalreadyloaded, avoidinganotherstartup/checkpoint-loadinspectionjob.
Check completion-status.json andpreflightreports atnextcontinuation.
Synthesisgates includequeryfanout16,accumulator54,allURAMoutputregistration
andsharedreductionretention;large source hashes linked totestedH1024summary.

Evidence:build/v2/rtl-dot4-check/summary.json,
build/v2/rtl-dot4-check/address-cursor-comparison.json,
build/v2/rtl-dot4-large-check/summary.json,
build/v2/eval/attention-cursor-simulation/summary.json.
Modelsstillusecurrentv2window/format; enlarginghiddenlimit doesnotprovehighDDR,
expandedLinuxreservation orcompleteFPGAdecoder. Preservevalidated125MHzapp.
Overnightautomation remainsPAUSED; authorizeddaytimejobcontinues independently.


## Larger-capacity candidate prepared while numerical tests run

Prepared isolated dot4/large Vivado selector withMAX_HIDDEN1024, retaining
128tokens/64head_dim and existing controls. No change to deployed app orDDR
reservation. Build directorykr260-opt-dot4-large will be created only after
numerical gates pass. Synthesis fit/timing are not yetverified. H1024 model
width is33.3% above deployed768 limit, but actual supported model footprint
stilldepends onwindow/runtimecalibration; fullFPGAdecoder remains separate.

Additional H1024 tests queued inexec85320 via
simulation/v2/run_large_attention_capacity.sh. Waits for activebase44237 to
finish, then reuses its H1024 boundary binary withwide8,L12eight andone-word5
goldens, without recompilation. New summarizer requires21additional exact
cases, BUILD20804004 andFEATURES5359013f plus17sourcehashes.
preflight_dot4_large_candidate.ps1 is PREPARED ONLY, notstarted; it requires
both base32KR260/Nexys/FIFO and H1024extra21 summaries, then synthesis only.
No placement/routing/deployment queued. Do not edit RTL underactive tests.
At latestreview basewide8/L12eight/one-word5/FIFO64 allpassed; controlL12,
Nexys andH1024boundary checks stillrunning. Preservefrozen dot3DCP evidence.


## Attention cursor RTL; board unavailable

User explicitly has no current board access. Continue RTL/simulation/build
qualification; do not attempt SSH/deployment or claim hardware verification.
Changed attention_engine.sv only for PIPELINED_DOT1: registered head offset,
query group/row and key row cursors follow FSM index transitions. Replaces
head*head_words and token*row_words runtime address products; query output
uses the same cursor. ConstantLANES stride only; no extra read latency or
retagging. Default0 preserves legacy Nexys address equations. Numerical
limits/protocol/model format unchanged; this is no claim of larger deployed
capacity yet. Expected benefit is shortening the placed attention address
critical path, pending synthesis/placement evidence.

Assertion-enabled standalone simulation passes10profiles (tokens1..128,
heads1..64,dimensions16/48/64),includingH1024,partialgroups andconsecutive
runs withdifferent dimensions. Per-cycle address comparisons against original
equations,read/writecounts andzero-outputbounds pass. Evidence:
build/v2/eval/attention-cursor-simulation. Full numerical regression ACTIVE,
exec44237, frozen /var/tmp/sysone-batch-regression.gy9VS3, output
build/v2/rtl-dot4-check. Do not edit17RTL sources whileunder test.
No synthesis/placement queued. Completefull32KR260+Nexys/FIFO gatesfirst.
Preserve dot3 synthesis/placedcheckpoints and validated125MHz board app.
For further model capacity, prioritize attention query storage/BRAM and
activation hierarchy before widening array; level5 congestion remains the
constraint. High-DDR integration still requires PS mapping/error-contract
validation, and unavailableboard prevents hardware qualification.


## Dot3 placement completed ï¿½ October 12, 2026, 10:03 Chicago

Full placement passed; no jobs remain active. opt_design166.541s (2m47s),
place_design1597.622s (26m38s), wrapper elapsed40m51s including checkpoint
loading/writing and reports. No routing or board change. Placed setup estimates:
125MHz+2.731ns,150+1.398,200-0.269,250-1.269,300-1.936.
Compared dot2 placed300-2.025, improvement is only0.089ns, not300MHz closure.
Worst path has moved from LayerNorm gamma multiplication to attention
head_words_reg -> buffer0 read_address,13logic levels includingDSP multiply.
Data5.086ns:logic2.916ns,routingestimate2.170ns. Congestion remainslevel5,
mostlyattention/shared-dot/MAC, some94..95%LUT/100%DSP windows.
Next RTL target: pipeline or strength-reduce attention address multiplication
and align its read/valid tags, then full regression before another build.
Do not route300MHz with this failing placed estimate.150MHz has positive
placement margin but still requires routed setup/hold andhardware qualification.
Evidencebuild/v2/kr260-opt-dot3/placement; preserveallDCPs/reports.


## Dot3 synthesis reviewed; placement started (October 12, 2026)

User authorized resuming work after overnight pause. Synthesis passed all gates
in 1,405.437 seconds (23m25s launcher wall): encoder synth_design12m56s,
top synth_design1m04s; startup/IP generation/checkpoint loading/reporting
account for additional wall time. All17 synthesis snapshot hashes match the
full regression. LUT104609 (+3 vs dot2),FF113066 (+67),DSP611 (+4),59BRAM,
32URAM with registered outputs. Query fanout maximum16 and accumulator54;
shared dot pipeline stages retained. Estimated300MHz setup-1.815ns, hold
-0.087ns UNPLACED; worst request-arbitration -> streamer left CE (4.820ns,
1.633ns logic/3.187ns route estimate). No LayerNorm endpoints in30worst paths.
Affine inventory shows8DSP subcomponent sets each for scale/gamma, and216
FDREs in gamma (registered54bit outputs across4lanes); native DSP_* primitives
mean this report does not establish explicit AREG/BREG/MREG/PREG values.
Initial inspection opened topDCP withoutOOCIPs and failed; fixed byopen_run,
preserved incomplete evidence in inspection-incomplete-top-dcp. No resynthesis.

One full-placement diagnostic nowactive, unifiedexec69970, output
build/v2/kr260-opt-dot3/placement. place_dot3_candidate.ps1 rechecks frozen
hashes and synthesis gates, then opt_design/place_design withoutincremental
reuse. Saves opt/placedDCPs,125..300MHz timing sweep,fanout/congestion and
elapsedtimes. NO routing/bitstream/deployment queued. Do notedit17RTLfiles
or duplicate the active job; inspect placement/completion-status.json and
console.log on next continuation. Deployed125MHz app remains unchanged.
Overnight automation remains PAUSED; daytime work is authorized separately.


## Resumed synthesis ï¿½ October 12, 2026, 08:55 Chicago

User authorized the next synthesis after the morning report. Dot3 complete
frozen regression and 17 source hashes rechecked successfully. Started
preflight_dot3_candidate.ps1, unifiedexec session85638, in isolated
build/v2/kr260-opt-dot3 at 13:55:02 UTC. One heavy job only; source snapshot
is frozen. No placement/routing queued. Overnight automation remains PAUSED;
this is explicitly authorized daytime work, independent of its cutoff.
Review completion-status.json and preflight reports before further builds.
report_dot3_synthesis.tcl is prepared to inventory affine pipeline primitives
and DSP AREG/BREG/MREG/PREG and report 30 critical paths from the synthesized
checkpoint after completion. Never edit the RTL while synthesis is active.


## Morning handoff ï¿½ October 12, 2026, 08:49 America/Chicago

Overnight work is stopping near the requested 09:00 cutoff. No synthesis,
implementation or regression job remains active. No new build is queued.
The overnight automation is being paused; retain all frozen evidence.

- The deployed `sysone-v2-memory` remains the validated 125 MHz baseline:
  eight input lengths and 350/350 frozen L12 requests bit-exact, 32 UltraRAM
  blocks and 59 BRAM tiles. No board or boot-memory changes this morning.
- Dot2 shared reduction synthesis reduced LUT use from 114,832 to 104,606.
  Incremental placement failed after 29m03s of placement plus checkpoint/import
  overhead. Full placement from the same optimized checkpoint succeeded in
  18m42s, avoiding repeated synthesis. Reuse was counterproductive for this
  particular candidate; this does not establish a general incremental result.
- Full placement estimates setup margin +2.642 ns at 125 MHz, +1.309 at 150,
  -0.358 at 200, -1.358 at 250 and -2.025 at 300 MHz. No routing was launched.
  Congestion remains level 5. The worst 300 MHz path shifted to LayerNorm's
  gamma BRAM through its wide multiplier, with 4.006 ns of logic delay.
- Dot3 addresses that path with registered operands, two partial products,
  and a registered combine. Scale/gamma alignment was adjusted together.
  All 32 KR260 cases, two Nexys cases and 64 stalled-output chunks passed;
  all 17 current RTL hashes match the frozen tested sources. The independent
  multiplier test passed 1,025 cycles across four lanes and both operand widths.
  Dot3 has NOT been synthesized, placed, routed or deployed.
- The simulated 128-token L12 encoder count increased from 7,509,558 to
  7,547,855 clocks (+0.510%). These runs include randomized stalls, so this
  comparison is diagnostic rather than a measured hardware performance claim.
- Independent high-address AXI tests and relative-image/address-window contracts
  passed, as did integer decoder primitives and empirical timing-policy checks.
  High-DDR executor/PS integration and a complete FPGA decoder remain open.

Next work session: run `scripts/v2/kr260/preflight_dot3_candidate.ps1` once.
It rechecks frozen regression hashes, uses isolated `kr260-opt-dot3`, and runs
synthesis only. Review LUT/DSP fit, retained split-product stages, local control
fanout, all 32 registered UltraRAM outputs and timing before placement. Routing
requires useful placement evidence. Keep the validated app until routed setup,
hold and hardware numerical checks pass; 300 MHz is not achieved.

Evidence: `build/v2/rtl-dot3-check/summary.json`,
`build/v2/eval/split-product-simulation/summary.json`,
`build/v2/kr260-opt-dot2/cold-placement/`, and the preserved failed incremental
run. Dot3 launcher PowerShell parsing and Python checker compilation passed;
the updated resource checker still passes the existing dot2 synthesis evidence.
The Tcl dot3 selector is prepared but has not been exercised by Vivado.

Overnight08:14 continuation (review through08:26Chicago): full dot2 cold
placement completed08:11 in1122.151s (18m42s), without incremental placement
or repeated synthesis. Legal placement succeeds where incremental failed.
Placed estimates:125MHz +2.642ns,150 +1.309,200 -0.358,250 -1.358,
300 -2.025. These are UNROUTED estimates; no hold/board qualification.
Placed104240LUTs (89.00%),113372FF,59BRAM32URAM607DSP; congestionlevel5
around attention/shared dot/MAC. Worst300MHz path now LayerNorm gamma BRAM
through multiplier:5.212ns data,4.006ns logic,1.206ns estimated routing.
No routing queued; preserve cold-placement checkpoint and failed incremental.

New dot3 source adds split_product_pipeline: input register, parallel signed
upper/unsigned lower products, registered signed combine (three clocks).
PIPELINED_DOT enables PIPELINED_AFFINE in LayerNorm: scale and gamma each
add two clocks, with gamma/beta/output tags adjusted. Default0 retains old
schedule. Four-lane21x32/18x30 isolated test passes1025 checked cycles with
signed extremes/random operands; build/v2/eval/split-product-simulation has
logs and hashes. Full regression frozen in /var/tmp/sysone-batch-regression.mpJExQ,
unifiedexec50528, outputbuild/v2/rtl-dot3-check. At08:27 all eight wide cases pass exact (10512 words compared); remaining
L12/one-word/control/Nexys/H1024 checks still ACTIVE.
Do not edit the17 RTL sources under this regression. No dot3 synthesis or
routing is queued. Finish numerical gates first, then review synthesis before
placement. Do not launch new heavyjobs near09:00cutoff; leave active tests
intact and pause overnight automation with a morning report. Board remains
validated sysone-v2-memory125MHz;300MHz is not achieved.

Overnight07:44Chicago: incremental dot2 placement FAILED07:26, no placedDCP.
Place46-13/30-99: >5%movableinstancescouldnotplace/spiralsearch. Measuredplace
29m03s,launcherwait44m32s. Match/reuse did NOT imply legalplacement/speedup.
No manualpblock constraints known; remaining cells around streamer/embed/
requestcontrols; physicalfreedom fromincremental reference is suspected, not
proven. Preserved project,logs and43MBoptimizedDCP. Started independent
cold placement session51013 at07:46 from system_wrapper_opt.dcp, no synthesis
repeat/no incremental. New place_dot2_cold.ps1/.tcl recheck17hashes/gates,
rejectunexpectedpblocks, reportutil/congestion/fanout and125..300MHz sweep.
Outputbuild/v2/kr260-opt-dot2/cold-placement; statusplacing_cold then
cold_placement_ready/cold_failed. No routingqueued. Review atnextwake.
Builddiagnostics nowrecordstage_outcomes/implementation_failed ratherthan
misreading runtimeascompletion;4testsPASS.45decoder/memory/policy/profile/
diagnostic testsPASS before addition, then4diagnostic testsPASS afterfix.
Referencequantization nowrejectsnonintegerconfigurationbeforecache use.

Overnight07:14Chicago: dot2 placement stillactive, phase2.4 globalplace at
review; no finishedtimingreports/no routing. Incremental nowworks:83.34%cell
match,82.20%placementreuse,80.89%netmatch but0routingreuse (placed reference).
Reference import8m40s overhead; actual placement/total cost pending. Windows
memory sample~1.4GiBfree,67pageReads/s,829pagesIn/s; Vivado~7.7GBprivate,
~2.4GBworking,peak7.3GB. Currentpaging observed; do not attribute all build
time to it or close userapps/changeglobalWSLsettings. Active job69176.
Independent AXI selftest nowparameterizes physicalBASE_ADDRESS (default0),
adds full40bit burst-window assertions to detect symmetric truncation, and
translates corruption address. Highsimbase0x800000ff0 (4KiBedge),240000bytes,
300beatrequests: clean0errors,corruptexactly1error,50read_last/runPASS, bus
modelchecks4KiB/256beat/WLAST underrandomstalls. Session22784done. Saved high
log build/v2/eval/high-ddr-simulation/high-axi.log; defaultlow rerun compiling.
This validates generic40bitAXIadapter in simulation, NOT PS HP0highmapping,
relative translator integration or board highDDR. Currentboard unchanged.

Overnight06:44Chicago: dot2 preflight completed06:22.104606LUT89.31%,112999FF,
59BRAM32URAM607DSP: vsfirstdot LUT-10226,FF-9247,DSP-1. Shared stages retained
pairs4608/quads2560/octets1536; query1024max16,accum2306max54,allURAMoreg.
Estimated300MHz setup-2.084ns sourceLINEARload_tile ->streamerleftCE; path
through readrequestqualifiers and memory write_request_ready (global arbitration),
5.089ns total/3.398route estimate. Not dot reduction now. Placement launched
session69176 at06:45 after gate/hash review, closerbatch3 placed reference.
Stops before routing. Review placed reports, real reuse and congestion at next
wake. Do not edit frozen dot2 RTL or start another heavyjob.
Independent decoder_math.py now defines integer RMSNorm with rational epsilon,
floored inverseRMS and explicit gamma/output scales, plus lookup-activated
gated multiply (caller-calibrated signedINT16table). Scalar/floatoracle/extreme/
clipping tests pass.37 relevant decoder/memory/policy/profile testsPASS this
turn. No model calibration or FPGA decoder integration claimed.

Overnight06:14Chicago: dot2 complete32KR260+Nexys/FIFO regressions passed;
synthesis began06:03, encoderIPdone06:17, top synthesis/reporting still active.
No second heavy job. Prepared place_dot2_candidate.ps1/.tcl and
report_dot2_placement.tcl, NOT launched: uses closer batch3 placed DCP as
incremental reference (placement reuse only, actual matching unknown), stops
at place_design and records timing/fanout/congestion/reuse. Review real
resource/timing gates before invoking. Do not use older memory reference
with known46.72% mismatch or claim incremental routing reuse.
Independent decoder reference now supports grouped-query attention via
kv_heads (cache stores KV heads once; default fullheads unchanged), and
rope_int8 half-split fixed-point rotation with externalcalibratedtables.
GQA matches expandedKV and incrementaldecode; RoPE identity/quarterturn/
clamping tests pass.12 decoder/INT4/relative compiler testsPASS this turn.
No complete decoder/model calibration, RMSNorm/gatedFFN or hardware integration.

Overnight continuation05:44Chicago: first dot synthesis completed05:32.
114832LUT98.05%,122246FF,59BRAM32URAM608DSP. Dot pairs9216/quads5120/
octets2944 retained; query1024max16,accum2304max54,all32URAMoreg pass.
300MHz unplacedsetup-2.216ns now request_tile->DDRread_address,18logic levels
including combinational address multiplier. Do NOT route this nearlyfull version.
Prepared dot2: one shared WIDTH24 four-stage dot tree in encoder_layer feeding
both mutuallyexclusive engines (attention truncates to SCORE_WIDTH), and
LINEAR stream_cursor advanced by tile_beats*16 ONLY on accepted non-LUT request,
initialized from stream_reg at launch. Default PIPELINED_DOT0 legacy preserved.
Frozen full regression session89002, build/v2/rtl-dot2-check; wideeightPASS,
L12running. Qualifier89043 waitscomplete then isolated kr260-opt-dot2 synth300.
No implementation/routingqueued. New preflight scripts and Tcl dot2 flag
preserve old projects. Do not edit active17RTLfiles while testing.

Independent software/RTL memory progress: experimental common/model_address_window.sv
one-entry registered completion tuple maps40bitbase+32bitoffset, rejects
region/alignment/overflow errors and holds under stalls; consumers must reject
out_error before AXI. Standalone RTL high-DDR/limits/stall/reset test PASS.
NOT connected to current executor. relative_model.py compiles existing image
payload atzero into outerSYS3bundle, bounds image+alignedrequest scratch in
MemoryWindow, requires futurecapabilitybit6 (currentappsrejected), writes
separate physicaldescriptor/payload/manifest.16 relative/windowPython tests
PASS after fixing synthetic test region/position sizes. No high-DDR runtime
or platformmapping has been enabled. Update frontier/overnightdocs next.

2026-10-12 owner requested overnight work. Created ACTIVE thread heartbeat
kr260-overnight-optimization, every30minutes, morning cutoff09:00America/Chicago
today (14:00UTC). Prompt requires pausing near cutoff and writing morning
report, leaving running builds intact. Priorities: finish deep-dot regression
and synthesis, review gates/placement before routing; progress independent
memory/decoder/timing work while heavy jobs run. Do not duplicate jobs or
change tested/frozen RTL. Credentials are not stored in automation or files.
Keep validated sysone-v2-memory app unless replacement qualifies. Update
scripts/v2/kr260/overnight-2026-10-12.md with milestones and active jobs.

2026-10-12 board UltraRAM validation COMPLETE: sysone-v2-memory active at
124999999Hz,256MiB reservation. All eight lengths1/2/3/4/5/12/64/128 exact,
350/350 frozenL12 eval exact. Board report retrieved to
build/v2/eval/kr260-memory-hardware/eval.json with app/deploy/check logs and
previous helper backups. Owner password was only entered at interactive
SSH/sudo prompts, never saved. Session14943 completed successfully; download
68853 complete. Candidate observed mean17.19ms,max57.65ms (123tokens), not
a guarantee. Matching baseline comparison.json generated in same directory;
image/suite/IDs/hidden/prediction/stat hashes independently crosschecked.
This supersedes pending-board statements below. PERF_COUNTERS is off in this
qualified memory app; real event profiling needs a later qualified candidate.

2026-10-12 owner authorized all six frontier workstreams and supplied SSH
authentication in chat. Do not persist credentials. Authenticated board access
works. Confirmed old sysone-v2-pipe125MHz,256MiB reservation, no active runs.
Transferred hash-verified memory package and launched deploy_memory.sh through
SSH PTY session14943. UltraRAM app sysone-v2-memory now loaded, BUILD20803004,
live124999999Hz,256MiB; L12 33916928 bytes readback exact. Eight-length board
check still running CPU reference; subsequent350-case frozen eval queued by
script. Read-only ps confirmed reference Python100%CPU, not proven bus stall.
Report directory /home/ubuntu/kr260-memory-20261012-095936 (board UTC clock).
Retrieve reports after completion; do not interrupt or issue concurrent RUNs.

300MHz diagnostics DONE:125+1.062,150-0.271,200-1.938,250-2.938,300-3.605ns
placed estimate. Worst DSP-product -> attention dot reduction. Implemented
optional PIPELINED_DOT=1 (capabilitybit5) through engines/system/KRwrapper/TB:
four registered balanced reduction levels in mac_array.sv dot16_pipeline.
LINEAR MAC_EXTRA/passgap +3 and old accumulator/tag alignment; attention
scoreD+3, weighted/P.V staysP. Default0 preserved. Independent unit512cycles
signed extrema/modular19/24-bit/fourcyclelatency PASS (session21739 complete).
Full frozen regression session7197, /var/tmp/sysone-batch-regression.RTORjV,
build/v2/rtl-dot-check: wide8,L12eight,one-wordfive,controlL12,NexysPASS;
H1024 boundary compiling. Do not change RTL until completes. Qualifier session
11647 automatically summarizes17hashes and starts new synthesis-only
kr260-opt-dot at300MHz AFTER all cases pass. Checks dot pairs/quads/octets
register retention, previous fanout/URAM/resource gates. No routing queued.

Software foundations: memory_window.py proposed SYS3 40bitbase+32bitoffset
descriptor/burst planner (NOT wired into current v2/compiler/HP mapping);
decoder_reference.py integer causal attention and boundedKVcache (NOT full
Qwen decoder); int4_reference.py signed nibble packing/matvec (NOT GGUFQ4_K);
timing_policy.py model/clock/token admission and measured deadline/counter-wrap
checks (NOT hard guarantee). Evaluation client records performance_counters
whenKR260 supports them and optional eval --budget. summarize_profile.py
reports overlapping event ratios and request-average traffic rates, not DDR
standalone bandwidth.47 relevant Python tests PASS. Full work/gates documented
scripts/v2/kr260/frontier_work.md. Larger checkpoint training, high-DDR RTL,
complete decoder/CDC, guaranteedservice and second-laptop measurement remain.

2026-10-11 user requests300MHz. Prepared read-only placed checkpoint timing
diagnostic scripts diagnose_batch3_frequency.ps1/.tcl for125/150/200/250/300MHz,
30distinct setup endpoints each. Session37154 waits placement_ready recovery
session63374 then runs diagnosis serially. No new full build or board clock
change. Reports explicitly unrouted/not qualified. Need inspect actual paths
before latency/pipeline RTL changes; current+1.062ns at8ns suggests~6.94ns
worst effective requirement, substantially longer than300MHz3.33ns period.

2026-10-11 20:22 Chicago placement review: place_design succeeded18:04,
17m36s placement (30m21s launcher wait including opt/reference/checkpoint).
Wrapper wrongly rejected STATUS='Not started phys_opt_design'; fixed to require
placed DCP, no error/stale run. Do NOT repeat placement. Reports recovery running
session63374 via report_batch3_placement.tcl, saved placed DCP only, no routing.
Recovery sets completion-status placement_ready when reports finish. Current
failed marker was wrapper/reporting failure, not placer failure.
Incremental disabled:46.72% cell match below80% threshold, default flow used.
Placed resources105267LUT89.88%,104713FF44.70%,2741controlsets. Log estimate
WNS+1.062ns at125MHz; unroute estimate NOT timing closure. Reports pending.

2026-10-11 17:34 Chicago: user approved placement check. Launched
place_batch3_candidate.ps1 (session3534), frozen batch3 synthesis/hash gates
rechecked. Configures memory routed DCP incremental reference with hash record;
launch_runs impl_1 -to_step place_design -jobs1, existing four-thread hook.
Stops before routing; requests placed utilization/timing/fanout/congestion/reuse.
completion-status.json is placing, then placement_ready or failed. Actual
reuse and turnaround unknown until reports; do not duplicate/reset run.

2026-10-11 batch3 synthesis/preflight finished08:19 Chicago; reviewed17:27.
All gates pass:1024query FF controls max16loads,2307accumulator FF controls
max54loads. Prior35329/23554fanout accumulator nets absent from top40 report;
remaining topfanout divider asyncreset4841, embedbeat~1382, s_keystage5~1322.
Resources106601LUTs (91.02%),104974FFs (44.82%),59BRAM,32URAM,608DSP;
all32URAMoutputs registered. Comparedbatch2 LUT-2697,FF+49249: locality costs
registers and may still affect placement/congestion. Synthsetup+2.657ns,
hold-0.087ns remain unplaced estimates. No implementation launched, no
claimed timing/build-speed benefit until routed evidence. No Vivado active.

2026-10-11 08:02 Chicago status: accumulator banking regression completed
07:52, summary.json accepted all wide/L12/control/one-word/H1024/Nexys/FIFO
checks. Qualifier launched batch3 synthesis at07:52; encoder OOC synthesis
still running, supporting IP runs completed. Actual fanout/resource gates
not yet available. No placement/routing started. No second-laptop placement
benchmark result found in repository.

2026-10-11: user already owns the 12900HX/RTX4070 laptop. Prepared portable
build/v2/kr260-placement-benchmark.zip from the frozen memory candidate's
optimized, unplaced DCP. Archive contents and checkpoint hash verified.
Extract on second laptop to C:\fpga-bench and run benchmark_placement.ps1;
requires Vivado 2025.2 K26 support, defaults to four threads for comparison.
Baseline placement on 8845HS was 1310 seconds (21m50s). Saves machine.json
and placement-result.json; no routing, bitstream generation or board access.
This measures placement only, not a guaranteed full-build speedup. New scripts
benchmark_placement.ps1/.tcl and package_placement_benchmark.py are in
scripts/v2/kr260. Other laptop has not been benchmarked yet.

2026-10-11 continuing on user instruction: implemented optional
LOCAL_ACCUMULATOR_CONTROLS=1 through attention/layer/system/KR260/wrapper/TB.
Two dimensions per lane bank, local read/write/first-key/output selectors;
controls parallel existing pipeline tags, no intended extra arithmetic latency.
Default0 preserves prior behavior. Capabilities bit4 signals feature. New
regression running session34034, WSL /var/tmp/sysone-batch-regression.dcSWMS,
evidence build/v2/rtl-batch3-check. Adds H768/A48/HD16 independent references
for1,2,3,31,33 tokens to existing suites. Do not change tested RTL while running.
summarize_kr260_batch.py takes evidence directory then 1 for accumulator profile.
Prepared qualify_batch3_candidate.ps1 waits for complete simulations, then
preflight_batch3_candidate.ps1 does synthesis only in new kr260-opt-batch3.
Gates actual query/accumulator FF fanout (16 / 64 or256) and resource/URAM fit.
No full implementation queued. See accumulator_banking.md for alignment/rationale.
User also asks about12900HX/4070 laptop: CPU-only Vivado implementation maximum
8threads;12900HX has8P+8E cores versus8845HS8cores. Await RAM/laptop model before
estimating benefit; no benchmark supports a dramatic speedup claim. 4070 does
not accelerate this Vivado place/route flow. RAM/headroom/cooling matter.

2026-10-11 07:22 Chicago review: batch2 synthesis completed05:20, preflight
passed. All1024 intended query-control FF copies survived synthesis, maximum16
loads per copy. Resources109298LUTs,55725FFs,59BRAM,32URAM,608DSP; all32URAM
outputs registered. No implementation started or incremental preparation applied.
Broader fanout report reveals remaining attention control nets: s_word stage6
bits0/1 each35329 loads, s_v stage6 23554 loads (23552 clock enables). Source
review maps these to the P.V accumulator dynamic read/write control. This is
the next priority before another full implementation. Synthesis setup+2.713ns
is only an estimate; hold-0.087ns is also unplaced, not routed qualification.
Do not interpret preflight_ready as timing closure or congestion solved.

While synthesis runs: added scripts/v2/kr260/analyze_build.py and regression
tests; produces per-candidate build-diagnostics.json from existing logs without
Vivado launches. Records command wall/CPU costs, routing warnings and critical
path. Actual routing wide23m45s, memory75m04s, batch310m48s; all report maximum
congestion level6, so level alone is not a reliable turnaround gate. Static
attention audit identifies query read-select and score/value mode controls as
next cones to inspect; no extra RTL changes made during current synthesis.
Review scripts/v2/kr260/attention_routing_audit.md. Session20217 still preflight.

2026-10-11 04:58 Chicago: user explicitly prioritizes build turnaround/congestion.
Corrected batch simulations COMPLETE: all 27 AXI requests, FIFO stalls and Nexys
checks pass; build/v2/rtl-batch2-check/summary.json contains exact 17-file hashes.
Synthesis-only preflight now running session 20217, new kr260-opt-batch2 project.
Gates: resource fit, all UltraRAM output registers and actual local query enable
fanout <=16. If enable registers merged, fix replication before routing.
No placement/routing queued. Prepared prepare_batch2_incremental.ps1/Tcl to
configure the timing-passing memory routed DCP as incremental reference AFTER
gate review; not yet applied. Records checkpoint hash and launches no build.
Do not restart/recreate the synthesis project or run concurrent heavy jobs.
Measured last batch placement20m49s, routing5h10m48s; memory routing1h15m04s.
Batch router warned level6 congestion and spent nearly3h in its first major
rip-up iteration. Reducing physical wiring pressure takes priority over adding
datapath width or clock targets. Deployment package remains ready for owner.

2026-10-11 04:40 Chicago: owner requested UltraRAM deployment and more prebuild
optimization. Prepared/verified build/v2/kr260-app-memory.tar.gz (3,279,634 bytes,
SHA256 a6d4fff69318b17fd0b9f4ed9d457432510c06f1c6e6e581f415e96486e2ac92),
app sysone-v2-memory. Packaging verifies frozen RTL hashes, bit/XSA equality,
memory profile and both-clock timing-125mhz.rpt; overlay max-hidden now matches
H768. Runtime/deployment whitelist and URAM profile checks updated, 37 tests pass.
Board reachable but SSH BatchMode authentication denied; NOT deployed remotely.
Owner command: powershell -ExecutionPolicy Bypass -File scripts/v2/kr260/deploy_memory.ps1.
It transfers, deploys, saves prior helpers and runs L12 eight-length checks plus
350-chain evaluation. Details/rollback: scripts/v2/kr260/memory_candidate.md.
Corrected batch query writes now have static destinations and registered lane/
word enables (eight enable copies per lane/word, sixteen loads each requested).
Simulation running session 85062, independent build/v2/rtl-batch2-check evidence,
WSL snapshot /var/tmp/sysone-batch-regression.PWWn3F. Do not modify its source
while qualifying. Once finished run summarize_kr260_batch.py with that evidence
directory argument. No new Vivado build running. Prepared synthesis-only batch2
gate checks actual enable fanout and high-fanout/timing reports, in a NEW project
kr260-opt-batch2; does not queue routing. Review register merging before full
implementation. Audit/gates: scripts/v2/kr260/batch_prebuild_review.md.

Latest result (2026-10-11 04:30 Chicago): grouped batch completed at 04:18,
but FAILED 125 MHz timing (setup -4.477 ns, hold +0.006 ns). Clock sweep only
passes 80 MHz (+0.023 ns); no XSA/runtime profile exported or deployment package
prepared. Final resources: 93,725 LUTs, 53,203 FFs, 59 BRAM, 32 URAM, 608 DSPs.
Worst path is attention s_word_reg[5][1] to query_reg clock enable in local
query distribution, 12.841 ns data delay (12.263 ns routing, 95.499%). Local
query data staging left a global word-index/control decode bottleneck. Next:
pipeline/distribute query write control with its local data, or use a separately
qualified profile disabling LOCAL_QUERY_REGISTERS while retaining streaming and
counters. Preserve the independent memory candidate that passes 125 MHz.
Actual elapsed batch implementation plus clock sweep was ~5 h 42 min; prior
1â€“2 hour estimate was too optimistic. No active implementation remains.

Latest (2026-10-10 22:36 Chicago): memory candidate completed routing, bitstream
and XSA; clock sweep passes 125 MHz (setup +0.001 ns, hold +0.010 ns), fails
150 MHz. Final resources: 95,139 LUTs, 52,465 FFs, 59 BRAM, 32 URAM, 606 DSPs.
Grouped batch synthesis preflight passed: 108,151 LUTs (92.34%), 54,366 FFs,
59 BRAM, 32 URAM, 608 DSPs; all 32 UltraRAM primitives have output registers.
Corrected checker to accept Vivado's CLB LUTs* footnote label; the prior failed
status was a report-parser error. Full grouped implementation now running via
route_batch_candidate.ps1 (exec session 44828), reusing completed synthesis and
verified frozen 17-file RTL snapshot. It reports resources, timing and a clock
sweep; exports the XSA only if 125 MHz meets setup/hold. No batch package or board
validation yet. Do not recreate this project or duplicate implementation.

Next grouped batch is prepared and simulation-qualified (2026-10-10 14:08
Chicago). Adds optional `STREAM_RESULTS=1` (eight-word credit-reserved output
FIFO), `LOCAL_QUERY_REGISTERS=1` (four-lane groups plus one query drain clock),
and `PERF_COUNTERS=1` (ten RUN-reset/frozen diagnostics, capabilities at 0x1C).
LINEAR row strides are now sixteen bits, fixing the 256-word/4096-element
FFN boundary. Runtime API: `Kr260Link.performance_counters()`; None on older
firmware, rejects busy reads. Registers/events documented in
`scripts/v2/kr260/batch_optimization.md`.
`build/v2/rtl-batch-check/summary.json` verifies 27 full AXI requests: eight
H768 synthetic, eight L12, eight matched L12 control, three H1024/F4096
boundary cases. All outputs bit-exact and AXI read/write/burst counters checked
against independent monitors. FIFO unit test passes 64 chunks with prolonged
and random backpressure at latency 3/4. Nexys default passes 39,216 words.
Host/memory guard tests pass 50 cases. Tested source hashes cover 17 RTL files.
Matched 128-token L12 simulated request overhead (request minus encoder)
falls 19,625 -> 4,561 clocks (-76.759%); encoder cycles change +0.0068%.
This is simulation, not a board speedup or guaranteed bound. H1024 is only a
boundary simulation; the candidate remains H768 and no H1024 fit is established.
`preflight_batch_candidate.ps1` is queued (exec session 98774): waits for the
independent memory build to finish, rechecks evidence and source hashes,
then runs synthesis only in `build/v2/kr260-opt-batch`. Check its status,
`preflight-utilization.rpt`, `preflight-memory.json`, `preflight-summary.json`.
Review fit and actual UltraRAM output-register inference before full routing.
No batch package, routed timing or board validation yet. Root RTL differs from
the frozen memory candidate; preserve both source snapshots and S: mapping.
Memory candidate's encoder synthesis now reports 107,212 LUTs, 59 BRAM tiles,
32 URAM blocks, 606 DSPs versus prior wide encoder synthesis 100,202 LUTs,
123 BRAM tiles, 24 URAM blocks. Its generated simulation netlist includes
OREG_A/B TRUE. These are synthesis results; final routed utilization is pending.
Memory-hierarchy candidate is now implemented and building (2026-10-10 13:52
Chicago). Optional `PIPELINED_URAM=1` uses whole activation arrays in UltraRAM
with an extra output register; engine and host read latency becomes four clocks.
All six engine consumers and request output reads are aligned. Port data
registers use max_fanout=8 to address the old wide design's 162-load attention
query path. Defaults retain the Nexys split-memory/three-clock implementation.
Evidence: `build/v2/rtl-memory-check/summary.json`, 16 KR260 cases/15,768 words
(H768 synthetic and existing L12), 60,000 masked-write/read memory checks and
Nexys per-instruction 39,216-word regression pass. Maximum simulated encoder
cycle increase is 0.228%; random AXI stalls affect comparative cycle counts.
Isolated full Vivado build: `build/v2/kr260-opt-memory`, launched via
`scripts/v2/kr260/build_memory_candidate.ps1` (exec session 52151). It automatically
writes routed resource/clock reports and completion status, but does NOT package
or deploy. Check actual URAM output-register inference and BRAM/URAM counts,
then setup/hold at 125 MHz before accepting. Preserve the completed wide build.
DDR4 burst scheduling is unchanged: already eight outstanding bursts and
double-buffered LINEAR loading. Actual AXI service/compute-wait profiling is
still needed before changing DDR4 prefetch or claiming a timing bound.
Owner's next-step priority: optimize UltraRAM, BRAM and DDR4 together after
qualifying the current wide candidate. Its placement report uses 24/64 URAM
blocks and 123/144 BRAM tiles. Audit activation-buffer packing and placement,
UltraRAM output pipelining (Vivado reports missing optional output registers),
and DDR4 burst reuse/prefetch with measured stalls. Align all latency-dependent
control and verify bit-exact results before claiming a performance improvement.
Preserve the current candidate's frozen sources while its build runs.
New 768-wide candidate (owner authorized proceeding): synthetic H768/A12/F3072
matches independent integer references and full AXI RTL at eight lengths, 10,512
words. Existing L12 also passes eight lengths, 5,256 words, on the wide hardware
configuration, with unchanged simulated cycles. Evidence/source hashes in
`build/v2/rtl-wide-check/summary.json`. Candidate BUILD20803004, separate app
`sysone-v2-wide`, registered MAC/BRAM options, H768/T128/HD64/TO32/drain4.
Full build completed in `build/v2/kr260-opt-wide`: package ready at 100 MHz,
`build/v2/kr260-app-wide.tar.gz`. Routed setup/hold slack: 100 MHz +1.839/+0.006 ns;
110 MHz +0.930/+0.006 ns also passes the clock sweep, but the exported profile
is 100 MHz. 125 MHz fails setup by 0.161 ns. Final utilization: 88,065 LUTs,
49,691 FFs, 606 DSPs, 123 BRAM tiles, 24 URAM blocks. Both runtime clocks
qualified by the export helper. No wider trained checkpoint or board validation
yet. Check `completion-status.json` and `clock-candidates.json`. Runtime/deployment/link tests
pass 32 cases including wide-profile checks. Preserve all working H384 artifacts.
Timing clarification: one second is not fixed. The goal is a declared predictable
timing budget (possibly longer) with stated model/input/operating conditions;
measured p95/max are not hard guarantees. Memory budget should be flexible.
Client now discovers the boot reservation, runtime/deploy permit larger verified
regions, and configurable DTB/FIT tools preserve the chosen allocation across
kernel updates. `scripts/v2/kr260/memory_budget.md` contains the full transfer,
configure/verify/reboot/reload workflow for a proposed 256 MiB at 0x60000000.
45 memory/runtime/deploy/link tests pass. The owner has now verified the 256 MiB
allocation after reboot: iomem 60000000-6fffffff reserved, auto-discovery 256 MiB,
pipeline app at 124,999,999 Hz, L12 image identical on readback and all eight
token lengths bit-exact. Evidence: `build/v2/eval/kr260-memory-256/board.log`
and `summary.json`. This verifies the reservation and existing model, not a full
256 MiB memory sweep or a larger model. Hidden width remains 384; high-DDR ISA
support is still outstanding.
The user requested better pipelining and higher compute frequency on KR260
and much larger models that use the board's DDR4 capacity. Capacity
audit and implementation order: `rtl/v2/KR260_SCALING.md`. Key blockers: 64 MiB
reservation, hidden width 384, 32-bit absolute ISA/descriptor addresses despite
40-bit AXI and a high-DDR region at 0x800000000, and eight-bit LINEAR row counters
that wrap for a 4096-wide FFN. Current RTL is an INT8 encoder, not a KV-cached
causal decoder. No larger reservation or high-DDR implementation is deployed.
The verified 125 MHz 32x16 array's ideal ceiling is 64G scalar products/s;
large-model throughput needs measured stalls/bandwidth, not memory size alone.
KR260 remains the new edge platform. Nexys is a compatibility regression target, not
the driver for further frequency work. Candidate 1 adds optional registered
MAC operands (`MAC_INPUT_REGISTERS=1`) and aligns LINEAR/ATTENTION control tags,
accumulator values and flush/hazard spacing. Default zero preserves the established
profiles. Multiplier exhaustive checks, KR260 BERT-mini and MiniLM-L12 (eight
lengths each), and Nexys per-instruction checks all pass. Reports and RTL hashes:
`build/v2/rtl-pipeline-check/summary.json`; design notes: `rtl/v2/OPTIMIZATION.md`.

**Candidate 1 now verified on KR260 hardware (2026-10-10).** Returned batch in
`build/v2/eval/kr260-pipeline-125/`: both baseline and pipeline complete 350/350
bit-exact, all eight token-length checks pass, matching suite/image/token/hidden
hashes and identical predictions/integer logits/score counts. Candidate manifest
matches the local packaged build. Baseline live clock 71,428,571 Hz; pipeline
124,999,999 Hz. Encoder mean 29.9905 -> 17.1598 ms (1.7477x speedup, 42.7825%
reduction); p95 62.6210 -> 35.8147 ms; max 100.6720 -> 57.5716 ms. Mean cycles
increase 0.1305%, so improvement is principally clock frequency. Host round trip
mean 30.5011 -> 17.6470 ms, with heads measured separately. Audit/comparison:
`build/v2/eval/kr260-pipeline-125/comparison.json`. The successful batch leaves
`sysone-v2-pipe` loaded. BRAM variant completed routed/runtime checks at 125 MHz
(setup +0.016 ns, hold +0.010 ns), with 89,085 LUTs versus 93,586 for pipeline.
Updated `kr260-app-bram.tar.gz` includes the flexible-memory runtime/deployer;
BRAM board validation remains pending. Flexible memory transfer bundle
`build/v2/kr260-memory-budget.tar.gz` is built and its contents/hash verified.
The isolated KR260 125 MHz build is `build/v2/kr260-opt`; Nexys 100 MHz OOC candidate
is `build/v2/encoder_ooc/both-pipe` (completed, 100 MHz setup -1.043 ns, hold
+0.041 ns; fails 100 MHz). KR260 now passes 125 MHz setup/hold and has the
hardware validation above. Windows path limits required
`subst S: <repo>` and the short-path `resume_optimized_build.tcl` retry. The retry
regenerated candidate IP. Future optimized builds snapshot RTL inputs. Baseline
builds and board applications are retained.

Latest KR260 candidate status: `impl_1` completed routing; final reports/export
are still running. The routed timing report passes +0.011 ns setup and +0.010 ns
hold at 125 MHz, with zero unconstrained internal endpoints. Both-clock runtime
qualification and board validation remain pending. Worst path: port_data_reg[0][87]
to replicated MAC operand FF; 7.830 ns data, 97.5% routing, source fanout 160.
The short-path retry is still running (console `build/v2/kr260-opt/resume-console.log`,
implementation `sysone_v2_kr260.runs/impl_1/runme.log`). A running
`finish_pipeline_build.ps1` waits for it, then runs `report_clock_candidates.tcl`
through S:, checks setup/hold, and exports only a passing profile with
`validate_runtime_clock.tcl` (both PL0 and PL1). Watch `completion-status.json`.
The first build's RTL and passing regression were frozen in `rtl-snapshot/`
and `regression.json` before subsequent edits; packaging checks those inputs. No new
clock is currently approved. `package_app.py --optimized` includes a single
`validate_pipeline.sh` board script: baseline and candidate MiniLM-L12 load,
eight token lengths, frozen 350-case evaluation, separate reports/live clocks.
It has passed Bash syntax checking but has not run on the board.

Additional KR260 resource experiment: the 32-lane softmax table prototype
maps to 768 LUTs + 16 BRAM tiles instead of 3,332 LUTs. Matching one-cycle
outputs passed 38,400 comparisons. Source/reports/logs are under
`build/v2/ram-inference/`. It is now integrated as optional `EXP_TABLE_IN_BRAM=1`
through attention, layer, system and KR260 wrapper. BERT-mini and MiniLM-L12
both pass eight lengths, with identical cycle counts against the pipelined LUT
variant. Nexys default passes 39,216 words. New staged hashes and checks are in
`build/v2/rtl-bram-check/summary.json`. Full area/timing measurement uses isolated
`kr260-opt-bram` (`build optimized 125 bram`), not the first candidate directory.
`finish_pipeline_build.ps1 -Bram` supports its clock/export/package checks;
separate app `sysone-v2-bram` is guarded in runtime/deploy preflight. All 25
KR260 runtime/deployment/link tests pass. This is a KR260 option because Nexys
lacks the BRAM capacity. BRAM hardware validation remains pending.
`build_bram_candidate.ps1` is queued behind the first candidate's completion
helper. It starts the isolated BRAM implementation only after a ready status,
copies its regression evidence, and then runs the BRAM completion checks.

**Both boards have completed the same 300-request bert-mini evaluation, with
identical outputs and scores. MiniLM also passed the same 350-request suite on both boards (section 5).**

Generation KR260 CPU reports reviewed (2026-10-10): both Q4/Q8 completed8/8
requests, all expected prompts/repeats, model fingerprints verified, no cached
prompt tokens, no thinking/truncation. Q4 medianfirstword5.138s, decode5.285tok/s,
peakRSS708.8MiB; Q8 median5.046s, decode5.781tok/s, peakRSS940.5MiB. 0/16
meet one-second first-word target. Prompt prefill dominates. Both negation
answers contradict themselves; technical context answers omit the supplied
same-leg short-circuit explanation. No reliable technical-answer quality claim.
Reports build/v2/eval/kr260-generation{,-q8}.json; summary and review alongside.
Problem29 records unmet acceptance criteria. No FPGA decoder acceleration or
laptop-generation integration performed. Backend/acceleration work remains open.

Earlier generation baseline preparation (2026-10-10): separate llama.cpp CPU runtime,
tagb11540, official Qwen3-0.6B-GGUF pinned revision23749fefcc72300e3a2ad315e1317431b06b590a.
Official Q8 SHA9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031
verified. Locally requantized Q4_K_M and original Q8 both included in
build/v2/kr260-generation.tar.gz (~1.03GB), alongside pinned source, license,
manifest, setup and stdlib streaming benchmark. scripts/v2/kr260/generation.md
has batch transfer/build/run/report commands. Laptop smoke passed8 Q4 and4 Q8
requests, non-thinking mode, no prompt caching; first words .075-.140s(Q4),
.125-.259s(Q8), startup separately measured. These are laptop results, not KR260.
Q4 negation was wrong; Q8 leading Yes contradicted keep-on explanation. This is
a speed/quality baseline, not a validated assistant. KR260 ARM CPU execution and
all on-board latency/memory/quality measurements remain pending. No FPGA decoder
acceleration, no routing integration, no retrieved-document grounding yet.

L12 routing batch reviewed (2026-10-10): build/v2/eval/kr260-l12-routing.json
complete16/16 expected probes, all success with DDR/live-clock preflight.
Review: build/v2/eval/kr260-l12-routing-review.md. Custom electronics now accepted,
3/4 intended custom labels versus L6 2/4; inventory still generic list routing.
Hotel duration captured, but SearchHotel remains. Restaurant party size absent,
orphan I-time remains. Negation still selects lightoff p.970; ambiguous cancel
still lacks clarification. No generated answers tested. Separate generation
runtime and targeted semantic regression work remain outstanding.

L12 KR260 hardware verified (2026-10-10): owner report
build/v2/eval/kr260-minilm-l12.json is complete,350/350 bit-exact. Independently
checked suite digest, image fingerprint, distinct cases, token hashes and all
hidden hashes against frozen goldens. Live clock71,428,571Hz. Encoder mean
29.9905ms,p95 62.6209ms,max100.6720ms at123tokens. Same350 requests/token IDs
as L6, whose mean was15.1387ms. L12 accuracy ATIS.980,CLINC.920,HWU.920,
MSRP.800,multiCLINC.94245,SGD.93333,SICK.740. Slot F1 ATIS.94444,HWU.77108,
SGD.48889. Compared with L6, SICK falls.820 to.740 while several other scores
improve; these are frozen subsets, not full-corpus or automatic-routing accuracy.
Audit/metrics: build/v2/eval/kr260-minilm-l12-summary.json. L12 Nexys testing
and routing/negation regression testing remain unperformed.

Earlier L12 package status (2026-10-10): all six preparation stages completed.
Transfer bundle build/v2/kr260-minilm-l12-v1.tar.gz exists, 33,812,416 bytes.
Both image variants matched all350 frozen cases; suite SHA256
f25425362e4487461f3b73ea07be25cddae354ba5269b026755db3b8ad0895be.
Preparation exited without logged errors. Owner has transfer/load/check/eval
commands; physical L12 FPGA execution and report retrieval remain pending.

Earlier L12 status (2026-10-10, about00:46 America/Chicago): both CPU training
epochs, float/INT8 test evaluation, few-shot evaluation and export completed.
results/v2/chain/minilm-l12-v1.json has two history entries and test_int8.
Preparation worker is active at stage4/6 (OOS/HWU calibration, final HWU test
pass1000/2538 at00:43); baseline/KR260 images compiled, KR26033,916,928 bytes.
Stage3 checked350 chains against IntEncoder with zero hidden/head mismatches.
Matched-suite generation and transfer packaging are still pending, as is all
L12 FPGA execution. No hardware validation claim yet. Active threshold child
PID24316; preparation Python3652, wrapper17392; waiter5184.
This status supersedes the earlier resumed-training notes below.

Current L12 state (2026-10-09): owner requested pause for a quick Radeon 780M
benchmark, then explicitly requested CPU continuation. Training Python PID23256
was resumed via NtResumeProcess; CPU activity verified. UV parent PID22148 remains.
Do not launch duplicate training. Preparation waiter PID15144 was stopped before
suspending training and replaced by live waiter PID5184 after resumption.
Durable external checkpoint was
loaded and verified: epoch1/batch_done200, one completed development-validation
epoch. Checkpoint: C:/Users/user/AppData/Local/SysoneCheckpoints/minilm-l12-v1_checkpoint.pt.
Live-run stdout: same directory/minilm-l12-v1-resume2.stdout.log. Pause metadata:
build/v2/eval/minilm-l12-training-paused.json (state running_cpu).
Preparation metadata: build/v2/eval/minilm-l12-preparation-process.json;
stdout/stderr are external minilm-l12-v1-preparation-resumed.*.log files.
If the process is gone, inspect logs and resume from the external checkpoint
with --resume. Do not resume or restart an already running process.
Isolated DirectML benchmark environment: C:/Users/user/AppData/Local/SysoneGpuBench/venv;
training environment/dependencies are unchanged. Benchmark script:
scripts/v2/benchmark_directml.py; results under build/v2/eval/minilm-l12-*-benchmark*.json.
Review: build/v2/eval/minilm-l12-gpu-benchmark.md. DirectML passes both encoder
training and multi-head compatibility but gives no clear overall speed advantage.
Owner chose CPU continuation; second epoch is running and KR260 preparation queued.

Matched hardware evaluation completed and compared (2026-10-09): both boards
passed 300/300 integer-reference checks. Case-by-case token IDs, hidden-state
hashes, task predictions/logit hashes and accuracy counts match. KR260 runtime
preflight and DDR verification passed after recovery, app reload and model reload.
Mean encoder time: Nexys 10.072 ms at 75 MHz, KR260 5.755 ms at 71,428,571 Hz,
about 1.75x faster overall. KR260 maximum was 18.36 ms (121 tokens); mean input
length was 33 tokens. These are board counter timings, with CPU heads and host
round trips recorded separately. The 16x12 Nexys and 16x32 KR260 variants use the
same trained model and frozen seed-0 subset, not the same hardware configuration.
Reports: build/v2/eval/nexys.json, kr260.json, comparison.json and comparison.md.
Suite SHA256: 4f557315887fdc140bc7028ee329038c8ecbf6c207f97a3d5ca57a42fca7c75b.
Accuracy covers supervised task heads on 50 requests per dataset; automatic
routing and full-corpus accuracy are not scored here.

The earlier silent run and RCU warnings did not recur during the guarded 300-request
evaluation. Recovery is complete; the original kernel-stall cause remains unknown.
See problem 26 in rtl/v2/README.md. All 46 relevant tests passed.

MiniLM KR260 automatic-routing smoke tests passed (owner output, 2026-10-09):

| Request | Route / result | Encoder ms | Request ms | Host round trip ms | CPU heads ms |
|---|---|---:|---:|---:|---:|
| show me flights from boston to denver tomorrow morning | ATIS: book_flight 0.894, atis_flight 0.999; both cities/date/time slots correct | 10.80 | 10.82 | 12 | 34.3 |
| how should I build a h-bridge circuit? | out of scope; CLINC oos 0.355, no specialist head | 10.90 | 10.92 | 12 | 26.2 |
| turn off the lights in the kitchen | HWU: smart_home 0.835, iot_hue_lightoff 0.988; kitchen B-house_place | 10.59 | 10.60 | 11 | 32.1 |
| book me a table for two at an italian restaurant tomorrow evening | SGD: restaurant_reservation 0.983, ReserveRestaurant 0.957; cuisine/date tagged, party size absent, orphan I-time | 11.11 | 11.13 | 12 | 35.9 |

Live clock 71,428,571 Hz; encoder/request times use FPGA counters. CPU heads
and host round trips are separate measurements. These four requests validate
specific routing branches, not corpus-level routing accuracy. SGD routing passed on the restaurant smoke test, but its slots are imperfect:
"two" is untagged and "evening" is I-time without a preceding B-time. Model
quality must be assessed separately from the bit-exact hardware checks.
Custom-intent/document paths have not yet been checked with MiniLM on the KR260.

Checkpoint recovery (2026-10-09): original L12 run stopped while replacing
logs/minilm-l12-v1_checkpoint.tmp with .pt (WinError5), before first-epoch
validation. Cause of the file lock is not confirmed. The committed checkpoint
contains epoch0/batch2800; the temporary file loads correctly and contains
batch3000. Copied the newer candidate to
C:/Users/user/AppData/Local/SysoneCheckpoints/minilm-l12-v1_checkpoint.pt,
SHA256 0dd8fa8ecbdefb187f70e63441e4899dbe9d9086f86d27cc3c51889276cc364d,
with both originals preserved. Added --checkpoint-dir and bounded replacement
retries, preserving old/new recovery files if replacement stays locked.
Three focused checkpoint tests pass. Resumed with unchanged hyperparameters
and --checkpoint-dir outside OneDrive. New log:
build/v2/eval/minilm-l12-v1-resume.log; process session50200. Check this log and
the external checkpoint before launching again. Training/export still incomplete.
Recovery audit: build/v2/eval/minilm-l12-checkpoint-recovery.json. Problem28.

MiniLM-L12 training started (2026-10-09): minilm-l12-v1, pretrained L12
encoder, fresh task heads, two epochs, HWU, embedding384, L12 teacher,
distillation10, slot weight4, LR4e-5/head LR1e-3, --resume. Laptop CPU;
log build/v2/eval/minilm-l12-v1-training.log, checkpoint
logs/minilm-l12-v1_checkpoint.pt. Training process session16050 started;
check process/log before launching again. Training and INT8 export/deployment
are incomplete. Owner's 16-case batch is recorded as regression evidence,
not new training data. Read build/v2/eval/kr260-routing-batch-review.md.

Current next work (2026-10-09): owner wants faster batch experimentation and
both stronger intent/slot/custom-intent models and generated answers on KR260.
Latency target is first generated words within one second. Prepared 16-case
routing/custom-intent batch: build/v2/kr260-smoke-batch.tar.gz. Owner ran all 16; review saved to build/v2/eval/kr260-routing-batch-review.md.
Negation failed (lightoff p=0.989), custom labels matched 2/4, slots have omissions. Larger encoder candidate all-MiniLM-L12-v2 added to fetch_models.py;
download completed and CPU forward verified: 33,360,000 parameters, 12 layers,
hidden 384, head dimension 32. Preflight: build/v2/eval/minilm-l12-preflight.json.
Task fine-tuning, calibration and FPGA image verification remain to be done. Generation candidate Qwen3-0.6B requires a
separate causal runtime; current FPGA image format cannot generate answers.
Measure ARM CPU generation first before claiming the first-token target.
See scripts/v2/kr260/larger-models.md. No paid resources/new hardware authorized.

Matched MiniLM hardware comparison completed (2026-10-09): programmed the
existing 75 MHz Nexys encoder through JTAG; 23,035,904-byte MiniLM image
read back exactly in 34 s (host path). Both boards passed 350/350 frozen
integer-reference checks. Per-case token IDs, hidden-state hashes, task-head
predictions/logit hashes and score counts match exactly. Suite SHA256:
f89ce2428293503f0458e98e5f5aebe29e5be08f7f9b3c36012c7d2e5428109e.
Nexys encoder mean 26.441 ms at 75 MHz, maximum 112.36 ms;
KR260 mean 15.139 ms at 71,428,571 Hz, maximum 50.94 ms.
Overall encoder speedup 1.747x. Mean input 28.39 tokens, maximum 123.
Nexys tile 16x12, KR260 16x32; same trained checkpoint and calibration.
Host transport/CPU heads remain separate; this is a seeded 50-request-per-dataset
supervised subset, not full-corpus or automatic-router accuracy.
Reports: build/v2/eval/nexys-minilm.json, kr260-minilm.json and minilm-comparison.*.
Both boards currently have their respective MiniLM image loaded in volatile DDR.
To return to bert-mini, use that board variant's load command; files/reports remain.

MiniLM-L6-v3b KR260 hardware evaluation verified (2026-10-09).

All 350 frozen requests match cached integer hidden states and CPU task-head predictions/logit hashes. Live clock: 71,428,571 Hz.

Encoder mean 15.139 ms; maximum 50.942 ms. Mean input 28.39 tokens; maximum input 123. Timings use FPGA counters.

| Dataset | Accuracy | Scored intents/pairs | Slot F1 | Encoder mean ms |
|---|---:|---:|---:|---:|
| atis | 0.960 | 50 | 0.920 | 10.953 |
| clinc | 0.900 | 50 | â€” | 10.783 |
| hwu | 0.920 | 50 | 0.659 | 10.718 |
| msrp | 0.640 | 50 | â€” | 21.048 |
| multi_clinc | 0.892 | 139 | â€” | 13.650 |
| sgd | 0.933 | 45 | 0.449 | 26.236 |
| sick | 0.820 | 50 | â€” | 12.583 |

50 requests per dataset, seed 0; supervised task heads. Automatic routing and full-corpus accuracy are not scored.
The 350-case MiniLM suite includes HWU and differs from the 300-case bert-mini suite; their mean times are not a matched model comparison.
Nexys MiniLM hardware evaluation subsequently passed on the same suite; see matched comparison above.

Suite SHA256: `f89ce2428293503f0458e98e5f5aebe29e5be08f7f9b3c36012c7d2e5428109e`.

MiniLM load/readback and 1/12/64/128-token hardware checks passed; encoder
times 9.75 / 10.90 / 26.07 / 52.99 ms at the live clock. The HWU scoring
fix (problem 27) passed its hardware rerun. Imported report:
`build/v2/eval/kr260-minilm.json`; verified summary: `kr260-minilm-summary.*`.

KR260 encoder verification passed (owner output, 2026-10-09):

| Tokens | Integer reference | Encoder clocks | Encoder ms | Request ms | Host round trip ms |
|---|---|---|---|---|---|
| 1 | bit-exact | 212,682 | 2.98 | 2.98 | 4 |
| 12 | bit-exact | 258,357 | 3.62 | 3.63 | 4 |
| 64 | bit-exact | 681,140 | 9.54 | 9.61 | 10 |
| 128 | bit-exact | 1,386,238 | 19.41 | 19.56 | 20 |

Clock is 71,428,571 Hz; image bert-mini-slots4-kr260, 16x32 tiles. These runs
verify PL DDR traffic and exact hidden states for the seeded test chains. They
are not a corpus accuracy evaluation. KR260 host processing is on ARM via local
AXI, despite the old client's generic "includes Ethernet" text; corrected locally.

First real-text KR260 request passed (owner output, 2026-10-09): "show me flights
from boston to denver tomorrow morning", 11 tokens. Auto router selected ATIS;
CLINC book_flight p=0.864, ATIS atis_flight p=0.998. Slots: Boston fromloc.city_name,
Denver toloc.city_name, tomorrow depart_date.today_relative, morning
depart_time.period_of_day. Encoder 3.56 ms, request 3.57 ms (board counters), host
round trip 4 ms, CPU heads 16.8 ms. This single request validates the routed
intent/slot path; corpus accuracy and other routing branches remain to be tested.

Out-of-scope KR260 smoke test passed (owner output, 2026-10-09): "how should I
build a h-bridge circuit?", 12 tokens, route out of scope because CLINC is below
its threshold; no specialist head used. CLINC oos p=0.286. Encoder 3.62 ms,
request 3.63 ms (board counters), host round trip 5 ms, CPU heads 5.1 ms.
Initial KR260 bring-up is complete: app/register/clock checks, exact DDR image
readback, bit-exact hidden states at four lengths, ATIS intent/slots, and OOS
rejection all pass. Next substantive experiment: matched corpus evaluation on
both boards with identical model, examples and seeds. Do not infer corpus
accuracy from these smoke tests.

Matched evaluation prepared (2026-10-09): frozen 300-request test suite, 50 each
from ATIS/CLINC/MSRP/multi_clinc/SGD/SICK, seed 0. Both image variants produce
identical integer hidden states and task heads for all cases. Suite SHA256:
4f557315887fdc140bc7028ee329038c8ecbf6c207f97a3d5ca57a42fca7c75b.
`prepare_eval_suite.py`, `eval --suite --verify --report`, `package_eval.py` and
`compare_eval.py` provide portable cached goldens and per-request comparison.
38 relevant tests pass. Actual Nexys bitstream was reprogrammed, image readback
passed (11,309,056 bytes, 16 s host path), and hardware evaluation passed 300/300
bit-exact. Mean encoder 10.07 ms at 75 MHz, max 37.22 ms; 33 tokens mean, 121 max.
Nexys report: build/v2/eval/nexys.json. CPU peer report: local-kr260.json, not a
KR260 hardware report. KR260 bundle build/v2/kr260-eval.tar.gz is 2,641,209 bytes;
transfer/run instructions are in scripts/v2/kr260/README.md. KR260 hardware
evaluation and final comparison subsequently passed; see the completed result above.

Nexys subset scores: ATIS accuracy 0.980 / slot F1 0.963, CLINC 0.920, MSRP 0.620,
multi_clinc 0.875 (160 segments), SGD 0.909 (44 scored intents) / slot F1 0.622,
SICK 0.880. This is a seeded 50-request-per-dataset subset with supervised task
heads; it is not full-corpus or automatic-router accuracy.

Board deployment passed (owner output, 2026-10-09): `sysone-v2` loaded in slot 0;
ID 0x53595332, BUILD 0x20801804, clock 71,428,571 Hz, reserved_bytes 67,108,864,
image_written false. The helper also verified operating FPGA manager, bound
clock/AFI drivers and enabled/prepared PL0. Next: load/read back the bert-mini
image, then check hidden states at 1/12/64/128 tokens. Use --clock-mhz 71.428571
for timing conversion; 75 MHz is the request, not the observed operating rate.

Image load passed (owner output, 2026-10-09): bert-mini-slots4-kr260,
11,256,832 bytes at 0x60000000, identical CPU readback in 5 seconds (host path).
This confirms the reserved DDR mapping and image transfer; PL DDR accesses and
encoder correctness were pending at that point; the checks above subsequently passed.

Latest deployment inspection (2026-10-08): installed k26-starter-kits contains
`k26_starter_kits.bit.bin`, `k26_starter_kits.dtbo` and `shell.json`
(`XRT_FLAT`, `num_slots: "1"`). Live symbols include `fpga_full`, `amba`,
`zynqmp_clk`; fpga_full resolves to /fpga-region, zynqmp_clk to
/firmware/zynqmp-firmware/clock-controller. The starter overlay targets
fpga_full with firmware-name and zynqmp_reset IDs 116..119. Its dtc reset
warning is from unresolved overlay references, not evidence of a boot fault.
Full Vivado implementation completed; the timing gate refused export at 100 MHz
(setup WNS -0.497 ns, TNS -2642.742 ns; hold WNS +0.002 ns). The routed checkpoint
passes an 80 MHz timing ceiling for a Linux request of 75 MHz using
`validate_runtime_clock.tcl` (setup +2.003 ns, hold +0.002 ns; no failing or
unconstrained endpoints, all 176,601 routable nets routed). Log:
`build/v2/kr260-runtime-clock.log`. This changes
constraints only; the XSA PS preset remains 100 MHz, so the Linux override and
live-clock check are required. Read-only ID/BUILD probing passed on 2026-10-09.
`build/v2/kr260-preview.xsa` is a hardware-only export for SDT inspection;
it contains no deployable bitstream and is not the final implementation export.
SDTGen preview output is in `build/v2/kr260-sdt-preview/pl.dtsi`: PL0/PL1
IDs 71/72, estimated rate 99,999,001 Hz, AFI IDs 0..13 value0, ID14 0xa00,
ID15 0, register range 0xa0000000/0x1000. Prepared `sysone-v2.dts` requests the
design's nominal 100 MHz, retains the port configuration and register mapping,
wraps them as an Ubuntu overlay and omits IRQ properties because
the current /dev/mem client polls DONE. Compilation and board application passed.
The board exposes xilinx_fclk and afi-fpga platform drivers, and live PL0/PL1
rates before deployment are 99,999,999 Hz. `package_app.py` requires final
bit/XSA/reports, verifies the embedded bitstream matches, converts it via
bootgen and builds a hashed app archive. Packaging succeeded after lower-clock
validation: `build/v2/kr260-app.tar.gz` is ready to transfer. Final XSA bitstream
matches the implementation; SDTGen final IDs/AFI/register mapping match the
overlay with its explicit lower clock. Bundle bit.bin SHA256 is
67f3b931c27e816330d2811ee746a75f607c34bc188c7a8931313694a5ce4eb5.
Overlay review corrected an extra nested simple-bus before deployment: the
clock/AFI/encoder nodes now attach directly under amba, matching AMD's KR260
overlay layout and Linux's populated-parent requirement for dynamic devices.
dtc compilation is warning-free. `deploy_app.py` is included in the app archive;
it validates hashes and the live reservation before installing/loading, then
checks manager state, bound fclk/AFI drivers and enabled PL0 before a read-only
SYS2/BUILD probe. Root board execution passed on 2026-10-09. Local checks pass: 31 tests,
including rejection of a live clock above the timing ceiling before MMIO.

Update 2026-10-08: the owner confirms the KR260 is just unboxed, with no OS setup.
The active first-boot and dual-board workflow is `scripts/v2/kr260/README.md`;
`scripts/v2/kr260/doctor.py` collects Linux setup information without probing PL.
Local Vivado 2025.2 lacks KR260 board files, so project creation is pending their
installation. Client clock defaults and KR260 image/region guards have been added;
hardware validation remains pending. Retain Nexys as the verified baseline.

First boot confirmed by the owner later on 2026-10-08: Ubuntu 24.04.2 LTS,
kernel 6.8.0-1015-xilinx aarch64, Python 3.12.3, eth1 DHCP address
192.168.0.239, user ubuntu (serial COM9). The 128 GB microSD boots and provides
114G root capacity, 107G available. `xmutil listapps` shows k26-starter-kits
loaded in slot 0. `~/sysone-venv` with NumPy 2.4.4 is confirmed working.
Workspace SSH still requires password authentication; no credentials are stored.
`build/v2/kr260-transfer.tar.gz` is prepared with runtime sources, examples,
bert-mini-slots4-kr260 image, source tokenizer and decision rule. Next: transfer
and run doctor; custom encoder deployment and DDR reservation remain pending.

Doctor received: board model ZynqMP KR260 revB; dtc and xmutil installed,
FPGA manager operating, /dev/mem available. The only boot reserved-memory node
is pmu@7ff00000, 1 MiB, no-map. The proposed 0x60000000 image region is inside
System RAM and is NOT a dedicated encoder allocation. Do not use it until the
boot memory configuration is fixed. /proc/iomem reports other transient reserved
subranges inside System RAM; these do not establish ownership for the encoder.
Local build probe also found that Vivado 2025.2 has no xck26 parts installed.
An official Board Store sparse checkout is prepared under build/v2/board-store,
commit 40fad97cf36f3d856c6759d83c2390de1566ffa7; the build script uses it if
present. Add K26/Zynq UltraScale+ MPSoC device support in the Vivado installer
before continuing project validation. This is a device-install prerequisite,
not an established licence failure.

After the owner added Kria device support, Vivado 2025.2 successfully created
`build/v2/kr260/sysone_v2_kr260.xpr`, applied the PS board preset, validated the
block design and generated system_wrapper.v (2026-10-08). Control map is
0xA0000000/4K; encoder HP0 DDR_LOW map is 0x00000000/2G. This verifies project
creation only, not synthesis, timing or deployment. Log: build/v2/kr260-create.log.
Warnings to review before implementation: local board repo shadows installed
board files, encoder clock lacks initial FREQ_HZ, SmartConnect endpoint auto-config
limitations, HP0 AWUSER/ARUSER widths 1 vs 0. Linux boot configuration output
(/proc/cmdline and /boot/firmware/extlinux/extlinux.conf) is still needed for the
boot-time reserved-memory step.

Boot configuration received: /boot/firmware contains image.fit and
boot.scr.uimg (plus .bak copies), not extlinux. /proc/cmdline includes
`cma=800M`, root=LABEL=writable and console=ttyPS1,115200. Inspect the FIT
components and installed flash-kernel ITS template before modifying memory
reservations; do not assume a standalone boot DTB or reuse the .bak files as a
verified recovery image. Dedicated encoder memory remains unconfigured.

FIT inventory received: kernel-1 (gzip), ramdisk-1, six uncompressed FDTs;
KR260 revB is Image 5, node fdt-smk-k26-revA-sck-kr-g-revB.dtb, configuration
conf-smk-k26-revA-sck-kr-g-revB. The installed ITS template is
/usr/share/flash-kernel/its/image-kria.its with kernel/initrd/version placeholders.
u-boot-tools 2025.10 and dtc 1.7 are installed. Next: prepare a separate copy of
the revB DTB with a 64 MiB no-map encoder reservation at 0x60000000, then rebuild
and verify a candidate FIT before replacing any boot files. Boot configuration
selection must remain intact and kernel updates must preserve the reservation.

Owner prepared ~/sysone-boot/kr260-reserved.dtb from FIT Image 5, verified reg
<0 0x60000000 0 0x04000000> and empty no-map. Boot files remain unchanged.
scripts/v2/kr260/prepare_reserved_fit.py now builds a candidate directly from
the current FIT, preserving other payloads and configurations, checks source
image hashes, allows only that exact DTB edit and updates its SHA hash. It rejects
signed/external-payload FITs, saves a source snapshot plus JSON hashes and never
installs a boot file. Six tests pass, including independent dtc validation.
Next: transfer this script and prepare the candidate on the board; inspect its
report before installing/rebooting. Persistent flash-kernel integration is pending.

Candidate prepared successfully on the board. Source SHA256:
29705143a73a5d4d697a4ff840bc98c6628ae1b98c73d53d9665c534ab29bbdf
Candidate SHA256:
f428fff44206d00bac4436b41c04e6151ebe59c7fc0f939e2c8e1087ad382d1a
Paths: ~/sysone-boot/image-sysone.fit and image-sysone.original.fit. Report
confirms only the revB DTB changes, all image hashes verified, installed=false.
Next: recheck live source/candidate hashes, preserve original on the boot FAT
partition as image.fit.sysone-original, install candidate, sync, reboot and
confirm the reserved-memory node and /proc/iomem before mapping memory.

Installation and reboot confirmed by the owner: live device tree contains
/reserved-memory/sysone@60000000 with reg and no-map, and /proc/iomem shows
60000000-63ffffff : reserved. The 64 MiB allocation is now excluded by Linux.
Recovery original is /boot/firmware/image.fit.sysone-original; cp -n emitted a
portability warning but all comparisons and reboot passed. This is a one-time
FIT patch so far: determine installed flash-kernel hooks/ITS override support
before enabling further package upgrades. Custom encoder bitstream remains
unbuilt/unloaded; never probe 0xA0000000 until the matching PL app is deployed.

Installed flash-kernel functions received: mkimage_fit substitutes kernel/version
placeholders and reads DTBs from /lib/firmware/<version>/device-tree/xilinx; no
preboot callback is shown before FIT construction. Persistent setup prepared:
patch_kernel_dtb.py adds the exact reservation idempotently to the version's revB
DTB, saves originals by SHA256 under /var/lib/sysone/dtb-backups/<version>, rejects
overlap/wrong board, verifies other nodes and atomically replaces only that DTB.
install_memory_hooks.sh installs 00-sysone-reserved-memory in kernel postinst.d
and initramfs post-update.d, plus helpers under /usr/local/lib/sysone. Installation
patches the current kernel DTB but does not regenerate FIT or reboot. Transfer
archive: build/v2/kr260-memory-hooks.tar.gz. Ten relevant tests pass. Next: owner
installs and returns run-parts order; verify hooks precede flash-kernel and test
regeneration before considering kernel-update persistence verified.

Owner installed memory hooks successfully. Running kernel is now
6.8.0-1036-xilinx. Its source revB DTB was patched; original backup SHA256 is
eaa64d3b6cf2842c412f938598e90074ad80ff8430384d931c5c07490dbb7aa1
under /var/lib/sysone/dtb-backups/6.8.0-1036-xilinx/. run-parts order confirms
00-sysone-reserved-memory precedes initramfs-tools and zz-flash-kernel in kernel
postinst, and precedes flash-kernel in initramfs post-update. Next: exercise
update-initramfs -u for the running kernel, extract the regenerated FIT's revB
DTB and verify its reservation before rebooting. Hook install alone is not yet
a verified regeneration test.

Normal regeneration tested successfully: update-initramfs -u on
6.8.0-1036-xilinx invoked the reservation hook (already correct), then
flash-kernel installed a new image.fit and boot.scr.uimg. Extracted FIT Image 5
contains reg <0 0x60000000 0 0x04000000> and no-map; SHA1
8d9c198ce4bf3cdb67f6800e2869e870daacbe16. Initramfs reported missing xc2028/
xc4000/xc5000 tuner firmware and flash-kernel printed a blank DTB lookup warning;
neither prevented successful ITS-based FIT construction. Next: reboot this
regenerated image, verify the live reservation, then proceed with the PL build.

Owner confirmed successful boot of the normally regenerated FIT: uname
6.8.0-1036-xilinx, live sysone@60000000 with reg/no-map, iomem
60000000-63ffffff : reserved. Same-kernel regeneration and reboot are verified;
a future new-kernel install has not yet been exercised. Local KR260 build started
with Vivado 2025.2, log build/v2/kr260-build.log. Build script now prefers installed
board files, writes utilization/timing reports and rejects negative setup/hold
slack before exporting the XSA. Generated AXI wiring was reviewed: s_axil is
AXI4LITE, m_axi AXI4, HP0 AWUSER/ARUSER are explicitly tied to zero.

## 1. The project in one paragraph

"System One" is a fast text classifier (an assistant's quick, intuitive first pass) built
in FPGA hardware. **v1** (in `rtl/`, `scripts/`, `src/sysone/`, unchanged) is a hashed
bag-of-n-grams classifier that runs entirely in block RAM on a Digilent Nexys 4 DDR
(Artix-7 xc7a100t). **v2** (everything under `*/v2/`) runs a small transformer encoder
(MiniLM-L6: 6 layers x 384, 23M parameters, INT8) on the FPGA: the weights live in the
board's DDR memory as one "DDR image"; the host sends token ids over raw Ethernet, the
FPGA runs the whole encoder and returns the final hidden states, and small task heads
(intent classification, slot filling, sentence pairs, a sentence embedding) run on the
host in NumPy. The FPGA result is bit-exact with a Python integer model
(`src/sysone/v2/ddr_image.py`, `ImageMachine`), which is how everything is verified.

## 2. Rules from the owner (standing)

* **Sole author.** Commits are by `Safwan Kamal <safwankamal123@gmail.com>` only: no AI
  co-author lines or "generated with" trailers in commits or pull requests.
* **Commit or push only when asked.** Never touch the `main` branch of the separate
  Genome-Classifier repository.
* **Never ask the owner for access tokens** (Hugging Face or others) in chat.
* **No speed conclusions from the Ethernet link.** The host connects through a USB
  100 Mb/s adapter, so host-measured times are dominated by it. Speed is reported from
  the board's own clock counters; host-measured times are labelled "host path".
* **Document significant problems and their fixes** in `rtl/v2/README.md`, section
  "Problems hit and how they were solved" (continue the numbering). When the owner pastes
  command output marked "document:", record the results in the README and fix anything
  the output shows to be wrong.
* Heads run on the host (an FPGA-heads variant exists behind the `FPGA_HEADS` RTL
  parameter; it was not worth it).
* Before starting on a request, check for recently changed or uncommitted files: once,
  an interrupted session left half-finished work that was then done a second time.

## 3. Machines, tools, repository

* **Repository**: `github.com/SafwanKamal/system-one-fpga`, branch `main`. The working
  copy is on the owner's Windows laptop:
  `C:\Users\user\OneDrive - Texas Tech University\Desktop\Code\FPGA Project\system-one-fpga\system-one-fpga`
  (long path: Windows' 260-character limit broke a Vivado IP build once, so Vivado
  projects use short names, `build/v2/enc`, `build/v2/encp`; `subst` a drive letter if
  it recurs).
* **Git state at the start of 2026-10-08 preparation: HEAD is `bc27a36`** (encoder
  board run, KR260 block, v3 models and host features committed). Subsequent
  dual-board preparation is uncommitted; use `git status` for the live state.
  Never commit `logs/` or `_to_delete/`
  (transfer leftovers, safe to delete). `export/`, `models/` and the downloaded corpora
  under `data/v2/` are gitignored.
* **Python**: `uv`. Runtime needs only NumPy (+ scapy for the Ethernet link):
  `uv run python ...`. Training and image compilation need PyTorch + transformers, in the
  `train` dependency group: `uv sync --group train`, then `uv run --group train python ...`.
  Corpora: `uv run python scripts/v2/fetch_v2_data.py`; base models:
  `uv run --group train python scripts/v2/fetch_models.py` (public, no token).
* **Training runs on the laptop CPU** (no NVIDIA GPU; all cores by default): about 36 min
  per epoch for the current corpus (~97k training chains).
* **Vivado**: laptop 2025.2. A desktop has 2026.1, whose licence tiers reject the
  xc7a100t unless the free BASIC tier is selected.
* **Simulation**: Verilator 5.x, `simulation/v2/Makefile` (targets listed in the README).
* **Nexys host side**: Windows laptop, Realtek USB Ethernet adapter, raw Ethernet via
  scapy/Npcap: `-i "Realtek USB FE Family Controller"`.

## 4. Current state

### Nexys 4 DDR: the v2 encoder runs on the board, bit-exact

* Bitstream: `vivado -mode batch -source scripts/v2/create_project_v2.tcl -tclargs build encoder`,
  then `vivado -mode batch -source scripts/v2/program_board_v2.tcl -tclargs encoder`.
  75 MHz, worst setup slack +0.187 ns; LUT 79%, block RAM 128/135, DSP 236/240 (full).
* `bert-mini-slots4` on the board: `check` bit-exact for 1/12/64/128 tokens; 128 tokens =
  2,951,462 clocks = 39.35 ms (simulation: 2,952,317). `eval --verify`: 120/120
  bit-exact.
* Host client `scripts/v2/sysone_v2_client.py` (all commands take `--image <name>`):
  `load` (writes the image to DDR, 15 s for 11 MB), `check` (random token chains vs
  `ImageMachine`), `run --dataset <name>|auto [--intents file.json] "text"`,
  `doc --file text.txt [--query ...] [--intents ...]` (long texts), `eval`; `--local`
  runs without a board; `--kr260` runs on the KR260's ARM cores (section 5).

### Models (heads on the host)

| test sets | minilm-l6 | **minilm-l6-v3b** (current best) |
|---|---|---|
| CLINC150 in-scope / combined incl. out-of-scope rule | 0.953 / 0.902 (Ï„ 0.475) | 0.961 / **0.9025** (Ï„ 0.48) |
| ATIS intent / slot F1 | 0.959 / 0.782 | 0.976 / 0.876 |
| HWU64 intent / slot F1 | â€“ | 0.916 / 0.696 |
| SGD dialogue intent / slot F1 | 0.879 / 0.496 | 0.868 / 0.506 |
| SICK / MSRP | 0.862 / 0.751 | 0.858 / 0.713 |
| unseen intents from 5 examples, integer image: Banking77 / SNIPS | â€“ | 0.752 / 0.905 |

* v3b training command (laptop): `uv run --group train python scripts/v2/train_chain.py
  --model models/all-MiniLM-L6-v2 --name minilm-l6-v3b --init export/v2/chain/minilm-l6/chain_model.pt
  --hwu --embed-dim 384 --teacher models/all-MiniLM-L6-v2 --epochs 2 --lr 4e-5 --head-lr 1e-3
  --distill-weight 10 --resume`.
* v3b image `export/v2/image/minilm-l6-v3b/` (23,035,904 bytes; `compile_image.py check`:
  0 mismatches over 1,400 chains; runs on the same bitstream). **Now verified on both boards over the frozen 350-request suite.**
* `auto` routing: one encoder pass; custom intents (embedding head, nearest centroid of a
  few example sentences, `examples/v2/custom_intents.json`) â†’ CLINC with its
  out-of-scope threshold â†’ ATIS (flights) / SGD (services) / HWU64 (assistant) intents
  and slots â†’ else the CLINC intent.
* Long inputs: the encoder window is 128 tokens. `doc` splits text into sentences and
  sends one request per sentence (packing several into one request costs accuracy:
  1000-word documents 0.919 alone vs 0.790 packed). The window cannot grow on the Nexys
  (block RAM).

### KR260 (K26 SOM, part xck26-sfvc784-2LV-c): bert-mini hardware evaluation complete

* RTL `rtl/v2/platform/kr260/`: `kr260_encoder.sv` (AXI4-Lite registers 0x00 CONTROL â€¦
  0x2C RESULT, ID register "SYS2", BUILD register, interrupt; the same `encoder_system`
  as the Nexys; `axi_memory_port.sv` = AXI4 master to the PS DDR) and
  `kr260_encoder_wrapper.v` (plain-Verilog wrapper for a block-design module reference).
  Parameters: TILE_OUT 32, DRAIN_LANES 4, NORM_LANES 4, 40-bit addresses.
* Simulation (`make encoder-kr260`; `make kr260-vectors` + `make kr260` with an AXI DDR
  model with random stalls, runs started through the registers): bit-exact for 1, 12
  and 128 tokens. bert-mini at 128 tokens: 1.39M clocks (2.95M on the Nexys), ~14 ms at
  100 MHz. LayerNorm is now ~31% of the time.
* Vivado block design `scripts/v2/kr260/create_project_kr260.tcl`: project validation,
  synthesis, placement and routing pass in Vivado 2025.2. The routed full design
  uses 99,783 LUTs (85.20%), 49,624 registers, 606 DSPs, 59 BRAM tiles and 18
  UltraRAMs. 100 MHz fails setup WNS -0.497 ns. The lower-clock export passes an
  80 MHz ceiling with setup +2.003 ns and hold +0.002 ns; Linux requests 75 MHz.
  Runtime clock must be checked before register access (problem 25).
  Zynq UltraScale+ PS with the board preset,
  M_AXI_HPM0_FPD â†’ encoder registers at 0xA000_0000, encoder â†’ S_AXI_HP0_FPD (128-bit),
  pl_clk0 100 MHz, interrupt â†’ pl_ps_irq0; output in `build/v2/kr260/`.
* ARM-side driver `src/sysone/v2/kr260_link.py`: `Kr260Link(registers=0xA000_0000,
  memory=(0x6000_0000, 64 MiB))` via `/dev/mem` (uncached); the whole host client runs on
  the board with `--kr260`. Bert-mini hardware checks and matched evaluation passed.
* KR260 images: `uv run --group train python scripts/v2/compile_image.py build --name <model>
  --board kr260 --base 0x60000000 --suffix=-kr260 --reuse-calibration` (tile 16x32,
  absolute addresses). Built: `bert-mini-slots4-kr260` and `minilm-l6-v3b-kr260`.

## 5. KR260 bring-up and next models

1. **Board OS â€” done**: Ubuntu 24.04.2, kernel 6.8.0-1036-xilinx, NumPy 2.4.4
   in ~/sysone-venv. SSH is ubuntu@192.168.0.239 (DHCP); direct workspace SSH
   still requires the owner's password. Runtime sources and bert-mini image
   have been transferred under ~/system-one-fpga.
2. **Vivado â€” done for bring-up**: Kria device/board support is installed. The
   32-lane design routes and passes the lower-clock timing gate. The checked
   final XSA, bitstream, timing, route status and utilization reports exist.
3. **Deploy â€” done**: packaging passed and produced
   build/v2/kr260-app.tar.gz with
   `.bit.bin`, `.dtbo`, shell metadata, hashes and the deployment helper. Transfer
   and unpack it on the board, then run its deploy_app.py with sudo. It validates
   the reservation and hashes before xmutil, then checks drivers/clock before
   the SYS2/BUILD probe. The owner ran it successfully on 2026-10-09 at 71,428,571 Hz.
   Do not use the hardware-only preview XSA for deployment.
4. **Memory â€” done**: 64 MiB at 0x6000_0000 is reserved with no-map in the boot
   DTB and verified in iomem. Early kernel/initramfs hooks preserve it before
   flash-kernel generation. Normal FIT regeneration and reboot passed; future
   new-kernel installation has not yet been exercised. HP0 is not cache coherent;
   the current driver uses an uncached /dev/mem mapping with O_SYNC.
5. **First run on the ARM, after deployment checks**: `sudo ~/sysone-venv/bin/python scripts/v2/sysone_v2_client.py --kr260 --image
   bert-mini-slots4-kr260 --clock-mhz <live clock_hz / 1000000> load`, then `check` (must be bit-exact; compare
   the clocks with the 1.39M simulation figure), `run --dataset auto "..."`, `doc`, and
   `eval --verify` (needs the corpora on the board).
6. **MiniLM-L6-v3b on the KR260**: build `minilm-l6-v3b-kr260` on the laptop (command
   above); copy the image directory (image, `manifest.json`, `decision.json`) and
   `export/v2/chain/minilm-l6-v3b/tokenizer.json`.
7. **Experiments the larger chip allows** (all measured with the board's clock
   counters): a faster pl_clk, a wider array or the packed-DSP option (two INT8 products
   per DSP; 1.6â€“1.7x in simulation on the Nexys), more LayerNorm lanes, a longer window
   (UltraRAM could hold MiniLM buffers for ~512 tokens; the models would need training
   on longer inputs), a per-segment attention mask (packed long-text speed without the
   accuracy loss), and evaluating through the hardware instead of `ImageMachine`
   (Banking77 few-shot took 5.7 h in NumPy).

### MiniLM KR260 preparation (2026-10-09)

Preparation completed: both image variants match on all 350 frozen test requests
(50 each: ATIS, CLINC, HWU, MSRP, multi-CLINC, SGD, SICK; seed 0), including
integer hidden states and task-head integer/float logits and labels. The embedding
head also passed a separate exact smoke comparison. Suite SHA256:
`f89ce2428293503f0458e98e5f5aebe29e5be08f7f9b3c36012c7d2e5428109e`.
Ready archive: `build/v2/kr260-minilm.tar.gz` (23,967,804 bytes). Every archived
file was read back and matched to its workspace source by SHA256; no training
checkpoint is included. Hardware MiniLM load/check/evaluation remains pending.

`minilm-l6-v3b-kr260` is built from the existing trained checkpoint and reused
calibration: 23,087,104 bytes, hidden 384, six layers, 16x32 tiles, base
0x60000000. Image SHA256:
0cf8d009e9fc55367a3fa53e853a9b498227daf91aa669206e4389ec5931eea1.
CRC checks pass; request IDs at 0x61700000 and maximum result end 0x6170d000
fit the 64 MiB reservation. Existing BUILD 0x20801804 supports it without a new
bitstream. The relocated ImageMachine flight smoke test passed intent/slot routing.
MiniLM FPGA load, length checks and the 350-request evaluation subsequently passed; see the verified hardware results above.

`package_eval.py` now accepts --image and --include-model, verifies SHA/CRCs,
checks the deployed KR260 dimensions/reserved bounds and bundles model files,
tokenizer and cached goldens alongside the NumPy runtime. The default bert-mini
bundle still validates. Runtime/suite/memory/deployment tests: 32 passed.
Source and artifact fingerprints: build/v2/eval/minilm-preparation.json.
Owner transfer, load and verification commands: scripts/v2/kr260/README.md.
After a reboot, reload the FPGA app first. Switching models requires DDR load;
both images use the same reserved base, while their files/reports are retained.

## 6. Loose ends on the Nexys side

* Out-of-scope thresholds rerun after the router-statistics fix (2026-10-09):
  CLINC tau stays 0.480; corrected HWU tau is 0.480 (was 0.515). Decision files
  for both image variants match. The full CLINC+HWU router rejects 29.2% of
  CLINC OOS test queries while accepting 96.97% of HWU test queries; CLINC-only
  rejects 70.3%. See results/v2/chain/minilm-l6-v3b_oos.json. This is CPU integer
  image/router evaluation; it is not a new FPGA measurement.
* v3b Nexys load and frozen 350-request evaluation passed; optional routing/document experiments: `--image minilm-l6-v3b` with `load`, `check`,
  `run --dataset auto --intents examples/v2/custom_intents.json "how should I build a h-bridge circuit?"`,
  `doc --file examples/v2/long_text.txt`.
* The packed-DSP build (`encoder_packed`) was never synthesised; the Nexys is nearly
  full.
* Commit the outstanding work when the owner asks (sole author, no AI trailers).
