"""Read-only provenance and scoped timing-command inspection for CSA routing."""
from pathlib import Path
from zipfile import ZipFile
from collections import Counter
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[3]
PARENT=ROOT/'build/v2/typed200-row-range-csa-physical-v1'
OUT=ROOT/'build/v2/typed200-row-range-csa-route-v1'
SEAL=ROOT/'docs/research/2026-10-16-typed200-row-range-csa-validation.json'
MAP_KEYS=('preserved_sha256','source_sha256','documentation_sha256','evidence_sha256','historical_evidence_sha256')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def verify_parent():
    r=json.loads(SEAL.read_text());files={}
    for key in MAP_KEYS:
        for n,h in r[key].items():assert sha(ROOT/n)==h,n;files[n]=h
    files[SEAL.relative_to(ROOT).as_posix()]=sha(SEAL)
    review=json.loads((PARENT/'placement-review.json').read_text())
    assert review['route_approved'] and review['minimum_placed_setup_ns']==0.5 and review['setup_ns']>=0.5
    assert review['target_mhz']==200 and not review['routed']
    for n,h in review['evidence_sha256'].items():assert sha(PARENT/n)==h,n
    return files,review
def constraints(checkpoint):
    records=[];properties=[]
    with ZipFile(checkpoint) as z:
        for n in z.namelist():
            if not n.endswith('.xdc'):continue
            context='';sources={};file_id=None
            for line in z.read(n).decode().splitlines():
                if not line.strip() or line.startswith('#'):continue
                if line.startswith('current_instance'):context=line;continue
                if line.startswith('set_property SRC_FILE_INFO '):
                    ident=re.search(r' id:(\d+) ',line);path=re.search(r'cfile:(.*?) rfile:',line);scope=re.search(r'scoped_inst:(\S+)',line)
                    if ident and path:sources[ident[1]]={'source_path':path[1],'source_scope':scope[1] if scope else ''}
                if line.startswith('set_property src_info '):
                    ident=re.search(r'file:(\d+)',line)
                    if ident:file_id=ident[1]
                if line.startswith('set_property '):
                    # Physical placement/metadata properties may change. Preserve all explicit
                    # timing properties, should any appear in a future serialized checkpoint.
                    prop=line.split()[1]
                    if re.search(r'(?i)PERIOD|UNCERTAINTY|JITTER|DERATE|INPUT_DELAY|OUTPUT_DELAY|MAX_DELAY|MIN_DELAY|CASE_ANALYSIS|DISABLE_TIMING|OPERATING_CONDITIONS',prop):
                        properties.append({'context':context,'command':line})
                    continue
                item={'context':context,'command':line,**sources.get(file_id,{})}
                records.append(item)
    clocks=[r for r in records if r['command'].startswith('create_clock ')]
    exceptions=[r for r in records if r['command'].startswith('set_false_path ')]
    assert len(clocks)==2 and len(exceptions)==39 and len(records)==41,'Unexpected explicit timing commands'
    assert all('/ip/xpm/xpm_cdc/' in r.get('source_path','') for r in exceptions)
    return {'commands':records,'timing_properties':properties}
def signature(c):
    return Counter((r['context'],r['command']) for r in c['commands']+c['timing_properties'])
