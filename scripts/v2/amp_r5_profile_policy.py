"""Observed workload checks, deliberately separate from source authentication."""
from amp_linux_tag_policy import check_apu,parse_trace,require

def word(value,bits):
    return type(value) is int and 0<=value<1<<bits

def profile(tag):
    return word(tag,19) and tag in (0x12000,0x12800)

def review(snapshot,trace,apu):
    cpu=parse_trace(trace);sources=check_apu(apu)
    require(profile(cpu['ar_tag']),'Unobserved R5 read profile')
    require(snapshot.get('magic')==0x4f524731 and snapshot.get('version')==1,'PL identity mismatch')
    require(snapshot.get('writes')==68 and snapshot.get('errors')==0,'PL counters mismatch')
    slots=snapshot.get('slots',[]);require(len(slots)==16,'PL slots missing')
    observations=[]
    for j,slot in enumerate(slots):
        require(slot.get('address')==0xa0000000+4*j,'Slot address mismatch')
        if j not in range(4,8):
            require(slot==apu['cores'][3]['slots'][j],'Unexpected non-R5 slot mutation')
            continue
        tag=slot.get('tag');metadata=slot.get('metadata')
        require(profile(tag),'Unobserved R5 write profile')
        require(word(metadata,32) and metadata>>16==60+j,'R5 sequence mismatch')
        require(slot.get('value')==0x52350000+j,'R5 marker mismatch')
        # Transaction IDs identify responses; variation is not an origin change.
        observations.append(dict(user=tag&65535,prot=tag>>16,mid=tag&1023,
                                 axi_id=metadata&65535,address=slot['address'],value=slot['value']))
    return dict(passed=True,scope='Observed diagnostic workload only',cpu=cpu,
        apu_sources=sources,r5_writes=observations,source_authentication_qualified=False,
        shared_mid_sources=['RPU0','CCI-400','SMMU TCU'],
        upper_bit_semantics_qualified=False,target_filter_deployed=False)
