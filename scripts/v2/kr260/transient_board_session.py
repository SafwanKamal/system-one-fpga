"""Transient board connection for authorized qualification; credentials stay in memory."""
from pathlib import Path
import sys,json,getpass
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'build/v2/board-auth-tools'))
import paramiko
password=getpass.getpass('KR260 authentication (transient): ')
client=paramiko.SSHClient();client.load_host_keys(str(Path.home()/'.ssh/known_hosts'))
client.connect('192.168.0.239',username='ubuntu',password=password,look_for_keys=False,allow_agent=False,timeout=10)
print('BOARD_SESSION_READY',flush=True)
for line in sys.stdin:
 try:
  request=json.loads(line)
  if request['action']=='close':break
  if request['action'] in ('put','get'):
   with client.open_sftp() as sftp:
    if request['action']=='put':sftp.put(request['local'],request['remote'])
    else:sftp.get(request['remote'],request['local'])
   print('TRANSFER_COMPLETE',flush=True);continue
  command=request['command']
  if request.get('sudo'):
   command="stty -echo; printf '__AUTH_READY__\n'; sudo -S -p '' -v && "+command
  inp,out,err=client.exec_command(command,get_pty=request.get('sudo',False))
  if request.get('sudo'):
   assert '__AUTH_READY__' in out.readline()
   inp.write(password+'\n');inp.flush()
  for output in out:print(output,end='',flush=True)
  errors=err.read().decode(errors='replace')
  if errors:print(errors,flush=True)
  print('REMOTE_EXIT='+str(out.channel.recv_exit_status()),flush=True)
 except Exception as error:print(type(error).__name__+': '+str(error),flush=True)
client.close();password=None
