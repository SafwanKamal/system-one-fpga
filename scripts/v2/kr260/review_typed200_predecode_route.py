"""Audit routed cache experiment only after the unchanged placement gate passes."""
from pathlib import Path
from zipfile import ZipFile
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    b=ROOT/'build/v2/typed200-predecode-physical-v1';dest=b/'route-review.json'
    assert not dest.exists()
    prior=json.loads((b/'placement-review.json').read_text());assert prior['route_approved']
    assert prior['minimum_placed_setup_ns']==0.5 and prior['setup_ns']>=0.5
    for n,h in prior['evidence_sha256'].items():assert sha(b/n)==h,n
    assert json.loads((b/'route-status.json').read_text())['exit_code']==0
    timing=json.loads((b/'route/timing.json').read_text());assert timing['routed']
    log=(b/'route/console.log').read_text()
    for label in ['Number of Unrouted Nets','Number of Node Overlaps']:
        values=re.findall(re.escape(label)+r'\s*=\s*(\d+)',log);assert values and int(values[-1])==0,label
    check=(b/'route/check-timing.rpt').read_text();checks=re.findall(r'checking (\w+) \((\d+)\)',check)
    assert len({n for n,v in checks})==12 and all(int(v)==0 for n,v in checks)
    assert 'All paths are Safely Timed.' in (b/'route/cdc.rpt').read_text()
    assert 'LUTAR-1' not in (b/'route/methodology.rpt').read_text()
    assert 'FIFO asynchronous reset/preset flip-flops: 0' in (b/'route/fifo-reset-mapping.txt').read_text()
    drc=(b/'route/drc.rpt').read_text();assert not re.search(r'\|[^\n]*\|\s*(Error|Critical Warning)\s*\|',drc)
    clocks=(b/'route/timing.rpt').read_text()
    rows=re.findall(r'^(clk_pl_\d+)\s+\{([\d.]+)\s+([\d.]+)\}\s+([\d.]+)\s+([\d.]+)\s*$',clocks,re.M)
    assert {n:tuple(map(float,v)) for n,*v in rows}=={'clk_pl_0':(0,2.5,5,200),'clk_pl_1':(0,5,10,100)}
    assert 'encoder_ooc_200' not in clocks
    exceptions=[]
    with ZipFile(b/'route/routed.dcp') as z:
        for n in z.namelist():
            if not n.endswith('.xdc'):continue
            sources={};file_id=None
            for line in z.read(n).decode().splitlines():
                if line.startswith('set_property SRC_FILE_INFO '):
                    ident=re.search(r' id:(\d+) ',line);path=re.search(r'cfile:(.*?) rfile:',line)
                    if ident and path:sources[ident[1]]=path[1]
                elif line.startswith('set_property src_info '):
                    ident=re.search(r'file:(\d+)',line)
                    if ident:file_id=ident[1]
                elif re.match(r'set_(false_path|multicycle_path|max_delay|clock_groups)\b',line):
                    assert line.startswith('set_false_path ') and '/ip/xpm/xpm_cdc/' in sources[file_id]
                    exceptions.append({'source':sources[file_id],'command':line})
    assert len(exceptions)==prior['exception_count']
    (b/'route/exceptions-classified.json').write_text(json.dumps(exceptions,indent=2)+'\n')
    closed=timing['setup_ns']>=0 and timing['hold_ns']>=0
    assert ('All user specified timing constraints are met.' in clocks)==closed
    files=[b/'placement-review.json',b/'route-status.json',*[p for p in (b/'route').iterdir() if p.is_file()]]
    result={'target_mhz':200,**timing,'sta_passed':closed,'unrouted_nets':0,'node_overlaps':0,
        'exception_count':len(exceptions),'hardware_qualified':False,'package_or_deployment_approved':False,
        'limits':['No300MHz/hardware qualification','R5 target ownership/numerical/WCET and external-delivery gates remain'],
        'evidence_sha256':{p.relative_to(b).as_posix():sha(p) for p in files}}
    dest.write_text(json.dumps(result,indent=2)+'\n');print('Routed STA passed='+str(closed)+'; no deployment qualification')
if __name__=='__main__':main()
