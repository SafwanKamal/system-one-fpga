"""RC1 service with optional lossless speculative decoding. The sealed RC1 package is used unchanged.

Run as root on the board, with the RC1 service stopped (it owns the inference lock):
  python3 spec_service.py serve --package PKG --socket S --ready R --speculate {off,adaptive,always}
Requests use the RC1 client unchanged:
  python3 PKG/scripts/v2/qwen_arm_service_candidate.py request --socket S --query ...
Generation semantics (typed-JSON stop, EOS refusal, prefix reuse, verification,
fault handling, tool execution) are copied from the RC1 Session.generate; only
the decode loop differs. `--speculate off` is the reference path.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import spec_decode  # noqa: E402


def load_package(package):
    sys.path.insert(0, str(Path(package) / 'src'))
    from sysone.v2 import qwen_arm_service_candidate as svc
    spec = importlib.util.spec_from_file_location('rc1_service_script', Path(package) / 'scripts/v2/qwen_arm_service_candidate.py')
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    return svc, script


def make_session_class(svc, mode, gate_threshold):
    class SpecSession(svc.Session):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.speculate = mode
            self.drafter = spec_decode.Drafter() if mode != 'off' else None
            self.gate = spec_decode.Gate(threshold=gate_threshold) if mode == 'adaptive' else None

        def generate(self, request):
            svc.validate_request(request)
            if request['op'] != 'generate':
                raise ValueError('Generation operation required')
            if self.state != 'READY':
                raise RuntimeError('Session is ' + self.state)
            started = time.monotonic()
            ids = self.vocab.encode_text(svc.prompt_for(request['query']))
            n = request.get('max_tokens', 64)
            if not ids or len(ids) + n > self.engine.context:
                raise ValueError('Prompt plus output exceeds FPGA context')
            tokenization = time.monotonic() - started
            e = self.engine
            before = {k: getattr(e, k) for k in svc.COUNTERS}
            timings = {k: dict(v) for k, v in e.command_timing.items()}
            result = dict(complete=False, query=request['query'], prompt_ids=ids,
                          generated_ids=[], prefix_tokens_reused=0,
                          ARM_model_inference=False, host_model_inference=False,
                          tools_executed=False, tokenization_seconds=tokenization,
                          prefill_batch_size=e.prefill_batch_size, speculate=self.speculate)
            self.state = 'BUSY'
            try:
                self.identity()
                result.update(verification_mode=self.verification,
                              startup_model_verify_ms=self.startup_proof['model_verify_ms'],
                              startup_verified_bytes=self.startup_proof['verified_bytes'],
                              model_verify_ms=0.0, verified_bytes=0,
                              resident_weights_verified=True, request_weights_hashed=False)
                if self.verification == 'per-request':
                    result.update(self.verify())
                    result['request_weights_hashed'] = True
                self.identity()
                conversation = request.get('conversation_id', 'default')
                if conversation != self.conversation or request.get('reset_cache', False):
                    self.cache.reset()
                self.conversation = conversation
                reused = self.cache.begin(e, ids, enabled=self.prefix_cache)
                result['prefix_tokens_reused'] = reused
                tick = time.monotonic()
                for pos in range(reused, len(ids), e.prefill_batch_size):
                    group = ids[pos:pos + e.prefill_batch_size]
                    token = e.prefill_batch(group, pos, logits=pos + len(group) == len(ids))
                result['prefill_seconds'] = time.monotonic() - tick
                prefill_tokens = e.prefill_tokens - before['prefill_tokens']
                eos = set(e.manifest['eos_ids'])
                state = dict(raw=b'', value=None, eos=False)

                def stop(tokens):
                    # Same per-token rule as RC1: typed value completes -> stop; EOS first -> refuse.
                    state['raw'] += self.vocab.piece(tokens[-1])
                    state['value'] = svc.typed_value(state['raw'])
                    if state['value'] is not None:
                        result['finish_reason'] = 'typed_json_complete'
                        return True
                    if tokens[-1] in eos:
                        state['eos'] = True
                        return True
                    return False

                tick = time.monotonic()
                out, _, stats = spec_decode.decode(e, ids, token, n, stop, drafter=self.drafter, gate=self.gate)
                result['decode_seconds'] = time.monotonic() - tick
                result['generated_ids'] = out
                result['speculation'] = stats
                if state['eos']:
                    raise RuntimeError('EOS without a complete typed call')
                if state['value'] is None:
                    raise RuntimeError('Output truncated; no tool executed')
                if self.drafter is not None:
                    self.drafter.add(out)
                self.identity()
                if prefill_tokens != len(ids) - reused:
                    raise RuntimeError('Physical prefill work does not match cache reuse')
                self.cache.commit(e, ids)
                tick = time.monotonic()
                value = state['value']
                call, tool = self.execute(json.dumps(dict(name=value[0], arguments=dict(path=value[1]))))
                result.update(complete=True, generated_text=state['raw'].decode('utf-8'),
                              call=call, tool_result=tool, tools_executed=True,
                              tool_seconds=time.monotonic() - tick,
                              clock_hz=e.clock_hz, memory_clock_hz=e.memory_clock_hz)
                self.state = 'READY'
            except BaseException:
                self.cache.reset()
                self.state = 'FAULTED'
                raise
            finally:
                result['work'] = {k: getattr(e, k) - v for k, v in before.items()}
                result['command_timing'] = {
                    k: {f: v[f] - timings.get(k, {}).get(f, 0) for f in ('calls', 'seconds')}
                    for k, v in e.command_timing.items()}
                result['elapsed_seconds'] = time.monotonic() - started
                self.last_result = result
            return result
    return SpecSession


def factory_for(svc, mode, gate_threshold):
    cls = make_session_class(svc, mode, gate_threshold)

    def factory(package, *, verification='startup', prefix_cache=True):
        base = svc.hardware_session(package, verification=verification, prefix_cache=prefix_cache)
        # Re-wrap the fully verified session's parts in the subclass; no second hardware open.
        s = cls.__new__(cls)
        s.__dict__.update(base.__dict__)
        s.speculate = mode
        s.drafter = spec_decode.Drafter() if mode != 'off' else None
        s.gate = spec_decode.Gate(threshold=gate_threshold) if mode == 'adaptive' else None
        return s
    return factory


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='mode', required=True)
    s = sub.add_parser('serve')
    s.add_argument('--package', type=Path, required=True)
    s.add_argument('--socket', type=Path, required=True)
    s.add_argument('--ready', type=Path, required=True)
    s.add_argument('--speculate', choices=['off', 'adaptive', 'always'], default='adaptive')
    s.add_argument('--gate-threshold', type=float, default=0.25)
    s.add_argument('--no-prefix-cache', action='store_true')
    a = ap.parse_args()
    svc, script = load_package(a.package)
    script.serve(a.package, a.socket, a.ready, factory=factory_for(svc, a.speculate, a.gate_threshold),
                 prefix_cache=not a.no_prefix_cache)


if __name__ == '__main__':
    main()
