"""Multi-task, multi-segment data for the v2 encoder.

One example is a *chain*: an ordered list of text segments that the board encodes
together in one pass, plus targets attached to some of the segments. Everything the
v2 model does is a special case of that:

  task          segments                               targets
  ------------  -------------------------------------  ------------------------------
  intent        [utterance]                            intent of the utterance
  slots+intent  [utterance]                            intent + a BIO tag per word
  dialogue      [turn_-k, ..., turn_-1, user turn]     intent + slots of the last turn,
                                                       which often only the earlier
                                                       turns disambiguate ("yes, 7pm")
  multi         [utt_1, utt_2, ..., utt_n]             an intent for every segment
  pair          [sentence_a, sentence_b]               one label for the pair
                                                       (entailment / paraphrase)

Sources (all reachable from GitHub; licences recorded in data/v2/PROVENANCE.md):
  CLINC150   data/clinc150 (already vendored)                    intent, 151 incl. oos
  ATIS       MiuLab/SlotGated-SLU data/atis                      intent + slots
  SGD        google-research-datasets/dstc8-schema-guided-dialogue  multi-turn, intent + slots
  SICK       brmson/dataset-sts data/sts/sick2014                entailment, 3 classes
  MSRP       brmson/dataset-sts data/para/msr                    paraphrase, 2 classes
  HWU64      xliuhw/NLU-Evaluation-Data (data/v2/hwu)            intent + slots, 18 assistant
                                                                 scenarios (MASSIVE's source)
Few-shot evaluation only (never trained on; tests the embedding head on new intents):
  Banking77  PolyAI-LDN/task-specific-datasets (data/v2/banking77)  77 banking intents
  SNIPS      sonos/nlu-benchmark 2017-06 (data/v2/snips)          7 intents

Words are whitespace tokens; a slot tag belongs to a word and the model predicts it
from the word's first sub-word. Characters are kept as is (the WordPiece tokenizer
lower-cases), because SGD slot spans are character offsets into the original text.
"""

from __future__ import annotations

import glob
import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXT = ROOT / "data" / "v2"           # external corpora (cloned, not vendored)

IGNORE = -100


@dataclass
class Segment:
    words: list[str]
    intent: int = IGNORE                 # index into the dataset's intent label set
    tags: list[int] | None = None        # one BIO tag id per word, or None
    role: str = ""                       # "user" / "system" / "" (for dialogue context)


@dataclass
class Chain:
    task: str                            # intent | slots | dialogue | multi | pair
    dataset: str                         # clinc | atis | sgd | sick | msrp | multi_clinc ...
    segments: list[Segment]
    pair_label: int = IGNORE
    meta: dict = field(default_factory=dict)


@dataclass
class Corpus:
    train: list[Chain]
    dev: list[Chain]
    test: list[Chain]
    intent_labels: dict[str, list[str]]  # head name -> labels
    tag_labels: dict[str, list[str]]
    pair_labels: dict[str, list[str]]


def _words(text: str) -> list[str]:
    return text.split()


# ----------------------------------------------------------------------- CLINC150

def load_clinc() -> tuple[dict, list[str]]:
    raw = json.loads((ROOT / "data" / "clinc150" / "data_full.json").read_text())
    labels = sorted({y for split in ("train", "val", "test") for _, y in raw[split]})
    labels = [l for l in labels] + ["oos"]
    idx = {l: i for i, l in enumerate(labels)}
    out = {}
    for ours, theirs in (("train", "train"), ("dev", "val"), ("test", "test")):
        rows = [(t, idx[y]) for t, y in raw[theirs]]
        rows += [(t, idx["oos"]) for t, _ in raw[f"oos_{theirs}"]]
        out[ours] = [Chain("intent", "clinc", [Segment(_words(t), intent=y)]) for t, y in rows]
    return out, labels


# --------------------------------------------------------------------------- ATIS

def load_atis() -> tuple[dict, list[str], list[str]]:
    base = EXT / "slu" / "data" / "atis"
    rows = {}
    for ours, theirs in (("train", "train"), ("dev", "valid"), ("test", "test")):
        d = base / theirs
        seq = (d / "seq.in").read_text().splitlines()
        tag = (d / "seq.out").read_text().splitlines()
        lab = (d / "label").read_text().splitlines()
        rows[ours] = list(zip(seq, tag, lab))
    # multi-intent labels like "atis_flight#atis_airfare" exist; keep the first
    intents = sorted({l.split("#")[0] for s in rows.values() for _, _, l in s})
    tags = sorted({t for s in rows.values() for _, ts, _ in s for t in ts.split()})
    tags.remove("O")
    tags = ["O"] + tags
    ii = {l: i for i, l in enumerate(intents)}
    ti = {t: i for i, t in enumerate(tags)}
    out = {}
    for split, rs in rows.items():
        out[split] = [Chain("slots", "atis",
                            [Segment(s.split(), intent=ii[l.split("#")[0]],
                                     tags=[ti[t] for t in ts.split()])])
                      for s, ts, l in rs if len(s.split()) == len(ts.split())]
    return out, intents, tags


