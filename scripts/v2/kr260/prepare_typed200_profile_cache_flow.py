"""Derive independent simulation/physical helpers; never edit sealed tools."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def main():
    files={}
    source=ROOT/'simulation/v2/run_typed200_observe.sh'
    files[ROOT/'simulation/v2/run_typed200_profile_cache.sh']=source.read_text().replace('typed200_observe','typed200_profile_cache').replace('typed200-observe','typed200-profile-cache')
    source=ROOT/'scripts/v2/kr260/build_typed200_profile_tree_physical.py'
    s=source.read_text().replace('typed200_profile_tree','typed200_profile_cache').replace('typed200-profile-tree','typed200-profile-cache')
    s=s.replace('typed200-profile-cache-formal-v2','typed200-profile-cache-formal-v3')
    files[ROOT/'scripts/v2/kr260/build_typed200_profile_cache_physical.py']=s
    for old,new in [('review_typed200_timing_synthesis.py','review_typed200_cache_synthesis.py'),
                    ('review_typed200_timing_placement.py','review_typed200_cache_placement.py'),
                    ('audit_typed200_timing_placement.tcl','audit_typed200_cache_placement.tcl')]:
        files[ROOT/'scripts/v2/kr260'/new]=(ROOT/'scripts/v2/kr260'/old).read_text().replace('profile-tree','profile-cache').replace('profile_tree','profile_cache')
    for p in files:assert not p.exists(),p
    for p,s in files.items():p.write_text(s,newline='\n')
    print('Prepared separate cache regression/physical review tools')
if __name__=='__main__':main()
