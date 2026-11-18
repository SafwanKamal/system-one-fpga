"""Speculative decoding qualification on RC1 (board, root, RC1 service stopped).

For each case: prefill from position 0 (no reuse), then decode twice: `ar`
(plain one-token steps, the RC1 path) and `adaptive` (spec_decode with the
gate). Records tokens, head logit bits, SHA-256 of committed K/V rows,
per-command timing. With --compare-with, also checks bit equality against an
earlier run's records (cross-boot determinism).

usage: python3 qual.py --package PKG --workload W.json --out DIR [--only-subset] [--compare-with OLD/qual.json]
                       [--resume-from PARTIAL/qual.json]

--resume-from (PROTOCOL Amendment 2): skip cases already in PARTIAL and seed the
drafter history with their recorded `ar` tokens in workload order. Gate state is
not replayed (it starts from its prior).
"""
import argparse, fcntl, hashlib, json, struct, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import spec_decode  # noqa: E402

NK, NC, HD = 8, 2048, 128


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
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--only-subset', action='store_true')
    ap.add_argument('--compare-with', type=Path)
    ap.add_argument('--resume-from', type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(a.package / 'src'))
    from sysone.v2.qwen_fpga_runtime_candidate import QwenFpga, OUTPUT, CACHE
    work = json.loads(a.workload.read_text())
    cases = [c for c in work['cases'] if c.get('subset') or not a.only_subset]
    done = {}
    if a.resume_from:
        done = {c['key']: c for c in json.loads(a.resume_from.read_text())['cases']}
    old = {}
    if a.compare_with:
        old = {c['key']: c for c in json.loads(a.compare_with.read_text())['cases']}
    res = dict(passed=False, started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               qual_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               spec_decode_sha256=hashlib.sha256((HERE / 'spec_decode.py').read_bytes()).hexdigest(),
               workload_sha256=hashlib.sha256(a.workload.read_bytes()).hexdigest(),
               only_subset=a.only_subset, resumed_from=str(a.resume_from) if a.resume_from else None,
               resume_skipped=len([c for c in cases if c['key'] in done]), gate_threshold=work['gate_threshold'], cases=[])
    lock = Path('/run/lock/sysone-inference.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    e = None
    try:
        e = QwenFpga(a.package)
        eos = set(e.manifest['eos_ids'])
        if any('query' in c for c in cases):
            from sysone.v2.qwen_tokenizer_v1 import Vocabulary
            from sysone.v2.qwen_arm_service_candidate import prompt_for
            vocab = Vocabulary(a.package)
            for c in cases:
                if 'query' in c:
                    c['prompt_ids'] = vocab.encode_text(prompt_for(c['query']))
            vocab.close()
        res.update(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(), clock_hz=e.clock_hz,
                   memory_clock_hz=e.memory_clock_hz, model_verify_ms=e.model_verify_ms, model_sha256=e.manifest['sha256'])
        logit = lambda: struct.unpack_from('<I', e.scratch, OUTPUT + 4)[0]
        stop = lambda toks: toks[-1] in eos
        drafter = spec_decode.Drafter()
        gate = spec_decode.Gate(threshold=work['gate_threshold'])
        ok = True
        for c in cases:
            if c['key'] in done:
                drafter.add(done[c['key']]['ar']['tokens'])
        for i, c in enumerate(cases):
            if c['key'] in done:
                continue
            ids = c['prompt_ids']
            rec = dict(key=c['key'], index=c['index'], domain=c['domain'], prompt_tokens=len(ids), max_new=c['max_new'])
            order = ['ar', 'adaptive'] if i % 2 == 0 else ['adaptive', 'ar']
            runs = {}
            # One prefill per case: decode reads only prompt K/V rows (< len(ids)), which neither
            # mode's decode writes, plus the first token and its logit bits recorded here.
            t0 = time.monotonic()
            for pos in range(0, len(ids), e.prefill_batch_size):
                g = ids[pos:pos + e.prefill_batch_size]
                first = e.prefill_batch(g, pos, logits=pos + len(g) == len(ids))
            first_bits = logit(); rec['prefill_seconds'] = time.monotonic() - t0
            for mode in order:
                t1 = time.monotonic(); b1 = snap(e)
                out, bits, st = spec_decode.decode(e, ids, first, c['max_new'], stop,
                                                   drafter=drafter if mode == 'adaptive' else None,
                                                   gate=gate if mode == 'adaptive' else None, logit=logit, first_bits=first_bits)
                t2 = time.monotonic()
                st.update(decode_seconds=t2 - t1, decode_work=delta(b1, snap(e)),
                          kv_sha256=kv_hash(e, CACHE, len(ids) + len(out) - 1), tokens=out, logit_bits=bits)
                runs[mode] = st
            drafter.add(runs['ar']['tokens'])
            r, s = runs['ar'], runs['adaptive']
            rec.update(ar=r, adaptive=s, tokens_equal=r['tokens'] == s['tokens'], logits_equal=r['logit_bits'] == s['logit_bits'],
                       kv_equal=r['kv_sha256'] == s['kv_sha256'], generated=len(r['tokens']),
                       decode_speedup=r['decode_seconds'] / s['decode_seconds'] if s['decode_seconds'] else None)
            rec['identical'] = rec['tokens_equal'] and rec['logits_equal'] and rec['kv_equal']
            if c['key'] in old:
                o = old[c['key']]
                rec['cross_boot_equal'] = all(o[m]['tokens'] == rec[m]['tokens'] and o[m]['logit_bits'] == rec[m]['logit_bits']
                                              and o[m]['kv_sha256'] == rec[m]['kv_sha256'] for m in ('ar', 'adaptive'))
                ok = ok and rec['cross_boot_equal']
            ok = ok and rec['identical']
            res['cases'].append(rec)
            print(json.dumps(dict(i=i, index=c['index'], domain=c['domain'], prompt=len(ids), gen=rec['generated'],
                                  identical=rec['identical'], xboot=rec.get('cross_boot_equal'),
                                  ar_s=round(r['decode_seconds'], 2), spec_s=round(s['decode_seconds'], 2),
                                  speedup=round(rec['decode_speedup'] or 0, 3), passes=s['passes'], gated=s['gated_off'])), flush=True)
            if i % 10 == 9 or a.resume_from:  # resumed runs checkpoint every case (Amendment 2)
                (a.out / 'qual.json').write_text(json.dumps(res) + '\n')
        res['passed'] = ok
    except Exception as exc:
        res['error'] = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        if e is not None:
            e.close()
        lock.close()
        res['finished_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        (a.out / 'qual.json').write_text(json.dumps(res) + '\n')
        print('QUAL RESULT: ' + ('PASS' if res['passed'] else 'FAIL') + (' ' + res['error'] if 'error' in res else ''), flush=True)


if __name__ == '__main__':
    main()
