"""The host client's WordPiece against the Hugging Face tokenizer (when installed)."""

from pathlib import Path

import pytest

from sysone.v2.wordpiece import WordPiece

ROOT = Path(__file__).resolve().parents[1]
TOK = ROOT / "export" / "v2" / "chain" / "bert-mini-slots4" / "tokenizer.json"

TEXTS = [
    "show me flights from denver to boston tomorrow morning",
    "Héllo, Wörld!! naïve café — 東京 test x",
    "I'd like $5.00 (now)... e-mail me@example.com",
    "ＦＵＬＬwidth  tabs\tand\nnewlines ​ zero-width",
    "a" * 120 + " supercalifragilisticexpialidocious",
    "",
]


def tiny() -> WordPiece:
    vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "un", "##aff", "##able", "runn", "##ing",
             "!", ",", "cafe", "東"]
    return WordPiece({w: i for i, w in enumerate(vocab)})


def test_greedy_longest_match_and_unknowns():
    wp = tiny()
    assert wp.encode("unaffable") == [4, 5, 6]
    assert wp.encode("running!") == [7, 8, 9]
    assert wp.encode("Café, 東x") == [11, 10, 12, 1]          # accents stripped, CJK split
    assert wp.encode("xyz") == [1]
    assert wp.word_pieces(["unaffable", "", "zzz"]) == [[4, 5, 6], [1], [1]]


@pytest.mark.skipif(not TOK.exists(), reason="no exported tokenizer")
def test_matches_hugging_face():
    tokenizers = pytest.importorskip("tokenizers")
    hf = tokenizers.Tokenizer.from_file(str(TOK))
    wp = WordPiece.from_file(TOK)
    for t in TEXTS:
        assert wp.encode(t) == hf.encode(t, add_special_tokens=False).ids, t
