# Attention LUT reclaim (v9h)

Exact-by-construction restructurings of v9h's `attention()` to free LUTs for the full dual weight
port. Write-up: `docs/research/2026-11-21-attention-reclaim.md`.

Run everything with the source checkout mapped as `S:` (`subst S: <checkout>`), because Vitis
breaks on the OneDrive path with spaces. Run one Vitis job at a time.

| File | Purpose |
|---|---|
| `make_attn.py SRC OUT VARIANT[+VARIANT]` | Derives a variant source directory from v9h (`build/v2/dual-port-study/src-s2`) using exact-count patches. Variants: `base`, `p2`, `aux`, `lim`, `bram`, `tmx`. |
| `hls_attn.py NAME SRC` | Runs csynth and writes `build/v2/attn-reclaim/claude/hls-NAME/summary.json`, with the attention breakdown (categories, FP operator counts, and per-loop II, iteration latency and trip count). |
| `model_p2.py` | Replays all 181 cases with the v9h board cost fit, split into port-split and attention-P terms. Writes `build/v2/attn-reclaim/claude/model_p2.json`. |
| `audit/` | Gemini's C-sim exactness harness (see its README). |

```sh
python experiments/attn_reclaim/make_attn.py S:/build/v2/dual-port-study/src-s2 S:/build/v2/attn-reclaim/claude/src-p2 p2
python experiments/attn_reclaim/hls_attn.py p2 S:/build/v2/attn-reclaim/claude/src-p2
SYS_ROOT=S:/ python experiments/attn_reclaim/model_p2.py
```
