"""Audit preserved native images and PS profile, never load them on a target."""
from pathlib import Path
import argparse,hashlib,json,re,struct,subprocess
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/v2/typed200-amp-ownership-v1'

def segments(p,machine):
 b=p.read_bytes();assert b[:4]==b'\x7fELF' and b[5]==1
 assert struct.unpack_from('<H',b,18)[0]==machine
 if b[4]==1:
  entry,off=struct.unpack_from('<II',b,24);size,n=struct.unpack_from('<HH',b,42)
  raw=[struct.unpack_from('<8I',b,off+i*size) for i in range(n)]
  rows=[dict(address=r[2],physical=r[3],offset=r[1],filesz=r[4],memsz=r[5],flags=r[6]) for r in raw if r[0]==1]
 else:
  entry,off=struct.unpack_from('<QQ',b,24);size,n=struct.unpack_from('<HH',b,54)
  raw=[struct.unpack_from('<II6Q',b,off+i*size) for i in range(n)]
  rows=[dict(address=r[3],physical=r[4],offset=r[2],filesz=r[5],memsz=r[6],flags=r[1]) for r in raw if r[0]==1]
 for r in rows:assert r['address']==r['physical'] and r['filesz']<=r['memsz'] and r['offset']+r['filesz']<=len(b)
 ordered=sorted(rows,key=lambda r:r['address'])
 for x,y in zip(ordered,ordered[1:]):assert x['address']+x['memsz']<=y['address']
 return dict(entry=entry,segments=rows,sha256=hashlib.sha256(b).hexdigest())

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);opt=ap.parse_args()
 assert re.fullmatch(r'native-audit-v[0-9]+',opt.attempt)
 out=BASE/opt.attempt;out.mkdir(exist_ok=False)
 pmu=BASE/'pmu-image-v3';atf=BASE/'atf-staged-v3';ps=BASE/'ps-profile-v4'
 pe=pmu/'typed200_amp_pmufw.elf';ae=atf/'native-build/zynqmp/release/bl31/bl31.elf'
 pr=segments(pe,189);ar=segments(ae,183)
 for r in pr['segments']:assert 0xffdc0000<=r['address'] and r['address']+r['memsz']<=0xffddfae0
 for r in ar['segments']:
  assert 0xfffea000<=r['address'] and r['address']+r['memsz']<=0xfffff000
  assert r['flags']&3!=3,'ATF writable executable load segment'
 for root,rec,elf in [(pmu,pr,'receipt.json'),(atf,ar,'receipt.json')]:
  assert rec['sha256']==json.loads((root/elf).read_text())['elf_sha256']
 # Disassembly presence is an audit aid, not a formal dominance/concurrency proof.
 dis=(pmu/'disassembly.log').read_text()
 commit=dis.split('<AmpPmuCommit>:',1)[1].split('\n\n',1)[0]
 assert '\tmfs\t' in commit and 'rmsr' in commit and '\tandi\t' in commit
 core=(pmu/'src/xpfw_core.c').read_text()
 assert 'mb_sleep();' not in core and core.count('AmpPmuLeasePoll();')==1
 assert core.index('AmpPmuLeaseIpi(')<core.index('/* Dispatch based on IPI ID')
 assert core.index('AmpPmuIpi(')<core.index('/* Dispatch based on IPI ID')
 assert 'if(!AmpPmuClosed() && (u32)TRUE == CorePtr->Scheduler.Enabled)' in core
 adis=(atf/'native-disassembly-v2.log').read_text()
 handler=adis.split('<pm_smc_handler>:',1)[1].split('\n\n',1)[0]
 assert '<AmpAtfLockAllow>' in handler and '<AmpAtfUnlock>' in handler
 assert '<AmpAtfIpiLockAllow>' in adis and '<AmpAtfCommit>:' in adis
 custom=(atf/'source/plat/xilinx/common/custom_sip_svc.c').read_text()
 assert 'SMC_RET1(handle, SMC_UNK)' in custom
 # Compare requested versus actual PS properties, never assume preset application.
 requested=json.loads((ps/'source-receipt.json').read_text())['config']
 actual=dict(line.split('\t',1) for line in (ps/'actual-properties.tsv').read_text().splitlines())
 mismatch={k:(v,actual.get(k)) for k,v in requested.items() if actual.get(k)!=v}
 # Vivado canonicalizes Boolean property 0/1 as false/true on some IP versions.
 mismatch={k:(v,w) for k,(v,w) in mismatch.items() if not ((v,w) in [('0','false'),('1','true')])}
 # Enabling the carrier's RGMII/ULPI peripherals overrides the SOM's generic
 # MIO defaults. Retain every difference; electrical compatibility is OPEN.
 derived={'CONFIG.PSU_MIO_43_DIRECTION':('inout','out'),
          'CONFIG.PSU_MIO_44_DIRECTION':('inout','in')}
 for pin in [44,46,47,48,49,64,65,67]:
  derived[f'CONFIG.PSU_MIO_{pin}_DRIVE_STRENGTH']=('4','12')
  derived[f'CONFIG.PSU_MIO_{pin}_SLEW']=('slow','fast')
 assert mismatch==derived,('unexpected property changes',mismatch)
 clock_keys=[k for k in actual if any(v in k for v in ['CPU_R5_CTRL','PL0_REF_CTRL','PL1_REF_CTRL','IOPLL_CTRL','RPLL_CTRL'])]
 for k in ['CONFIG.PSU__ENET0__PERIPHERAL__ENABLE','CONFIG.PSU__ENET1__PERIPHERAL__ENABLE',
           'CONFIG.PSU__ENET1__GRP_MDIO__ENABLE']:assert actual[k]=='1'
 hashes={}
 # Preserve source snapshots actually fed into the native images, not mutable
 # current firmware helper files. BSP remains covered by the prior baseline map.
 for directory in [pmu/'src',atf/'source/plat/xilinx/zynqmp/pm_service']:
  for p in directory.iterdir():
   if p.is_file():hashes[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
 result=dict(passed=True,pmu=pr,atf=ar,ps_requested_properties_match=False,
  ps_critical_clock_network_properties_match=True,ps_derived_mio_differences=mismatch,
  electrical_compatibility_qualified=False,
  generated_clocks={k:actual[k] for k in clock_keys},native_source_sha256=hashes,
  component_only=True,full_concurrency_or_platform_composition_proved=False,
  target_executed=False,deployable=False,
  rejected_native_attempts={'pmu-image-v2':'built but retains idle-sleep lost-wakeup window; use v3'},
  power_caveat='PMU polls instead of sleeping; idle-power cost unmeasured')
 (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
 print('PASS preserved native ELF/source/PS audit; hardware composition and qualification remain open')
if __name__=='__main__':main()
