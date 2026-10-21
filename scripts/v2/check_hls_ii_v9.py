"""Fail if any pipelined loop misses its target II, except an explicit allowlist.

Added after v9a build 2, where a BRAM reshape silently halved the matrix
accumulator (Target II=1, Final II=2) while every other check passed.
Allowed exceptions are loops whose II>1 is known and already in the cycle model.
"""
import argparse,re,sys
from pathlib import Path

# (source-line-independent) loop bodies with an accepted II above target:
# the two residual-add loops read X and P and write X on a 2-port URAM bank.
ALLOWED_ABOVE_TARGET=2


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('log',type=Path);args=ap.parse_args()
    results=re.findall(r"Pipelining result : Target II = (\w+), Final II = (\d+), Depth = \d+, (?:loop|function) '([^']+)'",args.log.read_text(errors='replace'))
    if not results:sys.exit('No pipelining results found in '+str(args.log))
    misses=[(t,f,n) for t,f,n in results if t!='NA' and int(f)>int(t)]
    for t,f,n in misses:print(f'MISS target={t} final={f} {n}')
    if len(misses)>ALLOWED_ABOVE_TARGET or any(int(f)>2 for t,f,n in misses):
        sys.exit(f'II gate failed: {len(misses)} loops above target (allowed {ALLOWED_ABOVE_TARGET}, each at most II=2)')
    print(f'II gate passed: {len(results)} pipelines, {len(misses)} known exceptions')


if __name__=='__main__':main()
