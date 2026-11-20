"""Predict v9g (v9f + P=4 attention) board timings from the v9f board pilot record.

The attention core costs 8 * (16 + 37 * ceil(k/P)) cycles per cached row per layer for a pass
of k tokens at 125 MHz (docs/research/2026-11-19-core-feasibility.md). Going from P=2 to P=4
saves 8 * 37 * (ceil(k/2) - ceil(k/4)) cycles per row per layer and leaves everything else
unchanged:
- k=1 single steps save nothing;
- prefill groups of 8 save 592 cycles (4.74 us) per row per layer.

Prefill (groups of 8 from position 0, causal rows = group start + group size) is exact in k.
Verify passes are approximated with the per-case mean pass size (1 + drafted/passes) at the
mean row count (prompt + generated/2), because per-pass sizes are not recorded.

usage: python predict_pilot.py v9f-pilot.json out.json
"""
import json, math, sys

CLK, LAYERS, GROUP = 125e6, 28, 8


def saved_cycles(k):
    return 8 * 37 * (math.ceil(k / 2) - math.ceil(k / 4))


def saved_frac(k):
    # fractional k: interpolate between the neighbouring integer pass sizes
    lo = math.floor(k); hi = lo + 1
    return saved_cycles(lo) + (k - lo) * (saved_cycles(hi) - saved_cycles(lo))


p = json.load(open(sys.argv[1]))
tot = dict(v9f_prefill=0.0, v9g_prefill=0.0, v9f_batched=0.0, v9g_batched=0.0, v9f_ar=0.0)
for c in p['cases']:
    n = c['prompt_tokens']
    save_pf = sum(saved_cycles(min(GROUP, n - s)) * (s + min(GROUP, n - s)) for s in range(0, n, GROUP)) * LAYERS / CLK
    b = c['batched']
    save_dec = 0.0
    if b['passes']:
        k = 1 + b['drafted'] / b['passes']
        rows = n + c['generated'] / 2
        save_dec = b['passes'] * saved_frac(k) * rows * LAYERS / CLK
    tot['v9f_prefill'] += c['prefill_seconds']; tot['v9g_prefill'] += c['prefill_seconds'] - save_pf
    tot['v9f_batched'] += b['decode_seconds']; tot['v9g_batched'] += b['decode_seconds'] - save_dec
    tot['v9f_ar'] += c['ar']['decode_seconds']
out = {k: round(v, 1) for k, v in tot.items()}
out.update(prefill_speedup=round(tot['v9f_prefill'] / tot['v9g_prefill'], 3),
           batched_decode_speedup=round(tot['v9f_batched'] / tot['v9g_batched'], 3),
           end_to_end_speedup=round((tot['v9f_prefill'] + tot['v9f_batched']) / (tot['v9g_prefill'] + tot['v9g_batched']), 3),
           single_step_change='none (k=1)', cases=len(p['cases']), source_boot=p.get('boot_id'))
json.dump(out, open(sys.argv[2], 'w'), indent=1)
print(json.dumps(out, indent=1))
