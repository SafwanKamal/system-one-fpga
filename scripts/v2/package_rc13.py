"""Assemble firmware/rc1_3 into build/v2/rc1-3/rc13.tar (bundle + v9h app + v9h registers.json +
copies of spec_decode.py and drafters.py (7-coefficient cost model) + config + tool queries).
usage: python scripts/v2/package_rc13.py
"""
import hashlib, json, shutil, tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'firmware/rc1_3'
OUT = ROOT / 'build/v2/rc1-3'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

stage = OUT / 'stage'
if stage.exists():
    shutil.rmtree(stage)
stage.mkdir(parents=True)
for f in ('rc13_image.py', 'spec_service_rc13.py', 'install_rc13.py', '20-rc13.conf', 'README.md'):
    shutil.copyfile(SRC / f, stage / f)
shutil.copyfile(ROOT / 'experiments/spec_service/spec_decode.py', stage / 'spec_decode.py')
shutil.copyfile(ROOT / 'experiments/draft_research/drafters.py', stage / 'drafters.py')
with tarfile.open(ROOT / 'build/v2/qwen-fpga-decoder-v9h/v9h-pilot.tar') as t:
    names = [m for m in t.getmembers() if m.name.startswith('sysone-qwen-decoder-v9h/')]
    t.extractall(stage, members=names)
app = stage / 'sysone-qwen-decoder-v9h'
fit = json.loads((ROOT / 'build/v2/rc1-3/fit.json').read_text())
work = json.loads((ROOT / 'build/v2/spec-qual/workload.json').read_text())
queries = [c['query'] for c in work['cases'] if 'query' in c]
(stage / 'queries.json').write_text(json.dumps(queries, indent=1) + '\n')
shutil.copyfile(ROOT / 'build/v2/qwen-fpga-decoder-v9h/pilot/registers-v9h.json', stage / 'registers-v9h.json')
cfg = dict(coef_v9h=fit['coef_v9h'], cost_features=fit['fit']['features'], drafter='CostAwareDrafter(VoteDrafter(prompts=True, ns=(6,4,3,2,1)), coef_v9h, prior=0.5, prior_w=2.0, P=4)',
           rc1_package_manifest_sha256=sha(ROOT / 'build/v2/hardware-consolidated-rc1/deployment-r2/package-sha256.json'),
           v9h_firmware_sha256={n: sha(app / n) for n in ('sysone-qwen-decoder-v9h.bit.bin', 'shell.json')})
(stage / 'config.json').write_text(json.dumps(cfg, indent=1) + '\n')
m = {str(p.relative_to(stage)).replace('\\', '/'): sha(p) for p in sorted(stage.rglob('*')) if p.is_file()}
(stage / 'bundle-sha256.json').write_text(json.dumps(m, indent=1) + '\n')
with tarfile.open(OUT / 'rc13.tar', 'w') as t:
    for p in sorted(stage.rglob('*')):
        if p.is_file():
            t.add(p, arcname='rc13/' + str(p.relative_to(stage)).replace('\\', '/'))
print(json.dumps(dict(tar=str(OUT / 'rc13.tar'), sha256=sha(OUT / 'rc13.tar'), files=len(m), queries=len(queries))))
