#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SOURCE="$ROOT/pamo"
VENV="$ROOT/venv"
PHASE="${1:-all}"
BASE_PYTHON="${PAMO_BASE_PYTHON:-/root/miniconda3/bin/python}"

export PATH="/usr/local/cuda/bin:/root/miniconda3/bin:$PATH"
export CUDA_HOME="${CUDA_HOME:-/usr/local/cuda}"
export TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -n 1 | tr -d '[:space:]')}"
export MAX_JOBS="${MAX_JOBS:-4}"

environment_report() {
  TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M:%S'
  nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap --format=csv
  nvcc --version
  "$BASE_PYTHON" --version
  "$BASE_PYTHON" -c 'import torch; print("torch", torch.__version__, "torch_cuda", torch.version.cuda)'
  printf 'TORCH_CUDA_ARCH_LIST=%s\n' "$TORCH_CUDA_ARCH_LIST"
}

setup_environment() {
  "$BASE_PYTHON" -m venv --system-site-packages "$VENV"
  "$VENV/bin/python" -m pip install --upgrade pip setuptools wheel
  "$VENV/bin/python" -m pip install --no-build-isolation \
    diso==0.1.4 \
    libigl==2.5.1 \
    numpy==1.26.4 \
    trimesh==4.4.0
  if [[ -d "$ROOT/cumesh2sdf" && -d "$ROOT/pdmc" ]]; then
    "$VENV/bin/python" -m pip install --no-build-isolation "$ROOT/cumesh2sdf" "$ROOT/pdmc"
  else
    "$VENV/bin/python" -m pip install --no-build-isolation \
      git+https://github.com/eliphatfs/cumesh2sdf.git@7789ade81bcd5fa77112d2cb5d825ed0e634e76b \
      git+https://github.com/seonghunn/pdmc.git@54406314bb9870c2c1b3c2badfde3f6d01f1e499
  fi
  (
    cd "$SOURCE/simp_cuda"
    FORCE_CUDA=1 "$VENV/bin/python" -m pip install --no-build-isolation .
  )
  (
    cd "$SOURCE/simp_cuda/safe_project/warp_"
    # Windows检出的packman脚本可能带CRLF，先恢复Linux解释器行尾。
    sed -i 's/\r$//' ./tools/packman/packman
    chmod +x ./tools/packman/packman
    "$VENV/bin/python" build_lib.py --cuda_path "$CUDA_HOME"
    "$VENV/bin/python" -m pip install --no-build-isolation .
  )
  "$VENV/bin/python" -m pip install --no-build-isolation "$SOURCE/simp_cuda/safe_project"
  "$VENV/bin/python" -m pip freeze > "$ROOT/dependencies.txt"
}

run_cases() {
  # 当前实例的Conda C++库较旧，Warp需要系统库中的GLIBCXX_3.4.30。
  conda_lib="$(dirname "$(dirname "$BASE_PYTHON")")/lib/libstdc++.so.6"
  system_lib=/usr/lib/x86_64-linux-gnu/libstdc++.so.6
  if [[ -f "$conda_lib" && -f "$system_lib" ]] && \
    ! strings "$conda_lib" | grep '^GLIBCXX_3\.4\.30$' >/dev/null && \
    strings "$system_lib" | grep '^GLIBCXX_3\.4\.30$' >/dev/null; then
    export LD_PRELOAD="$system_lib${LD_PRELOAD:+:$LD_PRELOAD}"
  fi
  "$VENV/bin/python" "$ROOT/run_pamo_author.py" \
    --pamo-root "$SOURCE" \
    --input-dir "$ROOT/inputs" \
    --output-dir "$ROOT/outputs" \
    --ratio 1.0
}

case "$PHASE" in
  environment)
    environment_report
    ;;
  setup)
    environment_report
    setup_environment
    ;;
  run)
    environment_report
    run_cases
    ;;
  all)
    environment_report
    setup_environment
    run_cases
    ;;
  *)
    echo "usage: $0 [environment|setup|run|all]" >&2
    exit 2
    ;;
esac
