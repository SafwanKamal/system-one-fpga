"""Cost-aware drafter board check on v9g (board, root, RC1 service stopped, v9g image loaded).
See BOARD_PROTOCOL.md.

Runs the speculative qualification workload in its original order. For each case: one
prefill from position 0, then two speculative decodes, both scored by one cmd 11 + cmd 12
head scan per verify pass (v9g):
- `rc11`: RC1.1's drafter and gate (spec_decode.Drafter, spec_decode.Gate), history fed with
  the output, exactly as in the v9g pilot;
- `candidate`: CostAwareDrafter(VoteDrafter(prompts=True, ns=(6,4,3,2,1)), coef_dev,
  prior=0.5, prior_w=2, P=4) from drafters.py (byte copy of experiments/draft_research),
  no gate, history fed with prompt + output.
The order of the two modes alternates by case. Each mode is compared with the v9e records
(tokens, head logit bits, SHA-256 of the committed K/V rows); each mode's draft statistics
are compared with the exact offline replay in expected.json.

usage: python3 draft_pilot.py --package PKG --workload W.json --expected E.json --v9e A.json [B.json ...] --out DIR
"""
import argparse, fcntl, hashlib, importlib.util, json, struct, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import spec_decode  # noqa: E402  (copy of experiments/spec_service/spec_decode.py)
from drafters import VoteDrafter, CostAwareDrafter  # noqa: E402

NK, NC, HD = 8, 2048, 128
KEYS = ('passes', 'ar_steps', 'drafted', 'accepted', 'zero_accept', 'gated_off', 'head_scans')
SWAPS = [("APP='sysone-qwen-decoder-v9e'", "APP='sysone-qwen-decoder-v9g'"),
         ("b'xlnx,qwen-decoder-v9e-1.0'", "b'xlnx,qwen-decoder-v9g-1.0'")]


