"""Extract one immutable, bounded head profile from the existing model image."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from sysone.v2.ddr_image import ImageMachine

IMAGE_SHA = '4129baded344729ccc7ef6a3f0a2b34799280a91d88173ae1c0b197cdef8c3bb'


def main():
    source = ROOT / 'export/v2/image/minilm-l12-v1-kr260'
    image = (source / 'minilm-l12-v1-kr260.img').read_bytes()
    if hashlib.sha256(image).hexdigest() != IMAGE_SHA:
        raise ValueError('Unexpected model image')
    manifest = json.loads((source / 'manifest.json').read_text())
    machine = ImageMachine(image)
    hd = machine.heads['intent.atis']
    w, b, _ = machine._stream(hd['stream'], 384, 18, 16, 32)
    scale = machine.mem.array(hd['scales'], 18, '<f4').astype(np.float64)
    recip = machine.mem.array(hd['recip'], 129, '<u4')
    labels = next(h['labels'] for h in manifest['heads']
                  if h['kind'] == 'intent' and h['name'] == 'atis')
    assert len(labels) == 18 and np.all(np.isfinite(scale)) and np.all(scale > 0)
    # A reciprocal may round a -128..127 input mean by at most one code.
    # Use the conservative |pooled|<=129 bound rather than observed activations.
    bound = 129 * np.abs(w.astype(np.int64)).sum(0) + np.abs(b.astype(np.int64))
    assert int(bound.max()) < 2**31
    spec = {
        'abi': 'sysone.typed.intent.atis.v1', 'head': 'intent.atis',
        'image_sha256': IMAGE_SHA, 'hidden': 384, 'max_tokens': 128,
        'labels': labels, 'input': 'INT8 row-major hidden codes; sorted unique selected segment rows',
        'pool': 'floor((sum(selected rows)*image_recip[count]+32768)/65536)',
        'logits': 'exact integer dot plus bias; signed 32-bit output, signed 64-bit accumulation',
        'decision': 'binary64(logit)*binary64(image_float32_scale); first maximum wins',
        'confidence': None, 'oos_rejection': False,
        'floating_environment': 'IEEE binary64 round-to-nearest ties-to-even; no fast-math/FMA',
        'failure_payload': 'label=0; reserved_score=0; only Accepted carries a label',
        'identity': 'fresh nonzero boot session + strictly increasing nonzero uint64 request ID + contract SHA256',
        'deadline': 'positive uint32 PL cycles; admission edge age=0; terminal by edge D; matching proposal at D wins',
        'guarantee_scope': 'stable local terminal record; reset/clock failure and external delivery excluded',
        'success_prerequisites': ['verified model/head deployment', 'complete successful encoder',
                                  'live AXI/FIFO quiescence', 'trusted bounded head/bridge',
                                  'matching session/request/profile'],
        'max_abs_logit_bound': int(bound.max()),
        'deployment_certificate': 'separate binding of contract, firmware, bitstream, environment and fresh boot session',
    }
    canonical = json.dumps(spec, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
    contract = hashlib.sha256(canonical).hexdigest()
    out = ROOT / 'firmware/typed_intent/generated'
    if out.exists():
        raise FileExistsError('Preserve frozen profile; use a new version for any change')
    out.mkdir(parents=True)
    (out / 'contract.json').write_text(json.dumps({'contract_sha256': contract, 'spec': spec}, indent=2)+'\n')
    def array(name, typ, values):
        return f'static const {typ} {name}[{len(values)}] = {{\n' + ',\n'.join(
            '    '+', '.join(str(x) for x in values[i:i+18]) for i in range(0,len(values),18)) + '\n};\n'
    text = '/* Generated from the hash-verified image. Do not edit. */\n'
    text += f'#define TI_CONTRACT_HEX "{contract}"\n'
    text += array('ti_contract_bytes', 'uint8_t', list(bytes.fromhex(contract)))
    text += array('ti_weights', 'int8_t', w.astype(np.int8).ravel().tolist())
    text += array('ti_bias', 'int32_t', b.astype(np.int32).tolist())
    text += array('ti_recip', 'uint32_t', recip.tolist())
    text += array('ti_scale', 'double', [float(x).hex() for x in scale])
    (out / 'profile.inc').write_text(text)
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}
    (out / 'manifest.json').write_text(json.dumps({'image_sha256': IMAGE_SHA, 'files': hashes},indent=2)+'\n')
    print(contract)


if __name__ == '__main__':
    main()
