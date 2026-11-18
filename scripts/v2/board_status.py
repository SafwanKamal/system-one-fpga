"""Coordinate board ownership through one canonical, OS-locked status file.

The reservation persists after this command exits. Keep it for the complete
board operation. Actual board operations must also hold the existing Linux
/run/lock/sysone-inference.lock. No SSH or hardware actions happen here.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import time
import uuid

DEFAULT=Path(__file__).resolve().parents[2]/'BOARD_STATUS.json'


def now():return datetime.now(timezone.utc).isoformat()


@contextmanager
def locked(path):
    # Lock the same file rather than replacing its inode or creating a second
    # status/lock file. A corrupt/missing file fails closed; never auto-initialize.
    with path.open('r+b') as f:
        deadline=time.monotonic()+5
        while True:
            try:
                f.seek(0)
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic()>=deadline:raise RuntimeError('Status transaction busy; retry later')
                time.sleep(.05)
        try:yield f
        finally:
            f.seek(0)
            if os.name=='nt':msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(f.fileno(),fcntl.LOCK_UN)


def transact(path,action,*,owner=None,purpose=None,claim=None,operation=None,observation=None):
    path=Path(path).resolve()
    with locked(path) as f:
        data=json.loads(f.read().decode('utf-8'))
        if Path(data['canonical_path']).resolve()!=path:
            raise ValueError('Use canonical status file: '+data['canonical_path'])
        if action=='show':return data
        reservation=data.get('reservation')
        if action=='reserve':
            if reservation:raise ValueError('Board reserved by '+reservation['owner']+' for '+reservation['purpose'])
            if data['current']['state'] in ('changing','unknown') and not purpose.startswith('RECOVERY:'):
                raise ValueError('Board state uncertain; reserve with purpose beginning RECOVERY: to reconcile')
            data['reservation']=dict(claim_id=str(uuid.uuid4()),owner=owner,purpose=purpose,acquired_at_utc=now())
        else:
            if not reservation or reservation['claim_id']!=claim:raise ValueError('Reservation claim does not match')
            if action=='begin':
                data['last_observation']=data['current']
                data['current']=dict(state='changing',operation=operation,recorded_at_utc=now(),
                                     note='Identity is unverified until owner records the post-operation observation.')
            elif action=='record':
                if not isinstance(observation,dict) or observation.get('state') not in ('ready','stopped','unknown'):
                    raise ValueError('Observation needs state ready, stopped or unknown')
                if observation['state']!='unknown' and not all(observation.get(k) for k in ('verified_at_utc','evidence','active_package','boot_id')):
                    raise ValueError('Verified observation needs verified_at_utc, evidence, active_package, boot_id')
                data['current']=dict(observation,recorded_at_utc=now())
            elif action=='release':
                if data['current']['state']=='changing':raise ValueError('Record verified result or unknown state before releasing')
                data['reservation']=None
            else:raise ValueError('Unknown action')
        data['revision']=data.get('revision',0)+1;data['updated_at_utc']=now()
        event=dict(revision=data['revision'],at_utc=data['updated_at_utc'],action=action,
                   owner=owner if action=='reserve' else reservation['owner'])
        if operation:event['operation']=operation
        data['events']=(data.get('events',[])+[event])[-50:]
        encoded=(json.dumps(data,indent=2)+'\n').encode('utf-8')
        f.seek(0);f.write(encoded);f.truncate();f.flush();os.fsync(f.fileno())
        return data


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--file',type=Path,default=DEFAULT)
    sub=ap.add_subparsers(dest='action',required=True)
    sub.add_parser('show')
    p=sub.add_parser('reserve');p.add_argument('--owner',required=True);p.add_argument('--purpose',required=True)
    for action in ('begin','record','release'):
        p=sub.add_parser(action);p.add_argument('--claim',required=True)
        if action=='begin':p.add_argument('--operation',required=True)
        if action=='record':p.add_argument('--observation',type=Path,required=True)
    a=ap.parse_args();observation=None
    if a.action=='record':observation=json.loads(a.observation.read_text(encoding='utf-8'))
    try:
        data=transact(a.file,a.action,owner=getattr(a,'owner',None),purpose=getattr(a,'purpose',None),
            claim=getattr(a,'claim',None),operation=getattr(a,'operation',None),observation=observation)
    except (OSError,ValueError,RuntimeError) as exc:ap.exit(2,str(exc)+'\n')
    print(json.dumps(data,indent=2))


if __name__=='__main__':main()
