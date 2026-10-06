"""v2 DDR image: the integer chain encoder packed for the board's external memory.

Bring-up step 3. `compile_image` turns a calibrated `IntEncoder` (the bit-exact
integer reference in `int_encoder.py`) into ONE byte image that holds everything
the encoder RTL needs: INT8 weights in the order the weight streamer reads them,
per-channel requantisation constants, the LayerNorm / GELU / softmax / pooling
tables, a per-layer program for the sequencer, and a head table. The image is
loaded with `scripts/v2/memory_link_client.py write|verify` and never changes
between requests.

`ImageMachine` executes an image using nothing but its bytes and integer
arithmetic. It is the golden model for the step-4 sequencer: its final hidden
codes and head logits must equal `IntEncoder`'s exactly (`scripts/v2/compile_image.py
check`), so any information missing from the image shows up as a mismatch.

Conventions
-----------
* Little-endian everywhere. A 16-byte memory beat holds the byte at the lowest
  address in bits [7:0], as in the memory link.
* All addresses inside the image are ABSOLUTE byte addresses in board memory
  (`base` + offset). The image must be written at the `base` it was compiled for
  (header field; default 0).
* Every section starts on a 1 KiB boundary (64 beats = one link frame and one
  engine burst); every record inside a section on a 16-byte boundary.

Layout
------
    base + 0      header (1 KiB): magic, format, dims, tile shape, section table
    program       instruction count, then 64-byte instructions
    heads         head count, then 64-byte head descriptors
    tables        softmax exp table, pooling reciprocal table
    embeddings    word rows, position rows, type vector, per-dim multipliers, LN params
    layer.<i>     the six weight streams of layer i, its LN params, its GELU table
    head.<name>   one weight stream + float32 logit scales per head

Weight stream (LINEAR operands), for W (in x out), tile TI x TO (TI % 16 == 0):
    in and out are zero-padded to multiples of TI and TO; then for every output
    tile ot (TO channels):
        channel block   TO x {bias int32, M int32}, padded to 16 bytes
        for every input tile it:
            for c in 0..TO-1: W[it*TI : it*TI+TI, ot*TO + c] as TI int8 bytes
    so a tile is TO beat-rows of TI inputs (TI/16 beats each), read once and
    applied to every token before the next one. Padded channels have bias 0, M 0.

Arithmetic (exactly `int_encoder.py`)
-------------------------------------
    requant(a, M, S)  = (a*M + 2^(S-1)) >> S   (arithmetic shift; a*M if S = 0)
    LINEAR            acc = x @ W + b (INT32); y = clamp(requant(acc, M[c], S), lo, hi);
                      optional 256-entry INT8 LUT: y = lut[y + 127]
    ADD_SKIP          r = clamp(a16 + clamp(requant(x8, M, S), +-32767), +-32767)
    LAYERNORM         mean = floor((2*sum + n) / (2n)); c = r - mean;
                      var = floor(sum(c^2) / n); std = max(isqrt(var), 1);
                      inv = floor(2^(F+16) / std); z = (c*inv + 2^15) >> 16;
                      y = clamp((z*g + b + 2^(F+7)) >> (F+8), +-127)     (F = 12)
    ATTENTION         per head h: s = q_h @ k_h^T (INT32); d = rowmax - s;
                      i = min(requant(d, Msm, Ssm), 255); e = exp[i] (0 if i = 255);
                      r = floor(2^24 / sum(e)); p = min((e*r + 2^15) >> 16, 255);
                      ctx_h = clamp(requant(p @ v_h, Mctx, Sctx), +-127)
    EMBED             r = clamp(requant(word[id], Mw[d], Sw) + requant(pos[t], Mp[d], Sp)
                      + type[d], +-32767)   (each requant clamped to +-32767 first)
    head pooling      (sum of rows * recip[count] + 2^15) >> 16, then the head's
                      LINEAR in raw INT32 mode; logit * scale[c] is the float logit.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
import zlib
from dataclasses import dataclass, field

import numpy as np

from .int_encoder import EXP_STEP, EXP_STEPS, LN_FRACTION, RESIDUAL_BITS, IntEncoder

MAGIC = b"SYSONEV2"
FORMAT = 1
BEAT = 16
SECTION_ALIGN = 1024
HEADER_BYTES = 1024
INSTR_BYTES = 64
HEAD_BYTES = 64
MAX_SECTIONS = 27              # 128 + 32 * 27 = 992 < 1024
# limits the encoder RTL is built for (rtl/v2/encoder): 17-bit requant multipliers, and
# shifts small enough that the rounding constant fits each requantiser's product width
MAX_MULTIPLIER = (1 << 17) - 1
MAX_SHIFT = {"linear": 47, "softmax": 38, "context": 39, "skip": 24}

# opcodes
EMBED, LAYERNORM, LINEAR, ATTENTION, ADD_SKIP, END = 0x01, 0x02, 0x03, 0x04, 0x05, 0x0F
OPNAMES = {EMBED: "EMBED", LAYERNORM: "LAYERNORM", LINEAR: "LINEAR", ATTENTION: "ATTENTION",
           ADD_SKIP: "ADD_SKIP", END: "END"}
# on-chip activation buffers (tokens x width); the sequencer maps them to RAMs
BUF_X, BUF_Q, BUF_K, BUF_V, BUF_CTX, BUF_R, BUF_A, BUF_G = range(8)
BUFNAMES = ["X", "Q", "K", "V", "CTX", "R", "A", "G"]
BUF_INT16 = {BUF_R, BUF_A}                       # everything else is INT8
# LINEAR output modes
OUT_CLAMP, OUT_RAW32 = 0, 1
# head kinds
HEAD_SEGMENT, HEAD_TOKEN, HEAD_ALL = 0, 1, 2     # mean of a segment / per token / mean of all
KIND_OF = {"intent": HEAD_SEGMENT, "slots": HEAD_TOKEN, "pair": HEAD_ALL}

# instruction payloads, after the 8-byte prefix <B op, B src, B src2, B dst, B layer, 3x pad>
PAYLOAD = {
    EMBED: "<IHIHHIIBIB",        # word, word_stride, pos, pos_stride, max_pos, type, Mw, Sw, Mp, Sp
    LAYERNORM: "<IHB",           # params (g int32[n], b int32[n]), n, fraction bits
    LINEAR: "<IIHHBBiiIHH",      # stream, bytes, in, out, S, mode, lo, hi, lut (0 = none), TI, TO
    ATTENTION: "<HHIBIBIH",      # heads, head_dim, Msm, Ssm, Mctx, Sctx, exp table, exp steps
    ADD_SKIP: "<IB",             # M, S
    END: "<",
}
HEADER_FMT = "<8sHHIII32sHHHHHIHHHHBBBB"  # see compile_image()
SECTION_FMT = "<16sIII4x"
HEAD_FMT = "<B15sHHIIII"       # kind, name, classes, in, stream, bytes, scales, recip


def _align(n: int, a: int) -> int:
    return (n + a - 1) // a * a


def _fits(name: str, v: np.ndarray, lo: int, hi: int) -> np.ndarray:
    v = np.asarray(v)
    if v.size and (v.min() < lo or v.max() > hi):
        raise OverflowError(f"{name}: range [{v.min()}, {v.max()}] outside [{lo}, {hi}]")
    return v


def _i32(name, v):
    return _fits(name, np.asarray(v, dtype=np.float64), -(1 << 31), (1 << 31) - 1).astype("<i4")


def _u32(name, v):
    return _fits(name, np.asarray(v, dtype=np.float64), 0, (1 << 32) - 1).astype("<u4")


def _scalar_m(name: str, ms, max_shift: int = 63) -> tuple[int, int]:
    M, S = ms
    M = int(np.atleast_1d(M)[0])
    _fits(name + ".M", np.array([M]), 0, MAX_MULTIPLIER)
    _fits(name + ".S", np.array([S]), 0, max_shift)
    return M, int(S)


# ------------------------------------------------------------------- packing

def weight_stream(W: np.ndarray, bias: np.ndarray, M: np.ndarray, ti: int, to: int) -> bytes:
    """Tiled weight stream for W (in x out) INT8; see module docstring."""
    if ti % BEAT:
        raise ValueError("tile_in must be a multiple of 16")
    n_in, n_out = W.shape
    pi, po = _align(n_in, ti), _align(n_out, to)
    Wp = np.zeros((pi, po), dtype=np.int8)
    Wp[:n_in, :n_out] = _fits("weights", W, -127, 127).astype(np.int8)
    bp = np.zeros(po, dtype="<i4")
    bp[:n_out] = _i32("bias", bias)
    Mp = np.zeros(po, dtype="<i4")
    Mp[:n_out] = _fits("M", np.broadcast_to(np.asarray(M), (n_out,)), 0, MAX_MULTIPLIER)
    out = bytearray()
    for ot in range(po // to):
        cs = slice(ot * to, ot * to + to)
        blk = np.stack([bp[cs], Mp[cs]], 1).astype("<i4").tobytes()
        out += blk + bytes(_align(len(blk), BEAT) - len(blk))
        for it in range(pi // ti):
            out += np.ascontiguousarray(Wp[it * ti:it * ti + ti, cs].T).tobytes()
    return bytes(out)


def read_stream(mem: "Memory", addr: int, n_in: int, n_out: int, ti: int, to: int):
    """Inverse of weight_stream: (W int64 in x out, bias int64, M int64)."""
    pi, po = _align(n_in, ti), _align(n_out, to)
    W = np.zeros((pi, po), dtype=np.int64)
    b = np.zeros(po, dtype=np.int64)
    M = np.zeros(po, dtype=np.int64)
    blk = _align(8 * to, BEAT)
    p = addr
    for ot in range(po // to):
        cb = mem.array(p, 2 * to, "<i4").reshape(to, 2)
        b[ot * to:ot * to + to], M[ot * to:ot * to + to] = cb[:, 0], cb[:, 1]
        p += blk
        for it in range(pi // ti):
            t = mem.array(p, ti * to, "i1").reshape(to, ti)
            W[it * ti:it * ti + ti, ot * to:ot * to + to] = t.T
            p += ti * to
    return W[:n_in, :n_out], b[:n_out], M[:n_out]


@dataclass
class Builder:
    base: int
    data: bytearray = field(default_factory=lambda: bytearray(HEADER_BYTES))
    sections: list = field(default_factory=list)
    _open: tuple | None = None

    def begin(self, name: str) -> None:
        self.data += bytes(_align(len(self.data), SECTION_ALIGN) - len(self.data))
        self._open = (name, len(self.data))

    def put(self, blob: bytes) -> int:
        """Append a 16-byte-aligned record; returns its absolute address."""
        self.data += bytes(_align(len(self.data), BEAT) - len(self.data))
        addr = self.base + len(self.data)
        self.data += blob
        return addr

    def end(self) -> None:
        name, start = self._open
        self.data += bytes(_align(len(self.data), BEAT) - len(self.data))
        self.sections.append((name, self.base + start, len(self.data) - start,
                              zlib.crc32(self.data[start:]) & 0xFFFFFFFF))
        self._open = None


def _instr(op: int, *payload, src=0, src2=0, dst=0, layer=0) -> bytes:
    b = struct.pack("<BBBBB3x", op, src, src2, dst, layer) + struct.pack(PAYLOAD[op], *payload)
    assert len(b) <= INSTR_BYTES, (OPNAMES[op], len(b))
    return b + bytes(INSTR_BYTES - len(b))




def program_length(layers: int) -> int:
    return 2 + 11 * layers + 1


def compile_image(ie: IntEncoder, name: str, head_labels: dict | None = None, *, base: int = 0,
                  tile_in: int = 16, tile_out: int = 12,
                  max_tokens: int = 128) -> tuple[bytes, dict]:
    """Pack a calibrated IntEncoder. Returns (image bytes, manifest dict)."""
    head_labels = head_labels or {}
    H, A, d = ie.H, ie.A, ie.d
    L = len(ie.layers)
    F = ie.layers[0]["i"]["W"].shape[1]
    V, P = ie.word_q.shape[0], ie.pos_q.shape[0]
    if base % SECTION_ALIGN:
        raise ValueError("base must be a multiple of 1024")
    if LN_FRACTION > 12:
        raise ValueError("the encoder RTL's LayerNorm widths assume LN_FRACTION <= 12")
    if H % BEAT:
        raise ValueError("hidden size must be a multiple of 16")
    if max_tokens > P:
        raise ValueError(f"max_tokens {max_tokens} > {P} positions")
    bld = Builder(base)

    # program and head table first, patched in at the end (their sizes are known now)
    n_instr = program_length(L)
    n_heads = len(ie.heads)
    bld.begin("program")
    prog_addr = bld.put(bytes(BEAT + INSTR_BYTES * n_instr))
    bld.end()
    bld.begin("heads")
    head_addr = bld.put(bytes(BEAT + HEAD_BYTES * n_heads))
    bld.end()
    prog, heads, man_heads = [], [], []

    bld.begin("tables")
    exp_addr = bld.put(_fits("exp", ie.exp_table, 0, 65535).astype("<u2").tobytes())
    recip_addr = bld.put(_u32("recip", ie.recip).tobytes())
    bld.end()

    bld.begin("embeddings")
    word_addr = bld.put(_fits("word", ie.word_q, -127, 127).astype(np.int8).tobytes())
    pos_addr = bld.put(_fits("pos", ie.pos_q[:max_tokens], -127, 127).astype(np.int8).tobytes())
    type_addr = bld.put(_i32("type", ie.emb_type).tobytes())
    (Mw, Sw), (Mp, Sp) = ie.emb_word_m, ie.emb_pos_m
    mw_addr = bld.put(_i32("emb Mw", Mw).tobytes())
    mp_addr = bld.put(_i32("emb Mp", Mp).tobytes())
    eln = bld.put(_i32("emb ln g", ie.e_ln["g"]).tobytes() + _i32("emb ln b", ie.e_ln["b"]).tobytes())
    bld.end()
    prog.append(_instr(EMBED, word_addr, H, pos_addr, H, max_tokens, type_addr,
                       mw_addr, Sw, mp_addr, Sp, dst=BUF_R))
    prog.append(_instr(LAYERNORM, eln, H, LN_FRACTION, src=BUF_R, dst=BUF_X))

    for i, Lq in enumerate(ie.layers):
        bld.begin(f"layer.{i}")

        def lin(key, src, dst, lut=0):
            P_ = Lq[key]
            s = weight_stream(P_["W"], P_["b"], P_["M"], tile_in, tile_out)
            a = bld.put(s)
            _fits(f"layer {i} {key}.S", np.array([P_["S"]]), 1, MAX_SHIFT["linear"])
            return _instr(LINEAR, a, len(s), P_["W"].shape[0], P_["W"].shape[1], P_["S"],
                          OUT_CLAMP, int(P_["lo"]), int(P_["hi"]), lut, tile_in, tile_out,
                          src=src, dst=dst, layer=i)

        gelu = bld.put(np.concatenate([_fits("gelu", Lq["gelu_table"], -127, 127), [0]])
                       .astype(np.int8).tobytes())
        ln1 = bld.put(_i32("ln1 g", Lq["ln1"]["g"]).tobytes() + _i32("ln1 b", Lq["ln1"]["b"]).tobytes())
        ln2 = bld.put(_i32("ln2 g", Lq["ln2"]["g"]).tobytes() + _i32("ln2 b", Lq["ln2"]["b"]).tobytes())
        Msm, Ssm = _scalar_m("sm", Lq["sm"], MAX_SHIFT["softmax"])
        Mc, Sc = _scalar_m("ctx", Lq["ctx"], MAX_SHIFT["context"])
        M1, S1 = _scalar_m("skip1", Lq["skip1"], MAX_SHIFT["skip"])
        M2, S2 = _scalar_m("skip2", Lq["skip2"], MAX_SHIFT["skip"])
        prog += [
            lin("q", BUF_X, BUF_Q), lin("k", BUF_X, BUF_K), lin("v", BUF_X, BUF_V),
            _instr(ATTENTION, A, d, Msm, Ssm, Mc, Sc, exp_addr, EXP_STEPS,
                   src=BUF_Q, src2=BUF_K, dst=BUF_CTX, layer=i),     # V operand is BUF_V
            lin("o", BUF_CTX, BUF_A),
            _instr(ADD_SKIP, M1, S1, src=BUF_A, src2=BUF_X, dst=BUF_R, layer=i),
            _instr(LAYERNORM, ln1, H, LN_FRACTION, src=BUF_R, dst=BUF_X, layer=i),
            lin("i", BUF_X, BUF_G, lut=gelu),
            lin("f", BUF_G, BUF_A),
            _instr(ADD_SKIP, M2, S2, src=BUF_A, src2=BUF_X, dst=BUF_R, layer=i),
            _instr(LAYERNORM, ln2, H, LN_FRACTION, src=BUF_R, dst=BUF_X, layer=i),
        ]
        bld.end()
    prog.append(_instr(END))
    assert len(prog) == n_instr

    s_x = ie.s[f"{L - 1}.x2"]
    for (kind, hname), (W, sw, b) in sorted(ie.heads.items()):
        bld.begin(f"h.{kind}.{hname}"[:16])
        s = weight_stream(W, np.round(b / (s_x * sw)), np.ones(W.shape[1]), tile_in, tile_out)
        a = bld.put(s)
        scale = (s_x * sw).astype("<f4")
        sa = bld.put(scale.tobytes())
        bld.end()
        nm = f"{kind}.{hname}".encode()
        if len(nm) > 15:
            raise ValueError(f"head name too long: {nm!r}")
        heads.append(struct.pack(HEAD_FMT, KIND_OF[kind], nm, W.shape[1], W.shape[0], a, len(s),
                                 sa, recip_addr).ljust(HEAD_BYTES, b"\0"))
        man_heads.append({"kind": kind, "name": hname, "classes": int(W.shape[1]),
                          "stream": a, "scales": sa,
                          "labels": head_labels.get(kind, {}).get(hname)})

    # patch program and heads
    data = bld.data
    blob = struct.pack("<I12x", n_instr) + b"".join(prog)
    data[prog_addr - base:prog_addr - base + len(blob)] = blob
    blob = struct.pack("<I12x", n_heads) + b"".join(heads)
    data[head_addr - base:head_addr - base + len(blob)] = blob
    secs = []
    for nm, a, size, _ in bld.sections:           # recompute CRCs after patching
        secs.append((nm, a, size, zlib.crc32(data[a - base:a - base + size]) & 0xFFFFFFFF))
    data += bytes(_align(len(data), SECTION_ALIGN) - len(data))
    if len(secs) > MAX_SECTIONS:
        raise ValueError(f"{len(secs)} sections > {MAX_SECTIONS}")
    hdr = struct.pack(HEADER_FMT, MAGIC, FORMAT, HEADER_BYTES, base, len(data), 0,
                      name.encode()[:32], H, A, d, L, F, V, P, tile_in, tile_out, max_tokens,
                      LN_FRACTION, RESIDUAL_BITS, int(round(1 / EXP_STEP)), len(secs))
    hdr = hdr.ljust(128, b"\0")
    for nm, a, size, crc in secs:
        hdr += struct.pack(SECTION_FMT, nm.encode()[:16], a, size, crc)
    data[:len(hdr)] = hdr
    crc = zlib.crc32(data[HEADER_BYTES:]) & 0xFFFFFFFF
    data[20:24] = struct.pack("<I", crc)
    img = bytes(data)

    manifest = {
        "format": FORMAT, "name": name, "base": base, "bytes": len(img),
        "sha256": hashlib.sha256(img).hexdigest(), "body_crc32": crc,
        "dims": {"hidden": H, "heads": A, "head_dim": d, "layers": L, "ffn": F, "vocab": V,
                 "positions": P, "max_tokens": max_tokens},
        "tile": {"in": tile_in, "out": tile_out},
        "sections": [{"name": nm, "address": a, "bytes": size, "crc32": c} for nm, a, size, c in secs],
        "program": {"address": prog_addr, "instructions": n_instr},
        "heads": man_heads,
        "activation_scales": {k: float(v) for k, v in ie.s.items()},
        "output_scale": float(s_x),
    }
    return img, manifest


# ------------------------------------------------------------------ reading

class Memory:
    """Board memory as seen from the image (absolute addresses)."""

    def __init__(self, image: bytes):
        hdr = parse_header(image)
        self.base = hdr["base"]
        self.buf = memoryview(image)

    def raw(self, addr: int, n: int) -> bytes:
        o = addr - self.base
        if o < 0 or o + n > len(self.buf):
            raise IndexError(f"address {addr:#x}+{n} outside the image")
        return bytes(self.buf[o:o + n])

    def array(self, addr: int, count: int, dtype: str) -> np.ndarray:
        dt = np.dtype(dtype)
        return np.frombuffer(self.raw(addr, count * dt.itemsize), dtype=dt).astype(np.int64) \
            if dt.kind in "iu" else np.frombuffer(self.raw(addr, count * dt.itemsize), dtype=dt)


def parse_header(image: bytes) -> dict:
    f = struct.unpack_from(HEADER_FMT, image, 0)
    keys = ["magic", "format", "header_bytes", "base", "bytes", "body_crc32", "name", "hidden",
            "heads", "head_dim", "layers", "ffn", "vocab", "positions", "tile_in", "tile_out",
            "max_tokens", "ln_fraction", "residual_bits", "exp_steps_per_unit", "sections"]
    h = dict(zip(keys, f))
    if h["magic"] != MAGIC:
        raise ValueError("not a SYSONEV2 image")
    if h["format"] != FORMAT:
        raise ValueError(f"image format {h['format']}, expected {FORMAT}")
    h["name"] = h["name"].rstrip(b"\0").decode()
    secs = []
    for k in range(h["sections"]):
        nm, a, size, crc = struct.unpack_from(SECTION_FMT, image, 128 + 32 * k)
        secs.append({"name": nm.rstrip(b"\0").decode(), "address": a, "bytes": size, "crc32": crc})
    h["section_table"] = secs
    return h


def verify_image(image: bytes) -> dict:
    """Header, length, body CRC and every section CRC. Raises on any mismatch."""
    h = parse_header(image)
    if len(image) != h["bytes"]:
        raise ValueError(f"image is {len(image)} bytes, header says {h['bytes']}")
    if zlib.crc32(image[HEADER_BYTES:]) & 0xFFFFFFFF != h["body_crc32"]:
        raise ValueError("body CRC mismatch")
    for s in h["section_table"]:
        o = s["address"] - h["base"]
        if zlib.crc32(image[o:o + s["bytes"]]) & 0xFFFFFFFF != s["crc32"]:
            raise ValueError(f"section {s['name']} CRC mismatch")
    return h


def decode_program(image: bytes) -> list[dict]:
    h = parse_header(image)
    mem = Memory(image)
    sec = {s["name"]: s for s in h["section_table"]}
    a = sec["program"]["address"]
    n = struct.unpack("<I", mem.raw(a, 4))[0]
    out = []
    for k in range(n):
        raw = mem.raw(a + BEAT + INSTR_BYTES * k, INSTR_BYTES)
        op, src, src2, dst, layer = struct.unpack_from("<BBBBB", raw)
        if op not in PAYLOAD:
            raise ValueError(f"instruction {k}: unknown opcode {op:#x}")
        args = struct.unpack_from(PAYLOAD[op], raw, 8)
        out.append({"op": op, "src": src, "src2": src2, "dst": dst, "layer": layer, "args": args})
    return out


def decode_heads(image: bytes) -> dict:
    h = parse_header(image)
    mem = Memory(image)
    sec = {s["name"]: s for s in h["section_table"]}
    a = sec["heads"]["address"]
    n = struct.unpack("<I", mem.raw(a, 4))[0]
    out = {}
    for k in range(n):
        kind, nm, classes, n_in, stream, size, scales, recip = struct.unpack_from(
            HEAD_FMT, mem.raw(a + BEAT + HEAD_BYTES * k, HEAD_BYTES))
        nm = nm.rstrip(b"\0").decode()
        out[nm] = {"kind": kind, "classes": classes, "in": n_in, "stream": stream, "bytes": size,
                   "scales": scales, "recip": recip}
    return out


def describe(image: bytes) -> str:
    h = verify_image(image)
    lines = [f"{h['name']}: {h['bytes']:,} bytes at {h['base']:#x}; hidden {h['hidden']}, "
             f"{h['layers']} layers x {h['heads']} heads, FFN {h['ffn']}, vocab {h['vocab']}, "
             f"tile {h['tile_in']}x{h['tile_out']}, max {h['max_tokens']} tokens"]
    for s in h["section_table"]:
        lines.append(f"  {s['name']:16s} {s['address']:#010x}  {s['bytes']:>10,} B  crc {s['crc32']:08x}")
    for k, ins in enumerate(decode_program(image)):
        a = ins["args"]
        extra = ""
        if ins["op"] == LINEAR:
            extra = f"{a[2]}->{a[3]} @ {a[0]:#x} ({a[1]:,} B) S={a[4]} [{a[6]},{a[7]}]" + \
                    (f" lut {a[8]:#x}" if a[8] else "")
        elif ins["op"] == ATTENTION:
            extra = f"{a[0]} heads x {a[1]}, softmax M={a[2]} S={a[3]}, ctx M={a[4]} S={a[5]}"
        elif ins["op"] == LAYERNORM:
            extra = f"n={a[1]} params @ {a[0]:#x}"
        elif ins["op"] == ADD_SKIP:
            extra = f"M={a[0]} S={a[1]}"
        elif ins["op"] == EMBED:
            extra = f"word @ {a[0]:#x}, pos @ {a[2]:#x}, max {a[4]} tokens"
        if ins["op"] in (ATTENTION, ADD_SKIP):
            bufs = f"{BUFNAMES[ins['src']]},{BUFNAMES[ins['src2']]}->{BUFNAMES[ins['dst']]}"
        elif ins["op"] in (LINEAR, LAYERNORM):
            bufs = f"{BUFNAMES[ins['src']]}->{BUFNAMES[ins['dst']]}"
        else:
            bufs = "->R" if ins["op"] == EMBED else ""
        lines.append(f"  {k:3d} L{ins['layer']} {OPNAMES[ins['op']]:9s} {bufs:10s} {extra}")
    return "\n".join(lines)


# ---------------------------------------------------------------- execution

def _rq(a: np.ndarray, M, S: int) -> np.ndarray:
    a = a.astype(np.int64) * np.asarray(M, dtype=np.int64)
    return (a + (1 << (S - 1))) >> S if S > 0 else a


def _isqrt(v: np.ndarray) -> np.ndarray:
    return np.array([math.isqrt(int(x)) for x in v.ravel()], dtype=np.int64).reshape(v.shape)


class ImageMachine:
    """Runs an image's program with integer NumPy, reading every operand from the image.

    The golden model for the encoder sequencer. `stats` records the widest value seen
    at each kind of intermediate (bits needed, sign included) to size the RTL.
    """

    def __init__(self, image: bytes):
        self.h = verify_image(image)
        self.mem = Memory(image)
        self.program = decode_program(image)
        self.heads = decode_heads(image)
        self.stats: dict[str, int] = {}
        self.clipped: dict[str, int] = {}      # values that hit a clamp, per kind
        self.counted: dict[str, int] = {}      # values that went through that clamp
        self._cache: dict = {}

    def _note(self, key: str, v: np.ndarray) -> None:
        if v.size:
            m = int(np.abs(v).max())
            self.stats[key] = max(self.stats.get(key, 0), m)

    def _clip(self, key: str, v: np.ndarray, lo: int, hi: int) -> np.ndarray:
        self.clipped[key] = self.clipped.get(key, 0) + int(((v < lo) | (v > hi)).sum())
        self.counted[key] = self.counted.get(key, 0) + v.size
        return np.clip(v, lo, hi)

    def _stream(self, addr, n_in, n_out, ti, to):
        k = ("s", addr)
        if k not in self._cache:
            self._cache[k] = read_stream(self.mem, addr, n_in, n_out, ti, to)
        return self._cache[k]

    def _linear(self, x, a):
        stream, _, n_in, n_out, S, mode, lo, hi, lut, ti, to = a
        W, b, M = self._stream(stream, n_in, n_out, ti, to)
        acc = x @ W + b
        self._note("linear_acc", acc)
        if mode == OUT_RAW32:
            return acc
        y = self._clip("linear_int8" if hi < 128 else "linear_int16", _rq(acc, M, S), lo, hi)
        if lut:
            y = self.mem.array(lut, 256, "i1")[y + 127]
        return y

    def _layernorm(self, r, a):
        addr, n, frac = a
        g = self.mem.array(addr, n, "<i4")
        b = self.mem.array(addr + 4 * n, n, "<i4")
        tot = r.sum(-1, keepdims=True)
        mean = (2 * tot + n) // (2 * n)
        c = r - mean
        sq = (c * c).sum(-1, keepdims=True)
        self._note("ln_sum_sq", sq)
        var = sq // n
        std = np.maximum(_isqrt(var), 1)
        inv = (1 << (frac + 16)) // std
        z = (c * inv + (1 << 15)) >> 16
        y = z * g + b
        self._note("ln_affine", y)
        y = (y + (1 << (frac + 7))) >> (frac + 8)
        return self._clip("layernorm", y, -127, 127)

    def _attention(self, q, k, v, a):
        A, d, Msm, Ssm, Mc, Sc, exp_addr, steps = a
        exp = self.mem.array(exp_addr, steps, "<u2")
        out = np.empty_like(q)
        for hd in range(A):
            sl = slice(hd * d, hd * d + d)
            s = q[:, sl] @ k[:, sl].T
            self._note("attn_score", s)
            dist = s.max(-1, keepdims=True) - s
            idx = np.minimum(_rq(dist, Msm, Ssm), steps - 1)
            e = np.where(idx >= steps - 1, 0, exp[idx])
            tot = e.sum(-1, keepdims=True)
            r = (1 << 24) // tot
            p = np.minimum((e * r + (1 << 15)) >> 16, 255)
            pv = p @ v[:, sl]
            self._note("attn_pv", pv)
            out[:, sl] = self._clip("context", _rq(pv, Mc, Sc), -127, 127)
        return out

    def hidden(self, ids: np.ndarray, on_step=None) -> np.ndarray:
        """Run the program; `on_step(k, instruction, buffers)` after every instruction."""
        ids = np.asarray(ids, dtype=np.int64)
        n = len(ids)
        H = self.h["hidden"]
        buf: dict[int, np.ndarray] = {}
        for k, ins in enumerate(self.program):
            op, a = ins["op"], ins["args"]
            if op == EMBED:
                word, ws, pos, ps, max_pos, typ, mw, sw, mp, sp = a
                if n > max_pos:
                    raise ValueError(f"{n} tokens > {max_pos}")
                rows = np.stack([self.mem.array(word + ws * int(t), H, "i1") for t in ids])
                prow = self.mem.array(pos, n * ps, "i1").reshape(n, ps)[:, :H]
                Mw = self.mem.array(mw, H, "<i4")
                Mp = self.mem.array(mp, H, "<i4")
                ty = self.mem.array(typ, H, "<i4")
                r = (np.clip(_rq(rows, Mw, sw), -32767, 32767)
                     + np.clip(_rq(prow, Mp, sp), -32767, 32767) + ty)
                buf[ins["dst"]] = self._clip("residual", r, -32767, 32767)
            elif op == LAYERNORM:
                buf[ins["dst"]] = self._layernorm(buf[ins["src"]], a)
            elif op == LINEAR:
                buf[ins["dst"]] = self._linear(buf[ins["src"]], a)
            elif op == ATTENTION:
                buf[ins["dst"]] = self._attention(buf[ins["src"]], buf[ins["src2"]], buf[BUF_V], a)
            elif op == ADD_SKIP:
                M, S = a
                sk = np.clip(_rq(buf[ins["src2"]], M, S), -32767, 32767)
                buf[ins["dst"]] = self._clip("residual", buf[ins["src"]] + sk, -32767, 32767)
            elif op == END:
                break
            if on_step is not None:
                on_step(k, ins, buf)
        return buf[BUF_X]

    def head_logits(self, x: np.ndarray, head: str, rows: np.ndarray | None = None):
        """INT32 logits and float32 per-class scales, as IntEncoder.head_logits."""
        hd = self.heads[head]
        W, b, _ = self._stream(hd["stream"], hd["in"], hd["classes"], self.h["tile_in"],
                               self.h["tile_out"])
        scale = self.mem.array(hd["scales"], hd["classes"], "<f4").astype(np.float64)
        x = np.asarray(x, dtype=np.int64)
        if hd["kind"] == HEAD_TOKEN:
            return x[rows] @ W + b, scale
        rows = np.arange(len(x)) if rows is None else rows
        recip = self.mem.array(hd["recip"] + 4 * len(rows), 1, "<u4")[0]
        pooled = (x[rows].sum(0) * recip + (1 << 15)) >> 16
        return pooled @ W + b, scale
