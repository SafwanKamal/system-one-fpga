# Handoff: start here (updated 2026-11-24)

A new session (Claude, Codex or Gemini), on this computer or another one, should read this
first. It records where the work stands, what each agent has done, the rules that are not
visible in the code, and the next steps. The 8k-line root `HANDOFF.md` is the older dated
history (RC1 baseline, v1–v9e, agent gate). Read it only for background.

## Getting going on another computer

1. Clone or pull: `git clone https://github.com/SafwanKamal/system-one-fpga.git`, then
   `git checkout codex/hardware-consolidated-rc1`. All work is on this branch; `main` is far
   behind it. Nothing has been merged to `main`.
2. **What is NOT on GitHub** (gitignored or untracked; only on the original PC):
   - `build/`: board runner scripts (`build/v2/*-run/auth_session.py`), all board evidence,
     Vivado outputs, deployment tarballs. If you need a board runner, copy one from the
     original PC or rebuild it from `scripts/v2/`.
   - `models/`: the Qwen3-0.6B Q8_0 weights (SHA256 `9465e63a…b031`).
   - `BOARD_STATUS.json`: the board ownership lock. It is canonical **only on the original
     PC**. Never treat a copy on another computer as the lock. If you work on the board from
     a second computer, agree with the user which machine holds the lock first.
   - `logs/`, `_to_delete/`, research worker archives.
3. **Board reachability:** the KR260 is at `192.168.0.239` on the home LAN, and its serial
   console is on COM9 of the original PC. The other computer can reach SSH only on the same
   network.
