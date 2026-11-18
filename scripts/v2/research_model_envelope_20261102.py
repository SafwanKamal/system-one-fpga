"""Fetch public model metadata only; never download weights or access the board."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/research/model-envelope-2026-11-02'
MODELS = [
    'Qwen/Qwen3-0.6B', 'Qwen/Qwen3-1.7B',
    'Qwen/Qwen3-4B-Instruct-2507', 'Qwen/Qwen3-8B',
    'Qwen/Qwen3.5-0.8B', 'Qwen/Qwen3.5-2B', 'Qwen/Qwen3.5-4B',
    'HuggingFaceTB/SmolLM3-3B', 'Salesforce/xLAM-2-1b-fc-r',
    'Salesforce/xLAM-2-3b-fc-r', 'google/functiongemma-270m-it',
    'LiquidAI/LFM2.5-1.2B-Instruct', 'ibm-granite/granite-4.0-micro',
    'microsoft/Phi-4-mini-instruct', 'microsoft/bitnet-b1.58-2B-4T',
]

def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'SystemOne-feasibility-research/1'})
    with urllib.request.urlopen(request, timeout=35) as response:
        return response.read()

def collect(model):
    folder = OUT / model.replace('/', '--')
    folder.mkdir(parents=True, exist_ok=True)
    result = {'model': model, 'sources': {}, 'errors': {}}
    try:
        raw = fetch('https://huggingface.co/api/models/' + model)
        info = json.loads(raw)
        revision = info['sha']
        (folder / 'api.json').write_bytes(raw)
        result.update(revision=revision, parameters=info.get('safetensors', {}).get('total'),
                      parameter_dtypes=info.get('safetensors', {}).get('parameters'),
                      license=info.get('cardData', {}).get('license'))
    except Exception as exc:
        result['errors']['api'] = str(exc)
        return result
    for name in ['config.json', 'README.md']:
        url = f'https://huggingface.co/{model}/resolve/{revision}/{name}'
        try:
            raw = fetch(url)
            (folder / name).write_bytes(raw)
            result['sources'][name] = {'url': url, 'sha256': hashlib.sha256(raw).hexdigest()}
            if name == 'config.json':
                config = json.loads(raw)
                result['config'] = config
        except Exception as exc:
            result['errors'][name] = str(exc)
    return result

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(collect, MODELS))
    (OUT / 'metadata.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    estimates = []
    for item in results:
        config = item.get('config', {})
        config = config.get('text_config', config)
        if config.get('model_type') not in ['qwen3', 'qwen2', 'smollm3']:
            continue
        h, f, layers = (config[k] for k in ['hidden_size', 'intermediate_size', 'num_hidden_layers'])
        hd = config.get('head_dim', h // config['num_attention_heads'])
        q, kv = config['num_attention_heads'] * hd, config['num_key_value_heads'] * hd
        matrices = config['vocab_size'] * h + layers * (2*h*q + 2*h*kv + 3*h*f)
        if not config.get('tie_word_embeddings', False):
            matrices += config['vocab_size'] * h
        other = layers * 2*h + h
        if config['model_type'] == 'qwen3':
            other += layers * 2*hd
        if config['model_type'] == 'qwen2':
            other += layers * (q + 2*kv)
        estimates.append({
            'model': item['model'], 'revision': item['revision'],
            'unique_parameters_from_config': matrices + other,
            'api_parameter_count_not_used_for_budget': item.get('parameters'),
            'matrix_parameters': matrices, 'other_parameters': other,
            'Q4_0_matrix_bytes_plus_FP32_other': matrices * 18 // 32 + other * 4,
            'Q8_0_matrix_bytes_plus_FP32_other': matrices * 34 // 32 + other * 4,
            'BF16_KV_bytes_by_total_context': {str(t): layers*2*kv*2*t for t in [512,1024,2048,4096]},
            'scope': 'Ideal tensor budget, not a GGUF file or deployment fit; no metadata/alignment/scratch/OS.',
        })
    (OUT / 'estimates.json').write_text(json.dumps(estimates, indent=2), encoding='utf-8')
    for item in results:
        config = item.get('config', {})
        text = config.get('text_config', config)
        keys = ['model_type', 'hidden_size', 'intermediate_size', 'num_hidden_layers',
                'num_attention_heads', 'num_key_value_heads', 'head_dim',
                'vocab_size', 'tie_word_embeddings', 'layer_types']
        print(json.dumps({'model': item['model'], 'parameters': item.get('parameters'),
                          'shape': {k: text[k] for k in keys if k in text},
                          'errors': item['errors']}))

if __name__ == '__main__':
    main()
