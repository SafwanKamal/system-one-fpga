"""Stage and run the flush boundary test against the immutable parent streamer."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/v2/kr260'))
import create_typed200_flush_candidate as candidate
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='typed200-flush-unit-v1');a=ap.parse_args()
    candidate.verify();out=ROOT/'build/v2'/a.name;out.mkdir(exist_ok=False)
    files={n:candidate.OUT/n for n in ['common/sync_fifo.sv','common/stream_fifo_sync_clear.sv','encoder/result_streamer.sv']}
    files['typed200_flush_tb.sv']=ROOT/'simulation/v2/typed200_flush_tb.sv'
    for n,p in files.items():(out/Path(n).name).write_bytes(p.read_bytes())
    parent=candidate.PARENT/'encoder/result_streamer.sv'
    (out/'reference_result_streamer.sv').write_text(parent.read_text().replace('module result_streamer #(','module reference_result_streamer #(',1))
    root='/mnt/'+ROOT.drive[0].lower()+ROOT.as_posix()[2:];rel=out.relative_to(ROOT).as_posix()
    stage=subprocess.check_output(['wsl','-d','Ubuntu-24.04','--','mktemp','-d','/var/tmp/typed200flush.XXXXXX'],text=True).strip()
    subprocess.run(['wsl','-d','Ubuntu-24.04','--','cp',*[root+'/'+rel+'/'+p.name for p in out.glob('*.sv')],stage],check=True)
    (out/'stage.txt').write_text(stage+'\n')
    commands=[['/opt/verilator-5.040/bin/verilator','--assert','--binary','--timing','-j','2','-Wno-fatal',
        '--top-module','typed200_flush_tb','--Mdir','obj','-o','sim',*[p.name for p in out.glob('*.sv')]],['./obj/sim']]
    passed=True
    for i,cmd in enumerate(commands):
        with (out/('build.log' if i==0 else 'run.log')).open('w') as f:
            r=subprocess.run(['wsl','-d','Ubuntu-24.04','--cd',stage,'--',*cmd],stdout=f,stderr=subprocess.STDOUT)
        if r.returncode:passed=False;break
    (out/'receipt.json').write_text(json.dumps({'passed':passed,'commands':commands,
        'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in [*files.values(),parent]},
        'staged_sha256':{p.name:sha(p) for p in out.glob('*.sv')},
        'scope':'Cycle/data equivalence for synchronous reset/start and stalled descriptor replacement; subcycle clear has no state effect',
        'limits':['not arbitrary asynchronous reset equivalence','not hardware qualification']},indent=2)+'\n')
    print('PASS flush boundary tests' if passed else 'FAIL; preserve attempt and inspect logs')
    raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()
