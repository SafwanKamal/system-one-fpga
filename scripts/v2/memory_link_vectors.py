"""Vectors and checker for the v2 memory link simulation (simulation/v2/memory_link_tb.sv).

    uv run python scripts/v2/memory_link_vectors.py            # write simulation/v2/vectors/
    uv run python scripts/v2/memory_link_vectors.py --check    # decode memory_responses.hex

Frames are built with the host's own encoder (src/sysone/v2/memory_protocol.py).
The traffic: writes of every size from 1 to 64 beats at scattered addresses
(including the last beats of the 128 MiB space), reads that cover them, reads of
memory never written (zeros), a short write frame (declares more beats than it
carries: the ack must report what was written), overlapping rewrites, broadcast
requests, and frames that must be ignored (bad FCS, another MAC, unaligned address,
0 or 65 beats, an address past the end, a v1 frame, a runt). RUN commands are
answered by this testbench's stand-in for the encoder with status 0x80 (no encoder),
as a link-only bitstream does; a RUN of two beats must be ignored.

The checker replays the traffic on a Python model of the memory and compares every
reply: type, sequence number, address, beat count and every data byte.
"""

from __future__ import annotations

import argparse
import json
import random
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sysone.v2 import memory_protocol as mp   # noqa: E402

HOST = bytes.fromhex("0a0000000001")
OUT = ROOT / "simulation" / "v2" / "vectors"
MEMORY_BYTES = 1 << 27


def build(seed: int = 0):
    rng = random.Random(seed)
    frames = []          # (bytes with FCS, expect_reply, description)
    memory: dict[int, int] = {}
    expected = []        # in reply order: dict(kind, seq, address, beats, data hex)
    seq = 100

    def write(address, data, declared=None, dst=mp.FPGA_MAC):
        nonlocal seq
        seq += 1
        beats = len(data) // 16
        frame = mp.encode(mp.WRITE, seq, address, declared or beats, data, HOST, dst=dst)
        for i, b in enumerate(data):
            memory[address + i] = b
        frames.append((frame, True, f"write {beats} beats at {address:#x}"))
        expected.append({"kind": mp.WRITE_ACK, "seq": seq, "address": address, "beats": beats})

    def read(address, beats, dst=mp.FPGA_MAC):
        nonlocal seq
        seq += 1
        frames.append((mp.read_frame(seq, address, beats, HOST, dst=dst), True,
                       f"read {beats} beats at {address:#x}"))
        data = bytes(memory.get(address + i, 0) for i in range(beats * 16))
        expected.append({"kind": mp.READ_DATA, "seq": seq, "address": address, "beats": beats,
                         "data": data.hex()})

    def run(descriptor):
        nonlocal seq
        seq += 1
        frames.append((mp.run_frame(seq, descriptor, HOST), True, "run"))
        expected.append({"kind": mp.RUN_DONE, "seq": seq, "address": 0, "beats": 1,
                         "data": mp.RunResult(0, 0, mp.STATUS_NO_ENCODER, 0).pack().hex()})

    def ignored(frame, why):
        frames.append((frame, False, why))

    regions = []
    for beats in list(range(1, 65)) + [64] * 6:
        address = rng.randrange(0, MEMORY_BYTES // 16 - beats) * 16
        if len(regions) < 4:
            address = [0, 4096 - 16 * (beats // 2), MEMORY_BYTES - 16 * beats, 1 << 20][len(regions)]
        data = bytes(rng.randrange(256) for _ in range(beats * 16))
        write(address, data)
        regions.append((address, beats))
        if rng.random() < 0.3:
            a, b = regions[rng.randrange(len(regions))]
            read(a, b)
    for a, b in regions:
        read(a, b)
    read(1 << 26, 8)                                    # never written: zeros
    a, b = regions[10]
    write(a + 16, bytes(rng.randrange(256) for _ in range(48)))   # overlapping rewrite
    read(a, b)
    write(3 << 24, bytes(rng.randrange(256) for _ in range(80)), declared=10)   # short frame
    read(3 << 24, 10)
    read(0, 4, dst=b"\xff" * 6)                          # broadcast is answered
    run(mp.run_descriptor(0x400, 12, 256, 0x100000, 0x200000))
    read(a, b)                                           # the link works after a run

    seq += 1
    bad = bytearray(mp.read_frame(seq, 0, 4, HOST))
    bad[-1] ^= 0xFF
    ignored(bytes(bad), "bad FCS")
    ignored(mp.read_frame(seq, 0, 4, HOST, dst=bytes.fromhex("020000000099")), "other MAC")
    ignored(mp.read_frame(seq, 8, 4, HOST), "unaligned address")
    ignored(mp.read_frame(seq, 0, 0, HOST), "zero beats")
    ignored(mp.encode(mp.READ, seq, 0, 65, b"", HOST), "65 beats")
    ignored(mp.read_frame(seq, MEMORY_BYTES, 1, HOST), "past the end")
    v1 = bytearray(mp.read_frame(seq, 0, 4, HOST, with_fcs=False))
    v1[14] = 1
    ignored(bytes(v1) + mp.fcs(bytes(v1)), "v1 version byte")
    ignored(mp.FPGA_MAC + HOST + b"\x88\xb5\x02", "runt")
    ignored(mp.encode(mp.RUN, seq, 0, 2, bytes(32), HOST), "run of two beats")
    read(0, 4)                                           # still alive afterwards
    return frames, expected


def write_vectors(frames) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    words = []
    for frame, _, _ in frames:
        words += [f"{b:03x}" for b in frame]
        words.append("100")
    (OUT / "memory_requests.hex").write_text("\n".join(words) + "\n")
    (OUT / "memory_expect.hex").write_text("\n".join("1" if e else "0" for _, e, _ in frames) + "\n")
    (OUT / "memory_frame_count.hex").write_text(f"{len(frames):08x}\n")


def check(expected) -> int:
    path = ROOT / "simulation" / "v2" / "memory_responses.hex"
    words = [int(w, 16) for w in path.read_text().split()]
    replies, cur = [], []
    for w in words:
        if w == 0x100:
            replies.append(bytes(cur))
            cur = []
        else:
            cur.append(w)
    errors = 0
    if len(replies) != len(expected):
        print(f"{len(replies)} replies, expected {len(expected)}")
        errors += 1
    for i, (raw, exp) in enumerate(zip(replies, expected)):
        try:
            m = mp.decode(raw)
        except mp.ProtocolError as e:
            print(f"reply {i}: {e}")
            errors += 1
            continue
        got = {"kind": m.kind, "seq": m.sequence, "address": m.address, "beats": m.beats}
        if m.kind in (mp.READ_DATA, mp.RUN_DONE):
            got["data"] = m.data.hex()
        if got != exp or m.source != mp.FPGA_MAC:
            errors += 1
            if errors < 6:
                print(f"reply {i} differs: got {json.dumps(got)[:200]} expected {json.dumps(exp)[:200]}")
    n_data = sum(e["beats"] * 16 for e in expected if e["kind"] == mp.READ_DATA)
    if errors:
        print(f"FAIL: {errors} problems")
        return 1
    print(f"PASS: {len(replies)} replies, FCS good, every field and all {n_data} read-back bytes "
          f"match the memory model")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    frames, expected = build()
    if args.check:
        return check(expected)
    write_vectors(frames)
    n_ok = sum(e for _, e, _ in frames)
    print(f"{len(frames)} frames ({n_ok} answered, {len(frames) - n_ok} ignored) -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
