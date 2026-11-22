# Handoff: start here (updated 2026-11-21)

A new Claude Code session on this repository should read this first. It records where the work
stands, the rules that are not visible in the code, and the next steps.

## Where things stand

- **Branch:** `codex/hardware-consolidated-rc1`. It has no upstream, sits 21 commits ahead of
  `origin/main`, and has never been pushed. Push or open a PR only when the user asks.
- **Live on the KR260:** RC1.3 as the default `sysone-rc1.service`. Details are in
  `docs/research/2026-11-20-rc1-3-ship.md`.
  - **Hardware:** the v9h image. Passes of up to 4 tokens split their weight rows across HP0 and
    HP1, so plain decode is 1.50x faster than v9g. Bit-exact on the board.
  - **Drafter:** the cost-aware drafter with a 7-coefficient v9h cost model
    (`experiments/rc13/fit_v9h.py`).
  - **Prompt cache:** the shared system-template prefix (32 tokens) stays cached across
    conversations; `reset_cache=True` still clears everything.
  - **Reboots:** a soft reboot was tested on boot `d65e03c2`. RC1.3 auto-starts and switches
    v9e → v9h.
  - **Results:** on 21 tool queries, end-to-end time is 23.5 s against 55.8 s on RC1.1 (2.38x).
    Outputs are identical to RC1.2.
  - **Rollback:** `python3 /var/lib/sysone/rc1-3-v1/install_rc13.py disable` returns to RC1.2.
  - **Update in place:** `install_rc13.py update --staged DIR` backs up, restarts, probes, and
    rolls back if the probe fails.
- **Board record:** `BOARD_STATUS.json` revision 120 shows state `ready` and no reservation.
- **Full benchmark sweep:** stopped. Do not restart it.

## Hard rules (not in the code)

- **Board passwords:** the user types them into the Tk dialog of a `build/v2/*-run/auth_session.py`
  script. Never type, store or log them.
- **Board ownership protocol:** use `scripts/v2/board_status.py` in this order:
  1. `reserve --owner Claude --purpose ...`;
  2. `begin --claim ID --operation ...`;
  3. `record --claim ID --observation FILE`, where the file is JSON with state, verified_at_utc,
     evidence, active_package and boot_id;
  4. `release --claim ID`.
- **Approvals:** hard resets, board image swaps, and reboots need the user's approval in chat.
- **Downloads:** ask before downloading packages.
- **Commit messages:**
  - write the message file with the Write tool, not PowerShell `Set-Content`, which adds a BOM;
  - end it with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`;
  - never stage `BOARD_STATUS.json`, `_to_delete/`, `logs/`, `results/research/future_sensor_memory/*/{archives,workers}`,
    `simulation/v2/gate/vectors/gate_v3_frames_*.txt` or `simulation/v2/vectors/kr260/image.hex`.
- **Working style:** the user wants bold progress with about 20% benches, not exhaustive
  verification. The safety rules above still apply in full.

## Pitfalls already hit

- **Board job queues:** write queue JSON from Python. Git Bash heredocs rewrite `/home/...` into
  Windows paths.
- **Queue file names:** job files must match `\d{2}-[a-z0-9-]+.json` and run in sorted order. To
  add a repair job, choose a name that sorts after the failed one, for example `05-r1-...`.
- **Uploads:** uploads are exclusive-create, so a re-upload needs a new remote filename.
- **After a reboot:** SSH accepts logins at about 90 s, but command channels can time out until
  startup settles. Wait longer before running jobs.
- **Renames:** blanket `rc12`→`rc13` style renames also hit `hardware-consolidated-rc1-20261108`.
  Diff the result against the source.
- **Machine limits:** 14 GB RAM, so run one Vivado job at a time.
- **C-sim path:** run Vitis C-sim from `S:\`, because the OneDrive path with spaces breaks its
  makefile.

## Multi-agent coordinator (new)

The `coordinator` MCP server in `~/.claude.json` and the `team-coordinator` skill let this
session hand work to Codex (GPT-6.2-Sol) and Gemini (Antigravity), with cross-review and
integration.

- **Tested:** test run `e87839077490` on this repository passed. All three agents built, reviewed
  and integrated, using a simulated KR260 lock.
- **Starting work:** use the skill's flow: `team_status`, then `start_run` or `start_plan` with
  disjoint write scopes, then claim Claude's job.
- **Board access:** only one owner at a time, and only through the board protocol above. Give
  plans that touch the board a `resources` lock, and never let a peer access the real board
  without the user's approval.
- **Merging and pushing:** stay with the user.

## Next steps (recommended order)

1. **Push the branch** if the user agrees. Twenty-one commits, including every RC from 1.1 to 1.3,
   exist only on this machine.
2. **Reclaim attention LUTs** (36.5k routed in v9g/v9h). This is the only route to the full dual
   port.
   - The full dual port synthesizes to 113.9k LUT for the decoder alone.
   - It would speed up prefill and add about 15% to speculation.
   - Prefill is weight-bandwidth-bound: 0.166 s per 8-token group, one single-port weight pass.
   - It's a multi-day study and a good candidate for a coordinator run: for example Codex on the
     HLS restructuring, Gemini on the exactness audit harness, and Claude on synthesis and
     integration.
3. **Remaining prefill per tool query** is the user-specific part of the prompt, about 0.56 s on
   average. Decode is about 0.5 s per query.