# ---------------------------------------------------------------------------- SGD

_TOK = re.compile(r"\S+")


def _span_tags(text: str, slots: list[dict]) -> tuple[list[str], list[str]]:
    """Whitespace words of ``text`` and a BIO slot name per word from char spans."""
    words, tags = [], []
    spans = sorted((s["start"], s["exclusive_end"], s["slot"]) for s in slots)
    for m in _TOK.finditer(text):
        a, b = m.start(), m.end()
        tag = "O"
        for s, e, name in spans:
            if a < e and b > s:                      # overlap
                tag = ("B-" if a <= s else "I-") + name
                break
        words.append(m.group())
        tags.append(tag)
    return words, tags


def load_sgd(max_context_turns: int = 4, train_dialogues: int | None = None,
             seed: int = 0) -> tuple[dict, list[str], list[str]]:
    base = EXT / "sgd"
    rows = {}
    for split in ("train", "dev", "test"):
        dialogues = []
        for fn in sorted(glob.glob(str(base / split / "dialogues_*.json"))):
            dialogues += json.loads(Path(fn).read_text())
        if split == "train" and train_dialogues:
            random.Random(seed).shuffle(dialogues)
            dialogues = dialogues[:train_dialogues]
        ex = []
        for d in dialogues:
            hist: list[tuple[str, str]] = []
            for t in d["turns"]:
                text = t["utterance"]
                if t["speaker"] == "USER":
                    f = t["frames"][0]
                    words, tags = _span_tags(text, f["slots"])
                    ex.append((list(hist[-max_context_turns:]), words, tags,
                               f["state"]["active_intent"], d["dialogue_id"]))
                hist.append((t["speaker"].lower(), text))
        rows[split] = ex
    intents = sorted({r[3] for r in rows["train"]})
    tags = sorted({t for r in rows["train"] for t in r[2]})
    tags.remove("O")
    tags = ["O"] + tags
    ii = {l: i for i, l in enumerate(intents)}
    ti = {t: i for i, t in enumerate(tags)}
    out = {}
    for split, ex in rows.items():
        chains = []
        for hist, words, tg, intent, did in ex:
            segs = [Segment(_words(txt), role=role) for role, txt in hist]
            segs.append(Segment(words, intent=ii.get(intent, IGNORE),
                                tags=[ti.get(t, 0) for t in tg], role="user"))
            chains.append(Chain("dialogue", "sgd", segs,
                                meta={"dialogue_id": did, "intent_seen": intent in ii,
                                      "context_turns": len(hist)}))
        out[split] = chains
    return out, intents, tags


# --------------------------------------------------------------------- SICK, MSRP

def load_sick() -> tuple[dict, list[str]]:
    base = EXT / "sts" / "data" / "sts" / "sick2014"
    labels = ["ENTAILMENT", "NEUTRAL", "CONTRADICTION"]
    li = {l: i for i, l in enumerate(labels)}
    out = {}
    for split, fn in (("train", "SICK_train.txt"), ("dev", "SICK_trial.txt"),
                      ("test", "SICK_test_annotated.txt")):
        lines = (base / fn).read_text(encoding="utf-8").splitlines()[1:]
        out[split] = []
        for line in lines:
            p = line.split("\t")
            if len(p) < 5:
                continue
            out[split].append(Chain("pair", "sick", [Segment(_words(p[1])), Segment(_words(p[2]))],
                                    pair_label=li[p[4].strip()]))
    return out, labels


def load_msrp() -> tuple[dict, list[str]]:
    base = EXT / "sts" / "data" / "para" / "msr"
    out = {}
    for split, fn in (("train", "msr-para-train.tsv"), ("dev", "msr-para-val.tsv"),
                      ("test", "msr-para-test.tsv")):
        lines = (base / fn).read_text(encoding="utf-8-sig").splitlines()[1:]
        out[split] = []
        for line in lines:
            p = line.split("\t")
            if len(p) < 5:
                continue
            out[split].append(Chain("pair", "msrp", [Segment(_words(p[3])), Segment(_words(p[4]))],
                                    pair_label=int(p[0])))
    return out, ["different", "paraphrase"]


# -------------------------------------------------------------------------- HWU64

_ANN = re.compile(r"\[\s*([^:\]]+?)\s*:\s*([^\]]*?)\s*\]")


def _hwu_words(annotation: str) -> tuple[list[str], list[str]]:
    """'wake me up at [time : five am]' -> words and BIO slot names."""
    words, tags, pos = [], [], 0
    for m in _ANN.finditer(annotation):
        for w in annotation[pos:m.start()].split():
            words.append(w)
            tags.append("O")
        for k, w in enumerate(m.group(2).split()):
            words.append(w)
            tags.append(("B-" if k == 0 else "I-") + m.group(1).strip().replace(" ", "_"))
        pos = m.end()
    for w in annotation[pos:].split():
        words.append(w)
        tags.append("O")
    return words, tags


