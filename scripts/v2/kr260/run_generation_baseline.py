"""Measure persistent llama.cpp CPU server first answer text and decoding speed."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import socket
import statistics
import subprocess
import time
import urllib.error
import urllib.request

CASES = [
    ('short', 'Explain what an H-bridge does in two short sentences.'),
    ('negation', 'The instruction is: "do not turn off the kitchen lights". Should the lights be turned off? Answer yes or no and explain briefly.'),
    ('ambiguity', 'A user says "cancel it", but there is no previous conversation. What should an assistant ask? Reply in one sentence.'),
    ('context', 'Reference: An H-bridge uses four switches. One diagonal pair drives a motor in one direction; the other diagonal reverses it. Turning on both switches in the same leg shorts the supply. Dead time prevents overlap. Using only this reference, explain why dead time is needed in two sentences.'),
]


def request(base, prompt, max_tokens, process, timeout):
    payload = {'messages': [{'role': 'system', 'content': 'Give a brief, direct answer.'},
                            {'role': 'user', 'content': prompt}],
               'stream': True, 'stream_options': {'include_usage': True},
               'chat_template_kwargs': {'enable_thinking': False},
               'cache_prompt': False, 'max_tokens': max_tokens,
               'temperature': 0.7, 'top_p': 0.8, 'top_k': 20, 'min_p': 0,
               'presence_penalty': 1.5, 'seed': 0}
    req = urllib.request.Request(base+'/v1/chat/completions',
        data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    start = time.perf_counter()
    first_event = first_visible = first_word = None
    text, reasoning, timings, usage = '', '', {}, {}
    finish_reason = None
    rss_kib = None
    completed = False
    with urllib.request.urlopen(req, timeout=timeout) as response:
        for raw in response:
            if time.perf_counter()-start > timeout:
                raise TimeoutError('Completion exceeded the request deadline')
            line = raw.decode('utf-8').strip()
            if not line.startswith('data: '):
                continue
            data = line[6:]
            if data == '[DONE]':
                completed = True
                break
            event = json.loads(data)
            if first_event is None:
                first_event = time.perf_counter()-start
            timings = event.get('timings', timings)
            usage = event.get('usage') or usage
            for choice in event.get('choices', []):
                finish_reason = choice.get('finish_reason') or finish_reason
                delta = choice.get('delta', {})
                reasoning += delta.get('reasoning_content') or ''
                chunk = delta.get('content') or ''
                text += chunk
                if first_visible is None and text.strip():
                    first_visible = time.perf_counter()-start
                if first_word is None and any(c.isalnum() for c in text):
                    first_word = time.perf_counter()-start
                if chunk:
                    print(chunk, end='', flush=True)
            if platform.system() == 'Linux':
                try:
                    status=Path(f'/proc/{process.pid}/status').read_text()
                    rss_kib=int(next(s for s in status.splitlines() if s.startswith('VmHWM:')).split()[1])
                except (OSError, StopIteration):
                    pass
    if not completed or first_word is None:
        raise RuntimeError('Incomplete SSE response or no answer text')
    print(flush=True)
    return {'prompt': prompt, 'answer': text, 'reasoning': reasoning,
            'first_event_seconds': first_event, 'first_visible_text_seconds': first_visible,
            'first_word_seconds': first_word, 'completion_seconds': time.perf_counter()-start,
            'server_timings': timings, 'usage': usage, 'server_peak_rss_kib': rss_kib,
            'finish_reason': finish_reason, 'output_truncated': finish_reason == 'length',
            'under_one_second_first_word': first_word <= 1.0,
            'thinking_disabled_as_requested': not reasoning and '<think>' not in text,
            'cache_prompt_requested': False}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--server', type=Path, required=True)
    ap.add_argument('--model', type=Path, required=True)
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--report', type=Path, required=True)
    ap.add_argument('--repeats', type=int, default=2)
    ap.add_argument('--max-tokens', type=int, default=64)
    ap.add_argument('--timeout', type=int, default=180)
    args=ap.parse_args()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    log_path=args.report.with_suffix('.server.log')
    # Choose an unused local-only port; fail startup if another process wins it.
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    command=[str(args.server.resolve()), '-m', str(args.model.resolve()),
             '--host', '127.0.0.1', '--port', str(port), '-ngl', '0',
             '-c', '2048', '-t', str(args.threads), '-tb', str(args.threads),
             '--parallel', '1', '--jinja']
    digest=hashlib.sha256()
    with args.model.open('rb') as handle:
        for chunk in iter(lambda:handle.read(4*1024*1024),b''):digest.update(chunk)
    report={'complete':False, 'backend':'llama.cpp CPU', 'machine':platform.machine(),
            'platform':platform.platform(), 'model':args.model.name,
            'model_sha256':digest.hexdigest(), 'threads':args.threads,
            'command':command, 'cases':[], 'note':'Local persistent server; includes prompt prefill, excludes model startup from per-request latency. No FPGA acceleration. Context is a synthetic supplied snippet, not retrieved documentation.'}
    def save():
        args.report.write_text(json.dumps(report,indent=2)+'\n')
    started=time.perf_counter()
    process=None
    try:
        with log_path.open('wb') as log:
            kwargs={'creationflags':getattr(subprocess,'CREATE_NO_WINDOW',0)} if platform.system()=='Windows' else {}
            process=subprocess.Popen(command, stdout=log, stderr=log, **kwargs)
            base=f'http://127.0.0.1:{port}'
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f'Server exited {process.returncode}; inspect {log_path}')
                try:
                    with urllib.request.urlopen(base+'/health',timeout=2) as health:
                        if health.status==200:break
                except (urllib.error.URLError, TimeoutError):pass
                if time.perf_counter()-started>args.timeout:
                    raise TimeoutError('Server did not become ready')
                time.sleep(0.5)
            report['startup_seconds']=time.perf_counter()-started
            print(f'Server ready in {report["startup_seconds"]:.2f}s; warming up...',flush=True)
            report['warmup']=request(base,'Say hello.',8,process,args.timeout)
            save()
            for repeat in range(args.repeats):
                for name,prompt in CASES:
                    print(f'[{repeat+1}/{args.repeats}] {name}',flush=True)
                    result=request(base,prompt,args.max_tokens,process,args.timeout)
                    report['cases'].append({'name':name,'repeat':repeat,**result})
                    save()
                    print(f'first word {result["first_word_seconds"]:.3f}s; total {result["completion_seconds"]:.2f}s',flush=True)
            report['complete']=True
            report['first_word_median_seconds']=statistics.median(c['first_word_seconds'] for c in report['cases'])
            report['all_first_words_under_one_second']=all(c['under_one_second_first_word'] for c in report['cases'])
    except Exception as exc:
        report['error']=f'{type(exc).__name__}: {exc}'
        raise
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        save()
    print(f'Saved {args.report}',flush=True)


if __name__=='__main__':
    main()
