"""Record a scoped routing decision from completed typed200 placement evidence."""
from pathlib import Path
from zipfile import ZipFile
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    b=ROOT/'build/v2/typed200-physical-v1';dest=b/'placement-review.json'
    assert not dest.exists(),'Preserve completed placement review'
    assert json.loads((b/'place-status.json').read_text())['exit_code']==0
    assert 'Exiting Vivado' in (b/'placement-audit-console.log').read_text()
    audit=b/'placement-audit';exceptions=[]
    with ZipFile(b/'place/placed.dcp') as z:
        for n in z.namelist():
            if not n.endswith('.xdc'):continue
            content=z.read(n);(audit/n).write_bytes(content)
            sources={};file_id=None
            for line in content.decode().splitlines():
                if line.startswith('set_property SRC_FILE_INFO '):
                    ident=re.search(r' id:(\d+) ',line);path=re.search(r'cfile:(.*?) rfile:',line)
                    scope=re.search(r'scoped_inst:(\S+)',line)
                    if ident and path:sources[ident[1]]={'path':path[1],'scope':scope[1] if scope else ''}
                elif line.startswith('set_property src_info '):
                    ident=re.search(r'file:(\d+)',line)
                    if ident:file_id=ident[1]
                elif re.match(r'set_(false_path|multicycle_path|max_delay|clock_groups)\b',line):
                    source=sources[file_id]
                    assert '/ip/xpm/xpm_cdc/' in source['path'],source
                    exceptions.append({'command':line,**source})
    assert exceptions and all(x['command'].startswith('set_false_path ') for x in exceptions)
    (audit/'exceptions-classified.json').write_text(json.dumps(exceptions,indent=2)+'\n')
    check=(b/'place/check-timing.rpt').read_text()
    for tag in ['no_clock','constant_clock','unconstrained_internal_endpoints','no_input_delay',
                'no_output_delay','multiple_clock','loops','latch_loops']:
        assert re.search(r'checking '+tag+r' \(0\)',check),tag
    assert 'All paths are Safely Timed.' in (b/'place/cdc.rpt').read_text()
    retain=(audit/'retention.txt').read_text()
    for n in ['epoch_inst','publication_inst','deployment_permit']:assert re.search(n+r'\* cells [1-9]',retain),n
    assert 'gpio_Data_Out_reg[0]/Q' in retain
    timing=json.loads((b/'place/timing.json').read_text());assert timing['setup_ns']>=0
    drc=(b/'place/drc.rpt').read_text();assert not re.search(r'\|[^\n]*\|\s*Error\s*\|',drc)
    method=(audit/'methodology.rpt').read_text()
    assert 'LUTAR-1#1 Warning' in method and 'reset alert' in method
    inputs=[b/'place/placed.dcp',b/'input-proof.json',b/'synth-status.json',b/'place-status.json',
            *[p for p in (b/'place').iterdir() if p.suffix in ('.rpt','.json')],
            *[p for p in audit.iterdir() if p.is_file()]]
    result={'route_approved':True,'approval_scope':'Timing-only routing experiment; no package or deployment approval',
        'target_mhz':200,**timing,'setup_reason':'Positive placed setup margin; no missing clocks or unconstrained endpoints',
        'hold_reason':'-0.103 ns pre-route hold is not closure; routing must repair and recheck all hold endpoints',
        'cdc':'All defined-clock paths safely timed; reset methodology warning separately retained',
        'exception_count':len(exceptions),'exception_scope':'Vendor XPM CDC reset/synchronizer exceptions only',
        'unresolved_qualification_gates':['LUTAR-1 derived async FIFO reset glitch warning',
            'Final routed setup/hold and route completion','R5 target execution and ownership enforcement',
            'Successful inference WCET and external delivery bound'],
        'drc_scope':'Only unrouted RTSTAT-13 critical warning and DSP pipeline advisories at placement',
        'evidence_sha256':{p.relative_to(b).as_posix():sha(p) for p in inputs}}
    dest.write_text(json.dumps(result,indent=2)+'\n')
    print('PASS placement evidence reviewed; timing-only route approved, async FIFO reset warning NOT waived')
if __name__=='__main__':main()
