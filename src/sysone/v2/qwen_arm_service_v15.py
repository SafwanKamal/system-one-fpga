"""Single-owner persistent v9d service; every generation verifies all weights.

No prefix reuse, model arithmetic, or changed completion policy on ARM.
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
    if type(request) is not dict or set(request) - {'op', 'query', 'max_tokens'}:
        raise ValueError('Unknown request fields')
    if request.get('op') not in ('generate', 'health', 'shutdown'):
        raise ValueError('Unknown operation')
    if request['op'] != 'generate':
        if set(request) != {'op'}:
            raise ValueError('Control operation has extra fields')
        return
    if type(request.get('query')) is not str or not 1 <= len(request['query']) <= 16384:
        raise ValueError('Query must contain 1..16384 characters')
    n = request.get('max_tokens', 64)
    if type(n) is not int or not 1 <= n <= 128:
        raise ValueError('Output profile')


class Session:
    def __init__(self, engine, vocab, verify, identity, execute):
        self.engine, self.vocab = engine, vocab
        self.verify, self.identity, self.execute = verify, identity, execute
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
            result.update(self.verify())  # Must finish before ANY request NN command.
            self.identity()
            e.begin_prefix(ids, enabled=False)
            tick = time.monotonic()
            for pos in range(0, len(ids), e.prefill_batch_size):
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
            tick = time.monotonic()
            call, tool = self.execute(json.dumps(dict(name=value[0], arguments=dict(path=value[1]))))
            result.update(complete=True, generated_text=raw.decode('utf-8'),
                          call=call, tool_result=tool, tools_executed=True,
                          tool_seconds=time.monotonic()-tick,
                          clock_hz=e.clock_hz, memory_clock_hz=e.memory_clock_hz)
            self.state = 'READY'
        except BaseException:
            # Fail closed after verification/inference errors. Never reuse uncertain KV.
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


def hardware_session(package):
    from .qwen_fpga_runtime_v9d import QwenFpga, active_firmware, dma_segments, execute_generated, APP
    from .qwen_tokenizer_v1 import Vocabulary
    from .qwen_weight_verification_v15 import verify_weights
    package = Path(package)
    e = QwenFpga(package, preserve_prefix=False)
    try:
        vocab = Vocabulary(package)
        original = dma_segments()
        boot = Path('/proc/sys/kernel/random/boot_id').read_text()
        files = [package/'model-manifest.json', package/'registers.json',
                 package/APP/'build.json', package/'rope.bin']
        import hashlib
        hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        def identity():
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
                       identity, execute_generated)
    except BaseException:
        e.close()
        raise
