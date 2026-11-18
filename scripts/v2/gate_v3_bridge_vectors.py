"""Bridge-level vectors for gate_bridge_core_v3: one line per frame sent into a port, with the frame expected on the
other port (if any).  The bridge's millisecond clock does not advance in simulation, so expectations come from a
GateV3Model fed t = 0.

Line (hex): dir  fcs_ok  len  tx  outlen  <len bytes in>  <outlen bytes out>      (frames without FCS)
The expected transmitted frame is `out` followed by its Ethernet FCS (CRC-32, little endian), which is the original
FCS for an unmodified frame and a regenerated one for a mutated frame.
"""
from __future__ import annotations

import argparse
import collections
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import gate_v3_vectors as V  # noqa: E402
from sysone.v2.agent_gate.frames_v3 import GateV3Model  # noqa: E402


def collect(source, *args):
    """Run a vector source (recorded / fuzz / probes) and capture the frames it sends."""
    frames = []
    orig = V.emit

    def cap(model, d, t, ok, f, out, cov):
        r = orig(model, d, t, ok, f, [], cov)      # real model, so response generation stays realistic
        frames.append((d, ok, f))
        return r

    V.emit = cap
    try:
        source(*args)
    finally:
        V.emit = orig
    return frames


def lines_for(frames, model):
    out, tx_n, mut_n, rst_n = [], 0, 0, 0
    for d, ok, f in frames:
        fwd, rule, cls = model.process(d, f, 0, ok)
        patched = model.patch["kind"] if model.patch else 0
        tx = fwd or patched == 1
        o = model.out if tx else b""
        tx_n += tx
        mut_n += patched == 1
        rst_n += patched == 2
        out.append(f"{d:x} {int(ok):x} {len(f):x} {int(tx):x} {len(o):x} " + " ".join(f"{b:02x}" for b in f) +
                   (" " + " ".join(f"{b:02x}" for b in o) if o else ""))
    return out, tx_n, mut_n, rst_n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "simulation/v2/gate/vectors/gate_v3_bridge"))
    ap.add_argument("--fuzz", type=int, default=6000)
    ap.add_argument("--rec", type=int, default=1)
    args = ap.parse_args()
    cov = collections.Counter()
    rec = collect(lambda: V.recorded(GateV3Model(), [], cov, args.rec))
    # one episode per scenario/task is plenty at bridge level: keep every 8th recorded frame run of 400
    rec = rec[:4000]
    fz = collect(lambda: V.fuzz(GateV3Model(), [], cov, args.fuzz, random.Random(41)))
    base = Path(args.out)
    for name, frames in (("rec", rec), ("fuzz", fz)):
        lines, tx, mut, rst = lines_for(frames, GateV3Model())
        base.with_name(base.name + f"_{name}.txt").write_text("\n".join(lines) + "\n")
        print(f"{name}: {len(frames)} frames, {tx} transmitted ({mut} mutated requests, {rst} restored replies)")


if __name__ == "__main__":
    main()