def load_hwu() -> tuple[dict, list[str], list[str]]:
    """HWU64 (Liu et al. 2019): 25.7k utterances to a home assistant, intent
    'scenario_intent' and bracketed slot annotations. No official split, so a fixed one:
    rows marked irrelevant (IRR*) dropped, duplicates (same lower-cased text) kept
    together, 80 / 10 / 10 by a hash of the text."""
    import csv
    import zlib
    fn = EXT / "hwu" / "NLU-Data-Home-Domain-Annotated-All.csv"
    rows = []
    with open(fn, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            ann = (r["answer_annotation"] or "").strip()
            if not ann or ann == "null" or r["status"].startswith("IRR"):
                continue
            if ann.count("[") != ann.count("]"):
                continue
            words, tags = _hwu_words(ann)
            if words:
                rows.append((words, tags, f"{r['scenario']}_{r['intent']}"))
    split_of = {}
    out_rows = {"train": [], "dev": [], "test": []}
    for words, tags, intent in rows:
        key = " ".join(words).lower()
        if key not in split_of:
            h = zlib.crc32(key.encode()) % 10
            split_of[key] = "test" if h == 0 else "dev" if h == 1 else "train"
        out_rows[split_of[key]].append((words, tags, intent))
    intents = sorted({r[2] for r in out_rows["train"]})
    tags_ = sorted({t for r in out_rows["train"] for t in r[1]} - {"O"})
    tags_ = ["O"] + tags_
    ii = {l: i for i, l in enumerate(intents)}
    ti = {t: i for i, t in enumerate(tags_)}
    out = {}
    for split, rs in out_rows.items():
        out[split] = [Chain("slots", "hwu", [Segment(w, intent=ii[l], tags=[ti.get(t, 0) for t in tg])])
                      for w, tg, l in rs if l in ii]
    return out, intents, tags_


# --------------------------------------------------- few-shot sets (evaluation only)

def load_banking77() -> dict[str, list[tuple[str, str]]]:
    """{'train': [(text, intent)], 'test': [...]}: Banking77 (Casanueva et al. 2020)."""
    import csv
    out = {}
    for split in ("train", "test"):
        with open(EXT / "banking77" / f"{split}.csv", encoding="utf-8") as f:
            out[split] = [(r["text"], r["category"]) for r in csv.DictReader(f)]
    return out


def load_snips() -> dict[str, list[tuple[str, str]]]:
    """{'train': [...], 'test': [...]}: SNIPS 2017 custom-intent benchmark, 7 intents
    (train_*_full.json as the pool, validate_*.json, 100 per intent, as the test set)."""
    out = {"train": [], "test": []}
    for fn in sorted((EXT / "snips").glob("*_*.json")):
        split = "train" if fn.name.startswith("train_") else "test"
        raw = json.loads(fn.read_bytes().decode("latin-1"))
        for intent, items in raw.items():
            for it in items:
                out[split].append(("".join(p["text"] for p in it["data"]).strip(), intent))
    return out


# ----------------------------------------------------------- synthetic multi-sentence

def make_multi(pool: list[Chain], n: int, lo: int = 2, hi: int = 4, seed: int = 0,
               name: str = "multi_clinc") -> list[Chain]:
    """Several independent single-utterance chains joined into one input.

    Each segment keeps its own intent. It tests whether one encoder pass can
    answer several requests at once (and costs about the same as one on hardware,
    where the weights, not the tokens, set the time).
    """
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        k = rng.randint(lo, hi)
        segs = [rng.choice(pool).segments[0] for _ in range(k)]
        out.append(Chain("multi", name, list(segs)))
    return out


def load_all(sgd_train_dialogues: int = 4000, multi_train: int = 8000, seed: int = 0,
             hwu: bool = False) -> Corpus:
    """The training corpus. `hwu` adds HWU64 (the v3 models); models trained without it
    keep exactly their original corpus (calibration, evaluation)."""
    clinc, clinc_labels = load_clinc()
    atis, atis_intents, atis_tags = load_atis()
    sgd, sgd_intents, sgd_tags = load_sgd(train_dialogues=sgd_train_dialogues, seed=seed)
    sick, sick_labels = load_sick()
    msrp, msrp_labels = load_msrp()
    intents = {"clinc": clinc_labels, "atis": atis_intents, "sgd": sgd_intents}
    tags = {"atis": atis_tags, "sgd": sgd_tags}
    h = {"train": [], "dev": [], "test": []}
    if hwu:
        h, intents["hwu"], tags["hwu"] = load_hwu()
    splits = {}
    for s in ("train", "dev", "test"):
        n_multi = multi_train if s == "train" else 1500
        splits[s] = (clinc[s] + atis[s] + sgd[s] + sick[s] + msrp[s]
                     + make_multi(clinc[s], n_multi, seed=seed + {"train": 0, "dev": 1, "test": 2}[s])
                     + h[s])
    return Corpus(splits["train"], splits["dev"], splits["test"],
                  intent_labels=intents, tag_labels=tags,
                  pair_labels={"sick": sick_labels, "msrp": msrp_labels})


def intent_head(chain: Chain) -> str:
    return {"multi_clinc": "clinc"}.get(chain.dataset, chain.dataset)
