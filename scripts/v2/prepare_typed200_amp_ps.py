"""Generate isolated K26 SOM+KR260 carrier PS IP; no synthesis or board access.

Do not invoke the frozen standalone design's PS initialization. Both presets
are explicitly composed so GEM0 SGMII and GEM1 MDIO are retained.
"""
from pathlib import Path
import argparse, hashlib, json, re, subprocess, xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-ownership-v1'

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);a=ap.parse_args()
 assert re.fullmatch(r'ps-profile-v[0-9]+',a.attempt)
 out=BASE/a.attempt;out.mkdir(exist_ok=False)
 store=ROOT/'build/v2/board-store'
 rev=subprocess.check_output(['git','-C',str(store),'rev-parse','HEAD'],text=True).strip()
 dirty=subprocess.check_output(['git','-C',str(store),'status','--porcelain'],text=True)
 assert not dirty,'do not consume locally modified board store'
 presets=[store/'boards/Xilinx/kr260_som/1.1/preset.xml',
          store/'boards/Xilinx/kr260_carrier/1.0/preset.xml']
 config={};origins={};receipts=[]
 for path in presets:
  preset='mpsoc_preset_vsom' if 'kr260_som' in path.parts else 'mpsoc_preset_som240_1'
  nodes=ET.parse(path).getroot().findall(".//ip_preset[@preset_proc_name='"+preset+"']")
  assert len(nodes)==1,path
  for v in nodes[0].findall('.//user_parameter'):
   config[v.attrib['name']]=v.attrib['value'];origins[v.attrib['name']]=str(path.relative_to(store))
  receipts.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
 overrides={'CONFIG.PSU__USE__M_AXI_GP0':'1','CONFIG.PSU__USE__M_AXI_GP1':'0',
  'CONFIG.PSU__USE__M_AXI_GP2':'0','CONFIG.PSU__USE__S_AXI_GP2':'1',
  'CONFIG.PSU__SAXIGP2__DATA_WIDTH':'128','CONFIG.PSU__FPGA_PL0_ENABLE':'1',
  'CONFIG.PSU__FPGA_PL1_ENABLE':'1','CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ':'200',
  'CONFIG.PSU__CRL_APB__PL1_REF_CTRL__FREQMHZ':'100','CONFIG.PSU__USE__IRQ0':'1'}
 config.update(overrides)
 for k in overrides:origins[k]='isolated AMP integration requirement'
 assert config['CONFIG.PSU__ENET0__PERIPHERAL__ENABLE']=='1'
 assert config['CONFIG.PSU__ENET1__PERIPHERAL__ENABLE']=='1'
 assert config['CONFIG.PSU__ENET0__PERIPHERAL__IO']=='GT Lane0'
 assert config['CONFIG.PSU__ENET1__GRP_MDIO__ENABLE']=='1'
 (out/'source-receipt.json').write_text(json.dumps(dict(commit=rev,files=receipts,
  reference='https://github.com/Xilinx/XilinxBoardStore/tree/'+rev,config=config,origins=origins,
  target_executed=False,deployable=False),indent=2)+'\n')
 # All Tcl interpolation is constrained property/value data from parsed XML.
 for k,v in config.items():assert not any(x in k+v for x in '{}$[];\n\r')
 rel='S:/'+out.relative_to(ROOT).as_posix()
 lines=['set_param general.maxThreads 4',
  f'create_project amp_ps {{{rel}/project}} -part xck26-sfvc784-2LV-c',
  'create_ip -name zynq_ultra_ps_e -vendor xilinx.com -library ip -module_name amp_ps',
  'set ps [get_ips amp_ps]', 'set props [list_property $ps]']
 for k,v in config.items():
  lines += ['if {[lsearch -exact $props {'+k+'}] < 0} {error {unknown requested property '+k+'}}']
 # Atomic property application avoids invalid intermediate MIO/PMU defaults.
 lines += ['set_property -dict [list '+ ' '.join('{'+k+'} {'+v+'}' for k,v in config.items())+'] $ps']
 lines += [f'set f [open {{{rel}/actual-properties.tsv}} w]',
           'foreach k [lsort [list_property $ps]] {if {[string match CONFIG.* $k]} {puts $f "$k\t[get_property $k $ps]"}}',
           'close $f','generate_target all $ps','close_project','exit']
 (out/'generate.tcl').write_text('\n'.join(lines)+'\n')
 cmd=['C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat','-mode','batch','-notrace',
      '-source',rel+'/generate.tcl','-log',rel+'/vivado.log','-journal',rel+'/vivado.jou']
 with (out/'console.log').open('wb') as f:
  r=subprocess.run(cmd,cwd=out,stdout=f,stderr=subprocess.STDOUT,timeout=900)
 assert r.returncode==0,'retain Vivado failure in '+str(out)
 generated={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (out/'project').rglob('psu_init*') if p.is_file()}
 assert generated,'no PS initialization artifact generated'
 (out/'receipt.json').write_text(json.dumps(dict(passed=True,command=cmd,generated=generated,
  target_executed=False,physical_integration_verified=False,deployable=False),indent=2)+'\n')
 print('PASS carrier+SOM PS IP generation; network/startup/clock compatibility still needs composition',flush=True)
if __name__=='__main__':main()
