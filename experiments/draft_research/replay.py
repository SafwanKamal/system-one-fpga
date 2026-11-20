"""Exact offline replay of greedy speculative decoding on the qualification workload.

With greedy decoding, the token the engine emits at a position depends only on the
tokens before it. A verify pass emits the engine's own token at every lane up to and
including the first rejected draft. Every token it emits is therefore one of the
recorded plain-decode (`ar`) tokens. A fake engine that serves those tokens makes
`spec_decode.decode` (unchanged, imported from experiments/spec_service) behave exactly
as on the board, for any drafter and gate. Validation: replaying the RC1.1 drafter and
gate reproduces the board's per-case pass statistics.

The fake engine also logs every command (single step or batched pass of k tokens at
position p) for the cost model in cost.py.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/spec_service'))
import spec_decode  # noqa: E402

PKG = ROOT / 'build/v2/hardware-consolidated-rc1/deployment-r2'
EOS = {151645, 151643}


def tokenizer(cases):
    """The pinned BPE with the stdlib pre-tokenizer stand-in, checked by re-encoding the decoded
    text of every stored prompt (must give back the same ids)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import host_tokenizers
    host_tokenizers.install()
    sys.path.insert(0, str(ROOT / 'src'))
    from sysone.v2.qwen_tokenizer_v1 import Vocabulary
    from sysone.v2.qwen_arm_service_candidate import prompt_for
    vocab = Vocabulary(PKG)
    names = {v: k for k, v in vocab.added.items()}
    for c in cases:
        if 'prompt_ids' in c:
            text = b''.join(names[t].encode() if t in names else vocab.piece(t) for t in c['prompt_ids']).decode('utf-8')
            if vocab.encode_text(text) != c['prompt_ids']:
                raise RuntimeError('host tokenizer round trip failed on case %d' % c['index'])
    return vocab, prompt_for


def load_cases(record=ROOT / 'build/v2/v9g-board/pilot.json'):
    """Workload cases (original order) with prompt ids and the recorded greedy output."""
    work = json.loads((ROOT / 'build/v2/spec-qual/workload.json').read_text())
    rec = {c['key']: c for c in json.loads(Path(record).read_text())['cases']}
    if any('query' in c for c in work['cases']):
        vocab, prompt_for = tokenizer(work['cases'])
    out = []
    for c in work['cases']:
        ids = c['prompt_ids'] if 'prompt_ids' in c else vocab.encode_text(prompt_for(c['query']))
        r = rec[c['key']]
        if len(ids) != r['prompt_tokens']:
            raise RuntimeError('prompt length differs for case %d' % c['index'])
        out.append(dict(key=c['key'], index=c['index'], domain=c['domain'], ids=ids, max_new=c['max_new'],
                        target=r['ar']['tokens'], record=r))
    return out, work['gate_threshold']


class FakeEngine:
    context = 2048

    def __init__(self, ids, target):
        self.n, self.target, self.log, self.pending = len(ids), target, [], None

    def _tok(self, p):  # greedy token predicted from position p, i.e. output index p - n + 1
        i = p - self.n + 1
        return self.target[i] if i < len(self.target) else -1  # lanes past the end are never emitted

    def step(self, token, p, logits=True):
        self.log.append(('s', 1, p))
        return self._tok(p)

    def prefill_batch(self, toks, p, logits=False):
        self.log.append(('b', len(toks), p))
        self.pending = p

    def batched(self, count):
        p = self.pending
        return [(self._tok(p + i), 0) for i in range(count)]


def run(cases, drafter_factory=spec_decode.Drafter, gate_factory=None, decode=spec_decode.decode, feed=None):
    """Replay all cases in order with one persistent drafter and gate, as on the board.
    feed(drafter, case, out) updates drafter history after a case (default: add the output)."""
    drafter = drafter_factory() if drafter_factory else None
    gate = gate_factory() if gate_factory else None
    res = []
    for c in cases:
        e = FakeEngine(c['ids'], c['target'])
        out, _, st = decode(e, c['ids'], c['target'][0], c['max_new'], lambda t: t[-1] in EOS,
                            drafter=drafter, gate=gate, batched=e.batched if drafter else None)
        if out != c['target']:
            raise RuntimeError('replay diverged on case %d' % c['index'])
        if drafter is not None:
            (feed or (lambda d, c, o: d.add(o)))(drafter, c, out)
        res.append(dict(st, log=e.log, index=c['index'], domain=c['domain'], key=c['key']))
    return res


if __name__ == '__main__':
    cases, thr = load_cases()
    spec = run(cases, gate_factory=lambda: spec_decode.Gate(threshold=thr))
    keys = ('passes', 'ar_steps', 'drafted', 'accepted', 'zero_accept', 'gated_off', 'head_scans')
    bad = [(c['index'], k) for c, s in zip(cases, spec) for k in keys if s[k] != c['record']['batched'][k]]
    print('cases', len(cases), 'stat mismatches vs v9g board batched run:', len(bad), bad[:5])
