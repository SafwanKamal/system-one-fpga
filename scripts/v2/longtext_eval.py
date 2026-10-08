"""Long inputs: per-sentence accuracy when sentences are packed into 128-token chains.

    ../mlenv/bin/python scripts/v2/longtext_eval.py --image minilm-l6 --words 100 300 1000 --docs 4

Documents are built from CLINC150 test utterances (each a sentence with a known intent,
out-of-scope ones included, each ending in a full stop), of about N words each. Every
document goes through src/sysone/v2/longtext.py exactly as `sysone_v2_client.py doc`
does, but on ImageMachine (bit-exact with the board), and every sentence's decision
(CLINC head with the image's out-of-scope rule) is compared with
  1. the gold intent, and
  2. the same sentence encoded alone (one chain per sentence, the usual request).
Board time is estimated from the measured encoder clocks per chain length
(rtl/v2/README.md) - the encoder is not simulated cycle by cycle here.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "v2"))

from sysone.v2 import ddr_image as di                    # noqa: E402
from sysone.v2.chain_data import load_clinc              # noqa: E402
from sysone.v2.encoder_client import LocalEncoder        # noqa: E402
from sysone.v2.host_heads import Heads, build_chain, pack   # noqa: E402
from sysone.v2.wordpiece import WordPiece                # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default="minilm-l6")
    ap.add_argument("--words", type=int, nargs="+", default=[100, 300, 1000])
    ap.add_argument("--docs", type=int, default=4, help="documents per length")
    ap.add_argument("--max-segments", type=int, default=0, help="sentences per chain (0: as many as fit)")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    d = ROOT / "export" / "v2" / "image" / a.image
    image = (d / f"{a.image}.img").read_bytes()
    manifest = json.loads((d / "manifest.json").read_text())
    decision = json.loads((d / "decision.json").read_text()) if (d / "decision.json").exists() else None
    model = a.image.split("-t24")[0]
    wp = WordPiece.from_file(ROOT / "export" / "v2" / "chain" / model / "tokenizer.json")
    enc = LocalEncoder(image)
    heads = Heads(manifest, enc.machine, decision)
    splits, labels = load_clinc()
    pool = splits["test"]
    rng = random.Random(a.seed)
    alone_cache: dict[tuple, str] = {}

    def alone(words):
        k = tuple(words)
        if k not in alone_cache:
            ch = build_chain(wp, [words], "intent", 128)
            alone_cache[k] = heads.intent(enc.machine.hidden(np.asarray(ch.ids)), ch, "clinc", 0).labels[0]
        return alone_cache[k]

    # encoder clocks per chain length: bert-mini measured on the board; MiniLM-L6 from
    # the RTL simulation (1 token 11.5 ms, 128 tokens 8,767,175 clocks)
    points = ({1: 232870, 12: 291527, 64: 1441377, 128: 2951462} if "bert-mini" in a.image
              else {1: 862500, 128: 8767175})
    xs, ys = sorted(points), [points[k] for k in sorted(points)]

    def clocks_at(n):
        return float(np.interp(n, xs, ys))
    res = {"image": a.image, "max_segments": a.max_segments, "lengths": {}}
    for n_words in a.words:
        ok = same = total = ok_alone = 0
        chains = tokens = 0
        est_clocks = 0.0
        t0 = time.perf_counter()
        for _ in range(a.docs):
            sents, gold, w = [], [], 0
            while w < n_words:
                c = rng.choice(pool)
                words = list(c.segments[0].words)
                if not words[-1].endswith((".", "?", "!")):
                    words[-1] += "."
                words[0] = words[0][:1].upper() + words[0][1:]   # real text; the model is uncased
                sents.append(words)
                gold.append(labels[c.segments[0].intent])
                w += len(words)
            # the known sentences (the splitter itself is tested in tests/test_host_client.py;
            # CLINC utterances can hold an inner "?" that it would split on)
            chains_words = pack(wp, [" ".join(s) for s in sents], 128, a.max_segments or None)
            # map the packed units back to their sentences (a long sentence may be cut)
            owner, i, used = [], 0, 0
            for units in chains_words:
                for u in units:
                    owner.append(i)
                    used += len(u)
                    if used >= len(sents[i]):
                        i, used = i + 1, 0
            j = 0
            for units in chains_words:
                ch = build_chain(wp, units, "multi", 128)
                x = enc.machine.hidden(np.asarray(ch.ids))
                chains += 1
                tokens += len(ch.ids)
                est_clocks += clocks_at(len(ch.ids))
                for k in range(len(units)):
                    si = owner[j]
                    j += 1
                    if k not in ch.word_rows or not ch.word_rows[k]:
                        continue
                    pred = heads.intent(x, ch, "clinc", k).labels[0]
                    g, al = gold[si], alone(sents[si])
                    total += 1
                    ok += int(pred == g)
                    ok_alone += int(al == g)
                    same += int(pred == al)
        est_ms = est_clocks / 75e6 * 1e3 / a.docs
        r = {"documents": a.docs, "sentences": total, "chains_per_doc": chains / a.docs,
             "tokens_per_doc": tokens / a.docs,
             "accuracy_packed": ok / total, "accuracy_alone": ok_alone / total,
             "agreement_packed_vs_alone": same / total,
             "board_ms_per_doc_estimate": est_ms, "numpy_seconds": time.perf_counter() - t0}
        res["lengths"][str(n_words)] = r
        print(f"{n_words:5d} words: {total} sentences, {r['chains_per_doc']:.1f} chains and "
              f"{r['tokens_per_doc']:.0f} tokens per document; accuracy packed {r['accuracy_packed']:.3f} "
              f"vs alone {r['accuracy_alone']:.3f} (same decision {r['agreement_packed_vs_alone']:.3f}); "
              f"board ~{est_ms:.0f} ms per document (estimate from clocks per token)", flush=True)
    out = ROOT / "results" / "v2" / "chain" / f"longtext_{a.image}_seg{a.max_segments}.json"
    out.write_text(json.dumps(res, indent=1))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
