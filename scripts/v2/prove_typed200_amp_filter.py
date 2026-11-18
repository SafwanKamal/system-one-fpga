"""Candidate-only access safety/beat accounting proof, not platform isolation."""
from pathlib import Path
import argparse, hashlib, json, re, subprocess, time
ROOT=Path(__file__).resolve().parents[2]
RTL=ROOT/'rtl/v2/candidates/typed200_amp/control/typed200_requester_filter.sv'
PROPERTIES=r'''
    reg f_past=0;
    reg [8:0] f_wcount, f_rtotal, f_rcount;
    always @(posedge clk) begin
      f_past<=1;
      if(!f_past) assume(!reset_n);
      if(!reset_n) begin f_wcount<=0;f_rtotal<=0;f_rcount<=0;end
      else begin
        if(s_bvalid && s_bready) f_wcount<=0;
        else if(s_wvalid && s_wready) f_wcount<=f_wcount+1'b1;
        if(s_arvalid && s_arready) begin
          f_rtotal<={1'b0,s_arlen}+9'd1;f_rcount<=0;
        end else if(s_rvalid && s_rready) f_rcount<=f_rcount+1'b1;
      end
      if(f_past && reset_n) begin
        if(aw_full && aw_allowed) begin
          assert(ENABLE_R5 && (aw_user & 16'hfff0)==0 && !aw_prot[1]);
          assert(aw_addr>=BASE && aw_addr<END_EXCLUSIVE && aw_addr[1:0]==0);
          assert(aw_len==0 && aw_burst<=1);
        end
        if(wstate==W_SEND) begin
          assert(aw_full && w_full && aw_allowed && first_last && strobe_ok);
          assert(f_wcount==1);
        end
        if(wstate==W_WAIT) assert(f_wcount=={8'd0,w_full});
        if(wstate==W_DROP) begin
          assert(aw_full && w_left!=0);
          assert(f_wcount+{1'b0,w_left}=={1'b0,aw_len}+9'd1);
        end
        if(s_bvalid) begin
          assert(aw_full && f_wcount=={1'b0,aw_len}+9'd1);
        end
        if(m_awvalid || m_wvalid) assert(wstate==W_SEND);
        if(m_arvalid || rstate==R_PASS) begin
          assert(ENABLE_R5 && (ar_user & 16'hfff0)==0 && !ar_prot[1]);
          assert(ar_addr>=BASE && ar_addr<END_EXCLUSIVE && ar_addr[1:0]==0);
          assert(ar_burst<=1 && f_rtotal==1);
        end
        if(rstate==R_REJECT) begin
          assert(f_rtotal==f_rcount+{1'b0,r_left}+9'd1);
          assert(s_rvalid && s_rdata==0 && s_rresp==3);
          assert(s_rlast==(f_rcount+9'd1==f_rtotal));
        end
        if(protocol_fault) begin assert(!s_awready && !s_arready);end
        if(!ENABLE_R5) assert(!m_awvalid && !m_wvalid && !m_arvalid);
        if($past(reset_n)) begin
          if($past(protocol_fault)) assert(protocol_fault);
          if($past(m_awvalid && !m_awready)) begin
            assert(m_awvalid);
            assert($stable({m_awid,m_awaddr,m_awlen,m_awsize,m_awburst,m_awlock,
              m_awcache,m_awprot,m_awqos,m_awuser}));
          end
          if($past(m_wvalid && !m_wready)) begin
            assert(m_wvalid && $stable({m_wdata,m_wstrb,m_wlast}));
          end
          if($past(m_arvalid && !m_arready)) begin
            assert(m_arvalid && $stable({m_arid,m_araddr,m_arlen,m_arsize,
              m_arburst,m_arlock,m_arcache,m_arprot,m_arqos,m_aruser}));
          end
          if($past(s_bvalid && !s_bready))
            assert(s_bvalid && $stable({s_bid,s_bresp}));
          if($past(rstate==R_REJECT && !s_rready))
            assert(s_rvalid && $stable({s_rid,s_rdata,s_rresp,s_rlast}));
          if($past(wstate==W_DROP && s_wvalid && s_wready && w_left==1))
            assert(s_bvalid);
        end
      end
    end
'''

def main():
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);a=p.parse_args()
    assert re.fullmatch(r'filter-formal-v[0-9]+',a.attempt)
    out=ROOT/'build/v2/typed200-amp-candidate-v1'/a.attempt;out.mkdir(exist_ok=False)
    source=RTL.read_text();(out/'instrumented.sv').write_text(source.replace('endmodule',PROPERTIES+'\nendmodule'))
    receipt={'rtl_sha256':hashlib.sha256(RTL.read_bytes()).hexdigest(),
      'scope':'two-state synchronous access safety and complete declared beat accounting',
      'assumptions':['first sampled edge reset asserted'],
      'not_proved':['PS source identity provenance','downstream protocol correctness',
        'bounded service or liveness under arbitrary stalls','platform isolation',
        'read-pass payload stability without downstream AXI compliance',
        'safe independent reset with outstanding downstream transactions'], 'runs':[]}
    for enabled in (1,0):
        prefix=out/f'enable-{enabled}'
        rel=lambda x:x.relative_to(ROOT).as_posix()
        script=f'''read_verilog -formal -sv {rel(out/'instrumented.sv')}
chparam -set ENABLE_R5 {enabled} typed200_requester_filter
prep -top typed200_requester_filter -flatten
async2sync
chformal -lower
formalff -clk2ff
dffunmap
opt_clean
sat -verify -prove-asserts -tempinduct -seq 2 -maxsteps 12 -set-assumes -set clk 1 -timeout 120 -dump_vcd {rel(prefix.with_suffix('.vcd'))}
'''
        ys=prefix.with_suffix('.ys');ys.write_text(script)
        command=['uv','tool','run','--from','yowasp-yosys==0.70.0.0.post1259','yowasp-yosys','-Q','-T','-l',rel(prefix.with_suffix('.log')),'-s',rel(ys)]
        started=time.time()
        with prefix.with_suffix('.console.log').open('w') as log:
            run=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=600)
        text=prefix.with_suffix('.log').read_text()
        ok=run.returncode==0 and 'Induction step proven: SUCCESS!' in text
        receipt['runs'].append({'enable_r5':enabled,'returncode':run.returncode,'induction_proven':ok,'seconds':time.time()-started})
        (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(receipt['runs'][-1]),flush=True)
        if not ok:raise SystemExit(1)
    receipt['passed']=True;(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()
