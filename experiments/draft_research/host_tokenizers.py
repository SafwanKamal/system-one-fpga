"""Stdlib stand-in for the three `tokenizers` pieces qwen_tokenizer_v1 uses (NFC, the Qwen split
regex, ByteLevel), so the pinned BPE can run on this PC; the package's own runtime is aarch64.
Install with install(); validated in replay.py by round-tripping every stored prompt.
\\p{L} is approximated by [^\\W\\d_] and \\p{N} by \\d (Python re); validation would catch a gap."""
import re, sys, types, unicodedata

L, N = r'[^\W\d_]', r'\d'


def _byte_map():
    bs = list(range(ord('!'), ord('~') + 1)) + list(range(ord('¡'), ord('¬') + 1)) + list(range(ord('®'), ord('ÿ') + 1))
    cs = bs[:]; n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b); cs.append(256 + n); n += 1
    return {b: chr(c) for b, c in zip(bs, cs)}


BYTE = _byte_map()
PATTERN = re.compile(
    r"(?i:'s|'t|'re|'ve|'m|'ll|'d)"
    r"|[^\r\n" + r"\w" + r"]?" + L + r"+"          # [^\r\n\p{L}\p{N}]?\p{L}+  (see fixup below)
    r"|" + N +
    r"| ?[^\s" + r"\w" + r"]+[\r\n]*"              # ' ?[^\s\p{L}\p{N}]+[\r\n]*'
    r"|\s*[\r\n]+|\s+(?!\S)|\s+")
# \w covers letters, digits and '_'. The Qwen classes exclude only letters and numbers, so '_'
# must be allowed where the pattern says [^...\p{L}\p{N}]:
PATTERN = re.compile(PATTERN.pattern.replace(r"[^\r\n\w]?", r"(?:[^\r\n\w]|_)?").replace(r" ?[^\s\w]+", r" ?(?:[^\s\w]|_)+"))


class Regex(str):
    pass


class _NFC:
    def normalize_str(self, s):
        return unicodedata.normalize('NFC', s)


class _Split:
    def __init__(self, regex, behavior='isolated'):
        pass

    def pre_tokenize_str(self, s):
        out, at = [], 0
        for m in PATTERN.finditer(s):
            if m.start() > at:
                out.append(s[at:m.start()])
            out.append(m.group()); at = m.end()
        if at < len(s):
            out.append(s[at:])
        return [(w, None) for w in out if w]


class _ByteLevel:
    def __init__(self, **kw):
        pass

    def map(self, w):
        return ''.join(BYTE[b] for b in w.encode('utf-8'))


class _Sequence:
    def __init__(self, parts):
        self.parts = parts

    def pre_tokenize_str(self, s):
        words = self.parts[0].pre_tokenize_str(s)
        return [(self.parts[1].map(w), o) for w, o in words]


def install():
    mod = types.ModuleType('tokenizers')
    mod.Regex = Regex
    mod.normalizers = types.SimpleNamespace(NFC=_NFC)
    mod.pre_tokenizers = types.SimpleNamespace(Split=_Split, ByteLevel=_ByteLevel, Sequence=_Sequence)
    sys.modules['tokenizers'] = mod
