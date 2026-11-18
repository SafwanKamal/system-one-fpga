"""Audit the actual diagnostic ELF layout without executing or editing it."""
from pathlib import Path
import json,struct

def audit(build: Path):
    data=(build/'typed200-trace.elf').read_bytes()
    h=struct.unpack_from('<16sHHIIIIIHHHHHH',data)
    assert h[0][:7]==b'\x7fELF\x01\x01\x01' and h[1:3]==(2,40) and h[4]==0
    loads=[]
    for i in range(h[10]):
        typ,off,va,pa,fs,ms,flags,align=struct.unpack_from('<8I',data,h[5]+i*h[9])
        if typ!=1:continue
        assert va==pa and fs<=ms and not (flags&1 and flags&2)
        assert (va<0x10000 and va+ms<=0x10000) or (0x20000<=va and va+ms<=0x30000)
        loads.append({'address':va,'file_bytes':fs,'memory_bytes':ms,'flags':flags})
    assert len(loads)==5 and loads[0]['address']==0 and loads[0]['flags']==5
    assert loads[0]['file_bytes']==loads[0]['memory_bytes']<=0xf000
    sections=[struct.unpack_from('<10I',data,h[6]+i*h[11]) for i in range(h[12])]
    ns=sections[h[13]];names=data[ns[4]:ns[4]+ns[5]]
    def name(blob,n):return blob[n:blob.index(b'\0',n)].decode()
    sec={name(names,s[0]):s for s in sections if s[0]}
    assert sec['.bss'][1]==8 and sec['.bss'][3]==0x20000
    assert sec['.bss'][5]<=0xd000
    for n,address,size in [('.shared',0x2f000,384),('.svc_stack',0x2d000,8192),
                           ('.exception_stacks',0xf000,1280)]:
        assert sec[n][1]==8 and sec[n][3:4]==(address,) and sec[n][5]==size
    sym=sec['.symtab'];strings=sections[sym[6]];blob=data[strings[4]:strings[4]+strings[5]]
    symbols={}
    for i in range(1,sym[5]//sym[9]):
        n,val,size,info,other,idx=struct.unpack_from('<IIIBBH',data,sym[4]+i*sym[9])
        assert idx!=0,'Unresolved symbol '+name(blob,n)
        symbols[name(blob,n)]=(val,size)
    address,size=symbols['ty_trace']
    assert size==1488 and 0x20000<=address and address+size<=0x2d000
    assert not any(n.startswith('ti_mmio_') for n in symbols)
    assert 'ti200_terminal_observe' in symbols and 'ti_head' in symbols
    frames={}
    for p in build.glob('*.su'):
        for line in p.read_text().splitlines():
            location,n,kind=line.split('\t');assert kind=='static'
            frames[location.rsplit(':',1)[1]]=int(n)
    # Separate executed call paths; compiler frame sums are not high-water proofs.
    chains=[['ty_r5_main','ty_service_poll','terminal','output','ty_trace_shared'],
            ['ty_r5_main','ty_service_poll','ti_bridge_core','ti_head'],
            ['ty_r5_main','ty_service_poll','terminal','ty_trace_pl','ty_trace_event']]
    chain_sums=[sum(frames.get(n,0) for n in chain) for chain in chains]
    assert max(chain_sums)<8192
    r={'passed':True,'load_segments':loads,'atcm_bytes':loads[0]['memory_bytes'],
       'btcm_bss_bytes':sec['.bss'][5],'btcm_spare_bytes':0xd000-sec['.bss'][5],
       'trace_address':address,'trace_bytes':size,'shared_bytes':384,
       'compiler_frames':frames,'examined_call_chains':chains,'compiler_frame_sums':chain_sums,
       'stack_note':'Absent names can be inlined; frame sums are not target high-water or WCET evidence',
       'target_executed':False,'wcet_certified':False,
       'linker_warning':'Inherited .shared input PROGBITS/output NOLOAD NOBITS; actual ELF verified NOBITS'}
    (build/'audit.json').write_text(json.dumps(r,indent=2)+'\n')
    return r
