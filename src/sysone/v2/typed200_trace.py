"""Decode a committed one-shot diagnostic trace; no live target access."""
import struct
from .typed200_capture import ExpectedCapture, assess_capture

KINDS = ('init', 'boot_ready', 'start_submitted', 'admission_observed',
         'native_observed', 'copy_begin', 'copy_end', 'bridge_head_begin',
         'bridge_head_end', 'proposal_begin', 'proposal_end', 'terminal_observed',
         'capture_begin', 'capture_end', 'shared_done', 'ack_written', 'finish')


def assess_trace(data: bytes, expected: ExpectedCapture):
    def require(ok, message):
        if not ok:
            raise ValueError(message)
    require(type(data) is bytes and len(data) == 1488, 'Expected 1488 trace bytes')
    magic, version, committed, count, dropped, source, hz, valid = struct.unpack_from('<8I', data)
    require((magic, version, committed) == (0x54524331, 1, 1), 'Uncommitted/wrong trace ABI')
    require(1 <= count <= 32 and dropped == 0, 'Incomplete/overflowed event trace')
    require(valid in (0, 1) and ((valid == 0 and source == hz == 0) or
                               (valid == 1 and source > 0 and hz > 0)), 'Invalid clock metadata')
    session, request, seq, origin, pl_present, shared_present, status_after = struct.unpack_from('<QQ5I', data, 32)
    require((session, request, seq) == (expected.session, expected.request, expected.sequence),
            'Trace identity mismatch')
    require(origin in (0, 1) and pl_present in (0, 1) and shared_present == 1,
            'Missing/invalid snapshot markers')
    require(data[68:80] == bytes(12), 'Trace reserved bytes set')
    pl = data[80:336]
    shared = data[336:720]
    require(struct.unpack_from('<I', shared, 304)[0] == origin, 'Trace/shared origin mismatch')
    if pl_present:
        require(struct.unpack_from('<I', pl, 4)[0] == status_after, 'PL status changed during capture')
    else:
        require(pl == bytes(256) and status_after == 0, 'Unmarked raw PL data')
    require(origin == 0 or pl_present == 1, 'Authoritative record lacks pre-ACK capture')
    report = assess_capture(shared, expected, pl if origin == 1 else None)
    events = []
    for i in range(count):
        kind, tick, sequence, phase, req = struct.unpack_from('<4IQ', data, 720+24*i)
        require(1 <= kind <= len(KINDS) and phase <= 5, 'Invalid trace event')
        require(valid == 1 or tick == 0, 'Order-only trace has timestamp data')
        require((sequence, req) in ((0, 0), (expected.sequence, expected.request)),
                'Event identity differs from captured request')
        events.append({'kind': KINDS[kind-1], 'tick': tick if valid else None,
                       'sequence': sequence, 'phase': phase, 'request': req})
    require(data[720+24*count:] == bytes(24*(32-count)), 'Unused event slots nonzero')
    names = [e['kind'] for e in events]
    require(names == sorted(names, key=KINDS.index), 'Phase ordering invalid')
    require(names[0] == 'init' and names[-1] == 'finish', 'Incomplete event boundaries')
    require(len(names) == len(set(names)), 'Repeated one-shot event')
    require('shared_done' in names, 'Missing mailbox completion')
    if pl_present:
        require(all(n in names for n in ('terminal_observed', 'capture_begin', 'capture_end')),
                'Missing PL capture events')
        require(names.index('terminal_observed') < names.index('capture_begin') <
                names.index('capture_end') < names.index('shared_done'), 'Capture ordering invalid')
    if 'ack_written' in names:
        require(origin == 1 and expected.outcome in (1, 2, 3, 6), 'Unexpected recovery ACK')
        require(names.index('shared_done') < names.index('ack_written') < len(names)-1,
                'ACK before shared/capture completion')
    if origin == 1 and expected.outcome in (1, 2, 3):
        require('ack_written' in names, 'Reusable terminal missing ACK event')
    for begin, end in [('copy_begin', 'copy_end'), ('bridge_head_begin', 'bridge_head_end'),
                       ('proposal_begin', 'proposal_end')]:
        require((begin in names) == (end in names), 'Incomplete phase interval')
        if begin in names:
            require(names.index(begin) < names.index(end), 'Reversed phase interval')
    return {**report, 'trace_events': events, 'raw_pl_capture_present': bool(pl_present),
            'clock_source': source, 'declared_clock_hz': hz,
            'timestamps_supplied': bool(valid), 'timestamp_provenance_verified': False,
            'instrumentation_overhead_bounded': False,
            'scope': 'Offline diagnostic consistency; extra instructions/MMIO reads perturb target execution'}
