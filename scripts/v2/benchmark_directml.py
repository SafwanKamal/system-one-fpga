"""Short, isolated CPU/DirectML L12 training benchmark; never saves model weights."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time
import traceback

import torch
from torch.nn import functional as F
from transformers import AutoModel

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_chain import ChainModel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--report', required=True)
    ap.add_argument('--device', choices=['cpu', 'dml'], required=True)
    ap.add_argument('--steps', type=int, default=3)
    ap.add_argument('--length', type=int, default=32)
    args = ap.parse_args()
    torch.set_num_threads(os.cpu_count() or 1)
    torch.manual_seed(0)
    report = {'device': args.device, 'torch': torch.__version__,
              'batch': 32, 'length': args.length, 'measured_steps': args.steps,
              'scope': 'synthetic L12 encoder + AdamW training, then existing ChainModel compatibility; excludes teacher/tokenization'}
    try:
        if args.device == 'dml':
            import torch_directml
            device = torch_directml.device()
            report['adapter'] = torch_directml.device_name(0).rstrip('\0')
        else:
            device = torch.device('cpu')
        encoder = AutoModel.from_pretrained(args.model, local_files_only=True,
                                            attn_implementation='eager').to(device).train()
        ids_cpu = torch.randint(100, 10000, (32, args.length))
        ids = ids_cpu.to(device)
        att = torch.ones_like(ids)
        opt = torch.optim.AdamW(encoder.parameters(), lr=4e-5, foreach=False)
        times, losses = [], []
        for step in range(args.steps + 1):
            start = time.perf_counter()
            opt.zero_grad(set_to_none=True)
            h = encoder(input_ids=ids, attention_mask=att).last_hidden_state
            loss = h[..., 0].square().mean()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(encoder.parameters(), 1.0, foreach=False)
            opt.step()
            value = float(loss.detach().cpu())  # completes queued GPU work
            elapsed = time.perf_counter() - start
            print(f'{args.device} step {step}: {elapsed:.3f}s loss {value:.6f}', flush=True)
            if step:
                times.append(elapsed)
                losses.append(value)
        report.update(seconds=times, median_seconds=statistics.median(times), losses=losses,
                      encoder_training_passed=all(__import__('math').isfinite(x) for x in losses))
        opt.zero_grad(set_to_none=True)
        del opt
        # Exercise the actual pooling, intent, slot and embedding paths. Targets
        # explicitly follow logits onto the device, as a migrated trainer must do.
        model = ChainModel(encoder, {'clinc': 151}, {'atis': 127}, {}, embed_dim=384).to(device)
        items = [{'targets': [(0, 'clinc', i % 151, ('benchmark',))],
                  'slot_head': 'atis', 'pair': None, 'distill_only': []} for i in range(32)]
        batch = {'ids': ids, 'att': att, 'seg': torch.zeros_like(ids),
                 'tags': torch.zeros_like(ids), 'items': items}
        start = time.perf_counter()
        out = model(batch)
        terms = [F.cross_entropy(logit[None], torch.tensor([y], device=device))
                 for _, logit, y, *_ in out['intent']]
        terms += [4 * F.cross_entropy(logit, y) for _, logit, y, *_ in out['slots']]
        for head, e, y, _ in out['embed']:
            logits = 20 * F.normalize(e, dim=-1) @ F.normalize(model.proto[head], dim=-1).T
            terms.append(F.cross_entropy(logits[None], torch.tensor([y], device=device)))
        loss = torch.stack(terms).mean()
        loss.backward()
        report.update(chain_loss=float(loss.detach().cpu()),
                      chain_forward_backward_seconds=time.perf_counter()-start,
                      chain_compatibility_passed=True)
    except Exception as exc:
        report.update(error=f'{type(exc).__name__}: {exc}', traceback=traceback.format_exc())
        print(report['traceback'], flush=True)
    finally:
        Path(args.report).write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2), flush=True)
    return 0 if report.get('chain_compatibility_passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
