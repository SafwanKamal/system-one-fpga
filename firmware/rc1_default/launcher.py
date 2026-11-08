#!/usr/bin/python3
"""Default sysone-qwen-fpga CLI backed by the boot-managed RC1 service."""
import argparse
import json
from pathlib import Path
import sys
import time

PACKAGE=Path('/var/lib/sysone/hardware-consolidated-rc1-20261108')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query')
    parser.add_argument('--out',type=Path,default=Path('/var/lib/sysone/rc1-results/last-command-result.json'))
    parser.add_argument('--max-tokens',type=int,default=64)
    parser.add_argument('--conversation-id',default='default')
    parser.add_argument('--reset-cache',action='store_true')
    parser.add_argument('--no-prefix-cache',action='store_true',help='Force cold prefill for this request')
    parser.add_argument('--health',action='store_true')
    args=parser.parse_args()
    if not args.health and not args.query:
        parser.error('--query is required for generation')
    sys.path.insert(0,str(PACKAGE/'scripts/v2'))
    from qwen_arm_service_candidate import exchange
    request=dict(op='health') if args.health else dict(op='generate',query=args.query,
        max_tokens=args.max_tokens,conversation_id=args.conversation_id,
        reset_cache=args.reset_cache or args.no_prefix_cache)
    started=time.monotonic()
    try:
        response=exchange(Path('/run/sysone-rc1/api.sock'),request)
    except OSError as exc:
        raise RuntimeError('RC1 service unavailable; inspect systemctl status sysone-rc1.service') from exc
    if args.health:
        result=response
    elif response['ok']:
        result=dict(response['result'],backend='consolidated RC1 persistent FPGA service',
                    client_seconds=response['client_seconds'],launcher_seconds=time.monotonic()-started)
    else:
        result=dict(complete=False,**response)
    text=json.dumps(result,indent=2)+'\n'
    if not args.health:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(text,encoding='utf-8')
    print(text,end='')
    if not response['ok']:
        raise SystemExit(1)


if __name__=='__main__':main()
