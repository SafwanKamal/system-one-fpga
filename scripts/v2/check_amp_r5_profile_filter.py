"""Exhaust profile admission and exercise the preserved AXI transport engine."""
from pathlib import Path
import hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-r5-profile-filter-v1'
RTL=ROOT/'rtl/v2/candidates/typed200_amp_r5_profile/typed200_r5_profile_filter.sv'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def run(out,name,tb):
    (out/(name+'.sv')).write_text(tb)
    commands=[['C:/iverilog/bin/iverilog.exe','-g2012','-s','tb','-o',str(out/(name+'.vvp')),str(RTL),str(out/(name+'.sv'))],
              ['C:/iverilog/bin/vvp.exe',str(out/(name+'.vvp'))]]
    for i,cmd in enumerate(commands):
        p=subprocess.run(cmd,capture_output=True,cwd=ROOT,timeout=180)
        (out/(name+('-compile.log' if i==0 else '-run.log'))).write_bytes(p.stdout+p.stderr)
        assert p.returncode==0,(name,i,p.stdout[-2000:],p.stderr[-2000:])
    assert b'PASS' in p.stdout
    print(p.stdout.decode(),flush=True)

def main():
    out=BASE/'filter-check-v1';out.mkdir(exist_ok=False)
    (out/'runner.py').write_bytes(Path(__file__).read_bytes())
    origin=json.loads((BASE/'candidate-origin.json').read_text());assert sha(RTL)==origin['candidate_sha256']
    tb='''module tb;
typed200_r5_profile_filter d0();
typed200_r5_profile_filter #(.ENABLE_R5(1)) d1();
typed200_r5_profile_filter #(.SOURCE_PATH_QUALIFIED(1)) d2();
typed200_r5_profile_filter #(.ENABLE_R5(1),.SOURCE_PATH_QUALIFIED(1)) d3();
integer expected,accepted=0,checks=0;
initial begin
 for(integer userv=0;userv<65536;userv++) for(integer protv=0;protv<8;protv++)begin
  expected=((userv==8192 || userv==10240) && protv==1);
  if(d0.allowed(40'ha0000010,userv,protv,0,2,1,0)!==1'b0 ||
     d1.allowed(40'ha0000010,userv,protv,0,2,1,0)!==1'b0 ||
     d2.allowed(40'ha0000010,userv,protv,0,2,1,0)!==1'b0)
    $fatal(1,"unqualified/default path admitted user=%h prot=%h",userv,protv);
  if(d3.allowed(40'ha0000010,userv,protv,0,2,1,0)!==1'(expected))
    $fatal(1,"qualified profile mismatch user=%h prot=%h",userv,protv);
  checks++;accepted+=expected;
 end
 if(accepted!=2 || checks!=524288)$fatal(1,"enumeration count");
 $display("PASS exhaustive: %0d USER/PROT combinations x4 gate configurations, exactly two enabled combinations",checks);
 $finish;
end
endmodule
'''
    run(out,'admission',tb)
    old=ROOT/'build/v2/typed200-amp-candidate-v1/filter-sim-v1'
    source=(old/'tb.sv').read_text()
    assert hashlib.sha256((ROOT/'rtl/v2/candidates/typed200_amp/control/typed200_requester_filter.sv').read_bytes()).hexdigest()==origin['original_sha256']
    tb=source.replace('typed200_requester_filter #(.ENABLE_R5(1))','typed200_r5_profile_filter #(.ENABLE_R5(1),.SOURCE_PATH_QUALIFIED(1))')
    tb=tb.replace('cycle>300000','cycle>1000000')
    tb=tb.replace('m_awuser[9:4]||m_awuser[15:10]||m_awprot[1]',"(m_awuser!=16'h2000 && m_awuser!=16'h2800)||m_awprot!=1")
    tb=tb.replace('m_aruser[9:4]||m_aruser[15:10]||m_arprot[1]',"(m_aruser!=16'h2000 && m_aruser!=16'h2800)||m_arprot!=1")
    prefix,seq=tb.split('initial begin',1)
    # Adapt only valid-policy stimuli; leave all protocol/error mechanics intact.
    def adapt(match):
        name,args=match.group(1),match.group(2).split(',')
        if args[0]=='0':args[0]='8192'
        if args[0]=='mid':args[0]='8192|mid'
        if args[6]=='0':args[6]='1'
        args=[x.replace('mid<16','mid==0') for x in args]
        return name+'('+','.join(args)+');'
    seq=re.sub(r'\b(wr|rd)\(([^;]+)\);',adapt,seq)
    old_loop=seq[seq.index(' for(integer bitn=10;'):seq.index(' for(integer lane=0;')]
    new_loop=''' for(integer upper=0;upper<64;upper++)begin
  wr(upper<<10,40'ha0001000,0,2,1,0,1,16'hf,upper==8||upper==10,0);
  rd(upper<<10,40'ha0001000,0,2,1,0,1,upper==8||upper==10);
 end
 for(integer protv=0;protv<8;protv++)begin
  wr(8192,40'ha0001000,0,2,1,0,protv,16'hf,protv==1,0);
  rd(10240,40'ha0001000,0,2,1,0,protv,protv==1);
 end
'''
    seq=seq.replace(old_loop,new_loop)
    # Both observed upper profiles across every MID, including all RPU1/APU/PL sources.
    seq=seq.replace('for(integer mid=0;mid<1024;mid++)begin','for(integer profile=0;profile<2;profile++)for(integer mid=0;mid<1024;mid++)begin')
    seq=seq.replace('8192|mid','(profile==0?8192:10240)|mid')
    tb=prefix+'initial begin'+seq
    # Exact recorded IDs and markers through the candidate, with backpressure.
    wr=tb[tb.index('task automatic wr('):tb.index('task automatic rd(')]
    wr=wr.replace('task automatic wr(','task automatic measured_wr(input integer observed_id,')
    wr=wr.replace("id=cases+16'h100","id=observed_id")
    rd=tb[tb.index('task automatic rd('):tb.index('initial begin')]
    rd=rd.replace('task automatic rd(','task automatic measured_rd(input integer observed_id,')
    rd=rd.replace("id=cases+16'h200","id=observed_id")
    tb=tb.replace('initial begin',wr+rd+'initial begin',1)
    review=ROOT/'build/v2/typed200-amp-linux-tag-probe-v1/observation-review-v1/receipt.json'
    evidence=json.loads(review.read_text());assert evidence['passed'] and not evidence['original_trial_passed']
    cases=[]
    for w in evidence['r5_writes']:
        cases.append(f"reset_all();measured_wr({w['axi_id']},{w['user']},40'h{w['address']:x},0,2,1,0,{w['prot']},16'h{15 << (w['address']%16):x},1,0);")
    ar=evidence['trace'];cases.append(f"reset_all();measured_rd({ar['ar_id']},{ar['ar_tag']&65535},40'ha0000018,0,2,1,0,{ar['ar_tag']>>16},1);")
    # APU tag mutations: PROT1 and both accepted upper profiles must not hide APU MID.
    for tag in evidence['apu_sources']['ar_tags']+evidence['apu_sources']['aw_tags']:
        for upper in [8192,10240]:
            user=upper|(tag&1023)
            cases.append(f"reset_all();wr({user},40'ha0000010,0,2,1,0,1,16'hf,0,0);rd({user},40'ha0000010,0,2,1,0,1,0);")
    # Same measured metadata attributed to a different upstream source is
    # indistinguishable. This witness prevents a false authentication claim.
    cases.append("reset_all();measured_wr(73,8192,40'ha0000010,0,2,1,0,1,16'hf,1,0);")
    marker=' $display("PASS filter:';assert tb.count(marker)==1
    tb=tb.replace(marker,'\n'.join(cases)+'\n'+marker)
    run(out,'transport',tb)
    result=dict(passed=True,rtl_sha256=sha(RTL),preserved_transport_engine=True,
        user_prot_combinations=524288,gate_configurations=4,
        accepted_complete_user_prot_pairs=[[8192,1],[10240,1]],
        measured_metadata_accepted=5,apu_secure_upper_mutations_rejected=32,
        shared_metadata_indistinguishability_witness=True,
        observation_sha256=sha(review),default_denies_all=True,
        enable_alone_denies_all=True,source_path_qualified=False,
        upper_bit_semantics_qualified=False,target_deployment_admitted=False,
        limits=['Synthetic payload/cache/QoS; no integrated hardware deployment',
                'Equal interface signals from different source devices are indistinguishable'])
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
