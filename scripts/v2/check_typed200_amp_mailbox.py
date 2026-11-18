"""Build/test isolated mailbox against frozen numerical/service sources."""
from pathlib import Path
import argparse, hashlib, json, os, re, subprocess
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-ownership-v1'

def main():
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);a=p.parse_args()
 assert re.fullmatch(r'mailbox-v[0-9]+',a.attempt)
 out=BASE/a.attempt;out.mkdir(exist_ok=False);rel=out.relative_to(ROOT).as_posix()
 units=['firmware/typed_intent/typed_intent.c','firmware/typed200_v2/typed200.c',
        'firmware/typed200_r5/service.c','firmware/typed200_amp_ownership/mailbox.c']
 sources=units+['firmware/typed200_amp_ownership/test_mailbox.c',
                'firmware/typed200_amp_ownership/mailbox.h','firmware/typed200_r5/service.h',
                'firmware/typed200_v2/typed200.h','firmware/typed_intent/typed_intent.h']
 hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in sources}
 wsl='/mnt/'+ROOT.drive[0].lower()+ROOT.as_posix()[2:]
 prefix=['wsl','-d','Ubuntu-24.04','--cd',wsl,'--'];records=[]
 def run(cmd,log,env=None):
  r=subprocess.run([str(v) for v in cmd],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
  (out/log).write_bytes(r.stdout);records.append(dict(command=[str(v) for v in cmd],exit=r.returncode,log=log))
  assert r.returncode==0,log
  return r.stdout.decode(errors='replace')
 flags=['-std=c11','-O2','-Wall','-Wextra','-Werror','-pedantic','-fno-fast-math','-ffp-contract=off',
        '-fsanitize=address,undefined','-fno-sanitize-recover=all']
 run([*prefix,'gcc',*flags,*units,sources[4],'-o',rel+'/test-mailbox'],'compile.log')
 print(run([*prefix,rel+'/test-mailbox'],'run.log'),flush=True)
 tools=Path('C:/AMDDesignTools/2025.2/win64/tools/clang-16/bin');env=os.environ.copy()
 env['PATH']='C:/AMDDesignTools/2025.2/Vitis/lib/win64.o'+os.pathsep+str(tools)+os.pathsep+env['PATH']
 run([tools/'clang.exe','--target=arm-none-eabi','-mcpu=cortex-r5','-mfloat-abi=soft',
      '-ffreestanding','-std=c11','-O2','-Wall','-Wextra','-Werror','-fstack-usage','-c',units[-1],
      '-o',rel+'/mailbox-r5.o'],'r5-compile.log',env)
 for n,h in hashes.items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h
 (out/'receipt.json').write_text(json.dumps(dict(passed=True,source_sha256=hashes,commands=records,
  target_executed=False,fpga_cycle_equivalence_proved=False,wcet_certified=False,
  activation_integrated=False,deployable=False),indent=2)+'\n')
 print('PASS mailbox host and R5 object; NOT deployment or timing qualification',flush=True)
if __name__=='__main__':main()
