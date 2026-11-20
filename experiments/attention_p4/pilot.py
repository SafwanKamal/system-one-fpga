"""v9g board pilot (board, root, RC1 service stopped, v9g image loaded). See BOARD_PROTOCOL.md.

Runs the speculative-decoding qualification workload in its original order. For each case:
one prefill from position 0, then `ar` (plain one-token steps) and `batched` (spec_decode
with the adaptive gate, every verify pass scored by one cmd 11 + cmd 12 head scan).
Each mode is compared with the v9e records from the qualification boots (tokens, head logit
bits, SHA-256 of the committed K/V rows). The batched mode's draft statistics are also
compared with the v9e `adaptive` run.

The sealed RC1 runtime is used with two strings changed at import (app name and overlay
compatible). The source hash of both the original and the transformed module is recorded.

usage: python3 pilot.py --package PILOT_PKG --workload W.json --v9e A.json [B.json ...] --out DIR
"""
import argparse, fcntl, hashlib, importlib.util, json, struct, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import spec_decode  # noqa: E402  (copy of experiments/spec_service/spec_decode.py with batched_head)

NK, NC, HD = 8, 2048, 128
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


def snap(e):
    return dict(commands=e.commands, layer_weight_passes=e.layer_weight_passes, head_rows=e.head_rows,
                timing={k: dict(v) for k, v in e.command_timing.items()})


def delta(a, b):
    out = {k: b[k] - a[k] for k in ('commands', 'layer_weight_passes', 'head_rows')}
    out['timing'] = {k: dict(calls=v['calls'] - a['timing'].get(k, {}).get('calls', 0),
                             seconds=round(v['seconds'] - a['timing'].get(k, {}).get('seconds', 0.0), 6))
                     for k, v in b['timing'].items()}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package', type=Path, required=True)
    ap.add_argument('--workload', type=Path, required=True)
    ap.add_argument('--v9e', type=Path, nargs='+', required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    rt, rt_hash = load_runtime(a.package)
    work = json.loads(a.workload.read_text())
    ref = {}
    for p in a.v9e:
        for c in json.loads(p.read_text())['cases']:
            ref.setdefault(c['key'], dict(c, source=p.name))
    res = dict(passed=False, started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), runtime=rt_hash,
               pilot_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               spec_decode_sha256=hashlib.sha256((HERE / 'spec_decode.py').read_bytes()).hexdigest(),
               workload_sha256=hashlib.sha256(a.workload.read_bytes()).hexdigest(),
               reference_files=[str(p) for p in a.v9e], gate_threshold=work['gate_threshold'], cases=[])
    lock = Path('/run/lock/sysone-inference.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    e = None
    try:
        e = rt.QwenFpga(a.package)
        if rt.active_firmware() != 'sysone-qwen-decoder-v9g.bit.bin':
            raise RuntimeError('v9g image is not active')
        cases = work['cases']
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
        stop = lambda toks: toks[-1] in eos
        eos = set(e.manifest['eos_ids'])
        batched = spec_decode.batched_head(e, rt.OUTPUT)
        drafter = spec_decode.Drafter()
        gate = spec_decode.Gate(threshold=work['gate_threshold'])
        ok = True
        for i, c in enumerate(cases):
            ids = c['prompt_ids']; o = ref[c['key']]
            rec = dict(key=c['key'], index=c['index'], domain=c['domain'], prompt_tokens=len(ids), max_new=c['max_new'], reference=o['source'])
            order = ['ar', 'batched'] if i % 2 == 0 else ['batched', 'ar']
            runs = {}
            t0 = time.monotonic()
            for pos in range(0, len(ids), e.prefill_batch_size):
                g = ids[pos:pos + e.prefill_batch_size]
                first = e.prefill_batch(g, pos, logits=pos + len(g) == len(ids))
            first_bits = logit(); rec['prefill_seconds'] = time.monotonic() - t0
            for mode in order:
                t1 = time.monotonic(); b1 = snap(e)
                spec = mode == 'batched'
                out, bits, st = spec_decode.decode(e, ids, first, c['max_new'], stop,
                                                   drafter=drafter if spec else None, gate=gate if spec else None,
                                                   logit=logit, first_bits=first_bits, batched=batched if spec else None)
                t2 = time.monotonic()
                st.update(decode_seconds=t2 - t1, decode_work=delta(b1, snap(e)),
                          kv_sha256=kv_hash(e, rt.CACHE, len(ids) + len(out) - 1), tokens=out, logit_bits=bits)
                runs[mode] = st
            drafter.add(runs['ar']['tokens'])
            r, s = runs['ar'], runs['batched']
            eq = lambda x, y: x['tokens'] == y['tokens'] and x['logit_bits'] == y['logit_bits'] and x['kv_sha256'] == y['kv_sha256']
            rec.update(ar=r, batched=s, ar_equal_v9e=eq(r, o['ar']), batched_equal_v9e=eq(s, o['adaptive']),
                       draft_stats_equal_v9e=all(s[k] == o['adaptive'][k] for k in ('passes', 'ar_steps', 'drafted', 'accepted', 'zero_accept', 'gated_off')),
                       generated=len(r['tokens']),
                       v9e_ar_seconds=o['ar']['decode_seconds'], v9e_adaptive_seconds=o['adaptive']['decode_seconds'])
            rec['identical'] = rec['ar_equal_v9e'] and rec['batched_equal_v9e']
            ok = ok and rec['identical']
            res['cases'].append(rec)
            print(json.dumps(dict(i=i, index=c['index'], domain=c['domain'], identical=rec['identical'],
                                  stats_eq=rec['draft_stats_equal_v9e'], ar_s=round(r['decode_seconds'], 2),
                                  batched_s=round(s['decode_seconds'], 2), v9e_spec_s=round(o['adaptive']['decode_seconds'], 2),
                                  head_scans=s['head_scans'])), flush=True)
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
