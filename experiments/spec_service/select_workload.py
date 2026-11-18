"""Fixed qualification workload (written before the run): build/v2/spec-qual/{workload,queries}.json.

- general / maintenance: distinct saved Qwen3-0.6B prompts (qwen06-q4 runs), excluding
  the 24 used by the 2026-11-17 pilot, chosen by SHA-256 order; 96 new tokens max.
- long: synthetic long contexts (1,200-1,950 prompt tokens) made by concatenating
  remaining maintenance prompts; 64 new tokens max. Exactness/attention-reach cases;
  reported separately from the domain speed claims.
- tool: RC1 service-style tool queries (only the three paths the executor allows),
  tokenized on the board with the RC1 tokenizer; 64 new tokens max.
Every 4th case (by position) is in the boot-B cross-boot subset.
"""
import hashlib, json, glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/v2/spec-qual'
N_GEN, N_MAINT, N_LONG = 70, 70, 20
GATE_THRESHOLD = 0.25
PATHS = ['/proc/sys/kernel/random/boot_id', '/proc/uptime', '/proc/version']
TEMPLATES = ['Read {p}', 'Please read {p}', 'Show me the contents of {p}', 'What does {p} contain?',
             'Open {p} and return it', 'I need the file {p}', 'Get {p} for me']


def main():
    pilot = {x['key'] for x in json.loads((ROOT / 'build/v2/spec-pilot/workload.json').read_text())['prompts']}
    seen, pools = set(pilot), {'general': [], 'maintenance': []}
    for f in sorted(glob.glob(str(ROOT / 'build/v2/model-capability-20261102*/runs/qwen06-q4/*.jsonl'))):
        if 'before-token-replay' in f:
            continue
        for line in open(f, encoding='utf-8'):
            r = json.loads(line)
            ids = r.get('prompt_ids')
            if not ids or r.get('thinking') or r.get('domain') not in pools or len(ids) + 96 > 2048:
                continue
            key = hashlib.sha256(json.dumps(ids).encode()).hexdigest()
            if key in seen:
                continue
            seen.add(key)
            pools[r['domain']].append(dict(key=key, domain=r['domain'], prompt_ids=ids, max_new=96))
    for d in pools:
        pools[d].sort(key=lambda x: x['key'])
    gen, maint = pools['general'][:N_GEN], pools['maintenance'][:N_MAINT]
    rest = pools['maintenance'][N_MAINT:]
    longs, j = [], 0
    while len(longs) < N_LONG and j < len(rest):
        ids, parts = [], []
        while j < len(rest) and len(ids) < 1200:
            nxt = rest[j]['prompt_ids']; j += 1
            if len(ids) + len(nxt) > 1950:
                continue
            ids += nxt; parts.append(rest[j - 1]['key'][:12])
        if len(ids) >= 1200:
            key = hashlib.sha256(json.dumps(ids).encode()).hexdigest()
            longs.append(dict(key=key, domain='long', prompt_ids=ids, max_new=64, parts=parts))
    tools = []
    for i, t in enumerate(TEMPLATES):
        for p in PATHS:
            q = t.format(p=p)
            tools.append(dict(key='tool:' + q, domain='tool', query=q, max_new=64))
    # interleave domains so order effects and drift do not align with domain
    streams = [gen, maint, longs, tools]
    cases, k = [], 0
    while any(streams):
        for s in streams:
            if s:
                cases.append(s.pop(0))
    for i, c in enumerate(cases):
        c['index'] = i
        c['subset'] = (i % 4 == 0)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'workload.json').write_text(json.dumps(dict(gate_threshold=GATE_THRESHOLD, cases=cases)) + '\n')
    (OUT / 'queries.json').write_text(json.dumps(dict(queries=[c['query'] for c in cases if c['domain'] == 'tool'])) + '\n')
    count = lambda d: sum(c['domain'] == d for c in cases)
    print(json.dumps(dict(cases=len(cases), general=count('general'), maintenance=count('maintenance'), long=count('long'),
                          tool=count('tool'), subset=sum(c['subset'] for c in cases),
                          long_lengths=[len(c['prompt_ids']) for c in cases if c['domain'] == 'long'],
                          prompt_tokens=sum(len(c.get('prompt_ids', [])) for c in cases))))


if __name__ == '__main__':
    main()
