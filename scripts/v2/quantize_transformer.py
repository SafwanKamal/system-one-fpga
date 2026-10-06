"""How much accuracy does a fine-tuned small transformer lose at board bit widths?

    ../mlenv/bin/python scripts/v2/quantize_transformer.py --name bert-mini

Simulated (fake) quantisation of a model saved by finetune_transformer.py --save
(or distill_transformer.py):

  * every nn.Linear weight: symmetric, per output channel, ``--w-bits``
  * every nn.Linear input: symmetric, per tensor, ``--a-bits``, scale calibrated
    on 512 training sentences (99.99th percentile of |x|, so one outlier does not
    eat the range)
  * word / position embeddings: symmetric per dimension, ``--emb-bits``

Softmax, GELU and LayerNorm stay in float. On the FPGA they become integer
approximations (lookup tables / I-BERT style polynomials), which the literature
puts at a few tenths of a point; that is the part this script does not measure.

Writes results/transformers/<name>_quant.json with one entry per bit-width setting.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "v2"))

from finetune_transformer import Classifier, predict, score   # noqa: E402
from sysone.data import load_clinc150                          # noqa: E402
from sysone.train import fit_temperature                       # noqa: E402


def fq(x: torch.Tensor, bits: int, scale: torch.Tensor) -> torch.Tensor:
    q = (1 << (bits - 1)) - 1
    return torch.clamp(torch.round(x / scale), -q, q) * scale


def quantize_weights(model: nn.Module, w_bits: int, emb_bits: int) -> None:
    with torch.no_grad():
        for name, mod in model.named_modules():
            if isinstance(mod, nn.Linear):
                W = mod.weight
                s = W.abs().amax(1, keepdim=True).clamp(min=1e-8) / ((1 << (w_bits - 1)) - 1)
                W.copy_(fq(W, w_bits, s))
            elif isinstance(mod, nn.Embedding) and emb_bits < 32:
                E = mod.weight
                s = E.abs().amax(0, keepdim=True).clamp(min=1e-8) / ((1 << (emb_bits - 1)) - 1)
                E.copy_(fq(E, emb_bits, s))


class ActQuant:
    """Forward pre-hooks on every Linear: calibrate, then fake-quantise inputs."""

    def __init__(self, model: nn.Module, bits: int):
        self.bits, self.calib, self.stats, self.scales, self.handles = bits, True, {}, {}, []
        for name, mod in model.named_modules():
            if isinstance(mod, nn.Linear):
                self.handles.append(mod.register_forward_pre_hook(self._hook(name)))

    def _hook(self, name):
        def h(_mod, inputs):
            x = inputs[0]
            if self.calib:
                v = x.detach().abs().flatten()
                if v.numel() > 200_000:
                    v = v[torch.randint(0, v.numel(), (200_000,))]
                self.stats.setdefault(name, []).append(torch.quantile(v.float(), 0.9999).item())
                return None
            return (fq(x, self.bits, self.scales[name]),)
        return h

    def finish(self):
        q = (1 << (self.bits - 1)) - 1
        self.scales = {k: torch.tensor(max(np.max(v), 1e-8) / q) for k, v in self.stats.items()}
        self.calib = False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="export/transformers/<name>/ from --save")
    ap.add_argument("--settings", nargs="+", default=["32,32,32", "8,32,8", "8,8,8", "8,8,4", "4,8,4"],
                    help="w_bits,a_bits,emb_bits (32 = float)")
    ap.add_argument("--max-len", type=int, default=48)
    ap.add_argument("--threads", type=int, default=2)
    args = ap.parse_args()

    from transformers import AutoConfig, AutoModel, AutoTokenizer

    torch.set_num_threads(args.threads)
    d = ROOT / "export" / "v2" / "transformers" / args.name
    ds = load_clinc150()
    tok = AutoTokenizer.from_pretrained(d)
    results = []
    for setting in args.settings:
        w_bits, a_bits, emb_bits = (int(v) for v in setting.split(","))
        enc = AutoModel.from_config(AutoConfig.from_pretrained(d))
        model = Classifier(enc, ds.n_classes)
        model.load_state_dict(torch.load(d / "classifier.pt"))
        model.eval()
        if w_bits < 32:
            quantize_weights(model, w_bits, emb_bits)
        aq = None
        if a_bits < 32:
            aq = ActQuant(model, a_bits)
            predict(model, tok, ds.train.texts[::30][:512], args.max_len)
            aq.finish()
        lv = predict(model, tok, ds.val.texts, args.max_len)
        lt = predict(model, tok, ds.test.texts, args.max_len)
        T = fit_temperature(lv, ds.val.y)
        r = score(lv, lt, ds, T)
        r["setting"] = {"w_bits": w_bits, "a_bits": a_bits, "emb_bits": emb_bits}
        results.append(r)
        a, t = r["argmax"], r["tau_rule"]
        print(f"{args.name} w{w_bits} a{a_bits} emb{emb_bits}: in-scope {a['in_scope_accuracy']:.4f} "
              f"ECE {a['ece_equal_width']:.4f} | tau: in-scope {t['in_scope_accuracy']:.4f} "
              f"OOS {t['oos_recall']:.4f} combined {t['combined_accuracy']:.4f}", flush=True)
    out = ROOT / "results" / "v2" / "transformers" / f"{args.name}_quant.json"
    out.write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
