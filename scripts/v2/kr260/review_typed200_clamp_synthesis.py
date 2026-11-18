"""Review exact full-composition inputs and clocks before placement experiments."""
from pathlib import Path
import argparse
import hashlib
import json
import re
from review_typed200_synthesis_clock import utilization

ROOT=Path(__file__).resolve().parents[3]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',required=True);a=ap.parse_args()
    match=re.fullmatch(r'typed200-(clock|observe|lut-capture|profile-cache|clamp)-physical-v[0-9]+',a.name)
    assert match
    b=ROOT/'build/v2'/a.name;dest=b/'synthesis-review.json'
    assert not dest.exists()
    status=json.loads((b/'synth-status.json').read_text())
    assert status['exit_code']==0 and status['target_mhz']==200 and not status['hardware_qualified']
    proof=json.loads((b/'input-proof.json').read_text())
    candidate={'clock':'typed200_flush','observe':'typed200_observe','lut-capture':'typed200_lut_capture','profile-cache':'typed200_profile_cache','clamp':'typed200_clamp'}[match[1]]
    manifest=ROOT/'rtl/v2/candidates'/candidate/'candidate.json'
    assert sha(manifest)==proof['candidate_sha256']
    m=json.loads(manifest.read_text())
    for n,h in m['candidate_sha256'].items():assert sha(manifest.parent/n)==h,n
    assert proof['clock_mhz']==200 and proof['permit_reset_value']==0
    assert proof['control_base']=='0xa0000000' and proof['permit_base']=='0xa0001000'
    assert proof['ooc_period_ns']==5.0
    runner_tag={'clock':'clock','observe':'observe','lut-capture':'lut_capture','profile-cache':'profile_cache','clamp':'clamp'}[match[1]]
    assert sha(ROOT/f'scripts/v2/kr260/build_typed200_{runner_tag}_physical.py')==proof['runner_sha256']
    for file,key in [('encoder-ooc.xdc','ooc_xdc_sha256'),('encoder-pre.tcl','ooc_pre_hook_sha256'),('encoder-post.tcl','ooc_post_hook_sha256')]:
        assert sha(b/file)==proof[key]
    assert sha(ROOT/'rtl/platform/typed200/typed200_encoder_wrapper.v')==proof['wrapper_sha256']
    assert sha(ROOT/'scripts/v2/kr260/create_project_kr260.tcl')==proof['board_setup_sha256']
    omitted={'platform/kr260/kr260_encoder.sv','platform/kr260/kr260_encoder_wrapper.v'}
    actual={p.relative_to(b/'rtl-snapshot').as_posix():sha(p) for p in (b/'rtl-snapshot').rglob('*') if p.is_file()}
    assert set(actual)==set(proof['rtl_sha256'])-omitted
    for n,h in proof['rtl_sha256'].items():
        assert sha(b/'rtl-input'/n)==h,n
        if n not in omitted:assert actual[n]==h,n
        if n!='platform/kr260/typed200_encoder_wrapper.v':assert sha(manifest.parent/n)==h,n
    clock_review=ROOT/'build/v2/typed200-synthesis-clock-v3/clock-experiment-review.json'
    assert sha(clock_review)==proof['clock_experiment_review_sha256']
    er=b/'sysone_v2_kr260.runs/system_encoder_0_synth_1'
    log=(er/'runme.log').read_text()
    assert '0 Critical Warnings and 0 Errors encountered.' in log
    assert 'Parsing XDC File [S:/build/v2/'+a.name+'/encoder-ooc.xdc]' in log
    script=(er/'system_encoder_0.tcl').read_text()
    assert script.index('encoder-pre.tcl')<script.index('\nsynth_design ')
    assert script.index('encoder-post.tcl')>script.index('\nsynth_design ')
    ooc=(b/'encoder-ooc-clocks.rpt').read_text()
    assert re.search(r'^encoder_ooc_200\s+5\.000\s+',ooc,re.M)
    timing=(b/'synthesis-timing.rpt').read_text()
    clock_rows=re.findall(r'^(clk_pl_\d+)\s+\{([\d.]+)\s+([\d.]+)\}\s+([\d.]+)\s+([\d.]+)\s*$',timing,re.M)
    assert {n:tuple(map(float,values)) for n,*values in clock_rows}=={
        'clk_pl_0':(0.0,2.5,5.0,200.0),'clk_pl_1':(0.0,5.0,10.0,100.0)}
    assert 'encoder_ooc_200' not in timing,'OOC clock leaked into full composition'
    for tag in ['unconstrained_internal_endpoints','multiple_clock','loops','latch_loops']:
        assert re.search(r'checking '+tag+r' \(0\)',timing),tag
    row=re.search(r'WNS\(ns\).*?\n\s*[- ]+\n([^\n]+)',timing,re.S)[1].split()
    files=[manifest,b/'input-proof.json',b/'synth-status.json',b/'synth.tcl',
        b/'synthesis-timing.rpt',b/'synthesis-critical.rpt',b/'synthesis-utilization.rpt',b/'synthesized.dcp',
        b/'encoder-ooc.xdc',b/'encoder-pre.tcl',b/'encoder-post.tcl',b/'encoder-ooc-clocks.rpt',
        b/'encoder-ooc-timing.rpt',er/'runme.log',er/'system_encoder_0.tcl',clock_review]
    result={'placement_experiment_admitted':True,'target_mhz':200,'candidate':candidate,
        'compiled_rtl_count':len(actual),'staged_rtl_count':len(proof['rtl_sha256']),
        'synthesis_setup_ns':float(row[0]),'synthesis_hold_ns':float(row[4]),
        'resources':utilization(b/'synthesis-utilization.rpt'),
        'ooc_clock_applied_during_synthesis':True,'composed_clocks_preserved':True,
        'route_approved':False,'hardware_qualified':False,'deployment_approved':False,
        'limits':['Synthesis timing is estimated','Post-opt clock checks and CDC/methodology still required',
                  'Route admission requires at least +0.500ns placed setup','No hardware or WCET evidence'],
        'evidence_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in files}}
    dest.write_text(json.dumps(result,indent=2)+'\n')
    print('PASS exact input/clock review; placement experiment admitted; estimated setup',result['synthesis_setup_ns'])


if __name__=='__main__':
    main()
