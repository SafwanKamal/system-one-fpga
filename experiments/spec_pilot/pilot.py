"""Host-only speculative decoding pilot on the unchanged RC1 (v9e) bitstream.

Runs ON THE BOARD as root with the RC1 service stopped. For every prompt it
decodes twice from position 0 with no prefix reuse:
  ar   - exactly the service's greedy path (prefill groups of 8, then cmd 1/2 steps);
  spec - prompt-lookup drafts of up to 7 tokens, verified in one 8-token batch
         pass (cmd 7/8), then one full head scan per lane until the first mismatch
         (cmd 9 copies the lane to lane 0; cmd 3/4 as in select_token).
It compares emitted tokens, the head's logit bits and a SHA-256 of every K/V row
the committed sequence owns. All neural arithmetic runs on the FPGA.

usage: python3 pilot.py --package PKG --workload workload.json --out DIR
"""
import argparse, fcntl, hashlib, json, struct, sys, time
from pathlib import Path

K = 7
NS = (6, 4, 3, 2)
NK, NC, HD = 8, 2048, 128


class Drafter:
    """Longest recent n-gram match in the context, then in earlier outputs (causal)."""
    def __init__(self):
        self.hist = {n: {} for n in NS}

    def add(self, seq):
        for n in NS:
            for s in range(len(seq) - n):
                self.hist[n][tuple(seq[s:s + n])] = seq[s + n:s + n + K]

    def draft(self, ctx):
        L = len(ctx)
        for n in NS:
            if L <= n:
                continue
            suf = ctx[L - n:]
            for s in range(L - n - 1, -1, -1):
                if ctx[s:s + n] == suf:
                    c = ctx[s + n:s + n + K]
                    if c:
                        return list(c)
            c = self.hist[n].get(tuple(suf))
            if c:
                return list(c)
        return []


def logit(e, OUTPUT):
    return struct.unpack_from('<I', e.scratch, OUTPUT + 4)[0]


def prefill(e, ids, OUTPUT):
    for pos in range(0, len(ids), e.prefill_batch_size):
        group = ids[pos:pos + e.prefill_batch_size]
        token = e.prefill_batch(group, pos, logits=pos + len(group) == len(ids))
    return token, logit(e, OUTPUT)


def kv_hash(e, CACHE, rows):
    h = hashlib.sha256()
    for layer in range(e.layer_count):
        for kv in range(2):
            for head in range(NK):
                base = CACHE + (((layer * 2 + kv) * NK + head) * NC) * HD * 2
                h.update(bytes(e.scratch[base:base + rows * HD * 2]))
    return h.hexdigest()


def counters(e):
    return dict(commands=e.commands, layer_weight_passes=e.layer_weight_passes, head_rows=e.head_rows,
                timing={k: dict(v) for k, v in e.command_timing.items()})


def delta(a, b):
    out = {k: b[k] - a[k] for k in ('commands', 'layer_weight_passes', 'head_rows')}
    out['timing'] = {k: dict(calls=v['calls'] - a['timing'].get(k, {}).get('calls', 0),
                             seconds=v['seconds'] - a['timing'].get(k, {}).get('seconds', 0.0))
                     for k, v in b['timing'].items()}
    return out


def run_ar(e, ids, max_new, eos, OUTPUT):
    t0 = time.monotonic()
    token, lg = prefill(e, ids, OUTPUT)
    t1 = time.monotonic()
    out, logits = [token], [lg]
    while len(out) < max_new and out[-1] not in eos:
        token = e.step(out[-1], len(ids) + len(out) - 1, logits=True)
        out.append(token); logits.append(logit(e, OUTPUT))
    return out, logits, dict(prefill_seconds=t1 - t0, decode_seconds=time.monotonic() - t1)


