"""Finish the authorized local cache experiment without intermediate restarts."""
from pathlib import Path
import json,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[3]
def main():
    name='typed200-profile-cache-physical-v1'
    sim=ROOT/'build/v2/typed200-profile-cache-integration-v1'
    receipt=ROOT/'build/v2/typed200-profile-cache-formal-v3/receipt.json'
    assert json.loads(receipt.read_text())['passed']
    logdir=ROOT/'build/v2/typed200-profile-cache-pipeline-v1';logdir.mkdir(exist_ok=False)
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
    builder='scripts/v2/kr260/build_typed200_profile_cache_physical.py'
    run([sys.executable,builder,'--name',name,'--stage','synth'],'synthesis')
    run([sys.executable,'scripts/v2/kr260/review_typed200_cache_synthesis.py','--name',name],'synthesis-review')
    run([sys.executable,builder,'--name',name,'--stage','place'],'placement')
    b=ROOT/'build/v2'/name
    # Use the same S: checkpoint and native audit checks as the completed control.
    run(['C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat','-mode','batch','-nojournal',
        '-log',f'S:/build/v2/{name}/placement-audit-vivado.log',
        '-source','S:/scripts/v2/kr260/audit_typed200_cache_placement.tcl','-tclargs',name],
        'placement-audit')
    # Review consumes a finished audit console at the established evidence path.
    (b/'placement-audit-console.log').write_bytes((logdir/'placement-audit.log').read_bytes())
    run([sys.executable,'scripts/v2/kr260/review_typed200_cache_placement.py','--name',name],'placement-review')
    review=json.loads((b/'placement-review.json').read_text())
    print('Placement reviewed; route admission='+str(review['route_approved']),flush=True)
    (logdir/'completion.json').write_text(json.dumps({'completed':True,'placement_review':review,
        'hardware_qualified':False,'no_package_or_deployment':True},indent=2)+'\n')
if __name__=='__main__':main()
