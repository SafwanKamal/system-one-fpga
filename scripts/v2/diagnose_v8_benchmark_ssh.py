"""Quiesce a finite failed benchmark, then accept diagnostic-only queue jobs.

No firmware/model/launcher modifications. Credentials are RAM-only.
"""
import argparse,base64,getpass,hashlib,json,shlex,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'build/v2/typed200-amp-candidate-v1/auth-deps'),str(ROOT/'build/v2/board-auth-tools')]
import paramiko


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=Path,required=True);ap.add_argument('--dialog',action='store_true');args=ap.parse_args()
    w=args.work.resolve();w.mkdir(parents=True,exist_ok=True);(w/'queue').mkdir(exist_ok=True);(w/'results').mkdir(exist_ok=True)
    def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
    client=paramiko.SSHClient();client.load_host_keys(str(Path.home()/'.ssh/known_hosts'));secret=None
    try:
        key=client.get_host_keys().lookup('192.168.0.239')['ssh-ed25519']
        finger=base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        if finger!='EGYkdZirFAYH1XOF2uPZYSzmLMOj7obcj/xAeHIW/Qc':raise RuntimeError('Host key mismatch')
        if args.dialog:
            import tkinter as tk
            from tkinter import simpledialog
            root=tk.Tk();root.withdraw();secret=simpledialog.askstring('KR260 benchmark diagnosis',
                'SSH/sudo password (memory only)\nStop benchmark after FPGA is idle; preserve v8 deployment.',show='*',parent=root);root.destroy()
        else:secret=getpass.getpass('KR260 password (RAM only): ')
        if not secret:raise RuntimeError('Authentication cancelled')
        def transport(sock,**kwargs):
            t=paramiko.Transport(sock,**kwargs);o=t.get_security_options();o.kex=('curve25519-sha256@libssh.org',);o.key_types=('ssh-ed25519',);o.ciphers=('aes128-ctr',);o.digests=('hmac-sha2-256',);return t
        client.connect('192.168.0.239',username='ubuntu',password=secret,look_for_keys=False,allow_agent=False,timeout=15,auth_timeout=15,banner_timeout=10,transport_factory=transport)
        client.get_transport().set_keepalive(30)
        def execute(name,command,timeout=120):
            folder=w/'results'/name;folder.mkdir(exist_ok=False)
            stdin,stdout,stderr=client.exec_command('sudo -k -S -p "" /bin/sh -c '+shlex.quote(command),timeout=15)
            stdin.write(secret+'\n');stdin.flush();stdin.channel.shutdown_write();ch=stdout.channel;start=time.monotonic()
            with (folder/'stdout').open('wb') as a,(folder/'stderr').open('wb') as b:
                while True:
                    while ch.recv_ready():a.write(ch.recv(65536));a.flush()
                    while ch.recv_stderr_ready():b.write(ch.recv_stderr(65536));b.flush()
                    if ch.exit_status_ready() and not ch.recv_ready() and not ch.recv_stderr_ready():code=ch.recv_exit_status();break
                    if time.monotonic()-start>timeout:raise TimeoutError(name+' timed out; do not unload hardware')
                    time.sleep(.05)
            save(folder/'receipt.json',dict(exit=code,seconds=time.monotonic()-start))
            if code:raise RuntimeError(name+' failed; inspect logs')
        quiesce='''import subprocess,time,os,mmap,struct,json
from pathlib import Path
unit='sysone-v8-baseline-v1'
before=subprocess.run(['systemctl','show',unit,'--property=ActiveState,SubState'],capture_output=True,text=True).stdout
if 'ActiveState=active' in before:
 subprocess.run(['systemctl','kill','--kill-whom=all','--signal=SIGSTOP',unit],check=True)
 fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
 with mmap.mmap(fd,4096,mmap.MAP_SHARED,mmap.PROT_READ,offset=0xa0000000) as view:
  deadline=time.monotonic()+130
  while True:
   control=struct.unpack_from('<I',view,0)[0]
   if control&4:
    time.sleep(.2)
    if struct.unpack_from('<I',view,0)[0]&4:break
   if time.monotonic()>deadline:raise RuntimeError('Benchmark frozen but FPGA not idle; no kill/reset')
   time.sleep(.1)
 os.close(fd)
 subprocess.run(['systemctl','kill','--kill-whom=all','--signal=SIGKILL',unit],check=True)
 time.sleep(1)
else:control=None
print(json.dumps(dict(before=before,fpga_idle_control=control,benchmark_processes_terminated=True,linux_boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip())))
'''
        execute('00-quiesce', 'python3 -c '+shlex.quote(quiesce),180)
        with client.open_sftp() as sftp:
            old='/var/lib/sysone/benchmarks/v8-baseline-v1/results'
            for name in ('status.json','requests.jsonl','fixture-before.json','run-config.json'):
                sftp.get(old+'/'+name,str(w/name))
        save(w/'connected.json',dict(connected=True,diagnostic_queue=True))
        deadline=time.monotonic()+7200;done=set()
        while time.monotonic()<deadline:
            if (w/'close-session').exists():return
            for p in sorted((w/'queue').glob('*.json')):
                if p.name in done:continue
                job=json.loads(p.read_text())
                if 'upload' in job:
                    source=Path(job['upload']).resolve();target=job['remote']
                    if not source.is_relative_to(w.parent) or not target.startswith('/home/ubuntu/sysone-v8-diagnosis-'):raise ValueError('Diagnostic upload scope')
                    with client.open_sftp() as sftp:sftp.put(str(source),target)
                    folder=w/'results'/p.stem;folder.mkdir();save(folder/'receipt.json',dict(exit=0,sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
                else:execute(p.stem,job['command'],job.get('timeout',120))
                done.add(p.name)
            time.sleep(.25)
    except Exception as exc:save(w/'attention.json',dict(type=type(exc).__name__,reason=str(exc)))
    finally:secret=None;client.close();save(w/'session-closed.json',dict(closed=True))


if __name__=='__main__':main()
