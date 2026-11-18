"""Generate a NONDEPLOYABLE boot protection plan, with no target-write API.

Addresses are a candidate allocation only. Actual Linux/DT/boot inventory,
reservations, IPI apertures and resource graph must be reviewed before binding.
"""
from pathlib import Path
import json,hashlib,shutil,argparse,re
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'build/v2/typed200-amp-ownership-v1'
MB=1<<20
def xregion(lo,hi,mid,mask,read,write,ns=False,shift=20):
    assert lo<hi and lo%(1<<shift)==0 and hi%(1<<shift)==0
    assert 0<=mid<1024 and 0<=mask<1024
    return dict(start=lo>>shift,end=(hi-1)>>shift,master=(mask<<16)|mid,
      config=1|int(read)*2|int(write)*4|int(ns)*8|16,
      lo=lo,hi=hi,mid=mid,mask=mask,read=read,write=write,ns=ns,strict=True)
def parity(value,groups):
    for shift,mask in groups:
        value|=((value&mask).bit_count()%2)<<shift
    return value
def xppu_aperture(bits,ns):
    v=bits|(int(ns)<<27)
    return parity(v,[(28,0x1f),(29,0x3e0),(30,0x7c00),(31,0x080f8000)])
def xppu_master(mid,mask,ro=False):
    v=mid|(mask<<16)|(int(ro)<<30)
    return v|((v.bit_count()%2)<<31)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);a=ap.parse_args()
    assert re.fullmatch(r'protection-plan-v[0-9]+',a.attempt)
    dest=OUT/a.attempt;dest.mkdir(exist_ok=False)
    units=[];ops=[]
    def op(a,v,m=0xffffffff):
        assert v&~m==0;ops.append(dict(address=a,mask=m,value=v))
    # PRIVATE allocation remains 64 MiB; IDs/hidden/IPC moved to different 1MiB units.
    # Live /proc/iomem and boot DT pin two 2GiB banks, sysone 60000000..6fffffff
    # and PMU 7ff00000..7fffffff reserved. Preserve BOTH reservations in full.
    private=[(0,0x60000000),(0x70000000,0x7ff00000),(0x800000000,0x880000000)]
    r5=[(0x60000000,0x62100000,True,False),(0x62100000,0x62200000,True,True),
        (0x62200000,0x62300000,True,False),(0x62300000,0x62400000,True,False),
        (0x62400000,0x62500000,True,True)]
    pl=[(0x60000000,0x62100000,True,False),(0x62100000,0x62200000,True,False),
        (0x62200000,0x62300000,False,True)]
    for port in range(6):
        regions=[xregion(a,b,0,0,True,True,True) for a,b in private]
        regions += [xregion(0x62300000,0x62400000,0x80,0x3c0,True,True,True),
                    xregion(0x62400000,0x62500000,0x80,0x3c0,True,False,True)]
        if port==0:regions += [xregion(a,b,0,0x3f0,r,w) for a,b,r,w in r5]
        # HP0 is AFI FM0; all 64 local IDs trusted only inside frozen encoder topology.
        if port==3:regions += [xregion(a,b,0x200,0x3c0,r,w) for a,b,r,w in pl]
        units.append(dict(kind='ddr',base=0xfd000000+port*0x10000,ctrl=8,regions=regions))
    # FPD: NS access only where no higher secure resource range matches.
    protected=[(0xfd000000,0xfd0a0000),(0xfd1a0000,0xfd1b0000),
      (0xfd360000,0xfd3c0000),(0xfd5d0000,0xfd600000),(0xfd610000,0xfd620000),
      (0xfd690000,0xfd6a0000),(0xfd6e0000,0xfd710000),(0xfd800000,0xfd820000),
      (0xfd4f0000,0xfd500000),(0xfd4d0000,0xfd4e0000)]
    regions=[xregion(0,1<<32,0,0,True,True,True,12)]
    regions += [xregion(a,b,0,0,True,True,False,12) for a,b in protected]
    units.append(dict(kind='fpd',base=0xfd5d0000,ctrl=4,regions=regions))
    units.append(dict(kind='ocm',base=0xffa70000,ctrl=0,
      regions=[xregion(0xfffc0000,1<<32,0,0,True,True,False,12)]))
    for u in units:
        b=u['base'];rs=u['regions'];assert len(rs)<=16
        op(b,u['ctrl'],15) # denies unmatched before changing any entry
        for i in range(16):op(b+0x10c+16*i,0,31)
        if u['kind']!='fpd':op(b+0xc,0x100000,0xfff00000)
        for i,r in enumerate(rs):
            for off,key in [(0,'start'),(4,'end'),(8,'master'),(12,'config')]:
                op(b+0x100+16*i+off,r[key],31 if off==12 else 0xffffffff)
        # Lock is a boot-only transition; integration must confirm code/data remain accessible.
        op(b+0x20,1,1)
    # Complete 401-entry XPPU image. Unknown IPI message apertures are denied;
    # no broad APU/ALL profile can be enabled in a trusted R5/PMU message slot.
    mids=[xppu_master(0,0x3f0),xppu_master(0x40,0x3ff),
          xppu_master(0x80,0x3c0),xppu_master(0,0)]
    aper=[xppu_aperture(8,True) for _ in range(401)]
    secure_indices=set(range(0xe0,0xf0))|set(range(392,400))|{0x02,0x03,0x0a,0x0f,0x15,0x18,0x24,0x41,0x4b,0x5e,0x96,0x98,0x9a,0x9b,0xa5,0xa7,400,
       0xc8,0xca,0xcb,0xcc,0xcd,0xce,0xd0,0xd4,0xd5,0xd6,0xd8}
    for i in secure_indices:aper[i]=xppu_aperture(3,False)
    # Controller 0 APU, RPU controllers secure; PMU 0..3 share aperture 0x33.
    for i in range(0x30,0x40):aper[i]=xppu_aperture(3,False)
    aper[0x30]=xppu_aperture(6,True)
    for i in range(256,384):aper[i]=xppu_aperture(2,False)
    # Pinned BSP: APU buffer index2, RPU0 index0, PMU index7.
    # Driver xipipsu_buf.c: base + src*0x200 + dst*0x40, response +0x20.
    # Live board DT confirms APU->PMU request at ff9905c0. Four APU/PMU
    # pair apertures are NS and permit only APU/PMU; never R5/PMU slots.
    for src,dst,bits,ns in [(2,7,6,True),(7,2,6,True),(0,7,3,False),(7,0,3,False)]:
        index=256+(src*0x200+dst*0x40)//32
        for i in (index,index+1):aper[i]=xppu_aperture(bits,ns)
    op(0xff980000,0,7)
    for i in range(20):op(0xff980100+4*i,mids[i] if i<len(mids) else 0)
    for i,v in enumerate(aper):op(0xff981000+4*i,v)
    op(0xff980000,7,7) # parity checking + enforcement; self-policy PMU/R5 trusted only
    model=dict(schema='sysone.amp.protection-plan.v1',deployable=False,units=units,
      xppu=dict(masters=mids,apertures=aper,secure_indices=sorted(secure_indices)),writes=ops,
      allocation=dict(model=[0x60000000,0x62100000],ids=[0x62100000,0x62200000],
       hidden=[0x62200000,0x62300000],ingress=[0x62300000,0x62400000],result=[0x62400000,0x62500000]),
      unresolved=['Actual live DDR/PS/boot/DT inventory and reservation',
       'Actual ATF/PMU provenance and Linux compatibility of final IPI policy',
       'Trusted PMU/ATF and all non-IPI mutation-path integration',
       'R5 secure attributes, PL HP0 origin binding and no bypass',
       'New service addresses, driver/DT and startup composition',
       'Physical timing and target negative-access/recovery qualification'])
    (dest/'plan.json').write_text(json.dumps(model,indent=2)+'\n')
    header='#include "ownership.h"\nstatic const struct amp_write amp_plan[]={\n'
    header+=''.join('{0x%08xu,0x%08xu,0x%08xu},\n'%(x['address'],x['mask'],x['value']) for x in ops)
    header+='};\n';(dest/'plan.h').write_text(header)
    # Pin all vendor sources actually used, never edit installed/frozen sources.
    sdk=Path('C:/AMDDesignTools/2025.2/Vitis/data/embeddedsw');refs=dest/'primary';refs.mkdir()
    sources=[sdk/'lib/sw_apps/zynqmp_pmufw/src'/n for n in
      ['pm_core.c','pm_binding.c','pm_master.c','pm_defs.h','xpfw_core.c','xpfw_xpu.c','xpfw_mod_pm.c']]
    sources += [sdk/'lib/sw_apps/zynqmp_fsbl/src'/n for n in ['xfsbl_handoff.c','xfsbl_hw.h']]
    sources += [sdk/'lib/bsp/standalone_v9_4/src/arm/ARMv8/includes_ps/platform/ZynqMP'/n
      for n in ['xddr_xmpu0_cfg.h','xfpd_xmpu_cfg.h','xlpd_xppu.h']]
    receipts=[]
    for p in sources:
        data=p.read_bytes();(refs/p.name).write_bytes(data)
        receipts.append(dict(path=str(p),sha256=hashlib.sha256(data).hexdigest()))
    (dest/'primary-sources.json').write_text(json.dumps(receipts,indent=2)+'\n')
    print('Generated',len(ops),'boot-only writes; NOT DEPLOYABLE; max regions',max(len(u['regions']) for u in units))
if __name__=='__main__':main()
