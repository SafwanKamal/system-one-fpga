#!/usr/bin/env python3
"""Board-side helper for the agent-gate bridge (runs on the KR260 as root, stdlib only).

  gate_board.py inventory                      live identity (boot id, fpga state/firmware, apps, links)
  gate_board.py install <pkg_dir>              install both gate apps into /lib/firmware/xilinx
  gate_board.py load <app>                     xmutil unloadapp; xmutil loadapp <app>
  gate_board.py status [--expected f.json]     read the read-only status window at 0xA000_0000
  gate_board.py watch <seconds>                status every second (link/counter changes)
  gate_board.py restore <app>                  reload the given previous app (e.g. sysone-qwen-decoder-v9e)
Every command prints one JSON document.
"""
import hashlib
import json
import mmap
import os
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

BASE = 0xA0000000
FW = Path("/lib/firmware/xilinx")
APPS = ["sysone-gate-bridge-prod", "sysone-gate-bridge-loop"]
NAMES = {0: "id", 1: "t_ms", 2: "rxA_frames", 3: "rxA_bad", 4: "rxA_overflow", 5: "rxB_frames",
         6: "rxB_bad", 7: "rxB_overflow", 8: "AB_loaded", 9: "AB_forwarded", 10: "AB_dropped",
         11: "txB_frames", 12: "BA_loaded", 13: "BA_forwarded", 14: "BA_dropped", 15: "txA_frames",
         16: "lat_last_cyc", 17: "lat_min_cyc", 18: "lat_max_cyc", 19: "last_decision", 20: "last_txid",
         21: "lvl10_act0", 22: "act1_act2", 23: "act3",
         48: "clk_status", 49: "mdioA_ctrl", 50: "mdioA_id", 51: "mdioA_bmsr_physts", 52: "mdioA_cfg",
         53: "mdioB_ctrl", 54: "mdioB_id", 55: "mdioB_bmsr_physts", 56: "mdioB_cfg", 57: "injector"}
RULES = ["pass", "fc_denied", "fc_not_holding_write", "unmapped", "range", "R1", "R7", "R2", "R3",
         "R4_low", "R4_drain", "R5", "R6", "malformed", "non_modbus", "fcs_bad"]


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return {"cmd": cmd, "rc": p.returncode, "out": p.stdout[-2000:], "err": p.stderr[-2000:]}


def fpga_state():
    r = {}
    for n, p in [("state", "/sys/class/fpga_manager/fpga0/state")]:
        try:
            r[n] = Path(p).read_text().strip()
        except Exception as e:
            r[n] = repr(e)
    try:
        D = Path("/sys/firmware/devicetree/base")
        region = D / (D / "__symbols__/fpga_full").read_bytes().rstrip(b"\0").decode().lstrip("/")
        r["firmware"] = (region / "firmware-name").read_bytes().rstrip(b"\0").decode()
    except Exception as e:
        r["firmware"] = None
    return r


def inventory():
    links = {}
    for n in sorted(os.listdir("/sys/class/net")):
        try:
            links[n] = {"operstate": Path(f"/sys/class/net/{n}/operstate").read_text().strip(),
                        "carrier": Path(f"/sys/class/net/{n}/carrier").read_text().strip()
                        if Path(f"/sys/class/net/{n}/carrier").exists() else None,
                        "speed": Path(f"/sys/class/net/{n}/speed").read_text().strip()
                        if Path(f"/sys/class/net/{n}/speed").exists() else None}
        except Exception as e:
            links[n] = repr(e)
    return {"boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(), "fpga": fpga_state(),
            "listapps": run(["xmutil", "listapps"])["out"], "links": links,
            "gate_apps_installed": {a: (FW / a).is_dir() for a in APPS}}


def install(pkg):
    pkg = Path(pkg)
    manifest = json.loads((pkg / "MANIFEST.json").read_text())
    res = {}
    for app in APPS:
        src = pkg / app
        for name, h in manifest[app].items():
            if hashlib.sha256((src / name).read_bytes()).hexdigest() != h:
                raise SystemExit(f"hash mismatch {app}/{name}")
        dst = FW / app
        tmp = Path(f"/tmp/{app}.dtbo")
        r = run(["dtc", "-@", "-I", "dts", "-O", "dtb", "-o", str(tmp), str(src / (app + ".dts"))])
        if r["rc"]:
            raise SystemExit(json.dumps(r))
        if dst.exists():
            same = all((dst / n).exists() and (dst / n).read_bytes() == (src / n).read_bytes()
                       for n in [app + ".bit.bin", "shell.json"])
            if not same:
                res[app] = "already installed (DIFFERENT bitstream, left untouched)"
            elif (dst / (app + ".dtbo")).read_bytes() != tmp.read_bytes():
                shutil.copyfile(dst / (app + ".dtbo"), Path(f"/tmp/{app}.dtbo.previous"))
                shutil.copyfile(tmp, dst / (app + ".dtbo"))
                res[app] = "overlay updated (previous kept in /tmp)"
            else:
                res[app] = "already installed"
            continue
        dst.mkdir()
        shutil.copyfile(src / (app + ".bit.bin"), dst / (app + ".bit.bin"))
        shutil.copyfile(tmp, dst / (app + ".dtbo"))
        shutil.copyfile(src / "shell.json", dst / "shell.json")
        res[app] = "installed"
    return res


