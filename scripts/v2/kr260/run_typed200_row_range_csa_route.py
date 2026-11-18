"""Route a byte-identical reviewed checkpoint in a new standalone directory."""
from datetime import datetime,timezone
from pathlib import Path
import json,shutil,subprocess,sys
from typed200_row_range_csa_route_common import ROOT,PARENT,OUT,SEAL,sha,verify_parent,constraints
def main():
    preserved,review=verify_parent();assert Path('S:/').samefile(ROOT)
    OUT.mkdir(exist_ok=False);(OUT/'input').mkdir()
    placed=PARENT/'place/placed.dcp';shutil.copyfile(placed,OUT/'input/placed.dcp')
    assert sha(placed)==sha(OUT/'input/placed.dcp')==review['evidence_sha256']['place/placed.dcp']
    timing=constraints(placed);(OUT/'input-constraints.json').write_text(json.dumps(timing,indent=2)+'\n')
    script=ROOT/'scripts/v2/kr260/route_typed200_row_range_csa.tcl';shutil.copyfile(script,OUT/'route.tcl')
    helpers=[Path(__file__),script,ROOT/'scripts/v2/kr260/typed200_row_range_csa_route_common.py',ROOT/'scripts/v2/kr260/review_typed200_row_range_csa_route.py']
    receipt={'started_utc':datetime.now(timezone.utc).isoformat(),'target_mhz':200,
        'input_checkpoint':placed.relative_to(ROOT).as_posix(),'input_checkpoint_sha256':sha(placed),
        'copied_checkpoint_sha256':sha(OUT/'input/placed.dcp'),'parent_seal_sha256':sha(SEAL),
        'placement_review_sha256':sha(PARENT/'placement-review.json'),'placed_setup_ns':review['setup_ns'],
        'required_placed_setup_ns':0.5,'preserved_unique_files':len(preserved),'preserved_sha256':preserved,
        'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in helpers},
        'staged_script_sha256':sha(OUT/'route.tcl'),'constraints_changed':False,
        'scope':'Default phys_opt_design and route_design on an exact standalone copy; no project open, bitstream, package or board action'}
    (OUT/'input-proof.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('Verified eligible sealed checkpoint; starting standalone timing-only routing',flush=True)
    with (OUT/'console.log').open('w') as log:
        r=subprocess.run(['C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat','-mode','batch','-nojournal',
            '-log','S:/build/v2/typed200-row-range-csa-route-v1/vivado.log','-source','S:/build/v2/typed200-row-range-csa-route-v1/route.tcl'],cwd=OUT,stdout=log,stderr=subprocess.STDOUT)
    (OUT/'native-status.json').write_text(json.dumps({'exit_code':r.returncode,'finished_utc':datetime.now(timezone.utc).isoformat()},indent=2)+'\n')
    assert r.returncode==0,'Native route failed; preserve attempt'
    print('Native route complete; reviewing exact constraints and routed evidence',flush=True)
    with (OUT/'review-console.log').open('w') as log:
        review_result=subprocess.run([sys.executable,str(ROOT/'scripts/v2/kr260/review_typed200_row_range_csa_route.py')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    (OUT/'completion.json').write_text(json.dumps({'native_exit_code':r.returncode,'review_exit_code':review_result.returncode,
        'completed':review_result.returncode==0,'hardware_qualified':False,'package_or_deployment_approved':False},indent=2)+'\n')
    assert review_result.returncode==0,'Review failed; preserve all evidence'
    print('COMPLETE timing-only route and review',flush=True)
if __name__=='__main__':main()
