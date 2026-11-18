"""Offline consistency gate for the cold-boot sole-R5 candidate; no target control.

Bytes cannot establish authentic capture, continuous ownership or clock bounds.
The final mailbox uses boot_status=2 (parked), unlike frozen v1's boot_status=1.
"""
import struct
from .typed200_timed import assess_timed_trace

R5_NOMINAL_HZ = 533328000


def assess_mvp(trace, pmu, final_shared, boot, owner, permit, expected):
    def require(ok, message):
        if not ok:
            raise ValueError(message)
    for data, size in ((trace, 1488), (pmu, 72), (final_shared, 384),
                       (boot, 64), (owner, 12), (permit, 4)):
        require(type(data) is bytes and len(data) == size, 'Wrong MVP snapshot ABI')
    magic, version, session, hz, *reserved = struct.unpack('<IIQ12I', boot)
    require((magic, version, session, hz) ==
            (0x4d565031, 1, expected.session, R5_NOMINAL_HZ) and not any(reserved),
            'MVP boot identity/profile mismatch')
    fault, checks, established = struct.unpack('<3I', owner)
    require(fault == 0 and 2 <= checks < 0xffffffff and established == 1,
            'Ownership not established or faulted')
    require(permit == bytes(4), 'Permit not low at parked capture')
    require(struct.unpack_from('<I', final_shared, 20)[0] == 2 and
            struct.unpack_from('<I', final_shared, 376)[0] == 0,
            'MVP not successfully parked or exception present')
    normalized = bytearray(final_shared)
    struct.pack_into('<I', normalized, 20, 1)
    require(bytes(normalized) == trace[336:720], 'Final record differs from pre-ACK trace')
    require(struct.unpack_from('<I', pmu, 24)[0] == hz, 'Wrong declared PMU frequency')
    result = assess_timed_trace(trace, pmu, expected)
    return {**result, 'mvp_parked_consistency_passed': True, 'ownership_checks': checks,
            'continuous_hardware_ownership_verified': False,
            'target_execution_verified': False,
            'profile': 'cold-boot, sole R5_0, trusted PMU/CSU/boot/debug, one preloaded request',
            'scope': 'Offline snapshot consistency only; not target provenance, wall-time or WCET'}
