"""Check the built ELF's actual load map, symbols, ABI and receipt; no execution."""
from pathlib import Path
import argparse,hashlib,json,shutil,struct
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='typed200-r5-elf-v8')
    ap.add_argument('--out',default='typed200-r5-audit-v3');args=ap.parse_args()
    build=ROOT/'build/v2'/args.name
    out=ROOT/'build/v2'/args.out;out.mkdir(exist_ok=False)
    receipt=json.loads((build/'receipt.json').read_text())
    for p,h in receipt['source_sha256'].items():assert sha(ROOT/p)==h,p
    for p,h in receipt['artifact_sha256'].items():assert sha(build/p)==h,p
    data=(build/'typed200-r5.elf').read_bytes()
    h=struct.unpack_from('<16sHHIIIIIHHHHHH',data)
    assert h[0][:7]==b'\x7fELF\x01\x01\x01' and h[1]==2 and h[2]==40 and h[4]==0
    loads=[]
    for i in range(h[10]):
        typ,off,va,pa,fs,ms,flags,align=struct.unpack_from('<8I',data,h[5]+i*h[9])
        if typ!=1:continue
        assert va==pa and fs<=ms and not (flags&1 and flags&2)
        assert (va<0x10000 and va+ms<=0x10000) or (0x20000<=va and va+ms<=0x30000)
        loads.append(dict(address=va,file_bytes=fs,memory_bytes=ms,flags=flags))
    assert len(loads)==5 and loads[0]['address']==0 and loads[0]['flags']==5
    assert loads[0]['file_bytes']==loads[0]['memory_bytes']<=0xf000
    sections=[struct.unpack_from('<10I',data,h[6]+i*h[11]) for i in range(h[12])]
    namesec=sections[h[13]];names=data[namesec[4]:namesec[4]+namesec[5]]
    def name(blob,n):return blob[n:blob.index(b'\0',n)].decode()
    sec={name(names,s[0]):s for s in sections if s[0]}
    for n,addr,size in [('.bss',0x20000,49640),('.svc_stack',0x2d000,8192),
                        ('.shared',0x2f000,384),('.exception_stacks',0xf000,1280)]:
        assert sec[n][1]==8 and sec[n][3]==addr and sec[n][5]==size,n
    sym=sec['.symtab'];strings=sections[sym[6]];blob=data[strings[4]:strings[4]+strings[5]]
    symbols=[]
    for i in range(1,sym[5]//sym[9]):
        n,val,size,info,other,idx=struct.unpack_from('<IIIBBH',data,sym[4]+i*sym[9])
        assert idx!=0,'unresolved '+name(blob,n)
        symbols.append(name(blob,n))
    assert not any(n.startswith('ti_mmio_') for n in symbols)
    for n in ['ti200_start','ti200_admission_observe','ti200_copy_hidden','ti200_propose',
              'ti200_terminal_observe','ti_head','ty_sha256','ty_r5_main']:
        assert n in symbols,n
    vendor=Path('C:/AMDDesignTools/2025.2/data/embeddedsw/lib/bsp/standalone_v9_1/src/arm/cortexr5')
    saved={}
    for src in ['gcc/boot.S','xreg_cortexr5.h','platform/ZynqMP/mpu_r5.c']:
        dest=out/Path(src).name;shutil.copyfile(vendor/src,dest);saved[src]=sha(dest)
    frames={}
    for usage in build.glob('*.su'):
        for line in usage.read_text().splitlines():
            location,n,kind=line.split('\t');assert kind=='static'
            frames[location.rsplit(':',1)[1]]=int(n)
    chain=['ty_r5_main','ty_service_poll','ti_bridge_core','ti_head']
    result={'passed':True,'target_executed':False,'wcet_certified':False,'elf_sha256':sha(build/'typed200-r5.elf'),
            'load_segments':loads,'atcm_code_constants_bytes':loads[0]['memory_bytes'],'btcm_work_bytes':49640,
            'svc_stack_bytes':8192,'shared_bytes':384,'banked_exception_stacks_bytes':1280,
            'head_chain_static_stack_bytes':sum(frames[n] for n in chain),'compiler_stack_frames':frames,
            'stack_limit_note':'Compiler frame sum for main/poll/bridge/head; not a measured high-water or WCET proof',
            'legacy_sha_transport_linked':False,'undefined_symbols':0,
            'vendor_reference':'Installed AMD 2025.2 standalone_v9_1; snapshots, not assumed identical to a Git commit',
            'vendor_source_sha256':saved}
    (out/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS actual ELF load map, RX/RW separation, TCM fit, resolved symbols and corrected transport only')
if __name__=='__main__':main()
