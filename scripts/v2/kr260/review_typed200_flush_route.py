"""Review final route completion and STA; never qualify or deploy the candidate."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    b=ROOT/'build/v2/typed200-flush-physical-v1';dest=b/'route-review.json'
    assert not dest.exists(),'Preserve completed route review'
    assert json.loads((b/'route-status.json').read_text())['exit_code']==0
    priorfile=b/('postplace-review.json' if (b/'postplace-review.json').exists() else 'placement-review.json')
    prior=json.loads(priorfile.read_text());assert prior['route_approved']
    for n,h in prior['evidence_sha256'].items():assert sha(b/n)==h,n
    t=json.loads((b/'route/timing.json').read_text());assert t['routed']
    log=(b/'route/console.log').read_text()
    for label in ['Number of Unrouted Nets','Number of Node Overlaps']:
        values=re.findall(re.escape(label)+r'\s*=\s*(\d+)',log);assert values and int(values[-1])==0,label
    checks=(b/'route/check-timing.rpt').read_text()
    assert all(int(n)==0 for n in re.findall(r'checking \w+ \((\d+)\)',checks))
    assert 'All paths are Safely Timed.' in (b/'route/cdc.rpt').read_text()
    assert 'LUTAR-1' not in (b/'route/methodology.rpt').read_text()
    assert 'FIFO asynchronous reset/preset flip-flops: 0' in (b/'route/fifo-reset-mapping.txt').read_text()
    drc=(b/'route/drc.rpt').read_text()
    assert not re.search(r'\|[^\n]*\|\s*(Error|Critical Warning)\s*\|',drc)
    closed=t['setup_ns']>=0 and t['hold_ns']>=0
    timing=(b/'route/timing.rpt').read_text()
    assert ('All user specified timing constraints are met.' in timing)==closed
    files=[b/'route-status.json',b/'placement-review.json',priorfile,*[p for p in (b/'route').iterdir() if p.is_file()]]
    r={'target_mhz':200,**t,'sta_passed':closed,'unrouted_nets':0,'node_overlaps':0,
       'missing_clock_or_delay_checks':0,'routed_drc_errors_or_critical_warnings':0,
       'hardware_qualified':False,'package_or_deployment_approved':False,
       'limitation':f'Final setup margin {t["setup_ns"]:.3f} ns; STA passed={closed}; no higher frequency demonstrated',
       'unresolved_assurance_gates':['Board reset/clock ownership and target validation',
           'R5 target startup/numerical/ownership validation','Successful inference WCET and external delivery bound'],
       'evidence_sha256':{p.relative_to(b).as_posix():sha(p) for p in files}}
    dest.write_text(json.dumps(r,indent=2)+'\n')
    print('PASS route completion and final STA reviewed; candidate remains unqualified')
if __name__=='__main__':main()
