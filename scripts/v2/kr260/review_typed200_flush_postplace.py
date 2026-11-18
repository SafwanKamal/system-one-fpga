"""Admit routing only if the separate physical-only optimization repairs setup."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    b=ROOT/'build/v2/typed200-flush-physical-v1';dest=b/'postplace-review.json'
    assert not dest.exists(),'Preserve completed review'
    prior=json.loads((b/'placement-review.json').read_text())
    for n,h in prior['evidence_sha256'].items():assert sha(b/n)==h,n
    out=b/'postplace-opt-v1'
    assert json.loads((b/'postplace-opt-v1-status.json').read_text())['exit_code']==0
    assert 'Exiting Vivado' in (b/'postplace-opt-v1-console.log').read_text()
    t=json.loads((out/'timing.json').read_text())
    check=(out/'check-timing.rpt').read_text()
    checks=re.findall(r'checking (\w+) \((\d+)\)',check)
    assert len({name for name,n in checks})==12 and all(int(n)==0 for name,n in checks)
    assert 'LUTAR-1' not in (out/'methodology.rpt').read_text()
    assert 'FIFO asynchronous reset/preset flip-flops: 0' in (out/'fifo-reset-mapping.txt').read_text()
    assert 'All paths are Safely Timed.' in (out/'cdc.rpt').read_text()
    assert not re.search(r'\|[^\n]*\|\s*Error\s*\|',(out/'drc.rpt').read_text())
    files=[b/'placement-review.json',b/'place/placed.dcp',*[p for p in out.iterdir() if p.is_file()]]
    r={'route_approved':t['setup_ns']>=0,'route_checkpoint':'postplace-opt-v1/optimized.dcp',
        'approval_scope':'Timing-only route experiment; no package or deployment approval',
        'target_mhz':200,**t,'rtl_changed':False,'clock_constraints_relaxed':False,
        'decision':'Positive optimized setup required before routing; pre-route hold requires router repair',
        'evidence_sha256':{p.relative_to(b).as_posix():sha(p) for p in files}}
    dest.write_text(json.dumps(r,indent=2)+'\n')
    print('POSTPLACE route approved='+str(r['route_approved'])+f'; setup {t["setup_ns"]:.3f} ns, hold {t["hold_ns"]:.3f} ns')
if __name__=='__main__':main()
