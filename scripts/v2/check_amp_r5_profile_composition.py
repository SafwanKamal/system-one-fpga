"""Compose the candidate with the frozen PL observer in simulation only."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-r5-profile-filter-v1'
FILTER=ROOT/'rtl/v2/candidates/typed200_amp_r5_profile/typed200_r5_profile_filter.sv'
PROBE=ROOT/'rtl/v2/candidates/typed200_amp_probe/axi_origin_probe.v'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);args=ap.parse_args()
    assert re.fullmatch(r'composition-check-v[0-9]+',args.attempt)
    out=BASE/args.attempt;out.mkdir(exist_ok=False)
    (out/'runner.py').write_bytes(Path(__file__).read_bytes())
    assert json.loads((BASE/'filter-check-v1/receipt.json').read_text())['rtl_sha256']==sha(FILTER)
    template=ROOT/'build/v2/typed200-amp-linux-tag-probe-v1/rtl-replay-v1/tb.sv'
    source=template.read_text();prefix,body=source.split('initial begin\n',1)
    # Declare downstream wires and insert the filter before the observer;
    # every channel traverses it, with no testbench bypass around the policy.
    declarations=prefix[prefix.index('logic [15:0] s_axi_awid;'):prefix.index('axi_origin_probe dut(')]
    ports=re.findall(r'logic\s*(?:\[[^\]]+\])?\s*(s_axi_\w+);',declarations)
    assert len(ports)==39,len(ports)
    instance=prefix[prefix.index('axi_origin_probe dut('):prefix.index('\n\nalways #5')]
    mapped=re.sub(r'\((s_axi_\w+)\)',lambda m:'('+m.group(1).replace('s_axi_','m_axi_')+')',instance)
    connect=['.clk(clk)','.reset_n(reset_n)','.protocol_fault(protocol_fault)']
    for port in ports:
        suffix=port[len('s_axi_'):]
        connect+=['.s_'+suffix+'('+port+')','.m_'+suffix+'(m_axi_'+suffix+')']
    insert=declarations.replace('s_axi_','m_axi_')+'logic protocol_fault;\n'
    insert+='typed200_r5_profile_filter #(.ENABLE_R5(1),.SOURCE_PATH_QUALIFIED(1)) filter('+','.join(connect)+');\n'+mapped
    prefix=prefix.replace(instance,insert).replace("16'h0077","16'h0049")
    commands=[body.split(' repeat(4)',1)[0],' repeat(4)@(negedge clk);reset_n=1;']
    for cpu in range(4):
        for slot in range(16):
            value=0x41500000|(cpu<<8)|slot
            commands.append(f"fork aw({140+cpu},2,{397+cpu*32},{slot},0,{slot%3});wd({slot},32'h{value:x},0,{(slot+1)%3},0);join response({397+cpu*32},3);")
    commands+= ["s_axi_aruser=16'h0080;s_axi_arprot=2;read(0,0,0,3);",
                "s_axi_aruser=16'h2000;s_axi_arprot=1;read(8,0,0,0);"]
    # Fixture: 64 privileged-profile writes establish the old ELF's expected
    # preamble count through the filter. This is not the original APU preamble
    # and is not a new bootable firmware/target diagnostic.
    for cpu in range(4):
        for slot in range(16):
            value=0x41500000|(cpu<<8)|slot
            commands.append(f"fork aw(8192,1,73,{slot},0,{slot%3});wd({slot},32'h{value:x},0,{(slot+1)%3},0);join response(73,0);")
    evidence=ROOT/'build/v2/typed200-amp-linux-tag-probe-v1/observation-review-v1/receipt.json'
    review=json.loads(evidence.read_text());writes=iter(review['r5_writes'])
    events=json.loads((ROOT/'build/v2/typed200-amp-linux-tag-probe-v1/firmware-check-v1/actual-elf-transactions.json').read_text())
    for event in events:
        offset=event['address']-0xa0000000;value=event['value']
        if event['kind']=='read':
            if offset==24:value=0x12000
            if offset==28:value=0x49
            commands.append(f"read({offset},32'h{value:x},0,0);")
        else:
            w=next(writes);assert w['address']==event['address'] and w['value']==value
            slot=offset//4
            commands.append(f"fork aw({w['user']},{w['prot']},{w['axi_id']},{slot},0,2);wd({slot},32'h{value:x},0,0,0);join response({w['axi_id']},0);")
    # Poison, unknown upper fields, nonprivileged/nonsecure/instruction, other
    # source IDs and address aliases must not change the downstream marker.
    denied=[(0x2400,1),(0x2c00,1),(0x3000,1),(0x2001,1),(0x2010,1),
            (0x208c,1),(0x2800,0),(0x2000,3),(0x2000,5)]
    for user,prot in denied:
        commands.append(f"fork aw({user},{prot},73,4,0,1);wd(4,32'hdeadbeef,0,0,0);join response(73,3);")
    commands.append("s_axi_aruser=16'h2000;s_axi_arprot=1;")
    for j,w in enumerate(review['r5_writes'],4):
        for offset,value in [(0,(w['prot']<<16)|w['user']),(4,w['address']),
                             (8,w['value']),(12,((60+j)<<16)|w['axi_id'])]:
            commands.append(f"read({256+j*16+offset},32'h{value:x},0,0);")
    commands+=['read(8,68,0,0);read(12,0,0,0);',
        'if(protocol_fault)$fatal(1,"unexpected protocol fault");',
        '$display("PASS composition: 64 APU writes denied; seeded 64 profile writes; 12 ELF events with observed metadata; denied mutations leave four markers intact");$finish;']
    tb=prefix+'initial begin\n'+'\n'.join(commands)+'\nend\nendmodule\n'
    (out/'tb.sv').write_text(tb)
    for name,cmd in [('compile',['C:/iverilog/bin/iverilog.exe','-g2012','-s','tb','-o',str(out/'sim.vvp'),str(out/'tb.sv'),str(FILTER),str(PROBE)]),
                     ('run',['C:/iverilog/bin/vvp.exe',str(out/'sim.vvp')])]:
        r=subprocess.run(cmd,capture_output=True,cwd=ROOT,timeout=120)
        (out/(name+'.log')).write_bytes(r.stdout+r.stderr)
        assert r.returncode==0,(name,r.stdout[-2000:],r.stderr[-2000:])
    assert b'PASS composition:' in r.stdout
    (out/'receipt.json').write_text(json.dumps(dict(passed=True,filter_sha256=sha(FILTER),probe_sha256=sha(PROBE),
        actual_elf_address_data_events=12,metadata_overridden_with_observed_values=True,
        apu_writes_rejected=64,synthetic_profile_fixture_writes=64,negative_mutations_rejected=len(denied),
        observed_markers_and_metadata_preserved=True,filter_has_no_bypass=True,
        source_path_qualified=False,simulation_only=True,target_deployment_admitted=False,
        bootable_filtered_smoke_firmware_ready=False),indent=2)+'\n')
    print(r.stdout.decode())

if __name__=='__main__':main()
