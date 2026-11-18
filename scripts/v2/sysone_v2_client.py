"""Host client of the v2 board: text in, labels out (heads on the host).

    # once per power-up: load the image (scripts/v2/memory_link_client.py write ... works too)
    uv run python scripts/v2/sysone_v2_client.py -i "Realtek USB FE Family Controller" load
    # the board against the golden model, random chains of several lengths
    uv run python scripts/v2/sysone_v2_client.py -i "..." check --tokens 1 12 64 128
    # one request
    uv run python scripts/v2/sysone_v2_client.py -i "..." run --dataset atis "show me flights from denver to boston tomorrow"
    uv run python scripts/v2/sysone_v2_client.py -i "..." run --dataset auto "book me a table for two at an italian place"
    # v3 images (embedding head): your own intents from a few examples each, no retraining
    uv run python scripts/v2/sysone_v2_client.py -i "..." --image minilm-l6-v3 run --dataset auto --intents my_intents.json "turn on the porch light"
    # long text: split into sentences, packed into 128-token requests, one result per sentence
    uv run python scripts/v2/sysone_v2_client.py -i "..." --image minilm-l6-v3 doc --file notes.txt --query "when is the meeting"
    uv run python scripts/v2/sysone_v2_client.py -i "..." run --dataset sgd "i need a table for two" "what time?" "7 pm please"
    uv run python scripts/v2/sysone_v2_client.py -i "..." run --dataset sick "a man is playing a guitar" "a person plays an instrument"
    # test sets through the board (needs the corpora: scripts/v2/fetch_v2_data.py)
    uv run python scripts/v2/sysone_v2_client.py -i "..." eval --per-dataset 50
    # any command without a board: --local (ImageMachine runs the image instead)
    # on the KR260's ARM (root; image built with --board kr260 --base 0x60000000 --suffix=-kr260):
    sudo python3 scripts/v2/sysone_v2_client.py --kr260 --image bert-mini-slots4-kr260 load

Needs the encoder bitstream (create_project_v2.tcl -tclargs build encoder, then
program_board_v2.tcl encoder) and the image in the board's DDR2 at its base address.
Files: export/v2/image/<name>/{<name>.img, manifest.json} and the tokenizer
export/v2/chain/<name>/tokenizer.json. NumPy and scapy only (no torch, no transformers).

Timing: the board reports its own clock counts for every request (encoder, and the
whole request including reading the ids and writing X), printed in ms at the 75 MHz
memory clock. Host-measured times include the Ethernet link and the host's packet
path and are labelled as such; they are not the encoder's speed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "v2"))

from sysone.v2.encoder_client import EncoderBoard, LocalEncoder   # noqa: E402
from sysone.v2.host_heads import (DATASETS, CustomIntents, Heads, build_chain, pack,   # noqa: E402
                                  predict, route, sentences, spans)
from sysone.v2.wordpiece import WordPiece                          # noqa: E402

CLOCK_HZ = 75e6                       # the Nexys 4 DDR's memory clock; --clock-mhz for others
IMAGE_NAME = ""


def ms(clocks: int) -> str:
    return f"{clocks / CLOCK_HZ * 1e3:.2f} ms"


def load_files(name: str):
    d = ROOT / "export" / "v2" / "image" / name
    image = (d / f"{name}.img").read_bytes()
    manifest = json.loads((d / "manifest.json").read_text())
    model = manifest.get("model_name") or (name[:-len("-kr260")] if name.endswith("-kr260") else name)
    tok = ROOT / "export" / "v2" / "chain" / model / "tokenizer.json"
    decision = None
    for dd in (d, ROOT / "export" / "v2" / "image" / model):      # the model's rule fits every build
        if (dd / "decision.json").exists():
            decision = json.loads((dd / "decision.json").read_text())
            break
    return image, manifest, WordPiece.from_file(tok), decision


def show(preds, chain, wp_vocab=None) -> None:
    for p in preds:
        if p.head.startswith("slots"):
            tags = [f"{w}/{t}" if t != "O" else w for w, t in zip(p.words, p.labels)]
            print(f"  {p.head:13s} seg {p.segment}: {' '.join(tags)}")
        else:
            where = f"seg {p.segment}" if p.segment is not None else "chain"
            print(f"  {p.head:13s} {where}: {p.labels[0]}  (p = {p.probability[0]:.3f})")


def cmd_check(enc, args) -> int:
    m = enc.machine
    rng = np.random.default_rng(args.seed)
    ok = True
    for n in args.tokens:
        for r in range(args.repeat):
            ids = rng.integers(1000, m.h["vocab"], n)
            ids[0] = 101
            ids[-1] = 102
            t0 = time.perf_counter()
            out = enc.encode(ids, args.timeout)
            t1 = time.perf_counter()
            if args.kr260:
                print(f"KR260: encoder completed; computing integer reference for {n} tokens...", flush=True)
            want = m.hidden(ids)
            bad = int((out.x != want).sum())
            ok &= bad == 0
            where = ("local ImageMachine run, no board" if enc.local else
                     f"board: encoder {out.run.encoder_clocks:,} clocks ({ms(out.run.encoder_clocks)}), "
                     f"request {ms(out.run.total_clocks)}; host round trip {1e3 * (t1 - t0):.0f} ms "
                     f"(host path)")
            print(f"{n:3d} tokens: X {'bit-exact' if bad == 0 else f'{bad} of {want.size} values differ'}"
                  f"; {where}")
    return 0 if ok else 1


def encode_segments(enc, wp, chains_words, timeout):
    """[[segment words, ...] per chain] -> [(chain, X, encoder clocks or None)]"""
    out = []
    for segs in chains_words:
        ch = build_chain(wp, segs, "multi", enc.layout.max_tokens)
        o = enc.encode(ch.ids, timeout)
        out.append((ch, o.x, None if enc.local else o.run.encoder_clocks))
    return out


def load_custom(path, enc, heads, wp, timeout, threshold) -> CustomIntents:
    """{"intent": ["example sentence", ...], ...} -> centroids of the examples' embeddings.
    The examples are encoded by the board (packed several per request) and cached next to
    the file per image (a .npz), so the board only sees them again when the file changes."""
    import hashlib
    if not heads.has_embedding:
        raise SystemExit("--intents needs an image with the embedding head (v3)")
    raw = Path(path).read_bytes()
    spec = json.loads(raw)
    key = hashlib.sha256(raw + IMAGE_NAME.encode()).hexdigest()[:16]     # per file and image
    cache = Path(path).with_suffix(f".{key}.npz")
    names = sorted(spec)
    if cache.exists():
        z = np.load(cache)
        if list(z["names"]) == names:
            return CustomIntents(names, z["centroids"], threshold)
    examples = [(n, t) for n in names for t in spec[n]]
    sents = [t.split() for _, t in examples]
    vecs = []
    for segs in pack_words(wp, sents, enc.layout.max_tokens):
        for ch, x, _ in encode_segments(enc, wp, [segs], timeout):
            vecs += [heads.embedding(x, ch, k) for k in sorted(ch.word_rows)]
    vecs = np.stack(vecs)
    cents = []
    for n in names:
        v = vecs[[i for i, (m, _) in enumerate(examples) if m == n]].mean(0)
        cents.append(v / np.linalg.norm(v))
    cents = np.stack(cents)
    np.savez(cache, names=np.array(names), centroids=cents)
    return CustomIntents(names, cents, threshold)


def pack_words(wp, sents_words, max_len):
    return pack(wp, [" ".join(w) for w in sents_words], max_len)


def describe(r) -> str:
    if r.decision == "custom":
        return f"custom intent {r.custom[0]} (similarity {r.custom[1]:.2f})"
    if r.decision == "out_of_scope":
        return "out of scope"
    head = {p.head.split(".")[1]: p for p in r.predictions if p.head.startswith("intent")}
    main = head.get(r.decision) or head.get("clinc")
    txt = f"{r.decision}: {main.labels[0]} ({main.probability[0]:.2f})"
    sl = [p for p in r.predictions if p.head.startswith("slots")]
    if sl:
        from sysone.v2.host_heads import spans as sp
        found = [f"{name}={' '.join(sl[0].words[a:b])}" for a, b, name in sorted(sp(sl[0].labels))]
        if found:
            txt += "; " + ", ".join(found)
    return txt


def cmd_doc(enc, heads, wp, args) -> int:
    text = Path(args.file).read_text(encoding="utf-8") if args.file else " ".join(args.text)
    sents = sentences(text)
    chains = ([[u] for c in pack(wp, sents, enc.layout.max_tokens) for u in c] if args.separate
              else pack(wp, sents, enc.layout.max_tokens, args.max_segments or None))
    custom = (load_custom(args.intents, enc, heads, wp, args.timeout, args.threshold)
              if args.intents else None)
    t0 = time.perf_counter()
    done = encode_segments(enc, wp, chains, args.timeout)
    t1 = time.perf_counter()
    rows, clocks = [], 0
    for ch, x, c in done:
        clocks += c or 0
        for k in sorted(ch.word_rows):
            r = route(heads, x, ch, k, custom)
            rows.append((" ".join(ch.words[k]), r))
    words = sum(len(s.split()) for s in sents)
    tokens = sum(len(ch.ids) for ch, _, _ in done)
    print(f"{words} words, {len(sents)} sentences -> {len(rows)} segments in {len(chains)} "
          f"request(s) of <= {enc.layout.max_tokens} tokens ({tokens} tokens)")
    if not args.quiet:
        for i, (sent, r) in enumerate(rows):
            print(f"  [{i:3d}] {describe(r):60s} | {sent[:70]}")
    if heads.has_embedding:
        E = np.stack([r.embedding for _, r in rows])
        doc = E.mean(0)
        doc /= np.linalg.norm(doc)
        if args.query:
            qc = build_chain(wp, [args.query.split()], "intent", enc.layout.max_tokens)
            q = heads.embedding(enc.encode(qc.ids, args.timeout).x, qc, 0)
            sims = E @ q
            print(f"query: {args.query!r} (similarity to the whole text {float(doc @ q):.2f})")
            for i in np.argsort(-sims)[:args.top]:
                print(f"  {sims[i]:.2f}  [{i}] {rows[i][0][:100]}")
    if enc.local:
        print(f"local run (ImageMachine, no board): {1e3 * (t1 - t0):.0f} ms in NumPy")
    else:
        print(f"board: encoder {ms(clocks)} for {len(chains)} request(s); host round trips "
              f"{1e3 * (t1 - t0):.0f} ms (host path)")
    return 0


def cmd_run(enc, heads, wp, args) -> int:
    auto = args.dataset == "auto"
    segments = [s.split() for s in args.text]
    if auto:
        task = "dialogue"                # earlier segments = context; the last one is routed
    else:
        task = DATASETS[args.dataset]["task"]
        if task == "pair" and len(segments) != 2:
            raise SystemExit("a pair dataset takes exactly two sentences")
    chain = build_chain(wp, segments, task, enc.layout.max_tokens)
    t0 = time.perf_counter()
    out = enc.encode(chain.ids, args.timeout)
    t1 = time.perf_counter()
    if auto:
        custom = (load_custom(args.intents, enc, heads, wp, args.timeout, args.threshold)
                  if args.intents else None)
        routed = route(heads, out.x, chain, None, custom)
        preds = routed.predictions
    else:
        preds = predict(heads, out.x, chain, args.dataset)
    t2 = time.perf_counter()
    print(f"{len(chain.ids)} tokens, {len(chain.kept)} segment(s)")
    if auto:
        print({"out_of_scope": "  route: out of scope (CLINC below its threshold); no specialist head used",
               "clinc": "  route: CLINC intent only",
               "atis": "  route: flight request -> ATIS intent and slots",
               "sgd": "  route: service request -> SGD intent and slots",
               "hwu": "  route: assistant request -> HWU64 intent and slots",
               "custom": "  route: custom intent (embedding head, nearest example centroid)"}[routed.decision])
        if routed.custom:
            print(f"  custom        {routed.custom[0]}  (cosine similarity {routed.custom[1]:.3f})")
    show(preds, chain)
    if enc.local:
        print(f"local run (ImageMachine, no board): encoder {1e3 * (t1 - t0):.0f} ms in NumPy, "
              f"heads {1e3 * (t2 - t1):.1f} ms")
    else:
        print(f"board: encoder {ms(out.run.encoder_clocks)}, request {ms(out.run.total_clocks)}; "
              f"host: round trip {1e3 * (t1 - t0):.0f} ms (host path), "
              f"heads {1e3 * (t2 - t1):.1f} ms")
    return 0


def cmd_eval(enc, heads, wp, args) -> int:
    import random
    from sysone.v2.chain_data import IGNORE, load_all
    from sysone.v2 import eval_suite
    print("Evaluation: validating frozen suite..." if args.suite else
          "Evaluation: loading test corpora...", flush=True)
    frozen = (eval_suite.load(args.suite, args.image_sha256, args.tokenizer_sha256, heads.labels)
              if args.suite else None)
    corpus = None if frozen else load_all(hwu="intent.hwu" in heads.labels)
    by: dict[str, list] = {}
    if frozen:
        for row in frozen["cases"]:
            c = eval_suite.chain(row)
            by.setdefault(c.dataset, []).append((row["id"], c, row))
    else:
        for index, c in enumerate(corpus.test):
            by.setdefault(c.dataset, []).append((f"{c.dataset}:{index}", c, None))
    rng = random.Random(args.seed)
    print(f"Evaluation ready: {sum(len(rows) for rows in by.values())} available chains", flush=True)
    stats, clocks, exact, total = {}, [], 0, 0
    report = {"format": 1, "complete": False,
        "backend": "local" if enc.local else "kr260" if args.kr260 else "nexys4ddr",
        "image": IMAGE_NAME, "image_sha256": args.image_sha256,
        "suite_sha256": frozen["suite_sha256"] if frozen else None,
        "seed": frozen["seed"] if frozen else args.seed,
        "clock_hz": None if enc.local else CLOCK_HZ, "numpy_version": np.__version__,
        "stats": stats, "cases": [], "verification": {"exact": 0, "total": 0}}
    def save_report():
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    budget = None
    if getattr(args, "budget", None):
        from sysone.v2.timing_policy import TimingPolicy
        if enc.local:
            raise ValueError("Timing policy requires hardware measurements")
        budget = TimingPolicy(**json.loads(args.budget.read_text()))
        report["timing_policy"] = budget.metadata()
    save_report()
    for ds, chains in sorted(by.items()):
        key = "multi" if ds == "multi_clinc" else ds
        st = stats.setdefault(ds, {"ok": 0, "n": 0, "tp": 0, "fp": 0, "fn": 0})
        selected = chains if frozen else rng.sample(chains, min(args.per_dataset, len(chains)))
        for identifier, c, row in selected:
            chain = build_chain(wp, [s.words for s in c.segments], c.task, enc.layout.max_tokens)
            if row and chain.ids != row["ids"]:
                raise ValueError(f"Tokenization differs from frozen suite: {identifier}")
            start = time.perf_counter()
            if budget:
                budget.admit(args.image_sha256, CLOCK_HZ, len(chain.ids))
            out = enc.encode(chain.ids, args.timeout)
            host_ms = (time.perf_counter() - start) * 1000
            counters = enc.link.performance_counters() if args.kr260 and not enc.local else None
            clocks.append((len(chain.ids), out.run.encoder_clocks))
            matched = None
            if args.verify:
                total += 1
                want = eval_suite.reference(row) if row else enc.machine.hidden(np.asarray(chain.ids))
                matched = bool(np.array_equal(out.x, want))
                exact += int(matched)
            start = time.perf_counter()
            preds = predict(heads, out.x, chain, key)
            heads_ms = (time.perf_counter() - start) * 1000
            report["cases"].append({"id": identifier, "dataset": ds, "tokens": len(chain.ids),
                "ids_sha256": hashlib.sha256(np.asarray(chain.ids, dtype="<u2").tobytes()).hexdigest(),
                "hidden_sha256": hashlib.sha256(np.asarray(out.x, dtype=np.int8).tobytes()).hexdigest(),
                "bit_exact": matched, "encoder_clocks": out.run.encoder_clocks,
                "request_clocks": out.run.total_clocks, "host_round_trip_ms": host_ms,
                "heads_ms": heads_ms,
                "performance_counters": counters,
                "timing_policy_result": budget.assess(int(out.run.total_clocks), host_ms) if budget else None,
                "predictions": [{"head": p.head, "segment": p.segment, "labels": p.labels,
                    "integer_logits_sha256": hashlib.sha256(
                        np.asarray(p.integer_logits, dtype="<i8").tobytes()).hexdigest()} for p in preds]})
            report["verification"] = {"exact": exact, "total": total}
            inv = {v: k for k, v in chain.kept.items()}
            for p in preds:
                if p.head.startswith("intent"):
                    gold = c.segments[inv[p.segment]].intent
                    if gold != IGNORE:
                        st["n"] += 1
                        st["ok"] += int(p.labels[0] == heads.labels[p.head][gold])
                elif p.head.startswith("slots"):
                    seg = c.segments[inv[p.segment]]
                    if seg.tags is None:
                        continue
                    names = heads.labels[p.head]
                    ps = spans(p.labels)
                    gs = spans([names[t] for t in seg.tags[:len(p.labels)]])
                    st["tp"] += len(ps & gs)
                    st["fp"] += len(ps - gs)
                    st["fn"] += len(gs - ps)
                else:
                    st["n"] += 1
                    st["ok"] += int(int(np.argmax(p.logits[0])) == c.pair_label)
            if len(report["cases"]) % 10 == 0:
                print(f"eval progress: {len(report['cases'])} chains", flush=True)
                save_report()
        r = []
        if st["n"]:
            r.append(f"accuracy {st['ok'] / st['n']:.3f} ({st['n']})")
        if st["tp"] + st["fp"] + st["fn"]:
            pr = st["tp"] / max(st["tp"] + st["fp"], 1)
            rc = st["tp"] / max(st["tp"] + st["fn"], 1)
            r.append(f"slot F1 {2 * pr * rc / max(pr + rc, 1e-9):.3f}")
        print(f"{ds:12s} {', '.join(r)}", flush=True)
        save_report()
    if args.verify:
        print(f"X bit-exact against ImageMachine: {exact} / {total}")
    if clocks and clocks[0][1]:
        c = np.array(clocks)
        print(f"board encoder time: mean {ms(c[:, 1].mean())} over {len(c)} chains of "
              f"{c[:, 0].mean():.0f} tokens on average, max {ms(c[:, 1].max())} ({c[:, 0].max()} tokens)")
    report["complete"] = True
    save_report()
    if args.report:
        print(f"Saved evaluation report: {args.report}")
    return 0 if exact == total else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--interface")
    transport = ap.add_mutually_exclusive_group()
    transport.add_argument("--local", action="store_true", help="no board: ImageMachine runs the image")
    transport.add_argument("--kr260", action="store_true", help="run on a KR260's ARM (/dev/mem)")
    ap.add_argument("--registers", type=lambda s: int(s, 0), default=0xA000_0000,
                    help="KR260: kr260_encoder's AXI4-Lite base")
    ap.add_argument("--region", type=lambda s: int(s, 0), nargs=2, default=None,
                    metavar=("BASE", "BYTES"), help="KR260: PS DDR region (default: discover the boot reservation)")
    ap.add_argument("--clock-mhz", type=float, default=None,
                    help="encoder clock for ms (default: Nexys 75, KR260 100; override for new builds)")
    ap.add_argument("--image", default="bert-mini-slots4", help="export/v2/image/<name>")
    ap.add_argument("--timeout", type=float, default=5.0, help="seconds to wait for a run")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("load", help="write the image to the board and read it back")
    c = sub.add_parser("check", help="random chains, board X against ImageMachine")
    c.add_argument("--tokens", type=int, nargs="+", default=[1, 12, 64, 128])
    c.add_argument("--repeat", type=int, default=1)
    c.add_argument("--seed", type=int, default=0)
    r = sub.add_parser("run", help="one request: segments as arguments")
    r.add_argument("--dataset", choices=sorted(DATASETS) + ["auto"], default=None,
                   help="auto: CLINC decides in/out of scope and routes to ATIS or SGD")
    r.add_argument("--intents", help="v3: JSON {intent: [example sentences]} for custom intents")
    r.add_argument("--threshold", type=float, default=0.6, help="custom-intent similarity threshold")
    r.add_argument("text", nargs="+")
    dc = sub.add_parser("doc", help="long text: one result per sentence (+ --query search, v3)")
    dc.add_argument("--file")
    dc.add_argument("--query", help="v3: rank the sentences by similarity to this")
    dc.add_argument("--top", type=int, default=3)
    dc.add_argument("--intents", help="v3: custom intents JSON, as for run")
    dc.add_argument("--threshold", type=float, default=0.6)
    dc.add_argument("--quiet", action="store_true", help="no per-sentence lines")
    dc.add_argument("--max-segments", type=int, default=1,
                    help="sentences per request. 1 (default): each sentence alone, the accuracy of a "
                         "single request. More is faster but sentences in one request influence each "
                         "other: CLINC, 1000 words, MiniLM-L6: 1 -> 0.919, 2 -> 0.886, 4 -> 0.876, "
                         "0 (as many as fit) -> 0.790 (scripts/v2/longtext_eval.py)")
    dc.add_argument("--separate", action="store_true",
                    help="one request per sentence instead of packing sentences into 128-token requests")
    dc.add_argument("text", nargs="*")
    e = sub.add_parser("eval", help="test chains through the board")
    e.add_argument("--per-dataset", type=int, default=50)
    e.add_argument("--seed", type=int, default=0)
    e.add_argument("--verify", action="store_true", help="also compare X with ImageMachine")
    e.add_argument("--suite", type=Path, help="frozen matched suite with cached integer goldens")
    e.add_argument("--budget", type=Path, help="matched timing policy JSON; reports measured overruns, not hard guarantees")
    e.add_argument("--report", type=Path, help="save per-case accuracy, hashes and board/host timings")
    args = ap.parse_args()

    if args.command == "eval" and (args.per_dataset <= 0 or (args.suite and not args.verify)):
        ap.error("eval needs positive --per-dataset; --suite requires --verify")

    if args.kr260:
        print("KR260: loading model files from storage...", flush=True)
    image, manifest, wp, decision = load_files(args.image)
    args.image_sha256 = hashlib.sha256(image).hexdigest()
    if args.command == "eval" and args.suite:
        model = manifest.get("model_name") or args.image.removesuffix("-kr260")
        args.tokenizer_sha256 = hashlib.sha256(
            (ROOT / "export/v2/chain" / model / "tokenizer.json").read_bytes()).hexdigest()
    global CLOCK_HZ, IMAGE_NAME
    IMAGE_NAME = args.image
    clock_mhz = args.clock_mhz if args.clock_mhz is not None else (100.0 if args.kr260 else 75.0)
    if clock_mhz <= 0:
        ap.error("--clock-mhz must be positive")
    CLOCK_HZ = clock_mhz * 1e6
    link = None
    if args.local:
        enc = LocalEncoder(image)
    elif args.kr260:
        from sysone.v2.kr260_link import Kr260Link
        from sysone.v2.kr260_runtime import discover_memory
        print("KR260: checking loaded FPGA app, drivers, clock and reserved memory before MMIO...", flush=True)
        region = tuple(args.region) if args.region is not None else discover_memory()
        print(f"KR260: reserved model/request memory {region[1] / (1 << 20):g} MiB at {region[0]:#x}", flush=True)
        link = Kr260Link(args.registers, region)
        try:
            if args.clock_mhz is not None and abs(CLOCK_HZ - link.clock_hz) > 1:
                raise ValueError(f"--clock-mhz differs from live PL0; use {link.clock_hz / 1e6:.6f}")
            CLOCK_HZ = link.clock_hz
            print(f"KR260: encoder registers ready; live clock {link.clock_hz} Hz", flush=True)
            enc = EncoderBoard(link, image)
            if args.command != "load":
                print("KR260: verifying loaded DDR image before RUN...", flush=True)
                link.verify_loaded_image(enc.machine.h["base"], image)
                print("KR260: DDR image matches", flush=True)
        except Exception:
            link.close()
            raise
    else:
        if not args.interface:
            ap.error("need -i INTERFACE (or --local)")
        from memory_link_client import Link
        link = Link(args.interface)
        enc = EncoderBoard(link, image)
    try:
        if args.command == "load":
            if link is None:
                raise SystemExit("load needs a board")
            base = enc.machine.h["base"]
            t0 = time.perf_counter()
            link.write(base, image)
            back = link.read(base, len(image))
            bad = sum(a != b for a, b in zip(image, back))
            print(f"{args.image}: {len(image):,} bytes at {base:#x}, "
                  + ("identical after read-back" if bad == 0 else f"{bad} bytes differ")
                  + f" ({time.perf_counter() - t0:.0f} s, host path)")
            return 0 if bad == 0 else 1
        if args.command == "check":
            return cmd_check(enc, args)
        heads = Heads(manifest, enc.machine, decision)
        if args.command == "run":
            if not args.dataset:
                ap.error("run needs --dataset (auto routes; add --intents for your own intents)")
            return cmd_run(enc, heads, wp, args)
        if args.command == "doc":
            return cmd_doc(enc, heads, wp, args)
        return cmd_eval(enc, heads, wp, args)
    finally:
        if link is not None:
            link.close()


if __name__ == "__main__":
    sys.exit(main())
