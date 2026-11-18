"""Resume the one interrupted Ubuntu archive download using verified ranges."""
from pathlib import Path
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'build/v2/typed200-amp-linux-r5-v1'


def main():
    out = BASE/'source-download-v2'
    out.mkdir(exist_ok=False)
    prefix = (BASE/'source-download-v1/linux-xilinx_6.8.0.orig.tar.gz').read_bytes()
    total = 230060117
    chunks = [prefix]
    records = []
    start = len(prefix)
    url = 'https://archive.ubuntu.com/ubuntu/pool/universe/l/linux-xilinx/linux-xilinx_6.8.0.orig.tar.gz'
    while start < total:
        end = min(start+8*1024*1024, total)-1
        request = urllib.request.Request(url, headers={'Range': f'bytes={start}-{end}'})
        with urllib.request.urlopen(request, timeout=30) as r:
            assert r.status == 206 and r.headers['Content-Range'] == f'bytes {start}-{end}/{total}'
            data = r.read()
        assert len(data) == end-start+1
        (out/f'range-{start}-{end}.bin').write_bytes(data)
        chunks.append(data)
        records.append(dict(start=start, end=end, sha256=hashlib.sha256(data).hexdigest()))
        start = end+1
        (out/'ranges.json').write_text(json.dumps(records,indent=2)+'\n')
        print(f'Downloaded {start}/{total} bytes', flush=True)
    data = b''.join(chunks)
    assert len(data) == total
    assert hashlib.sha256(data).hexdigest() == '26512115972bdf017a4ac826cc7d3e9b0ba397d4f85cd330e4e4ff54c78061c8'
    (out/'linux-xilinx_6.8.0.orig.tar.gz').write_bytes(data)
    for name in ['linux-xilinx_6.8.0-1036.37.dsc', 'linux-xilinx_6.8.0-1036.37.diff.gz']:
        (out/name).write_bytes((BASE/'source-download-v1'/name).read_bytes())
    (out/'receipt.json').write_text(json.dumps(dict(passed=True, total_bytes=total,
        sha256=hashlib.sha256(data).hexdigest(),partial_attempt_preserved=True),indent=2)+'\n')
    print('PASS complete archive matches exact Ubuntu source descriptor',flush=True)


if __name__ == '__main__':
    main()
