# Experimental counter300 successor

See [implementation and evidence](../../../../docs/research/2026-10-15-counter300-implementation.md).
This sealed successor adds a one-cycle diagnostic telemetry input cut to the
previous isolated locality300 design. Encoder computation and AXI control are
unchanged. MMIO 0x70 exposes pending/final snapshot readiness. Existing drivers
intentionally reject this new feature family; there is no deployment package.

Preserve the parent, qualified sources/packages/recovery and all rejected runs.
Do not modify sources during an active build. The manifest covers all 25 RTL
files; this README is outside the RTL seal. Tool success is not timing closure.
