"""Host side of a v2 request (heads on the host), without a board."""

import numpy as np

from sysone.v2 import ddr_image as di
from sysone.v2 import memory_protocol as mp
from sysone.v2.encoder_client import LocalEncoder, RequestLayout, ids_bytes, request_frames
from sysone.v2.host_heads import Heads, build_chain, predict, spans
from sysone.v2.wordpiece import WordPiece

from test_ddr_image import _tiny


def _wp():
    vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]"] + [f"w{i}" for i in range(96)]
    return WordPiece({w: i for i, w in enumerate(vocab)})


def test_run_descriptor_and_result_round_trip():
    d = mp.run_descriptor(0x400, 12, 256, 0xB00000, 0xB01000)
    assert len(d) == 16
    f = mp.run_frame(7, d, bytes(6))
    m = mp.decode(f)
    assert (m.kind, m.sequence, m.beats, m.data) == (mp.RUN, 7, 1, d)
    r = mp.RunResult(123, 456, 1, 46)
    assert mp.RunResult.parse(r.pack()) == r


def test_request_frames():
    h = {"section_table": [{"name": "program", "address": 0x400}], "base": 0, "hidden": 32,
         "max_tokens": 32}
    lay = RequestLayout.for_image(h, 3 << 20 | 5)
    assert lay.ids == 4 << 20 and lay.result == lay.ids + 4096
    ids = np.arange(20) + 4
    frames, seq = request_frames(lay, ids, 32, 10, bytes(6))
    kinds = [k for _, k in frames]
    assert kinds == [mp.WRITE_ACK, mp.RUN_DONE] + [mp.READ_DATA]          # 20 x 32 B = 40 beats
    w = mp.decode(frames[0][0])
    assert w.data == ids_bytes(ids) and len(w.data) == 48
    assert seq == 13


def test_build_chain_rows_and_dialogue_truncation():
    wp = _wp()
    c = build_chain(wp, [["w1", "w2"], ["w3"]], "multi", 32)
    assert c.ids == [2, 5, 6, 3, 7, 3]
    assert c.seg == [-1, 0, 0, -1, 1, -1]
    assert c.word_rows == {0: [1, 2], 1: [4]}
    turns = [[f"w{i}"] * 10 for i in range(5)]
    d = build_chain(wp, turns, "dialogue", 32)          # 5 x 11 > 31: oldest turns dropped
    assert min(d.kept) == 3 and len(d.ids) <= 32
    assert spans(["B-a", "I-a", "O", "B-b", "I-a"]) == {(0, 2, "a"), (3, 4, "b"), (4, 5, "a")}


def test_local_encoder_and_heads():
    ie, rng = _tiny()
    img, man = di.compile_image(ie, "tiny", tile_in=16, tile_out=12, max_tokens=32)
    for h in man["heads"]:
        h["labels"] = [f"{h['name']}{i}" for i in range(h["classes"])]
    enc = LocalEncoder(img)
    heads = Heads(man, enc.machine)
    wp = _wp()
    chain = build_chain(wp, [["w1", "w2", "w3"]], "slots", 32)
    out = enc.encode(chain.ids)
    preds = predict(heads, out.x, chain, "clinc")
    assert len(preds) == 1 and preds[0].labels[0].startswith("clinc")
    lg, _ = enc.machine.head_logits(out.x, "intent.clinc", np.array([1, 2, 3]))
    assert np.array_equal(preds[0].integer_logits[0], lg)


def test_route_on_the_real_image():
    """auto routing on the bert-mini-slots4 image (skipped when the export is absent)."""
    import json
    from pathlib import Path
    import pytest
    from sysone.v2.host_heads import route
    root = Path(__file__).resolve().parents[1]
    d = root / "export" / "v2" / "image" / "bert-mini-slots4"
    if not (d / "bert-mini-slots4.img").exists():
        pytest.skip("image not built")
    m = di.ImageMachine((d / "bert-mini-slots4.img").read_bytes())
    heads = Heads(json.loads((d / "manifest.json").read_text()), m,
                  json.loads((d / "decision.json").read_text()))
    wp = WordPiece.from_file(root / "export" / "v2" / "chain" / "bert-mini-slots4" / "tokenizer.json")
    want = {"how should I build a h-bridge circuit?": "out_of_scope",
            "show me flights from boston to denver tomorrow morning": "atis",
            "what is the weather in chicago": "sgd",
            "set a timer for ten minutes": "clinc"}
    for text, decision in want.items():
        chain = build_chain(wp, [text.split()], "dialogue", 128)
        assert route(heads, m.hidden(np.asarray(chain.ids)), chain).decision == decision, text


def test_sentences_and_pack():
    from sysone.v2.host_heads import pack, sentences
    s = sentences("w1 w2. W3 w4 w5! W6?\n\nw7 w8")
    assert s == ["w1 w2.", "W3 w4 w5!", "W6?", "w7 w8"]
    wp = _wp()
    text = " ".join(f"w{i % 90}" for i in range(300))       # one 300-word "sentence"
    chains = pack(wp, ["w1 w2", text, "w3"], max_len=32)
    for c in chains:                                         # every request fits
        assert 1 + sum(len(wp.word_pieces(u)) + 1 for u in c) <= 32
    flat = [w for c in chains for u in c for w in u]
    assert flat == ["w1", "w2"] + text.split() + ["w3"]     # nothing lost or reordered
