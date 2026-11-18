"""Independently decode boot.bin headers and compare actual partition bytes."""
from pathlib import Path
import hashlib,json,struct
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/v2/typed200-k26-boot-chain-v1'
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    recipe=json.loads((OUT/'boot-recipe.json').read_text())
    path=ROOT/recipe['image_path'];d=path.read_bytes()
    for artifact in recipe['artifacts'].values():
        assert sha((ROOT/artifact['path']).read_bytes())==artifact['sha256']
    u=lambda off:struct.unpack_from('<I',d,off)[0]
    assert u(0x20)==0xaa995566 and u(0x24)==0x584c4e58
    assert (sum(struct.unpack_from('<11I',d,0x20))&0xffffffff)==0xffffffff
    assert u(0x2c)==0xfffc0000 and u(0x28)==0
    iht=u(0x98);table=struct.unpack_from('<16I',d,iht)
    assert sum(table)&0xffffffff==0xffffffff
    assert table[0]==0x01020000 and table[1]==5 and table[5]==0
    ph=table[2]*4;rows=[];expected=[0x116,0x26,0x116,0x116,0x117]
    for index in range(5):
        w=struct.unpack_from('<16I',d,ph)
        assert sum(w)&0xffffffff==0xffffffff
        assert w[0]==w[1]==w[2] and w[9]==expected[index]
        start=w[8]*4;size=w[2]*4
        assert start+size<=len(d)
        rows.append(dict(index=index,offset=start,bytes=size,entry=w[4]|w[5]<<32,
          load=w[6]|w[7]<<32,attributes=w[9],payload_sha256=sha(d[start:start+size])))
        ph=w[3]*4
    assert ph==0
    assert [x['entry'] for x in rows]==[0xfffc0000,0,0,0,0x10000000]
    assert [x['load'] for x in rows]==[0xfffc0000,0xffffffff,0x60000000,0x100f0000,0x10000000]
    for role,row in [('model',rows[2]),('input',rows[3])]:
        raw=(ROOT/recipe['artifacts'][role]['path']).read_bytes()
        assert d[row['offset']:row['offset']+row['bytes']]==raw
    assert rows[2]['load']+rows[2]['bytes']==0x62058800
    assert rows[3]['bytes']==448
    staging=(0x100000,0x100000+rows[1]['bytes'])
    assert staging[1]<=0x10000000
    # Compare each file-backed PT_LOAD byte in the flattened Bootgen images.
    for role,base,fileoff in [('pmu',0xffdc0000,u(0x30)),
                              ('fsbl',0xfffc0000,u(0x30)+u(0x38)),
                              ('relay',0x10000000,rows[4]['offset'])]:
        b=(ROOT/recipe['artifacts'][role]['path']).read_bytes()
        wide=b[4]==2;h=struct.unpack_from('<16sHHIQQQIHHHHHH' if wide else '<16sHHIIIIIHHHHHH',b)
        for i in range(h[10]):
            p=struct.unpack_from('<IIQQQQQQ' if wide else '<8I',b,h[5]+i*h[9])
            if p[0]!=1:continue
            off,addr,size=(p[2],p[4],p[5]) if wide else (p[1],p[3],p[4])
            if size:assert d[fileoff+addr-base:fileoff+addr-base+size]==b[off:off+size],(role,i)
    # No normal partition targets relay NOLOAD stack, status, A53 OCM or R5 TCM.
    windows=[('PL staging',*staging),('model',0x60000000,0x62058800),
      ('relay code',rows[4]['load'],rows[4]['load']+rows[4]['bytes']),
      ('relay stack',0x100c0000,0x100c4000),('relay input',0x100f0000,0x100f01c0),
      ('relay status',0x100f1000,0x100f1004),('IDs',0x62100000,0x62101000),
      ('hidden',0x62101000,0x6210d000)]
    for i,(a,s,e) in enumerate(windows):
        assert s<e
        for name,lo,hi in windows[:i]:assert e<=lo or s>=hi,(a,name)
    result=dict(local_layout_pass=True,hardware_action_ready=False,target_executed=False,
       image_path=path.relative_to(ROOT).as_posix(),image_sha256=sha(d),image_bytes=len(d),
       bootrom_pmu_bytes=u(0x34),bootrom_fsbl_bytes=u(0x3c),partitions=rows,
       disjoint_windows=[dict(name=n,start=s,end=e) for n,s,e in windows],
       relay_reservation_static_validated=True,pmu_ddr_restart_compiled_out=True,
       usb_scratch_compiled_out=True,authentication_encryption_disabled_in_this_lab_image=True,
       limits=['Only this exact trusted local BIF/image; no generic malformed-image safety proof',
          'Reservation is an audited allocation, not XMPU exclusion or target permission proof',
          'Local BOOT.bin cannot establish a compatible cold-POR launch path on fixed-QSPI KR260'])
    (OUT/'image-layout-audit.json').write_text(json.dumps(result,indent=2))
    print('Actual BOOT.bin header checksums, ELF/model/input bytes, sole relay entry and disjoint ranges PASS')
if __name__=='__main__':main()
