"""Choose the pilot prompts deterministically from saved Qwen3-0.6B greedy runs.

Writes build/v2/spec-pilot/workload.json. Only prompt token ids are used; the
saved outputs came from a different quantization and are not a reference.
"""
import hashlib, json, glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/v2/spec-pilot'
PER_DOMAIN = 12
MAX_NEW = 96
TOOL_QUERIES = ['Read /proc/sys/kernel/random/boot_id', 'Read /proc/uptime', 'Read /proc/version']


def main():
    seen, pools = set(), {'general': [], 'maintenance': []}
    for f in sorted(glob.glob(str(ROOT / 'build/v2/model-capability-20261102*/runs/qwen06-q4/*.jsonl'))):
        if 'before-token-replay' in f:
            continue
        for line in open(f, encoding='utf-8'):
            r = json.loads(line)
            ids = r.get('prompt_ids')
            if not ids or r.get('thinking') or r.get('domain') not in pools:
                continue
            if len(ids) + MAX_NEW > 2048:
                continue
            key = hashlib.sha256(json.dumps(ids).encode()).hexdigest()
            if key in seen:
                continue
            seen.add(key)
            pools[r['domain']].append(dict(key=key, domain=r['domain'], prompt_ids=ids, source=Path(f).relative_to(ROOT).as_posix()))
    items = []
    for domain in ('general', 'maintenance'):
        items += sorted(pools[domain], key=lambda x: x['key'])[:PER_DOMAIN]
    # Interleave so drafting history and board drift do not line up with domain.
    general, maint = items[:PER_DOMAIN], items[PER_DOMAIN:]
    order = [x for pair in zip(general, maint) for x in pair]
    for i, x in enumerate(order):
        x['index'] = i
        x['max_new'] = MAX_NEW
        x['first'] = 'ar' if i % 2 == 0 else 'spec'
    OUT.mkdir(parents=True, exist_ok=True)
    workload = dict(max_new=MAX_NEW, prompts=order, tool_queries=TOOL_QUERIES, tool_max_new=32,
                    pool_sizes={k: len(v) for k, v in pools.items()})
    (OUT / 'workload.json').write_text(json.dumps(workload) + '\n')
    print(json.dumps(dict(prompts=len(order), pool_sizes=workload['pool_sizes'],
                          prompt_tokens=sum(len(x['prompt_ids']) for x in order))))


if __name__ == '__main__':
    main()
