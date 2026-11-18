"""New isolated physical helpers; parent helpers and completed builds stay frozen."""
from create_typed200_clamp_candidate import ROOT, verify

def main():
    verify();folder=ROOT/'scripts/v2/kr260'
    def save(name,text):
        p=folder/name;assert not p.exists(),name;p.write_text(text)
    s=(folder/'build_typed200_profile_cache_physical.py').read_text()
    s=s.replace('create_typed200_profile_cache_candidate','create_typed200_clamp_candidate')
    s=s.replace('typed200-profile-cache-physical','typed200-clamp-physical')
    s=s.replace('typed200-profile-cache-integration','typed200-clamp-integration')
    anchor="    build=ROOT/'build/v2'/a.name;bd=f'S:/build/v2/{a.name}'"
    assert s.count(anchor)==1
    extra='''    clamp_dir=ROOT/'build/v2/typed200-clamp-formal-v5'
    clamp=json.loads((clamp_dir/'receipt.json').read_text());assert clamp['passed']
    for n,h in clamp['source_sha256'].items():assert sha(ROOT/n)==h,n
    for n,h in clamp['artifact_sha256'].items():assert sha(clamp_dir/n)==h,n
    probe_dir=ROOT/'build/v2/typed200-clamp-ooc-v2'
    probe=json.loads((probe_dir/'receipt.json').read_text());assert probe['passed']
    for n,h in probe['source_sha256'].items():assert sha(ROOT/n)==h,n
    for n,h in probe['artifact_sha256'].items():assert sha(probe_dir/n)==h,n
    control=probe['results']['control'];candidate=probe['results']['clamp']
    assert candidate['rounded_slack_ns']-control['rounded_slack_ns']>=0.05,'No credible target-cone gain'
    assert candidate['overall_slack_ns']>=control['overall_slack_ns']-0.05,'Probe overall regression'
'''
    s=s.replace(anchor,extra+anchor)
    anchor="'runner_sha256':sha(Path(__file__))"
    assert s.count(anchor)==1
    s=s.replace(anchor,anchor+",'clamp_proof_sha256':sha(clamp_dir/'receipt.json'),'clamp_probe_sha256':sha(probe_dir/'receipt.json')")
    save('build_typed200_clamp_physical.py',s)
    for old,new in [('review_typed200_cache_synthesis.py','review_typed200_clamp_synthesis.py'),
                    ('review_typed200_cache_placement.py','review_typed200_clamp_placement.py'),
                    ('review_typed200_cache_route.py','review_typed200_clamp_route.py'),
                    ('audit_typed200_cache_placement.tcl','audit_typed200_clamp_placement.tcl')]:
        s=(folder/old).read_text().replace('clock|observe|lut-capture|profile-cache','clock|observe|lut-capture|profile-cache|clamp')
        s=s.replace("'profile-cache':'typed200_profile_cache'","'profile-cache':'typed200_profile_cache','clamp':'typed200_clamp'")
        s=s.replace("'profile-cache':'profile_cache'","'profile-cache':'profile_cache','clamp':'clamp'")
        s=s.replace('typed200-profile-cache-physical-v1','typed200-clamp-physical-v1')
        save(new,s)
    s=(folder/'run_typed200_profile_cache_pipeline.py').read_text()
    s=s.replace('typed200-profile-cache-physical','typed200-clamp-physical')
    s=s.replace('typed200-profile-cache-integration','typed200-clamp-integration')
    s=s.replace('typed200-profile-cache-formal-v3','typed200-clamp-formal-v5')
    s=s.replace('typed200-profile-cache-pipeline','typed200-clamp-pipeline')
    s=s.replace('build_typed200_profile_cache_physical','build_typed200_clamp_physical')
    s=s.replace('review_typed200_cache_','review_typed200_clamp_').replace('audit_typed200_cache_','audit_typed200_clamp_')
    # Before any full synthesis wait only for the EXISTING matched probe and regression.
    anchor="    builder='scripts/v2/kr260/build_typed200_clamp_physical.py'"
    assert s.count(anchor)==1
    extra='''    probe=ROOT/'build/v2/typed200-clamp-ooc-v2'
    while not (probe/'receipt.json').exists():
        for status in probe.glob('*/status.json'):
            assert json.loads(status.read_text())['exit_code']==0,'Probe failed; no full build'
        time.sleep(5)
    mapped=json.loads((probe/'receipt.json').read_text());assert mapped['passed']
    c=mapped['results']['control'];n=mapped['results']['clamp']
    admitted=n['rounded_slack_ns']-c['rounded_slack_ns']>=0.05 and n['overall_slack_ns']>=c['overall_slack_ns']-0.05
    if not admitted:
        (logdir/'completion.json').write_text(json.dumps({'completed':True,'physical_build_admitted':False,
            'reason':'Matched probe does not justify full physical spend','mapped_results':mapped['results'],
            'hardware_qualified':False,'no_package_or_deployment':True},indent=2)+'\\n')
        print('Probe gate held; no full synthesis/placement',flush=True);return
'''
    s=s.replace(anchor,extra+anchor)
    anchor="    (logdir/'completion.json').write_text"
    # Route exactly once only when the original preserved placement gate passes.
    idx=s.rindex(anchor)
    s=s[:idx]+'''    route=None
    if review['route_approved']:
        run([sys.executable,builder,'--name',name,'--stage','route'],'routing')
        run([sys.executable,'scripts/v2/kr260/review_typed200_clamp_route.py'],'route-review')
        route=json.loads((b/'route-review.json').read_text())
'''+s[idx:]
    s=s.replace("'completed':True,'placement_review':review,","'completed':True,'physical_build_admitted':True,'placement_review':review,'route_review':route,")
    save('run_typed200_clamp_pipeline.py',s)
    print('PASS separate physical helpers; full build gated by proof, regression and matched probe')

if __name__=='__main__':main()
