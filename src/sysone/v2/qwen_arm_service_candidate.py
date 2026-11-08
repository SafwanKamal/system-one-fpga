"""Consolidated RC1 service: sealed ownership, startup/transition SHA and optional prefix reuse.

Prefix metadata lives on ARM; neural arithmetic and completion policy are unchanged.
Hardware imports are lazy so lifecycle tests can run without Linux/FPGA.
"""
import json
from pathlib import Path
import time

SYSTEM = 'Tool: read_linux_file(path:string). Reply only with a compact JSON array ["read_linux_file","path"]. Copy the requested path exactly. No Markdown.'
COUNTERS = ('commands', 'layers', 'tokens', 'head_rows', 'prefill_groups',
            'prefill_tokens', 'layer_weight_passes')


def prompt_for(query):
    return '<|im_start|>system\n'+SYSTEM+'<|im_end|>\n<|im_start|>user\n'+query+'<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'


def typed_value(raw):
    try:
        text = raw.decode('utf-8').strip()
    except UnicodeDecodeError:
        return None
    for prefix in ('```json\n', '```\n'):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    try:
        value = json.loads(text)
    except ValueError:
        return None
    if type(value) is not list or len(value) != 2 or any(type(v) is not str for v in value):
        raise ValueError('Generated value does not match the two-string tool-call type')
    return value


def validate_request(request):
    if type(request) is not dict or set(request) - {'op', 'query', 'max_tokens', 'conversation_id', 'reset_cache'}:
        raise ValueError('Unknown request fields')
    if request.get('op') not in ('generate', 'health', 'shutdown', 'reset-cache'):
        raise ValueError('Unknown operation')
    if request['op'] != 'generate':
        if set(request) != {'op'}:
            raise ValueError('Control operation has extra fields')
        return
    if type(request.get('query')) is not str or not 1 <= len(request['query']) <= 16384:
        raise ValueError('Query must contain 1..16384 characters')
    conversation = request.get('conversation_id', 'default')
    if type(conversation) is not str or not 1 <= len(conversation) <= 128:
        raise ValueError('Invalid conversation identity')
    if type(request.get('reset_cache', False)) is not bool:
        raise ValueError('reset_cache must be boolean')
    n = request.get('max_tokens', 64)
    if type(n) is not int or not 1 <= n <= 128:
        raise ValueError('Output profile')


class Session:
    def __init__(self, engine, vocab, verify, identity, execute, *, verification="startup",
                 prefix_cache=True, startup_proof=None):
        self.engine, self.vocab = engine, vocab
        self.verify, self.identity, self.execute = verify, identity, execute
        if verification not in ('startup', 'per-request'):
            raise ValueError('Unsupported verification mode')
        self.verification = verification
        self.prefix_cache = prefix_cache
        from .prefix_cache_v14 import PrefixCache
        self.cache = PrefixCache()
        self.conversation = None
        self.startup_proof = startup_proof or {}
        if not self.startup_proof.get('resident_weights_verified'):
            raise RuntimeError('Completed startup verification proof required')
        self.state = 'READY'

    def generate(self, request):
        validate_request(request)
        if request['op'] != 'generate':
            raise ValueError('Generation operation required')
        if self.state != 'READY':
            raise RuntimeError('Session is ' + self.state)
        started = time.monotonic()
        ids = self.vocab.encode_text(prompt_for(request['query']))
        n = request.get('max_tokens', 64)
        if not ids or len(ids) + n > self.engine.context:
            raise ValueError('Prompt plus output exceeds FPGA context')
        tokenization = time.monotonic() - started
        e = self.engine
        before = {k: getattr(e, k) for k in COUNTERS}
        timings = {k: dict(v) for k, v in e.command_timing.items()}
        result = dict(complete=False, query=request['query'], prompt_ids=ids,
                      generated_ids=[], prefix_tokens_reused=0,
                      ARM_model_inference=False, host_model_inference=False,
                      tools_executed=False, tokenization_seconds=tokenization,
                      prefill_batch_size=e.prefill_batch_size)
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
                group = ids[pos:pos+e.prefill_batch_size]
                token = e.prefill_batch(group, pos, logits=pos+len(group) == len(ids))
            result['prefill_seconds'] = time.monotonic() - tick
            tick = time.monotonic()
            raw = b''
            value = None
            for index in range(n):
                result['generated_ids'].append(token)
                raw += self.vocab.piece(token)
                value = typed_value(raw)
                if value is not None:
                    result['finish_reason'] = 'typed_json_complete'
                    break
                if token in e.manifest['eos_ids']:
                    raise RuntimeError('EOS without a complete typed call')
                if index+1 < n:
                    token = e.step(token, len(ids)+index, logits=True)
            result['decode_seconds'] = time.monotonic() - tick
            if value is None:
                raise RuntimeError('Output truncated; no tool executed')
            self.identity()
            if e.prefill_tokens - before['prefill_tokens'] != len(ids)-reused:
                raise RuntimeError('Physical prefill work does not match cache reuse')
            self.cache.commit(e, ids)
            tick = time.monotonic()
            call, tool = self.execute(json.dumps(dict(name=value[0], arguments=dict(path=value[1]))))
            result.update(complete=True, generated_text=raw.decode('utf-8'),
                          call=call, tool_result=tool, tools_executed=True,
                          tool_seconds=time.monotonic()-tick,
                          clock_hz=e.clock_hz, memory_clock_hz=e.memory_clock_hz)
            self.state = 'READY'
        except BaseException:
            # Fail closed after verification/inference errors. Never reuse uncertain KV.
            self.cache.reset()
            self.state = 'FAULTED'
            raise
        finally:
            result['work'] = {k: getattr(e, k)-v for k, v in before.items()}
            result['command_timing'] = {
                k: {f: v[f]-timings.get(k, {}).get(f, 0) for f in ('calls', 'seconds')}
                for k, v in e.command_timing.items()}
            result['elapsed_seconds'] = time.monotonic()-started
            self.last_result = result
        return result

    def close(self):
        if self.state == 'BUSY':
            raise RuntimeError('Cannot close an in-flight transaction')
        self.engine.close()
        self.vocab.close()
        # FAULTED is retained for diagnostics; closing mappings never resets hardware.
        if self.state != 'FAULTED':
            self.state = 'STOPPED'


