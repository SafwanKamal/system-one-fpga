"""Host fault/negative-access tests and cross compilation; no target write API."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/v2/typed200-amp-ownership-v1'
def main():
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--plan',default='protection-plan-v1');a=p.parse_args()
 assert a.attempt.startswith('host-v') and a.attempt[6:].isdigit()
 out=BASE/a.attempt;out.mkdir(exist_ok=False);rel=out.relative_to(ROOT).as_posix()
 assert a.plan.startswith('protection-plan-v') and a.plan[17:].isdigit()
 config=BASE/a.plan;plan=json.loads((config/'plan.json').read_text())
 records=[]
 def run(cmd,log,env=None):
  r=subprocess.run([str(x) for x in cmd],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=150)
  (out/log).write_bytes(r.stdout);records.append(dict(command=[str(x) for x in cmd],exit=r.returncode,log=log))
  if r.returncode:raise RuntimeError(log)
  return r.stdout.decode(errors='replace')
 wslroot='/mnt/'+ROOT.drive[0].lower()+ROOT.as_posix()[2:]
 prefix=['wsl','-d','Ubuntu-24.04','--cd',wslroot,'--']
 src='firmware/typed200_amp_ownership';incs=['-I'+src,'-I'+config.relative_to(ROOT).as_posix()]
 flags=['-std=c11','-O2','-Wall','-Wextra','-Werror','-pedantic','-fsanitize=address,undefined','-fno-sanitize-recover=all']
 run([*prefix,'gcc',*flags,*incs,src+'/ownership.c',src+'/test_ownership.c','-o',rel+'/test'],'compile.log')
 print(run([*prefix,rel+'/test'],'run.log'),flush=True)
 # Separate declarative policy oracle. Check ALL source IDs, both security
 # states, R/W, boundaries and representative memory/TCM/management resources.
 def expected(port,addr,mid,secure,write):
  private=addr<0x60000000 or 0x70000000<=addr<0x7ff00000 or 0x800000000<=addr<0x880000000
  if private:return not secure
  if mid in range(0x80,0xc0) and not secure:
   return 0x62300000<=addr<0x62400000 or (not write and 0x62400000<=addr<0x62500000)
  if port==0 and mid<16 and secure:
   if 0x60000000<=addr<0x62500000:
    return not write or 0x62100000<=addr<0x62200000 or 0x62400000<=addr<0x62500000
  if port==3 and 0x200<=mid<0x240 and secure:
   return (not write and 0x60000000<=addr<0x62200000) or (write and 0x62200000<=addr<0x62300000)
  return False
 def actual(u,addr,mid,secure,write):
  match=None
  for r in u['regions']:
   if r['lo']<=addr<r['hi'] and (mid&r['mask'])==(r['mid']&r['mask']):match=r
  if not match:return False
  if secure==match['ns']:return False # strict secure/nonsecure equality
  return match['write' if write else 'read']
 addrs=set()
 for start,end in [tuple(v) for v in plan['allocation'].values()]+[(0,0x80000000),(0x70000000,0x7ff00000),(0x800000000,0x880000000)]:
  for x in [start-1,start,start+4095,end-1,end,end+4095]:
   if 0<=x<1<<40:addrs.add(x)
 cases=0
 for port,u in enumerate(plan['units'][:6]):
  for addr in sorted(addrs):
   for mid in range(1024):
    for sec in (False,True):
     for wr in (False,True):
      assert actual(u,addr,mid,sec,wr)==expected(port,addr,mid,sec,wr),(port,addr,mid,sec,wr)
      cases+=1
 # Decode generated XPPU parity independently of generation logic.
 for v in plan['xppu']['apertures']:
  for shift,mask in [(28,0x1f),(29,0x3e0),(30,0x7c00),(31,0x080f8000)]:
   assert (v&mask).bit_count()%2==((v>>shift)&1)
 for v in plan['xppu']['masters']:assert v.bit_count()%2==0
 for i in range(0xe0,0xf0):
  v=plan['xppu']['apertures'][i];assert v&0x080fffff==3
 # Cross compile unchanged policy for actual target ISA. These are objects,
 # not executable/deployable firmware or an integrated PMU image.
 tools=Path('C:/AMDDesignTools/2025.2/win64/tools/clang-16/bin');env=os.environ.copy()
 env['PATH']='C:/AMDDesignTools/2025.2/Vitis/lib/win64.o'+os.pathsep+str(tools)+os.pathsep+env['PATH']
 run([tools/'clang.exe','--target=arm-none-eabi','-mcpu=cortex-r5','-mfloat-abi=soft',
  '-ffreestanding','-std=c11','-O2','-Wall','-Wextra','-Werror','-c',src+'/ownership.c','-o',rel+'/ownership-r5.o'],'r5-compile.log',env)
 mb=Path('C:/AMDDesignTools/2025.2/Vivado/gnu/microblaze/nt/bin/mb-gcc.exe')
 run([mb,'-ffreestanding','-std=c11','-O2','-Wall','-Wextra','-Werror','-c',src+'/ownership.c','-o',rel+'/ownership-pmu.o'],'pmu-compile.log')
 hashes={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
  for p in [ROOT/src/'ownership.c',ROOT/src/'ownership.h',ROOT/src/'test_ownership.c',config/'plan.json',config/'plan.h']}
 (out/'receipt.json').write_text(json.dumps(dict(passed=True,ddr_negative_access_cases=cases,source_sha256=hashes,
  target_executed=False,integrated=False,deployable=False,commands=records),indent=2)+'\n')
 print('PASS DDR negative-access oracle:',cases,'cases; XPPU parity/TCM checks; R5 and PMU objects',flush=True)
if __name__=='__main__':main()
