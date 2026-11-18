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

APP='sysone-qwen-decoder-batch'
PAGES=0x1000
DESCRIPTOR=0x2000
OUTPUT=0x3000
ROTARY=0x10000
CACHE=0x400000
SYNC_COMMAND=0x515701
CACHE_TAG=0x80


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
    def __init__(self,package,preserve_prefix=False):
        self.package=Path(package)
        self.manifest=json.loads((self.package/'model-manifest.json').read_text())
        self.registers=json.loads((self.package/'registers.json').read_text())
        self.commands=0;self.layers=0;self.tokens=0;self.head_rows=0;self.command_timing={};self.prefill_groups=0;self.prefill_tokens=0;self.layer_weight_passes=0
        self.fd=None;self.dmafd=None;self.regs=None;self.scratch=None
        dt=Path('/sys/firmware/devicetree/base')
        bus=dt/(dt/'__symbols__/amba').read_bytes().rstrip(b'\0').decode().lstrip('/')
        node=bus/'qwen-decoder@a0000000'
        if not node.is_dir() or b'xlnx,qwen-decoder-batch-1.0' not in (node/'compatible').read_bytes().split(b'\0'):
            raise RuntimeError('Qwen FPGA overlay absent; no MMIO attempted')
        if active_firmware(dt)!=APP+'.bit.bin':
            raise RuntimeError('Wrong active FPGA image')
        if Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()!='operating':
            raise RuntimeError('FPGA not operating')
        if not bound(bus/'qwen-clocking0','xilinx_fclk') or not bound(bus/'qwen-afi','afi-fpga'):
            raise RuntimeError('Qwen clock/AXI configuration drivers are not bound; no MMIO attempted')
        clock=[line.split() for line in Path('/sys/kernel/debug/clk/clk_summary').read_text().splitlines() if line.split() and line.split()[0]=='pl0_ref']
        if len(clock)!=1 or not 99000000<=int(clock[0][4])<=100000000 or not int(clock[0][1]):
            raise RuntimeError('Qwen clock is outside its routed profile')
        self.clock_hz=int(clock[0][4])
        self.prefix_identity=dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),overlay_inode=node.stat().st_ino,dma_inode=Path('/sys/class/misc/sysone_qwen_dma/buffers').stat().st_ino,model_sha256=self.manifest['sha256'],kernel_sha256=json.loads((self.package/APP/'build.json').read_text())['bitstream_sha256'],runtime_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),rope_sha256=hashlib.sha256((self.package/'rope.bin').read_bytes()).hexdigest(),manifest_sha256=hashlib.sha256((self.package/'model-manifest.json').read_bytes()).hexdigest())
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
            if not preserve_prefix:self._copy_words(CACHE_TAG,bytes(32))
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
    def begin_prefix(self,prompt_ids,enabled=True):
        """Reuse only causally identical prompt KV; always recompute output tokens."""
        state=self.package/'prefix-cache.json';matched=0
        old_tag=bytes(self.scratch[CACHE_TAG:CACHE_TAG+32]).hex()
        if enabled and state.exists():
            try:
                previous=json.loads(state.read_text())
                if previous['identity']==self.prefix_identity and previous['tag']==old_tag:
                    for old,new in zip(previous['prompt_ids'],prompt_ids):
                        if old!=new:break
                        matched+=1
            except (OSError,ValueError,KeyError,TypeError):pass
        # Hidden activation is overwritten during decode; re-evaluate the final
        # prompt token even for an identical request to obtain fresh logits.
        matched=min(matched,len(prompt_ids)-1)
        tag=os.urandom(32);self._copy_words(CACHE_TAG,tag)
        fcntl.ioctl(self.dmafd,SYNC_COMMAND,0)
        self.pending_prefix=dict(identity=self.prefix_identity,tag=tag.hex(),prompt_ids=prompt_ids)
        return matched
    def commit_prefix(self):
        # Called only after successful model completion and tool validation.
        state=self.package/'prefix-cache.json';temp=state.with_suffix('.new')
        temp.write_text(json.dumps(self.pending_prefix)+'\n');os.replace(temp,state)
    def command(self,cmd,page=0,layer=0,position=0,rows=0,token_base=0):
        if not self._r(0)&4:raise RuntimeError('Decoder is not idle; no request issued')
        values=dict(cmd=cmd,page=page,cache=CACHE,rotary=ROTARY,result=OUTPUT,layer=layer,position=position,rows=rows,token_base=token_base)
        for key,value in values.items():self._w(self.registers[key],value)
        fcntl.ioctl(self.dmafd,SYNC_COMMAND,0)
        started=time.monotonic();self._w(0,1);deadline=started+120
        while not self._r(0)&2:
            if time.monotonic()>deadline:raise TimeoutError('FPGA decoder command timed out; preserve loaded hardware/model for inspection')
            time.sleep(.0005)
        error=self._r(self.registers['status'])
        if error:raise RuntimeError('FPGA decoder status '+str(error))
        elapsed=time.monotonic()-started
        item=self.command_timing.setdefault(str(cmd),dict(calls=0,seconds=0.0))
        item['calls']+=1;item['seconds']+=elapsed
        self.commands+=1

    def step(self,token,position,logits=False):
        if not 0<=token<151936 or not 0<=position<256:raise ValueError('Token/context profile exceeded')
        self.command(1,page=self.manifest['embedding']+token*1088,position=position)
        for layer,offsets in enumerate(self.manifest['layer_offsets']):
            self._copy_words(DESCRIPTOR,struct.pack('<11I',*offsets))
            self.command(2,page=DESCRIPTOR,layer=layer,position=position);self.layers+=1;self.layer_weight_passes+=1
        self.tokens+=1
        if logits:return self.select_token()
        return None

    def prefill_batch(self,ids,position,logits=False):
        count=len(ids)
        if not 1<=count<=4 or not 0<=position<=256-count or any(not 0<=token<151936 for token in ids):raise ValueError('Batch/context profile exceeded')
        self._copy_words(0x2100,struct.pack('<'+'I'*count,*[self.manifest['embedding']+token*1088 for token in ids]))
        self.command(7,page=0x2100,rows=count,position=position)
        for layer,offsets in enumerate(self.manifest['layer_offsets']):
            self._copy_words(DESCRIPTOR,struct.pack('<11I',*offsets))
            self.command(8,page=DESCRIPTOR,layer=layer,position=position,rows=count)
            self.layers+=count;self.layer_weight_passes+=1
        self.tokens+=count;self.prefill_tokens+=count;self.prefill_groups+=1
        if logits:
            if count>1:self.command(9,layer=count-1)
            return self.select_token()
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
