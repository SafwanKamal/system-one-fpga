"""Read-only probe readiness: saved-key SSH, recovery files and no-map snapshot."""
from pathlib import Path
import argparse,base64,getpass,hashlib,json,re,shlex,struct,sys,time
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/v2/typed200-amp-deployment-v1'
sys.path[:0]=[str(ROOT/'build/v2/typed200-amp-candidate-v1/auth-deps'),str(ROOT/'build/v2/board-auth-tools')]
import paramiko

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);args=ap.parse_args()
 assert re.fullmatch(r'board-readiness-v[0-9]+',args.attempt)
 out=BASE/args.attempt;out.mkdir(exist_ok=False)
 password=getpass.getpass('KR260 SSH/sudo authentication (memory only): ')
 client=paramiko.SSHClient();client.load_system_host_keys();client.load_host_keys(str(Path.home()/'.ssh/known_hosts'))
 def transport(sock,**kwargs):
  t=paramiko.Transport(sock,**kwargs);o=t.get_security_options()
  o.kex=('curve25519-sha256@libssh.org',);o.key_types=('ssh-ed25519',)
  o.ciphers=('aes128-ctr',);o.digests=('hmac-sha2-256',)
  return t
 client.connect('192.168.0.239',username='ubuntu',password=password,look_for_keys=False,allow_agent=False,
                timeout=20,auth_timeout=15,banner_timeout=10,transport_factory=transport)
 key=client.get_transport().get_remote_server_key();finger=base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
 assert finger=='EGYkdZirFAYH1XOF2uPZYSzmLMOj7obcj/xAeHIW/Qc'
 records=[]
 def root(command,name):
  i,o,e=client.exec_command('sudo -S -p "" /bin/sh -c '+shlex.quote(command),timeout=40)
  i.write(password+'\n');i.flush();stdout=o.read();stderr=e.read();code=o.channel.recv_exit_status()
  (out/name).write_bytes(stdout);(out/(name+'.stderr')).write_bytes(stderr)
  records.append(dict(command=command,exit=code,stdout=name))
  assert code==0,(name,stderr.decode(errors='replace'))
  return stdout
 root('xmutil listapps','apps.txt')
 root("for p in $(pgrep -f '^python3 /snap/kria-dashboard/' || true); do cat /proc/$p/cgroup; systemctl status $p --no-pager; done",'dashboard.txt')
 root('command -v xmutil; xmutil -h; command -v dfx-mgr-client; systemctl status dfx-mgr --no-pager; cat /usr/bin/xmutil','fpga-manager.txt')
 root('cat /proc/iomem; cat /sys/kernel/debug/clk/clk_summary','memory-clocks.txt')
 code='''from pathlib import Path
import mmap,os,struct,sys
p=Path('/sys/firmware/devicetree/base/reserved-memory/sysone@60000000')
assert (p/'no-map').exists()
base,size=struct.unpack('>QQ',(p/'reg').read_bytes())
assert base<=0x63f00000 and 0x63f10000<=base+size
fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
with mmap.mmap(fd,65536,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ,offset=0x63f00000) as m:sys.stdout.buffer.write(m[:])
os.close(fd)
'''
 data=root('python3 -c '+shlex.quote(code),'reserved-ddr-before.bin');assert len(data)==65536
 root('python3 -c '+shlex.quote("import os,mmap,struct,json; f=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC); a=[0xfd615000,0xff5e00c0,0xff5e023c,0xff9a0000,0xff9a0100,0xff9a0200]; d={}; exec(\"for x in a:\\n m=mmap.mmap(f,4096,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ,offset=x&~4095); d[hex(x)]=hex(struct.unpack_from('<I',m,x&4095)[0]); m.close()\"); print(json.dumps(d)); os.close(f)"),'ps-registers.json')
 files={}
 with client.open_sftp() as sftp:
  for app,stem in [('k26-starter-kits','k26_starter_kits'),('sysone-v2-attention-context-capture','sysone-v2-attention-context-capture')]:
   dst=out/app;dst.mkdir()
   for name in [stem+'.bit.bin',stem+'.dtbo','shell.json']:
    remote='/lib/firmware/xilinx/'+app+'/'+name;sftp.get(remote,str(dst/name))
    files[remote]=hashlib.sha256((dst/name).read_bytes()).hexdigest()
     
 root('find /sys/kernel/config/device-tree/overlays -maxdepth 2 -name path -exec cat {} \\;','overlays.txt')
 result=dict(passed=True,read_only=True,host_key_sha256=finger,
  observed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),commands=records,
  recovery_files_sha256=files,reserved_ddr_sha256=hashlib.sha256(data).hexdigest(),
  recovery_app='k26-starter-kits',r5_run_ready=False,probe_programmed=False)
 (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n');password=None;client.close()
 print('PASS read-only target readiness snapshots; stock and qualified app files preserved locally; no target write',flush=True)
if __name__=='__main__':main()
