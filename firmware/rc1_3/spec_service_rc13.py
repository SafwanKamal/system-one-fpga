"""RC1.3 service: RC1 on the v9h image with batched-head verification and the cost-aware drafter.

Run as root on the board by sysone-rc1.service (drop-in 20-rc13.conf), after rc13_image.py up:
  python3 spec_service_rc13.py serve --package PKG --socket S --ready R
PKG is the RC1 package plus the v9h app directory, with the v9h registers.json (scratch at 0x7c). The RC1 runtime is imported with two
strings changed (app name and overlay compatible), as in the v9h board pilots. Generation
semantics are those of firmware/rc1_spec/spec_service.py (copied from RC1 Session.generate);
only the decode loop differs. Every emitted token is the engine's greedy token: bit-identical
to plain RC1 (v9h board pilot 37/37 in plain and speculative modes). Draft lengths use the
7-coefficient v9h cost model (passes of <= 4 tokens run on both weight ports).
"""
import argparse, importlib.util, json, sys, time, types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import spec_decode  # noqa: E402  (experiments/spec_service/spec_decode.py, with batched_head)
from drafters import VoteDrafter, CostAwareDrafter  # noqa: E402

SWAPS = [("APP='sysone-qwen-decoder-v9e'", "APP='sysone-qwen-decoder-v9h'"),
         ("b'xlnx,qwen-decoder-v9e-1.0'", "b'xlnx,qwen-decoder-v9h-1.0'")]


def load_package(package):
    sys.path.insert(0, str(Path(package) / 'src'))
    import sysone.v2
    name = 'sysone.v2.qwen_fpga_runtime_candidate'
    path = Path(package) / 'src/sysone/v2/qwen_fpga_runtime_candidate.py'
    src = path.read_text()
    for old, new in SWAPS:
        if src.count(old) != 1:
            raise RuntimeError('Unexpected runtime source: ' + old)
        src = src.replace(old, new)
    rt = types.ModuleType(name); rt.__package__ = 'sysone.v2'; rt.__file__ = str(path)
    sys.modules[name] = rt; sysone.v2.qwen_fpga_runtime_candidate = rt
    exec(compile(src, str(path), 'exec'), rt.__dict__)
    from sysone.v2 import qwen_arm_service_candidate as svc
    spec = importlib.util.spec_from_file_location('rc1_service_script', Path(package) / 'scripts/v2/qwen_arm_service_candidate.py')
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    return svc, script, rt


def make_session_class(svc, rt):
    class Rc13Session(svc.Session):
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
                          prefill_batch_size=e.prefill_batch_size, speculate='rc1.3-costaware', image='v9h')
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
                if request.get('reset_cache', False):
                    self.cache.reset()
                elif conversation != self.conversation:
                    # Shared system template: keep only the public template tokens (identical K/V
                    # rows at identical positions and group boundaries); never another
                    # conversation's user text.
                    if self.cache.ids[:len(self.template)] == self.template:
                        self.cache.ids = list(self.template)
                    else:
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
                self.drafter.begin(ids)
                out, _, stats = spec_decode.decode(e, ids, token, n, stop, drafter=self.drafter, gate=None, batched=self.batched)
                result['decode_seconds'] = time.monotonic() - tick
                result['generated_ids'] = out
                result['speculation'] = stats
                if state['eos']:
                    raise RuntimeError('EOS without a complete typed call')
                if state['value'] is None:
                    raise RuntimeError('Output truncated; no tool executed')
                self.drafter.feed(dict(ids=ids), out)
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
    return Rc13Session


def template_ids(svc, vocab):
    """Token ids of the fixed system template that starts every prompt: the common prefix of
    prompts built from unrelated queries (39 tokens for the RC1 template)."""
    probes = [vocab.encode_text(svc.prompt_for(q)) for q in ('Read /proc/version', '0', 'x y', '{"a":1}', '\n')]
    n = 0
    while all(len(p) > n and p[n] == probes[0][n] for p in probes):
        n += 1
    return probes[0][:n]


def factory_for(svc, rt, coef):
    cls = make_session_class(svc, rt)

    def factory(package, *, verification='startup', prefix_cache=True):
        if rt.active_firmware() != 'sysone-qwen-decoder-v9h.bit.bin':
            raise RuntimeError('RC1.3 requires the v9h image (rc13_image.py up)')
        base = svc.hardware_session(package, verification=verification, prefix_cache=prefix_cache)
        s = cls.__new__(cls)
        s.__dict__.update(base.__dict__)
        s.drafter = CostAwareDrafter(VoteDrafter(prompts=True, ns=(6, 4, 3, 2, 1)), coef, prior=0.5, prior_w=2.0, P=4)
        s.batched = spec_decode.batched_head(s.engine, rt.OUTPUT)
        s.template = template_ids(svc, s.vocab)
        return s
    return factory


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='mode', required=True)
    s = sub.add_parser('serve')
    s.add_argument('--package', type=Path, required=True)
    s.add_argument('--socket', type=Path, required=True)
    s.add_argument('--ready', type=Path, required=True)
    s.add_argument('--no-prefix-cache', action='store_true')
    a = ap.parse_args()
    coef = json.loads((HERE / 'config.json').read_text())['coef_v9h']
    svc, script, rt = load_package(a.package)
    script.serve(a.package, a.socket, a.ready, factory=factory_for(svc, rt, coef), prefix_cache=not a.no_prefix_cache)


if __name__ == '__main__':
    main()
