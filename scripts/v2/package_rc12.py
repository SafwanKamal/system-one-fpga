"""Assemble firmware/rc1_2 into build/v2/rc1-2/rc12.tar (bundle + v9g app + copies of the qualified
spec_decode.py and drafters.py + config + tool queries).
usage: python scripts/v2/package_rc12.py
"""
import hashlib, json, shutil, tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'firmware/rc1_2'
OUT = ROOT / 'build/v2/rc1-2'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

stage = OUT / 'stage'
if stage.exists():
    shutil.rmtree(stage)
stage.mkdir(parents=True)
for f in ('rc12_image.py', 'spec_service_rc12.py', 'install_rc12.py', '20-rc12.conf', 'README.md'):
    shutil.copyfile(SRC / f, stage / f)
shutil.copyfile(ROOT / 'experiments/spec_service/spec_decode.py', stage / 'spec_decode.py')
shutil.copyfile(ROOT / 'experiments/draft_research/drafters.py', stage / 'drafters.py')
with tarfile.open(ROOT / 'build/v2/qwen-fpga-decoder-v9g/v9g-pilot.tar') as t:
    names = [m for m in t.getmembers() if m.name.startswith('sysone-qwen-decoder-v9g/')]
    t.extractall(stage, members=names)
app = stage / 'sysone-qwen-decoder-v9g'
exp = json.loads((ROOT / 'build/v2/draft-board/expected.json').read_text())
work = json.loads((ROOT / 'build/v2/spec-qual/workload.json').read_text())
queries = [c['query'] for c in work['cases'] if 'query' in c]
(stage / 'queries.json').write_text(json.dumps(queries, indent=1) + '\n')
cfg = dict(coef_dev=exp['coef_dev'], drafter='CostAwareDrafter(VoteDrafter(prompts=True, ns=(6,4,3,2,1)), coef_dev, prior=0.5, prior_w=2.0, P=4)',
           rc1_package_manifest_sha256=sha(ROOT / 'build/v2/hardware-consolidated-rc1/deployment-r2/package-sha256.json'),
           v9g_firmware_sha256={n: sha(app / n) for n in ('sysone-qwen-decoder-v9g.bit.bin', 'shell.json')})
(stage / 'config.json').write_text(json.dumps(cfg, indent=1) + '\n')
m = {str(p.relative_to(stage)).replace('\\', '/'): sha(p) for p in sorted(stage.rglob('*')) if p.is_file()}
(stage / 'bundle-sha256.json').write_text(json.dumps(m, indent=1) + '\n')
with tarfile.open(OUT / 'rc12.tar', 'w') as t:
    for p in sorted(stage.rglob('*')):
        if p.is_file():
            t.add(p, arcname='rc12/' + str(p.relative_to(stage)).replace('\\', '/'))
print(json.dumps(dict(tar=str(OUT / 'rc12.tar'), sha256=sha(OUT / 'rc12.tar'), files=len(m), queries=len(queries))))
