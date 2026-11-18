"""Review saved hardware evidence without changing failed trial or admission policy."""
from pathlib import Path
import hashlib,json,subprocess
from amp_linux_tag_policy import check_apu,check_r5,parse_trace

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-linux-tag-probe-v1'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    out=BASE/'observation-review-v1';out.mkdir(exist_ok=False)
    source=BASE/'target-trial-v2/collection-v1/collect.stdout'
    collected=json.loads(source.read_text())
    for name,text in collected.items():
        assert Path(name).name==name
        (out/name).write_text(text)
    apu=json.loads(collected['apu-observations.json'])
    snap=json.loads(collected['pl-snapshot.json'])
    trace=parse_trace(collected['r5-trace.txt']);sources=check_apu(apu)
    assert snap['magic']==0x4f524731 and snap['version']==1
    assert snap['writes']==68 and snap['errors']==0 and len(snap['slots'])==16
    writes=[]
    for j,slot in enumerate(snap['slots']):
        assert slot['address']==0xa0000000+4*j
        if j not in range(4,8):
            assert slot==apu['cores'][3]['slots'][j]
            continue
        assert slot['value']==0x52350000+j and slot['metadata']>>16==60+j
        assert 0<=slot['tag']<=0x7ffff
        writes.append(dict(**slot,user=slot['tag']&65535,prot=slot['tag']>>16,
                           mid=slot['tag']&1023,axi_id=slot['metadata']&65535))
    try:check_r5(snap,collected['r5-trace.txt'],apu)
    except RuntimeError as e:assert str(e)=='R5 AW identity inconsistent'
    else:raise AssertionError('Original policy unexpectedly accepted')
    recovery=json.loads(collected['recovery.json'])
    assert recovery['passed'] and recovery['stock_restored'] and recovery['r5_released']
    assert recovery['baseline_hashes_unchanged'] and recovery['linux_clock_restored']
    old=ROOT/'build/v2/typed200-amp-candidate-v1/filter-sim-v1'
    rtl=ROOT/'rtl/v2/candidates/typed200_amp/control/typed200_requester_filter.sv'
    assert sha(rtl)==json.loads((old/'receipt.json').read_text())['rtl_sha256']
    tb=(old/'tb.sv').read_text();marker=' $display("PASS filter:'
    assert tb.count(marker)==1
    # Clone harness tasks to inject the measured transaction IDs, too. Data,
    # cache/QoS and strobes are synthetic; this is an admission-metadata replay.
    wr=tb[tb.index('task automatic wr('):tb.index('task automatic rd(')]
    wr=wr.replace('task automatic wr(','task automatic measured_wr(input integer observed_id,')
    wr=wr.replace("id=cases+16'h100","id=observed_id")
    rd=tb[tb.index('task automatic rd('):tb.index('initial begin')]
    rd=rd.replace('task automatic rd(','task automatic measured_rd(input integer observed_id,')
    rd=rd.replace("id=cases+16'h200","id=observed_id")
    tb=tb.replace('initial begin',wr+rd+'initial begin',1)
    cases=[]
    for w in writes:
        cases.append(f" reset_all();measured_wr({w['axi_id']},{w['user']},40'h{w['address']:x},0,2,1,0,{w['prot']},16'h{15 << (w['address']%16):x},0,0);")
    cases.append(f" reset_all();measured_rd({trace['ar_id']},{trace['ar_tag']&65535},40'ha0000018,0,2,1,0,{trace['ar_tag']>>16},0);")
    tb=tb.replace(marker,'\n'.join(cases)+'\n'+marker)
    (out/'tb.sv').write_text(tb);(out/rtl.name).write_bytes(rtl.read_bytes())
    cmds=[['C:/iverilog/bin/iverilog.exe','-g2012','-s','tb','-o',str(out/'sim.vvp'),str(out/rtl.name),str(out/'tb.sv')],['C:/iverilog/bin/vvp.exe',str(out/'sim.vvp')]]
    for i,cmd in enumerate(cmds):
        r=subprocess.run(cmd,capture_output=True,timeout=60,cwd=ROOT)
        (out/('compile.log' if i==0 else 'run.log')).write_bytes(r.stdout+r.stderr)
        assert r.returncode==0,r.stderr[-2000:]
    assert 'PASS filter:' in (out/'run.log').read_text()
    result=dict(passed=True,review_scope='Marker integrity, recorded recovery and negative filter replay only',
        original_trial_passed=False,original_failure='R5 AW identity inconsistent',
        filter_admission_qualified=False,full_inference_ready=False,
        source_sha256=sha(source),filter_sha256=sha(rtl),trace=trace,
        apu_sources=sources,r5_writes=writes,total_writes=68,errors=0,
        measured_metadata_rejections=5,recovery=recovery,
        upper_field_interpretation_qualified=False,
        limitations=['One hardware trace; no exhaustive source provenance or upper-bit semantics proof',
                    'Metadata simulation uses synthetic payload/cache/QoS; not a physical integrated firewall test'])
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS observation integrity + recovery; five measured R5 metadata cases rejected by unchanged filter')
    print((out/'run.log').read_text())

if __name__=='__main__':main()