def load_runtime(package):
    sys.path.insert(0, str(package / 'src'))
    import sysone.v2  # noqa: F401  (package context for the runtime's relative imports)
    path = package / 'src/sysone/v2/qwen_fpga_runtime_candidate.py'
    src = path.read_text()
    for old, new in SWAPS:
        if src.count(old) != 1:
            raise RuntimeError('Unexpected runtime source: ' + old)
        src = src.replace(old, new)
    spec = importlib.util.spec_from_loader('sysone.v2.qwen_fpga_runtime_v9g_pilot', loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'sysone.v2'; mod.__file__ = str(path)
    sys.modules[spec.name] = mod
    exec(compile(src, str(path), 'exec'), mod.__dict__)
    return mod, dict(original_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                     transformed_sha256=hashlib.sha256(src.encode()).hexdigest())


def kv_hash(e, CACHE, rows):
    h = hashlib.sha256()
    for layer in range(e.layer_count):
        for kv in range(2):
            for head in range(NK):
                base = CACHE + (((layer * 2 + kv) * NK + head) * NC) * HD * 2
                h.update(bytes(e.scratch[base:base + rows * HD * 2]))
    return h.hexdigest()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package', type=Path, required=True)
    ap.add_argument('--workload', type=Path, required=True)
    ap.add_argument('--expected', type=Path, required=True)
    ap.add_argument('--v9e', type=Path, nargs='+', required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    rt, rt_hash = load_runtime(a.package)
    work = json.loads(a.workload.read_text())
    exp = json.loads(a.expected.read_text())
    expected = {c['key']: c for c in exp['cases']}
    ref = {}
    for p in a.v9e:
        for c in json.loads(p.read_text())['cases']:
            ref.setdefault(c['key'], dict(c, source=p.name))
    res = dict(passed=False, started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), runtime=rt_hash,
               pilot_sha256=sha(__file__), spec_decode_sha256=sha(HERE / 'spec_decode.py'),
               drafters_sha256=sha(HERE / 'drafters.py'), expected_sha256=sha(a.expected),
               workload_sha256=sha(a.workload), reference_files=[str(p) for p in a.v9e],
               gate_threshold=work['gate_threshold'], coef_dev=exp['coef_dev'], cases=[])
    lock = Path('/run/lock/sysone-inference.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    e = None
    try:
        e = rt.QwenFpga(a.package)
        if rt.active_firmware() != 'sysone-qwen-decoder-v9g.bit.bin':
            raise RuntimeError('v9g image is not active')
        cases = work['cases']
        if [c['key'] for c in cases] != [c['key'] for c in exp['cases']]:
            raise RuntimeError('expected.json does not follow the workload order')
        if any('query' in c for c in cases):
            from sysone.v2.qwen_tokenizer_v1 import Vocabulary
            from sysone.v2.qwen_arm_service_candidate import prompt_for
            vocab = Vocabulary(a.package)
            for c in cases:
                if 'query' in c:
                    c['prompt_ids'] = vocab.encode_text(prompt_for(c['query']))
            vocab.close()
        res.update(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(), clock_hz=e.clock_hz,
                   memory_clock_hz=e.memory_clock_hz, model_verify_ms=e.model_verify_ms, model_sha256=e.manifest['sha256'],
                   firmware=rt.active_firmware())
        logit = lambda: struct.unpack_from('<I', e.scratch, rt.OUTPUT + 4)[0]
        eos = set(e.manifest['eos_ids'])
        stop = lambda toks: toks[-1] in eos
        batched = spec_decode.batched_head(e, rt.OUTPUT)
        rc_drafter = spec_decode.Drafter()
        rc_gate = spec_decode.Gate(threshold=work['gate_threshold'])
        cand = CostAwareDrafter(VoteDrafter(prompts=True, ns=(6, 4, 3, 2, 1)), exp['coef_dev'], prior=0.5, prior_w=2.0, P=4)
        ok = True
        for i, c in enumerate(cases):
            ids = c['prompt_ids']; o = ref[c['key']]; x = expected[c['key']]
            rec = dict(key=c['key'], index=c['index'], domain=c['domain'], prompt_tokens=len(ids), max_new=c['max_new'], reference=o['source'])
            order = ['rc11', 'candidate'] if i % 2 == 0 else ['candidate', 'rc11']
            runs = {}
            t0 = time.monotonic()
            for pos in range(0, len(ids), e.prefill_batch_size):
                g = ids[pos:pos + e.prefill_batch_size]
                first = e.prefill_batch(g, pos, logits=pos + len(g) == len(ids))
            first_bits = logit(); rec['prefill_seconds'] = time.monotonic() - t0
            for mode in order:
                t1 = time.monotonic()
                if mode == 'rc11':
                    out, bits, st = spec_decode.decode(e, ids, first, c['max_new'], stop, drafter=rc_drafter, gate=rc_gate,
                                                       logit=logit, first_bits=first_bits, batched=batched)
                else:
                    cand.begin(ids)
                    out, bits, st = spec_decode.decode(e, ids, first, c['max_new'], stop, drafter=cand, gate=None,
                                                       logit=logit, first_bits=first_bits, batched=batched)
                t2 = time.monotonic()
                st.update(decode_seconds=t2 - t1, kv_sha256=kv_hash(e, rt.CACHE, len(ids) + len(out) - 1), tokens=out, logit_bits=bits)
                runs[mode] = st
            rc_drafter.add(runs['rc11']['tokens'])
            cand.feed(dict(ids=ids), runs['candidate']['tokens'])
            r, s = runs['rc11'], runs['candidate']
            eq = lambda y: y['tokens'] == o['ar']['tokens'] and y['logit_bits'] == o['ar']['logit_bits'] and y['kv_sha256'] == o['ar']['kv_sha256']
            rec.update(rc11=r, candidate=s, rc11_equal_v9e=eq(r), candidate_equal_v9e=eq(s),
                       rc11_stats_equal_replay=all(r[k] == x['rc11'][k] for k in KEYS),
                       candidate_stats_equal_replay=all(s[k] == x['candidate'][k] for k in KEYS),
                       generated=len(r['tokens']), model_rc11_seconds=x['model_rc11_seconds'],
                       model_candidate_seconds=x['model_candidate_seconds'])
            rec['identical'] = rec['rc11_equal_v9e'] and rec['candidate_equal_v9e']
            ok = ok and rec['identical']
            res['cases'].append(rec)
            print(json.dumps(dict(i=i, index=c['index'], domain=c['domain'], identical=rec['identical'],
                                  stats_eq=[rec['rc11_stats_equal_replay'], rec['candidate_stats_equal_replay']],
                                  rc11_s=round(r['decode_seconds'], 2), cand_s=round(s['decode_seconds'], 2),
                                  model=[round(x['model_rc11_seconds'], 2), round(x['model_candidate_seconds'], 2)])), flush=True)
            (a.out / 'pilot.json').write_text(json.dumps(res) + '\n')
        res['passed'] = ok
    except Exception as exc:
        res['error'] = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        if e is not None:
            e.close()
        lock.close()
        res['finished_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        (a.out / 'pilot.json').write_text(json.dumps(res) + '\n')
        print('PILOT RESULT: ' + ('PASS' if res['passed'] else 'FAIL') + (' ' + res['error'] if 'error' in res else ''), flush=True)


if __name__ == '__main__':
    main()
