"""Execute an explicit local command plan over pinned SSH; secrets stay in memory."""
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
sys.path[:0] = [str(ROOT / 'build/v2/typed200-amp-candidate-v1/auth-deps'),
               str(ROOT / 'build/v2/board-auth-tools')]
import paramiko


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    plan = json.loads(args.plan.read_text())
    args.out.mkdir(exist_ok=False)
    client = paramiko.SSHClient()
    client.load_host_keys(str(Path.home() / '.ssh/known_hosts'))
    keys = client.get_host_keys().lookup('192.168.0.239')
    assert keys and 'ssh-ed25519' in keys
    finger = base64.b64encode(hashlib.sha256(keys['ssh-ed25519'].asbytes()).digest()).decode().rstrip('=')
    assert finger == 'EGYkdZirFAYH1XOF2uPZYSzmLMOj7obcj/xAeHIW/Qc'

    def transport(sock, **kwargs):
        t = paramiko.Transport(sock, **kwargs)
        o = t.get_security_options()
        o.kex = ('curve25519-sha256@libssh.org',)
        o.key_types = ('ssh-ed25519',)
        o.ciphers = ('aes128-ctr',)
        o.digests = ('hmac-sha2-256',)
        return t

    password = getpass.getpass('KR260 SSH/sudo password (memory only): ')
    results = []
    try:
        client.connect('192.168.0.239', username='ubuntu', password=password,
                       look_for_keys=False, allow_agent=False, timeout=15,
                       auth_timeout=15, banner_timeout=10, transport_factory=transport)
        client.get_transport().set_keepalive(30)
        print('Saved-key SSH authenticated', flush=True)
        for item in plan['commands']:
            if 'upload' in item:
                with client.open_sftp() as sftp:
                    with sftp.open(item['remote'], 'wx') as remote:
                        with Path(item['upload']).open('rb') as local:
                            while chunk := local.read(262144):remote.write(chunk)
                results.append(dict(name=item['name'], exit=0))
                print(item['name']+': 0',flush=True)
                continue
            command = item['command']
            if item.get('root'):
                command = 'sudo -S -p "" /bin/sh -c ' + shlex.quote(command)
            i, o, e = client.exec_command(command, timeout=10)
            if item.get('root'):
                i.write(password + '\n')
                i.flush()
            i.channel.shutdown_write()
            channel = o.channel
            start = time.monotonic()
            timeout = item.get('timeout', 45)
            with (args.out / (item['name'] + '.stdout')).open('wb') as stdout, \
                 (args.out / (item['name'] + '.stderr')).open('wb') as stderr:
                while True:
                    while channel.recv_ready():
                        stdout.write(channel.recv(65536))
                        stdout.flush()
                    while channel.recv_stderr_ready():
                        stderr.write(channel.recv_stderr(65536))
                        stderr.flush()
                    if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                        code = channel.recv_exit_status()
                        break
                    if time.monotonic() - start > timeout:
                        channel.close()
                        code = 'timeout'
                        break
                    time.sleep(.05)
            results.append(dict(name=item['name'], exit=code, elapsed_seconds=round(time.monotonic()-start, 3)))
            (args.out / 'commands.json').write_text(json.dumps(results, indent=2) + '\n')
            print(item['name'] + ': ' + str(code), flush=True)
            if code != 0:
                raise RuntimeError('command failed; inspect retained stdout/stderr and exact status')
        (args.out / 'receipt.json').write_text(json.dumps(dict(passed=True, host_key_sha256=finger,
                           commands=results, observed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())), indent=2)+'\n')
    except Exception as exc:
        (args.out / 'failure.json').write_text(json.dumps(dict(passed=False, error_type=type(exc).__name__, commands=results), indent=2)+'\n')
        raise
    finally:
        password = None
        client.close()


if __name__ == '__main__':
    main()
