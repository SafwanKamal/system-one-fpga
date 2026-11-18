"""Verify the prior seal before creating a separate controller work area."""
from pathlib import Path
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'build/v2/typed200-amp-linux-r5-controller-v1'
ANCHOR = ROOT/'docs/research/2026-10-17-typed200-amp-linux-r5-validation.json'


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    prior = json.loads(ANCHOR.read_text())
    records = dict(prior['preserved_sha256'])
    for name, digest in prior['candidate_sha256'].items():
        assert name not in records or records[name] == digest
        records[name] = digest
    def verify(item):
        name, digest = item
        assert sha(ROOT/name) == digest, name
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(verify, records.items()))
    BASE.mkdir(exist_ok=False)
    (BASE/'prior-validation.json').write_bytes(ANCHOR.read_bytes())
    (BASE/'preservation-before.json').write_text(json.dumps(dict(
        passed=True, files=len(records), anchor=ANCHOR.relative_to(ROOT).as_posix(),
        anchor_sha256=sha(ANCHOR)), indent=2)+'\n')
    print(f'Prior preservation PASS {len(records)} files; separate controller root created')


if __name__ == '__main__':
    main()
