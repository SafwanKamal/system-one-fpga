"""Systemd readiness gate for the unchanged RC1 persistent service."""
import json
from pathlib import Path
import sys
import time

PACKAGE=Path('/var/lib/sysone/hardware-consolidated-rc1-20261108')
sys.path.insert(0,str(PACKAGE/'scripts/v2'))
from qwen_arm_service_candidate import exchange


def main():
    if sys.argv[1:] != ['wait-ready']:
        raise ValueError('Expected wait-ready')
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        try:
            response=exchange(Path('/run/sysone-rc1/api.sock'),dict(op='health'),timeout=2)
        except (OSError,ValueError):
            time.sleep(.1)
            continue
        if not response['ok'] or response['state']!='READY':
            raise RuntimeError('RC1 service is not ready')
        proof=response['startup_proof']
        if not proof['resident_weights_verified'] or proof['verified_bytes']!=639446688:
            raise RuntimeError('Startup verification proof absent')
        if response['verification']!='startup' or not response['prefix_cache']:
            raise RuntimeError('Unexpected RC1 service mode')
        print(json.dumps(response),flush=True)
        return
    raise TimeoutError('RC1 service did not become ready')


if __name__=='__main__':main()
