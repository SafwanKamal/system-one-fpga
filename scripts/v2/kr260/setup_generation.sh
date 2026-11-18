#!/bin/sh
set -eu
TASK_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$TASK_DIR"
test "$(uname -m)" = aarch64 || { echo 'This setup is for the KR260 ARM CPU.'; exit 1; }
python3 - <<'PY'
import hashlib,json
from pathlib import Path
m=json.loads(Path('manifest.json').read_text())
for name,want in m['files'].items():
    h=hashlib.sha256()
    with Path(name).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''): h.update(b)
    if h.hexdigest()!=want: raise SystemExit(f'Payload hash mismatch: {name}')
print('Generation payload hashes verified',flush=True)
PY
if ! command -v cmake >/dev/null 2>&1 || ! command -v c++ >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y build-essential cmake
fi
if [ ! -d llama.cpp ]; then
    mkdir llama.cpp
    tar -xzf llama.cpp-source.tar.gz --strip-components=1 -C llama.cpp
fi
cmake -S llama.cpp -B llama.cpp/build -DCMAKE_BUILD_TYPE=Release \
  -DGGML_NATIVE=ON -DGGML_CPU_KLEIDIAI=OFF -DGGML_CUDA=OFF \
  -DGGML_VULKAN=OFF -DLLAMA_OPENSSL=OFF -DLLAMA_SUBPROCESS=OFF \
  -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF \
  -DLLAMA_BUILD_IS_DEV=OFF -DLLAMA_BUILD_HTML=OFF -DLLAMA_BUILD_UI=OFF \
  -DLLAMA_BUILD_APP=OFF
cmake --build llama.cpp/build --target llama-server -j 4
python3 run_generation_baseline.py \
  --server ./llama.cpp/build/bin/llama-server \
  --model ./Qwen3-0.6B-Q4_K_M.gguf --threads 4 \
  --report "$TASK_DIR/kr260-generation.json"
python3 run_generation_baseline.py \
  --server ./llama.cpp/build/bin/llama-server \
  --model ./Qwen3-0.6B-Q8_0.gguf --threads 4 \
  --report "$TASK_DIR/kr260-generation-q8.json"
