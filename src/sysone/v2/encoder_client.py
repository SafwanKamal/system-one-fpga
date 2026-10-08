"""Host side of one v2 encoder request (heads on the host).

The board (nexys4ddr_link_top with ENCODER = 1) holds the DDR image, loaded once with
`memory_link_client.py write`. A request is three steps on the memory link
(src/sysone/v2/memory_protocol.py):

    WRITE  the token ids (UINT16, little-endian) to the request area
    RUN    run descriptor -> the board runs the image's program and writes X
    READ   X, the final hidden state (n x H INT8), from the result area

and the host finishes with the heads (`ImageMachine.head_logits`, exact: the same
integers the integer reference produces), then labels.

The request area sits after the image, at the next 1 MiB boundary: ids there,
X 4 KiB above. Nothing else on the board is written by a request.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import ddr_image as di
from . import memory_protocol as mp

REQUEST_ALIGN = 1 << 20
RESULT_OFFSET = 4096


@dataclass(frozen=True)
class RequestLayout:
    program: int                 # the image's program section
    ids: int                     # token ids, n UINT16
    result: int                  # X, n x H INT8
    hidden: int
    max_tokens: int

    @classmethod
    def for_image(cls, header: dict, image_bytes: int) -> "RequestLayout":
        program = next(s["address"] for s in header["section_table"] if s["name"] == "program")
        end = header["base"] + image_bytes
        area = (end + REQUEST_ALIGN - 1) // REQUEST_ALIGN * REQUEST_ALIGN
        return cls(program, area, area + RESULT_OFFSET, header["hidden"], header["max_tokens"])

    def descriptor(self, n: int) -> bytes:
        return mp.run_descriptor(self.program, n, self.hidden, self.ids, self.result)


def ids_bytes(ids) -> bytes:
    raw = np.asarray(ids, dtype="<u2").tobytes()
    return raw + bytes(-len(raw) % mp.BEAT_BYTES)


def check_ids(layout: RequestLayout, ids, vocab: int) -> np.ndarray:
    ids = np.asarray(ids, dtype=np.int64)
    if not 1 <= len(ids) <= layout.max_tokens:
        raise ValueError(f"{len(ids)} tokens: the image takes 1..{layout.max_tokens}")
    if ids.min() < 0 or ids.max() >= vocab:
        raise ValueError("token id outside the vocabulary")
    return ids


def request_frames(layout: RequestLayout, ids, hidden: int, seq: int, host: bytes,
                   with_fcs: bool = True):
    """The frames of one request, in order, with the reply type each expects.

    Returns ([(frame, reply kind)], next sequence number). Used by the simulation
    vectors; `EncoderBoard` sends the same three steps through a live link.
    """
    out = []
    data = ids_bytes(ids)
    for off in range(0, len(data), mp.MAX_BEATS * mp.BEAT_BYTES):
        seq += 1
        out.append((mp.write_frame(seq, layout.ids + off, data[off:off + mp.MAX_BEATS * 16], host,
                                   with_fcs=with_fcs), mp.WRITE_ACK))
    seq += 1
    out.append((mp.run_frame(seq, layout.descriptor(len(ids)), host, with_fcs=with_fcs),
                mp.RUN_DONE))
    total = -(-len(ids) * hidden // mp.BEAT_BYTES)
    for b in range(0, total, mp.MAX_BEATS):
        seq += 1
        out.append((mp.read_frame(seq, layout.result + 16 * b, min(mp.MAX_BEATS, total - b), host,
                                  with_fcs=with_fcs), mp.READ_DATA))
    return out, seq


@dataclass
class Encoded:
    x: np.ndarray                # n x H final hidden state (INT8 values as int64)
    run: mp.RunResult


class EncoderBoard:
    """One image on one board. `link` has write(address, data), read(address, n) and
    run(descriptor, timeout) -> RunResult (scripts/v2/memory_link_client.py Link)."""

    local = False

    def __init__(self, link, image: bytes):
        self.link = link
        self.machine = di.ImageMachine(image)
        self.layout = RequestLayout.for_image(self.machine.h, len(image))

    def encode(self, ids, timeout: float = 5.0) -> Encoded:
        ids = check_ids(self.layout, ids, self.machine.h["vocab"])
        self.link.write(self.layout.ids, ids_bytes(ids))
        res = self.link.run(self.layout.descriptor(len(ids)), timeout)
        if res.status:
            raise RuntimeError(f"board run failed: status {res.status:#x} at instruction {res.stopped_at}")
        H = self.layout.hidden
        raw = self.link.read(self.layout.result, len(ids) * H)
        x = np.frombuffer(raw, dtype=np.int8).reshape(len(ids), H).astype(np.int64)
        return Encoded(x, res)


class LocalEncoder:
    """The same interface without a board: ImageMachine runs the program (bit-exact
    with the RTL), for testing the host side and as the reference on the board."""

    local = True

    def __init__(self, image: bytes):
        self.machine = di.ImageMachine(image)
        self.layout = RequestLayout.for_image(self.machine.h, len(image))

    def encode(self, ids, timeout: float = 0.0) -> Encoded:
        ids = check_ids(self.layout, ids, self.machine.h["vocab"])
        return Encoded(self.machine.hidden(ids), mp.RunResult(0, 0, 0, 0))
