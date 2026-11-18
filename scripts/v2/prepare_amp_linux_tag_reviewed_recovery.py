"""Discharge the known pre-exec EACCES case without changing the failed journal."""
from pathlib import Path
import argparse
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-linux-tag-probe-v1'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);args=ap.parse_args()
    out=BASE/args.attempt;out.mkdir(exist_ok=False)
    code='''import fcntl,hashlib,json,os,pathlib,subprocess,sys
old=pathlib.Path('/run/sysone-linux-tag-target-trial-v1')
new=pathlib.Path('/var/lib/sysone/linux-tag-probe/reviewed-recovery-v1')
new.parent.mkdir(mode=0o700,parents=True,exist_ok=True);new.mkdir(mode=0o700)
def run(args,name):
 r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
 (new/name).write_bytes(r.stdout);assert r.returncode==0
 return r.stdout.decode(errors='replace')
with (old/'controller.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 original=(old/'state.json').read_bytes();state=json.loads(original)
 config=json.loads((old/'config.json').read_text())
 assert state['r5_start_attempted'] is False and state['apu_access_attempted'] is True
 assert not (old/'module-load.log').exists() and not (old/'apu-observations.json').exists()
 assert not pathlib.Path('/sys/module/sysone_r5_smoke').exists()
 assert not pathlib.Path('/sys/class/misc/sysone_r5_smoke').exists()
 assert os.statvfs(old).f_flag & os.ST_NOEXEC
 helper=old/'apu_probe'
 for name,digest in config['local_sha256'].items():
  assert hashlib.sha256((old/name).read_bytes()).hexdigest()==digest
 for p in pathlib.Path('/proc').glob('[0-9]*/cmdline'):
  try:first=p.read_bytes().split(bytes([0]))[0]
  except (FileNotFoundError,ProcessLookupError):continue
  assert first not in [str(helper).encode(),str(old/'pl_snapshot').encode()]
 journal=run(['journalctl','-u','sysone-linux-tag-target-trial-v1.service','--no-pager'],'original-journal.txt')
 assert 'PermissionError: [Errno 13] Permission denied: '+repr(str(helper)) in journal
 assert 'self._execute_child' in journal
 sys.path.insert(0,str(old));import amp_linux_tag_target as target
 before=target.observe();assert before['boot_id']==state['before']['boot_id']
 assert before['overlays']==['sysone-amp-origin-probe.dtbo'] and before['manager']=='operating'
 for maps in pathlib.Path('/proc').glob('[0-9]*/maps'):
  try:lines=maps.read_text().splitlines()
  except (FileNotFoundError,ProcessLookupError):continue
  for line in lines:
   words=line.split()
   assert not (len(words)>=6 and words[-1]=='/dev/mem' and 0xa0000000<=int(words[2],16)<0xb0000000)
 proof=dict(apu_helper_execve_refused=True,noexec_mount_confirmed=True,r5_never_loaded=True,
            original_journal_unchanged=True,pl_mapping_absent=True,no_raw_ps_mmio=True)
 (new/'no-execution-proof.json').write_text(json.dumps(proof,indent=2))
 run(['xmutil','unloadapp'],'unload.log');run(['xmutil','loadapp','k26-starter-kits'],'stock-load.log')
 after=target.observe();assert after['clock']==state['before']['clock']
 assert after['overlays']==['k26_starter_kits.dtbo'] and after['manager']=='operating'
 target.verify_files(state['baseline_files'])
 if state['dashboard_active']:
  run(['systemctl','start','snap.kria-dashboard.service.service'],'dashboard.log')
  run(['systemctl','is-active','--quiet','snap.kria-dashboard.service.service'],'dashboard-active.log')
 assert (old/'state.json').read_bytes()==original
 receipt=dict(passed=True,no_execution_proof=proof,stock_restored=True,clock_restored=True,
              baseline_hashes_unchanged=True,observed=after)
 (new/'receipt.json').write_text(json.dumps(receipt,indent=2))
 print(json.dumps(receipt,indent=2))
'''
    # --pipe routed Python stderr to the pinned SSH client, not journald.
    # Preserve that exact captured evidence in the independent review.
    captured=(BASE/'target-trial-v1/target/trial.stderr').read_bytes()
    digest=hashlib.sha256(captured).hexdigest()
    code=code.replace('/reviewed-recovery-v1', '/'+args.attempt)
    code=code.replace(" assert 'PermissionError: [Errno 13] Permission denied: '+repr(str(helper)) in journal\n assert 'self._execute_child' in journal",
        f" captured=bytes.fromhex('{captured.hex()}')\n assert hashlib.sha256(captured).hexdigest()=='{digest}'\n (new/'client-error.txt').write_bytes(captured)\n diagnosis=captured.decode()\n assert 'PermissionError: [Errno 13] Permission denied: '+repr(str(helper)) in diagnosis\n assert 'self._execute_child' in diagnosis")
    compile(code,'reviewed-recovery.py','exec');(out/'reviewed-recovery.py').write_text(code)
    plan=dict(commands=[dict(name='reviewed-recovery',root=True,command="python3 - <<'REVIEWED_RECOVERY'\n"+code+'\nREVIEWED_RECOVERY',timeout=180)])
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('PASS separate no-execution review/recovery plan; original failed journal preserved')


if __name__=='__main__':main()