4. **Multi-agent coordinator:** the `coordinator` MCP server and the `team-coordinator` skill
   live outside the repo (`~/.claude.json`; script under
   `C:\Users\user\Documents\Codex\2026-11-20\sa\outputs\coordinator\`). Install them again on
   the new machine if you want Codex and Gemini runs there.
5. Python environment: `uv sync` (`pyproject.toml`, `uv.lock`). Vitis C-sim needs a path
   without spaces (the original PC used `S:\`).

## Where things stand

- **Live on the KR260:** RC1.3 is the default `sysone-rc1.service`. Board record revision 128
  (2026-11-24 13:06Z) shows state `ready`, no reservation, boot `d65e03c2`.
  - **Hardware:** the v9h image. Passes of up to 4 tokens split their weight rows across HP0 and
    HP1, so plain decode is 1.50x faster than v9g. Bit-exact on the board.
  - **Drafter:** the cost-aware lossless drafter with a 7-coefficient v9h cost model
    (`experiments/rc13/fit_v9h.py`).
  - **Prompt cache:** the 32-token shared system-template prefix stays cached across
    conversations. `reset_cache=True` clears everything.
  - **Image switching:** while the service runs, the FPGA holds v9h. After
    `systemctl stop sysone-rc1.service` it holds v9e.
  - **Results:** 21 tool queries take 23.5 s end to end, against 55.8 s on RC1.1 (2.38x), with
    outputs identical to RC1.2.
  - **Rollback:** `python3 /var/lib/sysone/rc1-3-v1/install_rc13.py disable` returns to RC1.2.
  - **Update in place:** `install_rc13.py update --staged DIR` backs up, restarts and probes,
    and rolls back if the probe fails.
- **RC1.4 (v9i) is staged but not the default.** The bundle is on the board at
  `/var/lib/sysone/rc1-4-pilot`. Whether to promote it is **the user's decision**, so see the
  trade-off below.
- **Full benchmark sweep:** stopped. Do not restart it.

## Timeline of what was done (Claude, Codex, Gemini)

| Date | Who | What |
|---|---|---|
| ≤ 2026-11-08 | Codex + Claude | v1–v9e hardware, sealed persistent runtime, **RC1** baseline (v9e) with auto-start on boot. Agent-command gate research (v1 bridge on board; RTL v3 in simulation only). See root `HANDOFF.md`. |
| 11-17 → 11-18 | Claude | Card reflash and recovery (`experiments/kria_recovery/`). Bit-exact speculative decoding audit. **RC1.1** = RC1 + lossless speculation. Update policy that blocks unattended upgrades on the board. |
| 11-19 | Claude | **v9f** batched vocabulary head: 1.92x decode, bit-exact. |
| 11-19 → 11-20 | Claude | Core feasibility study. **v9g** (P=4 attention): 1.21x over v9f. Cost-aware drafter: 1.14x. **RC1.2** shipped. |
| 11-20 | Claude | **v9h**: small passes on a second weight port, 1.50x plain decode. **RC1.3** shipped with the system-template prefix cache. Survives reboot. |
| 11-21 | Claude | Coordinator MCP installed. Test run `e87839077490` passed (all three agents, simulated board lock). First `docs/HANDOFF.md`. |
| 11-22 | Run `7b30ba1da0cc`: Claude, Codex, Gemini | **v9i** (D3 dual port + P=2 attention) chosen for a pilot. **Codex:** v9j csynth, 133.3k decoder LUT, does not fit (`experiments/v9j/`). **Claude:** v9j route plan and gate (route skipped). **Gemini:** pilot analyser crosscheck plus per-format timing (`experiments/v9i/pilot_analysis/`, 23 tests). Write-up: `docs/research/2026-11-23-v9i-v9j.md`. |
| 11-22 | Run `d3f06adaeb92`: Claude, Codex, Gemini | **Claude:** v9i board pilot. 57/57 outputs identical to RC1.3, 1.28x end to end on tool queries (prefill 1.38x, decode 1.21x), long-prompt prefill 0.89x. Analyser gate NO-GO. RC1.3 restored. **Codex:** v9k (B=16) csynth exceeds BRAM/URAM; do not route. **Gemini:** exactness harness `--batch 16`. Write-up: `docs/research/2026-11-23-v9i-pilot-v9k.md`. |
| 11-24 | Claude (run `bf2b40a2002f`) | v9i drafter refit plus long-prompt board check. Refit was a no-op (modelled coefficients within 0.6%). Both images 52/52 exact. RC1.4 against RC1.3: long prompts **0.88x** (drafted decode 0.75x), short prompts **1.055x**. Verdict: **trade-off inherent to the hardware**, not calibration. See `experiments/v9i/refit/RESULTS.md`. RC1.3 restored on the same boot. |

## Hard rules (not in the code)

- **Board passwords:** the user types them into the Tk dialog of a `build/v2/*-run/auth_session.py`
  script. Never type, store or log them.
- **Board ownership protocol:** use `scripts/v2/board_status.py`, in this order:
  1. `reserve --owner <agent> --purpose ...`;
  2. `begin --claim ID --operation ...`;
  3. `record --claim ID --observation FILE`, where the file is JSON with state (ready, stopped
     or unknown), verified_at_utc, evidence, active_package and boot_id;
  4. `release --claim ID`.
- **Approvals:** hard resets, board image swaps, reboots, and promoting RC1.4 need the user's
  approval in chat.
- **Downloads:** ask before downloading packages.
- **Commit messages:**
  - write the message file with an editor or the Write tool, not PowerShell `Set-Content`,
    which adds a BOM;
  - end it with the agent's Co-Authored-By line;
  - never stage `BOARD_STATUS.json`, `_to_delete/`, `logs/`,
    `results/research/future_sensor_memory/*/{archives,workers}`,
    `simulation/v2/gate/vectors/gate_v3_frames_*.txt` or `simulation/v2/vectors/kr260/image.hex`.
- **Pushing and merging:** both stay with the user. Never merge to `main` without being asked.
- **Agent gate:** never present the gate or the interlock it hosts as a safety function. The
  KR260 is not SIL; frame the gate as an IEC 62443 security conduit.
- **Working style:** the user wants bold progress. Use benches of about 20% of the full
  workload (~36 cases, stratified) and no pre-registration for routine steps. The safety
  rules above still apply in full.

## Pitfalls already hit

- **Board queues:** write queue JSON from Python. Git Bash heredocs turn `/home/...` into
  Windows paths, or set `MSYS_NO_PATHCONV=1`.
- **Queue file names:** they must match `\d{2}-[a-z0-9-]+.json` and run in sorted order. Name a
  repair job so it sorts after the failed one, for example `05-r1-...`.
- **Uploads:** they are exclusive-create, so a re-upload needs a new remote filename.
- **Control bytes:** never put a NUL or other control byte in a command string. sshd drops the
  exec, which shows up as an endless EOF reconnect loop.
- **Backgrounding:** never end a command chain with `&`. When SSH returns it kills the whole
  backgrounded list, and once that left no FPGA app loaded. The fix was
  `xmutil loadapp <v9e>`.
- **Long board work:** launch it with `systemd-run --unit=spec-qual-... --collect`. needrestart
  skips units named `spec-qual*`.
- **After a reboot:** SSH accepts logins at about 90 s, but command channels can time out for a
  while longer. Wait before running jobs.
- **Board hangs:** past hangs traced to the failing USB root drive. Check COM9 for I/O errors
  first. After any JTAG use, kill `hw_server`.
- **Renames:** blanket `rc12`→`rc13` style renames also hit `hardware-consolidated-rc1-20261108`.
  Diff the result against the source.
- **Machine limits:** the original PC has 14 GB RAM, so run one Vivado job at a time.
- **Gemini sidecar:** after the coordinator update of 2026-11-23, the profiles moved to
  `work/profiles/`. Repoint `~/.gemini/config/sidecars/local-team-system-one-fpga/sidecar.json`,
  then restart it in the Antigravity UI.

## Next steps (recommended order)

1. **Decide on RC1.4** (the user's call). It gains 1.28x on tool queries and 1.055x on short
   prompts but loses 12% on long prompts. One option is a hybrid: route by prompt length, or
   swap images per request. Image swaps cost time, so measure that before promising it.
2. **Reclaim attention LUTs** (36.5k routed in v9g/v9h). This is the route to a full dual port
   without the P=2 attention penalty that v9i pays at long positions.
   - The full dual port alone synthesizes to 113.9k decoder LUT.
   - v9j (133.3k) and v9k (BRAM/URAM) do not fit.
   - It's a good coordinator run: Codex on HLS restructuring, Gemini on the exactness audit
     harness, Claude on synthesis and integration plus board qualification.
3. **Remaining time per tool query:** user-specific prefill is about 0.56 s and decode about
   0.5 s.
4. **Agent gate:** RTL v3 has still not been put in a board bitstream. Pick it up again only if
   the user returns to that track.
