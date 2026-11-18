"""Offline wiring test: SpecSession (all modes) vs the RC1 package Session on a fake engine/vocab."""
import json, sys, types
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.modules.setdefault('fcntl', types.ModuleType('fcntl'))
import spec_service, test_spec_decode as T  # noqa: E402

PKG = HERE.parents[1] / 'build/v2/hardware-consolidated-rc1/deployment-r2'
TEXT = '```json\n["read_linux_file","/proc/uptime"]\n'


class Eng(T.Fake):
    def __init__(self):
        super().__init__(vocab=len(TEXT) + 2, seed=5)
        self.manifest = dict(eos_ids=[len(TEXT) + 1]); self.prefix_identity = dict(x=1)
        self.scratch = bytearray(0x100); self.command_timing = {}; self.clock_hz = 1; self.memory_clock_hz = 2
        for k in ('commands', 'layers', 'tokens', 'head_rows', 'prefill_groups', 'prefill_tokens', 'layer_weight_passes'):
            setattr(self, k, 0)
        self.pending_prefix = None

    def nxt(self, pos):  # emit TEXT one char per token, independent of prompt
        L = pos + 1 - self.plen
        return L if 0 <= L < len(TEXT) else len(TEXT) + 1

    def prefill_batch(self, ids, position, logits=False):
        self.prefill_tokens += len(ids)
        return super().prefill_batch(ids, position, logits)

    def begin_prefix(self, ids, enabled=True):
        self.pending_prefix = dict(identity=self.prefix_identity, tag=bytes(self.scratch[0x80:0xa0]).hex(), prompt_ids=ids)


class Vocab:
    def encode_text(self, s): return [0] * (len(s) % 50 + 20)
    def piece(self, t): return TEXT[t].encode() if t < len(TEXT) else b''
    def close(self): pass


def run(cls_or_session, eng):
    req = dict(op='generate', query='Read /proc/uptime', max_tokens=64)
    return cls_or_session.generate(req)


svc, script = spec_service.load_package(PKG)
results = {}
for mode in ('rc1', 'off', 'adaptive', 'always'):
    eng = Eng(); eng.plen = len(Vocab().encode_text(svc.prompt_for('Read /proc/uptime')))
    args = (eng, Vocab(), lambda: {}, lambda: None, lambda s: (json.loads(s), dict(executed=True)))
    kw = dict(startup_proof=dict(resident_weights_verified=True, model_verify_ms=1.0, verified_bytes=1))
    cls = svc.Session if mode == 'rc1' else spec_service.make_session_class(svc, mode, 0.25)
    s = cls(*args, **kw)
    if mode != 'rc1':
        s.speculate = mode; s.drafter = spec_service.spec_decode.Drafter() if mode != 'off' else None
        s.gate = spec_service.spec_decode.Gate() if mode == 'adaptive' else None
    r = run(s, eng)
    results[mode] = (r['generated_ids'], r['generated_text'], r['complete'], r.get('finish_reason'), r.get('speculation', {}).get('passes'))
    print(mode, results[mode][1:])
assert all(results[m][:4] == results['rc1'][:4] for m in results), results
print('WIRING TEST PASSED')
