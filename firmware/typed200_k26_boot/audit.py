"""Audit the exact generated boot ELFs, effective macros, and reserved ranges."""
from pathlib import Path
import hashlib,json,re,struct,subprocess
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/v2/typed200-k26-boot-chain-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def elf(path):
    d=path.read_bytes();assert d[:4]==b'\x7fELF' and d[5]==1
    is64=d[4]==2
    h=struct.unpack_from('<16sHHIQQQIHHHHHH' if is64 else '<16sHHIIIIIHHHHHH',d)
    loads=[]
    for i in range(h[10]):
        p=struct.unpack_from('<IIQQQQQQ' if is64 else '<8I',d,h[5]+i*h[9])
        typ,flags,off,va,pa,fs,ms,align=p if is64 else (p[0],p[6],p[1],p[2],p[3],p[4],p[5],p[7])
        if typ==1:
            assert fs<=ms and off+fs<=len(d)
            loads.append(dict(address=pa,filesz=fs,memsz=ms,flags=flags,end=pa+ms))
    sections=[struct.unpack_from('<IIQQQQIIQQ' if is64 else '<10I',d,h[6]+i*h[11]) for i in range(h[12])]
    shstr=sections[h[13]];names=d[shstr[4]:shstr[4]+shstr[5]]
    sec={names[s[0]:].split(b'\0')[0].decode():s for s in sections}
    cfg=None
    if '.sys_cfg_data' in sec:
        s=sec['.sys_cfg_data'];raw=d[s[4]:s[4]+s[5]]
        (OUT/'pm-config-object.bin').write_bytes(raw)
        cfg=dict(address=s[3],bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                 words=list(struct.unpack('<'+'I'*(len(raw)//4),raw)))
    return dict(path=str(path.relative_to(ROOT)),sha256=sha(path),machine=h[2],entry=h[4],loads=loads,config=cfg)
def macros(app,file):
    entries=json.loads((OUT/app/'build/compile_commands.json').read_text())
    entry=next(x for x in entries if Path(x['file']).name==file)
    command=re.sub(r' -o .*? -c ', ' -dM -E ', entry['command'])
    result=subprocess.run(command,cwd=entry['directory'],capture_output=True,text=True,check=True)
    (OUT/f'{app}-effective-macros.txt').write_text(result.stdout)
    result2=subprocess.run(command.replace(' -dM -E ',' -E '),cwd=entry['directory'],capture_output=True,text=True,check=True)
    (OUT/f'{app}-preprocessed.c').write_text(result2.stdout)
    return dict(re.findall(r'^#define (\w+)(?: (.*))?$',result.stdout,re.M))
fsbl=elf(OUT/'app-fsbl-v1/build/typed200_fsbl.elf')
pmu=elf(OUT/'app-pmu-v1/build/typed200_pmufw.elf')
relay=elf(ROOT/'build/v2/typed200-boot-relay-v1/relay.elf')
assert fsbl['machine']==183 and pmu['machine']==189 and relay['entry']==0x10000000
assert all(0xfffc0000<=s['address']<=s['end']<=0x100000000 for s in fsbl['loads'])
assert all(0xffdc0000<=s['address']<=s['end']<=0xffddfae0 for s in pmu['loads'])
assert all(0x10000000<=s['address']<=s['end']<=0x100f0000 for s in relay['loads'])
f=macros('app-fsbl-v1','xfsbl_handoff.c');p=macros('app-pmu-v1','xpfw_core.c')
for n in ['K26_SOM','ENABLE_EM','ENABLE_MOD_OVERTEMP','ENABLE_PM','ENABLE_SCHEDULER']:
    assert n in p,n
for n in ['ENABLE_FPGA_LOAD','ENABLE_FPGA_READ_CONFIG_DATA','ENABLE_FPGA_READ_CONFIG_REG',
          'USE_DDR_FOR_APU_RESTART','ENABLE_RECOVERY','ENABLE_WDT','ENABLE_DDR_SR_WR',
          'ENABLE_RPU_RUN_MODE','ENABLE_UNUSED_RPU_PWR_DWN']:
    assert n not in p,n
assert p['OVERTEMP_DEGC']=='(90.0f)' or '90.0' in p['OVERTEMP_DEGC']
assert 'XFSBL_EARLY_HANDOFF' not in f and 'XFSBL_USB' not in f
assert 'XFSBL_SECURE' in f and 'XFSBL_BS' in f and 'K26_SOM' in f
pre=(OUT/'app-pmu-v1-preprocessed.c').read_text()
for text in ['TypedBootEvent(&CorePtr->ModList[Idx], EventId)',
             'TypedBootIpi(IpiNum,','!TypedBootClosed()','TypedBootService();']:
    assert text in pre,text
ps=OUT/'app-fsbl-v1/src/psu_init.c'
assert sha(ps)==sha(ROOT/'firmware/typed200_mvp/reference/psu_init.c')
# Firmware copy-to-DDR restart is compiled out; all static scratch is in ELF ranges.
# PL staging remains dynamic: its exact bounded size is checked in boot recipe audit.
result=dict(local_pass=True,target_execution=False,hardware_qualified=False,wcet_certified=False,
    fsbl=fsbl,pmu=pmu,relay=relay,ps_init_sha256=sha(ps),
    reservation=dict(start=0x10000000,end=0x10100000,input_start=0x100f0000,
      input_end=0x100f01c0,status_start=0x100f1000,status_end=0x100f1004,
      usb_scratch_compiled_out=True,pmu_ddr_restart_compiled_out=True,
      bitstream_staging_start=0x100000,bitstream_staging_limit=0x10000000,
      dynamic_partition_audit_pending=True),
    limits=['Static ELF ranges and actual macros only; validate exact boot partitions next',
       'Debug/BootROM remain trusted; no hostile-master firewall or target proof'])
(OUT/'boot-binary-audit.json').write_text(json.dumps(result,indent=2))
print('Boot ELF / effective macro / static reservation audit PASS')
print('FSBL config object:',fsbl['config']['bytes'],'bytes')
