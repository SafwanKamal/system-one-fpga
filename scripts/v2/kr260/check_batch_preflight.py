"""Inspect synthesized fit and UltraRAM registers before paying for full routing."""
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[3]
BUILD=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/"build/v2/kr260-opt-batch"


def main():
    context = BUILD.name == "kr260-opt-attention-context-capture-large"
    paired = context or BUILD.name == "kr260-opt-request-window-embed-large"
    narrowed = BUILD.name in {"kr260-opt-attention16-distance-large", "kr260-opt-request-window-embed-large", "kr260-opt-attention-context-capture-large"}
    lanes = 16 if narrowed else 32
    shared = BUILD.name in {"kr260-opt-dot7-large", "kr260-opt-capture-large", "kr260-opt-capture-flags-large", "kr260-opt-pipeline-cuts-large", "kr260-opt-operand-capture-large", "kr260-opt-source-row-bram-large", "kr260-opt-attention16-distance-large", "kr260-opt-request-window-embed-large", "kr260-opt-attention-context-capture-large"}
    report=(BUILD/"preflight-utilization.rpt").read_text()
    resources={}
    for name,limit in (("CLB LUTs",117120),("CLB Registers",234240),("Block RAM Tile",144),("URAM",64),("DSPs",1248)):
        match=re.search(r"\|\s*"+re.escape(name)+r"\*?\s*\|\s*([\d,.]+)\s*\|",report)
        if not match: raise ValueError(f"Missing {name} utilization")
        used=float(match[1].replace(",",""))
        if used>limit: raise ValueError(f"{name} exceeds device capacity")
        resources[name]={"used":used,"available":limit}
    memories=json.loads((BUILD/"preflight-memory.json").read_text())
    if len(memories)!=int(resources["URAM"]["used"]) or not memories:
        raise ValueError("Missing UltraRAM primitive inventory")
    pipelined=[m for m in memories if re.search(r"OREG_[AB]=(?:TRUE|1)(?:;|$)",m["output_registers"],re.I)]
    result={"resources":resources,"uram_blocks":len(memories),"uram_with_output_register":len(pipelined),
            "all_uram_outputs_registered":len(pipelined)==len(memories),
            "stage":"synthesis only; placement/routing and board validation still required"}
    if shared or BUILD.name in {"kr260-opt-batch2", "kr260-opt-batch3", "kr260-opt-dot", "kr260-opt-dot2", "kr260-opt-dot3", "kr260-opt-dot4", "kr260-opt-dot4-large", "kr260-opt-dot5", "kr260-opt-dot5-large"}:
        controls=json.loads((BUILD/"preflight-query-controls.json").read_text())
        if not controls or any(not 0 < c["loads"] <= 16 for c in controls):
            raise ValueError("Local query enable replication/fanout failed; review before routing")
        result["query_control_registers"]=len(controls)
        result["max_query_control_loads"]=max(c["loads"] for c in controls)
    if shared or BUILD.name in {"kr260-opt-batch3", "kr260-opt-dot", "kr260-opt-dot2", "kr260-opt-dot3", "kr260-opt-dot4", "kr260-opt-dot4-large", "kr260-opt-dot5", "kr260-opt-dot5-large"}:
        controls=json.loads((BUILD/"preflight-accumulator-controls.json").read_text())
        if not controls:
            raise ValueError("Missing local accumulator controls")
        for c in controls:
            limit = 256 if "word_reg" in c["cell"] else 64
            if not 0 < c["loads"] <= limit:
                raise ValueError(f"Accumulator control fanout exceeds {limit}: {c['cell']}")
        result["accumulator_control_registers"]=len(controls)
        result["max_accumulator_control_loads"]=max(c["loads"] for c in controls)
    if shared or BUILD.name in {"kr260-opt-dot", "kr260-opt-dot2", "kr260-opt-dot3", "kr260-opt-dot4", "kr260-opt-dot4-large", "kr260-opt-dot5", "kr260-opt-dot5-large"}:
        stages=json.loads((BUILD/"preflight-dot-stages.json").read_text())
        if {s["stage"] for s in stages}!={"pairs","quads","octets"} or any(s["registers"]<=0 for s in stages):
            raise ValueError("Deep dot pipeline registers missing")
        result["dot_pipeline_stages"]=stages
    if shared:
        rams=json.loads((BUILD/"preflight-accumulator-ram.json").read_text())
        if not rams or any(not r["primitive"].startswith("RAM") or r["primitive"].startswith("RAMB") for r in rams):
            raise ValueError("Shared accumulator RAM inventory missing/incorrect")
        previous=json.loads((ROOT/"build/v2/kr260-opt-dot5-large/preflight-summary.json").read_text())
        before=previous["resources"]["CLB LUTs"]["used"]
        result["lut_reduction_vs_failed_dot5"] = before-resources["CLB LUTs"]["used"]
        result["accumulator_ram_cells"] = len(rams)
        # Heuristic placement admission: require useful area relief before
        # paying for another congested full implementation. Not closure proof.
        if resources["CLB LUTs"]["used"] > before*0.95:
            raise ValueError("Less than 5% LUT relief versus failed dot5; optimize before placement")
    if BUILD.name in {"kr260-opt-capture-large", "kr260-opt-capture-flags-large", "kr260-opt-pipeline-cuts-large", "kr260-opt-operand-capture-large", "kr260-opt-source-row-bram-large", "kr260-opt-attention16-distance-large", "kr260-opt-request-window-embed-large", "kr260-opt-attention-context-capture-large"}:
        capture=json.loads((BUILD/"preflight-local-capture.json").read_text())
        if capture["registers"] != 896:
            raise ValueError("Per-buffer 7x128 physical capture was not preserved")
        result["local_read_capture_registers"]=capture["registers"]
    if BUILD.name in {"kr260-opt-capture-flags-large", "kr260-opt-pipeline-cuts-large", "kr260-opt-operand-capture-large", "kr260-opt-source-row-bram-large", "kr260-opt-attention16-distance-large", "kr260-opt-request-window-embed-large", "kr260-opt-attention-context-capture-large"}:
        flags=json.loads((BUILD/"preflight-length-flags.json").read_text())
        if flags["registers"] != 2:raise ValueError("Length FIFO registered full/empty cut missing")
        result["length_fifo_flag_registers"]=2
    if BUILD.name in {"kr260-opt-pipeline-cuts-large", "kr260-opt-operand-capture-large", "kr260-opt-source-row-bram-large", "kr260-opt-attention16-distance-large", "kr260-opt-request-window-embed-large", "kr260-opt-attention-context-capture-large"}:
        cuts=json.loads((BUILD/"preflight-pipeline-cuts.json").read_text())
        if cuts['probability_dsps']!=lanes or cuts['registered_probability_dsps']!=lanes or cuts['drain_bank_capture_ff']<256:
            raise ValueError('Probability/drain pipeline inference gates failed')
        result['pipeline_cuts']=cuts
    if BUILD.name in {"kr260-opt-operand-capture-large", "kr260-opt-source-row-bram-large", "kr260-opt-attention16-distance-large", "kr260-opt-request-window-embed-large", "kr260-opt-attention-context-capture-large"}:
        inputs=json.loads((BUILD/"preflight-operand-capture.json").read_text())
        if inputs['probability_input_registered_dsps']!=lanes or inputs['local_embed_control_ff']<=0:
            raise ValueError('DSP input capture or local embedding controls missing')
        inventory=(BUILD/"preflight-probability-input.txt").read_text().splitlines()
        if len(inventory)!=lanes or any('AREG=1 BREG=2 PREG=1' not in line for line in inventory):
            raise ValueError('Probability DSP input/PREG inventory mismatch')
        result['operand_capture']=inputs
    if BUILD.name in {"kr260-opt-source-row-bram-large", "kr260-opt-attention16-distance-large", "kr260-opt-request-window-embed-large", "kr260-opt-attention-context-capture-large"}:
        banks=json.loads((BUILD/"preflight-linear-bram.json").read_text())
        row=json.loads((BUILD/"preflight-source-row.json").read_text())
        if not banks or row['row_registers'] <= 0 or row['linear_lutram_cells'] != 0:
            raise ValueError('LINEAR block banks or incremental row stage missing')
        if any(not b['primitive'].startswith('RAMB') or b['write_mode_a'] != 'READ_FIRST' or b['write_mode_b'] != 'READ_FIRST' or b['doa_reg'] != 0 or b['dob_reg'] != 0 for b in banks):
            raise ValueError('LINEAR read-first/one-clock bank contract changed')
        result['linear_block_bank_primitives']=len(banks)
        result['incremental_source_row']=row
    if narrowed:
        mapping=json.loads((BUILD/"preflight-attention-width-distance.json").read_text())
        if mapping != {'query_lanes':16,'external_distance_ff':352,'distance_dsps':16,'distance_dsp_mapping_passed':16}:
            raise ValueError('Attention query width or fabric score-distance mapping failed')
        inventory=(BUILD/"preflight-distance-dsp.txt").read_text().splitlines()
        if len(inventory)!=16 or any('AREG=0 PREG=1' not in line for line in inventory):
            raise ValueError('Score distance DSP input/PREG inventory failed')
        controls=json.loads((BUILD/'preflight-accumulator-controls.json').read_text())
        originals={c['cell'] for c in controls if not re.search(r'_rep(?:_\d+)?$',c['cell'])}
        replicas=[c for c in controls if re.search(r'_rep(?:_\d+)?$',c['cell'])]
        if (result['query_control_registers'] != 512 or len(originals) != 512
                or len(originals)+len(replicas) != len(controls)
                or any(re.sub(r'_rep(?:_\d+)?$','',c['cell']) not in originals for c in replicas)):
            raise ValueError('Narrow query/accumulator control inventory differs')
        result['accumulator_original_control_registers']=len(originals)
        result['accumulator_replicated_control_registers']=len(replicas)
        baseline=json.loads((ROOT/"build/v2/kr260-opt-source-row-bram-large/preflight-summary.json").read_text())
        before=baseline['resources']['CLB LUTs']['used']
        if resources['CLB LUTs']['used'] > before*.9:
            raise ValueError('Less than10% whole-design LUT relief; review tradeoff before placement')
        result['attention_width_distance']=mapping
        result['lut_reduction_vs_source_row_bram']=before-resources['CLB LUTs']['used']
    if paired:
        cuts=json.loads((BUILD/'preflight-window-embed.json').read_text())
        if cuts['request_window_registers']<17 or cuts['embed_address_dsps']!=2 or cuts['embed_address_mapping_passed']!=2:
            raise ValueError('Paired request-window/embedding address stage missing')
        inventory=(BUILD/'preflight-embed-address-dsp.txt').read_text().splitlines()
        if len(inventory)!=2 or any('AREG=1 BREG=1 CREG=1 MREG=0 PREG=1' not in line for line in inventory):
            raise ValueError('Embedding address DSP register inventory mismatch')
        result['request_window_embed']=cuts
    if context:
        capture=json.loads((BUILD/'preflight-context-capture.json').read_text())
        if capture['fabric_context_ff'] < 92 or capture['context_dsps'] != 4 or capture['mapping_passed'] != 4:
            raise ValueError('Fabric context register/DSP mapping failed')
        inventory=(BUILD/'preflight-context-dsp.txt').read_text().splitlines()
        if len(inventory)!=4 or any('AREG=0 BREG=1 MREG=0 PREG=1' not in line for line in inventory):
            raise ValueError('Context DSP input/PREG inventory mismatch')
        result['context_capture']=capture
    (BUILD/"preflight-summary.json").write_text(json.dumps(result,indent=2)+"\n")
    if len(pipelined)!=len(memories):
        raise ValueError("UltraRAM output register inference needs review; inspect preflight-memory.json")
    print("PASS: synthesized resource fit and UltraRAM output registers; ready for routing review")


if __name__=="__main__": main()
