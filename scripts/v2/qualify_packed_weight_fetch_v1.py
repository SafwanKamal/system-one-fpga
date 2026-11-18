"""Offline packed row fetch + existing AXI port integration, with Python goldens."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from sysone.v2.functiongemma_packed_weights import PackedWeights, pack_codes


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    compiler, runtime = shutil.which("iverilog"), shutil.which("vvp")
    if not compiler or not runtime:
        raise RuntimeError("Icarus required")
    common = [ROOT / name for name in [
        "rtl/v2/common/packed_weight_fetch16_v1.sv",
        "rtl/v2/common/packed_weight_row16.sv",
        "rtl/v2/platform/kr260/axi_memory_port.sv",
        "rtl/v2/common/sync_fifo.sv",
        "rtl/v2/common/sync_fifo_registered_flags.sv",
        "rtl/v2/common/signed_int8_dot16_v1.sv",
        "rtl/v2/common/packed_weight_fetch_dot16_v1.sv",
    ]]
    benches = [ROOT / f"rtl/v2/test/packed_weight_fetch16_{mode}_v1_tb.sv" for mode in ("axi", "fault")]
    dot_bench=ROOT / "rtl/v2/test/signed_int8_dot16_v1_tb.sv"
    sources = [Path(__file__).resolve(), *common, *benches, dot_bench,
               ROOT / "src/sysone/v2/functiongemma_packed_weights.py"]
    # Icarus rejects an enum-valued ternary in the unchanged write path. Use
    # equivalent if/else only in a recorded simulation copy, with an exact
    # single replacement guard. Synthesizers use the original source.
    original_memory = common[2].read_text(encoding="utf-8")
    old = "write_state_next = (write_left_reg == 1) ? WRITE_RESPONSES : WRITE_ADDRESS;"
    new = "if (write_left_reg == 1) write_state_next = WRITE_RESPONSES; else write_state_next = WRITE_ADDRESS;"
    if original_memory.count(old) != 1:
        raise ValueError("memory port Icarus compatibility source changed")
    simulation_memory = args.out / "axi_memory_port_icarus.sv"
    simulation_memory.write_text(original_memory.replace(old, new), encoding="utf-8")
    simulation_sources = common.copy()
    simulation_sources[2] = simulation_memory
    checks = []
    for bits in (6, 7, 8):
        rng = np.random.default_rng(18492 + bits)
        limit = 1 << (bits - 1)
        row_bytes = bits * 2
        records = []
        for code_value in (-limit,limit-1,0):
            for activation_value in (-128,127):
                codes=np.full(16,code_value,dtype=np.int16)
                records.append((0x7000,pack_codes(codes,bits),codes))
        # Every offset, including one/two-beat edges and crossing 4 KiB. Cover
        # address zero, upper address bits, largest valid 32-byte beat extent.
        for base in (0, 0x120, 0xFF0, 0x1000, 0x800000FFF0, 0xFFFFFFFFE0):
            for offset in range(16):
                codes = rng.integers(-limit, limit, size=16, dtype=np.int16)
                codes[:4] = [-limit, -1, 0, limit-1]
                records.append((base+offset, pack_codes(codes, bits), codes))
        codes=np.full(16,-limit,dtype=np.int16)
        records.append(((1<<40)-row_bytes,pack_codes(codes,bits),codes))
        # Actual tile serialization, including padded columns, row31/32,
        # output tile and input tile transitions; byte-misaligned image bases.
        codes = rng.integers(-limit, limit, size=(37, 35), dtype=np.int16)
        matrix = PackedWeights.from_codes(codes, bits)
        for image_base in (0x20000, 0x20FF3, 0x8000000037):
            for nt in range(matrix.output_tiles):
                for kt in range(matrix.input_tiles):
                    for within in range(32):
                        start = (nt*matrix.input_tiles+kt)*matrix.tile_bytes+within*row_bytes
                        row, col = nt*32+within, kt*16
                        expected = np.zeros(16, dtype=np.int16)
                        if row < matrix.rows:
                            size = max(0, min(16, matrix.columns-col))
                            expected[:size] = codes[row, col:col+size]
                        records.append((image_base+start, matrix.data[start:start+row_bytes], expected))
        for _ in range(512):
            codes = rng.integers(-limit, limit, size=16, dtype=np.int16)
            address = int(rng.integers(0, 1 << 39))
            records.append((address, pack_codes(codes, bits), codes))
        vectors = args.out / f"fetch-{bits}.hex"
        with vectors.open("w", encoding="ascii") as stream:
            for record_index,(address, packed, codes) in enumerate(records):
                memory = bytearray(rng.bytes(32))
                offset = address % 16
                memory[offset:offset+row_bytes] = packed
                expected = int.from_bytes(codes.astype(np.int8).tobytes(), "little")
                activation = rng.integers(-128,128,size=16,dtype=np.int16)
                if record_index<6: activation[:]=(-128 if record_index%2==0 else 127)
                elif record_index%8==0: activation[:]= -128
                elif record_index%8==1: activation[:]=127
                elif record_index%8==2: activation[:]=0
                total=int(activation.astype(np.int64) @ codes.astype(np.int64)) & ((1<<20)-1)
                act=int.from_bytes(activation.astype(np.int8).tobytes(),"little")
                stream.write(f"{act:032x}{total:05x}{expected:032x}{int.from_bytes(memory,'little'):064x}{address:010x}\n")
        for mode, bench in (("axi",benches[0]),("dot",benches[0]),("fault",benches[1]),
                            ("dotfault",benches[1]),("dotstream",dot_bench)):
            top = ("signed_int8_dot16_v1_tb" if mode=="dotstream" else
                   f"packed_weight_fetch16_{'axi' if mode=='dot' else 'fault' if mode=='dotfault' else mode}_v1_tb")
            executable = args.out / f"{mode}-{bits}.vvp"
            command = [compiler, "-g2012", "-s", top, f"-P{top}.BITS={bits}",
                       "-o", str(executable), *map(str, simulation_sources), str(bench)]
            if mode in ("dot","dotfault"): command.insert(5,f"-P{top}.WITH_DOT=1")
            compile_run = subprocess.run(command, capture_output=True, text=True)
            log = compile_run.stdout + compile_run.stderr
            if compile_run.returncode:
                (args.out / f"{mode}-{bits}.log").write_text(log, encoding="utf-8")
                raise RuntimeError(log)
            simulation = subprocess.run([runtime, str(executable), f"+vectors={vectors.resolve()}",
                                         f"+count={len(records)}"], capture_output=True, text=True, timeout=90)
            log += simulation.stdout + simulation.stderr
            (args.out / f"{mode}-{bits}.log").write_text(log, encoding="utf-8")
            if simulation.returncode or f"PASS bits={bits}" not in simulation.stdout:
                raise RuntimeError(log)
            checks.append(dict(bits=bits, mode=mode, rows=len(records) if mode not in ("fault","dotfault") else 0,
                               passed=True, output=simulation.stdout.strip(),
                               executable_sha256=sha(executable), vectors_sha256=sha(vectors)))
    result = dict(stage="complete", scope="offline RTL integration with real existing AXI memory port",
                  board_contacted=False, deployed_design_changed=False, quantization_quality_qualified=False,
                  synthesized=False, source_sha256={str(p.relative_to(ROOT)):sha(p) for p in sources},
                  simulator_compatibility=dict(source_sha256=sha(common[2]),
                      generated_sha256=sha(simulation_memory), old=old, new=new,
                      scope="equivalent enum if/else in unused write path; original unchanged"),
                  checks=checks, tools=dict(iverilog=compiler, vvp=runtime),
                  reset_contract="adapter and memory transaction domain reset together; no AXI cancellation",
                  remaining=["matrix accumulation and requantization", "whole model integer accuracy",
                             "R5/compiler ABI and checked image layout", "route/timing", "board qualification"])
    (args.out / "qualification.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(dict(stage="complete", checks=checks)))


if __name__ == "__main__":
    main()
