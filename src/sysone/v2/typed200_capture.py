"""Offline consistency checks for the frozen R5 v1 shared/typed200 PL ABI.

No MMIO, target control, admission authority or WCET certification lives here.
Only coherent, ownership-protected snapshots may be supplied. File bytes alone
cannot establish that a snapshot came from a deployed target or was atomic.
"""
from dataclasses import dataclass
import re
import struct

CONTRACT = '8133633315487f8f322ecac49e95e7aca3801d00fccb4b4fba36026c5b2752d2'
OUTCOMES = {1: 'accepted', 2: 'clarify', 3: 'abstain', 4: 'fault',
            5: 'deadline', 6: 'invalid'}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _uint(value, bits, name, *, nonzero=False):
    _require(type(value) is int and int(nonzero) <= value < 1 << bits,
             f'Invalid {name}')


@dataclass(frozen=True)
class ExpectedCapture:
    session: int
    request: int
    sequence: int
    tokens: int
    first: int
    count: int
    budget: int
    admitted: bool
    outcome: int
    label: int
    token_ids: tuple[int, ...] = ()
    contract_sha256: str = CONTRACT

    def __post_init__(self):
        for n, bits in [('session', 64), ('request', 64), ('sequence', 32),
                        ('tokens', 16), ('first', 16), ('count', 16),
                        ('budget', 32), ('outcome', 8), ('label', 16)]:
            _uint(getattr(self, n), bits, n,
                  nonzero=n in ('session', 'sequence'))
        _require(type(self.admitted) is bool, 'Invalid admission evidence flag')
        _require(type(self.token_ids) is tuple and len(self.token_ids) <= 128 and
                 len(self.token_ids) == min(self.tokens, 128), 'Expected token IDs required')
        for token in self.token_ids:
            _uint(token, 16, 'token ID')
        _require(type(self.contract_sha256) is str and
                 re.fullmatch('[0-9a-f]{64}', self.contract_sha256) and
                 self.contract_sha256 == CONTRACT, 'Unsupported frozen contract')
        _require(self.outcome in OUTCOMES, 'Invalid expected outcome')
        _require((self.outcome == 1 and self.label < 18) or
                 (self.outcome != 1 and self.label == 0), 'Invalid expected label')
        if self.admitted:
            _require(self.request > 0 and self.budget > 0 and
                     1 <= self.tokens <= 128 and 0 <= self.first < self.tokens and
                     1 <= self.count <= self.tokens-self.first,
                     'Invalid admitted identity/shape/budget')
            _require(self.outcome != 6, 'Admitted request cannot be INVALID')
            _require(all(t < 30522 for t in self.token_ids), 'Admitted token out of vocabulary')


@dataclass(frozen=True)
class Terminal:
    session: int
    request: int
    contract_sha256: str
    elapsed: int
    label: int
    outcome: int


def _terminal(session, request, digest, elapsed, label, score, outcome):
    _require(outcome in OUTCOMES, 'Unknown terminal outcome')
    _require(score == 0, 'Reserved score must be zero')
    _require(label < 18 if outcome == 1 else label == 0,
             'Noncanonical terminal label')
    return Terminal(session, request, digest, elapsed, label, outcome)


def decode_shared(data: bytes):
    """Decode exactly 384 bytes, with explicit frozen offsets (no host packing)."""
    _require(type(data) is bytes and len(data) == 384, 'Expected 384 shared bytes')
    magic, version, session, attest, boot, state, seq = struct.unpack_from('<IIQIIII', data)
    _require((magic, version, attest, boot, state) == (0x54594331, 1, 1, 1, 3),
             'Mailbox not a booted, completed v1 command')
    tokens, first, count, reserved, budget = struct.unpack_from('<HHHHI', data, 32)
    result_seq, origin = struct.unpack_from('<II', data, 300)
    _require(session != 0 and seq != 0 and seq == result_seq, 'Stale result sequence/session')
    _require(origin in (0, 1), 'Unknown result origin')
    _require(reserved == 0 and data[308:312] == bytes(4) and
             data[369:376] == bytes(7) and data[380:384] == bytes(4),
             'Nonzero reserved/padding bytes')
    _require(struct.unpack_from('<I', data, 376)[0] == 0, 'R5 exception reported')
    s, req = struct.unpack_from('<QQ', data, 312)
    age, label, score, outcome = struct.unpack_from('<IHHB', data, 360)
    terminal = _terminal(s, req, data[328:360].hex(), age, label, score, outcome)
    _require(s == session, 'Mailbox/result session mismatch')
    if origin == 0:
        _require(outcome in (4, 6) and age == 0, 'CPU record masquerades as PL terminal')
    return terminal, dict(sequence=seq, origin=origin, tokens=tokens,
                          first=first, count=count, budget=budget)


