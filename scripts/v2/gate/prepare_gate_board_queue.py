"""Write the numbered job queue for the agent-gate board session.

The session (build/v2/agent-gate-board-20261108/auth_session.py) runs these in order after a
local password dialog; a failed job pauses the queue.  Board protocol: the canonical
BOARD_STATUS.json must be reserved (scripts/v2/board_status.py) before the session starts
and released afterwards; every hardware command also holds /run/lock/sysone-inference.lock.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
import sys
TAG = sys.argv[1] if len(sys.argv) > 1 else ""          # e.g. "-r2" for a follow-up session
SESSION = ROOT / f"build/v2/agent-gate-board-20261108{TAG}"
ARCHIVE = ROOT / "build/v2/agent-gate-bridge/deploy.tar"
REMOTE_TAR = f"/home/ubuntu/sysone-gate-bridge-20261108{TAG}.tar"
PKG = f"/var/lib/sysone/gate-bridge-20261108{TAG}"
LOCK = "flock -w 30 /run/lock/sysone-inference.lock"


def job(name, **kw):
    (SESSION / "queue" / f"{name}.json").write_text(json.dumps(kw) + "\n")


def main():
    h = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    (SESSION / "queue").mkdir(parents=True, exist_ok=True)
    tool = f"python3 {PKG}/tools/gate_board.py"
    job("00-inventory", root=True, command=(
        f"sh -c 'cat /proc/sys/kernel/random/boot_id; cat /sys/class/fpga_manager/fpga0/state; xmutil listapps; "
        "ip -br link; for i in /sys/class/net/*; do echo $i $(cat $i/carrier 2>/dev/null) $(cat $i/speed 2>/dev/null); done; "
        "pgrep -af \"qwen|sysone\" || true'"))
    job("01-upload", upload=str(ARCHIVE), remote=REMOTE_TAR)
    job("02-unpack", root=True, command=(
        f"python3 -c \"import hashlib,tarfile;from pathlib import Path\n"
        f"a=Path('{REMOTE_TAR}');assert hashlib.sha256(a.read_bytes()).hexdigest()=='{h}'\n"
        f"p=Path('{PKG}');p.mkdir(parents=True,exist_ok=False)\n"
        f"t=tarfile.open(a);[(m.isfile() and (p/m.name).resolve().is_relative_to(p.resolve())) or exit(3) for m in t.getmembers()]\n"
        f"t.extractall(p,filter='data');print('unpacked',a)\""))
    job("03-inventory", root=True, command=f"{tool} inventory")
    job("04-install", root=True, command=f"{tool} install {PKG}")
    # RC1's service holds the inference lock and the DMA lease: drain it (no disable, no reboot)
    own = "cat /sys/class/misc/sysone_qwen_dma/ownership"
    units = "systemctl show -p ActiveState -p SubState -p MainPID sysone-rc1-init.service sysone-rc1.service"
    job("05-drain-rc1", root=True, timeout=180, command=(
        f"sysone-qwen-fpga --health; systemctl stop sysone-rc1.service; {units}; {own}; "
        "for k in owner_tgid=0 vmas=0 loading=0 sealed=1; do " f"{own} | grep -Eq \"(^| )$k( |$)\" || exit 7; done"))
    job("06-load-loop", root=True, command=f"{LOCK} {tool} load sysone-gate-bridge-loop", timeout=120)
    job("07-loop-status", root=True, command=f"sleep 5; {LOCK} {tool} status --expected {PKG}/tools/loop_expected.json")
    job("08-load-prod", root=True, command=f"{LOCK} {tool} load sysone-gate-bridge-prod", timeout=120)
    job("09-prod-watch", root=True, command=f"sleep 3; {LOCK} {tool} watch 20", timeout=120)
    job("10-prod-status", root=True, command=f"{LOCK} {tool} status")
    job("11-inventory-gate", root=True, command=f"{LOCK} {tool} inventory")
    # Restore through RC1's own boot path: back to the stock starter image (the state the
    # initializer starts from at boot), re-run the initializer (programs v9e, keeps the sealed
    # model only after a full SHA check; it takes the inference lock itself, non-blocking, so
    # it is NOT wrapped in flock), then start the service and check health.
    job("12-restore-rc1", root=True, timeout=420, command=(
        f"{LOCK} sh -c 'xmutil unloadapp; xmutil loadapp k26-starter-kits' && sleep 2 && "
        "systemctl restart sysone-rc1-init.service && systemctl start sysone-rc1.service && "
        f"cat /run/sysone-rc1-init/state.json && sysone-qwen-fpga --health && {units}"))
    job("13-rc1-query", root=True, timeout=300, command=(
        "mkdir -p /var/lib/sysone/rc1-results && sysone-qwen-fpga --query 'Read /proc/sys/kernel/random/boot_id' "
        "--out /var/lib/sysone/rc1-results/gate-bridge-20261108-restore.json --max-tokens 64 && "
        "cat /var/lib/sysone/rc1-results/gate-bridge-20261108-restore.json"))
    job("14-final-inventory", root=True, command=f"python3 {PKG}/tools/gate_board.py inventory; {units}; {own}")
    job("99-close", close=True)
    print(json.dumps({"queue": sorted(p.name for p in (SESSION / "queue").iterdir()), "archive_sha256": h}))


if __name__ == "__main__":
    main()
