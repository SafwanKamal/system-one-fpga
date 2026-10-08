"""BERT uncased WordPiece in plain Python, for the board's host client.

The chain models' tokenizers (export/v2/chain/<name>/tokenizer.json: BertNormalizer
with lowercase and accent stripping, BertPreTokenizer, WordPiece with "##"
continuations, 100-character words) reimplemented without `transformers` or
`tokenizers`, so the client runs in the board flow's environment (NumPy only).
`tests/test_wordpiece.py` checks it against the Hugging Face tokenizer on the
corpora when that is installed.

`word_pieces(words)` mirrors scripts/v2/train_chain.py Encoder.word_pieces: each
word is tokenised on its own; a word that yields nothing becomes [UNK].
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path


def _is_whitespace(ch: str) -> bool:
    if ch in " \t\n\r":
        return True
    return unicodedata.category(ch) == "Zs"


def _is_control(ch: str) -> bool:
    if ch in "\t\n\r":
        return False
    return unicodedata.category(ch) in ("Cc", "Cf")


def _is_punctuation(ch: str) -> bool:
    cp = ord(ch)
    if 33 <= cp <= 47 or 58 <= cp <= 64 or 91 <= cp <= 96 or 123 <= cp <= 126:
        return True
    return unicodedata.category(ch).startswith("P")


def _is_chinese(cp: int) -> bool:
    return (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or 0x20000 <= cp <= 0x2A6DF
            or 0x2A700 <= cp <= 0x2B73F or 0x2B740 <= cp <= 0x2B81F or 0x2B820 <= cp <= 0x2CEAF
            or 0xF900 <= cp <= 0xFAFF or 0x2F800 <= cp <= 0x2FA1F)


class WordPiece:
    def __init__(self, vocab: dict[str, int], unk: str = "[UNK]", prefix: str = "##",
                 max_chars: int = 100):
        self.vocab = vocab
        self.unk, self.prefix, self.max_chars = unk, prefix, max_chars
        self.unk_id = vocab[unk]
        self.cls_id, self.sep_id, self.pad_id = vocab["[CLS]"], vocab["[SEP]"], vocab["[PAD]"]
        self.cache: dict[str, list[int]] = {}

    @classmethod
    def from_file(cls, path) -> "WordPiece":
        """tokenizer.json (Hugging Face fast-tokenizer file) or vocab.txt."""
        path = Path(path)
        if path.is_dir():
            path = path / "tokenizer.json" if (path / "tokenizer.json").exists() else path / "vocab.txt"
        if path.suffix == ".json":
            t = json.loads(path.read_text(encoding="utf-8"))
            m = t["model"]
            if m["type"] != "WordPiece" or t["normalizer"]["type"] != "BertNormalizer" \
                    or not t["normalizer"]["lowercase"]:
                raise ValueError(f"{path}: not an uncased BERT WordPiece tokenizer")
            return cls(m["vocab"], m["unk_token"], m["continuing_subword_prefix"],
                       m["max_input_chars_per_word"])
        words = path.read_text(encoding="utf-8").split("\n")
        return cls({w: i for i, w in enumerate(words) if w})

    # BertNormalizer (clean text, CJK spacing, strip accents, lowercase)
    @staticmethod
    def normalize(text: str) -> str:
        out = []
        for ch in text:
            cp = ord(ch)
            if cp == 0 or cp == 0xFFFD or _is_control(ch):
                continue
            if _is_whitespace(ch):
                out.append(" ")
            elif _is_chinese(cp):
                out.append(f" {ch} ")
            else:
                out.append(ch)
        text = unicodedata.normalize("NFD", "".join(out))
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
        return text.lower()

    # BertPreTokenizer: whitespace, then every punctuation character on its own
    @staticmethod
    def pre_tokenize(text: str) -> list[str]:
        words, cur = [], []
        for ch in text:
            if _is_whitespace(ch):
                if cur:
                    words.append("".join(cur))
                    cur = []
            elif _is_punctuation(ch):
                if cur:
                    words.append("".join(cur))
                    cur = []
                words.append(ch)
            else:
                cur.append(ch)
        if cur:
            words.append("".join(cur))
        return words

    def _word(self, word: str) -> list[int]:
        if len(word) > self.max_chars:
            return [self.unk_id]
        ids, start = [], 0
        while start < len(word):
            end, found = len(word), None
            while start < end:
                piece = word[start:end]
                if start > 0:
                    piece = self.prefix + piece
                if piece in self.vocab:
                    found = self.vocab[piece]
                    break
                end -= 1
            if found is None:
                return [self.unk_id]
            ids.append(found)
            start = end
        return ids

    def encode(self, text: str) -> list[int]:
        """Token ids of a text, no special tokens."""
        ids = []
        for w in self.pre_tokenize(self.normalize(text)):
            if w not in self.cache:
                self.cache[w] = self._word(w)
            ids += self.cache[w]
        return ids

    def word_pieces(self, words: list[str]) -> list[list[int]]:
        """Pieces of each word of a pre-split sentence (train_chain.Encoder.word_pieces)."""
        return [self.encode(w) or [self.unk_id] for w in words]
