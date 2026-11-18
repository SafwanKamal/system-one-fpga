"""Full AXIL endpoint sequential correspondence, including byte-cache invariant."""
from pathlib import Path
import argparse,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='typed200-profile-cache-formal-v1');a=ap.parse_args()
    out=ROOT/'build/v2'/a.name;out.mkdir(exist_ok=False);rel=out.relative_to(ROOT).as_posix();sources=[]
    # Proof-only ports in copied modules expose private recurrence state, not RTL.
    state={'configured':1,'result_session':64,'ready':1,'active':1,'valid':1,'quarantine':1,
           'result_id':64,'result_contract':256,'outcome':3,'label':16,'score':16,'elapsed':32,
           'proof_seen':64,'proof_last':64,'proof_limit':32}
    sw=sum(state.values())
    for prefix,candidate in [('old','typed200_flush'),('new','typed200_profile_cache')]:
        folder=ROOT/'rtl/v2/candidates'/candidate/'contracts'
        for fn,module in [('typed_publication_gate.sv','gate'),('typed_intent_guard.sv','guard'),('typed_intent_axil.sv','axil')]:
            p=folder/fn;sources.append(p);s=p.read_text()
            s=s.replace('module typed_'+('publication_gate' if module=='gate' else 'intent_'+module),f'module {prefix}_{module}',1)
            if module=='gate':
                s=s.replace('output logic [31:0] elapsed\n','output logic [31:0] elapsed,\n    output wire [63:0] proof_last,\n    output wire [31:0] proof_limit\n')
                s=s.replace('endmodule','assign proof_last=last_request;assign proof_limit=limit_reg;\nendmodule')
            if module=='guard':
                s=s.replace('typed_publication_gate #(',f'{prefix}_gate #(')
                s=s.replace('output wire [31:0] elapsed\n','output wire [31:0] elapsed,\n    output wire [63:0] proof_seen,proof_last,\n    output wire [31:0] proof_limit\n')
                s=s.replace('.elapsed(elapsed)', '.elapsed(elapsed),.proof_last(proof_last),.proof_limit(proof_limit)')
                s=s.replace('endmodule','assign proof_seen=last_seen_request;\nendmodule')
            if module=='axil':
                s=s.replace('output wire [63:0] admitted_session, admitted_request_id\n',f'''output wire [63:0] admitted_session, admitted_request_id,
    output wire [959:0] proof_bank,
    output wire [119:0] proof_written,
    output wire [45:0] proof_bus,
    output wire [{sw-1}:0] proof_state,
    output wire [31:0] proof_flags
''')
                s=s.replace('typed_intent_guard guard',f'{prefix}_guard guard')
                s=s.replace('.elapsed(elapsed)', '.elapsed(elapsed),.proof_seen(proof_seen),.proof_last(proof_last),.proof_limit(proof_limit)')
                observe='wire [63:0] proof_seen,proof_last;wire [31:0] proof_limit;\n'
                observe+='for(genvar j=0;j<30;j++) begin assign proof_bank[32*j+:32]=bank[j];assign proof_written[4*j+:4]=written[j];end\n'
                observe+='assign proof_bus={aw_full,w_full,aw,wd,ws};\n'
                observe+='assign proof_state={'+','.join(state)+'};\n'
                if prefix=='new':observe+='assign proof_flags=profile_byte_equal;\n'
                else:observe+="localparam [255:0] EXPECTED=256'h8133633315487f8f322ecac49e95e7aca3801d00fccb4b4fba36026c5b2752d2;\nfor(genvar j=0;j<32;j++) assign proof_flags[j]=bank[6+j/4][8*(j%4)+:8]==EXPECTED[8*j+:8];\n"
                s=s.replace('endmodule',observe+'endmodule')
            (out/f'{prefix}_{module}.sv').write_text(s)
    inputs={'clk':1,'reset':1,'s_awaddr':8,'s_awvalid':1,'s_wdata':32,'s_wstrb':4,'s_wvalid':1,
        's_bready':1,'s_araddr':8,'s_arvalid':1,'s_rready':1,'core_complete':1,'core_success':1,
        'live_quiet':1,'core_session':64,'core_request_id':64,'environment_ready':1,
        'encoder_clocks':32,'request_clocks':32}
    outputs={'s_awready':1,'s_wready':1,'s_bresp':2,'s_bvalid':1,'s_arready':1,'s_rdata':32,
        's_rresp':2,'s_rvalid':1,'terminal_valid':1,'terminal_quarantined':1,'retired':1,
        'admission_tokens':16,'admission_first':16,'admission_count':16,'owned_tokens':16,
        'owned_first':16,'owned_count':16,'admitted':1,'admitted_session':64,'admitted_request_id':64,
        'proof_bank':960,'proof_written':120,'proof_bus':46,'proof_state':sw,'proof_flags':32}
    def decl(k,n,w):return k+(' ' if w==1 else f' [{w-1}:0] ')+n
    code='module cache_formal('+',\n'.join(decl('input wire',n,w) for n,w in inputs.items())+');\n'
    for prefix in ('old','new'):
        code+=';\n'.join(decl('wire',prefix+'_'+n,w) for n,w in outputs.items())+';\n'
        code+=prefix+'_axil '+prefix+'('+','.join([f'.{n}({n})' for n in inputs]+[f'.{n}({prefix}_{n})' for n in outputs])+');\n'
    code+='reg past_valid=0;always @(posedge clk) begin past_valid<=1;if(!past_valid) assume(reset);if(past_valid) begin\n'
    code+='\n'.join(f'assert(old_{n}==new_{n});' for n in outputs)+'\nend end endmodule\n'
    (out/'miter.sv').write_text(code)
    files=' '.join(f'{rel}/{p}_{m}.sv' for p in ('old','new') for m in ('gate','guard','axil'))
    (out/'prove.ys').write_text(f'''read_verilog -formal -sv {files} {rel}/miter.sv
prep -top cache_formal -flatten
memory
opt -full
async2sync
chformal -lower
formalff -clk2ff
dffunmap
opt_clean
opt -full
sat -verify -prove-asserts -tempinduct -seq 2 -maxsteps 12 -set-assumes -set clk 1 -timeout 120 -dump_vcd {rel}/counterexample.vcd
''')
    with (out/'console.log').open('w') as log:
        r=subprocess.run(['uv','tool','run','--from','yowasp-yosys==0.70.0.0.post1259','yowasp-yosys','-Q','-T','-l',f'{rel}/prove.log','-s',f'{rel}/prove.ys'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    passed=r.returncode==0 and 'Induction step proven: SUCCESS!' in (out/'prove.log').read_text()
    (out/'receipt.json').write_text(json.dumps({'passed':passed,'exit_code':r.returncode,
        'scope':'Full AXIL endpoint outputs, stored bank/written/bus/guard state and all32 byte invariants match at every sampled edge',
        'assumptions':['first sampled edge reset','single sampled clock','two-state semantics'],
        'axi_master_constraints':'None; arbitrary valid/backpressure/addresses/data/byte strobes',
        'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in sources},
        'artifact_sha256':{p.name:sha(p) for p in out.iterdir() if p.is_file()}},indent=2)+'\n')
    print('PASS full endpoint sequential equivalence and byte-cache invariant' if passed else 'NOT PROVED; preserve attempt')
    raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()
