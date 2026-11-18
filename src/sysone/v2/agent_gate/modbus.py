"""Stdlib Modbus/TCP pieces for the gate bench: ADU codec, a plant server backed by the
simulated pumping station, and an ADU-level software gate (same integer rules as the RTL).

Register map (same as plant.py / the RTL):
  holding 0..3 : inlet_valve, pump_speed, outlet_valve, heater_power   (FC3 read, FC6/FC16 write)
  input   0..3 : level*10, temperature*10, pressure*100, flow*100       (FC4 read, signed int16)
"""
from __future__ import annotations

import asyncio
import json
import random
import struct
import time

from . import intspec as S
from . import plant

ORDER = ["inlet_valve", "pump_speed", "outlet_valve", "heater_power"]


def parse_adu(buf: bytes):
    """Return (adu, rest) or (None, buf) if incomplete."""
    if len(buf) < 7:
        return None, buf
    txid, pid, length, unit = struct.unpack("!HHHB", buf[:7])
    if len(buf) < 6 + length:
        return None, buf
    return buf[:6 + length], buf[6 + length:]


def exception(adu: bytes, code: int) -> bytes:
    txid, pid, _, unit, fc = struct.unpack("!HHHBB", adu[:8])
    return struct.pack("!HHHBBB", txid, 0, 3, unit, fc | 0x80, code)


# ------------------------------------------------------------------ plant server

class PlantServer:
    def __init__(self, seed: int = 0, log_path: str | None = None):
        rng = random.Random(seed)
        self.p = plant.Params.sample(rng)
        self.s = plant.State(level=55.0)
        self.rng = rng
        self.t0 = time.monotonic()
        self.hazards: list[tuple[float, str]] = []
        self.log = open(log_path, "a") if log_path else None

    def advance(self):
        now = time.monotonic() - self.t0
        while self.s.t + plant.DT <= now:
            for h in plant.step(self.p, self.s):
                self.hazards.append((self.s.t, h))

    def handle(self, adu: bytes) -> bytes:
        self.advance()
        txid, pid, length, unit, fc = struct.unpack("!HHHBB", adu[:8])
        if fc in (3, 4):
            start, qty = struct.unpack("!HH", adu[8:12])
            if fc == 3:
                vals = [int(self.s.act[ORDER[i]]) for i in range(4)]
            else:
                r = plant.readings(self.p, self.s, self.rng)
                vals = [int(round(r["level"] * 10)), int(round(r["temperature"] * 10)),
                        int(round(r["pressure"] * 100)), int(round(r["flow"] * 100))]
            if start + qty > 4 or qty == 0:
                return exception(adu, 2)
            body = b"".join(struct.pack("!H", v & 0xFFFF) for v in vals[start:start + qty])
            return struct.pack("!HHHBBB", txid, 0, 3 + len(body), unit, fc, len(body)) + body
        if fc in (6, 16):
            if fc == 6:
                addr, v = struct.unpack("!HH", adu[8:12])
                vals = [v]
            else:
                addr, qty, bc = struct.unpack("!HHB", adu[8:13])
                vals = [struct.unpack("!H", adu[13 + 2 * i:15 + 2 * i])[0] for i in range(qty)]
            if addr + len(vals) > 4:
                return exception(adu, 2)
            for i, v in enumerate(vals):
                hz = plant.apply_write(self.p, self.s, ORDER[addr + i], float(min(v, 100)))
                self.hazards += [(self.s.t, h) for h in hz]
            if self.log:
                self.log.write(json.dumps({"t": round(self.s.t, 3), "fc": fc, "addr": addr, "vals": vals}) + "\n")
                self.log.flush()
            if fc == 6:
                return adu[:12]
            return struct.pack("!HHHBBHH", txid, 0, 6, unit, 16, addr, len(vals))
        return exception(adu, 1)

    async def serve_client(self, reader, writer):
        buf = b""
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                buf += data
                while True:
                    adu, buf = parse_adu(buf)
                    if adu is None:
                        break
                    writer.write(self.handle(adu))
                await writer.drain()
        except (ConnectionResetError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()


# ------------------------------------------------------------------ software gate (ADU level)

class SoftwareGate:
    """Same state tracking and integer rules as rtl/v2/gate/gate_core.sv, applied per ADU."""

    def __init__(self):
        self.lvl10 = 500
        self.act = [0, 0, 0, 0]
        self.starts: list[int] = []
        self.pending: dict[int, tuple[int, int, int]] = {}
        self.t0 = time.monotonic()
        self.decisions: list[dict] = []

    def t_ms(self) -> int:
        return int((time.monotonic() - self.t0) * 1000) & 0xFFFFFFFF

    def request(self, adu: bytes) -> int:
        txid, pid, length, unit, fc = struct.unpack("!HHHBB", adu[:8])
        if pid != 0 or len(adu) < 8:
            return 13
        if fc in (3, 4):
            if len(adu) != 12:
                return 13
            start, qty = struct.unpack("!HH", adu[8:12])
            self.pending[txid] = (fc, start, qty)
            return S.PASS
        if fc == 6:
            if len(adu) != 12:
                return 13
            addr, v = struct.unpack("!HH", adu[8:12])
            vals, over = [v], False
        elif fc == 16:
            if len(adu) < 13:
                return 13
            addr, qty, bc = struct.unpack("!HHB", adu[8:13])
            if bc != 2 * qty or len(adu) != 13 + bc:
                return 13
            vals = [struct.unpack("!H", adu[13 + 2 * i:15 + 2 * i])[0] for i in range(min(qty, 4))]
            over = qty > 4
        else:
            return S.decide(fc, 0, [], self.lvl10, self.act, self.t_ms(), self._pad())
        t = self.t_ms()
        rule = S.UNMAPPED if over else S.decide(fc, addr, vals, self.lvl10, self.act, t, self._pad())
        if rule == S.PASS:
            old = self.act[S.PUMP]
            for i, v in enumerate(vals):
                self.act[addr + i] = v
            if old == 0 and self.act[S.PUMP] > 0:
                self.starts = (self.starts + [t])[-4:]
        self.decisions.append({"fc": fc, "addr": addr, "vals": vals, "rule": rule})
        return rule

    def response(self, adu: bytes):
        txid, pid, length, unit, fc = struct.unpack("!HHHBB", adu[:8])
        e = self.pending.pop(txid, None)
        if e and fc == 4 and e[0] == 4 and e[1] == 0 and e[2] >= 1 and len(adu) >= 11:
            r0 = struct.unpack("!H", adu[9:11])[0]
            self.lvl10 = r0 - 0x10000 if r0 & 0x8000 else r0

    def _pad(self):
        return self.starts + [S.NO_START] * (4 - len(self.starts))
