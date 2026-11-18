"""Honor latest positive-gain experiment instruction without replaying any work."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[3]

def main():
    src=ROOT/'scripts/v2/kr260/run_typed200_predecode_pipeline.py'
    out=ROOT/'build/v2/typed200-predecode-pipeline-v1'
    snapshot=out/'runner-snapshot.py';assert not snapshot.exists();snapshot.write_bytes(src.read_bytes())
    policy={'authority':'Latest user: probe all stages, then synthesize and place if timing improves',
        'previous_probe_cost_gate_ns':0.05,'current_probe_cost_gate':'strictly positive matched overall probe gain',
        'observed_gain_ns':0.015,'placed_route_gate_ns':0.5,'qualified_baseline_changed':False,
        'reason':'Positive gain warrants requested experiment; it is not robust physical closure',
        'old_runner_state':'Waiting on existing regression; no full build started; replace only this waiting runner'}
    (out/'policy-revision.json').write_text(json.dumps(policy,indent=2)+'\n')
    dst=ROOT/'scripts/v2/kr260/run_typed200_predecode_pipeline_v2.py';assert not dst.exists()
    s=src.read_text().replace('typed200-predecode-pipeline-v1','typed200-predecode-pipeline-v2')
    old="n['overall_slack_ns']-c['overall_slack_ns']>=0.05";assert s.count(old)==1
    s=s.replace(old,"n['overall_slack_ns']>c['overall_slack_ns']")
    dst.write_text(s);print('PASS positive-gain continuation runner; existing jobs reused; route margin unchanged')

if __name__=='__main__':main()
