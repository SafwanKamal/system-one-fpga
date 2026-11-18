"""Finish the authorized local cache experiment without intermediate restarts."""
from pathlib import Path
import json,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[3]
def main():
    name='typed200-predecode-physical-v1'
    sim=ROOT/'build/v2/typed200-predecode-integration-v1'
    receipt=ROOT/'build/v2/typed200-predecode-formal-v3/receipt.json'
    assert json.loads(receipt.read_text())['passed']
    logdir=ROOT/'build/v2/typed200-predecode-pipeline-v2';logdir.mkdir(exist_ok=False)
    commands=[]
    def run(cmd,label):
        print(label,flush=True)
        with (logdir/(label+'.log')).open('w') as log:
            r=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        commands.append({'label':label,'argv':cmd,'returncode':r.returncode})
        (logdir/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
        assert r.returncode==0,label
    # Existing foreground regression is the only dependency being waited on.
    # This is a single invocation, not a scheduled automation or board monitor.
    print('Waiting for existing full regression; no duplicate simulation',flush=True)
    while not (sim/'completion-status.json').exists():time.sleep(5)
    assert json.loads((sim/'completion-status.json').read_text())=={'exit_code':0,'complete':True}
    probe=ROOT/'build/v2/typed200-predecode-ooc-v1'
    while not (probe/'receipt.json').exists():
        for status in probe.glob('*/status.json'):
            assert json.loads(status.read_text())['exit_code']==0,'Probe failed; no full build'
        time.sleep(5)
    mapped=json.loads((probe/'receipt.json').read_text());assert mapped['passed']
    c=mapped['results']['control'];n=mapped['results']['predecode']
    admitted=n['overall_slack_ns']>c['overall_slack_ns'] and n['overall_slack_ns']>=c['overall_slack_ns']-0.05
    if not admitted:
        (logdir/'completion.json').write_text(json.dumps({'completed':True,'physical_build_admitted':False,
            'reason':'Matched probe does not justify full physical spend','mapped_results':mapped['results'],
            'hardware_qualified':False,'no_package_or_deployment':True},indent=2)+'\n')
        print('Probe gate held; no full synthesis/placement',flush=True);return
    builder='scripts/v2/kr260/build_typed200_predecode_physical.py'
    run([sys.executable,builder,'--name',name,'--stage','synth'],'synthesis')
    run([sys.executable,'scripts/v2/kr260/review_typed200_predecode_synthesis.py','--name',name],'synthesis-review')
    run([sys.executable,builder,'--name',name,'--stage','place'],'placement')
    b=ROOT/'build/v2'/name
    # Use the same S: checkpoint and native audit checks as the completed control.
    run(['C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat','-mode','batch','-nojournal',
        '-log',f'S:/build/v2/{name}/placement-audit-vivado.log',
        '-source','S:/scripts/v2/kr260/audit_typed200_predecode_placement.tcl','-tclargs',name],
        'placement-audit')
    # Review consumes a finished audit console at the established evidence path.
    (b/'placement-audit-console.log').write_bytes((logdir/'placement-audit.log').read_bytes())
    run([sys.executable,'scripts/v2/kr260/review_typed200_predecode_placement.py','--name',name],'placement-review')
    review=json.loads((b/'placement-review.json').read_text())
    print('Placement reviewed; route admission='+str(review['route_approved']),flush=True)
    route=None
    if review['route_approved']:
        run([sys.executable,builder,'--name',name,'--stage','route'],'routing')
        run([sys.executable,'scripts/v2/kr260/review_typed200_predecode_route.py'],'route-review')
        route=json.loads((b/'route-review.json').read_text())
    (logdir/'completion.json').write_text(json.dumps({'completed':True,'physical_build_admitted':True,'placement_review':review,'route_review':route,
        'hardware_qualified':False,'no_package_or_deployment':True},indent=2)+'\n')
if __name__=='__main__':main()
