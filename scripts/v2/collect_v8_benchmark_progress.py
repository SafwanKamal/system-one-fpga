"""Read-only v8 sweep snapshot over pinned SSH; no job restart or board writes."""
import argparse
import base64
import getpass
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'build/v2/typed200-amp-candidate-v1/auth-deps'),str(ROOT/'build/v2/board-auth-tools')]
import paramiko


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--dialog',action='store_true');args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    def save(name,value): (args.out/name).write_text(json.dumps(value,indent=2)+'\n')
    client=paramiko.SSHClient();client.load_host_keys(str(Path.home()/'.ssh/known_hosts'));secret=None
    try:
        key=client.get_host_keys().lookup('192.168.0.239')['ssh-ed25519']
        fingerprint=base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        if fingerprint!='EGYkdZirFAYH1XOF2uPZYSzmLMOj7obcj/xAeHIW/Qc':raise RuntimeError('Host key mismatch')
        save('collection-status.json',dict(stage='awaiting_local_authentication'))
        if args.dialog:
            import tkinter as tk
            from tkinter import simpledialog
            root=tk.Tk();root.withdraw()
            secret=simpledialog.askstring('KR260 benchmark progress — read only',
                'SSH password for ubuntu@192.168.0.239\nMemory only; do not enter in chat.',show='*',parent=root)
            root.destroy()
        else:secret=getpass.getpass('KR260 SSH password (RAM only): ')
        if not secret:raise RuntimeError('Authentication cancelled')
        def transport(sock,**kwargs):
            t=paramiko.Transport(sock,**kwargs);o=t.get_security_options()
            o.kex=('curve25519-sha256@libssh.org',);o.key_types=('ssh-ed25519',)
            o.ciphers=('aes128-ctr',);o.digests=('hmac-sha2-256',);return t
        client.connect('192.168.0.239',username='ubuntu',password=secret,look_for_keys=False,
            allow_agent=False,timeout=15,auth_timeout=15,banner_timeout=10,transport_factory=transport)
        secret=None
        remote='/var/lib/sysone/benchmarks/v8-baseline-v1'
        with client.open_sftp() as sftp:
            for name in ('status.json','requests.jsonl','fixture-before.json','fixture-after.json',
                         'summary.json','partial-summary.json','deployment-before.json','deployment-after.json',
                         'run-config.json','resident-startup.json','requests.csv'):
                try:sftp.get(remote+'/results/'+name,str(args.out/name))
                except FileNotFoundError:pass
            sftp.get(remote+'/workloads.json',str(args.out/'workloads.json'))
        stdin,stdout,stderr=client.exec_command(
            'date -u +%Y-%m-%dT%H:%M:%SZ; cat /proc/sys/kernel/random/boot_id; '
            'systemctl show sysone-v8-baseline-v1 --property=ActiveState,SubState,ExecMainStatus,ActiveEnterTimestamp; '
            'journalctl -u sysone-v8-baseline-v1 --no-pager -n 15',timeout=20)
        stdin.channel.shutdown_write()
        (args.out/'board-status.stdout').write_bytes(stdout.read())
        (args.out/'board-status.stderr').write_bytes(stderr.read())
        save('collection-status.json',dict(stage='collected',utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),host_key_sha256=fingerprint))
    except Exception as exc:save('collection-status.json',dict(stage='attention',type=type(exc).__name__,reason=str(exc)))
    finally:secret=None;client.close()


if __name__=='__main__':main()
