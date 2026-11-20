"""Causal draft sources for lossless greedy speculation (exactness never depends on them).

VoteDrafter generalizes the RC1.1 Drafter (spec_decode.Drafter):
- ns: suffix lengths tried, longest first (RC1.1: 6, 4, 3, 2);
- prompts: also put earlier prompts into the cross-case history (RC1.1: outputs only);
- vote: build the draft token by token from all matches of the chosen suffix length,
  weighting context matches over history (RC1.1: most recent context match, else the
  latest history entry);
- chain: when the chosen continuation ends early (match near the end of the context),
  draft again from context + draft;
- min_support: stop a voted draft when the winning token's share falls below this.
The draft is capped at K = 7 tokens (8 batched slots).
"""
from collections import defaultdict

K = 7


class VoteDrafter:
    def __init__(self, ns=(6, 4, 3, 2), prompts=False, vote=False, chain=False, min_support=0.0,
                 ctx_weight=2.0, hist_cap=8, history_limit=1 << 16):
        self.ns, self.prompts, self.vote, self.chain = tuple(ns), prompts, vote, chain
        self.min_support, self.ctx_weight, self.hist_cap, self.history_limit = min_support, ctx_weight, hist_cap, history_limit
        self.hist = {n: {} for n in self.ns}

    # history: n-gram -> list of continuations (latest last, at most hist_cap)
    def add(self, seq):
        for n in self.ns:
            table = self.hist[n]
            for s in range(len(seq) - n):
                key = tuple(seq[s:s + n])
                lst = table.pop(key, [])          # re-insert to keep recency order for eviction
                lst.append(tuple(seq[s + n:s + n + K]))
                table[key] = lst[-self.hist_cap:]
            while len(table) > self.history_limit:
                table.pop(next(iter(table)))

    def feed(self, case, out):
        if self.prompts:
            self.add(list(case['ids']) + list(out))
        else:
            self.add(out)

    def _candidates(self, ctx, n):
        L = len(ctx)
        if L <= n:
            return [], []
        suf = ctx[L - n:]
        cands = [tuple(ctx[s + n:s + n + K]) for s in range(L - n - 1, -1, -1) if ctx[s:s + n] == suf]
        cands = [c for c in cands if c]
        hist = [c for c in reversed(self.hist[n].get(tuple(suf), [])) if c]
        return cands, hist

    def _draft_once(self, ctx):
        for n in self.ns:
            cands, hist = self._candidates(ctx, n)
            if not cands and not hist:
                continue
            if not self.vote:
                return list(cands[0] if cands else hist[0]), n
            weighted = [(c, self.ctx_weight) for c in cands] + [(c, 1.0) for c in hist]
            draft = []
            for i in range(K):
                tally = defaultdict(float); total = 0.0
                for c, w in weighted:
                    if len(c) > i and list(c[:i]) == draft:
                        tally[c[i]] += w; total += w
                if not tally:
                    break
                tok, w = max(tally.items(), key=lambda kv: kv[1])
                if draft and w / total < self.min_support:
                    break
                draft.append(tok)
            return draft, n
        return [], 0

    def draft(self, ctx):
        d, n = self._draft_once(ctx)
        while self.chain and d and len(d) < K:
            more, _ = self._draft_once(list(ctx) + d)
            if not more:
                break
            d = d + more[:K - len(d)]
        return d, n


