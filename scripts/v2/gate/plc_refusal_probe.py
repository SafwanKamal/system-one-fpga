"""Real-server probe for the gate's refusal-by-mutation (direction 1, first experiment; pre-registered).

  python scripts/v2/gate/plc_refusal_probe.py --out build/v2/plc-refusal/<run> --server name=host:port [...] [--rounds 10000]
  python scripts/v2/gate/plc_refusal_probe.py --out ... --prereg-only

The gate refuses a write by rewriting byte 7 of the ADU (the function code) to 0x7F and forwarding it unchanged otherwise;
the server must answer function 0xFF with exception 01, must not apply the write and must keep the TCP session. This
probe sends exactly the bytes the gate would forward, over a real TCP session to a real Modbus server implementation, and
checks all three, interleaved with normal reads and writes. It also tests the alternative mutation for FC6 (rewrite to an
FC3 read of zero registers, same length, expected exception 03).

A second check (`--client-check`) runs real client libraries through a Modbus-level relay that applies the gate's two
rewrites (request 0x7F, reply -> original|0x80 with code 03) and checks that the client reports exception 03 and that the
same connection keeps working.
"""
from __future__ import annotations

import hashlib
import json
import random
import socket
import struct
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ILLEGAL_FC = 0x7F
TIMEOUT_S = 1.0

PREREG = {
    "question": "Do real Modbus/TCP server implementations answer the gate's mutated request (function code rewritten to "
                "0x7F, same length) with exception 01, without applying the write and without closing the session; and "
                "do client libraries accept the restored exception 03 and keep the session?",
    "stimulus": "per server: one TCP session; N rounds; each round a random FC6 (or, 1 in 4, FC16 1-4 registers) write to "
                "holding registers 0-3, sent with its function code rewritten to 0x7F; then an FC3 read-back of registers "
                "0-3 compared with a shadow copy. Every 5th round a genuine FC6 write (control) updates the shadow. "
                "Every 4th FC6 refusal is instead sent as the alternative mutation (FC3, quantity 0, expected exception 03). "
                "Seed 1.",
    "pass_per_server": {
        "R1": "0x7F refusals answered with function 0xFF and exception 01 in >= 99.99% of rounds",
        "R2": "zero register changes caused by any refused write",
        "R3": "zero connection closures or resets during the run; all control writes and read-backs succeed",
        "R4": "alternative mutation answered with function 0x83 and exception 03 in >= 99.99% of its rounds (reported; "
              "not required for direction 1)"},
    "client_check": "1000 refused writes per client library through a relay applying the gate's two rewrites: the library "
                    "must report exception 03 for 100% and the same connection must serve a following read each time",
    "kill": "direction 1 is killed if more than one of three PLC implementations fails R1-R3 (decided on PLC hardware; "
            "software stacks here are the first screen and do not settle it)",
    "caveat": "software Modbus stacks (OpenPLC v3 runtime core, libmodbus, pymodbus) on localhost, not PLC hardware; "
              "IDS false alarms on function code 0x7F are not measured here",
}


def mbap(txid, unit, pdu):
    return struct.pack("!HHHB", txid, 0, len(pdu) + 1, unit) + pdu


def recv_adu(sock):
    hdr = b""
    while len(hdr) < 7:
        c = sock.recv(7 - len(hdr))
        if not c:
            raise ConnectionError("closed")
        hdr += c
    ln = struct.unpack("!H", hdr[4:6])[0]
    body = b""
    while len(body) < ln - 1:
        c = sock.recv(ln - 1 - len(body))
        if not c:
            raise ConnectionError("closed")
        body += c
    return hdr + body


class Session:
    def __init__(self, host, port):
        self.host, self.port = host, port
        self.tx = 0
        self.sock = None
        self.connect()

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=TIMEOUT_S)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def xact(self, pdu, unit=1):
        self.tx = (self.tx + 1) & 0xFFFF
        t0 = time.perf_counter()
        self.sock.sendall(mbap(self.tx, unit, pdu))
        r = recv_adu(self.sock)
        dt = time.perf_counter() - t0
        rtx = struct.unpack("!H", r[:2])[0]
        return r[7:], dt, rtx == self.tx

    def read4(self):
        p, _, ok = self.xact(struct.pack("!BHH", 3, 0, 4))
        if not ok or p[0] != 3 or p[1] != 8:
            raise RuntimeError(f"read failed {p.hex()}")
        return list(struct.unpack("!4H", p[2:10]))


