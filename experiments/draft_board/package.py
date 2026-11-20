"""Build build/v2/draft-board/draft-board.tar and record the pre-registration hashes.
The v9g image and swap tool come from the v9g pilot tar, which is uploaded unchanged.
usage: python package.py
"""
import hashlib, json, shutil, tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BUILD = ROOT / 'build/v2/draft-board'
V9G_TAR = ROOT / 'build/v2/qwen-fpga-decoder-v9g/v9g-pilot.tar'
V9G_TAR_SHA = '796618b0f368d31582ef9e51e265106a38d93c66c69f8fd2ea5773c1a1f96431'
FILES = {'draft_pilot.py': HERE / 'draft_pilot.py', 'BOARD_PROTOCOL.md': HERE / 'BOARD_PROTOCOL.md',
         'prepare.py': HERE / 'prepare.py', 'dry_run.py': HERE / 'dry_run.py', 'expected.json': BUILD / 'expected.json',
         'drafters.py': ROOT / 'experiments/draft_research/drafters.py',
         'spec_decode.py': ROOT / 'experiments/spec_service/spec_decode.py',
         'workload.json': ROOT / 'build/v2/spec-qual/workload.json',
         'bootb-full-qual.json': ROOT / 'build/v2/spec-qual/board/bootb-full/qual.json',
         'bootc-resume-qual.json': ROOT / 'build/v2/spec-qual/board/bootc-resume/qual.json'}
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

if sha(V9G_TAR) != V9G_TAR_SHA:
    raise SystemExit('v9g pilot tar changed')
stage = BUILD / 'stage'
if stage.exists():
    shutil.rmtree(stage)
(stage / 'bundle').mkdir(parents=True)
for name, src in FILES.items():
    shutil.copyfile(src, stage / 'bundle' / name)
hashes = {'bundle/' + n: sha(stage / 'bundle' / n) for n in sorted(FILES)}
(stage / 'draft-sha256.json').write_text(json.dumps(hashes, indent=2) + '\n')
archive = BUILD / 'draft-board.tar'
with tarfile.open(archive, 'w') as out:
    for p in sorted(stage.rglob('*')):
        if p.is_file():
            out.add(p, arcname=str(p.relative_to(stage)).replace('\\', '/'))
prereg = dict(hashes, **{'draft-board.tar': sha(archive), 'v9g-pilot.tar': V9G_TAR_SHA})
(BUILD / 'prereg-sha256.txt').write_text(''.join('%s  %s\n' % (v, k) for k, v in prereg.items()))
print(json.dumps(dict(archive=str(archive), sha256=sha(archive), files=len(hashes))))
