"""Exercise the separate requester filter; preserve every attempt and receipt."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[2]
RTL=ROOT/'rtl/v2/candidates/typed200_amp/control/typed200_requester_filter.sv'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',default='filter-sim-v1');a=ap.parse_args()
    assert re.fullmatch(r'filter-sim-v[0-9]+',a.attempt)
    out=ROOT/'build/v2/typed200-amp-candidate-v1'/a.attempt;out.mkdir(exist_ok=False)
    text=RTL.read_text();header=text.split(') (',1)[1].split(');',1)[0]
    ports=[]
    for match in re.finditer(r'\b(input|output)\s+(?:wire|logic)\s*(\[[^\]]+\])?\s*(.*?)(?=,\s*(?:input|output)\b|$)',header,re.S):
        direction,width,names=match.groups()
        for name in names.split(','):
            name=name.strip();assert re.fullmatch(r'[A-Za-z_]\w*',name),name
            ports.append((direction,width or '',name))
    decl='\n'.join(f'logic {w} {n};' for d,w,n in ports)
    init='\n'.join(n+"='0;" for d,w,n in ports if d=='input' and n not in ['clk','reset_n'])
    connect=','.join('.'+n+'('+n+')' for d,w,n in ports)
    tb='module tb;\n'+decl+'\nlogic [1:0] native_bresp,native_rresp;logic wrong_bid,wrong_rid,bad_rlast;\n'
    tb+='typed200_requester_filter #(.ENABLE_R5(1)) dut('+connect+');\n'
    tb+=r'''
integer cycle=0,aw_count=0,w_count=0,ar_count=0,cases=0;
integer stall_mode=0;logic got_aw,got_w;
logic [15:0] saved_awid;
logic [39:0] saved_awaddr;
logic [127:0] saved_wdata;
logic [15:0] saved_wstrb;
always #5 clk=~clk;
always @(negedge clk) begin
 if(reset_n) begin
  m_awready=stall_mode!=1 && (($urandom%4)!=0);
  m_wready=stall_mode!=2 && (($urandom%4)!=0);
  m_arready=stall_mode!=3 && (($urandom%4)!=0);
 end else begin m_awready=0;m_wready=0;m_arready=0;end
end
always @(posedge clk) begin
 cycle<=cycle+1;
 if(cycle>300000)$fatal(1,"global timeout");
 if(!reset_n)begin
  got_aw<=0;got_w<=0;m_bvalid<=0;m_rvalid<=0;m_bid<=0;m_bresp<=0;
  m_rid<=0;m_rdata<=0;m_rresp<=0;m_rlast<=0;
 end else begin
  if(m_awvalid&&m_awready)begin
   if(got_aw)$fatal(1,"duplicate downstream AW");
   got_aw<=1;saved_awid<=m_awid;saved_awaddr<=m_awaddr;aw_count<=aw_count+1;
   if(m_awlen||m_awsize!=2||m_awlock||m_awburst>1||m_awuser[9:4]||m_awuser[15:10]||m_awprot[1])
     $fatal(1,"unauthorized/malformed AW reached downstream");
  end
  if(m_wvalid&&m_wready)begin
   if(got_w||!m_wlast)$fatal(1,"duplicate/malformed downstream W");
   got_w<=1;saved_wdata<=m_wdata;saved_wstrb<=m_wstrb;w_count<=w_count+1;
  end
  if(got_aw&&got_w&&!m_bvalid)begin
   m_bid<=saved_awid ^ wrong_bid;m_bresp<=native_bresp;m_bvalid<=1;
  end
  if(m_bvalid&&m_bready)begin m_bvalid<=0;got_aw<=0;got_w<=0;end
  if(m_arvalid&&m_arready)begin
   if(m_rvalid)$fatal(1,"duplicate downstream AR");
   ar_count<=ar_count+1;m_rvalid<=1;m_rid<=m_arid ^ wrong_rid;
   m_rdata<={4{32'h89abcdef}} ^ m_araddr;m_rresp<=native_rresp;m_rlast<=!bad_rlast;
   if(m_arlen||m_arsize!=2||m_arlock||m_arburst>1||m_aruser[9:4]||m_aruser[15:10]||m_arprot[1])
     $fatal(1,"unauthorized/malformed AR reached downstream");
  end
  if(m_rvalid&&m_rready)m_rvalid<=0;
 end
end
task automatic reset_all;
 @(negedge clk);reset_n=0;s_awvalid=0;s_wvalid=0;s_arvalid=0;s_bready=0;s_rready=0;
 native_bresp=0;native_rresp=0;wrong_bid=0;wrong_rid=0;bad_rlast=0;stall_mode=0;
 repeat(3)@(negedge clk);reset_n=1;@(negedge clk);
endtask
task automatic aw(input integer id,input logic[39:0] addr,input integer user,
 input integer len,input integer size,input integer burst,input integer lockv,
 input integer prot,input integer delayv);
 repeat(delayv)@(negedge clk);
 s_awid=id;s_awaddr=addr;s_awuser=user;s_awlen=len;s_awsize=size;
 s_awburst=burst;s_awlock=lockv;s_awprot=prot;s_awcache=4'ha;s_awqos=4'h5;s_awvalid=1;
 do @(posedge clk);while(!s_awready);
 @(negedge clk);s_awvalid=0;s_awuser=16'hffff;s_awaddr='1;
endtask
task automatic wd(input integer len,input logic[15:0] strb,input integer delayv,
 input integer badfirst);
 repeat(delayv)@(negedge clk);
 for(integer j=0;j<=len;j++)begin
  s_wvalid=1;s_wdata={4{32'h12345678}} ^ j;s_wstrb=strb;
  s_wlast=(j==len) ^ (badfirst&&j==0);
  do @(posedge clk);while(!s_wready);
  @(negedge clk);
 end
 s_wvalid=0;s_wdata='1;s_wstrb='1;
endtask
task automatic wr(input integer user,input logic[39:0] addr,input integer len,
 input integer size,input integer burst,input integer lockv,input integer prot,
 input logic[15:0] strb,input integer expect_forward,input integer badfirst);
 integer a0,w0,id,holdv;logic[1:0] expected;
 a0=aw_count;w0=w_count;id=cases+16'h100;cases++;
 fork
  aw(id,addr,user,len,size,burst,lockv,prot,cases%4);
  wd(len,strb,(cases/4)%4,badfirst);
 join
 while(!s_bvalid)@(negedge clk);
 expected=expect_forward ? (wrong_bid?2'b10:native_bresp):2'b11;
 if(s_bid!=16'(id)||s_bresp!=expected)$fatal(1,"bad B response case%0d",cases);
 holdv=$urandom%5;
 repeat(holdv)begin @(negedge clk);if(!s_bvalid||s_bid!=16'(id)||s_bresp!=expected)$fatal(1,"B changed under backpressure");end
 if(aw_count-a0!=expect_forward||w_count-w0!=expect_forward)$fatal(1,"write leak/missing case%0d",cases);
 if(expect_forward && (saved_awaddr!=addr || saved_wstrb!=strb || saved_wdata!={4{32'h12345678}}))
  $fatal(1,"allowed write changed");
 s_bready=1;@(posedge clk);@(negedge clk);s_bready=0;@(negedge clk);
endtask
task automatic rd(input integer user,input logic[39:0] addr,input integer len,
 input integer size,input integer burst,input integer lockv,input integer prot,input integer expect_forward);
 integer a0,id;logic[1:0] expected;logic[127:0] data_expected;
 a0=ar_count;id=cases+16'h200;cases++;
 @(negedge clk);s_arid=id;s_araddr=addr;s_aruser=user;s_arlen=len;s_arsize=size;
 s_arburst=burst;s_arlock=lockv;s_arprot=prot;s_arcache=4'h9;s_arqos=4'h6;s_arvalid=1;
 do @(posedge clk);while(!s_arready);
 @(negedge clk);s_arvalid=0;s_aruser=16'hffff;s_araddr='1;
 for(integer j=0;j<=len;j++)begin
  while(!s_rvalid)@(negedge clk);
  expected=expect_forward ? ((wrong_rid||bad_rlast)?2'b10:native_rresp):2'b11;
  data_expected=expect_forward ? ({4{32'h89abcdef}} ^ addr):128'd0;
  if(s_rid!=16'(id)||s_rresp!=expected||s_rdata!=data_expected||s_rlast!=(j==len))
    $fatal(1,"bad R response case%0d beat%0d",cases,j);
  repeat($urandom%4)begin
   @(negedge clk);
   if(!s_rvalid||s_rid!=16'(id)||s_rresp!=expected||s_rdata!=data_expected||s_rlast!=(j==len))
     $fatal(1,"R changed under backpressure");
  end
  s_rready=1;@(posedge clk);@(negedge clk);s_rready=0;
 end
 if(ar_count-a0!=expect_forward)$fatal(1,"read leak/missing case%0d",cases);
 @(negedge clk);
endtask
initial begin
 clk=0;reset_n=0;
'''+init+r'''
 native_bresp=0;native_rresp=0;wrong_bid=0;wrong_rid=0;bad_rlast=0;
 reset_all();
 // Exhaust every low-10-bit PS master identity, with changing AW/W order.
 for(integer mid=0;mid<1024;mid++)begin
  wr(mid,40'ha0000010,0,2,1,0,0,16'hf,mid<16,0);
  rd(mid,40'ha0000010,0,2,1,0,0,mid<16);
 end
 // Secure R5 only; unknown upper USER attributes fail closed.
 wr(0,40'ha0001000,0,2,1,0,2,16'hf,0,0);rd(0,40'ha0001000,0,2,1,0,2,0);
 for(integer bitn=10;bitn<16;bitn++)begin
  wr(1<<bitn,40'ha0001000,0,2,1,0,0,16'hf,0,0);
  rd(1<<bitn,40'ha0001000,0,2,1,0,0,0);
 end
 for(integer lane=0;lane<4;lane++)for(integer maskv=0;maskv<16;maskv++)
  wr(0,40'ha0000000+4*lane,0,2,1,0,0,16'(maskv<<(4*lane)),1,0);
 wr(0,40'ha0000004,0,2,1,0,0,16'hf,0,0);
 wr(0,40'h9ffffffc,0,2,1,0,0,16'hf000,0,0);rd(0,40'h9ffffffc,0,2,1,0,0,0);
 wr(0,40'ha0002000,0,2,1,0,0,16'hf,0,0);rd(0,40'ha0002000,0,2,1,0,0,0);
 wr(0,40'ha0001ffc,0,2,1,0,0,16'hf000,1,0);rd(0,40'ha0001ffc,0,2,1,0,0,1);
 for(integer bitn=32;bitn<40;bitn++)begin
  wr(0,40'ha0000000|(40'd1<<bitn),0,2,1,0,0,16'hf,0,0);
  rd(0,40'ha0000000|(40'd1<<bitn),0,2,1,0,0,0);
 end
 for(integer off=1;off<4;off++)begin
  wr(0,40'ha0000000+off,0,2,1,0,0,16'hf,0,0);rd(0,40'ha0000000+off,0,2,1,0,0,0);
 end
 for(integer sizev=0;sizev<8;sizev++)if(sizev!=2)begin
  wr(0,40'ha0000000,0,sizev,1,0,0,16'hf,0,0);rd(0,40'ha0000000,0,sizev,1,0,0,0);
 end
 for(integer burstv=2;burstv<4;burstv++)begin
  wr(0,40'ha0000000,0,2,burstv,0,0,16'hf,0,0);rd(0,40'ha0000000,0,2,burstv,0,0,0);
 end
 wr(0,40'ha0000000,0,2,1,1,0,16'hf,0,0);rd(0,40'ha0000000,0,2,1,1,0,0);
 for(integer lenv=1;lenv<=255;lenv=(lenv==1?15:255))begin
  wr(0,40'ha0000000,lenv,2,1,0,0,16'hf,0,0);rd(0,40'ha0000000,lenv,2,1,0,0,0);
  if(lenv==255)break;
 end
 // Downstream error transparency and independent read/write channels.
 native_bresp=2;native_rresp=2;
 fork
  wr(0,40'ha0000020,0,2,1,0,0,16'hf,1,0);
  rd(0,40'ha0000030,0,2,1,0,0,1);
 join
 native_bresp=0;native_rresp=0;
 // Reset discards an incomplete upstream frame before any downstream effect.
 aw(16'h55,40'ha0000010,0,0,2,1,0,0,0);reset_all();
 wd(0,16'hf,0,0);reset_all();
 wr(0,40'ha0000000,0,2,1,0,0,16'hf,1,0);
 // Invalid WLAST never forwards; declared rejected data still drains.
 wr(0,40'ha0000000,2,2,1,0,0,16'hf,0,1);
 if(!protocol_fault||s_awready||s_arready)$fatal(1,"protocol fault not sticky/fail closed");
 reset_all();wr(0,40'ha0000000,0,2,1,0,0,16'hf,0,1);
 if(!protocol_fault)$fatal(1,"missing bad single WLAST fault");
 reset_all();wrong_bid=1;wr(0,40'ha0000000,0,2,1,0,0,16'hf,1,0);
 if(!protocol_fault)$fatal(1,"missing BID fault");
 reset_all();wrong_rid=1;rd(0,40'ha0000000,0,2,1,0,0,1);
 if(!protocol_fault)$fatal(1,"missing RID fault");
 reset_all();bad_rlast=1;rd(0,40'ha0000000,0,2,1,0,0,1);
 if(!protocol_fault)$fatal(1,"missing RLAST fault");
 $display("PASS filter: %0d transactions; all1024 master IDs R/W; AW/W skew; stalls; full denied bursts; bounds/strobes/reset/faults",cases);
 $finish;
end
endmodule
'''
    # Icarus 12 does not implement break; the loop is finite without it.
    tb=tb.replace('lenv=(lenv==1?15:255)','lenv=(lenv==1?15:(lenv==15?255:256))').replace('  if(lenv==255)break;','')
    (out/'tb.sv').write_text(tb)
    commands=[['C:/iverilog/bin/iverilog.exe','-g2012','-s','tb','-o',str(out/'sim.vvp'),str(RTL),str(out/'tb.sv')],
              ['C:/iverilog/bin/vvp.exe',str(out/'sim.vvp')]]
    results=[]
    for i,cmd in enumerate(commands):
        r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=120)
        (out/('compile.log' if i==0 else 'run.log')).write_text(r.stdout+r.stderr)
        results.append(dict(command=cmd,exit=r.returncode))
        if r.returncode:break
    passed=len(results)==2 and all(r['exit']==0 for r in results) and 'PASS filter:' in (out/'run.log').read_text()
    (out/'receipt.json').write_text(json.dumps(dict(passed=passed,rtl_sha256=hashlib.sha256(RTL.read_bytes()).hexdigest(),
       commands=results,limits=['Behavioral AXI model; not proof of PS source provenance or physical timing',
        'Only aligned secure R5 32-bit single-beat accesses eligible; upper USER must zero',
        'Fault/reset isolation and system ownership still require composition/target qualification']),indent=2))
    print((out/'run.log').read_text() if (out/'run.log').exists() else (out/'compile.log').read_text())
    raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()
