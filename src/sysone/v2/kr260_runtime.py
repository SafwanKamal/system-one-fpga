"""Read-only Linux preflight; never probe an unconfirmed PL register address."""
from __future__ import annotations

import json
import math
from pathlib import Path
import struct


def discover_memory(root: Path = Path("/")) -> tuple[int, int]:
    """Read the actual dedicated Linux reservation, without opening /dev/mem."""
    parent = root / "sys/firmware/devicetree/base/reserved-memory"
    nodes = list(parent.glob("sysone@*"))
    if len(nodes) != 1 or not (nodes[0] / "no-map").exists():
        raise IOError("KR260 preflight: one dedicated no-map DDR reservation is required")
    raw = (nodes[0] / "reg").read_bytes()
    if len(raw) != 16:
        raise IOError("KR260 preflight: invalid reserved DDR encoding")
    base, size = struct.unpack(">QQ", raw)
    if (base % 4096 or size <= 0 or size % 4096 or base + size > 0x80000000
            or nodes[0].name != f"sysone@{base:x}"):
        raise IOError("KR260 preflight: reservation must fit the mapped low-DDR window")
    if f"{base:08x}-{base + size - 1:08x} : reserved" not in (root / "proc/iomem").read_text():
        raise IOError("KR260 preflight: kernel iomem does not confirm reserved DDR")
    return base, size


def _bound(node: Path, driver: str, root: Path) -> bool:
    devices = root / "sys/bus/platform/devices"
    if not devices.is_dir():
        return False
    for device in devices.iterdir():
        of_node, binding = device / "of_node", device / "driver"
        if of_node.exists() and of_node.resolve() == node.resolve():
            return binding.exists() and binding.resolve().name == driver
    return False


