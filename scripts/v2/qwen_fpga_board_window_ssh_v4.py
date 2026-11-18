"""User-authorized Qwen FPGA deployment board window; SSH secret stays in RAM only.

Run interactively. Numbered local jobs allow preparation after read-only inventory
without another login. No task scheduler/daemon; expires after four hours.
"""
import argparse
import base64
import getpass
import hashlib
import json
from pathlib import Path
import re
import shlex
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'build/v2/typed200-amp-candidate-v1/auth-deps'),str(ROOT/'build/v2/board-auth-tools')]
import paramiko


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--work',type=Path,required=True);args=ap.parse_args()
    work=args.work.resolve();(work/'queue').mkdir(exist_ok=True);(work/'results').mkdir(exist_ok=True)
    client=paramiko.SSHClient();client.load_host_keys(str(Path.home()/'.ssh/known_hosts'))
    keys=client.get_host_keys().lookup('192.168.0.239')
    if not keys or 'ssh-ed25519' not in keys:raise RuntimeError('pinned host key unavailable')
    finger=base64.b64encode(hashlib.sha256(keys['ssh-ed25519'].asbytes()).digest()).decode().rstrip('=')
    if finger!='EGYkdZirFAYH1XOF2uPZYSzmLMOj7obcj/xAeHIW/Qc':raise RuntimeError('host key differs')
    def transport(sock,**kwargs):
        t=paramiko.Transport(sock,**kwargs);o=t.get_security_options()
        o.kex=('curve25519-sha256@libssh.org',);o.key_types=('ssh-ed25519',)
        o.ciphers=('aes128-ctr',);o.digests=('hmac-sha2-256',);return t
    password=getpass.getpass('KR260 SSH/sudo password (memory only; never enter in chat): ')
    try:
        client.connect('192.168.0.239',username='ubuntu',password=password,look_for_keys=False,allow_agent=False,
            timeout=15,auth_timeout=15,banner_timeout=10,transport_factory=transport)
        client.get_transport().set_keepalive(30)
        (work/'connected.json').write_text(json.dumps(dict(connected=True,host_key_sha256=finger))+'\n')
        print('Authenticated. Qwen FPGA deployment queue is ready; credentials remain in RAM.',flush=True)
        done={p.name+'.json' for p in (work/'results').iterdir() if p.is_dir() and (p/'receipt.json').exists()}
        expires=time.monotonic()+14400
        while time.monotonic()<expires:
            if (work/'close-session').exists():break
            for path in sorted((work/'queue').glob('*.json')):
                if path.name in done:continue
                if not re.fullmatch(r'\d{2}-[a-z0-9-]+\.json',path.name):raise ValueError('job filename')
                job=json.loads(path.read_text(encoding='utf-8'));out=work/'results'/path.stem;out.mkdir(exist_ok=False)
                start=time.monotonic();code=0
                if job.get('close'):
                    (out/'receipt.json').write_text(json.dumps(dict(exit=0,session_closed=True))+'\n')
                    print('FPGA deployment queue completed; closing login.',flush=True)
                    return
                if 'upload' in job:
                    local=Path(job['upload']).resolve()
                    if local!=ROOT/'build/v2/qwen-fpga-decoder-v5/qwen-fpga-deployment.tar':raise ValueError('upload outside fixed FPGA deployment archive')
                    with client.open_sftp() as sftp:
                        with sftp.open(job['remote'],'wx') as remote:
                            with local.open('rb') as source:
                                for block in iter(lambda:source.read(262144),b''):remote.write(block)
                else:
                    command=job['command']
                    if job.get('root'):command='sudo -k -S -p "" /bin/sh -c '+shlex.quote(command)
                    stdin,stdout,stderr=client.exec_command(command,timeout=10)
                    if job.get('root'):stdin.write(password+'\n');stdin.flush()
                    stdin.channel.shutdown_write();channel=stdout.channel
                    with (out/'stdout').open('wb') as a,(out/'stderr').open('wb') as b:
                        while True:
                            while channel.recv_ready():a.write(channel.recv(65536));a.flush()
                            while channel.recv_stderr_ready():b.write(channel.recv_stderr(65536));b.flush()
                            if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                                code=channel.recv_exit_status();break
                            if time.monotonic()-start>job.get('timeout',60):
                                channel.close();code='timeout';break
                            time.sleep(.05)
                (out/'receipt.json').write_text(json.dumps(dict(exit=code,elapsed_seconds=time.monotonic()-start))+'\n')
                print(path.stem+': '+str(code),flush=True);done.add(path.name)
                if code!=0:
                    (work/'attention.json').write_text(json.dumps(dict(job=path.name,exit=code))+'\n')
                    print('Paused after a failed job; retained logs and login. Waiting for an explicit local resume marker.',flush=True)
                    marker=work/'resume-after-failure'
                    while not marker.exists():
                        if (work/'close-session').exists() or time.monotonic()>expires:return
                        time.sleep(.25)
                    marker.unlink()
                    break # re-enumerate queue after an explicit repair
            time.sleep(.25)
    finally:
        password=None;client.close()
        print('SSH session closed; no credential saved.',flush=True)


if __name__=='__main__':main()
