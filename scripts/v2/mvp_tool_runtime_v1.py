"""Small live MVP tool registry and Qwen response client; no host encoder model."""
import json
from pathlib import Path
import time
import urllib.request

BOOT_ID_PATH = '/proc/sys/kernel/random/boot_id'


def registered_tools():
    return [dict(name='read_linux_file', description='Reads a Linux system file.',
        parameters=dict(type='object', properties=dict(path=dict(type='string',
            description='The absolute file path to read.')), required=['path']))]


def execute_calls(calls):
    results = []
    for call in calls:
        if call['name'] != 'read_linux_file' or set(call['arguments']) != {'path'}:
            raise ValueError('Tool is not registered for the live MVP')
        path = call['arguments']['path']
        if path not in [BOOT_ID_PATH, '/proc/uptime', '/proc/version']:
            raise ValueError('This MVP tool reads the registered Linux system files')
        text = Path(path).read_text(encoding='utf-8').strip()
        if not text or len(text) > 4096:
            raise ValueError('Unexpected Linux system file result')
        results.append(dict(name=call['name'], arguments=call['arguments'],
            executed=True, result=dict(path=path, text=text)))
    if not results:
        raise ValueError('No tool call was produced; no action executed')
    return results


def generate_response(query, results, base_url):
    payload = dict(messages=[
        dict(role='system', content='Report the actual tool result in one sentence. Copy identifiers exactly. Use only the supplied result.'),
        dict(role='user', content=query+'\nActual tool output:\n'+json.dumps(results)+'\nReport the returned file text.')],
        stream=False, temperature=0, seed=0, max_tokens=96, cache_prompt=False,
        chat_template_kwargs=dict(enable_thinking=False))
    request = urllib.request.Request(base_url.rstrip('/')+'/v1/chat/completions',
        data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=180) as response:
        data = json.load(response)
    choice = data['choices'][0]
    answer = choice['message'].get('content') or ''
    expected = results[0]['result']['text']
    return dict(model='Qwen3-0.6B-Q4_K_M', backend='KR260_ARM_CPU_llama_cpp',
        fpga_generation=False, answer=answer, grounded_in_tool_result=expected in answer,
        finish_reason=choice.get('finish_reason'), usage=data.get('usage'),
        timings=data.get('timings'), elapsed_ms=(time.monotonic()-started)*1000)
