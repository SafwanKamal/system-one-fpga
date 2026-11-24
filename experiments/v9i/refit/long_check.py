"""Long-prompt raw check on the KR260: one image (v9h or v9i), the service's own drafter.

For each case in workload order: batched prefill (timed), then plain decode and drafted decode
in alternating order from the same prefilled cache. The drafter is the image's service drafter
(CostAwareDrafter over VoteDrafter(prompts=True, ns=(6,4,3,2,1)), prior 0.5/2.0, with the
given coefficients and P), with persistent history across cases as in the service. Every arm
must reproduce the recorded greedy tokens. Writes OUT/result.json after every case.

Run as root with the socket service stopped and the target image active (rc13_image.py up for
v9h, rc14_image.py up for v9i).
usage: long_check.py --package PKG --app v9h|v9i --workload W --coef C --P N --out DIR
"""
import argparse, fcntl, hashlib, importlib.util, json, struct, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import spec_decode  # noqa: E402  (experiments/spec_service/spec_decode.py)
from drafters import VoteDrafter, CostAwareDrafter  # noqa: E402  (experiments/draft_research/drafters.py)

NK, NC, HD = 8, 2048, 128


def load_runtime(package, app):
    sys.path.insert(0, str(package / 'src'))
    import sysone.v2  # noqa: F401
    path = package / 'src/sysone/v2/qwen_fpga_runtime_candidate.py'
    src = path.read_text()
    for old, new in [("APP='sysone-qwen-decoder-v9e'", "APP='sysone-qwen-decoder-%s'" % app),
                     ("b'xlnx,qwen-decoder-v9e-1.0'", "b'xlnx,qwen-decoder-%s-1.0'" % app)]:
        if src.count(old) != 1:
            raise RuntimeError('Unexpected runtime source: ' + old)
        src = src.replace(old, new)
    spec = importlib.util.spec_from_loader('sysone.v2.qwen_fpga_runtime_long_check', loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'sysone.v2'; mod.__file__ = str(path)
    sys.modules[spec.name] = mod
    exec(compile(src, str(path), 'exec'), mod.__dict__)
    return mod


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
    ap.add_argument('--app', choices=('v9h', 'v9i'), required=True)
    ap.add_argument('--workload', type=Path, required=True)
    ap.add_argument('--coef', type=Path, required=True)
    ap.add_argument('--P', type=int, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    coef = json.loads(a.coef.read_text())
    work = json.loads(a.workload.read_text())
    rt = load_runtime(a.package, a.app)
    res = dict(image=a.app, passed=False, started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               drafter=dict(coef=coef, P=a.P), checker_sha256=sha(__file__), spec_decode_sha256=sha(HERE / 'spec_decode.py'),
               drafters_sha256=sha(HERE / 'drafters.py'), workload_sha256=sha(a.workload), cases=[])
    out_file = a.out / 'result.json'
    lock = Path('/run/lock/sysone-inference.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    e = None
    try:
        e = rt.QwenFpga(a.package)
        if rt.active_firmware() != 'sysone-qwen-decoder-%s.bit.bin' % a.app:
            raise RuntimeError('%s image is not active: %s' % (a.app, rt.active_firmware()))
        res.update(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(), firmware=rt.active_firmware(),
                   clock_hz=e.clock_hz, memory_clock_hz=e.memory_clock_hz, model_sha256=e.manifest['sha256'])
        logit = lambda: struct.unpack_from('<I', e.scratch, rt.OUTPUT + 4)[0]
        eos = set(e.manifest['eos_ids'])
        stop = lambda toks: toks[-1] in eos
        batched = spec_decode.batched_head(e, rt.OUTPUT)
        drafter = CostAwareDrafter(VoteDrafter(prompts=True, ns=(6, 4, 3, 2, 1)), coef, prior=0.5, prior_w=2.0, P=a.P)
        ok = True
        for i, c in enumerate(work['cases']):
            ids = c['prompt_ids']
            rec = dict(key=c['key'], index=c['index'], domain=c['domain'], prompt_tokens=len(ids), max_new=c['max_new'])
            t0 = time.monotonic()
            for pos in range(0, len(ids), e.prefill_batch_size):
                g = ids[pos:pos + e.prefill_batch_size]
                first = e.prefill_batch(g, pos, logits=pos + len(g) == len(ids))
            first_bits = logit(); rec['prefill_seconds'] = time.monotonic() - t0
            runs = {}
            for mode in (['ar', 'drafted'] if i % 2 == 0 else ['drafted', 'ar']):
                t1 = time.monotonic()
                if mode == 'ar':
                    out, bits, st = spec_decode.decode(e, ids, first, c['max_new'], stop, logit=logit, first_bits=first_bits)
                else:
                    drafter.begin(ids)
                    out, bits, st = spec_decode.decode(e, ids, first, c['max_new'], stop, drafter=drafter, gate=None,
                                                       logit=logit, first_bits=first_bits, batched=batched)
                t2 = time.monotonic()
                st.update(decode_seconds=t2 - t1, kv_sha256=kv_hash(e, rt.CACHE, len(ids) + len(out) - 1), tokens=out, logit_bits=bits)
                runs[mode] = st
            drafter.feed(dict(ids=ids), runs['drafted']['tokens'])
            r, d = runs['ar'], runs['drafted']
            rec.update(ar=r, drafted=d, ar_equal_target=r['tokens'] == c['target'],
                       drafted_equal_ar=d['tokens'] == r['tokens'] and d['logit_bits'] == r['logit_bits'] and d['kv_sha256'] == r['kv_sha256'])
            rec['identical'] = rec['ar_equal_target'] and rec['drafted_equal_ar']
            ok = ok and rec['identical']
            res['cases'].append(rec)
            print(json.dumps(dict(i=i, index=c['index'], domain=c['domain'], identical=rec['identical'],
                                  prefill_s=round(rec['prefill_seconds'], 2), ar_s=round(r['decode_seconds'], 2),
                                  drafted_s=round(d['decode_seconds'], 2))), flush=True)
            out_file.write_text(json.dumps(res) + '\n')
        res['passed'] = ok
    except Exception as exc:
        res['error'] = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        if e is not None:
            e.close()
        lock.close()
        res['finished_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        out_file.write_text(json.dumps(res) + '\n')
        print('LONG RESULT: ' + ('PASS' if res['passed'] else 'FAIL') + (' ' + res['error'] if 'error' in res else ''), flush=True)
    if not res['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
