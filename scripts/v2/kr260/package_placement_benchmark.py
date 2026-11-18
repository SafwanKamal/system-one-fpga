"""Bundle a fixed optimized checkpoint for another laptop; no Vivado job launched."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parent


def main():
    checkpoint = ROOT / "build/v2/kr260-opt-memory/sysone_v2_kr260.runs/impl_1/system_wrapper_opt.dcp"
    if not checkpoint.is_file():
        raise SystemExit("Completed UltraRAM candidate checkpoint required")
    archive = ROOT / "build/v2/kr260-placement-benchmark.zip"
    manifest = {"checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                "candidate": "kr260-opt-memory", "vivado_version": "2025.2",
                "baseline_8845hs_placement_seconds": 1310,
                "baseline_threads": 4,
                "note": "Fixed optimized netlist. Placement runtime comparison does not establish full-route speedup."}
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(checkpoint, "system_wrapper_opt.dcp")
        for name in ("benchmark_placement.ps1", "benchmark_placement.tcl"):
            bundle.write(SOURCE / name, name)
        bundle.writestr("benchmark-manifest.json", json.dumps(manifest, indent=2) + "\n")
        bundle.writestr("README.txt", "Extract to a short local path, such as C:\\fpga-bench.\n"
                         "Requires Vivado 2025.2 with K26 support; board files are unnecessary.\n"
                         "Use AC power and a consistent performance mode.\n"
                         "Run: powershell -ExecutionPolicy Bypass -File .\\benchmark_placement.ps1\n"
                         "First compare four threads; optionally rerun with -Threads 8.\n"
                         "8845HS baseline placement: 1310 seconds at four threads.\n"
                         "No routing, bitstream generation or board access occurs.\n"
                         "Return machine.json and placement-result.json from the result directory.\n")
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        assert hashlib.sha256(bundle.read("system_wrapper_opt.dcp")).hexdigest() == manifest["checkpoint_sha256"]
    print(f"Verified benchmark: {archive} ({archive.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