def run_spec(e, ids, max_new, eos, OUTPUT, drafter):
    t0 = time.monotonic()
    token, lg = prefill(e, ids, OUTPUT)
    t1 = time.monotonic()
    out, logits = [token], [lg]
    st = dict(passes=0, ar_steps=0, drafted=0, accepted=0, head_scans=0, zero_accept=0)
    while len(out) < max_new and out[-1] not in eos:
        p = len(ids) + len(out) - 1          # position of out[-1], not yet in K/V
        d = drafter.draft(ids + out)[:min(K, max_new - len(out) - 1, e.context - 1 - p)]
        if not d:
            token = e.step(out[-1], p, logits=True); st['ar_steps'] += 1; st['head_scans'] += 1
            out.append(token); logits.append(logit(e, OUTPUT)); continue
        e.prefill_batch([out[-1]] + d, p, logits=False)
        st['passes'] += 1; st['drafted'] += len(d)
        a = 0
        for lane in range(len(d) + 1):
            if lane:
                e.command(9, layer=lane)
            token = e.select_token(); st['head_scans'] += 1
            out.append(token); logits.append(logit(e, OUTPUT))
            if token in eos or len(out) >= max_new:
                break
            if lane < len(d) and token == d[lane]:
                a += 1; continue
            break
        st['accepted'] += a; st['zero_accept'] += (a == 0)
    st.update(prefill_seconds=t1 - t0, decode_seconds=time.monotonic() - t1)
    return out, logits, st


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package', type=Path, required=True)
    ap.add_argument('--workload', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.package / 'src'))
    from sysone.v2.qwen_fpga_runtime_candidate import QwenFpga, OUTPUT, CACHE
    from sysone.v2.qwen_tokenizer_v1 import Vocabulary
    from sysone.v2.qwen_arm_service_candidate import prompt_for
    work = json.loads(args.workload.read_text())
    result = dict(passed=False, started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                  pilot_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  workload_sha256=hashlib.sha256(args.workload.read_bytes()).hexdigest(), cases=[])
    lock = Path('/run/lock/sysone-inference.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    e = vocab = None
    try:
        e = QwenFpga(args.package)
        vocab = Vocabulary(args.package)
        eos = set(e.manifest['eos_ids'])
        result.update(clock_hz=e.clock_hz, memory_clock_hz=e.memory_clock_hz, model_verify_ms=e.model_verify_ms,
                      model_sha256=e.manifest['sha256'], boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
        cases = [dict(index=x['index'], domain=x['domain'], key=x['key'], prompt_ids=x['prompt_ids'],
                      max_new=x['max_new'], first=x['first']) for x in work['prompts']]
        for i, q in enumerate(work['tool_queries']):
            cases.append(dict(index=len(cases), domain='tool', key=q, prompt_ids=vocab.encode_text(prompt_for(q)),
                              max_new=work['tool_max_new'], first='ar' if i % 2 == 0 else 'spec'))
        drafter = Drafter()
        all_ok = True
        for c in cases:
            ids, rec = c['prompt_ids'], dict(index=c['index'], domain=c['domain'], key=c['key'],
                                             prompt_tokens=len(c['prompt_ids']), first=c['first'])
            runs = {}
            for mode in ([c['first'], 'spec' if c['first'] == 'ar' else 'ar']):
                before = counters(e)
                if mode == 'ar':
                    out, lg, st = run_ar(e, ids, c['max_new'], eos, OUTPUT)
                else:
                    out, lg, st = run_spec(e, ids, c['max_new'], eos, OUTPUT, drafter)
                st['kv_sha256'] = kv_hash(e, CACHE, len(ids) + len(out) - 1)
                st['work'] = delta(before, counters(e))
                runs[mode] = dict(tokens=out, logit_bits=lg, **st)
            drafter.add(runs['ar']['tokens'])     # identical to spec output when the case passes
            a, s = runs['ar'], runs['spec']
            rec.update(ar=a, spec=s, tokens_equal=a['tokens'] == s['tokens'], logits_equal=a['logit_bits'] == s['logit_bits'],
                       kv_equal=a['kv_sha256'] == s['kv_sha256'], generated=len(a['tokens']),
                       decode_speedup=a['decode_seconds'] / s['decode_seconds'] if s['decode_seconds'] else None)
            rec['identical'] = rec['tokens_equal'] and rec['logits_equal'] and rec['kv_equal']
            all_ok = all_ok and rec['identical']
            result['cases'].append(rec)
            print(json.dumps(dict(index=rec['index'], domain=rec['domain'], prompt=rec['prompt_tokens'], generated=rec['generated'],
                                  identical=rec['identical'], ar_s=round(a['decode_seconds'], 3), spec_s=round(s['decode_seconds'], 3),
                                  speedup=round(rec['decode_speedup'] or 0, 3), passes=s['passes'], ar_steps=s['ar_steps'],
                                  accepted=s['accepted'])), flush=True)
            (args.out / 'pilot.json').write_text(json.dumps(result) + '\n')
        result['passed'] = all_ok
    except Exception as exc:
        result['error'] = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        if vocab is not None:
            vocab.close()
        if e is not None:
            e.close()
        lock.close()
        result['finished_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        (args.out / 'pilot.json').write_text(json.dumps(result) + '\n')
        print('PILOT RESULT: ' + ('PASS' if result['passed'] else 'FAIL') + (' ' + result['error'] if 'error' in result else ''), flush=True)


if __name__ == '__main__':
    main()
