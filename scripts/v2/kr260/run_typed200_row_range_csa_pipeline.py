"""Single authorized regression/synthesis/placement continuation, no deployment."""
from pathlib import Path
from datetime import datetime,timezone
import json,subprocess,sys
ROOT=Path(__file__).resolve().parents[3]
def main():
    logdir=ROOT/'build/v2/typed200-row-range-csa-pipeline-v1';logdir.mkdir(exist_ok=False)
    commands=[]
    def run(cmd,label):
        print(label,flush=True)
        (logdir/'phase.json').write_text(json.dumps({'phase':label,'started_utc':datetime.now(timezone.utc).isoformat(),'argv':cmd},indent=2)+'\n')
        with (logdir/(label+'.log')).open('w') as log:
            r=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        commands.append({'label':label,'argv':cmd,'returncode':r.returncode})
        (logdir/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
        assert r.returncode==0,label
    try:
        probe=ROOT/'build/v2/typed200-row-range-csa-ooc-v1/receipt.json';p=json.loads(probe.read_text());assert p['passed']
        wslroot='/mnt/'+ROOT.drive[0].lower()+str(ROOT)[2:].replace('\\','/')
        run(['wsl','-d','Ubuntu-24.04','--cd',wslroot,'--','env',
            'PATH=/opt/verilator-5.040/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
            'bash','simulation/v2/run_typed200_row_range_csa.sh'],'regression')
        run([sys.executable,'scripts/v2/check_typed200_row_range_csa_functional.py'],'functional-freeze')
        admitted=p['overall_gain_ns']>0 and p['shape_gain_ns']>0
        result={'completed':True,'physical_build_admitted':admitted,'mapped_results':p['results'],
            'hardware_qualified':False,'no_package_or_deployment':True,'routed':False}
        if admitted:
            name='typed200-row-range-csa-physical-v1';b=ROOT/'build/v2'/name
            builder='scripts/v2/kr260/build_typed200_row_range_csa_physical.py'
            run([sys.executable,builder,'--name',name,'--stage','synth'],'synthesis')
            run([sys.executable,'scripts/v2/kr260/review_typed200_row_range_csa_synthesis.py','--name',name],'synthesis-review')
            run([sys.executable,builder,'--name',name,'--stage','place'],'placement')
            run(['C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat','-mode','batch','-nojournal',
                '-log',f'S:/build/v2/{name}/placement-audit-vivado.log',
                '-source','S:/scripts/v2/kr260/audit_typed200_row_range_csa_placement.tcl','-tclargs',name],'placement-audit')
            (b/'placement-audit-console.log').write_bytes((logdir/'placement-audit.log').read_bytes())
            run([sys.executable,'scripts/v2/kr260/review_typed200_row_range_csa_placement.py','--name',name],'placement-review')
            result['placement_review']=json.loads((b/'placement-review.json').read_text())
            result['routing_scope']='No routing started in this synthesis/placement request; preserved +0.500 ns gate applies to any later route'
        else:result['reason']='No strictly positive matched overall and shape probe gain; full build held'
        (logdir/'completion.json').write_text(json.dumps(result,indent=2)+'\n')
        print('COMPLETE full requested row-range experiment',flush=True)
    except BaseException as e:
        (logdir/'failure.json').write_text(json.dumps({'type':type(e).__name__,'reason':str(e),'commands':commands},indent=2)+'\n')
        raise
if __name__=='__main__':main()