def probe(name, host, port, rounds, seed=1):
    rng = random.Random(seed)
    s = Session(host, port)
    shadow = s.read4()
    res = {"server": name, "rounds": rounds, "refusals": 0, "ff01": 0, "other_reply": {}, "timeouts": 0, "closures": 0,
           "reg_changes": 0, "txid_mismatch": 0, "alt": 0, "alt_8303": 0, "alt_other": {}, "control_writes": 0,
           "control_fail": 0, "lat_refusal_ms": [], "lat_control_ms": [], "lat_alt_ms": []}

    def safe(fn):
        try:
            return fn()
        except (socket.timeout, TimeoutError):
            res["timeouts"] += 1
        except (ConnectionError, OSError):
            res["closures"] += 1
        s.sock.close()
        s.connect()
        return None

    for i in range(rounds):
        if i % 5 == 4:
            a, v = rng.randrange(4), rng.randrange(65536)
            out = safe(lambda: s.xact(struct.pack("!BHH", 6, a, v)))
            res["control_writes"] += 1
            if out and out[0] == struct.pack("!BHH", 6, a, v) and out[2]:
                shadow[a] = v
                res["lat_control_ms"].append(out[1] * 1000)
            else:
                res["control_fail"] += 1
        if rng.random() < 0.25:
            a = 0
            n = rng.randint(1, 4)
            vals = [rng.randrange(65536) for _ in range(n)]
            pdu = struct.pack("!BHHB", 16, a, n, 2 * n) + b"".join(struct.pack("!H", x) for x in vals)
        else:
            pdu = struct.pack("!BHH", 6, rng.randrange(4), rng.randrange(65536))
        alt = pdu[0] == 6 and rng.random() < 0.25
        mpdu = struct.pack("!BHH", 3, struct.unpack("!H", pdu[1:3])[0], 0) if alt else bytes([ILLEGAL_FC]) + pdu[1:]
        out = safe(lambda: s.xact(mpdu))
        if out:
            p, dt, ok = out
            res["txid_mismatch"] += not ok
            key = p[:2].hex()
            if alt:
                res["alt"] += 1
                if p[:2] == b"\x83\x03":
                    res["alt_8303"] += 1
                    res["lat_alt_ms"].append(dt * 1000)
                else:
                    res["alt_other"][key] = res["alt_other"].get(key, 0) + 1
            else:
                res["refusals"] += 1
                if p[:2] == b"\xff\x01":
                    res["ff01"] += 1
                    res["lat_refusal_ms"].append(dt * 1000)
                else:
                    res["other_reply"][key] = res["other_reply"].get(key, 0) + 1
        elif not alt:
            res["refusals"] += 1
        regs = safe(s.read4)
        if regs is not None and regs != shadow:
            res["reg_changes"] += 1
            shadow = regs
    s.sock.close()
    for k in ("lat_refusal_ms", "lat_control_ms", "lat_alt_ms"):
        xs = sorted(res[k])
        res[k] = {"n": len(xs), "median": round(xs[len(xs) // 2], 3) if xs else None,
                  "p99": round(xs[int(len(xs) * 0.99)], 3) if xs else None, "max": round(xs[-1], 3) if xs else None}
    n = max(res["refusals"], 1)
    res["verdict"] = {
        "R1": res["ff01"] / n >= 0.9999,
        "R2": res["reg_changes"] == 0,
        "R3": res["closures"] == 0 and res["timeouts"] == 0 and res["control_fail"] == 0 and res["txid_mismatch"] == 0,
        "R4": res["alt"] > 0 and res["alt_8303"] / res["alt"] >= 0.9999,
    }
    return res


# ------------------------------------------------------------------ client check through a gate-semantics relay
class GateRelay(threading.Thread):
    """Modbus-level relay applying the gate's rewrites to every write: request fc -> 0x7F, reply 0xFF -> fc|0x80, code 03."""

    def __init__(self, upstream):
        super().__init__(daemon=True)
        self.upstream = upstream
        self.ls = socket.socket()
        self.ls.bind(("127.0.0.1", 0))
        self.ls.listen(4)
        self.port = self.ls.getsockname()[1]
        self.refused = self.restored = 0

    def run(self):
        while True:
            c, _ = self.ls.accept()
            u = socket.create_connection(self.upstream)
            threading.Thread(target=self.serve, args=(c, u), daemon=True).start()

    def serve(self, c, u):
        try:
            while True:
                q = recv_adu(c)
                fc = q[7]
                if fc in (6, 16):
                    q = q[:7] + bytes([ILLEGAL_FC]) + q[8:]
                    self.refused += 1
                u.sendall(q)
                r = recv_adu(u)
                if fc in (6, 16) and r[7] == 0xFF and len(r) == 9:
                    r = r[:7] + bytes([fc | 0x80, 0x03])
                    self.restored += 1
                c.sendall(r)
        except (ConnectionError, OSError):
            c.close()
            u.close()


def client_check_pymodbus(port, n):
    import pymodbus
    from pymodbus.client import ModbusTcpClient
    # pymodbus 3.7.4's client was found unable to decode even unmodified write replies from a 3.16 server, so the
    # client check uses the current release; the unit keyword was renamed in 3.10
    unit = {"slave": 1} if pymodbus.__version__.startswith("3.7") else {"device_id": 1}
    cl = ModbusTcpClient("127.0.0.1", port=port, timeout=TIMEOUT_S, retries=0)
    assert cl.connect()
    ok = bad = 0
    detail = {}
    for i in range(n):
        r = cl.write_register(i % 4, i & 0xFFFF, **unit) if i % 4 else cl.write_registers(0, [i & 0xFFFF, 1], **unit)
        rd = cl.read_holding_registers(0, count=4, **unit)
        good = r.isError() and getattr(r, "exception_code", None) == 3 and not rd.isError()
        ok += good
        if not good:
            k = repr(r)[:80]
            detail[k] = detail.get(k, 0) + 1
            bad += 1
    sock_same = cl.connected
    cl.close()
    return {"client": "pymodbus " + __import__("pymodbus").__version__, "n": n, "exception03_and_session_ok": ok,
            "failures": bad, "failure_kinds": detail, "still_connected": sock_same}


def main():
    out = ROOT / sys.argv[sys.argv.index("--out") + 1]
    out.mkdir(parents=True, exist_ok=True)
    me = Path(__file__).read_bytes()
    pre = out / "prereg.json"
    if not pre.exists():
        pre.write_text(json.dumps({**PREREG, "probe_sha256": hashlib.sha256(me).hexdigest(),
                                   "written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=1) + "\n")
        print("pre-registration written")
    elif json.loads(pre.read_text())["probe_sha256"] != hashlib.sha256(me).hexdigest():
        raise SystemExit("probe changed after pre-registration")
    if "--prereg-only" in sys.argv:
        return
    rounds = int(sys.argv[sys.argv.index("--rounds") + 1]) if "--rounds" in sys.argv else 10000
    servers = [a.split("=", 1) for a in (sys.argv[i + 1] for i, x in enumerate(sys.argv) if x == "--server")]
    results = []
    for name, hp in servers:
        host, port = hp.rsplit(":", 1)
        t0 = time.time()
        r = probe(name, host, int(port), rounds)
        r["wall_s"] = round(time.time() - t0, 1)
        if "--client-check" in sys.argv:
            relay = GateRelay((host, int(port)))
            relay.start()
            r["client_check"] = client_check_pymodbus(relay.port, 1000)
            r["client_check"]["relay_refused"], r["client_check"]["relay_restored"] = relay.refused, relay.restored
        results.append(r)
        print(json.dumps({k: r[k] for k in ("server", "refusals", "ff01", "other_reply", "timeouts", "closures",
                                            "reg_changes", "alt", "alt_8303", "alt_other", "verdict", "wall_s")}), flush=True)
        if "client_check" in r:
            print("  client:", json.dumps(r["client_check"]), flush=True)
    (out / "results.json").write_text(json.dumps(results, indent=1) + "\n")


if __name__ == "__main__":
    main()
