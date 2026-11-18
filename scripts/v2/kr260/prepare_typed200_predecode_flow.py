"""Derive isolated predecode flow; all prior helpers remain frozen."""
from create_typed200_predecode_candidate import ROOT,verify

def main():
    verify();folder=ROOT/'scripts/v2/kr260'
    def cv(s):
        return s.replace('typed200-stage-clamp','typed200-predecode').replace('typed200_stage_clamp','typed200_predecode').replace('typed200-predecode-formal-v1','typed200-predecode-formal-v3').replace("['results']['stage']","['results']['predecode']").replace("'stage-clamp'","'predecode'").replace("'stage_clamp'","'predecode'")
    def save(p,s):assert not p.exists(),p;p.write_text(s)
    src=ROOT/'simulation/v2/run_typed200_stage_clamp.sh';dest=ROOT/'simulation/v2/run_typed200_predecode.sh';assert not dest.exists()
    with dest.open('w',encoding='utf-8',newline='\n') as f:f.write(cv(src.read_text()))
    for old,new in [('build_typed200_stage_clamp_physical.py','build_typed200_predecode_physical.py'),
                    ('review_typed200_stage_clamp_synthesis.py','review_typed200_predecode_synthesis.py'),
                    ('review_typed200_stage_clamp_placement.py','review_typed200_predecode_placement.py'),
                    ('review_typed200_stage_clamp_route.py','review_typed200_predecode_route.py'),
                    ('audit_typed200_stage_clamp_placement.tcl','audit_typed200_predecode_placement.tcl'),
                    ('run_typed200_stage_clamp_pipeline.py','run_typed200_predecode_pipeline.py')]:
        s=cv((folder/old).read_text()).replace('(stage-clamp)','(predecode)')
        save(folder/new,s)
    s=cv((folder/'seal_typed200_stage_clamp.py').read_text())
    s=s.replace("parent=docs/'2026-10-16-typed200-clamp-validation.json'", "parent=docs/'2026-10-16-typed200-stage-clamp-validation.json'")
    s=s.replace("assert p['arithmetic']['passed'] and p['engine']['passed']", "assert p['sequencer']['passed'] and p['arithmetic']['passed'] and p['engine']['passed']")
    anchor="    history=[q for q in (ROOT/'build/v2/typed200-predecode-flow-preparation-v1').glob('*') if q.is_file()]"
    assert s.count(anchor)==1
    s=s.replace(anchor,"    history=[q for i in (1,2) for q in (ROOT/f'build/v2/typed200-predecode-formal-v{i}').glob('*') if q.is_file()]")
    s=s.replace("'whole_domain_arithmetic_proved':True", "'sequencer_cache_stability_and_history_proved':True,'whole_domain_arithmetic_proved':True")
    save(folder/'seal_typed200_predecode.py',s)
    print('PASS separate predecode regression and full physical pipeline helpers')

if __name__=='__main__':main()
