"""Package a completed, timing-checked KR260 build for xmutil; never install it."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import shutil
import subprocess
import tarfile
import zipfile
if __package__:
    from .check_routed_evidence import validate as validate_routed
else:
    from check_routed_evidence import validate as validate_routed


def frontier_profile(candidate):
    if candidate not in ("dot5-large", "dot7-large", "capture-large", "capture-flags-large", "pipeline-cuts-large", "operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large"):
        raise ValueError("Unknown frozen frontier candidate")
    profile = {"max_hidden": 1024, "mac_input_registers": 1, "exp_table_in_bram": 1,
            "pipelined_uram": 1, "stream_results": 1, "local_query_registers": 1,
            "perf_counters": 1, "local_accumulator_controls": 3 if candidate != "dot5-large" else 1,
            "pipelined_dot": 1}
    if candidate in ("capture-large","capture-flags-large", "pipeline-cuts-large", "operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large"):
        profile["local_read_capture"] = 1
    if candidate in ("capture-flags-large", "pipeline-cuts-large", "operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large"):
        profile["registered_fifo_flags"] = 1
    if candidate in ("pipeline-cuts-large", "operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large"):
        profile.update(probability_pipeline=1,pipelined_drain_select=1)
    if candidate in ("operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large"):
        profile.update(probability_input_capture=1,local_embed_controls=1)
    if candidate in ("source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large"):
        profile.update(incremental_source_row=1,linear_accumulators_in_bram=1)
    if candidate in ("attention16-distance-large","request-window-embed-large","attention-context-capture-large"):
        profile.update(attention_lanes=16,fabric_score_distance=1)
    if candidate in ("request-window-embed-large","attention-context-capture-large"):
        profile.update(cached_request_window=1,dsp_embed_row_address=1)
    if candidate == "attention-context-capture-large":
        profile.update(fabric_context_capture=1)
    return profile


def capture_fixture(checks, repo):
    """Require the complete eight-length fixture used by the frozen regression."""
    vectors = repo / "build/v2/kr260-dot7-h1024-eight-vectors"
    recorded = checks["checks"]["h1024"]["vectors_sha256"]
    required = {"image.hex", "manifest.json", "cases.txt", *(f"case_{i}.txt" for i in range(8))}
    if not required <= recorded.keys():
        raise SystemExit("Incomplete frozen capture fixture")
    for name in required:
        if hashlib.sha256((vectors / name).read_bytes()).hexdigest() != recorded[name]:
            raise SystemExit(f"Capture fixture differs from regression: {name}")
    manifest = json.loads((vectors / "manifest.json").read_text())
    if (manifest.get("reference_verified") is not True or manifest["dims"]["hidden"] != 1024
            or manifest["dims"]["ffn"] != 4096
            or manifest["token_lengths"] != [1, 2, 3, 4, 5, 12, 64, 128]):
        raise SystemExit("Capture requires eight independently verified H1024 lengths")
    return vectors, manifest


def attention_distance_evidence(checks, repo):
    """Validate the additional query grouping fixture and measured scheduling cost."""
    cost=checks.get('encoder_cycle_change_vs_32query_range_percent')
    if (checks.get('capability_word') != ('0x5377ffff' if checks.get('candidate')=='attention-context-capture-large' else '0x5363ffff' if checks.get('candidate')=='request-window-embed-large' else '0x535affff') or checks.get('numerical_cases') != 32
            or checks.get('query_group_cases') != 4 or checks.get('partial_tile_cases') != 6
            or checks.get('nexys_default_cycles_unchanged') is not True
            or not isinstance(cost,list) or len(cost)!=2
            or not all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in cost)
            or cost[0]>cost[1] or not checks.get('cycle_comparison_scope')):
        raise SystemExit('Missing exact attention query-group/scheduling evidence')
    vectors=repo/'build/v2/attention16-head32-vectors'
    recorded=checks.get('query_group_vectors_sha256',{})
    required={'image.hex','manifest.json','cases.txt',*(f'case_{i}.txt' for i in range(4))}
    if not required <= recorded.keys():
        raise SystemExit('Incomplete query-group fixture')
    for name in required:
        if hashlib.sha256((vectors/name).read_bytes()).hexdigest()!=recorded[name]:
            raise SystemExit('Query-group fixture differs: '+name)
    manifest=json.loads((vectors/'manifest.json').read_text())
    if (manifest.get('reference_verified') is not True or manifest['dims']['hidden']!=1024
            or manifest['dims']['head_dim']!=32 or manifest['token_lengths']!=[1,3,12,128]):
        raise SystemExit('Wrong query-group fixture profile')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--optimized", action="store_true", help="package the isolated MAC pipeline candidate")
    parser.add_argument("--bram", action="store_true", help="package the BRAM-table variant of the optimized candidate")
    parser.add_argument("--wide", action="store_true", help="package the 768-wide optimized BRAM candidate")
    parser.add_argument("--memory", action="store_true", help="package the routed wide pipelined UltraRAM candidate")
    parser.add_argument("--frontier", action="store_true", help="package the selected separately routed H1024 candidate")
    parser.add_argument("--frontier-candidate", choices=("dot5-large", "dot7-large", "capture-large", "capture-flags-large", "pipeline-cuts-large", "operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large"), default="dot5-large")
    args = parser.parse_args()
    capture = args.frontier and args.frontier_candidate in ("capture-large","capture-flags-large", "pipeline-cuts-large", "operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large")
    context_capture = args.frontier and args.frontier_candidate == "attention-context-capture-large"
    paired = args.frontier and args.frontier_candidate in ("request-window-embed-large","attention-context-capture-large")
    attention_distance = args.frontier and args.frontier_candidate in ("attention16-distance-large","request-window-embed-large","attention-context-capture-large")
    source_row_bram = args.frontier and args.frontier_candidate in ("source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large")
    operand_capture = args.frontier and args.frontier_candidate in ("operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large")
    pipeline_cuts = args.frontier and args.frontier_candidate in ("pipeline-cuts-large", "operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large")
    fifo_flags = args.frontier and args.frontier_candidate in ("capture-flags-large", "pipeline-cuts-large", "operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large")
    if args.frontier_candidate != "dot5-large" and not args.frontier:
        parser.error("--frontier-candidate requires --frontier")
    if args.frontier:
        args.optimized = args.bram = args.wide = args.memory = True
    if args.bram and not args.optimized:
        parser.error("--bram requires --optimized")
    if args.wide and not (args.optimized and args.bram):
        parser.error("--wide requires --optimized --bram")
    if args.memory and not args.wide:
        parser.error("--memory requires --optimized --bram --wide")
    repo = Path(__file__).resolve().parents[3]
    source = Path(__file__).resolve().parent
    build = repo / ("build/v2/kr260-opt" if args.optimized else "build/v2/kr260")
    app_name = "sysone-v2-pipe" if args.optimized else "sysone-v2"
    if args.bram:
        build = repo / "build/v2/kr260-opt-bram"
        app_name = "sysone-v2-bram"
    if args.wide:
        build = repo / "build/v2/kr260-opt-wide"
        app_name = "sysone-v2-wide"
    if args.memory:
        build = repo / "build/v2/kr260-opt-memory"
        app_name = "sysone-v2-memory"
    if args.frontier:
        build = repo / f"build/v2/kr260-opt-{args.frontier_candidate}"
        app_name = "sysone-v2-attention-context-capture" if context_capture else "sysone-v2-request-window-embed" if paired else "sysone-v2-attention16-distance" if attention_distance else "sysone-v2-source-row-bram" if source_row_bram else "sysone-v2-operand-capture" if operand_capture else "sysone-v2-pipeline-cuts" if pipeline_cuts else "sysone-v2-capture-flags" if fifo_flags else "sysone-v2-capture" if capture else "sysone-v2-frontier"
    bit = build / "sysone_v2_kr260.runs/impl_1/system_wrapper.bit"
    xsa = build / "sysone_v2_kr260.xsa"
    for artifact in (bit, xsa, build / "timing.rpt", build / "utilization.rpt"):
        if not artifact.is_file():
            raise SystemExit(f"Completed build required: missing {artifact}")
    # Reject preview/stale hardware exports. The build script only exports this
    # final XSA after the implemented design passes setup and hold timing.
    with zipfile.ZipFile(xsa) as hardware:
        embedded = [name for name in hardware.namelist() if name.endswith(".bit")]
        if len(embedded) != 1 or hardware.read(embedded[0]) != bit.read_bytes():
            raise SystemExit("Final XSA must contain the implemented bitstream")
    staging = build / "app-staging"
    staging.mkdir(exist_ok=True)
    profile_path = build / "runtime-clock.json"
    profile = json.loads(profile_path.read_text()) if profile_path.exists() else {
        "clock_requested_hz": 100000000, "clock_timing_max_hz": 100000000}
    requested, ceiling = profile["clock_requested_hz"], profile["clock_timing_max_hz"]
    if not 0 < requested <= ceiling <= (300000000 if args.frontier else 125000000 if args.optimized else 100000000):
        raise SystemExit("Invalid runtime clock profile")
    if paired and not requested == ceiling == 200000000:
        raise SystemExit("Paired candidate must qualify requested200MHz without fallback")
    if args.frontier and (profile.get("timing_qualified") is not True
                         or not all(type(profile.get(key)) in (int,float) and math.isfinite(profile[key]) and profile[key]>0
                                    for key in ("routed_setup_slack_ns","routed_hold_slack_ns"))):
        raise SystemExit("Frontier requires passing routed setup and hold evidence")
    # The completed memory candidate was also qualified with both Linux PL
    # clocks at 125 MHz; the implementation's unused PL1 default is 100 MHz.
    timing_path = build / ("timing-125mhz.rpt" if args.memory and not args.frontier else "timing.rpt")
    timing = timing_path.read_text()
    if args.frontier:
        if profile.get("candidate") != args.frontier_candidate:
            raise SystemExit("Runtime profile differs from selected frozen candidate")
        route_dir = build / f"route-{ceiling // 1000000}mhz"
        validate_routed(timing, (route_dir / "route-status.rpt").read_text(), ceiling // 1000000)
    if "All user specified timing constraints are met." not in timing:
        raise SystemExit("Passing routed timing report required")
    for name in ("clk_pl_0", "clk_pl_1"):
        clock = re.search(rf"^{name}\s+\{{[^}}]+\}}\s+([0-9.]+)\s+", timing, re.MULTILINE)
        if clock is None or abs(float(clock[1]) - 1e9 / ceiling) > 0.001:
            raise SystemExit(f"Timing report {name} differs from the runtime ceiling")
    checks = None
    regression_path = build / "regression.json"
    if not regression_path.is_file():
        regression_path = repo / ("build/v2/rtl-wide-check/summary.json" if args.wide else
                                  "build/v2/rtl-bram-check/summary.json" if args.bram
                                  else "build/v2/rtl-pipeline-check/summary.json")
    if args.optimized:
        generated = build / "sysone_v2_kr260.gen/sources_1/bd/system/ip/system_encoder_0/synth/system_encoder_0.v"
        if ".MAC_INPUT_REGISTERS(1)" not in generated.read_text():
            raise SystemExit("Candidate must enable registered MAC operands")
        if args.bram and ".EXP_TABLE_IN_BRAM(1)" not in generated.read_text():
            raise SystemExit("BRAM candidate must enable block RAM lookup tables")
        max_hidden = 1024 if args.frontier else 768
        if args.wide and f".MAX_HIDDEN({max_hidden})" not in generated.read_text():
            raise SystemExit(f"Wide candidate must enable {max_hidden}-wide activation storage")
        checks = json.loads(regression_path.read_text())
        expected_profile = {"max_hidden": 768, "mac_input_registers": 1, "exp_table_in_bram": 1}
        if args.memory:
            expected_profile.update(pipelined_uram=1, activation_read_latency=4)
            if ".PIPELINED_URAM(1)" not in generated.read_text():
                raise SystemExit("Memory candidate must enable pipelined UltraRAM")
        if args.frontier:
            expected_profile = frontier_profile(args.frontier_candidate)
            for flag in ("STREAM_RESULTS", "LOCAL_QUERY_REGISTERS", "PERF_COUNTERS",
                         "LOCAL_ACCUMULATOR_CONTROLS", "PIPELINED_DOT", *(("LOCAL_READ_CAPTURE",) if capture else ()), *(("REGISTERED_FIFO_FLAGS",) if fifo_flags else ()), *(("PROBABILITY_PIPELINE","PIPELINED_DRAIN_SELECT") if pipeline_cuts else ()), *(("PROBABILITY_INPUT_CAPTURE","LOCAL_EMBED_CONTROLS") if operand_capture else ()), *(("INCREMENTAL_SOURCE_ROW","LINEAR_ACCUMULATORS_IN_BRAM") if source_row_bram else ()), *(("ATTENTION_LANES","FABRIC_SCORE_DISTANCE") if attention_distance else ()), *(("CACHED_REQUEST_WINDOW","DSP_EMBED_ROW_ADDRESS") if paired else ()), *(("FABRIC_CONTEXT_CAPTURE",) if context_capture else ())):
                value = expected_profile[flag.lower()]
                if f".{flag}({value})" not in generated.read_text():
                    raise SystemExit(f"Frontier candidate must enable {flag}")
            if capture:
                if checks.get("numerical_cases") != 32 or checks.get("read_latency") != 5:
                    raise SystemExit("Capture numerical/latency evidence differs")
                if not pipeline_cuts and fifo_flags and (checks.get("encoder_cycles_unchanged_vs_capture") is not True
                                   or len(checks.get("rtl_sha256", {})) != 19):
                    raise SystemExit("Grouped FIFO cut lacks complete source/cycle equivalence evidence")
                if pipeline_cuts and (len(checks.get("rtl_sha256",{}))!=(23 if paired else 22 if operand_capture else 21)
                                      or checks.get("nexys_default_cycles_unchanged") is not True
                                      or not all(c.get("prototype_cycles_identical") is True for c in checks["checks"].values())):
                    raise SystemExit("Pipeline cuts lack complete source/default/cycle equivalence evidence")
                if operand_capture and (checks.get("capability_word")!=("0x5377ffff" if context_capture else "0x5363ffff" if paired else "0x535affff" if attention_distance else "0x53597fff" if source_row_bram else "0x53591fff")
                                        or checks.get("partial_tile_cases")!=6
                                        or checks.get("partial_tile_cycles_unchanged") is not True):
                    raise SystemExit("Operand capture lacks exact feature/partial-tile evidence")
                if attention_distance:
                    attention_distance_evidence(checks, repo)
                vectors, vector_manifest = capture_fixture(checks, repo)
            else:
                base_regression = repo / ("build/v2/rtl-dot7-check/summary.json" if args.frontier_candidate == "dot7-large"
                                          else "build/v2/rtl-dot5-check/summary.json")
                if hashlib.sha256(base_regression.read_bytes()).hexdigest() != checks.get("base_regression_sha256"):
                    raise SystemExit("Frontier base regression evidence differs")
        if args.wide and checks.get("profile") != expected_profile:
            raise SystemExit("Passing 768-wide regression evidence required")
        snapshot = build / "rtl-snapshot"
        for name, digest in checks["rtl_sha256"].items():
            source_file = (snapshot / Path(name).relative_to("rtl/v2")
                           if snapshot.is_dir() else repo / name)
            if not source_file.is_file() or hashlib.sha256(source_file.read_bytes()).hexdigest() != digest:
                raise SystemExit(f"RTL differs from the bit-exact regression: {name}")
    bootgen, dtc = shutil.which("bootgen"), shutil.which("dtc")
    if not bootgen or not dtc:
        raise SystemExit("bootgen and dtc must be on PATH (Vivado tools)")
    shutil.copyfile(bit, staging / f"{app_name}.bit")
    (staging / "bitstream.bif").write_text(f"all: {{ {app_name}.bit }}\n", encoding="ascii")
    subprocess.run([bootgen, "-arch", "zynqmp", "-image", "bitstream.bif",
                    "-w", "-process_bitstream", "bin"], cwd=staging, check=True)
    binaries = list(staging.glob("*.bin"))
    if len(binaries) != 1:
        raise SystemExit(f"Expected one converted bitstream, found {binaries}")
    package = build / app_name
    package.mkdir(exist_ok=True)
    shutil.copyfile(binaries[0], package / f"{app_name}.bit.bin")
    overlay = staging / f"{app_name}.dts"
    overlay.write_text((source / "sysone-v2.dts").read_text().replace(
        "<100000000>", f"<{requested}>").replace("sysone-v2.bit.bin", f"{app_name}.bit.bin").replace(
        "xlnx,max-hidden = <384>", f"xlnx,max-hidden = <{1024 if args.frontier else 768 if args.wide else 384}>"), encoding="utf-8")
    subprocess.run([dtc, "-@", "-I", "dts", "-O", "dtb", "-o",
                    str(package / f"{app_name}.dtbo"), str(overlay)], check=True)
    shutil.copyfile(source / "shell.json", package / "shell.json")
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
              for path in package.iterdir() if path.name in
              {f"{app_name}.bit.bin", f"{app_name}.dtbo", "shell.json"}}
    manifest = {"files_sha256": hashes, "bit_sha256": hashlib.sha256(bit.read_bytes()).hexdigest(),
                "xsa_sha256": hashlib.sha256(xsa.read_bytes()).hexdigest(),
                **profile, "app_name": app_name, "mac_input_registers": int(args.optimized),
                "exp_table_in_bram": int(args.bram),
                "max_hidden": 1024 if args.frontier else 768 if args.wide else 384,
                "pipelined_uram": int(args.memory),
                "activation_read_latency": 5 if capture else 4 if args.memory else 3,
                "register_base": "0xa0000000",
                "timing_sha256": hashlib.sha256(timing_path.read_bytes()).hexdigest(),
                "timing_report": timing_path.name,
                "memory_base": "0x60000000", "memory_bytes": 64 << 20,
                "memory_allocation": "discover dedicated boot reservation; memory_base/bytes are legacy defaults",
                "note": "Check live clock, reserved memory and SYS2 ID before loading an image"}
    if checks is not None:
        manifest["rtl_sha256"] = checks["rtl_sha256"]
        manifest["regression_sha256"] = hashlib.sha256(
            regression_path.read_bytes()).hexdigest()
    if args.frontier:
        manifest.update({flag: 1 for flag in ("stream_results", "local_query_registers", "perf_counters",
                                            "local_accumulator_controls", "pipelined_dot", "registered_requests")})
        manifest["local_accumulator_controls"] = expected_profile["local_accumulator_controls"]
        if capture:
            manifest["local_read_capture"] = 1
        if fifo_flags:
            manifest["registered_fifo_flags"] = 1
        if pipeline_cuts:
            manifest.update(probability_pipeline=1,pipelined_drain_select=1,capability_word="0x535907ff")
        if operand_capture:
            manifest.update(probability_input_capture=1,local_embed_controls=1,capability_word="0x53591fff")
        if source_row_bram:
            manifest.update(incremental_source_row=1,linear_accumulators_in_bram=1,capability_word="0x53597fff")
        if attention_distance:
            manifest.update(attention_lanes=16,fabric_score_distance=1,capability_word="0x535affff")
            for key in ("numerical_cases","query_group_cases","partial_tile_cases","nexys_default_cycles_unchanged",
                        "query_group_vectors_sha256","encoder_cycle_change_vs_32query_range_percent","cycle_comparison_scope"):
                manifest[key]=checks[key]
        if paired:
            manifest.update(cached_request_window=1,dsp_embed_row_address=1,capability_word="0x5363ffff",component_proofs_sha256=checks["component_proofs_sha256"])
        if context_capture:
            manifest.update(fabric_context_capture=1,capability_word="0x5377ffff")
        manifest["hardware_qualified"] = False
    (package / "build.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    archive = build.parent / ("kr260-app-pipe.tar.gz" if args.optimized else "kr260-app.tar.gz")
    if args.bram:
        archive = build.parent / "kr260-app-bram.tar.gz"
    if args.wide:
        archive = build.parent / "kr260-app-wide.tar.gz"
    if args.memory:
        archive = build.parent / "kr260-app-memory.tar.gz"
    if args.frontier:
        archive = build.parent / ("kr260-app-attention-context-capture-large.tar.gz" if context_capture else "kr260-app-request-window-embed-large.tar.gz" if paired else "kr260-app-attention16-distance-large.tar.gz" if attention_distance else "kr260-app-source-row-bram-large.tar.gz" if source_row_bram else "kr260-app-operand-capture-large.tar.gz" if operand_capture else "kr260-app-pipeline-cuts-large.tar.gz" if pipeline_cuts else "kr260-app-capture-flags-large.tar.gz" if fifo_flags else "kr260-app-capture-large.tar.gz" if capture else
                                   "kr260-app-frontier-dot7-large.tar.gz" if args.frontier_candidate == "dot7-large"
                                   else "kr260-app-frontier.tar.gz")
    with tarfile.open(archive, "w:gz") as bundle:
        for name in (*sorted(hashes), "build.json"):
            bundle.add(package / name, arcname=f"{app_name}/{name}")
        bundle.add(source / "deploy_app.py", arcname="deploy_app.py")
        if args.optimized:
            bundle.add(repo / "src/sysone/v2/kr260_runtime.py", arcname="kr260_runtime.py")
            bundle.add(repo / "src/sysone/v2/kr260_link.py", arcname="kr260_link.py")
            bundle.add(source / "validate_pipeline.sh", arcname="validate_pipeline.sh")
            if args.memory:
                if args.frontier:
                    bundle.add(source / "deploy_frontier.sh", arcname="deploy_frontier.sh")
                    bundle.add(source / "validate_h1024.py", arcname="validate_h1024.py")
                    bundle.add(repo / "scripts/v2/sysone_v2_client.py", arcname="sysone_v2_client.py")
                    bundle.add(repo / "src/sysone/v2/timing_policy.py", arcname="timing_policy.py")
                    if not capture:
                        vectors = base_regression.parent / "boundary-vectors"
                        vector_manifest = json.loads((vectors / "manifest.json").read_text())
                        if vector_manifest != json.loads(base_regression.read_text())["boundary_reference"]:
                            raise SystemExit("H1024 fixture differs from the frozen regression reference")
                    binary = b"".join(int(line, 16).to_bytes(16, "little")
                                      for line in (vectors / "image.hex").read_text().splitlines())
                    if len(binary) != vector_manifest["bytes"] or hashlib.sha256(binary).hexdigest() != vector_manifest["sha256"]:
                        raise SystemExit("Synthetic H1024 validation image hash differs")
                    validation = build / "h1024-vectors"
                    validation.mkdir(exist_ok=True)
                    (validation / "image.bin").write_bytes(binary)
                    shutil.copyfile(vectors / "manifest.json", validation / "manifest.json")
                    for index in range(len(vector_manifest["token_lengths"])):
                        shutil.copyfile(vectors / f"case_{index}.txt", validation / f"case_{index}.txt")
                    for path in sorted(validation.iterdir()):
                        bundle.add(path, arcname=f"h1024-vectors/{path.name}")
                    if attention_distance:
                        query_vectors=repo/'build/v2/attention16-head32-vectors'
                        query_manifest=json.loads((query_vectors/'manifest.json').read_text())
                        query_binary=b''.join(int(line,16).to_bytes(16,'little')
                                              for line in (query_vectors/'image.hex').read_text().splitlines())
                        if len(query_binary)!=query_manifest['bytes'] or hashlib.sha256(query_binary).hexdigest()!=query_manifest['sha256']:
                            raise SystemExit('Query-group validation image hash differs')
                        query_validation=build/'query-group-vectors'
                        query_validation.mkdir(exist_ok=True)
                        (query_validation/'image.bin').write_bytes(query_binary)
                        for name in ['manifest.json',*(f'case_{i}.txt' for i in range(4))]:
                            shutil.copyfile(query_vectors/name,query_validation/name)
                        for path in sorted(query_validation.iterdir()):
                            bundle.add(path,arcname=f'query-group-vectors/{path.name}')
                else:
                    bundle.add(source / "deploy_memory.sh", arcname="deploy_memory.sh")
    print(json.dumps({"package": str(package), "archive": str(archive), **manifest}, indent=2))


if __name__ == "__main__":
    main()