def decode_pl(data: bytes):
    """Decode a coherent, pre-ACK 0x100-byte little-endian CSR observation."""
    _require(type(data) is bytes and len(data) == 256, 'Expected 256 PL CSR bytes')
    words = struct.unpack('<64I', data)
    _require(words[0xc0//4] == 0x54590201, 'Wrong PL ABI')
    status = words[1]
    _require(status & ~31 == 0 and status & 0x17 == 0x14,
             'PL record is not stable configured terminal state')
    session = words[32] | words[33] << 32
    request = words[34] | words[35] << 32
    digest = b''.join(words[36+i].to_bytes(4, 'big') for i in reversed(range(8)))
    payload = words[0xb0//4]
    _require(payload & 0xfff8 == 0, 'PL outcome reserved bits set')
    terminal = _terminal(session, request, digest.hex(), words[0xb8//4],
                         payload >> 16, words[0xb4//4], payload & 7)
    if terminal.outcome in (4, 5):
        _require(status & 8 != 0, 'Fault/deadline lacks quarantine')
    elif terminal.outcome in (1, 2, 3):
        _require(status & 8 == 0, 'Useful terminal unexpectedly quarantined')
    return terminal, words


def assess_capture(shared: bytes, expected: ExpectedCapture, pl: bytes | None = None):
    """Validate identity/schema and measured age, never infer a hard bound."""
    terminal, meta = decode_shared(shared)
    for field in ('sequence', 'tokens', 'first', 'count', 'budget'):
        _require(meta[field] == getattr(expected, field), f'Command {field} mismatch')
    ids = struct.unpack_from('<'+str(len(expected.token_ids))+'H', shared, 44)
    _require(ids == expected.token_ids, 'Input token IDs mismatch')
    for field in ('session', 'request', 'contract_sha256', 'outcome', 'label'):
        _require(getattr(terminal, field) == getattr(expected, field), f'Terminal {field} mismatch')
    authoritative = meta['origin'] == 1
    if authoritative:
        _require(pl is not None, 'PL-origin record requires independent PL snapshot')
        observed, words = decode_pl(pl)
        _require(observed == terminal, 'Shared/PL terminal mismatch')
        if expected.admitted:
            _require(1 <= terminal.elapsed <= expected.budget, 'Terminal age outside admitted budget')
            if terminal.outcome == 5:
                _require(terminal.elapsed == expected.budget, 'Deadline age differs from D')
            _require(words[0xc4//4] == expected.tokens | expected.first << 16 and
                     words[0xc8//4] == expected.count, 'Owned PL shape mismatch')
        else:
            _require(terminal.outcome == 6 and terminal.elapsed == 0,
                     'Unadmitted PL record must be immediate INVALID')
        if terminal.outcome == 1:
            _require(expected.admitted and words[0xcc//4] & 31 == 30,
                     'Accepted lacks successful, quiet, permitted native epoch')
    return {'consistent': True, 'input_token_ids_match': True, 'outcome': OUTCOMES[terminal.outcome],
            'label': terminal.label if terminal.outcome == 1 else None,
            'origin': 'pl_terminal' if authoritative else 'cpu_rejection_or_fault',
            'elapsed_pl_cycles': terminal.elapsed if authoritative else None,
            'observed_terminal_within_budget': True if authoritative and expected.admitted else None,
            'expected_label_matches': terminal.outcome == 1,
            'target_execution_verified': False, 'successful_inference_guaranteed': False,
            'wcet_certified': False, 'external_delivery_guaranteed': False,
            'scope': 'Offline snapshot consistency; coherent capture and provenance must be established separately'}
