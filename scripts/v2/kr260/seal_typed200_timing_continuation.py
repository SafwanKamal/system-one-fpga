"""Rehash preserved baselines and bind completed local timing experiments."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json

ROOT=Path(__file__).resolve().parents[3]
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def main():
    docs=ROOT/'docs/research'
    dest=docs/'2026-10-15-typed200-timing-continuation-validation.json'
    assert not dest.exists(),'Preserve completed evidence seal'
    recorded={}
    def check(name,expected):
        actual=sha(ROOT/name);assert actual==expected,name
        recorded[name]=actual
    preservation=docs/'2026-10-14-system-one-preservation.json'
    protected=json.loads(preservation.read_text())['file_checks']
    for row in protected:check(row['path'],row['before_sha256'])
    prior_names=['typed-intent-validation','typed200-validation',
        'typed200-transport-validation','typed200-physical-r5-validation',
        'typed200-flush-validation','typed200-timing-functional-evidence',
        'typed200-validation-functional-evidence']
    counts={}
    for name in prior_names:
        p=docs/f'2026-10-15-{name}.json';d=json.loads(p.read_text());count=0
        for key in ['source_sha256','documentation_sha256','evidence_sha256']:
            for n,h in d.get(key,{}).items():check(n,h);count+=1
        counts[p.name]=count
        recorded[p.relative_to(ROOT).as_posix()]=sha(p)
    check('build/v2/kr260-app-attention-context-capture-large.tar.gz',
        'ecd320163baa3c289c64e069186497974d4703039df4a455bc8620d357d7ec99')
    reviews={}
    for directory,filename in [
        ('typed200-synthesis-clock-v3','clock-experiment-review.json'),
        ('typed200-clock-physical-v1','synthesis-review.json'),
        ('typed200-clock-physical-v1','placement-review.json'),
        ('typed200-clock-physical-v1','postplace-review.json'),
        ('typed200-profile-tree-physical-v1','synthesis-review.json'),
        ('typed200-profile-tree-physical-v1','placement-review.json')]:
        b=ROOT/'build/v2'/directory;p=b/filename;d=json.loads(p.read_text())
        for n,h in d.get('evidence_sha256',{}).items():
            candidate=b/n
            if not candidate.exists():candidate=ROOT/n
            check(candidate.relative_to(ROOT).as_posix(),h)
        reviews[p.relative_to(ROOT).as_posix()]=sha(p)
    additions=[Path(__file__),docs/'2026-10-15-typed200-timing-continuation.md',
        docs/'2026-10-15-typed200-target-qualification-plan.md']
    for pattern in ['*typed200*timing*.py','*typed200*timing*.tcl',
                    'build_typed200_*physical.py','check_typed200_synthesis_clock.py']:
        additions.extend((ROOT/'scripts/v2/kr260').glob(pattern))
    result={'verified_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Completed local functional/synthesis/placement experiments; no board qualification',
        'protected_paths_checked':len(protected),'all_protected_files_unchanged':True,
        'prior_seal_entries_checked':counts,'preserved_sha256':recorded,
        'review_sha256':reviews,
        'new_source_and_report_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in additions},
        'board_programming_performed':False,'new_hardware_qualification':False,
        'limits':['No 300MHz closure','No R5 target execution/WCET certificate',
                  'Typed local terminal bound does not guarantee successful inference or external delivery']}
    dest.write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS preserved {len(protected)} baseline paths and {sum(counts.values())} prior-seal entries; completed reviews bound')
if __name__=='__main__':main()
