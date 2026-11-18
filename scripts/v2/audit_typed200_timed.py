"""Reuse the frozen ELF audit with an explicit additional 32-byte config ABI."""
from pathlib import Path
import struct,json
ROOT=Path(__file__).resolve().parents[2]
def audit(build):
    source=(ROOT/'scripts/v2/audit_typed200_trace.py').read_text()
    assert source.count("('.shared',0x2f000,384)")==1
    source=source.replace("('.shared',0x2f000,384)","('.shared',0x2f000,416)")
    source=source.replace("'shared_bytes':384","'shared_bytes':416")
    (build/'derived-elf-audit.py').write_text(source)
    ns={'__name__':'timed_derived_audit'};exec(compile(source,'derived-elf-audit.py','exec'),ns)
    r=ns['audit'](build)
    data=(build/'typed200-trace.elf').read_bytes();h=struct.unpack_from('<16sHHIIIIIHHHHHH',data)
    sections=[struct.unpack_from('<10I',data,h[6]+i*h[11]) for i in range(h[12])]
    symbols={}
    for section in sections:
        if section[1]!=2:continue
        strings=sections[section[6]];blob=data[strings[4]:strings[4]+strings[5]]
        for i in range(1,section[5]//section[9]):
            n,val,size,info,other,idx=struct.unpack_from('<IIIBBH',data,section[4]+i*section[9])
            name=blob[n:blob.index(b'\0',n)].decode();symbols[name]=(val,size)
    assert symbols['ty_pmu_config']==(0x2f180,32)
    addr,size=symbols['ty_pmu_evidence'];assert size==72 and 0x20000<=addr and addr+size<=0x2d000
    assert 'ty_pmu_bind' in symbols and 'ty_trace_clock' in symbols
    r.update({'mailbox_bytes':384,'clock_config_address':0x2f180,'clock_config_bytes':32,
              'pmu_evidence_address':addr,'pmu_evidence_bytes':72,
              'counter_read_instructions_compiled':True,'target_executed':False,
              'linker_warning':'Input .shared and new .clock_config PROGBITS mapped to output NOLOAD NOBITS; actual416-byte section verified'})
    (build/'audit.json').write_text(json.dumps(r,indent=2)+'\n')
    return r
