"""Qwen3 FPGA runtime: CPU byte transfers/tokenization, no CPU model arithmetic.

All embedding, matrix, norm, RoPE, attention, SwiGLU and argmax operations are
issued to the deployed decoder accelerator. No ARM/host inference fallback.
"""
import fcntl
import hashlib
import json
import mmap
import os
from pathlib import Path
import re
import struct
import subprocess
import time

APP='sysone-qwen-decoder'
PAGES=0x1000
DESCRIPTOR=0x2000
OUTPUT=0x3000
ROTARY=0x10000
CACHE=0x400000
SYNC_COMMAND=0x515701


def active_firmware(dt=Path('/sys/firmware/devicetree/base')):
    region=dt/(dt/'__symbols__/fpga_full').read_bytes().rstrip(b'\0').decode().lstrip('/')
    return (region/'firmware-name').read_bytes().rstrip(b'\0').decode()


def bound(node,driver):
    for device in Path('/sys/bus/platform/devices').iterdir():
        of_node=device/'of_node';binding=device/'driver'
        if of_node.exists() and of_node.resolve()==node.resolve():
            return binding.exists() and binding.resolve().name==driver
    return False


def dma_segments():
    lines=Path('/sys/class/misc/sysone_qwen_dma/buffers').read_text().splitlines()
    header={k:int(v,0) for k,v in (s.split('=') for s in lines[0].split())}
    regions=[{k:int(v,0) for k,v in (s.split('=') for s in line.split())} for line in lines[1:]]
    if header['chunk_bytes']!=1<<24 or len(regions)!=header['segments']:
        raise RuntimeError('DMA segment format mismatch')
    return header,regions


