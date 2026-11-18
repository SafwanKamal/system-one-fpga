"""Run frozen synthetic H1024 boundary cases on the verified KR260 app."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys


def load_vectors(directory):
    manifest = json.loads((directory / 'manifest.json').read_text())
    image = (directory / 'image.bin').read_bytes()
    if (manifest.get('synthetic') is not True or manifest.get('reference_verified') is not True
            or manifest['dims']['hidden'] != 1024 or len(image) != manifest['bytes']
            or hashlib.sha256(image).hexdigest() != manifest['sha256']):
        raise ValueError('Unverified H1024 image')
    cases = []
    for index, expected_tokens in enumerate(manifest['token_lengths']):
        fields = (directory / f'case_{index}.txt').read_text().split()
        n, hidden, program, ids, result = map(int, fields[:5])
        count = (2*n + 15)//16
        words = [int(value, 16).to_bytes(16, 'little') for value in fields[5:]]
        if n != expected_tokens or hidden != 1024 or len(words) != count+n*hidden//16:
            raise ValueError('Invalid H1024 frozen case')
        cases.append((n, hidden, program, ids, result, b''.join(words[:count]), b''.join(words[count:])))
    return manifest, image, cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('vectors', type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    args = parser.parse_args()
    manifest, image, cases = load_vectors(args.vectors)
    sys.path.insert(0, str(args.repo.resolve() / 'src'))
    from sysone.v2.kr260_link import Kr260Link
    from sysone.v2.kr260_runtime import discover_memory
    memory = discover_memory()
    base, size = memory
    if manifest['base'] != base or len(image) > size:
        raise ValueError('H1024 image exceeds verified boot reservation')
    for n, hidden, program, ids, result, id_bytes, expected in cases:
        for address, length in ((program, 16), (ids, len(id_bytes)), (result, len(expected))):
            if address % 16 or not base <= address < address+length <= base+size:
                raise ValueError('H1024 descriptor exceeds verified boot reservation')
    link = Kr260Link(memory=memory)
    try:
        if link.build['max_hidden'] < 1024:
            raise ValueError('Loaded app lacks H1024 capacity')
        link.write(base, image)
        link.verify_loaded_image(base, image)
        results = []
        for n, hidden, program, ids, result, id_bytes, expected in cases:
            link.write(ids, id_bytes)
            run = link.run(struct.pack('<IHHII', program, n, hidden, ids, result))
            got = link.read(result, len(expected))
            if run.status or got != expected:
                raise RuntimeError(f'H1024 {n}-token hardware result mismatch: status {run.status}')
            results.append({'tokens': n, 'hidden': hidden, 'bit_exact': True,
                            'expected_sha256': hashlib.sha256(expected).hexdigest(),
                            'hardware_sha256': hashlib.sha256(got).hexdigest(),
                            'encoder_clocks': run.encoder_clocks, 'request_clocks': run.total_clocks,
                            'performance_counters': link.performance_counters()})
            print(f'H1024 {n} tokens: bit-exact', flush=True)
        args.report.write_text(json.dumps({'synthetic': True, 'image_sha256': manifest['sha256'],
                                         'clock_hz': link.clock_hz, 'cases': results}, indent=2)+'\n')
    finally:
        link.close()


if __name__ == '__main__':
    main()
