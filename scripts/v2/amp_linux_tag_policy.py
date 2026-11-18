"""Pure checks for the fixed Linux/R5 tag diagnostic; no target I/O."""
import re


def require(condition,message):
    if not condition:raise RuntimeError(message)


def idle(status):
    return all(status.get(k)=='0' for k in ['pinned','reserved','lease_pending','mapped','may_run','loaded','quarantine'])


def restore_allowed(state,status):
    """Only a fully released R5 and positive post-start drain evidence suffice."""
    attempted=state.get('r5_start_attempted');quiet=state.get('r5_quiet_proved')
    apu_attempted=state.get('apu_access_attempted');apu_quiet=state.get('apu_quiet_proved')
    if any(type(x) is not bool for x in [attempted,quiet,apu_attempted,apu_quiet]):return False
    return idle(status) and (not attempted or quiet) and (not apu_attempted or apu_quiet)


def parse_trace(text):
    match=re.fullmatch(r'R5: PASS\nSCTLR=([0-9a-f]{8})\nCPSR=([0-9a-f]{8})\nMIDR=([0-9a-f]{8})\nAR=([0-9a-f]{8})\nARID=([0-9a-f]{8})\n',text)
    require(match is not None,'Fresh complete R5 tag-probe PASS required')
    ctl,cpsr,midr,ar,ident=(int(x,16) for x in match.groups())
    require(ctl & 0x1005==0 and cpsr & 255==0xd3 and midr & 0xfff0==0xc150,'CPU reset-state mismatch')
    require(ar<=0x7ffff and ident<=0xffff,'Metadata outside implemented width')
    return dict(sctlr=ctl,cpsr=cpsr,midr=midr,ar_tag=ar,ar_id=ident)


def check_apu(result):
    require(result.get('passed') is True and result.get('writes')==64 and result.get('errors')==0,'APU probe incomplete')
    cores=result.get('cores',[])
    require(len(cores)==4 and [c.get('cpu') for c in cores]==list(range(4)),'Four pinned A53 observations required')
    for cpu,c in enumerate(cores):
        slots=c.get('slots',[]);require(len(slots)==16,'Missing APU slots')
        require(0<=c['ar_tag']<=0x7ffff and 0<=c['ar_id']<=65535,'APU AR width')
        for j,slot in enumerate(slots):
            require(slot['address']==0xa0000000+4*j and slot['value']==0x41500000|(cpu<<8)|j,'APU exact address/value mismatch')
            require(slot['metadata']>>16==cpu*16+j,'APU write sequence mismatch')
            require(slot['tag']==slots[0]['tag'] and slot['metadata'] & 65535==slots[0]['metadata'] & 65535,'APU AW identity changed')
            require(0<=slot['tag']<=0x7ffff,'APU AW width')
    return dict(ar_tags=[c['ar_tag'] for c in cores],aw_tags=[c['slots'][0]['tag'] for c in cores])


def check_r5(snapshot,trace,apu):
    cpu=parse_trace(trace);sources=check_apu(apu)
    require(snapshot['magic']==0x4f524731 and snapshot['version']==1 and snapshot['writes']==68 and snapshot['errors']==0,'PL counters/identity mismatch')
    slots=snapshot['slots'];require(len(slots)==16,'Missing PL slots')
    tags=[];ids=[]
    for j in range(16):
        slot=slots[j]
        require(slot['address']==0xa0000000+4*j,'Slot address mismatch')
        if 4<=j<8:
            require(slot['value']==0x52350000+j and slot['metadata']>>16==60+j,'R5 marker/sequence mismatch')
            tags.append(slot['tag']);ids.append(slot['metadata'] & 65535)
        else:
            require(slot==apu['cores'][3]['slots'][j],'Unexpected modification of another APU slot')
    require(len(set(tags))==len(set(ids))==1,'R5 AW identity inconsistent')
    require(0<=tags[0]<=0x7ffff,'R5 AW width')
    require(tags[0] not in sources['aw_tags'] and cpu['ar_tag'] not in sources['ar_tags'],'R5/APU source collision')
    return dict(**cpu,aw_tag=tags[0],aw_id=ids[0],r5_writes=4,total_writes=68,errors=0,apu_sources=sources)
