"""Independent Python layout oracle for the experimental logical KV RTL span."""
import random
from pathlib import Path
import sys

from sysone.v2.kv_cache_layout import KvCacheLayout
from sysone.v2.memory_window import MemoryWindow


def main(output):
    rng = random.Random(20261014)
    cases = [
        (1 << 32, 0, 16, 1 << 27, 1, 0, 1, (1 << 27)-1, 1),
        (1024, 896, 32, 2, 1, 0, 1, 1, 1),
        (1 << 32, 0, 0xfffffff0, 0xffffffff, 65535, 0, 0, 0, 1),
        (1 << 32, 0xfffffff0, 16, 1, 1, 0, 0, 0, 1),
    ]
    for _ in range(6000):
        stride = rng.choice([16, 32, 64, 256, 1024, 65536, 0xfffffff0])
        capacity = rng.choice([1, 2, 128, 4096, 65536, 1 << 27, 0xffffffff])
        layers = rng.choice([1, 2, 32, 65535])
        size = rng.choice([1024, 1 << 20, 256 << 20, 1 << 32])
        offset = rng.choice([0, 16, 1024, 0xfffffff0])
        layer = rng.choice([0, layers-1, layers])
        first = rng.choice([0, capacity-1, capacity, 0xffffffff])
        count = rng.choice([0, 1, 2, capacity, 0xffffffff])
        cases.append((size, offset, stride, capacity, layers, min(layer, 65535), rng.randrange(2), first, count))
    # Sustained valid traffic, including small rows, slices spanning multiple
    # finite-width descriptors and every layer/matrix's final token.
    for _ in range(4000):
        layers = rng.randint(1, 32)
        capacity = rng.randint(1, 4096)
        stride = 16 * rng.randint(1, 64)
        offset = 16 * rng.randint(0, 256)
        first = rng.randrange(capacity)
        count = rng.randint(1, capacity-first)
        cases.append((1 << 32, offset, stride, capacity, layers, rng.randrange(layers), rng.randrange(2), first, count))
    for index in range(9):
        row = [4096, 0, 16, 2, 1, 0, 0, 0, 1]
        if index == 0: row[0] = 0
        if index == 1: row[0] = (1 << 32) + 16
        if index == 2: row[1] = 1
        if index == 3: row[2] = 0
        if index == 4: row[2] = 17
        if index == 5: row[3] = 0
        if index == 6: row[4] = 0
        if index == 7: row[7] = 2
        if index == 8: row[8] = 0
        cases.append(tuple(row))
    widths = (33, 32, 32, 32, 16, 16, 1, 32, 32, 32, 33, 2)
    records = []
    for size, offset, stride, capacity, layers, layer, kind, first, count in cases:
        address = length = error = 0
        try:
            layout = KvCacheLayout(MemoryWindow(0x800000000, size), offset,
                                   layers, 1, stride, capacity)
            if stride % 16:
                raise ValueError('RTL requires a pre-padded stride')
        except ValueError:
            error = 1
        else:
            if layer >= layers or count == 0 or first + count > capacity:
                error = 2
            else:
                address, _ = layout.token_span(layer, 'value' if kind else 'key', first)
                length = count * stride
        fields = (size, offset, stride, capacity, layers, layer, kind, first, count, address, length, error)
        packed = 0
        for field, width in zip(fields, widths):
            assert 0 <= field < 1 << width
            packed = (packed << width) | field
        records.append(f'{packed:074x}\n')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'vectors.hex').write_text(''.join(records))
    (output / 'count.txt').write_text(str(len(records)) + '\n')
    print('KV span reference vectors:', len(records))


if __name__ == '__main__':
    main(sys.argv[1])
