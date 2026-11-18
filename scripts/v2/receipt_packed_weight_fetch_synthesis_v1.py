"""Verify completed offline synthesis and bind it to qualified RTL fingerprints."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--synthesis",type=Path,required=True)
    ap.add_argument("--simulation",type=Path,required=True)
    args=ap.parse_args()
    target=args.synthesis/"qualification.json"
    if target.exists():raise FileExistsError(target)
    simulation=json.loads((args.simulation/"qualification.json").read_text(encoding="utf-8"))
    if simulation["stage"]!="complete" or not all(x["passed"] for x in simulation["checks"]):
        raise ValueError("simulation not qualified")
    rtl=["packed_weight_row16.sv","packed_weight_fetch16_v1.sv",
         "signed_int8_dot16_v1.sv","packed_weight_fetch_dot16_v1.sv"]
    source_paths=[ROOT/"rtl/v2/common"/name for name in rtl]
    for path in source_paths:
        key=str(path.relative_to(ROOT))
        if simulation["source_sha256"][key]!=sha(path):raise ValueError(f"RTL changed: {path}")
    script=ROOT/"scripts/v2/kr260/check_packed_weight_fetch_dot_ooc_v1.tcl"
    source_paths.extend([script,Path(__file__).resolve()])
    log=(args.synthesis/"vivado.log").read_text(encoding="utf-8")
    if "ERROR:" in log or "CRITICAL WARNING:" in log or log.count("synth_design completed successfully")!=3:
        raise ValueError("incomplete/failed synthesis")
    warnings=[line for line in log.splitlines() if line.startswith("WARNING:")]
    unused=[line for line in warnings if re.fullmatch(
        r"WARNING: \[Synth 8-7129\] Port packed_row\[\d+\] in module packed_weight_row16 is either unconnected or has no load",line)]
    clock_warning='WARNING: [Timing 38-242] The property HD.CLK_SRC of clock port "clk" is not set. In out-of-context mode, this prevents timing estimation for clock delay/skew'
    zero_replication=[line for line in warnings if re.fullmatch(
        r"WARNING: \[Synth 8-693\] zero replication count - replication ignored \[.*rtl/v2/common/packed_weight_row16.sv:20\]",line)]
    unexpected=[line for line in warnings if line not in unused and line!=clock_warning and line not in zero_replication]
    if unexpected:raise ValueError(f"unreviewed warnings: {unexpected}")
    if len(unused)!=48 or warnings.count(clock_warning)!=3 or len(zero_replication)!=16:
        raise ValueError("unexpected warning counts")
    rows=[]
    for bits in (6,7,8):
        for kind in (f"complete-{bits}.txt",f"utilization-{bits}.rpt",f"synthesis-timing-{bits}.rpt",f"synthesized-{bits}.dcp"):
            if not (args.synthesis/kind).is_file():raise FileNotFoundError(kind)
        report=(args.synthesis/f"utilization-{bits}.rpt").read_text(encoding="utf-8")
        if "packed_weight_fetch_dot16_v1" not in report or "Design State : Synthesized" not in report:
            raise ValueError("wrong design/report state")
        counts={}
        for label in ("CLB LUTs*","CLB Registers","DSPs","Block RAM Tile"):
            matches=re.findall(r"\|\s*"+re.escape(label)+r"\s*\|\s*(\d+)\s*\|",report)
            if len(matches)!=1:raise ValueError(f"resource count {label}")
            counts[label]=int(matches[0])
        rows.append(dict(bits=bits,resource_counts=counts))
    result=dict(stage="complete",scope="isolated offline KR260 synthesis only",
        board_contacted=False,deployed_design_changed=False,placed=False,routed=False,
        hardware_timing_qualified=False,frequency_claim=None,
        synthesized_top="packed_weight_fetch_dot16_v1",part="xck26-sfvc784-2LV-c",
        threads=2,simulation_qualification_sha256=sha(args.simulation/"qualification.json"),
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in source_paths},
        source_binding="All four actual synthesis input RTL hashes match passing simulation receipt; TCL/log specify these input paths",
        warning_review=dict(count=len(warnings),critical=0,errors=0,
            unused_bits=len(unused),missing_clock_source=3,zero_replication=len(zero_replication),
            reason="Unused upper packed-row bits:32 at6bit and16 at7bit. At8bits the16 sign-extensions replicate zero bits, yielding exact existing8bit codes. Each isolated top also lacks physical clock source; timing is unqualified."),
        checks=rows,artifact_sha256={p.name:sha(p) for p in args.synthesis.iterdir() if p.is_file()},
        limitations=["Memory-port logic is simulation-integrated but not included in this isolated synthesis top",
                     "No routed timing, full executor, model image, R5 ABI or board qualification",
                     "No whole-model quantization accuracy or requantization/accumulation"])
    target.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(stage="complete",checks=rows,warnings=len(warnings))))


if __name__=="__main__":main()