def hardware_session(package, *, verification='startup', prefix_cache=True):
    from .qwen_fpga_runtime_candidate import QwenFpga, active_firmware, dma_segments, execute_generated, APP
    from .qwen_tokenizer_v1 import Vocabulary
    from .qwen_weight_verification_v16 import verify_weights
    from .qwen_dma_ownership_v16 import ownership
    package = Path(package)
    e = QwenFpga(package, preserve_prefix=False)
    try:
        vocab = Vocabulary(package)
        original = dma_segments()
        owned = dict(e.ownership_identity)
        e.prefix_identity['dma_ownership'] = owned
        startup_proof = dict(resident_weights_verified=True, verified_bytes=e.manifest['bytes'],
                             model_verify_ms=e.model_verify_ms, ownership=owned)
        boot = Path('/proc/sys/kernel/random/boot_id').read_text()
        files = [package/'model-manifest.json', package/'registers.json',
                 package/APP/'build.json', package/'rope.bin']
        import hashlib
        hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        def identity():
            if ownership() != owned:
                raise RuntimeError('DMA ownership/generation changed; drain, reload/seal and restart required')
            if (Path('/proc/sys/kernel/random/boot_id').read_text() != boot
                    or active_firmware() != APP+'.bit.bin' or dma_segments() != original
                    or Path('/sys/class/fpga_manager/fpga0/state').read_text().strip() != 'operating'):
                raise RuntimeError('Resident session identity changed')
            clocks = {p[0]: (int(p[1]), int(p[4])) for line in
                      Path('/sys/kernel/debug/clk/clk_summary').read_text().splitlines()
                      if (p := line.split()) and p[0] in ('pl0_ref', 'pl1_ref')}
            if any(clocks.get(k, (0, 0))[0] == 0 or clocks[k][1] != hz
                   for k, hz in [('pl0_ref', e.clock_hz), ('pl1_ref', e.memory_clock_hz)]):
                raise RuntimeError('Session clocks changed')
            if any(hashlib.sha256(p.read_bytes()).hexdigest() != h for p, h in hashes.items()):
                raise RuntimeError('Session package changed')
        return Session(e, vocab, lambda: verify_weights(e.dmafd, e.manifest, *original),
                       identity, execute_generated, verification=verification,
                       prefix_cache=prefix_cache, startup_proof=startup_proof)
    except BaseException:
        if 'vocab' in locals(): vocab.close()
        e.close()
        raise