class SourceDrafter(VoteDrafter):
    """Ranks match sources instead of only suffix length.

    Sources: 'out' (this reply so far), 'hist' (earlier replies, and earlier prompts if
    prompts=True), 'prompt' (this prompt). `order` is a list of (source, min_n) tiers tried in
    turn; within a tier the longest suffix wins. begin(ids) marks where the prompt ends.
    """
    def __init__(self, order=(('out', 3), ('hist', 3), ('prompt', 3), ('out', 1), ('hist', 1), ('prompt', 1)),
                 ns=(8, 6, 5, 4, 3, 2, 1), **kw):
        super().__init__(ns=ns, **kw)
        self.order, self.plen = order, 0

    def begin(self, ids):
        self.plen = len(ids)

    def _match(self, ctx, src, n):
        L = len(ctx)
        if L <= n:
            return None
        suf = ctx[L - n:]
        if src == 'hist':
            h = self.hist[n].get(tuple(suf))
            return list(h[-1]) if h else None
        lo, hi = (self.plen, L - n - 1) if src == 'out' else (0, min(self.plen, L - n - 1) - 1 if self.plen else -1)
        for s in range(hi, lo - 1, -1):
            if ctx[s:s + n] == suf:
                c = ctx[s + n:s + n + K]
                if c:
                    return list(c)
        return None

    def _draft_once(self, ctx):
        for src, mn in self.order:
            for n in self.ns:
                if n < mn:
                    break
                c = self._match(ctx, src, n)
                if c:
                    return c, n
        return [], 0


class CostAwareDrafter:
    """Chooses how much of a base draft to verify, from causal acceptance estimates and the
    fitted v9g cost model.

    For each (suffix length n, draft index i) it keeps q[n][i] = P(token i is right | tokens
    before it are right), estimated from earlier full (untruncated) drafts once the reply has
    revealed the true tokens. A draft truncated to L tokens is expected to emit
    E(L) = 1 + sum_{i<L} prod_{j<=i} q_j tokens at cost pass(L+1, p); L = 0 is a plain step.
    It picks L maximizing E(L) / cost(L). Priors: q = prior with weight prior_w.
    """
    def __init__(self, base, coef, prior=0.5, prior_w=2.0, P=4, nbucket=lambda n: min(n, 6)):
        self.base, self.coef, self.P, self.nb = base, coef, P, nbucket
        self.prior, self.prior_w = prior, prior_w
        self.hit, self.tot = {}, {}
        self.pending, self.plen = [], 0

    def begin(self, ids):
        self.pending, self.plen = [], len(ids)
        if hasattr(self.base, 'begin'):
            self.base.begin(ids)

    def feed(self, case, out):
        self._resolve(list(case['ids']) + list(out), final=True)
        (self.base.feed if hasattr(self.base, 'feed') else lambda c, o: self.base.add(o))(case, out)

    def add(self, seq):
        self.base.add(seq)

    def q(self, n, i):
        k = (self.nb(n), i)
        return (self.hit.get(k, 0) + self.prior * self.prior_w) / (self.tot.get(k, 0) + self.prior_w)

    def _resolve(self, ctx, final=False):
        keep = []
        for start, d, n in self.pending:
            known = ctx[start:start + len(d)]
            if len(known) < len(d) and not final:
                keep.append((start, d, n)); continue
            for i, tok in enumerate(d):
                if i >= len(known):
                    break
                k = (self.nb(n), i)
                self.tot[k] = self.tot.get(k, 0) + 1
                if known[i] != tok:
                    break
                self.hit[k] = self.hit.get(k, 0) + 1
        self.pending = keep

    def cost(self, k, p):
        c = self.coef  # FEATURES order: steps, step_pos, passes, pass_tokens, pass_pos, pass_pos_groups
        if k == 1:
            return c[0] + c[1] * p
        if len(c) == 7:  # v9h: steps, step_pos, passes<=P, passes>P, pass_tokens, pass_pos, pass_pos_groups
            return (c[2] if k <= self.P else c[3]) + c[4] * k + c[5] * p + c[6] * p * -(-k // self.P)
        return c[2] + c[3] * k + c[4] * p + c[5] * p * -(-k // self.P)

    def draft(self, ctx):
        self._resolve(ctx)
        d, n = self.base.draft(ctx)
        if not d:
            return [], 0
        self.pending.append((len(ctx), list(d), n))
        p = len(ctx) - 1
        best, bestv, e, run = 0, 1.0 / self.cost(1, p), 1.0, 1.0
        for L in range(1, len(d) + 1):
            run *= self.q(n, L - 1); e += run
            v = e / self.cost(L + 1, p)
            if v > bestv:
                best, bestv = L, v
        return list(d[:best]), n
