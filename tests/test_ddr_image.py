"""v2 DDR image (bring-up step 3): format round trips and bit-exact execution.

Uses a small random BERT so it runs in the board flow's NumPy-only environment
(no torch, no corpora). The real models are checked by
`scripts/v2/compile_image.py check`.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sysone.v2 import ddr_image as di                     # noqa: E402
from sysone.v2.int_encoder import FloatEncoder, IntEncoder  # noqa: E402


class _T:
    """Stands in for a torch tensor in FloatEncoder's state dict."""

    def __init__(self, a):
        self.a = a

    def detach(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self.a


def _tiny(H=32, A=2, L=2, F=64, V=100, P=40, seed=0):
    rng = np.random.default_rng(seed)
    st = {}
    p = "encoder."

    def put(k, *shape, scale=0.2, one=False):
        st[p + k] = _T((1.0 if one else 0.0) + rng.normal(0, scale, shape))

    put("embeddings.word_embeddings.weight", V, H, scale=0.5)
    put("embeddings.position_embeddings.weight", P, H, scale=0.2)
    put("embeddings.token_type_embeddings.weight", 2, H, scale=0.1)
    put("embeddings.LayerNorm.weight", H, scale=0.1, one=True)
    put("embeddings.LayerNorm.bias", H, scale=0.05)
    for i in range(L):
        q = f"encoder.layer.{i}."
        for k in ("attention.self.query", "attention.self.key", "attention.self.value",
                  "attention.output.dense"):
            put(q + k + ".weight", H, H)
            put(q + k + ".bias", H, scale=0.05)
        put(q + "intermediate.dense.weight", F, H)
        put(q + "intermediate.dense.bias", F, scale=0.05)
        put(q + "output.dense.weight", H, F, scale=0.1)
        put(q + "output.dense.bias", H, scale=0.05)
        for k in ("attention.output.LayerNorm", "output.LayerNorm"):
            put(q + k + ".weight", H, scale=0.1, one=True)
            put(q + k + ".bias", H, scale=0.05)
    heads = {"intent": {"clinc": list(range(7))}, "slots": {"atis": list(range(5))},
             "pair": {"sick": list(range(3))}}
    for kind, hs in heads.items():
        for n, labs in hs.items():
            st[f"{kind}.{n}.weight"] = _T(rng.normal(0, 0.3, (len(labs), H)))
            st[f"{kind}.{n}.bias"] = _T(rng.normal(0, 0.1, len(labs)))
    cfg = SimpleNamespace(hidden_size=H, num_attention_heads=A, layer_norm_eps=1e-12,
                          num_hidden_layers=L)
    fe = FloatEncoder(st, cfg, heads)
    fe.trace = {}
    for _ in range(8):
        fe.hidden(rng.integers(0, V, rng.integers(5, P)))
    trace, fe.trace = fe.trace, None
    return IntEncoder(fe, trace), rng


@pytest.fixture(scope="module")
def tiny():
    ie, rng = _tiny()
    img, man = di.compile_image(ie, "tiny", tile_in=16, tile_out=12, max_tokens=32)
    return ie, img, man, rng


def test_weight_stream_round_trip_odd_shapes():
    rng = np.random.default_rng(3)
    for n_in, n_out, ti, to in [(37, 29, 16, 12), (256, 256, 16, 12), (64, 5, 32, 32), (16, 1, 16, 1)]:
        W = rng.integers(-127, 128, (n_in, n_out))
        b = rng.integers(-2**31, 2**31 - 1, n_out)
        M = rng.integers(0, 2**17, n_out)
        s = di.weight_stream(W, b, M, ti, to)
        assert len(s) % 16 == 0
        img = bytearray(s)
        mem = SimpleNamespace(array=lambda a, c, dt: np.frombuffer(
            bytes(img[a:a + c * np.dtype(dt).itemsize]), dtype=dt).astype(np.int64))
        W2, b2, M2 = di.read_stream(mem, 0, n_in, n_out, ti, to)
        assert np.array_equal(W, W2) and np.array_equal(b, b2) and np.array_equal(M, M2)


def test_layout(tiny):
    _, img, man, _ = tiny
    h = di.verify_image(img)
    assert len(img) % 1024 == 0 and h["bytes"] == len(img) == man["bytes"]
    for s in h["section_table"]:
        assert s["address"] % 1024 == 0
    names = [s["name"] for s in h["section_table"]]
    assert names[:4] == ["program", "heads", "tables", "embeddings"]
    prog = di.decode_program(img)
    assert len(prog) == di.program_length(2) and prog[-1]["op"] == di.END
    assert set(di.decode_heads(img)) == {"intent.clinc", "slots.atis", "pair.sick"}


def test_crc_catches_one_flipped_byte(tiny):
    _, img, man, _ = tiny
    bad = bytearray(img)
    bad[man["sections"][3]["address"] + 100] ^= 1        # inside the embeddings
    with pytest.raises(ValueError):
        di.verify_image(bytes(bad))


def test_base_address_relocates(tiny):
    ie, img, _, rng = tiny
    img2, _ = di.compile_image(ie, "tiny", base=0x0400_0000, tile_in=16, tile_out=12, max_tokens=32)
    assert di.parse_header(img2)["base"] == 0x0400_0000
    ids = rng.integers(0, 100, 20)
    assert np.array_equal(di.ImageMachine(img).hidden(ids), di.ImageMachine(img2).hidden(ids))


def test_image_machine_is_bit_exact(tiny):
    ie, img, _, rng = tiny
    m = di.ImageMachine(img)
    for n in (1, 2, 7, 31, 32):
        ids = rng.integers(0, 100, n)
        x = ie.hidden(ids)
        y = m.hidden(ids)
        assert np.array_equal(x, y), n
        for kind, name, rows in [("intent", "clinc", np.arange(n)), ("slots", "atis", np.arange(n)),
                                 ("pair", "sick", np.arange(n))]:
            a, sa = ie.head_logits(x, kind, name, rows)
            b, sb = m.head_logits(y, f"{kind}.{name}", rows)
            assert np.array_equal(a, b)
            assert np.allclose(sa, sb, rtol=1e-6)
    with pytest.raises(ValueError):
        m.hidden(rng.integers(0, 100, 33))                  # longer than max_tokens


def test_head_program_matches_head_logits(tiny):
    """POOL + raw-INT32 LINEAR (heads on the FPGA) give exactly head_logits (heads on the host)."""
    _, img, _, rng = tiny
    m = di.ImageMachine(img)
    heads = di.decode_heads(img)
    names = sorted(heads)
    for n in (1, 5, 32):
        ids = rng.integers(0, 100, n)
        x = m.hidden(ids)
        cuts = sorted(set(rng.integers(1, n, 2).tolist())) if n > 2 else []
        bounds = [0] + cuts + [n]
        segments = [(a, b) for a, b in zip(bounds, bounds[1:]) if b > a]
        blob, what = di.head_program(heads, names, n, segments, 16, 12)
        program = di.decode_instructions(blob)
        assert program[-1]["op"] == di.END and len(program) == len(what) + 1
        got = {}

        def on_step(k, ins, buf):
            if what[k]["kind"] == "logits":
                got[what[k]["head"]] = buf[di.BUF_A].copy()

        m.run(program, {di.BUF_X: x}, on_step=on_step)
        for nm in names:
            kind = heads[nm]["kind"]
            if kind == di.HEAD_TOKEN:
                want, _ = m.head_logits(x, nm, np.arange(n))
            elif kind == di.HEAD_ALL:
                want = m.head_logits(x, nm)[0][None]
            else:
                want = np.stack([m.head_logits(x, nm, np.arange(a, b))[0] for a, b in segments])
            assert np.array_equal(got[nm], want), nm


def test_overflow_is_refused():
    ie, _ = _tiny(seed=1)
    ie.layers[0]["q"]["b"] = ie.layers[0]["q"]["b"] + 2.0**40
    with pytest.raises(OverflowError):
        di.compile_image(ie, "tiny", max_tokens=32)


def test_header_magic():
    with pytest.raises(ValueError):
        di.parse_header(struct.pack("<8s", b"NOTANIMG") + bytes(1016))
