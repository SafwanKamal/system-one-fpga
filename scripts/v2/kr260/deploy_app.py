"""Verify and load the packaged encoder on Ubuntu KR260; no image writes."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import mmap
import os
from pathlib import Path
import shutil
import struct
import subprocess


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def bound(node: Path, driver: str) -> bool:
    for device in Path("/sys/bus/platform/devices").iterdir():
        of_node, binding = device / "of_node", device / "driver"
        if of_node.exists() and of_node.resolve() == node.resolve():
            return binding.exists() and binding.resolve().name == driver
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="unpacked sysone-v2 directory")
    args = parser.parse_args()
    require(os.geteuid() == 0, "Run with sudo on the KR260")
    dt = Path("/sys/firmware/devicetree/base")
    require((dt / "model").read_bytes().rstrip(b"\0") == b"ZynqMP KR260 revB", "Requires KR260 revB")
    regions = list((dt / "reserved-memory").glob("sysone@*"))
    require(len(regions) == 1 and (regions[0] / "no-map").exists(),
            "Dedicated no-map boot reservation is required")
    region = regions[0]
    raw = (region / "reg").read_bytes()
    require(len(raw) == 16, "Invalid reserved-memory encoding")
    memory_base, memory_bytes = struct.unpack(">QQ", raw)
    require(memory_base % 4096 == 0 and memory_bytes > 0 and memory_bytes % 4096 == 0
            and memory_base + memory_bytes <= 0x80000000 and region.name == f"sysone@{memory_base:x}",
            "Reservation must fit the mapped low-DDR window")
    require(f"{memory_base:08x}-{memory_base + memory_bytes - 1:08x} : reserved" in Path("/proc/iomem").read_text(),
            "Kernel iomem does not confirm the reservation")
    xmutil = shutil.which("xmutil")
    require(xmutil is not None, "xmutil is required")
    manifest = json.loads((args.package / "build.json").read_text())
    app_name = manifest.get("app_name", "sysone-v2")
    require(app_name in {"sysone-v2", "sysone-v2-pipe", "sysone-v2-bram", "sysone-v2-wide", "sysone-v2-memory", "sysone-v2-frontier", "sysone-v2-capture", "sysone-v2-capture-flags", "sysone-v2-pipeline-cuts", "sysone-v2-operand-capture", "sysone-v2-source-row-bram", "sysone-v2-attention16-distance", "sysone-v2-request-window-embed", "sysone-v2-attention-context-capture"}, "Unexpected FPGA app name")
    expected = {f"{app_name}.bit.bin", f"{app_name}.dtbo", "shell.json"}
    hashes = manifest["files_sha256"]
    require(set(hashes) == expected, "Unexpected package files")
    for name, digest in hashes.items():
        require(hashlib.sha256((args.package / name).read_bytes()).hexdigest() == digest,
                f"Package hash mismatch: {name}")
    requested = manifest["clock_requested_hz"]
    ceiling = manifest["clock_timing_max_hz"]
    pipeline = app_name != "sysone-v2"
    frontier = app_name in {"sysone-v2-frontier", "sysone-v2-capture", "sysone-v2-capture-flags", "sysone-v2-pipeline-cuts", "sysone-v2-operand-capture", "sysone-v2-source-row-bram", "sysone-v2-attention16-distance", "sysone-v2-request-window-embed", "sysone-v2-attention-context-capture"}
    require(not pipeline or manifest.get("mac_input_registers") == 1, "Missing pipeline profile")
    require(app_name not in {"sysone-v2-bram", "sysone-v2-wide", "sysone-v2-memory"} or manifest.get("exp_table_in_bram") == 1, "Missing BRAM profile")
    require(app_name not in {"sysone-v2-wide", "sysone-v2-memory"} or manifest.get("max_hidden") == 768, "Missing 768-wide profile")
    require(app_name != "sysone-v2-memory" or
            (manifest.get("pipelined_uram") == 1 and manifest.get("activation_read_latency") == 4),
            "Missing pipelined UltraRAM profile")
    if frontier:
        candidate=manifest.get("candidate")
        controls=3 if candidate in ("dot7-large","capture-large","capture-flags-large","pipeline-cuts-large","operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large") else 1
        capture = candidate in ("capture-large","capture-flags-large","pipeline-cuts-large","operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large")
        context_capture = candidate == "attention-context-capture-large"
        paired = candidate in ("request-window-embed-large","attention-context-capture-large")
        attention_distance = candidate in ("attention16-distance-large","request-window-embed-large","attention-context-capture-large")
        source_row_bram = candidate in ("source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large")
        operand_capture = candidate in ("operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large")
        pipeline_cuts = candidate in ("pipeline-cuts-large","operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large")
        fifo_flags = candidate in ("capture-flags-large","pipeline-cuts-large","operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large")
        require(candidate in (None,"dot5-large","dot7-large","capture-large","capture-flags-large","pipeline-cuts-large","operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large"), "Unknown frontier candidate")
        require(app_name == ("sysone-v2-attention-context-capture" if context_capture else "sysone-v2-request-window-embed" if paired else "sysone-v2-attention16-distance" if attention_distance else "sysone-v2-source-row-bram" if source_row_bram else "sysone-v2-operand-capture" if operand_capture else "sysone-v2-pipeline-cuts" if pipeline_cuts else "sysone-v2-capture-flags" if fifo_flags else "sysone-v2-capture" if capture else "sysone-v2-frontier"), "Capture candidate/app mismatch")
        require(manifest.get("max_hidden") == 1024 and manifest.get("exp_table_in_bram") == 1
                and manifest.get("pipelined_uram") == 1 and manifest.get("activation_read_latency") == (5 if capture else 4)
                and manifest.get("local_read_capture", 0) == int(capture)
                and manifest.get("registered_fifo_flags", 0) == int(fifo_flags)
                and manifest.get("probability_pipeline", 0) == int(pipeline_cuts)
                and manifest.get("pipelined_drain_select", 0) == int(pipeline_cuts)
                and manifest.get("probability_input_capture", 0) == int(operand_capture)
                and manifest.get("local_embed_controls", 0) == int(operand_capture)
                and manifest.get("incremental_source_row", 0) == int(source_row_bram)
                and manifest.get("linear_accumulators_in_bram", 0) == int(source_row_bram)
                and (not operand_capture or manifest.get("capability_word") == ("0x5377ffff" if context_capture else "0x5363ffff" if paired else "0x535affff" if attention_distance else "0x53597fff" if source_row_bram else "0x53591fff"))
                and manifest.get("local_accumulator_controls") == controls
                and all(manifest.get(flag) == 1 for flag in (
                    "stream_results", "local_query_registers", "perf_counters",
                    "pipelined_dot", "registered_requests")),
                "Missing H1024 frontier profile")
        require(manifest.get("cached_request_window",0)==int(paired)
                and manifest.get("dsp_embed_row_address",0)==int(paired)
                and manifest.get("fabric_context_capture",0)==int(context_capture)
                and (not paired or (len(manifest.get("rtl_sha256",{}))==23 and requested==ceiling==200000000)),
                "paired window/DSP address profile mismatch")
        require(manifest.get("attention_lanes",32)==(16 if attention_distance else 32)
                and manifest.get("fabric_score_distance",0)==int(attention_distance),
                "Attention width/distance profile mismatch")
        if attention_distance:
            cost=manifest.get("encoder_cycle_change_vs_32query_range_percent")
            require(manifest.get("numerical_cases")==32 and manifest.get("query_group_cases")==4
                    and manifest.get("partial_tile_cases")==6
                    and manifest.get("nexys_default_cycles_unchanged") is True
                    and isinstance(cost,list) and len(cost)==2
                    and all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in cost)
                    and cost[0]<=cost[1], "Missing attention numerical/scheduling profile")
        require(manifest.get("timing_qualified") is True
                and all(type(manifest.get(key)) in (int,float) and math.isfinite(manifest[key]) and manifest[key]>0
                        for key in ("routed_setup_slack_ns","routed_hold_slack_ns")),
                "Frontier app lacks passing routed timing evidence")
    require(0 < requested <= ceiling <= (300000000 if frontier else 125000000 if pipeline else 100000000), "Invalid clock timing ceiling")
    target = Path(f"/lib/firmware/xilinx/{app_name}")
    if target.exists():
        require(all((target / name).is_file() and
                    hashlib.sha256((target / name).read_bytes()).hexdigest() == hashes[name]
                    for name in expected), f"Existing {app_name} app differs; preserve it before replacing")
    else:
        target.mkdir()
        for name in expected | {"build.json"}:
            shutil.copyfile(args.package / name, target / name)
    subprocess.run([xmutil, "listapps"], check=True)
    subprocess.run([xmutil, "unloadapp"], check=True)
    subprocess.run([xmutil, "loadapp", app_name], check=True)
    subprocess.run([xmutil, "listapps"], check=True)
    state = Path("/sys/class/fpga_manager/fpga0/state").read_text().strip()
    require(state == "operating", f"FPGA manager state: {state}")
    # The live amba label supplies the parent path, which differs across BSPs.
    amba = (dt / "__symbols__/amba").read_bytes().rstrip(b"\0").decode()
    bus = dt / amba.lstrip("/")
    require(bound(bus / "sysone-clocking0", "xilinx_fclk"), "PL0 fabric-clock driver did not bind")
    require(bound(bus / "sysone-afi", "afi-fpga"), "AXI port configuration driver did not bind")
    summary = Path("/sys/kernel/debug/clk/clk_summary").read_text()
    lines = [line.split() for line in summary.splitlines() if line.split() and line.split()[0] == "pl0_ref"]
    require(len(lines) == 1, "Cannot confirm live PL0 clock")
    clock = int(lines[0][4])
    require(int(lines[0][1]) > 0 and int(lines[0][2]) > 0, "PL0 clock is not enabled/prepared")
    require(requested * 0.95 <= clock <= ceiling,
            f"PL0 clock {clock} is outside the requested/validated range")
    if frontier:
        require(bound(bus / "sysone-clocking1", "xilinx_fclk"), "PL1 fabric-clock driver did not bind")
        clock1 = [line.split() for line in summary.splitlines()
                  if line.split() and line.split()[0] == "pl1_ref"]
        require(len(clock1) == 1 and len(clock1[0]) >= 5
                and int(clock1[0][1]) > 0 and int(clock1[0][2]) > 0
                and requested * 0.95 <= int(clock1[0][4]) <= ceiling,
                "PL1 clock is outside the requested/validated range")
    # Probe only after programming, clock and AFI configuration have succeeded.
    fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
    try:
        with mmap.mmap(fd, mmap.PAGESIZE, mmap.MAP_SHARED,
                       mmap.PROT_READ, offset=0xA0000000) as regs:
            ident, build = struct.unpack_from("<II", regs, 0x14)
            features = struct.unpack_from("<I", regs, 0x1C)[0] if frontier else None
    finally:
        os.close(fd)
    require(ident == 0x53595332, f"Encoder ID mismatch: {ident:#x}")
    expected_build = 0x20804004 if frontier else 0x20803004 if app_name in {"sysone-v2-wide", "sysone-v2-memory"} else 0x20801804
    require(build == expected_build, f"Encoder BUILD mismatch: {build:#x}")
    require(not frontier or features == (0x5377FFFF if context_capture else 0x5363FFFF if paired else 0x535AFFFF if attention_distance else 0x53597FFF if source_row_bram else 0x53591FFF if operand_capture else 0x535907FF if pipeline_cuts else 0x535901FF if fifo_flags else 0x5359017F if capture else 0x5359013F), "Frontier feature register mismatch")
    print(json.dumps({"id": hex(ident), "build": hex(build), "clock_hz": clock,
                      **({"features": hex(features), "clock1_hz": int(clock1[0][4])} if frontier else {}),
                      "reserved_base": hex(memory_base), "reserved_bytes": memory_bytes,
                      "image_written": False}, indent=2))


if __name__ == "__main__":
    main()
