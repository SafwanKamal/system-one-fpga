"""Transient interactive authentication, exact admitted bundle, existing rollback qualification."""
from pathlib import Path
import sys,getpass,hashlib,json,shlex,time
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'build/v2/board-auth-tools'))
import paramiko
ARCHIVE=ROOT/'build/v2/kr260-app-attention-context-capture-large.tar.gz'
EXPECTED='ecd320163baa3c289c64e069186497974d4703039df4a455bc8620d357d7ec99'
def main():
 local=ROOT/'build/v2/context-capture-board-validation'
 if local.exists():raise SystemExit('Existing board-validation evidence must be reviewed; no duplicate upload or deployment')
 assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()==EXPECTED,'Admitted archive changed'
 password=getpass.getpass('KR260 ubuntu password (transient; never saved): ')
 client=paramiko.SSHClient();client.load_host_keys(str(Path.home()/'.ssh/known_hosts'))
 client.connect('192.168.0.239',username='ubuntu',password=password,look_for_keys=False,allow_agent=False,timeout=10,auth_timeout=20)
 stamp=time.strftime('%Y%m%d-%H%M%S',time.gmtime())
 remote='/home/ubuntu/kr260-context-capture-'+stamp
 report='/home/ubuntu/kr260-context-capture-validation-'+stamp
 # Check baseline workspace and avoid overwriting any existing bundle/report.
 cmd='test -d /home/ubuntu/system-one-fpga && test -x /home/ubuntu/sysone-venv/bin/python && test ! -e '+shlex.quote(remote)+' && test ! -e '+shlex.quote(report)+' && mkdir '+shlex.quote(remote)
 _,out,err=client.exec_command(cmd);code=out.channel.recv_exit_status();assert code==0,'Board workspace/recovery prerequisites failed'
 sftp=client.open_sftp();remote_archive=remote+'/bundle.tar.gz'
 print('Authenticated; uploading exact admitted bundle.',flush=True)
 sftp.put(str(ARCHIVE),remote_archive)
 _,out,err=client.exec_command('sha256sum '+shlex.quote(remote_archive));actual=out.read().decode().split()[0];assert actual==EXPECTED,'Remote archive hash differs'
 _,out,err=client.exec_command('tar -xzf '+shlex.quote(remote_archive)+' -C '+shlex.quote(remote));assert out.channel.recv_exit_status()==0,'Unpack failed'
 # Password travels on stdin only after terminal echo is disabled. No secret in command or logs.
 cmd="stty -echo; printf '__AUTH_READY__\n'; sudo -S -p '' -v && bash "+shlex.quote(remote+'/deploy_frontier.sh')+' /home/ubuntu/system-one-fpga '+shlex.quote(report)
 inp,out,err=client.exec_command(cmd,get_pty=True)
 marker=out.readline();assert '__AUTH_READY__' in marker,'Transient authentication channel not ready'
 inp.write(password+'\n');inp.flush();password=None
 local.mkdir(exist_ok=False)
 with (local/'console.log').open('w',encoding='utf-8') as log:
  for line in out:
   print(line,end='',flush=True);log.write(line);log.flush()
 code=out.channel.recv_exit_status()
 metadata={'remote_bundle':remote,'remote_reports':report,'archive_sha256':EXPECTED,'exit_code':code,'hardware_qualified':False}
 # Retrieve the existing validator outputs without interpreting a partial run as success.
 try:
  for name in sftp.listdir(report):
   if name.endswith(('.json','.txt','.log')):sftp.get(report+'/'+name,str(local/name))
  status=(local/'validation-status.txt').read_text().strip()
  metadata['hardware_qualified']=code==0 and status=='passed'
 except OSError as error:metadata['report_retrieval_error']=str(error)
 (local/'receipt.json').write_text(json.dumps(metadata,indent=2)+'\n')
 sftp.close();client.close()
 if not metadata['hardware_qualified']:raise SystemExit('Hardware validation failed or incomplete; inspect rollback/report evidence')
 print('Board qualification completed; reports retrieved. Review exact hardware evidence.',flush=True)
if __name__=='__main__':main()
