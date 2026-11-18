"""Record a scoped routing decision from completed typed200 placement evidence."""
from pathlib import Path
from zipfile import ZipFile
import argparse,hashlib,json,re
ROOT=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',required=True);a=ap.parse_args()
    assert re.fullmatch(r'typed200-(clock|observe|lut-capture|profile-cache)-physical-v[0-9]+',a.name)
    b=ROOT/'build/v2'/a.name;dest=b/'placement-review.json'
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
    checks=re.findall(r'checking (\w+) \((\d+)\)',check)
    assert len({n for n,c in checks})==12 and all(int(c)==0 for n,c in checks)
    clocks=(audit/'clocks.rpt').read_text()
    assert re.search(r'^clk_pl_0\s+5\.000\s+',clocks,re.M) and re.search(r'^clk_pl_1\s+10\.000\s+',clocks,re.M)
    assert 'encoder_ooc_200' not in clocks

    for tag in ['no_clock','constant_clock','unconstrained_internal_endpoints','no_input_delay',
                'no_output_delay','multiple_clock','loops','latch_loops']:
        assert re.search(r'checking '+tag+r' \(0\)',check),tag
    assert 'All paths are Safely Timed.' in (b/'place/cdc.rpt').read_text()
    retain=(audit/'retention.txt').read_text()
    for n in ['epoch_inst','publication_inst','deployment_permit']:assert re.search(n+r'\* cells [1-9]',retain),n
    assert 'gpio_Data_Out_reg[0]/Q' in retain
    timing=json.loads((b/'place/timing.json').read_text())
    reopened=json.loads((audit/'reopened-timing.json').read_text())
    for key in ('setup_ns','hold_ns'):
        assert abs(timing[key]-reopened[key])<=0.001,key
        timing[key]=min(timing[key],reopened[key])
    drc=(b/'place/drc.rpt').read_text();assert not re.search(r'\|[^\n]*\|\s*Error\s*\|',drc)
    method=(audit/'methodology.rpt').read_text()
    assert 'LUTAR-1' not in method
    assert 'FIFO asynchronous reset/preset flip-flops: 0' in (b/'place/fifo-reset-mapping.txt').read_text()
    inputs=[b/'place/placed.dcp',b/'input-proof.json',b/'synth-status.json',b/'place-status.json',
            *[p for p in (b/'place').iterdir() if p.suffix in ('.rpt','.json','.txt')],
            *[p for p in audit.iterdir() if p.is_file()]]
    result={'route_approved':timing['setup_ns']>=0.5,'approval_scope':'Timing-only routing experiment; no package or deployment approval',
        'target_mhz':200,'minimum_placed_setup_ns':0.5,**timing,'setup_reason':('Placed setup meets the preserved +0.500ns admission margin' if timing['setup_ns']>=0.5 else 'Placed setup below the preserved +0.500ns admission margin; route held')+'; no missing clocks or unconstrained endpoints',
        'hold_reason':f'Placed hold {timing["hold_ns"]:.3f} ns is not routed closure; routing must repair/recheck all hold endpoints',
        'cdc':'All defined-clock paths safely timed; no derived async FIFO reset warning',
        'exception_count':len(exceptions),'exception_scope':'Vendor XPM CDC reset/synchronizer exceptions only',
        'unresolved_qualification_gates':['Board reset/clock ownership and target validation',
            'Final routed setup/hold and route completion','R5 target execution and ownership enforcement',
            'Successful inference WCET and external delivery bound'],
        'drc_scope':'Only unrouted RTSTAT-13 critical warning and DSP pipeline advisories at placement',
        'evidence_sha256':{p.relative_to(b).as_posix():sha(p) for p in inputs}}
    dest.write_text(json.dumps(result,indent=2)+'\n')
    print('PASS full placed design has no LUTAR-1 and no async result-FIFO resets; route decision recorded')
if __name__=='__main__':main()
