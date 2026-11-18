"""Finite, append-only v8 baseline. No deployment writes and no real tool calls.

Run the copied source snapshot on Linux. Local --self-test uses a fake backend.
Cold workers are fresh processes under the parent's exclusive inference lock.
"""
import argparse
import csv
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT/'src'))
from sysone.v2.v8_benchmark import (chat, complete_record, chain_prompt, reduce_observed,
    transition, OUTPUT_RESERVE, VERSION)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''): h.update(block)
    return h.hexdigest()


def dump(path, value):
    temporary = path.with_suffix(path.suffix+'.new')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    temporary.replace(path)


def package_identity(package):
    expected = json.loads((package/'package-sha256.json').read_text())
    mismatches = [name for name, digest in expected.items() if sha(package/name) != digest]
    if mismatches: raise RuntimeError('Deployment package mismatch: '+','.join(mismatches))
    return dict(package_sha256=sha(package/'package-sha256.json'), files=len(expected),
                launcher_sha256=sha(Path('/usr/local/bin/sysone-qwen-fpga')),
                boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def telemetry():
    result = dict(monotonic=time.monotonic(), utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                  cpu_times=list(os.times()), loadavg=list(os.getloadavg()))
    result['temperatures_mC'] = {str(p): p.read_text().strip()
        for p in Path('/sys/class/thermal').glob('thermal_zone*/temp')}
    result['meminfo'] = Path('/proc/meminfo').read_text()
    return result


class Session:
    def __init__(self, package):
        from sysone.v2.qwen_fpga_runtime_v7 import QwenFpga
        from sysone.v2.qwen_tokenizer_v1 import Vocabulary
        started = time.monotonic()
        self.engine = None
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(QwenFpga, package, preserve_prefix=False)
            try:
                self.vocab = Vocabulary(package)
            except Exception:
                self.engine = future.result(); self.engine.close()
                raise
            self.engine = future.result()
        self.setup = dict(startup_wall_seconds=time.monotonic()-started,
                          model_verify_ms=self.engine.model_verify_ms,
                          model_verify_method=self.engine.model_verify_method)

    def close(self):
        if self.engine is not None: self.engine.close()
        if hasattr(self, 'vocab'): self.vocab.close()

    def infer(self, job):
        engine, vocab = self.engine, self.vocab
        started = time.monotonic(); token_start = started
        ids = job.get('prompt_ids')
        if ids is None: ids = vocab.encode_text(job['prompt'])
        result = dict(id=job['id'], prompt_ids=ids, input_tokens=len(ids),
                      tokenize_seconds=time.monotonic()-token_start,
                      output_budget=job['output_tokens'], generated_ids=[],
                      prefix_tokens_reused=0, backend='FPGA', status='started')
        if not ids or len(ids)+job['output_tokens'] > engine.context:
            result.update(status='context_exhausted', request_seconds=time.monotonic()-started)
            return result
        engine.begin_prefix(ids, enabled=False)
        before = {k: getattr(engine, k) for k in ('commands','layers','head_rows','layer_weight_passes')}
        prefill = time.monotonic()
        for pos in range(0, len(ids), engine.prefill_batch_size):
            group = ids[pos:pos+engine.prefill_batch_size]
            token = engine.prefill_batch(group, pos, logits=pos+len(group)==len(ids))
        result.update(prefill_seconds=time.monotonic()-prefill,
                      ttft_request_seconds=time.monotonic()-started)
        raw = b''; per_token = []; eos = []
        decode = time.monotonic()
        for index in range(job['output_tokens']):
            result['generated_ids'].append(token); raw += vocab.piece(token)
            if token in engine.manifest['eos_ids']: eos.append(index)
            stop = False
            if job.get('wire'):
                stop = complete_record(raw, job['wire']) is not None
            elif job.get('natural'):
                stop = parse_tool(raw) is not None
            if stop:
                result['finish_reason'] = 'record_complete'; break
            if job.get('natural') and eos:
                result['finish_reason'] = 'eos'; break
            if index+1 < job['output_tokens']:
                tick = time.monotonic()
                token = engine.step(token, len(ids)+index, logits=True)
                per_token.append(time.monotonic()-tick)
        result.update(status='completed', generated_text=raw.decode('utf-8', errors='replace'),
                      output_tokens=len(result['generated_ids']), subsequent_decode_steps=len(per_token),
                      decode_seconds=time.monotonic()-decode, per_token_seconds=per_token,
                      eos_positions=eos, request_seconds=time.monotonic()-started)
        result.setdefault('finish_reason', 'fixed_length' if not job.get('natural') else 'token_budget')
        result['work'] = {k: getattr(engine, k)-value for k, value in before.items()}
        return result


def parse_tool(raw):
    try:
        value = raw.decode('utf-8').strip()
        for prefix in ('```json\n', '```\n'):
            if value.startswith(prefix): value = value[len(prefix):].strip(); break
        row = json.loads(value)
        if type(row) is list and len(row) == 2 and all(type(x) is str for x in row): return row
    except (ValueError, UnicodeDecodeError): pass
    return None


def fixture(session):
    from sysone.v2.qwen_fpga_runtime_v7 import DESCRIPTOR, OUTPUT
    e = session.engine
    package = session.package
    ids = json.loads((package/'fixture-manifest.json').read_text())['ids']
    if len(ids) != 8: raise RuntimeError('Fixture token count')
    cases = []
    for start, count in [(0, 8), (0, 1), (1, 7)]:
        e._copy_words(0x2100, struct.pack('<'+'I'*count,
            *[e.manifest['embedding']+ids[start+b]*e.embedding_row_bytes for b in range(count)]))
        e.command(7, page=0x2100, rows=count, position=start)
        e._copy_words(DESCRIPTOR, struct.pack('<11I', *e.manifest['layer_offsets'][0]))
        e.command(8, page=DESCRIPTOR, rows=count, layer=0, position=start)
        for lane in range(count):
            e.command(10, layer=lane)
            actual = struct.unpack('<'+str(e.hidden)+'f', bytes(e.scratch[OUTPUT:OUTPUT+e.hidden*4]))
            expected = struct.unpack('<'+str(e.hidden)+'f', (package/f'expected-{start+lane}.bin').read_bytes())
            error = max(abs(a-b) for a,b in zip(actual, expected))
            if not all(math.isfinite(a) for a in actual) or error > .00002:
                raise RuntimeError('Causal board fixture failed')
            cases.append(dict(start=start, count=count, lane=lane, max_absolute_error=error))
    return dict(passed=True, cases=cases)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--package', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--manifest', type=Path)
    ap.add_argument('--worker', type=Path)
    args = ap.parse_args()
    if args.worker:
        started = time.monotonic(); session = None
        try:
            session = Session(args.package)
            row = session.infer(json.loads(args.worker.read_text()))
            row.update(session.setup)
            row['cold_call_seconds'] = time.monotonic()-started
            if 'ttft_request_seconds' in row:
                row['ttft_cold_seconds'] = session.setup['startup_wall_seconds']+row['ttft_request_seconds']
            dump(args.out, row)
        finally:
            if session is not None: session.close()
        return
    import fcntl
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out/'requests').mkdir()
    manifest = json.loads(args.manifest.read_text())
    if manifest['version'] != VERSION: raise ValueError('Manifest version')
    frozen = json.loads((ROOT/'source-sha256.json').read_text())
    for name, digest in frozen.items():
        if sha(ROOT/name) != digest: raise RuntimeError('Benchmark source changed: '+name)
    initial = package_identity(args.package)
    dump(args.out/'deployment-before.json', initial)
    dump(args.out/'environment-before.json', telemetry())
    dump(args.out/'run-config.json', dict(version=VERSION, manifest_sha256=sha(args.manifest),
        source_sha256=sha(ROOT/'source-sha256.json'), package=str(args.package),
        mode='finite', power='unmeasured', tool_execution='simulated; no real reads', warmups=0))
    lock = Path('/run/lock/sysone-inference.lock').open('a')
    lock_start = time.monotonic()
    # Do not queue behind another workload and then contaminate cold-call timings.
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    rows = []; session = None; completed = 0; active = None

    def status(stage, **extra):
        dump(args.out/'status.json', dict(stage=stage, completed_requests=completed,
            current=active, utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), **extra))

    def resident():
        nonlocal session
        if session is None:
            session = Session(args.package); session.package = args.package
            dump(args.out/'resident-startup.json', session.setup)
        return session

    def run(job, mode='resident'):
        nonlocal completed, active
        active = job['id']; status('running')
        # Intent is durable before hardware use; interrupted attempts stay visible.
        dump(args.out/'requests'/(active+'.intent.json'), job)
        before = telemetry(); t = time.monotonic()
        if mode == 'cold':
            destination = args.out/'requests'/(active+'.worker.json')
            proc = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()),
                '--package', str(args.package), '--out', str(destination),
                '--worker', str(args.out/'requests'/(active+'.intent.json'))],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (args.out/'requests'/(active+'.stderr')).write_bytes(proc.stderr)
            if proc.returncode: raise RuntimeError('Cold worker failed: '+active)
            row = json.loads(destination.read_text())
        else: row = resident().infer(job)
        row.update(mode=mode, suite=job.get('suite'), harness_wall_seconds=time.monotonic()-t,
                   environment_before=before, environment_after=telemetry())
        return row

    def commit(row):
        nonlocal completed
        dump(args.out/'requests'/(row['id']+'.result.json'), row)
        with (args.out/'requests.jsonl').open('a') as f:
            f.write(json.dumps(row, allow_nan=False)+'\n'); f.flush(); os.fsync(f.fileno())
        rows.append(row); completed += 1; status('running')

    def tool_job(job):
        system = 'Tool: read_linux_file(path:string). Reply only with a compact JSON array ["read_linux_file","path"]. Copy the requested path exactly. No Markdown.'
        return dict(job, prompt=chat(system, job['query']), natural=True)

    try:
        dump(args.out/'lock.json', dict(wait_seconds=time.monotonic()-lock_start, exclusive=True))
        status('pre-fixture'); dump(args.out/'fixture-before.json', fixture(resident()))
        # Development chains exercise the frozen protocol; no adaptive tuning.
        chain_jobs = manifest['chains']
        phases = [('development', [j for j in chain_jobs if j['split']=='development']),
                  ('historical', manifest['historical']), ('fixed', manifest['fixed']),
                  ('application', manifest['application']),
                  ('heldout', [j for j in chain_jobs if j['split']=='heldout'])]
        for phase, jobs in phases:
            status(phase)
            for item in jobs:
                if item['suite'] != 'chain':
                    job = item
                    if item['suite'] == 'fixed':
                        ids = item['prompt_ids']
                        if len(ids) != item['input_tokens']: raise ValueError('Fixed input length')
                        job = dict(item, prompt_ids=ids)
                    else: job = tool_job(item)
                    row = run(job, item['mode'])
                    if item['suite'] in ('historic','application'):
                        parsed = parse_tool(row.get('generated_text','').encode())
                        allowed = parsed is not None and parsed[0]=='read_linux_file' and parsed[1] in (
                            '/proc/sys/kernel/random/boot_id','/proc/uptime','/proc/version')
                        expected = item['expected_path']
                        row.update(parsed_call=parsed, accepted=allowed,
                            correct=(parsed==['read_linux_file',expected]) if expected else None,
                            unsupported_safe_nonacceptance=(not allowed) if expected is None else None,
                            score_policy='Unsupported: report nonacceptance only; malformed output is not a correct refusal')
                    commit(row); continue
                chain = item['chain']; state = chain['initial']; gold = chain['initial']; history = []
                for index, step in enumerate(chain['steps']):
                    prompt, user = chain_prompt(chain,index,state,item['context'],item['wire'],history)
                    expected = transition(gold,step); gold = reduce_observed(gold,expected)
                    job = dict(id=f'{item["id"]}-step-{index+1:02d}', suite='chain',
                        prompt=prompt, output_tokens=OUTPUT_RESERVE, natural=True, wire=item['wire'])
                    row = run(job)
                    observed = complete_record(row.get('generated_text','').encode(),item['wire'])
                    tick = time.monotonic(); next_state = reduce_observed(state,observed)
                    row.update(chain_id=chain['id'], split=item['split'], context=item['context'],
                        wire=item['wire'], step=index+1, expected=expected, observed=observed,
                        correct=observed==expected, format_valid=observed is not None,
                        state_before=state,state_after=next_state,
                        reducer_seconds=time.monotonic()-tick,
                        provenance='Only observed model proposals committed; gold used for scoring only')
                    state = next_state
                    commit(row)
                    if row['status']=='context_exhausted': break
                    history.extend([('user',user),('assistant',row.get('generated_text','')),
                        ('user','Simulator committed '+json.dumps(observed,separators=(',',':')))])
        status('post-fixture'); dump(args.out/'fixture-after.json', fixture(resident()))
        final = package_identity(args.package)
        dump(args.out/'deployment-after.json', final)
        if final != initial: raise RuntimeError('Deployment identity changed')
        dump(args.out/'environment-after.json',telemetry())
        summary = summarize(rows)
        dump(args.out/'summary.json',summary)
        columns=['id','suite','mode','split','context','wire','step','status','correct',
                 'input_tokens','output_tokens','prefill_seconds','decode_seconds',
                 'request_seconds','cold_call_seconds','ttft_request_seconds','ttft_cold_seconds']
        with (args.out/'requests.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore')
            writer.writeheader();writer.writerows(rows)
        status('complete', deployment_unchanged=True)
    except Exception as exc:
        status('attention', error_type=type(exc).__name__, error=str(exc),
               instruction='No automatic retry, FPGA reload or model reload. Inspect current state.')
        dump(args.out/'partial-summary.json',summarize(rows))
        raise
    finally:
        if session is not None: session.close()
        lock.close()


