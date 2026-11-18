"""Fetch pinned official Qwen/llama.cpp artifacts for an isolated CPU baseline."""
from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[3]
TAG = 'b11540'
REVISION = '23749fefcc72300e3a2ad315e1317431b06b590a'
Q8_SHA = '9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def download(url, path, expected=None, size=None):
    if path.exists() and (expected is None or sha(path) == expected):
        return
    print(f'Downloading {path.name}', flush=True)
    tmp = path.with_suffix(path.suffix + '.download')
    if size:
        block = 4 * 1024 * 1024
        def fetch(start):
            end = min(size, start+block)-1
            req = urllib.request.Request(url, headers={'Range':f'bytes={start}-{end}'})
            with urllib.request.urlopen(req, timeout=60) as response:
                if response.headers.get('Content-Range') != f'bytes {start}-{end}/{size}':
                    raise ValueError('Download server did not honor byte range')
                data=response.read()
                if len(data)!=end-start+1:raise ValueError('Incomplete byte range')
                return start,data
        with tmp.open('wb') as handle, ThreadPoolExecutor(max_workers=4) as pool:
            handle.truncate(size)
            tasks=[pool.submit(fetch,start) for start in range(0,size,block)]
            completed=0
            for future in as_completed(tasks):
                start,data=future.result()
                handle.seek(start);handle.write(data)
                completed+=len(data)
                if completed//(64*1024*1024)!=(completed-len(data))//(64*1024*1024):
                    print(f'Downloaded {completed//(1024*1024)} / {size//(1024*1024)} MiB',flush=True)
    else:
        with urllib.request.urlopen(url, timeout=120) as response, tmp.open('wb') as handle:
            shutil.copyfileobj(response, handle, 4 * 1024 * 1024)
    if expected and sha(tmp) != expected:
        raise ValueError(f'Hash mismatch: {path.name}')
    tmp.replace(path)


def main():
    work = ROOT / 'build/v2/generation'
    work.mkdir(parents=True, exist_ok=True)
    q8 = ROOT / 'models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf'
    q8.parent.mkdir(parents=True, exist_ok=True)
    download(f'https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/{REVISION}/{q8.name}?download=true', q8, Q8_SHA,639446688)
    license_path = q8.parent / 'LICENSE'
    download(f'https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/{REVISION}/LICENSE', license_path)
    binary_zip = work / f'llama-{TAG}-bin-win-cpu-x64.zip'
    download(f'https://github.com/ggml-org/llama.cpp/releases/download/{TAG}/{binary_zip.name}', binary_zip)
    win = work / 'windows'
    win.mkdir(exist_ok=True)
    with zipfile.ZipFile(binary_zip) as archive:
        archive.extractall(win)
    quantizer = next(win.rglob('llama-quantize.exe'))
    kit = work / 'kr260-generation'
    kit.mkdir(exist_ok=True)
    q4 = kit / 'Qwen3-0.6B-Q4_K_M.gguf'
    if not q4.exists():
        subprocess.run([str(quantizer), '--allow-requantize', str(q8), str(q4), 'Q4_K_M'], check=True)
    kit_q8 = kit / q8.name
    if not kit_q8.exists() or sha(kit_q8) != Q8_SHA:
        shutil.copy2(q8, kit_q8)
    source = kit / 'llama.cpp-source.tar.gz'
    download(f'https://api.github.com/repos/ggml-org/llama.cpp/tarball/{TAG}', source)
    for name in ('run_generation_baseline.py', 'setup_generation.sh'):
        shutil.copy2(ROOT / 'scripts/v2/kr260' / name, kit / name)
    shutil.copy2(license_path, kit / 'QWEN-LICENSE')
    manifest = {'model_repo': 'Qwen/Qwen3-0.6B-GGUF', 'model_revision': REVISION,
                'llama_cpp_tag': TAG, 'input_q8_sha256': Q8_SHA,
                'quantization': 'Q4_K_M requantized locally from official Q8_0 with --allow-requantize',
                'backend': 'CPU; no FPGA decoder',
                'files': {p.name: sha(p) for p in kit.iterdir() if p.is_file() and p.name != 'manifest.json'}}
    (kit / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    out = ROOT / 'build/v2/kr260-generation.tar.gz'
    with tarfile.open(out, 'w:gz') as archive:
        for p in sorted(kit.iterdir()):
            archive.add(p, arcname=p.name)
    print(f'Prepared {out} ({out.stat().st_size:,} bytes)', flush=True)


if __name__ == '__main__':
    main()
