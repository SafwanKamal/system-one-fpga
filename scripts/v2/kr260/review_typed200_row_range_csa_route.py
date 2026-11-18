"""Record routed setup/hold, route status, DRC/CDC and exact scoped constraints."""
from collections import Counter
import json,re
from typed200_row_range_csa_route_common import ROOT,PARENT,OUT,sha,verify_parent,constraints,signature
def main():
    dest=OUT/'route-review.json';assert not dest.exists()
    preserved,prior=verify_parent();p=json.loads((OUT/'input-proof.json').read_text())
    assert json.loads((OUT/'native-status.json').read_text())['exit_code']==0
    assert sha(PARENT/'place/placed.dcp')==sha(OUT/'input/placed.dcp')==p['input_checkpoint_sha256']
    assert sha(OUT/'route.tcl')==p['staged_script_sha256']
    for n,h in p['source_sha256'].items():assert sha(ROOT/n)==h,n
    before=json.loads((OUT/'input-constraints.json').read_text());after=constraints(OUT/'routed.dcp')
    (OUT/'routed-constraints.json').write_text(json.dumps(after,indent=2)+'\n')
    unchanged=signature(before)==signature(after)
    def exception_sources(c):
        return Counter((r.get('source_path'),r.get('source_scope'),r['context'],r['command']) for r in c['commands'] if r['command'].startswith('set_false_path '))
    vendor_sources_unchanged=exception_sources(before)==exception_sources(after)
    timing=json.loads((OUT/'timing.json').read_text());assert timing['routed']
    log=(OUT/'console.log').read_text();route_values={}
    for label in ('Number of Unrouted Nets','Number of Node Overlaps'):
        values=re.findall(re.escape(label)+r'\s*=\s*(\d+)',log);assert values,label
        route_values[label]=int(values[-1])
    checks=re.findall(r'checking (\w+) \((\d+)\)',(OUT/'check-timing.rpt').read_text())
    assert len({n for n,v in checks})==12,'Missing native timing checks'
    timing_checks_passed=all(int(v)==0 for n,v in checks)
    cdc_passed='All paths are Safely Timed.' in (OUT/'cdc.rpt').read_text()
    drc=(OUT/'drc.rpt').read_text()
    drc_passed=not bool(re.search(r'\|[^\n]*\|\s*(Error|Critical Warning)\s*\|',drc))
    method=(OUT/'methodology.rpt').read_text();no_lutar='LUTAR-1' not in method
    fifo_safe='FIFO asynchronous reset/preset flip-flops: 0' in (OUT/'fifo-reset-mapping.txt').read_text()
    assert fifo_safe,'Mapping check failed'
    clock_report=(OUT/'timing.rpt').read_text()
    rows=re.findall(r'^(clk_pl_\d+)\s+\{([\d.]+)\s+([\d.]+)\}\s+([\d.]+)\s+([\d.]+)\s*$',clock_report,re.M)
    clocks_unchanged={n:tuple(map(float,v)) for n,*v in rows}=={'clk_pl_0':(0,2.5,5,200),'clk_pl_1':(0,5,10,100)} and 'encoder_ooc_200' not in clock_report
    setup_hold_passed=timing['setup_ns']>=0 and timing['hold_ns']>=0
    assert ('All user specified timing constraints are met.' in clock_report)==setup_hold_passed
    clean_route=all(v==0 for v in route_values.values())
    closed=all((unchanged,vendor_sources_unchanged,clocks_unchanged,timing_checks_passed,cdc_passed,drc_passed,no_lutar,fifo_safe,setup_hold_passed,clean_route))
    evidence=[q for q in OUT.iterdir() if q.is_file() and q!=dest]
    result={'target_mhz':200,**timing,'review_completed':True,'routed_closure_passed':closed,
        'setup_hold_passed':setup_hold_passed,'drc_passed':drc_passed,'cdc_passed':cdc_passed,
        'timing_checks_passed':timing_checks_passed,'check_timing':dict(checks),'route_counts':route_values,
        'constraints_unchanged':unchanged,'vendor_exception_sources_unchanged':vendor_sources_unchanged,
        'exception_count':39,'exception_scope':'Same scoped vendor XPM reset/synchronizer false paths as reviewed placement',
        'clock_constraints_unchanged':clocks_unchanged,'minimum_placed_setup_ns':0.5,'admitted_placed_setup_ns':prior['setup_ns'],
        'preserved_unique_files':len(preserved),'all_prior_sealed_files_unchanged':True,
        'hardware_qualified':False,'wcet_certified':False,'bitstream_created':False,'package_or_deployment_approved':False,
        'limits':['200MHz timing-only route; not 300MHz evidence','No board qualification or ARM target ownership/service/WCET/external-delivery claim'],
        'evidence_sha256':{q.relative_to(ROOT).as_posix():sha(q) for q in evidence}}
    with dest.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print('Routed closure passed='+str(closed)+'; setup='+str(timing['setup_ns'])+'ns; hold='+str(timing['hold_ns'])+'ns; no deployment')
if __name__=='__main__':main()
