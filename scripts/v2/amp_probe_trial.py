"""Saved-key upload/start/collect for a board-local, automatically restored probe."""
from pathlib import Path
import argparse,base64,getpass,hashlib,json,re,shlex,sys,time
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/v2/typed200-amp-deployment-v1'
sys.path[:0]=[str(ROOT/'build/v2/typed200-amp-candidate-v1/auth-deps'),str(ROOT/'build/v2/board-auth-tools')]
import paramiko

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);ap.add_argument('--collect-only',action='store_true');args=ap.parse_args()
    assert re.fullmatch(r'probe-target-v[0-9]+',args.attempt)
    out=BASE/args.attempt
    if not args.collect_only:out.mkdir(exist_ok=False)
    pkg=BASE/'probe-package-v1/sysone-amp-origin-probe'
    manifest=json.loads((pkg/'build.json').read_text())
    receipt=json.loads((BASE/'probe-package-v1/receipt.json').read_text())
    assert receipt['passed'] and hashlib.sha256((pkg/'build.json').read_bytes()).hexdigest()==receipt['manifest_sha256']
    for name,h in manifest['files_sha256'].items():assert hashlib.sha256((pkg/name).read_bytes()).hexdigest()==h
    readiness=BASE/'board-readiness-v4/receipt.json';r=json.loads(readiness.read_text());assert r['passed']
    password=getpass.getpass('KR260 SSH/sudo authentication (memory only): ')
    client=paramiko.SSHClient();client.load_system_host_keys();client.load_host_keys(str(Path.home()/'.ssh/known_hosts'))
    def transport(sock,**kwargs):
        t=paramiko.Transport(sock,**kwargs);o=t.get_security_options()
        o.kex=('curve25519-sha256@libssh.org',);o.key_types=('ssh-ed25519',);o.ciphers=('aes128-ctr',);o.digests=('hmac-sha2-256',)
        return t
    client.connect('192.168.0.239',username='ubuntu',password=password,look_for_keys=False,allow_agent=False,timeout=15,auth_timeout=15,banner_timeout=10,transport_factory=transport)
    finger=base64.b64encode(hashlib.sha256(client.get_transport().get_remote_server_key().asbytes()).digest()).decode().rstrip('=')
    assert finger==r['host_key_sha256']
    def command(cmd,log,root=False):
        if root:cmd='sudo -S -p "" /bin/sh -c '+shlex.quote(cmd)
        i,o,e=client.exec_command(cmd,timeout=30)
        if root:i.write(password+'\n');i.flush()
        data=o.read();err=e.read();code=o.channel.recv_exit_status()
        (out/log).write_bytes(data);(out/(log+'.stderr')).write_bytes(err)
        assert code==0,(log,code,err.decode(errors='replace'))
        return data
    remote='/home/ubuntu/sysone-'+args.attempt
    unit='sysone-'+args.attempt
    if args.collect_only:
        command('systemctl show '+unit+' -p ActiveState -p SubState -p Result','collected-service-state.txt')
        command('journalctl -u '+unit+' --no-pager -o short-iso','journal.log',True)
        with client.open_sftp() as sftp:
            sftp.get_channel().settimeout(30)
            for attr in sftp.listdir_attr(remote):
                if attr.filename.endswith(('.log','.json')):sftp.get(remote+'/'+attr.filename,str(out/attr.filename))
        password=None;client.close();print('Collected existing target trial; inspect trial/recovery/journal',flush=True);return
    command('mkdir '+shlex.quote(remote),'mkdir.log')
    uploads={ROOT/'scripts/v2/amp_probe_target_trial.py':'target.py',BASE/'apu-probe-v1.elf':'apu_probe',readiness:'readiness.json'}
    uploads.update({p:'sysone-amp-origin-probe/'+p.name for p in pkg.iterdir() if p.name!='sysone-amp-origin-probe.dts'})
    hashes={}
    with client.open_sftp() as sftp:
        sftp.get_channel().settimeout(30)
        sftp.mkdir(remote+'/sysone-amp-origin-probe')
        for src,dst in uploads.items():
            sftp.put(str(src),remote+'/'+dst)
            with sftp.open(remote+'/'+dst,'rb') as f:assert hashlib.sha256(f.read()).digest()==hashlib.sha256(src.read_bytes()).digest()
            hashes[dst]=hashlib.sha256(src.read_bytes()).hexdigest()
        sftp.chmod(remote+'/apu_probe',0o755)
    (out/'upload.json').write_text(json.dumps(dict(remote=remote,unit=unit,files_sha256=hashes),indent=2)+'\n')
    # Freeze trial files against unprivileged modification before root execution.
    command('chown -R root:root '+shlex.quote(remote)+' && chmod -R go-w '+shlex.quote(remote),'freeze.log',True)
    stop='/usr/bin/python3 '+remote+'/target.py --recover'
    cmd=['systemd-run','--unit='+unit,'--property=Type=oneshot','--property=TimeoutStartSec=120s','--property=TimeoutStopSec=20s','--property=ExecStopPost='+stop,'/usr/bin/python3',remote+'/target.py']
    command(shlex.join(cmd),'launch.log',True)
    for n in range(65):
        data=command('systemctl show '+unit+' -p ActiveState -p SubState -p Result','service-state.txt')
        if b'ActiveState=inactive' in data or b'ActiveState=failed' in data:break
        time.sleep(2)
    else:raise RuntimeError('Service still active; preserve it and collect exact continuation before any retry')
    command('journalctl -u '+unit+' --no-pager -o short-iso','journal.log',True)
    with client.open_sftp() as sftp:
        for attr in sftp.listdir_attr(remote):
            if attr.filename.endswith(('.log','.json')):
                sftp.get(remote+'/'+attr.filename,str(out/attr.filename))
    assert json.loads((out/'recovery.json').read_text())['passed'],'STOCK RECOVERY NOT CONFIRMED'
    trial=json.loads((out/'trial.json').read_text());assert trial['passed']
    (out/'receipt.json').write_text(json.dumps(dict(passed=True,diagnostic_only=True,stock_restored=True,inference_deployed=False,r5_executed=False,host_key_sha256=finger,remote=remote),indent=2)+'\n')
    password=None;client.close();print('PASS APU diagnostic probe and automatic stock restoration',flush=True)
if __name__=='__main__':main()
