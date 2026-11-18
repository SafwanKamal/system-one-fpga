"""Reconstruct selected exact Ubuntu kernel sources for the installed R5 driver."""
import gzip
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'build/v2/typed200-amp-linux-r5-v1'
DOWNLOAD = BASE / 'source-download-v1'
WANTED = {
    'drivers/remoteproc/zynqmp_r5_remoteproc.c',
    'Documentation/devicetree/bindings/remoteproc/xilinx,zynqmp-r5-remoteproc.yaml',
    'drivers/remoteproc/remoteproc_core.c',
    'drivers/remoteproc/remoteproc_elf_loader.c',
    'drivers/remoteproc/remoteproc_sysfs.c',
    'drivers/remoteproc/remoteproc_internal.h',
    'drivers/firmware/xilinx/zynqmp.c',
    'drivers/firmware/xilinx/zynqmp-debug.c',
    'drivers/pmdomain/xilinx/zynqmp-pm-domains.c',
    'include/linux/firmware/xlnx-zynqmp.h',
    'include/dt-bindings/power/xlnx-zynqmp-power.h',
    'drivers/remoteproc/Kconfig',
    'drivers/remoteproc/Makefile',
    'drivers/of/overlay.c',
    'drivers/of/platform.c',
    'arch/arm64/boot/dts/xilinx/zynqmp.dtsi',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def patch(source, change):
    old = source.decode().splitlines(keepends=True)
    result = []
    pos = 0
    lines = change.splitlines(keepends=True)
    index = 0
    while index < len(lines):
        line = lines[index]
        match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
        if not match:
            index += 1
            continue
        start = max(int(match[1])-1, 0)
        assert start >= pos
        result.extend(old[pos:start])
        pos = start
        expected_old = int(match[2]) if match[2] is not None else 1
        expected_new = int(match[4]) if match[4] is not None else 1
        consumed = produced = 0
        index += 1
        while index < len(lines) and not lines[index].startswith('@@ '):
            row = lines[index]
            if row.startswith('\\ No newline'):
                raise RuntimeError('explicit no-newline handling required')
            if not row or row[0] not in ' +-':
                break
            if row[0] in ' -':
                assert pos < len(old) and old[pos] == row[1:], (pos, row[:100])
                pos += 1
                consumed += 1
            if row[0] in ' +':
                result.append(row[1:])
                produced += 1
            index += 1
        assert (consumed, produced) == (expected_old, expected_new)
    result.extend(old[pos:])
    return ''.join(result).encode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--attempt', required=True)
    ap.add_argument('--archive-dir', type=Path, required=True)
    args = ap.parse_args()
    assert re.fullmatch(r'kernel-source-v[0-9]+', args.attempt)
    out = BASE / args.attempt
    out.mkdir(exist_ok=False)
    descriptor = (DOWNLOAD/'linux-xilinx_6.8.0-1036.37.dsc').read_text()
    checksums = descriptor.split('Checksums-Sha256:\n', 1)[1].split('Files:', 1)[0]
    expected = {row.split()[2]: (row.split()[0], int(row.split()[1]))
                for row in checksums.splitlines() if row.strip()}
    for name in expected:
        p = args.archive_dir/name
        if not p.exists():
            url = 'https://archive.ubuntu.com/ubuntu/pool/universe/l/linux-xilinx/'+name
            with urllib.request.urlopen(url, timeout=60) as response, p.open('xb') as f:
                while data := response.read(1024*1024):
                    f.write(data)
        data = p.read_bytes()
        assert (sha(data), len(data)) == expected[name], name
    original = {}
    with tarfile.open(args.archive_dir/'linux-xilinx_6.8.0.orig.tar.gz', 'r|gz') as archive:
        for member in archive:
            name = member.name.split('/', 1)[-1]
            if member.isfile() and name in WANTED:
                original[name] = archive.extractfile(member).read()
    changes = {}
    diff = gzip.decompress((args.archive_dir/'linux-xilinx_6.8.0-1036.37.diff.gz').read_bytes()).decode()
    for block in re.split(r'(?m)^--- linux-xilinx-6.8.0.orig/', diff)[1:]:
        name = block.splitlines()[0].split('\t')[0]
        if name in WANTED:
            changes[name] = block
    records = {}
    for name in sorted(WANTED):
        assert name in original or name in changes, name
        result = patch(original.get(name, b''), changes[name]) if name in changes else original[name]
        path = out/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(result)
        records[name] = sha(result)
    receipt = dict(passed=True, package='linux-xilinx 6.8.0-1036.37',
                   descriptor_sha256=sha((DOWNLOAD/'linux-xilinx_6.8.0-1036.37.dsc').read_bytes()),
                   archives_sha256={n:h for n,(h,size) in expected.items()},
                   files_sha256=records, source_only=True, module_rebuilt=False,
                   descriptor_signature_verified=False)
    (out/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(f'PASS exact source-package checksums and contextual patch reconstruction: {len(records)} sources')


if __name__ == '__main__':
    main()