def summarize(rows):
    groups = {}
    for row in rows:
        key = '/'.join(str(row.get(k,'')) for k in ('suite','mode','split','context','wire','input_tokens','output_budget'))
        groups.setdefault(key, []).append(row)
    result = {}
    for key, records in groups.items():
        times = [r['request_seconds'] for r in records if r['status']=='completed']
        result[key] = dict(attempts=len(records), completed=len(times),
            correct=sum(r.get('correct') is True for r in records),
            context_exhausted=sum(r['status']=='context_exhausted' for r in records),
            request_median_seconds=statistics.median(times) if times else None)
    survival = {}
    for row in rows:
        if row.get('suite') != 'chain': continue
        key = '/'.join((row['split'],row['context'],row['wire']))
        survival.setdefault(key,{}).setdefault(row['chain_id'],[]).append(row)
    result_survival = {}
    for key, chains_ in survival.items():
        result_survival[key] = {str(k):dict(chains_observed=len(chains_),
            correct_through_k=sum(len(rs)>=k and all(r['correct'] for r in rs[:k]) for rs in chains_.values()))
            for k in (1,2,4,8,16)}
    return dict(groups=result, chain_survival=result_survival,
        total_recorded=len(rows), notes='No p99/WCET/energy claims. Counts include capacity failures.')


if __name__ == '__main__': main()
