# v9i drafter refit and long-prompt board check (2026-11-24, run bf2b40a2002f)

## Refit

- **Script:** `fit_v9i.py`, on 72 board runs from the 2026-11-22 pilot. Replay matches the board.
- **Model:** 7 features, P=2. The `shared` fit, with one coefficient for small and large passes,
  was chosen: median relative error 0.16%, maximum 3.6%, leave-one-out maximum 3.6%.
- **Outcome:** the refit coefficients are within 0.6% of the modelled ones
  (`coef_v9i_modelled.json`), so the refit is effectively a no-op. See `fit.json`.

## Long-prompt board check

- **Workload:** `make_long.py`, 52 cases, 20 of them long. `long_check.py` ran both arms on boot
  `d65e03c2`.
- **Exactness:**
  - v9h + RC1.3 drafter: PASS 52/52.
  - v9i + refit RC1.4 drafter (P=2): PASS 52/52.
- **Timing, RC1.4 against RC1.3 end to end:**
  - long prompts: 0.88x (drafted decode 0.75x);
  - short prompts: 1.055x.
- **Image path:** v9h → v9e → v9i → v9e. RC1.3 was then started again (v9e → v9h), and the
  probe reported `rc1.3-costaware`.
- **Evidence:** the board copy is in `/var/lib/sysone/long-20261124`. The local copy is in
  `build/v2/rc1-4/long/evidence-20261124/`, which is gitignored and exists only on the original
  PC.

## Verdict

**Trade-off.** The long-prompt loss comes from the P=2 attention cost at long positions, so it
is inherent to the hardware and not a calibration error. A better fit will not remove it.
RC1.3 stays the default unless the user chooses to promote RC1.4.
