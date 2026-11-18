"""Preserve prior baseline and snapshot this component milestone. No target API."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-ownership-v1'
DEST=ROOT/'docs/research/2026-10-16-typed200-amp-ownership-validation.json'

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
 assert not DEST.exists(),'never replace a sealed milestone'
 old=json.loads((BASE/'preservation-before.json').read_text())['preserved_sha256']
 print('Checking',len(old),'prior sealed files',flush=True)
 for name,h in old.items():assert (ROOT/name).is_file() and sha(ROOT/name)==h,name
 snap=BASE/'source-snapshot-v1';snap.mkdir(exist_ok=False)
 sources=list((ROOT/'firmware/typed200_amp_ownership').glob('*'))
 sources += [ROOT/'scripts/v2'/name for name in [
  'prepare_typed200_amp_protection.py','check_typed200_amp_ownership.py',
  'check_typed200_amp_firewalls.py','stage_typed200_amp_pmu.py',
  'build_typed200_amp_pmu.py','stage_typed200_amp_atf.py',
  'check_typed200_amp_mailbox.py','prepare_typed200_amp_ps.py',
  'audit_typed200_amp_native.py','seal_typed200_amp_ownership.py']]
 for p in sources:
  if p.is_file():
   dst=snap/p.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
 overlays={'plat/xilinx/zynqmp/pm_service/'+n for n in
  ['ownership.c','ownership.h','atf_guard.c','atf_guard.h','zynqmp_pm_svc_main.c']}
 overlays |= {'plat/xilinx/common/ipi_mailbox_service/ipi_mailbox_svc.c',
              'plat/xilinx/zynqmp/libpm.mk','plat/xilinx/zynqmp/platform.mk'}
 files=[]
 for p in BASE.rglob('*'):
  if not p.is_file():continue
  rel=p.relative_to(BASE);parts=rel.parts
  if any(x in parts for x in ('.Xil','__pycache__')):continue
  if p.name.startswith('hw-server-'):continue # daemon logs remain live
  if any(x.startswith('arm-trusted-firmware-') for x in parts):continue # pinned archive
  if 'source' in parts:
   i=parts.index('source');tail='/'.join(parts[i+1:])
   if tail not in overlays:continue # upstream files covered by archive
  if 'project' in parts:
   if not p.name.startswith('psu_init') and p.suffix!='.xci':continue
  files.append(p)
 docs=[ROOT/'docs/research'/n for n in [
  '2026-10-16-typed200-amp-ownership.md',
  '2026-10-16-typed200-amp-ownership-readiness.json',
  '2026-10-16-typed200-amp-ownership-experiments.csv']]
 candidate={p.relative_to(ROOT).as_posix():sha(p) for p in files+docs}
 # Validate local relative links in the report so the next chat can find receipts.
 import re
 for target in re.findall(r'\]\(([^)]+)\)',docs[0].read_text()):
  if not target.startswith('http'):assert (docs[0].parent/target).is_file(),target
 for name,h in old.items():assert sha(ROOT/name)==h,name
 result=dict(passed=True,preserved_unique_files=len(old),preserved_sha256=old,
  candidate_sha256=candidate,mutable_working_source_snapshotted=True,
  working_source_snapshot=snap.relative_to(ROOT).as_posix(),
  excludes=['mutable handoffs','live hw_server logs','Vivado project transient files',
            'unmodified upstream ATF trees covered by pinned archive'],
  component_milestone=True,deployment_ready=False,target_modified=False,
  next_gate='Compose trusted ATF/PMU/R5 activation and safe firewall transitions')
 with DEST.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print('PASS preserved',len(old),'prior files; sealed',len(candidate),'new source/evidence files; NOT deployment-ready',flush=True)
if __name__=='__main__':main()
