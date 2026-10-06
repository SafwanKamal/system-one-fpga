"""Which exported model the board is built from: the one place that says so.

memory/*.mem, rtl/model_parameters.svh, the simulation vectors, the Ethernet test
vectors and the host client's bit-exact check must all come from the same export.
rtl_pack.py, ethernet_vectors.py, rtl_metrics.py, oos_tradeoff.py and
sysone_ethernet_client.py all default to DEPLOYED_EXPORT, so switching the board
to another model is: change this line, run `make vectors` (repacks memory/),
rebuild the bitstream.

The out-of-scope threshold belongs to the model (it is tuned on that model's
validation probabilities), so it lives next to it in <export>/decision.json;
DEFAULT_OOS_THRESHOLD is only the fallback for exports that predate that file.

History:
  export/student_bram_max      0.9071 in-scope, tau 0.32 -> combined 0.8678 (board 2026-10-03)
  export/student_kd_roberta    distilled from fine-tuned RoBERTa-base on MLM-augmented
                               CLINC150 (scripts/distill_board.py): 0.9231 in-scope,
                               tau 0.395 -> combined 0.8829. Same RTL.
  export/student_kd15_roberta  the same with 15 augmented copies per sentence instead of 5
                               (241,600 teacher-labelled sentences): 0.9309 in-scope,
                               tau 0.38 -> in-scope 0.9222, OOS 0.750, combined 0.8909.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOYED_EXPORT = ROOT / "export" / "student_kd15_roberta"
DEFAULT_OOS_THRESHOLD = 0.32


def oos_threshold(export_dir: Path | str = DEPLOYED_EXPORT) -> float:
    f = Path(export_dir) / "decision.json"
    if f.exists():
        return float(json.loads(f.read_text())["oos_threshold"])
    return DEFAULT_OOS_THRESHOLD