def read_regs():
    fd = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
    try:
        m = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ, offset=BASE)
        words = [struct.unpack_from("<I", m, 4 * i)[0] for i in range(64)]
        m.close()
    finally:
        os.close(fd)
    return words


def decode(w):
    r = {NAMES[i]: w[i] for i in NAMES}
    r["rule_counts"] = {RULES[i]: w[32 + i] for i in range(16)}
    for side, base in (("A", 49), ("B", 53)):
        c = w[base]
        r[f"phy{side}"] = {"addr": c & 31, "speed": {2: 1000, 1: 100, 0: 10}.get((c >> 5) & 3, "?"),
                           "link": bool(c >> 7 & 1), "cfg_done": bool(c >> 8 & 1), "found": bool(c >> 9 & 1),
                           "dp83867": bool(c >> 10 & 1), "id": f"{w[base + 1]:08x}",
                           "bmsr": f"{w[base + 2] >> 16:04x}", "physts": f"{w[base + 2] & 0xffff:04x}",
                           "rgmiictl": f"{w[base + 3] >> 16:04x}", "scan_attempts": w[base + 3] & 0xff}
    r["mmcm_locked"] = bool(w[48] & 1)
    r["injector"] = {"test_build": bool(w[57] >> 31 & 1), "loopback": bool(w[57] >> 30 & 1),
                     "done": bool(w[57] >> 29 & 1), "sent": w[57] & 0xFFFFFF}
    r["lvl10"] = w[21] >> 16 if w[21] >> 16 < 0x8000 else (w[21] >> 16) - 0x10000
    r["act"] = [w[21] & 0xFFFF, w[22] >> 16, w[22] & 0xFFFF, w[23] & 0xFFFF]
    return r


def status(expected=None):
    # Never touch 0xA000_0000 unless a gate image is the operating PL image: an access with no
    # responding slave can stall the bus.
    f = fpga_state()
    if f.get("state") != "operating" or f.get("firmware") not in [a + ".bit.bin" for a in APPS]:
        return {"error": "gate image not operating; status window not read", "fpga": f}
    w = read_regs()
    if w[0] != 0x6A7E0001:
        return {"error": f"status window id {w[0]:08x} (gate app not loaded?)", "fpga": fpga_state()}
    r = {"decoded": decode(w), "raw": [f"{x:08x}" for x in w], "fpga": fpga_state()}
    if expected:
        e = json.loads(Path(expected).read_text())
        mism = {k: {"expected": v, "got": w[int(k)]} for k, v in e["status"].items() if w[int(k)] != v}
        r["expected_compare"] = {"mismatches": mism, "matched": len(e["status"]) - len(mism),
                                 "final_state_expected": [e["final_lvl10"], e["final_act"]]}
    return r


def main():
    cmd = sys.argv[1]
    if cmd == "inventory":
        out = inventory()
    elif cmd == "install":
        out = install(sys.argv[2])
    elif cmd in ("load", "restore"):
        own = Path("/sys/class/misc/sysone_qwen_dma/ownership")
        if own.exists():
            o = {k: int(v, 0) for k, v in (kv.split("=") for kv in own.read_text().split())}
            if o.get("owner_tgid") or o.get("vmas") or o.get("loading"):
                raise SystemExit(json.dumps({"refused": "RC1 DMA owner active; drain sysone-rc1.service first",
                                             "ownership": o}))
        out = {"unload": run(["xmutil", "unloadapp"]), "load": run(["xmutil", "loadapp", sys.argv[2]])}
        time.sleep(2)
        out["fpga"] = fpga_state()
        if out["load"]["rc"] or out["fpga"].get("firmware") != sys.argv[2] + ".bit.bin":
            print(json.dumps(out, indent=1, default=str))
            raise SystemExit(4)
    elif cmd == "status":
        exp = sys.argv[sys.argv.index("--expected") + 1] if "--expected" in sys.argv else None
        out = status(exp)
    elif cmd == "watch":
        out = []
        for _ in range(int(sys.argv[2])):
            d = status()
            out.append({k: d.get("decoded", {}).get(k) for k in ("t_ms", "phyA", "phyB", "rxA_frames", "rxA_bad",
                                                                 "rxB_frames", "rxB_bad", "AB_forwarded",
                                                                 "BA_forwarded", "injector")})
            time.sleep(1)
    else:
        raise SystemExit(__doc__)
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
