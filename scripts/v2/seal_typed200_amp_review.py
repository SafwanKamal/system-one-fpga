"""Seal research evidence only. Does not promote any AMP candidate/readiness gate."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/v2/typed200-amp-feasibility-v1'
DOC=ROOT/'docs/research'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    dst=DOC/'2026-10-16-typed200-amp-feasibility-validation.json'
    assert not dst.exists(),'Preserve existing review seal'
    before=json.loads((OUT/'preservation-before.json').read_text(encoding='utf-8'))
    audit=json.loads((OUT/'source-audit.json').read_text(encoding='utf-8'))
    policy=json.loads((DOC/'2026-10-16-typed200-amp-policy-draft.json').read_text(encoding='utf-8'))
    assert before['passed'] and before['files']==len(before['preserved_sha256'])
    assert audit['investigation_complete'] and not audit['deployable']
    assert not any(policy[k] for k in ['hardware_action_authorized','implemented',
                                     'target_executed','hardware_exclusivity_verified','wcet_certified'])
    assert all(not r['verified'] for r in policy['resource_policy'])
    assert policy['timeouts']['deadline_cancels_axi'] is False
    assert policy['timeouts']['may_reuse_buffers_on_timeout_alone'] is False
    assert audit['generated_ps_ethernet_enables']=={f'ENET{i}':'0' for i in range(4)}
    for name,digest in before['preserved_sha256'].items():assert sha(ROOT/name)==digest,name
    sources={p.relative_to(ROOT).as_posix():sha(p) for p in [
       ROOT/'scripts/v2/review_typed200_amp.py',Path(__file__).resolve()]}
    docs={p.relative_to(ROOT).as_posix():sha(p) for p in [
       DOC/'2026-10-16-typed200-amp-feasibility.md',
       DOC/'2026-10-16-typed200-amp-experiment-plan.md',
       DOC/'2026-10-16-typed200-amp-policy-draft.json',
       DOC/'2026-10-16-typed200-amp-ownership-matrix.csv']}
    evidence={p.relative_to(ROOT).as_posix():sha(p) for p in OUT.rglob('*') if p.is_file()}
    result=dict(investigation_complete=True,baseline_and_all_previous_seals_preserved=True,
      previously_sealed_files_verified=len(before['preserved_sha256']),
      local_source_audit_passed=True,new_proofs_or_simulations_run=False,
      new_firmware_rtl_or_fpga_builds=False,board_contact=False,deployed=False,
      amp_candidate_implemented=False,hardware_exclusivity_verified=False,
      successful_inference_deadline_certified=False,ssh_delivery_deadline_certified=False,
      wcet_certified=False,hardware_action_ready=False,
      recommendation='Separate one-shot AMP candidate: Linux/SSH A53 management, protected R5/PL inference; local typed deadline first',
      limitations=['Current v5 and PMU policy do not support concurrent Linux',
       'Current standalone PS metadata disables all four GEM interfaces',
       'Current Lite endpoint has no requester metadata; filter must precede conversion',
       'Shared DDR/control service and successful completion unbounded in current evidence',
       'Pinned 2025.2 Linux sources are reference artifacts, not identified live-board binaries',
       'XAPP1353 documentation inspected; attempted source archive download returned HTML'],
      preserved_sha256=before['preserved_sha256'],source_sha256=sources,
      documentation_sha256=docs,evidence_sha256=evidence,
      installed_primary_sha256=audit['installed_primary_sha256'])
    dst.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('PASS AMP architectural review sealed;',len(before['preserved_sha256']),
          'prior files unchanged. No deployed/implemented AMP or WCET claim.')
if __name__=='__main__':main()