class QwenFpga:
    def __init__(self,package):
        self.package=Path(package)
        self.manifest=json.loads((self.package/'model-manifest.json').read_text())
        self.registers=json.loads((self.package/'registers.json').read_text())
        self.commands=0;self.layers=0;self.tokens=0;self.head_rows=0
        self.fd=None;self.dmafd=None;self.regs=None;self.scratch=None
        dt=Path('/sys/firmware/devicetree/base')
        bus=dt/(dt/'__symbols__/amba').read_bytes().rstrip(b'\0').decode().lstrip('/')
        node=bus/'qwen-decoder@a0000000'
        if not node.is_dir() or b'xlnx,qwen-decoder-1.0' not in (node/'compatible').read_bytes().split(b'\0'):
            raise RuntimeError('Qwen FPGA overlay absent; no MMIO attempted')
        if active_firmware(dt)!='sysone-qwen-decoder.bit.bin':
            raise RuntimeError('Wrong active FPGA image')
        if Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()!='operating':
            raise RuntimeError('FPGA not operating')
        if not bound(bus/'qwen-clocking0','xilinx_fclk') or not bound(bus/'qwen-afi','afi-fpga'):
            raise RuntimeError('Qwen clock/AXI configuration drivers are not bound; no MMIO attempted')
        clock=[line.split() for line in Path('/sys/kernel/debug/clk/clk_summary').read_text().splitlines() if line.split() and line.split()[0]=='pl0_ref']
        if len(clock)!=1 or not 49000000<=int(clock[0][4])<=50000000 or not int(clock[0][1]):
            raise RuntimeError('Qwen clock is outside its routed profile')
        self.clock_hz=int(clock[0][4])
        reserved=list((dt/'reserved-memory').glob('sysone@*'))
        if len(reserved)!=1 or not (reserved[0]/'no-map').exists():raise RuntimeError('Scratch reservation absent')
        self.base,self.size=struct.unpack('>QQ',(reserved[0]/'reg').read_bytes())
        if self.size<CACHE+28*2*256*1024*4 or self.base+self.size>0x80000000:
            raise RuntimeError('Scratch/cache extent does not fit the owned reservation')
        header,regions=dma_segments()
        if header['model_bytes']!=self.manifest['bytes']:raise RuntimeError('Wrong DMA model extent')
        self.dmafd=os.open('/dev/sysone_qwen_dma',os.O_RDWR|os.O_SYNC)
        try:
            # Keep the module/file owner pinned for the complete request. Verify
            # model bytes before hardware access; CPU reads here are hashing only.
            digest=hashlib.sha256();started=time.monotonic()
            for region in regions:
                payload=min(1<<24,self.manifest['bytes']-region['index']*(1<<24))
                with mmap.mmap(self.dmafd,region['bytes'],mmap.MAP_SHARED,mmap.PROT_READ|mmap.PROT_WRITE,offset=region['index']*(1<<24)) as view:
                    for offset in range(0,payload,4<<20):digest.update(view[offset:min(offset+(4<<20),payload)])
            if digest.hexdigest()!=self.manifest['sha256']:raise RuntimeError('Resident DMA weights differ from pinned Q8 model')
            self.model_verify_ms=(time.monotonic()-started)*1000
            self.fd=os.open('/dev/mem',os.O_RDWR|os.O_SYNC)
            self.regs=mmap.mmap(self.fd,4096,mmap.MAP_SHARED,mmap.PROT_READ|mmap.PROT_WRITE,offset=0xa0000000)
            self.scratch=mmap.mmap(self.fd,self.size,mmap.MAP_SHARED,mmap.PROT_READ|mmap.PROT_WRITE,offset=self.base)
            table=struct.pack('<'+'I'*len(regions),*[r['dma'] for r in regions]);self._copy_words(PAGES,table)
            rope=(self.package/'rope.bin').read_bytes()
            if len(rope)!=256*128*4:raise RuntimeError('RoPE table extent')
            self._copy_words(ROTARY,rope)
            self._w(self.registers['model'],0);self._w(self.registers['model']+4,0)
            self._w(self.registers['scratch'],self.base);self._w(self.registers['scratch']+4,0)
            self.command(0,page=PAGES,rows=len(regions),token_base=self.manifest['bytes'])
        except Exception:
            self.close();raise

    def _w(self,offset,value):struct.pack_into('<I',self.regs,offset,value)
    def _r(self,offset):return struct.unpack_from('<I',self.regs,offset)[0]
    def _copy_words(self,offset,payload):
        # /dev/mem maps this no-map reservation as device memory. A generic
        # memcpy can emit an unaligned tail store (e.g. a 156-byte page table),
        # which AArch64 rejects. Use aligned scalar transfers for every copy.
        if offset%4 or len(payload)%4:raise ValueError('Unaligned scratch transfer')
        for index,(value,) in enumerate(struct.iter_unpack('<I',payload)):
            struct.pack_into('<I',self.scratch,offset+4*index,value)
    def command(self,cmd,page=0,layer=0,position=0,rows=0,token_base=0):
        if not self._r(0)&4:raise RuntimeError('Decoder is not idle; no request issued')
        values=dict(cmd=cmd,page=page,cache=CACHE,rotary=ROTARY,result=OUTPUT,layer=layer,position=position,rows=rows,token_base=token_base)
        for key,value in values.items():self._w(self.registers[key],value)
        fcntl.ioctl(self.dmafd,SYNC_COMMAND,0)
        self._w(0,1);deadline=time.monotonic()+120
        while not self._r(0)&2:
            if time.monotonic()>deadline:raise TimeoutError('FPGA decoder command timed out; preserve loaded hardware/model for inspection')
            time.sleep(.0005)
        error=self._r(self.registers['status'])
        if error:raise RuntimeError('FPGA decoder status '+str(error))
        self.commands+=1

    def step(self,token,position,logits=False):
        if not 0<=token<151936 or not 0<=position<256:raise ValueError('Token/context profile exceeded')
        self.command(1,page=self.manifest['embedding']+token*1088,position=position)
        for layer,offsets in enumerate(self.manifest['layer_offsets']):
            self._copy_words(DESCRIPTOR,struct.pack('<11I',*offsets))
            self.command(2,page=DESCRIPTOR,layer=layer,position=position);self.layers+=1
        self.tokens+=1
        if logits:return self.select_token()
        return None

    def select_token(self):
        self.command(3,page=self.manifest['output_norm'])
        for start in range(0,151936,8192):
            rows=min(8192,151936-start)
            self.command(4,page=self.manifest['embedding']+start*1088,rows=rows,token_base=start)
            self.head_rows+=rows
        token=struct.unpack_from('<I',self.scratch,OUTPUT)[0]
        if not 0<=token<151936:raise RuntimeError('Invalid FPGA vocabulary result')
        return token

    def block_fixture(self,token,position,layer=0):
        self.command(1,page=self.manifest['embedding']+token*1088,position=position)
        self._copy_words(DESCRIPTOR,struct.pack('<11I',*self.manifest['layer_offsets'][layer]))
        self.command(2,page=DESCRIPTOR,layer=layer,position=position)
        self.command(5)
        return bytes(self.scratch[OUTPUT:OUTPUT+4096])

    def close(self):
        for key in ['scratch','regs']:
            value=getattr(self,key,None)
            if value is not None:value.close();setattr(self,key,None)
        for key in ['fd','dmafd']:
            value=getattr(self,key,None)
            if value is not None:os.close(value);setattr(self,key,None)


SYSTEM='You call tools. Available function: read_linux_file(path: string). Return only a JSON object with keys "name" and "arguments". Copy the file path from the request.'

def prompt_for(query):
    return '<|im_start|>system\n'+SYSTEM+'<|im_end|>\n<|im_start|>user\n'+query+'<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'


def execute_generated(text):
    value=text.strip()
    if value.startswith('```json\n') and value.endswith('```'):value=value[8:-3].strip()
    elif value.startswith('```\n') and value.endswith('```'):value=value[4:-3].strip()
    call=json.loads(value)
    if type(call) is not dict or set(call)!={'name','arguments'} or call['name']!='read_linux_file':raise ValueError('Unregistered generated command')
    args=call['arguments']
    if type(args) is not dict or set(args)!={'path'} or args['path'] not in ['/proc/sys/kernel/random/boot_id','/proc/uptime','/proc/version']:raise ValueError('Unregistered Linux file argument')
    result=Path(args['path']).read_text(encoding='utf-8').strip()
    if not result or len(result)>4096:raise ValueError('Unexpected system file result')
    return call,dict(path=args['path'],text=result,executed=True)
