"""Independent encoded-register firewall oracle. Host only; no board access.

These tests validate a proposed register image, not silicon enforcement, source
provenance, quiescence, or downstream peripheral TrustZone configuration.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'build/v2/typed200-amp-ownership-v1'

# Review specification, intentionally independent of plan metadata/region lists.
FPD_SECURE = [(0xfd000000, 0xfd0a0000), (0xfd1a0000, 0xfd1b0000),
 (0xfd360000, 0xfd3c0000), (0xfd5d0000, 0xfd600000),
 (0xfd610000, 0xfd620000), (0xfd690000, 0xfd6a0000),
 (0xfd6e0000, 0xfd710000), (0xfd800000, 0xfd820000),
 (0xfd4f0000, 0xfd500000), (0xfd4d0000, 0xfd4e0000)]
LPD_SECURE = set(range(0xe0, 0xf0)) | set(range(392, 400)) | {
 2, 3, 0x0a, 0x0f, 0x15, 0x18, 0x24, 0x41, 0x4b, 0x5e,
 0x96, 0x98, 0x9a, 0x9b, 0xa5, 0xa7, 400,
 0xc8, 0xca, 0xcb, 0xcc, 0xcd, 0xce, 0xd0, 0xd4, 0xd5, 0xd6, 0xd8}


def image(plan):
    regs = {}
    for op in plan['writes']:
        a, m, v = (op[k] for k in ('address', 'mask', 'value'))
        regs[a] = (regs.get(a, 0) & ~m) | v
    return regs


def xmpu(regs, base, address, mid, secure, write, shift):
    chosen = None
    for i in range(16):
        a = base + 0x100 + i * 16
        c = regs[a + 12]
        if not c & 1:
            continue
        master = regs[a + 8]
        if (regs[a] << shift) <= address <= ((regs[a + 4] + 1) << shift) - 1:
            if mid & ((master >> 16) & 1023) == master & ((master >> 16) & 1023):
                chosen = c
    if chosen is None:
        return bool(regs[base] & (2 if write else 1))
    ns = bool(chosen & 8)
    # UG1085 p393 higher-numbered match wins; strict NSCheckType=1.
    if (not secure and not ns) or (secure and ns and chosen & 16):
        return False
    return bool(chosen & (4 if write else 2))


def xppu(regs, aperture, mid, secure, write):
    control = regs[0xff980000]
    assert control & 7 == 7
    perm = regs[0xff981000 + 4 * aperture]
    for bit, mask in [(28, 0x1f), (29, 0x3e0), (30, 0x7c00), (31, 0x080f8000)]:
        if ((perm & mask).bit_count() & 1) != ((perm >> bit) & 1):
            return False
    if not secure and not perm & (1 << 27):
        return False
    for i in range(20):
        if not perm & (1 << i):
            continue
        p = regs[0xff980100 + 4 * i]
        if p.bit_count() & 1:
            continue
        mask = (p >> 16) & 1023
        if mid & mask == p & mask and not (write and p & (1 << 30)):
            return True
    return False


def xppu_expected(i, mid, secure):
    r5 = mid < 16
    pmu = mid == 0x40
    apu = 0x80 <= mid < 0xc0
    # UG1085 p405: TRUSTZONE=1 allows BOTH security states, not strict NS.
    if i in (302, 303, 372, 373) or i == 0x30:
        return apu or pmu
    if i in (270, 271, 368, 369):
        return secure and (r5 or pmu)
    if 256 <= i < 384:
        return secure and pmu
    if i in LPD_SECURE or 0x30 <= i < 0x40:
        return secure and (r5 or pmu)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--attempt', required=True)
    ap.add_argument('--plan', default='protection-plan-v4')
    a = ap.parse_args()
    assert a.attempt.startswith('firewall-v') and a.attempt[10:].isdigit()
    assert a.plan.startswith('protection-plan-v') and a.plan[17:].isdigit()
    out = BASE / a.attempt
    out.mkdir(exist_ok=False)
    source = BASE / a.plan / 'plan.json'
    regs = image(json.loads(source.read_text()))
    counts = {'fpd': 0, 'ocm': 0, 'xppu': 0}
    addresses = {0, (1 << 32) - 1}
    for lo, hi in FPD_SECURE:
        addresses.update((lo - 1, lo, lo + 4095, hi - 1, hi, hi + 4095))
    for addr in sorted(addresses):
        for mid in range(1024):
            for secure in (False, True):
                for write in (False, True):
                    expected = secure == any(lo <= addr < hi for lo, hi in FPD_SECURE)
                    got = xmpu(regs, 0xfd5d0000, addr, mid, secure, write, 12)
                    assert got == expected, ('fpd', addr, mid, secure, write)
                    counts['fpd'] += 1
    for addr in (0, 0xfffbffff, 0xfffc0000, 0xfffc0fff, 0xffffffff):
        for mid in range(1024):
            for secure in (False, True):
                for write in (False, True):
                    got = xmpu(regs, 0xffa70000, addr, mid, secure, write, 12)
                    assert got == (addr >= 0xfffc0000 and secure), ('ocm', addr, mid)
                    counts['ocm'] += 1
    for i in range(401):
        for mid in range(1024):
            for secure in (False, True):
                for write in (False, True):
                    got = xppu(regs, i, mid, secure, write)
                    assert got == xppu_expected(i, mid, secure), ('xppu', i, mid, secure, write)
                    counts['xppu'] += 1
    # Mutations prove tests observe the permission decisions, not just metadata.
    mutations = []
    altered = dict(regs)
    altered[0xff981000 + 4 * 0x98] = 0x98000008  # valid parity, ALL + both TZ
    assert xppu(altered, 0x98, 0x80, False, True)
    assert not xppu_expected(0x98, 0x80, False)
    mutations.append('NS APU access to XPPU configuration detected')
    altered = dict(regs)
    altered[0xff981000 + 4 * 270] ^= 1 << 28
    assert not xppu(altered, 270, 0, True, False)
    mutations.append('bad aperture parity denies R5 IPI access')
    altered = dict(regs)
    altered[0xfd5d010c + 16 * 2] = 0  # disable CRF protection region
    assert xmpu(altered, 0xfd5d0000, 0xfd1a0000, 0x80, False, True, 12)
    mutations.append('removed CRF isolation detected')
    result = dict(passed=True, plan_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  cases=counts, mutation_checks=mutations, target_executed=False,
                  assumptions=['UG1085 register semantics', 'trusted actual source/security tags',
                               'all writes take effect', 'peripheral TZ configuration compatible'],
                  deployable=False)
    (out / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
