"""Incremental full-byte profile equality in the AXIL shadow bank, separate RTL."""
import argparse,json,shutil
from create_typed200_flush_candidate import ROOT,OUT as PARENT,verify as parent_verify,sha
OUT=ROOT/'rtl/v2/candidates/typed200_profile_cache'
CHANGED={'contracts/typed_intent_axil.sv','contracts/typed_intent_guard.sv'}
def verify():
    parent=parent_verify();m=json.loads((OUT/'candidate.json').read_text())
    assert sha(PARENT/'candidate.json')==m['parent_manifest_sha256']
    actual={p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.suffix in ('.sv','.v')}
    assert actual==m['candidate_sha256']
    assert {n for n in actual if actual[n]!=parent['candidate_sha256'].get(n)}==CHANGED
    return m
def create():
    parent_verify();assert not OUT.exists();shutil.copytree(PARENT,OUT)
    p=OUT/'contracts/typed_intent_guard.sv';s=p.read_text()
    assert s.count('request_contract==CONTRACT')==2
    s=s.replace('input logic [255:0] request_contract,',
                'input logic [255:0] request_contract,\n    input wire request_contract_matches,')
    assert 'input wire request_contract_matches,' in s
    s=s.replace('request_contract==CONTRACT','request_contract_matches');p.write_text(s)
    p=OUT/'contracts/typed_intent_axil.sv';s=p.read_text()
    anchor='    logic aw_full,w_full;';assert s.count(anchor)==1
    s=s.replace(anchor,'''    localparam logic [255:0] PROFILE=256'h8133633315487f8f322ecac49e95e7aca3801d00fccb4b4fba36026c5b2752d2;
    // Each bit equals its stored byte's equality, including unwritten reset bytes.
    // Update on the SAME execute edge/WSTRB as that byte. Never cache live quiet,
    // errors, epoch, ownership, request sequencing or deadline permission.
    (* keep = "true" *) logic [31:0] profile_byte_equal;
    (* keep = "true" *) wire [3:0] profile_group_equal;
    for(genvar w=0;w<8;w++) begin : gen_profile_word
        for(genvar b=0;b<4;b++) begin : gen_profile_byte
            always_ff @(posedge clk) begin
                if(reset) profile_byte_equal[4*w+b] <= PROFILE[32*w+8*b+:8]==8'd0;
                else if(execute && aw==8'(32+4*w) && ws[b])
                    profile_byte_equal[4*w+b] <= wd[8*b+:8]==PROFILE[32*w+8*b+:8];
            end
        end
    end
    for(genvar g=0;g<4;g++) begin : gen_profile_group
        assign profile_group_equal[g]=&profile_byte_equal[8*g+:8];
    end
    wire request_contract_matches=&profile_group_equal;
'''+anchor)
    anchor='.request_contract({bank[13],bank[12],bank[11],bank[10],bank[9],bank[8],bank[7],bank[6]}),'
    assert s.count(anchor)==1
    s=s.replace(anchor,anchor+'\n        .request_contract_matches(request_contract_matches),');p.write_text(s)
    (OUT/'README.md').write_text('''# Separate typed200_profile_cache candidate

Only AXIL endpoint and guard change from frozen typed200_flush. Thirty-two
registered byte equalities replace the wide request-profile compare at admission.
Each flag is exactly equivalent to its stored byte, updated on the same write
edge/byte strobe; reset flags reflect equality to the zeroed bank. Commands do
not clear flags because they do not clear bank values. All256 digest bits remain
checked. No request/admission cycle, validation/deadline pause or numerical change.
Current quiet/error/epoch/shape/request and full fresh-frame checks remain intact.
Raw request banks may be pruned by synthesis if now unobservable; no ABI CSR reads
them. Only this endpoint may supply the new guard equality input; standalone guard
equivalence is insufficient. Full endpoint sequential equivalence is required.
Functional/physical benefit and hardware qualification are pending. Qualified
sources/package/recovery, numerical baselines and all prior candidates stay frozen.
''')
    (OUT/'candidate.json').write_text(json.dumps({'candidate':'typed200_profile_cache','sealed':False,
        'parent_manifest_sha256':sha(PARENT/'candidate.json'),
        'candidate_sha256':{p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.suffix in ('.sv','.v')},
        'digest_bits_checked':256,'new_equality_state_bits':32,'intended_external_cycle_delta':0,
        'numerical_contract_changed':False,'deadline_epoch_logic_changed':False,'hardware_qualified':False},indent=2)+'\n')
    verify()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true');a=p.parse_args()
    verify() if a.verify else create();print('PASS separate profile-cache inventory; full endpoint proof required')
