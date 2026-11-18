"""One reserved, pinned SSH qualification session. Password is RAM-only."""
import argparse
import base64
from datetime import datetime,timezone
import getpass
import hashlib
import json
from pathlib import Path
import shlex
import sys
import time
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'build/v2/typed200-amp-candidate-v1/auth-deps'),str(ROOT/'build/v2/board-auth-tools')]
sys.path.insert(0,str(ROOT/'src'))
import paramiko
from board_status import transact
from run_v8_chain_pilot_v5 import dump
from sysone.v2.retention_comparison_v13 import VERSION

REMOTE='/var/lib/sysone/benchmarks/'+VERSION
PACKAGE='/var/lib/sysone/qwen-fpga-decoder-v9d-candidate1'
V8_PACKAGE='/var/lib/sysone/qwen-fpga-decoder-v8-startup-v2'
UNIT='sysone-'+VERSION


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--claim',required=True);args=ap.parse_args()
    work=ROOT/'build/v2'/VERSION/'evaluation';board=work/'board';board.mkdir(exist_ok=False)
    status=transact(ROOT/'BOARD_STATUS.json','show')
    if not status.get('reservation') or status['reservation']['claim_id']!=args.claim:raise RuntimeError('Claim is not held')
    client=paramiko.SSHClient();client.load_host_keys(str(Path.home()/'.ssh/known_hosts'))
    key=client.get_host_keys().lookup('192.168.0.239')['ssh-ed25519']
    fingerprint=base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
    if fingerprint!='EGYkdZirFAYH1XOF2uPZYSzmLMOj7obcj/xAeHIW/Qc':raise RuntimeError('Pinned SSH host key differs')
    def transport(sock,**kwargs):
        t=paramiko.Transport(sock,**kwargs);o=t.get_security_options()
        o.kex=('curve25519-sha256@libssh.org',);o.key_types=('ssh-ed25519',)
        o.ciphers=('aes128-ctr',);o.digests=('hmac-sha2-256',);return t
    password=getpass.getpass('KR260 SSH/sudo password (RAM only): ')
    def execute(name,command,root=False,limit=60):
        if root:command='sudo -k -S -p "" /bin/sh -c '+shlex.quote(command)
        stdin,stdout,stderr=client.exec_command(command,timeout=15)
        if root:stdin.write(password+'\n');stdin.flush()
        stdin.channel.shutdown_write();channel=stdout.channel;tick=time.monotonic()
        with (board/(name+'.stdout')).open('wb') as a,(board/(name+'.stderr')).open('wb') as b:
            while True:
                while channel.recv_ready():a.write(channel.recv(65536));a.flush()
                while channel.recv_stderr_ready():b.write(channel.recv_stderr(65536));b.flush()
                if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                    code=channel.recv_exit_status();break
                if time.monotonic()-tick>limit:raise TimeoutError(name+' timed out; no FPGA reset performed')
                time.sleep(.05)
        dump(board/(name+'.receipt.json'),dict(exit=code,seconds=time.monotonic()-tick))
        if code:raise RuntimeError(name+' failed; retained logs')
        return (board/(name+'.stdout')).read_text()
    def inventory_command(candidate):
        filename='inventory_retention_v13.py' if candidate else 'inventory_v8_json_retention_v11.py'
        package=PACKAGE if candidate else V8_PACKAGE
        payload=base64.b64encode((work/'bundle/scripts/v2'/filename).read_bytes()).decode()
        code=("import sys,base64,json;sys.path.insert(0,"+repr(package+'/src')+
          ");g={'__name__':'inventory_bootstrap'};exec(base64.b64decode("+repr(payload)+
          "),g);d=g['inventory']();g['validate'](d);print(json.dumps(d))")
        return 'flock -n /run/lock/sysone-inference.lock /usr/bin/python3 -c '+shlex.quote(code)
    started=False;complete=False
    try:
        client.connect('192.168.0.239',username='ubuntu',password=password,look_for_keys=False,allow_agent=False,
                       timeout=15,auth_timeout=15,banner_timeout=10,transport_factory=transport)
        client.get_transport().set_keepalive(30)
        transact(ROOT/'BOARD_STATUS.json','begin',claim=args.claim,
                 operation='Authorized v8 to v9d swap, then finite matched JSON/history comparison; full sweep stopped')
        initial=json.loads(execute('00-live-v8-preflight',inventory_command(False),root=True))
        dump(board/'live-v8-initial.json',initial)
        print('Live v8 identity/idle preflight passed; candidate swap authorized.',flush=True)
        archive=work/'qualification.tar';digest=hashlib.sha256(archive.read_bytes()).hexdigest()
        expected=json.loads((work/'preflight.json').read_text())['archive_sha256']
        if digest!=expected:raise RuntimeError('Upload archive changed')
        upload='/home/ubuntu/sysone-'+VERSION+'.tar'
        with client.open_sftp() as sftp:
            with sftp.open(upload,'wx') as dst,archive.open('rb') as src:
                for block in iter(lambda:src.read(262144),b''):dst.write(block)
        extract=("import hashlib,tarfile;from pathlib import Path,PurePosixPath;"
                 f"a=Path({upload!r});assert hashlib.sha256(a.read_bytes()).hexdigest()=={digest!r};"
                 f"p=Path({REMOTE!r});p.mkdir(parents=True,exist_ok=False);t=tarfile.open(a);"
                 "assert all(m.isfile() and not PurePosixPath(m.name).is_absolute() and '..' not in PurePosixPath(m.name).parts for m in t.getmembers());"
                 "t.extractall(p,filter='data');t.close()")
        execute('01-extract','/usr/bin/python3 -c '+shlex.quote(extract),root=True)
        deploy=(f'/usr/bin/python3 {PACKAGE}/scripts/v2/deploy_qwen_fpga_v9d.py --package {PACKAGE} '
                f'--direction candidate --out {REMOTE}/deploy-v9d.json')
        execute('02-deploy-v9d',deploy,root=True,limit=150)
        with client.open_sftp() as sftp:sftp.get(REMOTE+'/deploy-v9d.json',str(board/'deploy-v9d.json'))
        before=json.loads(execute('03-live-v9d-preflight',inventory_command(True),root=True))
        dump(board/'live-before.json',before)
        for field in ('boot_id','launcher_sha256','dma_table_sha256','dma_header','services','clocks'):
            if initial[field]!=before[field]:raise RuntimeError('Swap changed protected identity: '+field)
        print('Verified v9d active; boot, DMA, launcher, services and clocks preserved.',flush=True)
        command=(f'systemd-run --unit={UNIT} --collect --property=WorkingDirectory={REMOTE} '
                 f'--property=StandardOutput=append:{REMOTE}/unit.stdout --property=StandardError=append:{REMOTE}/unit.stderr '
                 f'--setenv=PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -u {REMOTE}/scripts/v2/run_retention_comparison_v13.py '
                 f'--backend fpga --work {REMOTE} --out {REMOTE}/fpga --package {PACKAGE}')
        execute('04-start',command,root=True);started=True
        counts=json.loads((work/'preflight.json').read_text())
        print('Started finite comparison: '+str(counts['runnable'])+' inference, '+str(counts['overflow'])+' explicit overflow; full sweep untouched.',flush=True)
        deadline=time.monotonic()+14400;last=None
        with client.open_sftp() as sftp:
            while time.monotonic()<deadline:
                try:
                    with sftp.open(REMOTE+'/fpga/status.json') as f:progress=json.loads(f.read())
                    dump(board/'progress.json',progress)
                    if progress!=last:print(json.dumps(progress),flush=True);last=progress
                    if progress['stage'] in ('complete','attention'):break
                except FileNotFoundError:pass
                time.sleep(5)
            else:raise TimeoutError('Finite retention run exceeded four-hour collection limit')
            out=work/'fpga';out.mkdir(exist_ok=False)
            for name in sftp.listdir(REMOTE+'/fpga'):sftp.get(REMOTE+'/fpga/'+name,str(out/name))
            for name in ('unit.stdout','unit.stderr'):sftp.get(REMOTE+'/'+name,str(board/name))
        if progress['stage']!='complete':raise RuntimeError('FPGA qualification needs attention')
        # Final inventory also proves the transient inference kernel lock was released.
        after=json.loads(execute('05-live-final',inventory_command(True),root=True))
        dump(board/'live-after.json',after)
        if before!=after:raise RuntimeError('Live board/deployment identity changed')
        complete=True
        observation=dict(state='ready',verified_at_utc=datetime.now(timezone.utc).isoformat(),
            evidence=[str(board/'live-after.json'),str(work/'fpga/status.json'),str(work/'fpga/fixture-after.json')],
            active_package=PACKAGE,active_fpga_app=after['active_fpga_app'],boot_id=after['boot_id'],
            fpga_manager_state=after['fpga_manager_state'],launcher_sha256=after['launcher_sha256'],
            dma_header=after['dma_header'],dma_table_sha256=after['dma_table_sha256'],
            decoder_clock_hz=after['clocks']['pl0_ref']['rate_hz'],memory_clock_hz=after['clocks']['pl1_ref']['rate_hz'],
            mvp_service=after['services']['sysone-qwen06b-mvp.service'],r5_loaded=after['r5_loaded'],
            benchmark_processes=[],preflight_required_before_use=True,
            note='V13 JSON/history comparison complete on authorized v9d. v8 package preserved. Launcher still v8 and MVP/full-sweep services inactive; use v9d package explicitly. Full sweep stopped.',
            last_validation=json.loads((work/'fpga/status.json').read_text()))
        dump(board/'observation.json',observation)
        transact(ROOT/'BOARD_STATUS.json','record',claim=args.claim,observation=observation)
        transact(ROOT/'BOARD_STATUS.json','release',claim=args.claim)
        dump(board/'released.json',dict(released=True,full_sweep_started=False))
        print('Final v9d identity verified; shared board reservation released; full sweep stopped.',flush=True)
    except Exception as exc:
        dump(board/'attention.json',dict(error_type=type(exc).__name__,error=str(exc),unit_may_be_running=started and not complete))
        # Keep ownership on uncertainty; never free a possibly active MMIO session.
        transact(ROOT/'BOARD_STATUS.json','record',claim=args.claim,
                 observation=dict(state='unknown',evidence=[str(board/'attention.json')],note='Qualification interrupted; owner must reconcile before release.'))
        raise
    finally:
        password=None;client.close();dump(board/'session-closed.json',dict(closed=True))


if __name__=='__main__':main()
