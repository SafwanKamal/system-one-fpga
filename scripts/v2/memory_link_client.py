"""Host side of the v2 memory link: read and write the board's DDR2 over raw Ethernet.

    uv run python scripts/v2/memory_link_client.py --list-interfaces
    uv run python scripts/v2/memory_link_client.py -i "Ethernet" test --mib 4
    uv run python scripts/v2/memory_link_client.py -i "Ethernet" write weights.bin --address 0
    uv run python scripts/v2/memory_link_client.py -i "Ethernet" read out.bin --address 0 --length 65536
    uv run python scripts/v2/memory_link_client.py -i "Ethernet" verify weights.bin --address 0

Needs the nexys4ddr_link_top bitstream (scripts/v2/create_project_v2.tcl -tclargs build).
Protocol: src/sysone/v2/memory_protocol.py; one frame carries up to 64 beats = 1 KiB.

`test` writes pseudo-random data, reads it back and compares, at the bottom and the
top of the 128 MiB space. The throughput it prints is the throughput of this
Ethernet link through the host's packet path (scapy / Npcap); it says nothing about
the DDR2 (measured on the board itself by the ddr_test top) or the encoder, which
never goes through this link.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sysone.v2 import memory_protocol as mp   # noqa: E402

CHUNK = mp.MAX_BEATS * mp.BEAT_BYTES
MEMORY_BYTES = 1 << 27


class Link:
    """Pipelined request/reply over one persistent capture.

    Up to `window` requests are in flight; a request without a reply after
    `timeout` seconds is sent again (both operations are idempotent).
    """

    def __init__(self, interface: str, timeout: float = 0.2, window: int = 2):
        from scapy.all import AsyncSniffer, conf, get_if_hwaddr
        self.interface = interface
        self.host = bytes.fromhex(get_if_hwaddr(interface).replace(":", ""))
        self.timeout = timeout
        self.window = window
        self.sequence = int(time.time()) & 0xFFFF0000
        self.replies: dict[int, mp.Message] = {}
        self.lock = threading.Condition()
        self.socket = conf.L2socket(iface=interface)
        bpf = f"ether proto 0x{mp.ETHERTYPE:04x} and ether src 02:00:00:00:00:02"
        self.sniffer = AsyncSniffer(iface=interface, filter=bpf, store=False, prn=self._on_frame)
        self.sniffer.start()
        time.sleep(0.3)
        self.retries = 0

    def close(self) -> None:
        self.sniffer.stop()
        self.socket.close()

    def _on_frame(self, packet) -> None:
        try:
            m = mp.decode(bytes(packet), has_fcs=False)
        except mp.ProtocolError:
            return
        with self.lock:
            self.replies[m.sequence] = m
            self.lock.notify_all()

    def _run(self, requests: list[tuple[int, bytes]]) -> dict[int, mp.Message]:
        """requests: (sequence, frame). Returns sequence -> reply."""
        pending = list(requests)
        in_flight: dict[int, tuple[bytes, float]] = {}
        done: dict[int, mp.Message] = {}
        resent = 0
        while pending or in_flight:
            while pending and len(in_flight) < self.window:
                seq, frame = pending.pop(0)
                self.socket.send(frame)
                in_flight[seq] = (frame, time.perf_counter())
            with self.lock:
                self.lock.wait(timeout=0.01)
                for seq in list(in_flight):
                    if seq in self.replies:
                        done[seq] = self.replies.pop(seq)
                        del in_flight[seq]
            now = time.perf_counter()
            for seq, (frame, sent) in list(in_flight.items()):
                if now - sent > self.timeout:
                    self.retries += 1
                    resent += 1
                    if resent > 50 + len(requests):
                        raise TimeoutError("the board stopped answering")
                    self.socket.send(frame)
                    in_flight[seq] = (frame, now)
        return done

    def _next(self) -> int:
        self.sequence = (self.sequence + 1) & 0xFFFFFFFF
        return self.sequence

    def write(self, address: int, data: bytes) -> None:
        if address % 16:
            raise ValueError("address must be a multiple of 16")
        data = data + bytes(-len(data) % 16)
        reqs, beats = [], {}
        for off in range(0, len(data), CHUNK):
            seq = self._next()
            chunk = data[off:off + CHUNK]
            beats[seq] = len(chunk) // 16
            reqs.append((seq, mp.write_frame(seq, address + off, chunk, self.host, with_fcs=False)))
        replies = self._run(reqs)
        for seq, frame in reqs:
            m = replies[seq]
            # beats from the data, not the frame length: a 1-beat frame is padded to
            # Ethernet's 60-byte minimum, which would read as 2 beats
            sent = beats[seq]
            if m.kind != mp.WRITE_ACK or m.beats != sent:
                raise IOError(f"write at {m.address:#x}: board wrote {m.beats} beats")

    def read(self, address: int, length: int) -> bytes:
        if address % 16:
            raise ValueError("address must be a multiple of 16")
        beats_total = -(-length // 16)
        reqs, order = [], []
        for b in range(0, beats_total, mp.MAX_BEATS):
            n = min(mp.MAX_BEATS, beats_total - b)
            seq = self._next()
            reqs.append((seq, mp.read_frame(seq, address + 16 * b, n, self.host, with_fcs=False)))
            order.append((seq, n))
        replies = self._run(reqs)
        out = bytearray()
        for seq, n in order:
            m = replies[seq]
            if m.kind != mp.READ_DATA or m.beats != n:
                raise IOError(f"read at {m.address:#x}: {m.beats} beats")
            out += m.data
        return bytes(out[:length])

    def run(self, descriptor: bytes, timeout: float = 5.0) -> mp.RunResult:
        """RUN (encoder bitstream): returns the board's run result. Sent again if no
        reply in `timeout` seconds (a repeated run just runs again)."""
        seq = self._next()
        frame = mp.run_frame(seq, descriptor, self.host, with_fcs=False)
        saved, self.timeout = self.timeout, timeout
        try:
            m = self._run([(seq, frame)])[seq]
        finally:
            self.timeout = saved
        if m.kind != mp.RUN_DONE:
            raise IOError(f"run: reply type {m.kind:#x}")
        return mp.RunResult.parse(m.data)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--interface")
    ap.add_argument("--list-interfaces", action="store_true")
    ap.add_argument("--timeout", type=float, default=0.2)
    ap.add_argument("--window", type=int, default=2, help="requests in flight")
    sub = ap.add_subparsers(dest="command")
    t = sub.add_parser("test")
    t.add_argument("--mib", type=float, default=1.0)
    for name in ("write", "read", "verify"):
        p = sub.add_parser(name)
        p.add_argument("file")
        p.add_argument("--address", type=lambda s: int(s, 0), default=0)
        if name == "read":
            p.add_argument("--length", type=lambda s: int(s, 0), required=True)
    args = ap.parse_args()

    if args.list_interfaces:
        from scapy.all import show_interfaces
        show_interfaces()
        return 0
    if not args.interface or not args.command:
        ap.error("need -i INTERFACE and a command (see --help)")
    link = Link(args.interface, args.timeout, args.window)
    try:
        if args.command == "test":
            n = int(args.mib * (1 << 20)) // 16 * 16
            ok = True
            for base in (0, MEMORY_BYTES - n):
                data = os.urandom(n)
                t0 = time.perf_counter()
                link.write(base, data)
                t1 = time.perf_counter()
                back = link.read(base, n)
                t2 = time.perf_counter()
                bad = sum(a != b for a, b in zip(data, back))
                ok &= bad == 0
                print(f"{n / (1 << 20):.2f} MiB at {base:#010x}: "
                      f"{'OK' if bad == 0 else f'{bad} bytes differ'}   "
                      f"(link, host-measured: write {n / (t1 - t0) / 1e6:.2f} MB/s, "
                      f"read {n / (t2 - t1) / 1e6:.2f} MB/s; not the DDR2's speed)")
            print(f"retransmissions: {link.retries}")
            return 0 if ok else 1
        if args.command == "write":
            data = Path(args.file).read_bytes()
            link.write(args.address, data)
            print(f"wrote {len(data)} bytes at {args.address:#x}")
        elif args.command == "read":
            data = link.read(args.address, args.length)
            Path(args.file).write_bytes(data)
            print(f"read {len(data)} bytes from {args.address:#x} into {args.file}")
        else:
            data = Path(args.file).read_bytes()
            link.write(args.address, data)
            back = link.read(args.address, len(data))
            bad = sum(a != b for a, b in zip(data, back))
            print(f"{len(data)} bytes at {args.address:#x}: "
                  + ("identical after read-back" if bad == 0 else f"{bad} bytes differ"))
            return 0 if bad == 0 else 1
    finally:
        link.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
