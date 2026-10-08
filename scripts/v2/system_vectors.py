"""Vectors and checker for the whole-request simulation (simulation/v2/encoder_system_tb.sv).

    ../mlenv/bin/python scripts/v2/system_vectors.py --name bert-mini-slots4
    cd simulation/v2 && make system            # runs the testbench, then --check

Bring-up step 5, heads on the host. The DDR model starts with the image loaded (as
`memory_link_client.py write` leaves the board); for every chain the host traffic is
exactly what `scripts/v2/sysone_v2_client.py` sends, built with the same code
(src/sysone/v2/encoder_client.py):

    WRITE  the token ids (UINT16) at the request area
    RUN    descriptor: program, n, H, ids address, result address
    READ   X (n x H INT8) from the result address, 64 beats per frame

The checker decodes every reply with the host decoder: the RUN DONE must report
status 0 and stop at the END instruction, and X must equal ImageMachine's final
hidden state bit for bit; then the heads run on the host from that X. It prints the
encoder clock counts the board reported (board-side figures, not Ethernet ones).

Chains: --tokens picks lengths of synthetic chains (random ids); with the corpora
and tokenizer present, --real adds one real test chain per dataset.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sysone.v2 import ddr_image as di                    # noqa: E402
from sysone.v2 import memory_protocol as mp              # noqa: E402
from sysone.v2.encoder_client import RequestLayout, request_frames   # noqa: E402

HOST = bytes.fromhex("0a0000000001")
OUT = ROOT / "simulation" / "v2" / "vectors" / "system"


def chains(args, m) -> list[np.ndarray]:
    rng = np.random.default_rng(args.seed)
    vocab = m.h["vocab"]
    out = []
    for n in args.tokens:
        ids = rng.integers(1000, vocab, n)
        ids[0], ids[-1] = 101, 102
        out.append(ids)
    if args.real:
        sys.path.insert(0, str(ROOT / "scripts" / "v2"))
        from encoder_vectors import real_chains          # noqa: E402
        import random
        out += real_chains(args.name, random.Random(args.seed), m.h["max_tokens"])[:args.real]
    return out


def build(args):
    img = (ROOT / "export" / "v2" / "image" / args.name / f"{args.name}.img").read_bytes()
    m = di.ImageMachine(img)
    layout = RequestLayout.for_image(m.h, len(img))
    frames, expected = [], []
    seq = 1000
    for ids in chains(args, m):
        reqs, seq = request_frames(layout, ids, m.h["hidden"], seq, HOST)
        frames += [f for f, _ in reqs]
        expected.append({"ids": [int(t) for t in ids], "kinds": [k for _, k in reqs]})
    return img, m, layout, frames, expected


def write_vectors(img, frames) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "image.hex", "w") as f:
        for o in range(0, len(img), 16):
            f.write(img[o:o + 16][::-1].hex() + "\n")
    words = []
    for frame in frames:
        words += [f"{b:03x}" for b in frame]
        words.append("100")
    (OUT / "memory_requests.hex").write_text("\n".join(words) + "\n")
    (OUT / "memory_expect.hex").write_text("\n".join("1" for _ in frames) + "\n")
    (OUT / "memory_frame_count.hex").write_text(f"{len(frames):08x}\n")


def check(m, expected) -> int:
    path = ROOT / "simulation" / "v2" / "system_responses.hex"
    words = [int(w, 16) for w in path.read_text().split()]
    replies, cur = [], []
    for w in words:
        if w == 0x100:
            replies.append(bytes(cur))
            cur = []
        else:
            cur.append(w)
    end_index = next(k for k, ins in enumerate(m.program) if ins["op"] == di.END)
    H = m.h["hidden"]
    errors, k = 0, 0
    report = []
    for case, e in enumerate(expected):
        n = len(e["ids"])
        msgs = []
        for kind in e["kinds"]:
            if k >= len(replies):
                print(f"case {case}: missing replies")
                return 1
            msgs.append(mp.decode(replies[k]))
            k += 1
        if [x.kind for x in msgs] != e["kinds"]:
            print(f"case {case}: reply kinds {[hex(x.kind) for x in msgs]}")
            errors += 1
            continue
        run = next(x for x in msgs if x.kind == mp.RUN_DONE)
        res = mp.RunResult.parse(run.data)
        x_bytes = b"".join(x.data for x in msgs if x.kind == mp.READ_DATA)[:n * H]
        x = np.frombuffer(x_bytes, dtype=np.int8).reshape(n, H).astype(np.int64)
        want = m.hidden(np.asarray(e["ids"]))
        bad = int((x != want).sum())
        ok = res.status == 0 and res.stopped_at == end_index and bad == 0
        errors += 0 if ok else 1
        heads = {nm: m.head_logits(x, nm, np.arange(n))[0].shape for nm in sorted(m.heads)}
        report.append({"tokens": n, "status": res.status, "stopped_at": res.stopped_at,
                       "encoder_clocks": res.encoder_clocks, "total_clocks": res.total_clocks,
                       "mismatching_bytes": bad})
        print(f"case {case}: {n:3d} tokens, status {res.status}, stopped at {res.stopped_at} "
              f"(END is {end_index}), X {'bit-exact' if bad == 0 else f'{bad} bytes differ'}; "
              f"board clocks: encoder {res.encoder_clocks:,}, request {res.total_clocks:,} "
              f"({res.total_clocks / 75e3:.1f} ms at 75 MHz); heads on the host: {len(heads)}")
    if k != len(replies):
        print(f"{len(replies) - k} extra replies")
        errors += 1
    out = ROOT / "simulation" / "v2" / "system_report.json"
    out.write_text(json.dumps(report, indent=1))
    if errors:
        print(f"FAIL: {errors} problems")
        return 1
    print(f"PASS: {len(expected)} requests through the RMII pins, X bit-exact, every reply decoded")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="bert-mini-slots4")
    ap.add_argument("--tokens", type=int, nargs="*", default=[12, 1])
    ap.add_argument("--real", type=int, default=0, help="real test chains to add (needs corpora)")
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        saved = json.loads((OUT / "cases.json").read_text())
        args.name, args.tokens, args.real, args.seed = (saved["name"], saved["tokens"],
                                                        saved["real"], saved["seed"])
    img, m, layout, frames, expected = build(args)
    if args.check:
        return check(m, expected)
    write_vectors(img, frames)
    (OUT / "cases.json").write_text(json.dumps({"name": args.name, "tokens": args.tokens,
                                                "real": args.real, "seed": args.seed}))
    print(f"{len(expected)} requests, {len(frames)} frames, image {len(img):,} bytes -> {OUT}; "
          f"ids at {layout.ids:#x}, X at {layout.result:#x}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
