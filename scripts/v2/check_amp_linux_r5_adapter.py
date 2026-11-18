"""Exercise extracted actual adapter functions in blocked and modeled-live builds."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-linux-r5-controller-v1'
SOURCE=ROOT/'firmware/typed200_amp_linux_r5_controller'


def extract(text,name):
    match=re.search(r'(?m)^static (?:int|void|ssize_t) '+name+r'\([^;{}]*\)\s*\{',text)
    assert match,name
    start=text.index('{',match.start());end=start+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[match.start():end]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--attempt',required=True)
    ap.add_argument('--package',required=True)
    args=ap.parse_args()
    out=BASE/args.attempt;out.mkdir(exist_ok=False)
    source=(SOURCE/'linux.c').read_text()
    order=['smoke_pm_event','correct_mode','smoke_node_state','no_rpu_dt_owner','inspect','pin','unpin',
           'reserve','unreserve','request','lease','release','stop','off','map','unmap','load','wake']
    functions='\n'.join(extract(source,n) for n in order)
    ops=re.search(r'static const struct smoke_ops ops = \{.*?\};',source,re.S)
    assert ops
    functions+='\n'+ops.group()
    functions+='\n'+'\n'.join(extract(source,n) for n in [
        'capture_trace','recover_workfn','trace_show','command_store'])
    (out/'adapter_functions.inc').write_bytes(functions.encode())
    for name in ['session.c','session.h','adapter_test.c']:
        (out/name).write_bytes((SOURCE/name).read_bytes())
    (out/'smoke_image.h').write_bytes((BASE/args.package/'smoke_image.h').read_bytes())
    wsl='/mnt/c/'+str(out.resolve())[3:].replace('\\','/')
    results={}
    for live,prepare in [(0,0),(0,1),(1,1)]:
        command=['gcc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-unused-parameter',
                 '-Wno-misleading-indentation','-O1','-g','-fsanitize=address,undefined',
                 '-fno-omit-frame-pointer',f'-DSYSONE_R5_LIVE_ADMITTED={live}',
                 f'-DSYSONE_R5_PREPARE_ADMITTED={prepare}',
                 wsl+'/session.c',wsl+'/adapter_test.c','-o',wsl+f'/adapter-{live}-{prepare}']
        for cmd,name in [(command,f'compile-{live}-{prepare}'),([wsl+f'/adapter-{live}-{prepare}'],f'adapter-{live}-{prepare}')]:
            r=subprocess.run(['wsl.exe','-d','Ubuntu-24.04','--',*cmd],stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,timeout=60)
            (out/(name+'.log')).write_bytes(r.stdout)
            assert not r.returncode,name
            results[name]=r.stdout.decode().strip()
    (out/'receipt.json').write_text(json.dumps(dict(passed=True,software_only=True,
        actual_adapter_functions=True,host_live_branch_tested=True,target_live_enabled=False,
        source_sha256=hashlib.sha256((SOURCE/'linux.c').read_bytes()).hexdigest(),
        results=results,limitations='Linux APIs, SMC, TCM and workqueue are mocks; no hardware power, reset, ECC or scheduler timing proof.'),indent=2)+'\n')
    for mode in ['0-0','0-1','1-1']: print(results['adapter-'+mode])


if __name__=='__main__':main()
