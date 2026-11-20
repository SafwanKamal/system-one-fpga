"""v9h board check (board, root, RC1 service stopped, v9h image loaded): every 5th workload case,
plain one-token decode (`ar`) and the RC1.2 cost-aware drafter (`candidate`), both compared
with the v9e records (tokens, logit bits, K/V hash). Speed is compared offline with the v9g runs.

usage: python3 v9h_pilot.py --package PKG --workload W.json --expected E.json --v9e A.json [B.json ...] --out DIR
"""
import argparse, fcntl, hashlib, importlib.util, json, struct, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import spec_decode  # noqa: E402  (copy of experiments/spec_service/spec_decode.py)
from drafters import VoteDrafter, CostAwareDrafter  # noqa: E402

NK, NC, HD = 8, 2048, 128
KEYS = ('passes', 'ar_steps', 'drafted', 'accepted', 'zero_accept', 'gated_off', 'head_scans')
SWAPS = [("APP='sysone-qwen-decoder-v9e'", "APP='sysone-qwen-decoder-v9h'"),
         ("b'xlnx,qwen-decoder-v9e-1.0'", "b'xlnx,qwen-decoder-v9h-1.0'")]


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
        if rt.active_firmware() != 'sysone-qwen-decoder-v9h.bit.bin':
            raise RuntimeError('v9h image is not active')
        cases = [c for c in work['cases'] if c['index'] % 5 == 0]
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
        cand = CostAwareDrafter(VoteDrafter(prompts=True, ns=(6, 4, 3, 2, 1)), exp['coef_dev'], prior=0.5, prior_w=2.0, P=4)
        ok = True
        for i, c in enumerate(cases):
            ids = c['prompt_ids']; o = ref[c['key']]
            rec = dict(key=c['key'], index=c['index'], domain=c['domain'], prompt_tokens=len(ids), max_new=c['max_new'], reference=o['source'])
            order = ['ar', 'candidate'] if i % 2 == 0 else ['candidate', 'ar']
            runs = {}
            t0 = time.monotonic()
            for pos in range(0, len(ids), e.prefill_batch_size):
                g = ids[pos:pos + e.prefill_batch_size]
                first = e.prefill_batch(g, pos, logits=pos + len(g) == len(ids))
            first_bits = logit(); rec['prefill_seconds'] = time.monotonic() - t0
            for mode in order:
                t1 = time.monotonic()
                if mode == 'ar':
                    out, bits, st = spec_decode.decode(e, ids, first, c['max_new'], stop, logit=logit, first_bits=first_bits)
                else:
                    cand.begin(ids)
                    out, bits, st = spec_decode.decode(e, ids, first, c['max_new'], stop, drafter=cand, gate=None,
                                                       logit=logit, first_bits=first_bits, batched=batched)
                t2 = time.monotonic()
                st.update(decode_seconds=t2 - t1, kv_sha256=kv_hash(e, rt.CACHE, len(ids) + len(out) - 1), tokens=out, logit_bits=bits)
                runs[mode] = st
            cand.feed(dict(ids=ids), runs['candidate']['tokens'])
            r, s = runs['ar'], runs['candidate']
            eq = lambda y: y['tokens'] == o['ar']['tokens'] and y['logit_bits'] == o['ar']['logit_bits'] and y['kv_sha256'] == o['ar']['kv_sha256']
            rec.update(ar=r, candidate=s, ar_equal_v9e=eq(r), candidate_equal_v9e=eq(s), generated=len(r['tokens']))
            rec['identical'] = rec['ar_equal_v9e'] and rec['candidate_equal_v9e']
            ok = ok and rec['identical']
            res['cases'].append(rec)
            print(json.dumps(dict(i=i, index=c['index'], domain=c['domain'], identical=rec['identical'],
                                  ar_s=round(r['decode_seconds'], 2), cand_s=round(s['decode_seconds'], 2),
                                  prefill_s=round(rec['prefill_seconds'], 2))), flush=True)
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
