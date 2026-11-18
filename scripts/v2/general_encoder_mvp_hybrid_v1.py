"""Explicit FPGA proposal + local FP32 argument correction for the MVP.

This does not qualify INT8 argument accuracy. Nothing dispatches external tools.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def correct_arguments(physical_calls, float_calls):
    # A host argument check must not silently invent/remove/reorder FPGA calls.
    if [c['name'] for c in physical_calls] != [c['name'] for c in float_calls]:
        raise ValueError('FPGA/FP32 call selection disagreement; no proposal')
    corrections = []
    for slot, (physical, checked) in enumerate(zip(physical_calls, float_calls)):
        for key in sorted(set(physical['arguments']) | set(checked['arguments'])):
            before = physical['arguments'].get(key)
            after = checked['arguments'].get(key)
            if (key in physical['arguments']) != (key in checked['arguments']) or type(before) is not type(after) or before != after:
                corrections.append(dict(call=slot, argument=key,
                    fpga_present=key in physical['arguments'], fpga_value=before,
                    host_present=key in checked['arguments'], host_value=after))
    return float_calls, corrections


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--request', type=Path, required=True)
    ap.add_argument('--physical', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--bundle', type=Path, default=ROOT / 'build/v2/general-tool-encoder-mvp-v1')
    args = ap.parse_args()
    started = time.monotonic()
    import numpy as np
    import torch
    from tokenizers import Tokenizer
    from sysone.v2.general_tool_encoder import ToolEncoder
    from sysone.v2.general_tools import validate_calls
    from sysone.v2.general_schema_annotations import adapt_tool
    torch.set_num_threads(2)
    request_bytes = args.request.read_bytes()
    request = json.loads(request_bytes)
    physical = json.loads(args.physical.read_text(encoding='utf-8-sig'))
    request_sha = hashlib.sha256(request_bytes).hexdigest()
    if physical.get('request_sha256') != request_sha:
        raise ValueError('physical receipt not bound to this request')
    if not all(physical.get(k) is True for k in ['board_executed', 'r5_controls_pl', 'r5_computes_logits']):
        raise ValueError('physical R5/FPGA receipt required')
    candidate = json.loads((args.bundle / 'candidate.json').read_text())
    if physical.get('image_sha256') != candidate['image_sha256'] or physical.get('r5_elf_sha256') != candidate['r5_elf_sha256']:
        raise ValueError('wrong physical model/firmware')
    parent = ROOT / 'build/v2/general-tool-expanded-training-v4/encoder'
    checkpoint = parent / 'best.pt'
    checkpoint_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if checkpoint_sha != candidate['parent_checkpoint_sha256']:
        raise ValueError('FP32 verifier checkpoint changed')
    run = json.loads((parent / 'run.json').read_text())
    model = ToolEncoder(run['arguments']['model'], 4)
    model.load_state_dict(torch.load(checkpoint, map_location='cpu', weights_only=False)['trainable_state'], strict=False)
    model.eval()
    class FloatBackend:
        passes = 0
        def predict(self, ids, types):
            self.passes += 1
            tokens = dict(input_ids=torch.tensor([ids]), token_type_ids=torch.tensor([types]),
                          attention_mask=torch.ones((1, len(ids)), dtype=torch.long))
            with torch.inference_mode():
                count, kind, span = model(tokens)
            return np.concatenate([count[0].numpy(), kind[0].numpy()]), span[0].numpy()
    client = load_module('mvp_client', ROOT / 'scripts/v2/general_encoder_mvp_client_v1.py')
    helpers = load_module('mvp_helpers', args.bundle / 'runtime/helpers.py')
    tok = Tokenizer.from_file(str(args.bundle / 'runtime/tokenizer.json'))
    tok.no_truncation(); tok.no_padding()
    backend = FloatBackend()
    checked = client.infer(request['query'], request['tools'], tok, backend, helpers)
    tools = [adapt_tool(t) for t in request['tools']]
    validate_calls(physical['calls'], tools); validate_calls(checked, tools)
    calls, corrections = correct_arguments(physical['calls'], checked)
    result = dict(outcome='proposal' if calls else 'no_calls', calls=calls,
        backend='R5_controlled_FPGA_with_explicit_host_FP32_argument_check',
        physical_evidence_mode=physical.get('evidence_mode', 'live_board_smoke'),
        request_sha256=request_sha, physical_calls=physical['calls'], argument_corrections=corrections,
        fpga_encoder_passes=physical['encoder_passes'], host_encoder_passes=backend.passes,
        host_checkpoint_sha256=checkpoint_sha, host_elapsed_ms=(time.monotonic()-started)*1000,
        tools_executed=False, int8_argument_accuracy_fixed=False, terminal_by_D_qualified=False)
    args.out.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