def check_runtime(registers: int, memory: tuple[int, int], root: Path = Path("/")) -> dict:
    """Confirm overlay, driver binding, clock and boot reservation before /dev/mem."""
    def require(condition, message):
        if not condition:
            raise IOError(f"KR260 preflight: {message}")
    try:
        dt = root / "sys/firmware/devicetree/base"
        require((dt / "model").read_bytes().rstrip(b"\0") == b"ZynqMP KR260 revB",
                "requires the verified KR260 revB Linux environment")
        amba = (dt / "__symbols__/amba").read_bytes().rstrip(b"\0").decode()
        bus = dt / amba.lstrip("/")
        encoder = bus / f"encoder@{registers:x}"
        require(encoder.is_dir(),
                "sysone-v2 overlay is absent; reload the FPGA app after reboot, before any encoder command")
        require(b"xlnx,kr260-encoder-wrapper-1.0" in (encoder / "compatible").read_bytes().split(b"\0"),
                "unexpected encoder device-tree node")
        require((encoder / "reg").read_bytes() == struct.pack(">IIII", 0, registers, 0, 4096),
                "encoder register mapping differs")
        firmware = (dt / "fpga-region/firmware-name").read_bytes().rstrip(b"\0")
        apps = {b"sysone-v2.bit.bin": "sysone-v2", b"sysone-v2-pipe.bit.bin": "sysone-v2-pipe",
                b"sysone-v2-bram.bit.bin": "sysone-v2-bram",
                b"sysone-v2-wide.bit.bin": "sysone-v2-wide",
                b"sysone-v2-memory.bit.bin": "sysone-v2-memory",
                b"sysone-v2-frontier.bit.bin": "sysone-v2-frontier",
                b"sysone-v2-capture.bit.bin": "sysone-v2-capture",
                b"sysone-v2-capture-flags.bit.bin": "sysone-v2-capture-flags",
                b"sysone-v2-pipeline-cuts.bit.bin": "sysone-v2-pipeline-cuts",
                b"sysone-v2-operand-capture.bit.bin": "sysone-v2-operand-capture",
                b"sysone-v2-source-row-bram.bit.bin": "sysone-v2-source-row-bram",
                b"sysone-v2-attention16-distance.bit.bin": "sysone-v2-attention16-distance",
                b"sysone-v2-request-window-embed.bit.bin": "sysone-v2-request-window-embed",
                b"sysone-v2-attention-context-capture.bit.bin": "sysone-v2-attention-context-capture"}
        require(firmware in apps, "FPGA region does not describe a supported sysone-v2 app")
        app_name = apps[firmware]
        state = (root / "sys/class/fpga_manager/fpga0/state").read_text().strip()
        require(state == "operating", f"FPGA manager is {state}")
        require(_bound(bus / "sysone-clocking0", "xilinx_fclk", root), "PL0 clock driver is not bound")
        require(_bound(bus / "sysone-afi", "afi-fpga", root), "AXI port configuration driver is not bound")
        summary = (root / "sys/kernel/debug/clk/clk_summary").read_text()
        clocks = [line.split() for line in summary.splitlines()
                  if line.split() and line.split()[0] == "pl0_ref"]
        require(len(clocks) == 1 and len(clocks[0]) >= 5, "cannot confirm PL0 clock")
        clock = clocks[0]
        require(int(clock[1]) > 0 and int(clock[2]) > 0, "PL0 clock is not enabled/prepared")
        profile = json.loads((root / f"lib/firmware/xilinx/{app_name}/build.json").read_text())
        require(profile.get("app_name", "sysone-v2") == app_name, "app manifest does not match loaded firmware")
        requested, ceiling = profile["clock_requested_hz"], profile["clock_timing_max_hz"]
        pipeline = app_name != "sysone-v2"
        frontier = app_name in {"sysone-v2-frontier", "sysone-v2-capture", "sysone-v2-capture-flags", "sysone-v2-pipeline-cuts", "sysone-v2-operand-capture", "sysone-v2-source-row-bram", "sysone-v2-attention16-distance", "sysone-v2-request-window-embed", "sysone-v2-attention-context-capture"}
        require(not pipeline or profile.get("mac_input_registers") == 1, "missing pipeline app profile")
        require(app_name not in {"sysone-v2-bram", "sysone-v2-wide", "sysone-v2-memory"} or profile.get("exp_table_in_bram") == 1,
                "missing BRAM app profile")
        require(app_name not in {"sysone-v2-wide", "sysone-v2-memory"} or profile.get("max_hidden") == 768,
                "missing 768-wide app profile")
        require(app_name != "sysone-v2-memory" or
                (profile.get("pipelined_uram") == 1 and profile.get("activation_read_latency") == 4),
                "missing pipelined UltraRAM app profile")
        if frontier:
            candidate=profile.get("candidate")
            controls=3 if candidate in ("dot7-large","capture-large","capture-flags-large","pipeline-cuts-large","operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large") else 1
            capture = candidate in ("capture-large","capture-flags-large","pipeline-cuts-large","operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large")
            context_capture = candidate == "attention-context-capture-large"
            paired = candidate in ("request-window-embed-large","attention-context-capture-large")
            attention_distance = candidate in ("attention16-distance-large","request-window-embed-large","attention-context-capture-large")
            source_row_bram = candidate in ("source-row-bram-large", "attention16-distance-large","request-window-embed-large","attention-context-capture-large")
            operand_capture = candidate in ("operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large")
            pipeline_cuts = candidate in ("pipeline-cuts-large","operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large")
            fifo_flags = candidate in ("capture-flags-large","pipeline-cuts-large","operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large")
            require(candidate in (None,"dot5-large","dot7-large","capture-large","capture-flags-large","pipeline-cuts-large","operand-capture-large","source-row-bram-large","attention16-distance-large","request-window-embed-large","attention-context-capture-large"), "unknown frontier candidate")
            require(app_name == ("sysone-v2-attention-context-capture" if context_capture else "sysone-v2-request-window-embed" if paired else "sysone-v2-attention16-distance" if attention_distance else "sysone-v2-source-row-bram" if source_row_bram else "sysone-v2-operand-capture" if operand_capture else "sysone-v2-pipeline-cuts" if pipeline_cuts else "sysone-v2-capture-flags" if fifo_flags else "sysone-v2-capture" if capture else "sysone-v2-frontier"), "Capture candidate/app mismatch")
            require(profile.get("max_hidden") == 1024 and profile.get("exp_table_in_bram") == 1
                    and profile.get("pipelined_uram") == 1 and profile.get("activation_read_latency") == (5 if capture else 4)
                    and profile.get("local_read_capture", 0) == int(capture)
                    and profile.get("registered_fifo_flags", 0) == int(fifo_flags)
                and profile.get("probability_pipeline", 0) == int(pipeline_cuts)
                and profile.get("pipelined_drain_select", 0) == int(pipeline_cuts)
                and profile.get("probability_input_capture", 0) == int(operand_capture)
                and profile.get("local_embed_controls", 0) == int(operand_capture)
                and profile.get("incremental_source_row", 0) == int(source_row_bram)
                and profile.get("linear_accumulators_in_bram", 0) == int(source_row_bram)
                and (not operand_capture or profile.get("capability_word") == ("0x5377ffff" if context_capture else "0x5363ffff" if paired else "0x535affff" if attention_distance else "0x53597fff" if source_row_bram else "0x53591fff"))
                    and profile.get("local_accumulator_controls") == controls
                    and all(profile.get(flag) == 1 for flag in (
                        "stream_results", "local_query_registers", "perf_counters",
                        "pipelined_dot", "registered_requests")),
                    "missing H1024 frontier profile")
            require(profile.get("cached_request_window",0)==int(paired)
                    and profile.get("dsp_embed_row_address",0)==int(paired)
                    and profile.get("fabric_context_capture",0)==int(context_capture)
                    and (not paired or (len(profile.get("rtl_sha256",{}))==23 and requested==ceiling==200000000)),
                    "paired window/DSP address profile mismatch")
            require(profile.get("attention_lanes", 32) == (16 if attention_distance else 32)
                    and profile.get("fabric_score_distance", 0) == int(attention_distance),
                    "attention width/distance profile mismatch")
            if attention_distance:
                cost = profile.get("encoder_cycle_change_vs_32query_range_percent")
                require(profile.get("numerical_cases") == 32 and profile.get("query_group_cases") == 4
                        and profile.get("partial_tile_cases") == 6
                        and profile.get("nexys_default_cycles_unchanged") is True
                        and isinstance(cost, list) and len(cost) == 2
                        and all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in cost)
                        and cost[0] <= cost[1], "missing attention scheduling/numerical evidence")
            require(profile.get("timing_qualified") is True
                    and all(type(profile.get(key)) in (int,float) and math.isfinite(profile[key]) and profile[key]>0
                            for key in ("routed_setup_slack_ns","routed_hold_slack_ns")),
                    "frontier app lacks passing routed timing evidence")
        require(0 < requested <= ceiling <= (300000000 if frontier else 125000000 if pipeline else 100000000), "invalid app clock profile")
        hz = int(clock[4])
        require(requested * 0.95 <= hz <= ceiling, f"live clock {hz} is outside the validated range")
        if frontier:
            require(_bound(bus / "sysone-clocking1", "xilinx_fclk", root), "PL1 clock driver is not bound")
            clock1 = [line.split() for line in summary.splitlines()
                      if line.split() and line.split()[0] == "pl1_ref"]
            require(len(clock1) == 1 and len(clock1[0]) >= 5
                    and int(clock1[0][1]) > 0 and int(clock1[0][2]) > 0
                    and requested * 0.95 <= int(clock1[0][4]) <= ceiling,
                    "PL1 clock is outside the validated range")
        base, size = memory
        reserved_base, reserved_size = discover_memory(root)
        require(base >= reserved_base and size > 0 and base + size <= reserved_base + reserved_size,
                "requested memory exceeds the boot-time no-map DDR reservation")
        return {"clock_hz": hz, "clock_requested_hz": requested, "clock_timing_max_hz": ceiling,
                "memory_base": reserved_base, "memory_bytes": reserved_size,
                **({"expected_build": 0x20804004,
                    "expected_capabilities": 0x5377ffff if context_capture else 0x5363ffff if paired else 0x535affff if attention_distance else 0x53597fff if source_row_bram else 0x53591fff if operand_capture else
                        0x535907ff if pipeline_cuts else 0x535901ff if fifo_flags else
                        0x5359017f if capture else 0x5359013f} if frontier else {})}
    except (OSError, ValueError, KeyError, IndexError) as error:
        if str(error).startswith("KR260 preflight:"):
            raise
        raise IOError(f"KR260 preflight cannot confirm Linux runtime: {error}; no MMIO performed") from error
