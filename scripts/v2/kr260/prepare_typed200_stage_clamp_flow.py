"""Separate flow derived from preserved clamp helpers; no parent mutation."""
from create_typed200_stage_clamp_candidate import ROOT,verify

def main():
    verify();folder=ROOT/'scripts/v2/kr260'
    def convert(s):
        return s.replace('typed200-clamp','typed200-stage-clamp').replace('typed200_clamp','typed200_stage_clamp').replace('typed200-stage-clamp-formal-v5','typed200-stage-clamp-formal-v1').replace('typed200-stage-clamp-ooc-v2','typed200-stage-clamp-ooc-v1').replace("['results']['clamp']","['results']['stage']")
    def save(p,s):
        if p.exists():assert p.read_text()==s,p
        else:p.write_text(s)
    src=ROOT/'simulation/v2/run_typed200_clamp.sh';dest=ROOT/'simulation/v2/run_typed200_stage_clamp.sh'
    if dest.exists():assert dest.read_text()==convert(src.read_text())
    else:
        with dest.open('w',encoding='utf-8',newline='\n') as f:f.write(convert(src.read_text()))
    for old,new in [('build_typed200_clamp_physical.py','build_typed200_stage_clamp_physical.py'),
                    ('review_typed200_clamp_synthesis.py','review_typed200_stage_clamp_synthesis.py'),
                    ('review_typed200_clamp_placement.py','review_typed200_stage_clamp_placement.py'),
                    ('review_typed200_clamp_route.py','review_typed200_stage_clamp_route.py'),
                    ('audit_typed200_clamp_placement.tcl','audit_typed200_stage_clamp_placement.tcl'),
                    ('run_typed200_clamp_pipeline.py','run_typed200_stage_clamp_pipeline.py')]:
        s=convert((folder/old).read_text())
        s=s.replace('clock|observe|lut-capture|profile-cache|clamp','stage-clamp')
        s=s.replace("'clamp':'typed200_stage_clamp'","'clamp':'typed200_stage_clamp','stage-clamp':'typed200_stage_clamp'")
        s=s.replace("'clamp':'clamp'","'clamp':'clamp','stage-clamp':'stage_clamp'")
        s=s.replace("candidate['rounded_slack_ns']-control['rounded_slack_ns']>=0.05", "candidate['overall_slack_ns']-control['overall_slack_ns']>=0.05")
        s=s.replace("n['rounded_slack_ns']-c['rounded_slack_ns']>=0.05", "n['overall_slack_ns']-c['overall_slack_ns']>=0.05")
        if new.startswith('audit_'):
            anchor='close_design';assert s.count(anchor)==1
            extra='''set skip_regs [get_cells -quiet -hier -filter {NAME =~ *add_skip_inst/skip_clamped_reg* && REF_NAME =~ FD*}]
if {[llength $skip_regs] != 128} {error "Expected128 clamped stage registers"}
report_timing -to $skip_regs -delay_type max -max_paths 10 -input_pins -file [file join $out rounding-stage-paths.rpt]
set skip_pins [get_pins -of_objects $skip_regs -filter {REF_PIN_NAME == Q}]
report_timing -from $skip_pins -delay_type max -max_paths 10 -input_pins -file [file join $out output-stage-paths.rpt]
'''
            s=s.replace(anchor,extra+anchor)
        save(folder/new,s)
    s=convert((folder/'seal_typed200_clamp.py').read_text())
    # The predecessor is the finished Boolean-clamp experiment, not the current output.
    s=s.replace("parent=docs/'2026-10-16-typed200-profile-cache-validation.json'", "parent=docs/'2026-10-16-typed200-clamp-validation.json'")
    s=s.replace("'full_engine_equivalence_points':966", "'full_engine_equivalence_points':p['engine']['equivalence_points']")
    s=s.replace("'arithmetic_domain'", "'arithmetic_domain'")
    # Do not pretend older failed attempts belong to this new namespace.
    begin=s.index('    history=[]');end=s.index('    result=',begin)
    s=s[:begin]+'''    history=[]
'''+s[end:]
    s=s.replace("ROOT/'scripts/v2/prove_typed200_stage_clamp.py',ROOT/'scripts/v2/snapshot_typed200_deployment_profile.py',", "ROOT/'scripts/v2/prove_typed200_stage_clamp.py',")
    save(folder/'seal_typed200_stage_clamp.py',s)
    print('PASS separate stage-clamp regression/full-flow helpers; both-stage overall gain required')

if __name__=='__main__':main()
