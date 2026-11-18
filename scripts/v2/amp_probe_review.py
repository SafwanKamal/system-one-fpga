"""Independent physical review for diagnostic probe only; no bitstream/load."""
from pathlib import Path
import hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/v2/typed200-amp-deployment-v1'

def main():
 b=BASE/'probe-physical-v2';s='S:/'+b.relative_to(ROOT).as_posix()
 out=b/'review-v2';out.mkdir(exist_ok=False)
 assert json.loads((b/'implementation-completion.json').read_text())['exit_code']==0
 state=json.loads((b/'route-status.json').read_text());assert state['routed'] and state['setup_ns']>0 and state['hold_ns']>0
 assert json.loads((b/'placement-gate.json').read_text())['setup_ns']>=0.500
 sim=BASE/'probe-sim-v4/receipt.json';r=json.loads(sim.read_text())
 assert r['passed'] and hashlib.sha256((b/'axi_origin_probe.v').read_bytes()).hexdigest()==r['rtl_sha256']
 checks=(b/'route-check-timing.rpt').read_text()
 summary=re.findall(r'^\d+\. checking (\S+) \((\d+)\)',checks,re.M)
 assert len(summary)==24 and len(dict(summary))==12 and all(int(n)==0 for name,n in summary),summary
 assert 'Checks found: 0' in (b/'route-drc.rpt').read_text()
 assert 'All paths are Safely Timed.' in (b/'route-cdc.rpt').read_text()
 assert 'All user specified timing constraints are met.' in (b/'route-timing.rpt').read_text()
 t=f'''open_checkpoint {{{s}/routed.dcp}}
write_xdc -force {{{s}/review-v2/effective.xdc}}
set c [get_clocks clk_pl_0]
if {{[llength $c]!=1}} {{error "missing sole PL clock"}}
set f [open {{{s}/review-v2/clock.json}} w]
puts $f [format {{{{"period_ns":%s,"clocks":%s,"top_ports":%s}}}} [get_property PERIOD $c] [llength [get_clocks]] [llength [get_ports]]]
close $f
report_route_status -file {{{s}/review-v2/route-status.rpt}}
close_design
exit
'''
 (out/'inspect.tcl').write_text(t)
 cmd=['C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat','-mode','batch','-notrace','-source',s+'/review-v2/inspect.tcl',
      '-log',s+'/review-v2/vivado.log','-journal',s+'/review-v2/vivado.jou']
 with (out/'console.log').open('wb') as f:ret=subprocess.run(cmd,cwd=out,stdout=f,stderr=subprocess.STDOUT,timeout=180)
 assert ret.returncode==0
 clock=json.loads((out/'clock.json').read_text());assert clock['clocks']==1 and clock['top_ports']==0
 assert clock['period_ns']==10.0,clock
 xdc=(out/'effective.xdc').read_text();exceptions=[l for l in xdc.splitlines() if l.startswith('set_false_path')]
 # Explicit exact-target review is required before admitting a bitstream.
 (out/'pre-review.json').write_text(json.dumps(dict(setup_ns=state['setup_ns'],hold_ns=state['hold_ns'],
  clock=clock,false_paths=exceptions,passed_nonexception_checks=True,bitstream_admitted=False),indent=2)+'\n')
 print(json.dumps(dict(clock=clock,false_paths=exceptions),indent=2),flush=True)
if __name__=='__main__':main()
