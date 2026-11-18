"""Read-only architectural evidence collection for A53 Linux + R5 typed ownership.

No target access, SDK build, RTL change, register write or deployment command.
This is a structural/source audit, not an isolation or timing proof.
"""
from pathlib import Path
import csv,hashlib,json,re,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/v2/typed200-amp-feasibility-v1'
DOC=ROOT/'docs/research'
CAND=ROOT/'rtl/v2/candidates/typed200_row_range_csa'

def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(path):return path.read_text(encoding='utf-8')
def location(path,needle):
    lines=read(path).splitlines()
    n=next(i+1 for i,line in enumerate(lines) if needle in line)
    try:name=path.relative_to(ROOT).as_posix()
    except ValueError:name=str(path)
    return dict(path=name,line=n,sha256=sha(path),needle=needle)
def logic(text):return re.sub(r'\s+','',re.sub(r'//[^\n]*|/\*.*?\*/','',text,flags=re.S))

def main():
    hwh=ROOT/'build/v2/typed200-row-range-csa-physical-v1/sysone_v2_kr260.gen/sources_1/bd/system/hw_handoff/system.hwh'
    tree=ET.parse(hwh).getroot()
    ctl=next(x for x in tree.iter('MODULE') if x.get('INSTANCE')=='control_interconnect')
    buses={b.get('NAME'):{p.get('NAME'):p.get('VALUE') for p in b.findall('PARAMETER')}
           for b in ctl.findall('./BUSINTERFACES/BUSINTERFACE')}
    assert buses['S00_AXI']['AWUSER_WIDTH']==buses['S00_AXI']['ARUSER_WIDTH']=='16'
    assert all(buses[n]['AWUSER_WIDTH']==buses[n]['ARUSER_WIDTH']=='0' for n in ['M00_AXI','M01_AXI'])
    ps=next(x for x in tree.iter('MODULE') if x.get('INSTANCE')=='zynq_ultra_ps_e_0')
    params={p.get('NAME'):p.get('VALUE') for p in ps.findall('./PARAMETERS/PARAMETER')}
    gem={f'ENET{i}':params[f'PSU__ENET{i}__PERIPHERAL__ENABLE'] for i in range(4)}
    assert set(gem.values())=={'0'}
    wrapper=ROOT/'rtl/platform/typed200/typed200_encoder_wrapper.v'
    # The actual slave wrapper has neither requester ID/USER nor PROT inputs.
    assert not re.search(r'input\s+(?:wire|logic)?[^;\n]*s_axil_(?:aw|ar)(?:user|prot|id)\b',read(wrapper))
    gate=CAND/'contracts/typed_publication_gate.sv'
    original=ROOT/'rtl/contracts/typed_publication_gate.sv'
    assert logic(read(gate))==logic(read(original))
    proof=ROOT/'build/v2/typed-formal-gate-final-v5/receipt.json'
    proofdata=json.loads(read(proof))
    assert proofdata['induction_proved'] and proofdata['rtl_sha256']==sha(original)
    local=[
      (ROOT/'firmware/typed200_mvp/ownership.c','{V_CRF_APB_RST_FPD_APU,0xf,0xf}'),
      (ROOT/'firmware/typed200_mvp/ownership.c','{V_CRL_APB_RST_LPD_IOU0,0xf,0xf}'),
      (ROOT/'firmware/typed200_mvp/platform.c','while((rd(0,0xfd1a0104)&15)!=15'),
      (ROOT/'firmware/typed200_mvp/platform.c','one-shot evidence; no concurrent client'),
      (ROOT/'firmware/typed200_k26_boot/pmu_seal.c','if(((p[0]>>16)&0xffu)!=TB_MODULE && !seal.closed)return 0'),
      (gate,'else if(active)'),(gate,"else if(elapsed==limit_reg-1'b1)"),
      (gate,'if(ack && result_valid && !quarantined)'),
      (CAND/'contracts/typed_intent_guard.sv','wire successful_epoch'),
      (CAND/'platform/kr260/typed200_encoder.sv','wire live_quiet=!busy && memory_drained'),
      (ROOT/'firmware/typed200_r5/service.c','for(unsigned i=0;i<c->tokens;i++)c->ids[i]=ids[i]'),
      (ROOT/'firmware/typed200_v2/typed200.c','for(unsigned i=0;i<tokens*TI_HIDDEN;i++)dst->hidden[i]=result[i]'),
      (ROOT/'scripts/v2/kr260/sysone-v2.dts','Memory reservation belongs in the boot DTB'),
      (ROOT/'firmware/typed200_mvp/reference/psu_init.c','unsigned long psu_protection_lock_data')]
    findings=[location(p,n) for p,n in local]
    externalfiles={
      'remoteproc.c':'drivers/remoteproc/xlnx_r5_remoteproc.c',
      'r5fss.yaml':'Documentation/devicetree/bindings/remoteproc/xlnx,zynqmp-r5fss.yaml',
      'of-reserved-mem.c':'drivers/of/of_reserved_mem.c',
      'fpga-manager.c':'drivers/fpga/zynqmp-fpga.c',
      'zynqmp-core.c':'drivers/firmware/xilinx/zynqmp-core.c',
      'zynqmp-pm.c':'drivers/firmware/xilinx/zynqmp-pm.c',
      'zynqmp-fpga.c':'drivers/firmware/xilinx/zynqmp-fpga.c'}
    commit=read(OUT/'linux-xlnx-commit.txt').strip();assert re.fullmatch('[a-f0-9]{40}',commit)
    primary={name:dict(url=f'https://raw.githubusercontent.com/Xilinx/linux-xlnx/{commit}/{path}',
                      sha256=sha(OUT/name)) for name,path in externalfiles.items()}
    # Pin installed implementation sources actually reviewed, not just macro examples.
    sdk=Path('C:/AMDDesignTools/2025.2/Vitis/data/embeddedsw/lib/sw_apps/zynqmp_pmufw/src')
    installed={str(sdk/n):sha(sdk/n) for n in ['pm_core.c','pm_ioctl.c','pm_clock.c','pm_reset.c','xpfw_xpu.c']}
    result=dict(schema='sysone.typed200.amp-feasibility.v1',investigation_complete=True,
      deployable=False,board_contact=False,rtl_modified=False,build_started=False,
      current_mvp_supports_linux=False,hardware_exclusivity_verified=False,wcet_certified=False,
      existing_logic_deadline_evidence=dict(gate_matches_proved_source_modulo_comments_whitespace=True,
        receipt=location(proof,'induction_proved'),
        scope='Existing RTL-step invariant only; continuous clock/reset and protected controls required; no physical/AMP proof'),
      control_interfaces={name:{k:v for k,v in p.items() if k in
        ['PROTOCOL','ARUSER_WIDTH','AWUSER_WIDTH','DATA_WIDTH','ADDR_WIDTH']} for name,p in buses.items()},
      generated_ps_ethernet_enables=gem,hwh_sha256=sha(hwh),wrapper_sha256=sha(wrapper),
      local_source_evidence=findings,linux_reference_commit=commit,primary_source_snapshots=primary,
      installed_primary_sha256=installed,
      unavailable_reference=dict(name='XAPP1353 source archive',
       attempted_url='https://www.xilinx.com/support/documentation/application_notes/xapp1353-pl-isolation.zip',
       received='AMD Customer Community HTML, not ZIP; docs inspected, VHDL not obtained or audited',
       sha256=sha(OUT/'xapp1353-download-attempt.bin')))
    (OUT/'source-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    matrix=[
      ['R5 code/stack/PMU counter','R5 plus trusted loader before lease','No runtime A53 write/load/reset; protect global TCM aliases',
       'R5 MPU alone does not isolate A53/DMA','XPPU/TZ coverage and lifecycle negative tests','firmware/typed200_mvp/platform.c'],
      ['Model/head','R5/PL read; trusted loader writes before lease','A53 and all Linux DMA writes denied after seal',
       'Startup hash is not continuous integrity','DDR XMPU policy across ingress paths; lock configs','firmware/typed200_mvp/platform.c'],
      ['IDs/hidden','R5 writes IDs; encoder writes hidden; R5 reads hidden','No Linux write during owned epoch',
       'Current addresses shared with system DDR','Boot carveout + enforcement + alias/cache review','firmware/typed200_v2/typed200.c'],
      ['Typed CSR/permit/ACK/proposal','R5 only','Linux denied; export independent read-only status',
       'AW/ARUSER 16 bits upstream -> 0 at both Lite endpoints','Filter before identity loss; verify source-ID decode/lock/reset','rtl/platform/typed200/typed200_encoder_wrapper.v'],
      ['PL/R5 clocks/reset/power/CSU','Trusted platform policy','Linux only approved disjoint leaf operations',
       'Current PMU seal blocks every normal IPI, not Linux-compatible selective ownership','API+resource+argument filter, direct-MMIO protection and PSCI review','firmware/typed200_k26_boot/pmu_seal.c'],
      ['GEM/Linux private DDR','Linux on one A53; selected Ethernet controller DMA','Keep SSH live; DMA restricted to private buffers',
       'Generated standalone HWH disables ENET0..3; frozen rules reset all GEM','New Linux-compatible PS/DT; all DMA masters policy and stress','firmware/typed200_mvp/ownership.c'],
      ['Ingress IPC','Linux submits; R5 takes bounded private snapshot','No Linux mutation of an admitted owned slot; R5 never waits for Linux after admit',
       'Frozen service is preloaded one-shot; no deployed broker','Separate mailbox/driver ABI, bounds/ownership/cache protocol','firmware/typed200_r5/service.c'],
      ['Terminal delivery','PL authoritative local record; R5 mirrors; Linux reads','Local deadline excludes SSH delivery; Linux cannot ACK the authoritative CSR',
       'Linux scheduling/network and DDR service not bounded','Guard/retention proof + eventual-copy tests; network percentiles separate','rtl/v2/candidates/typed200_row_range_csa/contracts/typed_publication_gate.sv'],
      ['Shared DDR/interconnect','All admitted masters','Need bounded service only to promise Accepted by D',
       'One A53/GEM DMA can contend; carveout/XMPU/QoS priority is not a latency proof','Matched traffic, adversarial stress, documented regulator/service bounds','scripts/v2/kr260/create_project_kr260.tcl']]
    csvpath=DOC/'2026-10-16-typed200-amp-ownership-matrix.csv'
    with csvpath.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['resource','proposed_owner','linux_policy','current_gap','required_evidence','local_source']);w.writerows(matrix)
    print('PASS structural AMP audit: current MVP incompatible; 16->0 requester identity loss; ENET0..3 disabled.')
    print('Existing local guard proof source matches; no new isolation/target/WCET proof claimed.')

if __name__=='__main__':main()
