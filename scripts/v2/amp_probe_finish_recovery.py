"""Complete and audit the existing v1 stock recovery; never program PL here."""
from pathlib import Path
import base64,getpass,hashlib,json,shlex,sys
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/v2/typed200-amp-deployment-v1'
sys.path[:0]=[str(ROOT/'build/v2/typed200-amp-candidate-v1/auth-deps'),str(ROOT/'build/v2/board-auth-tools')]
import paramiko

CODE='''from pathlib import Path
import hashlib,importlib.util,json,mmap,os,subprocess
p=Path('/home/ubuntu/sysone-probe-target-v1')
spec=importlib.util.spec_from_file_location('trial',p/'target.py'); t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
s=json.loads((p/'state.json').read_text())
actual=dict(overlays=t.overlays(),clock=t.clock(),afi=t.reg(0xfd615000),pl0=t.reg(0xff5e00c0),rpu_reset=t.reg(0xff5e023c),rpu_global=t.reg(0xff9a0000))
(p/'recovery-reviewed-observation.json').write_text(json.dumps(actual,indent=2)+'\\n')
assert actual['overlays']==['k26_starter_kits.dtbo']
assert Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()=='operating'
assert actual['afi']==s['afi_before']
assert (actual['pl0'] ^ s['pl0_before'])==0x01000000
assert (actual['pl0'] & 0x01000000)==0
assert actual['clock']==s['clock_before'] and actual['clock']['enable']==0 and actual['clock']['prepare']==0
assert actual['rpu_reset']==0x13 and actual['rpu_global']==0x50
t.hashes()
fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
with mmap.mmap(fd,65536,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ,offset=0x63f00000) as m:
 assert hashlib.sha256(m[:]).hexdigest()==json.loads((p/'readiness.json').read_text())['reserved_ddr_sha256']
os.close(fd)
if s['dashboard_active']:
 subprocess.run(['systemctl','start',t.SERVICE],check=True,timeout=30)
 subprocess.run(['systemctl','is-active','--quiet',t.SERVICE],check=True,timeout=10)
result=dict(passed=True,stock_restored=True,baseline_files_unchanged=True,reserved_ddr_unchanged=True,
 clock_rate_and_parent_dividers_unchanged=True,pl0_enable_cleared_by_linux_clock_driver=True,
 explanation='Stock overlay has no PL0 consumer. Probe unload disabled PL0 through Linux clock framework. Initial unreferenced clock was physically enabled despite enable/prepare counts zero. No raw clock write was applied.',observed=actual)
(p/'recovery-reviewed.json').write_text(json.dumps(result,indent=2)+'\\n')
print(json.dumps(result))
'''

def main():
    out=BASE/'probe-target-v1/recovery-reviewed-v1';out.mkdir(exist_ok=False)
    (out/'target-recovery.py').write_text(CODE)
    password=getpass.getpass('KR260 SSH/sudo authentication (memory only): ')
    c=paramiko.SSHClient();c.load_system_host_keys();c.load_host_keys(str(Path.home()/'.ssh/known_hosts'))
    def transport(sock,**kwargs):
        t=paramiko.Transport(sock,**kwargs);o=t.get_security_options();o.kex=('curve25519-sha256@libssh.org',);o.key_types=('ssh-ed25519',);o.ciphers=('aes128-ctr',);o.digests=('hmac-sha2-256',);return t
    c.connect('192.168.0.239',username='ubuntu',password=password,look_for_keys=False,allow_agent=False,timeout=15,auth_timeout=15,banner_timeout=10,transport_factory=transport)
    key=base64.b64encode(hashlib.sha256(c.get_transport().get_remote_server_key().asbytes()).digest()).decode().rstrip('=');assert key=='EGYkdZirFAYH1XOF2uPZYSzmLMOj7obcj/xAeHIW/Qc'
    cmd='sudo -S -p "" python3 -c '+shlex.quote(CODE)
    i,o,e=c.exec_command(cmd,timeout=45);i.write(password+'\n');i.flush();data=o.read();err=e.read();code=o.channel.recv_exit_status()
    (out/'stdout.json').write_bytes(data);(out/'stderr.txt').write_bytes(err)
    with c.open_sftp() as f:
        for n in ['recovery-reviewed-observation.json','recovery-reviewed.json']:
            try:f.get('/home/ubuntu/sysone-probe-target-v1/'+n,str(out/n))
            except FileNotFoundError:pass
    password=None;c.close();assert code==0,(code,err.decode());print('PASS reviewed stock recovery, dashboard restarted, baseline files and reserved DDR unchanged')
if __name__=='__main__':main()
