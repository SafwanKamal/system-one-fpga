"""Finite benchmark SSH session. Password stays in RAM; deployment is read-only.

Windows can use --dialog for a masked local authentication dialog. The only
uploaded archive is the new benchmark package. No overlay or launcher changes.
"""
import argparse
import base64
import getpass
import hashlib
import json
from pathlib import Path
import shlex
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'build/v2/typed200-amp-candidate-v1/auth-deps'),
               str(ROOT/'build/v2/board-auth-tools')]
import paramiko

REMOTE = '/var/lib/sysone/benchmarks/v8-baseline-v1'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', type=Path, required=True)
    ap.add_argument('--dialog', action='store_true')
    args = ap.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    client = paramiko.SSHClient()
    client.load_host_keys(str(Path.home()/'.ssh/known_hosts'))
    secret = None
    def save(name, value):
        (work/name).write_text(json.dumps(value, indent=2)+'\n')
    try:
        key = client.get_host_keys().lookup('192.168.0.239')['ssh-ed25519']
        fingerprint = base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        if fingerprint != 'EGYkdZirFAYH1XOF2uPZYSzmLMOj7obcj/xAeHIW/Qc':
            raise RuntimeError('Pinned host key mismatch')
        if args.dialog:
            import tkinter as tk
            from tkinter import simpledialog
            root = tk.Tk(); root.withdraw()
            secret = simpledialog.askstring('KR260 benchmark authentication',
                'SSH/sudo password for ubuntu@192.168.0.239\n'
                'Stored in memory only. Do not enter it in chat.', show='*', parent=root)
            root.destroy()
        else:
            secret = getpass.getpass('KR260 SSH/sudo password (RAM only): ')
        if not secret:
            save('attention.json', {'stage': 'authentication', 'reason': 'No password supplied'})
            return
        def transport(sock, **kwargs):
            t = paramiko.Transport(sock, **kwargs); options = t.get_security_options()
            options.kex = ('curve25519-sha256@libssh.org',)
            options.key_types = ('ssh-ed25519',)
            options.ciphers = ('aes128-ctr',); options.digests = ('hmac-sha2-256',)
            return t
        client.connect('192.168.0.239', username='ubuntu', password=secret,
            look_for_keys=False, allow_agent=False, timeout=15, auth_timeout=15,
            banner_timeout=10, transport_factory=transport)
        client.get_transport().set_keepalive(30)

        def execute(name, command, root=False, limit=60):
            if root:
                command = 'sudo -k -S -p "" /bin/sh -c '+shlex.quote(command)
            stdin, stdout, stderr = client.exec_command(command, timeout=15)
            if root:
                stdin.write(secret+'\n'); stdin.flush()
            stdin.channel.shutdown_write()
            channel = stdout.channel; started = time.monotonic()
            with (work/(name+'.stdout')).open('wb') as a, (work/(name+'.stderr')).open('wb') as b:
                while True:
                    while channel.recv_ready(): a.write(channel.recv(65536)); a.flush()
                    while channel.recv_stderr_ready(): b.write(channel.recv_stderr(65536)); b.flush()
                    if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                        code = channel.recv_exit_status(); break
                    if time.monotonic()-started > limit:
                        raise TimeoutError(name+' did not finish; do not reset the FPGA')
                    time.sleep(.1)
            save(name+'.receipt.json', {'exit': code, 'seconds': time.monotonic()-started})
            if code:
                raise RuntimeError(name+' failed; inspect its logs')

        execute('inventory', "cat /proc/sys/kernel/random/boot_id; uname -r; "
            "cat /sys/class/fpga_manager/fpga0/state; "
            "cat /sys/class/misc/sysone_qwen_dma/buffers; "
            "cat /usr/local/bin/sysone-qwen-fpga")
        save('connected.json', {'host_key_sha256': fingerprint, 'connected': True})
        deadline = time.monotonic()+14400
        while not (work/'upload-ready.json').exists():
            if (work/'close-session').exists(): return
            if time.monotonic()>deadline: raise TimeoutError('Benchmark preparation window expired')
            time.sleep(.5)
        ready = json.loads((work/'upload-ready.json').read_text())
        archive = work/'benchmark.tar'
        if hashlib.sha256(archive.read_bytes()).hexdigest() != ready['sha256']:
            raise RuntimeError('Benchmark archive hash mismatch')
        upload = '/home/ubuntu/sysone-v8-baseline-v1.tar'
        with client.open_sftp() as sftp:
            with sftp.open(upload, 'wx') as target, archive.open('rb') as source:
                for block in iter(lambda: source.read(262144), b''): target.write(block)
        code = ("import hashlib,tarfile;from pathlib import Path;"
            f"a=Path({upload!r});assert hashlib.sha256(a.read_bytes()).hexdigest()=={ready['sha256']!r};"
            f"p=Path({REMOTE!r});p.mkdir(parents=True,exist_ok=False);"
            "t=tarfile.open(a);t.extractall(p,filter='data');t.close()")
        execute('extract', 'python3 -c '+shlex.quote(code), root=True)
        # systemd launches one finite process, not a scheduler or recurring service.
        # It survives an SSH disconnect and retains its own append-only records.
        command = (f"systemd-run --unit=sysone-v8-baseline-v1 --collect "
            f"--property=WorkingDirectory={REMOTE} --setenv=PYTHONDONTWRITEBYTECODE=1 "
            f"/usr/bin/python3 -u {REMOTE}/scripts/v2/run_v8_benchmark.py "
            f"--package /var/lib/sysone/qwen-fpga-decoder-v8-startup-v2 "
            f"--out {REMOTE}/results --manifest {REMOTE}/workloads.json")
        execute('start', command, root=True)
        save('started.json', {'remote': REMOTE, 'unit': 'sysone-v8-baseline-v1', 'recurring': False})
        # The finite job outlives this connection. Mirror progress while connected;
        # credentials are no longer needed after initial privileged setup.
        time.sleep(10)
        execute('initial-progress', f"cat {REMOTE}/results/status.json; "
            "systemctl show sysone-v8-baseline-v1 --property=ActiveState,SubState", root=True)
        secret = None
        local_results = work.parent/'results'
        local_results.mkdir(exist_ok=True)
        with client.open_sftp() as sftp:
            offset = 0
            while time.monotonic() < deadline:
                try:
                    with sftp.open(REMOTE+'/results/status.json') as source:
                        state = json.loads(source.read())
                    save('progress.json',state)
                    for name in ('status.json','fixture-before.json','fixture-after.json',
                                 'summary.json','partial-summary.json','deployment-before.json',
                                 'deployment-after.json','run-config.json','requests.csv'):
                        try: sftp.get(REMOTE+'/results/'+name,str(local_results/name))
                        except FileNotFoundError: pass
                    try:
                        with sftp.open(REMOTE+'/results/requests.jsonl') as source:
                            source.seek(offset); data=source.read()
                        if data:
                            with (local_results/'requests.jsonl').open('ab') as target:target.write(data)
                            offset += len(data)
                    except FileNotFoundError: pass
                    if state['stage'] in ('complete','attention'):
                        # Preserve every per-request artifact after the finite job.
                        target=local_results/'requests';target.mkdir(exist_ok=True)
                        for name in sftp.listdir(REMOTE+'/results/requests'):
                            sftp.get(REMOTE+'/results/requests/'+name,str(target/name))
                        save('collected.json',dict(stage=state['stage'],bytes_jsonl=offset))
                        return
                except FileNotFoundError:
                    pass
                time.sleep(20)
            save('collection-window-ended.json',dict(remote=REMOTE,job_may_still_be_running=True))
    except Exception as exc:
        save('attention.json', {'type': type(exc).__name__, 'reason': str(exc)})
    finally:
        secret = None; client.close()
        save('session-closed.json', {'closed': True})


if __name__ == '__main__':
    main()
