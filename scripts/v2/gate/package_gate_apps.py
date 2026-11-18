"""Package the gate bridge bitstreams as dfx-mgr apps plus board tools into one archive.

  python package_gate_apps.py --prod <dir with gate_kr260_top.bit> --loop <dir> --out build/v2/agent-gate-bridge/deploy
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BOOTGEN = "C:/AMDDesignTools/2025.2/Vivado/bin/bootgen.bat"

DTS = """/dts-v1/;
/plugin/;
// Agent-gate bridge ({variant}).  Full PL image; the PS reads a 4 KiB read-only status
// window at 0xA000_0000 through /dev/mem.  No PS clocks are used by the bridge (it runs
// from the 25 MHz HPA_CLK0P oscillator); only the AFI width driver is bound.
// AFI_FS (config-afi index 14) must say 32-bit for M_AXI_HPM0_FPD: the previous image
// (RC1 v9e) leaves it at 0xA00 (128-bit), which masks 3 of every 4 status words.
/ {{
    fragment@0 {{
        target = <&fpga_full>;
        __overlay__ {{
            firmware-name = "{app}.bit.bin";
            resets = <&zynqmp_reset 116>, <&zynqmp_reset 117>,
                     <&zynqmp_reset 118>, <&zynqmp_reset 119>;
        }};
    }};
    fragment@1 {{
        target = <&amba>;
        __overlay__ {{
            gate_afi: gate-afi {{
                compatible = "xlnx,afi-fpga";
                status = "okay";
                resets = <&zynqmp_reset 116>, <&zynqmp_reset 117>,
                         <&zynqmp_reset 118>, <&zynqmp_reset 119>;
                config-afi = <0 0>, <1 0>, <2 0>, <3 0>, <4 0>, <5 0>,
                             <6 0>, <7 0>, <8 0>, <9 0>, <10 0>, <11 0>,
                             <12 0>, <13 0>, <14 0x000>, <15 0>;
            }};
        }};
    }};
}};
"""


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prod", required=True)
    ap.add_argument("--loop", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    if out.exists():
        raise SystemExit(f"{out} exists; refusing to overwrite")
    out.mkdir(parents=True)
    manifest, builds = {}, {}
    for variant, d in (("prod", Path(args.prod)), ("loop", Path(args.loop))):
        app = f"sysone-gate-bridge-{variant}"
        adir = out / app
        adir.mkdir()
        bit = d / "gate_kr260_top.bit"
        work = out / f"_bootgen_{variant}"
        work.mkdir()
        shutil.copyfile(bit, work / f"{app}.bit")
        (work / "bitstream.bif").write_text(f"all:\n{{\n  [destination_device = pl] {app}.bit\n}}\n")
        r = subprocess.run(["cmd", "/c", BOOTGEN, "-arch", "zynqmp", "-image", "bitstream.bif",
                            "-process_bitstream", "bin", "-w"], cwd=work, capture_output=True)
        (work / "bootgen.log").write_bytes(r.stdout + r.stderr)
        if r.returncode:
            raise SystemExit(f"bootgen failed for {variant}")
        shutil.copyfile(work / f"{app}.bit.bin", adir / f"{app}.bit.bin")
        (adir / f"{app}.dts").write_text(DTS.format(app=app, variant=variant))
        (adir / "shell.json").write_text(json.dumps({"shell_type": "XRT_FLAT", "num_slots": "1"}, indent=2) + "\n")
        summary = dict(l.split(" ", 1) for l in (d / "summary.txt").read_text().split("\n") if l)
        builds[app] = {"bit_sha256": sha(bit), "summary": summary}
        manifest[app] = {n.name: sha(n) for n in adir.iterdir()}
        shutil.rmtree(work)
    tools = out / "tools"
    tools.mkdir()
    shutil.copyfile(ROOT / "scripts/v2/gate/gate_board.py", tools / "gate_board.py")
    shutil.copyfile(ROOT / "build/v2/agent-gate-bridge/inject/expected.json", tools / "loop_expected.json")
    shutil.copyfile(ROOT / "scripts/v2/gate_host/gate_bench.py", tools / "gate_bench.py")
    for f in ("intspec.py", "modbus.py", "plant.py", "__init__.py"):
        (tools / "agent_gate").mkdir(exist_ok=True)
        shutil.copyfile(ROOT / "src/sysone/v2/agent_gate" / f, tools / "agent_gate" / f)
    manifest["tools"] = {str(p.relative_to(out)).replace("\\", "/"): sha(p) for p in tools.rglob("*") if p.is_file()}
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    (out / "BUILDS.json").write_text(json.dumps(builds, indent=2))
    tar = out.with_suffix(".tar")
    with tarfile.open(tar, "w") as t:
        for p in sorted(out.rglob("*")):
            if p.is_file():
                t.add(p, arcname=str(p.relative_to(out)).replace("\\", "/"))
    print(json.dumps({"archive": str(tar), "sha256": sha(tar), "builds": builds}, indent=2))


if __name__ == "__main__":
    main()
