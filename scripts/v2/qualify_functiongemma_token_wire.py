"""Qualify proposed uint32 token boundary on host and compile for Cortex-R5."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import zlib

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.functiongemma_token_wire import encode_prompt,decode_prompt


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out=ROOT/'build/v2/functiongemma-token-wire-v1';out.mkdir(parents=True,exist_ok=False)
    sha=bytes(range(32));records=[]
    for ids,reserve in [([0],256),([65535,65536,262143],256),([262143]*1792,256),([65536]*2047,1),([1,50,106],16)]:
        packet=encode_prompt(ids,sha,reserve);assert decode_prompt(packet,sha)==(ids,reserve)
        records.append((0,packet))
    packet=encode_prompt([0,65536,262143],sha)
    for offset in [0,4,6,8,12,16,20,24,28,32,64]:
        changed=bytearray(packet);changed[offset]^=1;records.append((1,bytes(changed)))
    for data in [b'',packet[:63],packet[:-1],packet+b'\0']:
        records.append((1,data))
    for offset,value in [(8,0),(8,0xffffffff),(12,0),(12,257),(24,0xffffffff)]:
        changed=bytearray(packet);struct.pack_into('<I',changed,offset,value);records.append((1,bytes(changed)))
    for token in [262144,262145,0xffffffff]:
        changed=bytearray(packet);struct.pack_into('<I',changed,64,token)
        struct.pack_into('<I',changed,28,zlib.crc32(changed[64:]));records.append((1,bytes(changed)))
    for expected,data in records:
        try:decode_prompt(data,sha);actual=0
        except ValueError:actual=1
        assert expected==actual
    corpus=out/'corpus.hex';corpus.write_text(''.join(f'{s} {p.hex()}\n' for s,p in records),encoding='ascii')
    relative=out.relative_to(ROOT).as_posix();wslroot='/mnt/'+ROOT.drive[0].lower()+ROOT.as_posix()[2:]
    source='firmware/functiongemma_token_v1/token_wire.c'
    harness='firmware/functiongemma_token_v1/test_token_wire.c'
    tool=Path('C:/AMDDesignTools/2025.2/win64/tools/clang-16/bin')
    env=os.environ.copy();env['PATH']='C:/AMDDesignTools/2025.2/Vitis/lib/win64.o;'+str(tool)+';'+env['PATH']
    commands=[['wsl','-d','Ubuntu-24.04','--cd',wslroot,'--','gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-pedantic',
        '-fsanitize=address,undefined','-fno-sanitize-recover=all',source,harness,'-o',relative+'/host-test'],
        ['wsl','-d','Ubuntu-24.04','--cd',wslroot,'--',relative+'/host-test',relative+'/corpus.hex'],
        [str(tool/'clang.exe'),'--target=arm-none-eabi','-mcpu=cortex-r5','-mfloat-abi=soft','-std=c11','-O2',
         '-Wall','-Wextra','-Werror','-pedantic','-ffreestanding','-fno-builtin','-fstack-usage','-c',source,'-o',str(out/'token_wire.o')],
        [str(tool/'llvm-nm.exe'),'--undefined-only',str(out/'token_wire.o')]]
    logs=[]
    for index,command in enumerate(commands):
        run=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=60)
        log=out/f'command-{index}.log';log.write_bytes(run.stdout+run.stderr);logs.append(log)
        if run.returncode:raise RuntimeError('command failed; preserved '+str(log))
    if logs[-1].read_text(encoding='utf-8').strip():raise ValueError('R5 undefined symbol dependencies')
    sources=[Path(__file__),ROOT/source,ROOT/harness,ROOT/'firmware/functiongemma_token_v1/token_wire.h',
        ROOT/'src/sysone/v2/functiongemma_token_wire.py',ROOT/'src/sysone/v2/functiongemma_profile.py',
        ROOT/'tests/test_functiongemma_token_wire.py']
    value=dict(stage='complete',scope='proposed request validation only; no hardware dispatch or target execution',
        board_contacted=False,current_abi_changed=False,cases=len(records),valid=sum(s==0 for s,_ in records),
        rejected=sum(s==1 for s,_ in records),host_sanitizers=['address','undefined'],r5_compile=True,
        undefined_symbols=0,wire_header_bytes=64,token_storage_bits=32,text_vocab=262144,
        source_sha256={str(p.relative_to(ROOT)):digest(p) for p in sources},commands=commands,
        artifacts={p.name:digest(p) for p in out.iterdir() if p.is_file()},
        limits=['caller must own immutable input for view lifetime','CRC is not authentication',
            'no DDR/cache ownership or model dispatch','not a linked/deployed R5 firmware or terminal publication protocol'])
    (out/'qualification.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(stage='complete',cases=value['cases'],host_result=logs[1].read_text(encoding='utf-8').strip(),r5_compile=True)))


if __name__=='__main__':main()
