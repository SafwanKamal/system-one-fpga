# RC1.4 v9i pilot bundle

RC1.4 runs the RC1.3 service logic, shared template prefix cache, and batched
greedy verification on the routed v9i image. The package uses the v9h CSR map.
The DMA ABI, sealed model and 125/250 MHz clocks carry over from RC1.3.

The seven drafter coefficients are **modelled from the v9h board fit**. The
full dual weight port makes the large-pass constant equal to the small-pass
constant. Attention uses `ceil(k/2)` groups. The other coefficients carry over
unchanged. See `experiments/attn_reclaim/model_p2.py`, variant `dual+p2`.
The v9i coefficients have no v9i board calibration.

The installer copies the sealed RC1 package and stages a dedicated v9i firmware
application. It compiles the v9i overlay using the board's existing `dtc`.
Activation uses a volatile systemd drop-in so a normal boot selects the
persistent RC1.3 configuration. The explicit rollback drains the pilot, returns
the fabric to v9e, discards the volatile drop-in, then starts and probes RC1.3
on v9h. Stage files and logs stay available for review.

Build with `python scripts/v2/package_rc14.py --source SOURCE_CHECKOUT`. Use
[the pilot runbook](../../experiments/v9i/pilot/PILOT.md) for the local dry run,
operator commands, evidence collection, and rollback.
