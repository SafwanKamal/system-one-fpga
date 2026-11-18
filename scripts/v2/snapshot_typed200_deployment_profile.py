"""Read-only, explicitly unqualified deployment inventory; never a loader."""
from pathlib import Path
import hashlib,json

ROOT=Path(__file__).resolve().parents[2]
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def main():
    dest=ROOT/'docs/research/2026-10-16-typed200-deployment-profile-draft.json'
    assert not dest.exists(),'Preserve inventory snapshot'
    files={
        'qualified_encoder_recovery_archive':'build/v2/kr260-app-attention-context-capture-large.tar.gz',
        'unqualified_typed_placed_checkpoint':'build/v2/typed200-profile-cache-physical-v1/place/placed.dcp',
        'typed_placement_review':'build/v2/typed200-profile-cache-physical-v1/placement-review.json',
        'typed_physical_validation':'docs/research/2026-10-16-typed200-profile-cache-validation.json',
        'diagnostic_r5_elf':'build/v2/typed200-timed-host-v3/typed200-trace.elf',
        'diagnostic_r5_elf_audit':'build/v2/typed200-timed-host-v3/audit.json',
        'diagnostic_r5_validation':'docs/research/2026-10-15-typed200-timed-validation.json',
        'typed_contract':'firmware/typed_intent/generated/contract.json',
        'typed_model_manifest':'firmware/typed_intent/generated/manifest.json',
        'active_digest_transport':'firmware/typed200_v2/typed200.c',
        'r5_startup_source':'firmware/typed200_timed/platform.c',
        'r5_pmu_source':'firmware/typed200_timed/pmu.c',
        'r5_mailbox_abi':'firmware/typed200_r5/service.h'
    }
    inventory={role:{'path':n,'sha256':sha(ROOT/n)} for role,n in files.items()}
    assert inventory['qualified_encoder_recovery_archive']['sha256']=='ecd320163baa3c289c64e069186497974d4703039df4a455bc8620d357d7ec99'
    review=json.loads((ROOT/files['typed_placement_review']).read_text());assert not review['route_approved']
    audit=json.loads((ROOT/files['diagnostic_r5_elf_audit']).read_text());assert audit['passed']
    model=json.loads((ROOT/files['typed_model_manifest']).read_text())
    r={
        'schema':'sysone.typed200.deployment-profile-draft.v1',
        'purpose':'Exact local artifact inventory and unresolved target evidence; not a deployable profile or certificate',
        'deployment_ready':False,'target_executed':False,'successful_inference_wcet_certified':False,
        'external_delivery_bound_certified':False,'artifacts':inventory,
        'artifact_compatibility':{
            'qualified_archive_is_encoder_baseline_only':True,
            'typed_checkpoint_has_no_admitted_route_or_package':True,
            'r5_elf_is_unexecuted_diagnostic_candidate':True,
            'do_not_combine_inventory_as_a_qualified_system':True},
        'contract':{
            'abi':'0x54590201',
            'identity_sha256':'8133633315487f8f322ecac49e95e7aca3801d00fccb4b4fba36026c5b2752d2',
            'model_sha256':model['image_sha256'],'model_bytes':33916928,
            'hidden_width':384,'tokens_min':1,'tokens_max':128,
            'selected_rows':'contiguous nonempty subset within admitted tokens',
            'outcome_type':'Accepted(label) | Clarify | Abstain | HardwareFault | DeadlineExceeded | InvalidInput; non-Accepted label and all reserved scores are zero',
            'outcome_tags':{'Accepted':1,'Clarify':2,'Abstain':3,'HardwareFault':4,'DeadlineExceeded':5,'InvalidInput':6},
            'active_head_policy':'Frozen head proposes Accepted or HardwareFault; no new confidence/Clarify/Abstain policy is introduced',
            'numerical_policy':'frozen binary64 scaled head; first-index tie; 18 labels; no confidence/OOS guarantee'},
        'intended_partition':{
            'a53':'ingress/tokenization/staging before admission; consume after local terminal',
            'r5':'exclusive admitted service, hidden-to-TCM copy and fixed head',
            'pl':'identity/shape/epoch checks, encoder, live bus/error veto and independent local deadline',
            'concurrent_master_policy':None},
        'addresses':{
            'csr':'0xa0000000','permit_gpio':'0xa0001000','model':'0x60000000',
            'ids':1645215744,'hidden_result':1645219840,
            'r5_local_trace':audit['trace_address'],'r5_local_trace_bytes':audit['trace_bytes'],
            'r5_local_pmu_config':'0x2f180','mailbox_bytes':384,'shared_noload_bytes':audit['shared_bytes'],
            'a53_to_r5_tcm_translation':None},
        'claim_boundaries':{
            'local_terminal':'Conditional terminal-by-D PL cycles under uninterrupted clock/reset and contract assumptions; includes fail-closed outcomes',
            'useful_success':'Requires justified native/drain/copy/head/proposal/publication service bounds; not supplied',
            'external_delivery':'A53/consumer/network observation separate from local terminal; no bound supplied',
            'clock_stop':'Uninterrupted-cycle argument does not bound wall time with stopped PL clock; independent supervisor required'},
        'unresolved_target_gates':{name:{'status':'unresolved','evidence':None} for name in (
            'typed_routed_setup_hold_and_recoverable_package',
            'loader_identity_and_load_order_after_nobits_zeroing',
            'rpu_split_mode_tcm_ecc_and_reset_entry',
            'measured_pl_r5_clocks_and_minimum_ratio',
            'fresh_session_and_fullrate_exclusive_pmu_configuration',
            'enforced_a53_dma_debug_and_other_master_exclusion',
            'immutable_model_program_input_result_and_mmio_ownership',
            'target_head_numerical_goldens_ties_and_scaled_argmax',
            'owner_local_target_phase_captures_and_decoder_review',
            'bounded_ddr_interconnect_and_mmio_service',
            'nonoverlapping_phase_wcet_composition_and_margin',
            'cpu_bus_consumer_fault_and_clock_reset_campaign',
            'independent_external_delivery_supervisor_and_recovery')},
        'safety_note':'Software attestations, R5 MPU settings, core affinity and observed maxima do not discharge global ownership or WCET gates'
    }
    with dest.open('x',encoding='utf-8') as f:json.dump(r,f,indent=2);f.write('\n')
    print('PASS exact artifact inventory; deployment_ready=false; 13 target gates unresolved')

if __name__=='__main__':main()
