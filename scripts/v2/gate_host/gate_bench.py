"""Gate bench tools (stdlib only; runs on the laptop, the KR260 Linux, or both).

  plant   : Modbus/TCP plant server      python gate_bench.py plant --bind 10.50.0.20 --port 502
  swgate  : software gate (TCP proxy)    python gate_bench.py swgate --listen 127.0.0.1:15021 --upstream 127.0.0.1:15020
  replay  : agent replay client          python gate_bench.py replay --target 10.50.0.20:502 --run <go/no-go dir>
  rehearse: plant + swgate + replay over localhost, checks decisions against intspec

A blocked write is never answered (the hardware gate drops it), so the client times out,
aborts the TCP connection with RST and reconnects.  A TCP-aware gate that answers with a
Modbus exception is future work.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import socket
import struct
import sys
import time
from pathlib import Path

try:                                   # repository layout
    ROOT = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(ROOT / "src"))
    from sysone.v2.agent_gate import intspec as S  # noqa: E402
    from sysone.v2.agent_gate import modbus as M  # noqa: E402
except (ImportError, IndexError):      # board package layout: tools/agent_gate/
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from agent_gate import intspec as S  # noqa: E402
    from agent_gate import modbus as M  # noqa: E402


# ------------------------------------------------------------------ software gate proxy

async def run_swgate(listen: str, upstream: str, log_path: str | None):
    gate = M.SoftwareGate()
    lh, lp = listen.rsplit(":", 1)
    uh, up = upstream.rsplit(":", 1)
    logf = open(log_path, "a") if log_path else None

    async def client(cr, cw):
        ur, uw = await asyncio.open_connection(uh, int(up))

        async def up_to_down():
            buf = b""
            while True:
                d = await ur.read(4096)
                if not d:
                    break
                buf += d
                while True:
                    adu, buf = M.parse_adu(buf)
                    if adu is None:
                        break
                    gate.response(adu)
                    cw.write(adu)
                await cw.drain()

        task = asyncio.create_task(up_to_down())
        buf = b""
        try:
            while True:
                d = await cr.read(4096)
                if not d:
                    break
                buf += d
                while True:
                    adu, buf = M.parse_adu(buf)
                    if adu is None:
                        break
                    t0 = time.perf_counter_ns()
                    rule = gate.request(adu)
                    dt = time.perf_counter_ns() - t0
                    if logf:
                        logf.write(json.dumps({"rule": rule, "decide_ns": dt, "adu": adu.hex()}) + "\n")
                        logf.flush()
                    if rule == S.PASS:
                        uw.write(adu)
                await uw.drain()
        except ConnectionResetError:
            pass
        finally:
            task.cancel()
            uw.close()
            cw.close()

    server = await asyncio.start_server(client, lh, int(lp))
    async with server:
        await server.serve_forever()


# ------------------------------------------------------------------ replay client

class Client:
    def __init__(self, target: str, timeout: float):
        self.host, port = target.rsplit(":", 1)
        self.port = int(port)
        self.timeout = timeout
        self.sock = None
        self.txid = 0

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def abort(self):
        if self.sock:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            self.sock.close()
            self.sock = None

    def call(self, pdu: bytes):
        """Return (response_pdu or None on timeout, seconds)."""
        if self.sock is None:
            self.connect()
        self.txid = (self.txid + 1) & 0xFFFF
        adu = struct.pack("!HHHB", self.txid, 0, len(pdu) + 1, 1) + pdu
        t0 = time.perf_counter()
        self.sock.sendall(adu)
        buf = b""
        try:
            while True:
                d = self.sock.recv(4096)
                if not d:
                    raise ConnectionResetError
                buf += d
                r, buf = M.parse_adu(buf)
                if r is not None:
                    return r[7:], time.perf_counter() - t0
        except (socket.timeout, ConnectionResetError, OSError):
            self.abort()
            return None, time.perf_counter() - t0


def replay(target: str, run_dir: str, limit: int, timeout: float, out: str | None):
    recs = [json.loads(l) for l in open(Path(run_dir) / "decisions.jsonl")]
    recs = [r for r in recs if r["source"] == "llm"][:limit]
    c = Client(target, timeout)
    results = []
    for r in recs:
        poll, tp = c.call(struct.pack("!BHH", 4, 0, 4))
        q = r["req"]
        vals = [S.u16(v) for v in q["values"]]
        if q["fc"] == 6 and len(vals) == 1:
            pdu = struct.pack("!BHH", 6, q["addr"] & 0xFFFF, vals[0])
        else:
            pdu = struct.pack("!BHHB", 16, q["addr"] & 0xFFFF, len(vals), 2 * len(vals)) + \
                b"".join(struct.pack("!H", v) for v in vals)
        resp, tw = c.call(pdu)
        results.append({"req": q, "answered": resp is not None, "rtt_s": round(tw, 6),
                        "poll_rtt_s": round(tp, 6), "exception": bool(resp and resp[0] & 0x80)})
    c.abort()
    summ = {"writes": len(results), "answered": sum(r["answered"] for r in results),
            "blocked_or_lost": sum(not r["answered"] for r in results)}
    if out:
        Path(out).write_text(json.dumps({"summary": summ, "results": results}, indent=1))
    return summ, results


# ------------------------------------------------------------------ localhost rehearsal

def rehearse(run_dir: str, limit: int, out_dir: str):
    import subprocess
    import threading
    outp = Path(out_dir)
    outp.mkdir(parents=True, exist_ok=True)
    plant_log = outp / "plant_writes.jsonl"
    gate_log = outp / "swgate_decisions.jsonl"
    for f in (plant_log, gate_log):
        f.unlink(missing_ok=True)
    py = sys.executable
    me = str(Path(__file__).resolve())
    p1 = subprocess.Popen([py, me, "plant", "--bind", "127.0.0.1", "--port", "15020", "--log", str(plant_log)])
    time.sleep(1.0)
    p2 = subprocess.Popen([py, me, "swgate", "--listen", "127.0.0.1:15021", "--upstream", "127.0.0.1:15020",
                           "--log", str(gate_log)])
    time.sleep(1.0)
    try:
        summ, results = replay("127.0.0.1:15021", run_dir, limit, 0.3, str(outp / "replay.json"))
    finally:
        p2.terminate(); p1.terminate()
    dec = [json.loads(l) for l in open(gate_log)]
    writes = [d for d in dec if struct.unpack("!B", bytes.fromhex(d["adu"])[7:8])[0] in (6, 16)]
    blocked = sum(d["rule"] != 0 for d in writes)
    applied = sum(1 for _ in open(plant_log))
    ns = sorted(d["decide_ns"] for d in writes)
    rep = {"replay": summ, "gate_write_decisions": len(writes), "gate_blocked": blocked,
           "plant_writes_applied": applied,
           "consistent": (applied == len(writes) - blocked == summ["answered"]),
           "software_decide_ns_p50_p99_max": [ns[len(ns) // 2], ns[int(len(ns) * 0.99)], ns[-1]] if ns else None,
           "rule_hist": {S.NAMES.get(k, str(k)): sum(d["rule"] == k for d in writes) for k in range(16)
                         if any(d["rule"] == k for d in writes)}}
    (outp / "rehearsal.json").write_text(json.dumps(rep, indent=2))
    return rep


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("plant"); a.add_argument("--bind", default="0.0.0.0"); a.add_argument("--port", type=int, default=502)
    a.add_argument("--seed", type=int, default=0); a.add_argument("--log")
    b = sub.add_parser("swgate"); b.add_argument("--listen", required=True); b.add_argument("--upstream", required=True)
    b.add_argument("--log")
    c = sub.add_parser("replay"); c.add_argument("--target", required=True); c.add_argument("--run", required=True)
    c.add_argument("--limit", type=int, default=200); c.add_argument("--timeout", type=float, default=0.5); c.add_argument("--out")
    d = sub.add_parser("rehearse"); d.add_argument("--run", required=True); d.add_argument("--limit", type=int, default=150)
    d.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.cmd == "plant":
        srv = M.PlantServer(args.seed, args.log)

        async def go():
            s = await asyncio.start_server(srv.serve_client, args.bind, args.port)
            async with s:
                await s.serve_forever()
        asyncio.run(go())
    elif args.cmd == "swgate":
        asyncio.run(run_swgate(args.listen, args.upstream, args.log))
    elif args.cmd == "replay":
        print(json.dumps(replay(args.target, args.run, args.limit, args.timeout, args.out)[0]))
    else:
        print(json.dumps(rehearse(args.run, args.limit, args.out), indent=2))


if __name__ == "__main__":
    main()
