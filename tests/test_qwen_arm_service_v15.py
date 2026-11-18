import json
from types import SimpleNamespace
import pytest
from sysone.v2.qwen_arm_service_v15 import Session, COUNTERS, validate_request, prompt_for, typed_value


class Engine:
    context = 1024
    prefill_batch_size = 8
    clock_hz = 125000000
    memory_clock_hz = 250000000
    manifest = {'eos_ids': [99]}
    def __init__(self, events):
        self.events = events
        for k in COUNTERS:
            setattr(self, k, 0)
        self.command_timing = {}
    def begin_prefix(self, ids, enabled):
        assert not enabled
        self.events.append('begin')
    def prefill_batch(self, ids, pos, logits):
        self.events.append('NN')
        self.tokens += len(ids)
        return 1
    def close(self):
        self.events.append('close')


def make(verify=None):
    events = []
    e = Engine(events)
    vocab = SimpleNamespace(encode_text=lambda s: [7]*9,
                            piece=lambda t: b'["read_linux_file","/proc/uptime"]', close=lambda: None)
    def check():
        events.append('verify')
        return {'verified_bytes': 639446688, 'resident_weights_verified': True}
    s = Session(e, vocab, verify or check, lambda: events.append('identity'),
                lambda s: (json.loads(s), {'executed': True}))
    return s, events


def test_every_request_verifies_before_nn_and_counters_are_deltas():
    s, events = make()
    for _ in range(2):
        r = s.generate(dict(op='generate', query='Read /proc/uptime'))
        assert r['work']['tokens'] == 9
        assert r['resident_weights_verified'] and r['prefix_tokens_reused'] == 0
    assert events.count('verify') == 2
    assert events == ['identity','verify','identity','begin','NN','NN','identity']*2
    assert s.engine.tokens == 18 and s.state == 'READY'


def test_verification_failure_prevents_any_nn_and_faults_session():
    def bad():
        raise RuntimeError('weight mismatch')
    s, events = make(bad)
    with pytest.raises(RuntimeError, match='weight mismatch'):
        s.generate(dict(op='generate', query='x'))
    assert 'NN' not in events and s.state == 'FAULTED'
    with pytest.raises(RuntimeError, match='FAULTED'):
        s.generate(dict(op='generate', query='x'))


def test_rejection_does_not_touch_hardware_or_fault_session():
    s, events = make()
    s.engine.context = 2
    with pytest.raises(ValueError, match='context'):
        s.generate(dict(op='generate', query='x'))
    assert events == [] and s.state == 'READY'
    for request in [dict(op='generate',query='x',max_tokens=True),
                    dict(op='shutdown',query='x'), dict(op='other'), []]:
        with pytest.raises(ValueError):
            validate_request(request)


def test_prompt_and_completion_policy_match_unchanged_runner():
    from pathlib import Path
    # AST extraction avoids importing Linux-only fcntl on Windows.
    import ast
    tree = ast.parse(Path('scripts/v2/run_qwen_fpga_command_v9d.py').read_text())
    nodes = [n for n in tree.body if
             (isinstance(n, ast.FunctionDef) and n.name in ('prompt_for','typed_value')) or
             (isinstance(n, ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SYSTEM' for t in n.targets))]
    env = {'json': json}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<reference>','exec'),env)
    assert prompt_for('Read /proc/version') == env['prompt_for']('Read /proc/version')
    for raw in [b'[', b'```json\n["a","b"]', b'["a","b"]', b'\xff']:
        assert typed_value(raw) == env['typed_value'](raw)


def test_hardware_timeout_faults_and_rejects_next_request():
    s, events = make()
    def timeout(*a, **kw):
        raise TimeoutError('FPGA still running')
    s.engine.prefill_batch = timeout
    with pytest.raises(TimeoutError):
        s.generate(dict(op='generate', query='x'))
    assert s.state == 'FAULTED' and s.last_result['resident_weights_verified']
    assert events.count('verify') == 1
    with pytest.raises(RuntimeError, match='FAULTED'):
        s.generate(dict(op='generate',query='x'))
    assert events.count('verify') == 1
