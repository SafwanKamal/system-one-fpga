"""Build tiny diagnostic R5 image in existing no-map DDR; no target actions."""
from pathlib import Path
import hashlib,json,os,struct,subprocess
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/v2/typed200-amp-deployment-v1'

def main():
 out=BASE/'r5-probe-build-v1';out.mkdir(exist_ok=False)
 tools=Path('C:/AMDDesignTools/2025.2/win64/tools/clang-16/bin')
 env=os.environ.copy();env['PATH']='C:/AMDDesignTools/2025.2/Vitis/lib/win64.o'+os.pathsep+str(tools)+os.pathsep+env['PATH']
 src=ROOT/'firmware/typed200_amp_probe';commands=[]
 def run(cmd,name):
  r=subprocess.run([str(x) for x in cmd],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
  (out/name).write_bytes(r.stdout);commands.append([str(x) for x in cmd]);assert not r.returncode,name
 run([tools/'clang.exe','--target=arm-none-eabi','-mcpu=cortex-r5','-mfloat-abi=soft','-c',src/'r5_probe.S','-o',out/'probe.o'],'compile.log')
 elf=out/'r5_probe.elf'
 run([tools/'ld.lld.exe','-T',src/'r5_probe.ld','--gc-sections','--no-undefined','-Map='+str(out/'probe.map'),out/'probe.o','-o',elf],'link.log')
 run([tools/'llvm-readelf.exe','-hlSs',elf],'elf-audit.txt')
 run([tools/'llvm-objdump.exe','-d',elf],'disassembly.txt')
 b=elf.read_bytes();assert b[:6]==b'\x7fELF\x01\x01' and struct.unpack_from('<H',b,18)[0]==40
 entry,off=struct.unpack_from('<II',b,24);size,num=struct.unpack_from('<HH',b,42)
 assert entry==0x63f00000
 rows=[]
 for i in range(num):
  r=struct.unpack_from('<8I',b,off+i*size)
  if r[0]!=1:continue
  assert r[2]==r[3] and r[4]<=r[5] and 0x63f00000<=r[2] and r[2]+r[5]<=0x63f10000 and r[6]&3!=3
  rows.append(dict(address=r[2],filesz=r[4],memsz=r[5],flags=r[6]))
 d=(out/'disassembly.txt').read_text();assert 'wfi' in d and 'dsb' in d
 (out/'receipt.json').write_text(json.dumps(dict(passed=True,entry=entry,segments=rows,
  elf_sha256=hashlib.sha256(b).hexdigest(),source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in src.iterdir() if p.is_file()},
  commands=commands,diagnostic_only=True,tcms_accessed=False,target_executed=False,
  reserved_ddr_backup_and_rpu_readiness_required=True),indent=2)+'\n')
 print('PASS diagnostic R5 ELF; dedicated 64KiB no-map window; no target action',flush=True)
if __name__=='__main__':main()
