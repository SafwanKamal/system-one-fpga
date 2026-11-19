"""Lossless greedy speculative decoding for the RC1 (v9e) engine. No FPGA changes.

Exactness does not depend on drafts or on the gate: every emitted token is the
engine's own greedy choice for that position, and the v9e kernel's per-position
arithmetic is independent of how the host groups positions (C-sim audit and the
2026-11-17 board pilot). The gate only decides whether a step is a batched
verify pass or an ordinary single-token step.
"""
K = 7
NS = (6, 4, 3, 2)


class Drafter:
    """Longest recent n-gram match in prompt+output, then in earlier outputs (causal)."""
    def __init__(self, history_limit=4096):
        self.hist = {n: {} for n in NS}
        self.history_limit = history_limit

    def add(self, seq):
        for n in NS:
            table = self.hist[n]
            for s in range(len(seq) - n):
                table[tuple(seq[s:s + n])] = list(seq[s + n:s + n + K])
            while len(table) > self.history_limit:
                table.pop(next(iter(table)))

    def draft(self, ctx):
        """Return (tokens, n) for the longest matching suffix, or ([], 0)."""
        L = len(ctx)
        for n in NS:
            if L <= n:
                continue
            suf = ctx[L - n:]
            for s in range(L - n - 1, -1, -1):
                if ctx[s:s + n] == suf:
                    c = ctx[s + n:s + n + K]
                    if c:
                        return list(c), n
            c = self.hist[n].get(tuple(suf))
            if c:
                return list(c), n
        return [], 0


class Gate:
    """Per-match-length running estimate of accepted tokens per verify pass.

    Speculate when the estimate is at least `threshold`; otherwise take a plain
    step, but still probe one draft in every `probe_every` skipped opportunities
    so a recovering estimate is noticed. Threshold fixed in PROTOCOL.md.
    """
    def __init__(self, threshold=0.25, alpha=0.3, probe_every=4, prior=1.0):
        self.threshold, self.alpha, self.probe_every = threshold, alpha, probe_every
        self.est = {n: prior for n in NS}
        self.skipped = {n: 0 for n in NS}

    def allow(self, n):
        if self.est[n] >= self.threshold:
            return True
        self.skipped[n] += 1
        if self.skipped[n] >= self.probe_every:
            self.skipped[n] = 0
            return True
        return False

    def update(self, n, accepted):
        self.est[n] += self.alpha * (accepted - self.est[n])


def batched_head(e, output_offset, chunk=8192):
    """v9f only: score slots 0..count-1 of the last batched pass in one head scan.

    cmd 11 applies the final norm to every slot and cmd 12 streams each head chunk
    once for all slots; slot b's (token, logit bits) word lands at output_offset+32*b.
    The C-sim audit (experiments/batched_head) shows each slot equals the v9e
    cmd 9/3/4 sequence bit for bit.
    """
    import struct

    def score(count):
        e.command(11, page=e.manifest['output_norm'], rows=count)
        for start in range(0, e.vocab, chunk):
            rows = min(chunk, e.vocab - start)
            e.command(12, page=e.head_offset + start * e.embedding_row_bytes, layer=count, rows=rows, token_base=start)
            e.head_rows += rows
        res = [struct.unpack_from('<II', e.scratch, output_offset + 32 * b) for b in range(count)]
        if any(not 0 <= t < e.vocab for t, _ in res):
            raise RuntimeError('Invalid FPGA vocabulary result')
        return res
    return score


def decode(e, ids, first_token, max_new, stop, drafter=None, gate=None, logit=None, first_bits=None, batched=None):
    """Greedy decode after prefill. `first_token` came from the prompt's last position.

    stop(tokens) -> True once generation must end (checked after every emitted token).
    drafter=None means plain one-token decoding (the RC1 reference path).
    batched=None scores each verify lane with cmd 9 + a full head scan (v9e);
    batched=batched_head(...) scores all lanes of a verify pass in one scan (v9f).
    Emitted tokens do not depend on `batched`; only the head work does.
    Returns (tokens, logit_bits or None, stats).
    """
    out = [first_token]
    bits = [first_bits if first_bits is not None else logit()] if logit else None
    st = dict(passes=0, ar_steps=0, drafted=0, accepted=0, head_scans=0, zero_accept=0, gated_off=0)
    if stop(out):
        return out, bits, st
    while len(out) < max_new:
        p = len(ids) + len(out) - 1                  # position of out[-1]; not yet in K/V
        d, n = (drafter.draft(ids + out) if drafter else ([], 0))
        d = d[:min(K, max_new - len(out) - 1, e.context - 1 - p)]
        if d and gate is not None and not gate.allow(n):
            st['gated_off'] += 1
            d = []
        if not d:
            token = e.step(out[-1], p, logits=True)
            st['ar_steps'] += 1; st['head_scans'] += 1
            out.append(token)
            if bits is not None:
                bits.append(logit())
            if stop(out):
                break
            continue
        e.prefill_batch([out[-1]] + d, p, logits=False)
        st['passes'] += 1; st['drafted'] += len(d)
        a, done = 0, False
        scored = None
        if batched is not None:
            scored = batched(len(d) + 1); st['head_scans'] += 1
        for lane in range(len(d) + 1):
            if scored is not None:
                token = scored[lane][0]
            else:
                if lane:
                    e.command(9, layer=lane)
                token = e.select_token(); st['head_scans'] += 1
            out.append(token)
            if bits is not None:
                bits.append(scored[lane][1] if scored is not None else logit())
            if stop(out) or len(out) >= max_new:
                done = True
                break
            if lane < len(d) and token == d[lane]:
                a += 1
                continue
            break
        st['accepted'] += a; st['zero_accept'] += (a == 0)
        if gate is not None:
            gate.update(n, a)
        if done:
            break
    return out, bits, st
