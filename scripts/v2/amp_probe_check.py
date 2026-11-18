"""Qualification-only AXI origin probe regression, with no target API."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-deployment-v1'
RTL=ROOT/'rtl/v2/candidates/typed200_amp_probe/axi_origin_probe.v'

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);a=ap.parse_args()
 assert re.fullmatch(r'probe-sim-v[0-9]+',a.attempt)
 out=BASE/a.attempt;out.mkdir(exist_ok=False)
 ports=[];header=RTL.read_text().split('module axi_origin_probe (',1)[1].split(');',1)[0]
 header=re.sub(r'\(\*.*?\*\)','',header,flags=re.S)
 for m in re.finditer(r'\b(input|output)\s+wire\s*(\[[^\]]+\])?\s*(.*?)(?=,\s*(?:input|output)\b|$)',header,re.S):
  direction,width,names=m.groups()
  for name in names.split(','):
   name=name.strip();assert re.fullmatch(r'\w+',name),name
   ports.append((direction,width or '',name))
 assert len(ports)==41,len(ports)
 decl='\n'.join(f'logic {w} {n};' for d,w,n in ports)
 init='\n'.join(n+"='0;" for d,w,n in ports if d=='input')
 tb='module tb;\n'+decl+'\naxi_origin_probe dut('+','.join('.'+n+'('+n+')' for d,w,n in ports)+');\n'
 tb+=r'''
always #5 clk=~clk;
integer cycles=0,cases=0;
always @(posedge clk)begin cycles<=cycles+1;if(cycles>2000000)$fatal(1,"timeout");end
task automatic aw(input int user,input int prot,input int id,input int slot,input int len,input int delayv);
 repeat(delayv)@(negedge clk);
 s_axi_awid=16'(id);s_axi_awaddr=40'ha0000000+40'(slot*4);s_axi_awlen=8'(len);
 s_axi_awuser=16'(user);s_axi_awprot=3'(prot);s_axi_awsize=2;s_axi_awburst=1;
 s_axi_awvalid=1;do @(posedge clk);while(!s_axi_awready);
 @(negedge clk);s_axi_awvalid=0;s_axi_awuser='1;
endtask
task automatic wd(input int slot,input int value,input int len,input int delayv,input bit badlast);
 repeat(delayv)@(negedge clk);
 for(int j=0;j<=len;j++)begin
  s_axi_wvalid=1;s_axi_wdata=128'(32'(value))<<(8*((slot*4)%16));
  s_axi_wstrb=16'hf<<((slot*4)%16);s_axi_wlast=(j==len)^badlast;
  do @(posedge clk);while(!s_axi_wready);
  @(negedge clk);s_axi_wvalid=0;
 end
endtask
task automatic response(input int id,input int resp);
 logic[15:0] oldid;logic[1:0] oldresp;
 s_axi_bready=0;do @(negedge clk);while(!s_axi_bvalid);
 oldid=s_axi_bid;oldresp=s_axi_bresp;
 repeat(4)begin @(negedge clk);assert(s_axi_bvalid && oldid==s_axi_bid && oldresp==s_axi_bresp)else $fatal(1,"B stalled stability");end
 assert(s_axi_bid==16'(id) && s_axi_bresp==2'(resp))else $fatal(1,"B mismatch %h %h",s_axi_bid,s_axi_bresp);
 s_axi_bready=1;@(posedge clk);@(negedge clk);s_axi_bready=0;
endtask
task automatic read(input int addr,input int expected,input int len,input int resp);
 logic[127:0] saved;
 s_axi_araddr=40'ha0000000+40'(addr);s_axi_arid=16'h8732;s_axi_arlen=8'(len);
 s_axi_arsize=2;s_axi_arburst=1;s_axi_arvalid=1;s_axi_rready=0;
 do @(posedge clk);while(!s_axi_arready);
 @(negedge clk);s_axi_arvalid=0;
 for(int j=0;j<=len;j++)begin
  do @(negedge clk);while(!s_axi_rvalid);
  saved=s_axi_rdata;
  repeat(3)begin @(negedge clk);assert(s_axi_rvalid && s_axi_rdata===saved && s_axi_rid==16'h8732)else $fatal(1,"R stability");end
  assert(s_axi_rresp==2'(resp) && s_axi_rlast==(j==len))else $fatal(1,"R control");
  assert((s_axi_rdata>>(8*(addr%16)))=={96'b0,32'(expected)})else $fatal(1,"R data %h wanted %h",s_axi_rdata,expected);
  s_axi_rready=1;@(posedge clk);@(negedge clk);s_axi_rready=0;
 end
endtask
initial begin
INIT
 repeat(4)@(negedge clk);reset_n=1;
 read(0,32'h4f524731,0,0);read(4,1,0,0);
 s_axi_aruser=16'hc180;s_axi_arprot=3'd3;
 read(24,32'h0003c180,0,0);read(28,32'h8732,0,0);
 for(int u=0;u<1024;u++)for(int sec=0;sec<2;sec++)begin
  int slot,prot,value,id;slot=(u+sec)%16;prot=sec*2+1;value=32'h12340000+u*2+sec;id=u^32'h7256;
  fork aw(u,prot,id,slot,0,u%3);wd(slot,value,0,(u+1)%3,0);join
  response(id,0);
  read(256+slot*16,u|(prot<<16),0,0);
  read(260+slot*16,32'ha0000000+slot*4,0,0);
  read(264+slot*16,value,0,0);
  read(268+slot*16,(cases<<16)|id,0,0);cases++;
 end
 read(8,cases,0,0);
 for(int n=1;n<=255;n+=127)begin
  fork aw(32'hfe80,2,91,3,n,0);wd(3,32'habc,n,2,1);join
  response(91,3);read(0,0,n,3);
 end
 read(8,cases,0,0);
 // Reset with an unmatched W; no transaction survives a sampled reset.
 wd(0,9,0,0,0);reset_n=0;repeat(3)@(negedge clk);reset_n=1;
 read(8,0,0,0);read(256,0,0,0);
 $display("PASS origin probe %0d exact source/prot/id/lane traces; burst drain, stalled responses, reset",cases);$finish;
end
endmodule
'''
 tb=tb.replace('INIT',init);(out/'tb.sv').write_text(tb)
 wsl='/mnt/'+ROOT.drive[0].lower()+ROOT.as_posix()[2:];rel=out.relative_to(ROOT).as_posix()
 stage='/tmp/sysone-'+a.attempt+'-amp-deployment';prefix=['wsl','-d','Ubuntu-24.04','--']
 def run(cmd,name):
  r=subprocess.run([str(x) for x in cmd],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
  (out/name).write_bytes(r.stdout);assert r.returncode==0,name
  return r.stdout.decode(errors='replace')
 run([*prefix,'test','!','-e',stage],'unused.log');run([*prefix,'mkdir',stage],'mkdir.log')
 run([*prefix,'cp',wsl+'/'+rel+'/tb.sv',wsl+'/'+RTL.relative_to(ROOT).as_posix(),stage+'/'],'stage.log')
 run([*prefix,'verilator','--assert','--binary','--timing','-j','2','-Wno-fatal',
  '--Mdir',stage+'/obj','--top-module','tb',stage+'/tb.sv',stage+'/axi_origin_probe.v',
  '-o','test-probe'],'compile.log')
 print(run([*prefix,stage+'/obj/test-probe'],'run.log'),flush=True)
 (out/'receipt.json').write_text(json.dumps(dict(passed=True,rtl_sha256=hashlib.sha256(RTL.read_bytes()).hexdigest(),
  source_tag_target_qualified=False,no_encoder=True,no_ddr_master=True,deployable=False),indent=2)+'\n')
if __name__=='__main__':main()
