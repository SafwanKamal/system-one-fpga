"""Compile the actual session engine with fault-injection and sanitizers."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'build/v2/typed200-amp-linux-r5-controller-v1'
SOURCE = ROOT/'firmware/typed200_amp_linux_r5_controller'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--attempt', required=True)
    args = ap.parse_args()
    out = BASE/args.attempt
    out.mkdir(exist_ok=False)
    for name in ['session.h', 'session.c', 'session_test.c']:
        (out/name).write_bytes((SOURCE/name).read_bytes())
    wsl = '/mnt/c/'+str(out.resolve())[3:].replace('\\','/')
    compile_args = ['gcc','-std=c11','-Wall','-Wextra','-Werror','-O1','-g',
                    '-fsanitize=address,undefined','-fno-omit-frame-pointer',
                    wsl+'/session.c',wsl+'/session_test.c','-o',wsl+'/session-test']
    results = {}
    for command, name in [(compile_args, 'compile'), ([wsl+'/session-test'], 'trajectories')]:
        run = subprocess.run(['wsl.exe','-d','Ubuntu-24.04','--',*command],
                             stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
        (out/(name+'.log')).write_bytes(run.stdout)
        assert run.returncode == 0, name
        results[name] = run.stdout.decode().strip()
    (out/'receipt.json').write_text(json.dumps(dict(
        passed=True, software_only=True, sanitizers=['address','undefined'],
        actual_session_engine=True, results=results, target_executed=False,
        source_sha256={name:hashlib.sha256((SOURCE/name).read_bytes()).hexdigest()
                       for name in ['session.h','session.c','session_test.c']}),indent=2)+'\n')
    print(results['trajectories'])


if __name__ == '__main__':
    main()
