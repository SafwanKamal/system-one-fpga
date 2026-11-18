"""Admit routing only if the separate physical-only optimization repairs setup."""
from pathlib import Path
from zipfile import ZipFile
import argparse,hashlib,json,re
ROOT=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',required=True);a=ap.parse_args()
    assert re.fullmatch(r'typed200-(clock|profile-tree)-physical-v[0-9]+',a.name)
    b=ROOT/'build/v2'/a.name;dest=b/'postplace-review.json'
    assert not dest.exists(),'Preserve completed review'
    prior=json.loads((b/'placement-review.json').read_text())
    for n,h in prior['evidence_sha256'].items():assert sha(b/n)==h,n
    out=b/'postplace-opt-v1'
    assert json.loads((b/'postplace-opt-v1-status.json').read_text(encoding='utf-8-sig'))['exit_code']==0
    assert 'Exiting Vivado' in (b/'postplace-opt-v1-console.log').read_text()
    t=json.loads((out/'timing.json').read_text())
    check=(out/'check-timing.rpt').read_text()
    checks=re.findall(r'checking (\w+) \((\d+)\)',check)
    assert len({name for name,n in checks})==12 and all(int(n)==0 for name,n in checks)
    assert 'LUTAR-1' not in (out/'methodology.rpt').read_text()
    assert 'FIFO asynchronous reset/preset flip-flops: 0' in (out/'fifo-reset-mapping.txt').read_text()
    assert 'All paths are Safely Timed.' in (out/'cdc.rpt').read_text()
    clocks=(out/'clocks.rpt').read_text()
    assert re.search(r'^clk_pl_0\s+5\.000\s+',clocks,re.M) and re.search(r'^clk_pl_1\s+10\.000\s+',clocks,re.M)
    assert 'encoder_ooc_200' not in clocks
    retain=(out/'retention.txt').read_text()
    for n in ['epoch_inst','publication_inst','deployment_permit']:
        assert re.search(n+r'\* cells [1-9]',retain),n
    exceptions=[]
    with ZipFile(out/'optimized.dcp') as archive:
        for name in archive.namelist():
            if not name.endswith('.xdc'):continue
            sources={};file_id=None
            for line in archive.read(name).decode().splitlines():
                if line.startswith('set_property SRC_FILE_INFO '):
                    ident=re.search(r' id:(\d+) ',line);path=re.search(r'cfile:(.*?) rfile:',line)
                    scope=re.search(r'scoped_inst:(\S+)',line)
                    if ident and path:sources[ident[1]]={'path':path[1],'scope':scope[1] if scope else ''}
                elif line.startswith('set_property src_info '):
                    ident=re.search(r'file:(\d+)',line)
                    if ident:file_id=ident[1]
                elif re.match(r'set_(false_path|multicycle_path|max_delay|clock_groups)\b',line):
                    src=sources[file_id]
                    assert '/ip/xpm/xpm_cdc/' in src['path'] and line.startswith('set_false_path '),line
                    exceptions.append({'command':line,**src})
    assert len(exceptions)==prior['exception_count']
    (out/'exceptions-classified.json').write_text(json.dumps(exceptions,indent=2)+'\n')

    assert not re.search(r'\|[^\n]*\|\s*Error\s*\|',(out/'drc.rpt').read_text())
    files=[b/'placement-review.json',b/'place/placed.dcp',*[p for p in out.iterdir() if p.is_file()]]
    r={'route_approved':t['setup_ns']>=0.5,'route_checkpoint':'postplace-opt-v1/optimized.dcp',
        'approval_scope':'Timing-only route experiment; no package or deployment approval',
        'target_mhz':200,'minimum_placed_setup_ns':0.5,**t,'rtl_changed':False,'clock_constraints_relaxed':False,
        'decision':'At least +0.500ns optimized setup required before routing; pre-route hold requires router repair',
        'evidence_sha256':{p.relative_to(b).as_posix():sha(p) for p in files}}
    dest.write_text(json.dumps(r,indent=2)+'\n')
    print('POSTPLACE route approved='+str(r['route_approved'])+f'; setup {t["setup_ns"]:.3f} ns, hold {t["hold_ns"]:.3f} ns')
if __name__=='__main__':main()
