"""Preserve the completed smoke milestone before creating an AXI-tag candidate."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-linux-tag-probe-v1'
ANCHOR=ROOT/'docs/research/2026-10-17-typed200-amp-linux-r5-controller-validation.json'


def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    prior=json.loads(ANCHOR.read_text());records={}
    for group in ['preserved_sha256','candidate_sha256']:
        for name,digest in prior[group].items():
            assert name not in records or records[name]==digest,name
            records[name]=digest
    def check(item):
        name,digest=item
        assert sha(ROOT/name)==digest,name
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(check,records.items()))
    BASE.mkdir(exist_ok=False)
    (BASE/'prior-validation.json').write_bytes(ANCHOR.read_bytes())
    (BASE/'preservation-before.json').write_text(json.dumps(dict(passed=True,
        files=len(records),anchor=ANCHOR.relative_to(ROOT).as_posix(),
        anchor_sha256=sha(ANCHOR)),indent=2)+'\n')
    source=ROOT/'firmware/typed200_amp_linux_tag_probe'
    source.mkdir(exist_ok=False)
    for name in ['session.h','session.c','session_test.c','linux.c','Makefile','adapter_test.c','smoke-padded.ld']:
        original=ROOT/'firmware/typed200_amp_linux_r5_controller'/name
        assert sha(original)==records[original.relative_to(ROOT).as_posix()]
        (source/name).write_bytes(original.read_bytes())
    (source/'tag_probe.S').write_bytes((ROOT/'firmware/typed200_amp_linux_r5_controller/smoke-v2.S').read_bytes())
    print(f'PASS {len(records)} prior files preserved; separate candidate copied')


if __name__=='__main__':main()
