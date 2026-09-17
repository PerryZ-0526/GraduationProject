#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SOURCE="$ROOT/pamo"
VENV="$ROOT/venv"
PHASE="${1:-all}"
BASE_PYTHON="${PAMO_BASE_PYTHON:-/root/miniconda3/bin/python}"

export PATH="/usr/local/cuda/bin:/root/miniconda3/bin:$PATH"
export CUDA_HOME="${CUDA_HOME:-/usr/local/cuda}"
export TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-8.9}"
export MAX_JOBS="${MAX_JOBS:-4}"

environment_report() {
  TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M:%S'
  nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap --format=csv
  nvcc --version
  "$BASE_PYTHON" --version
}

setup_environment() {
  "$BASE_PYTHON" -m venv --system-site-packages "$VENV"
  "$VENV/bin/python" -m pip install --upgrade pip setuptools wheel
  "$VENV/bin/python" -m pip install \
    diso==0.1.4 \
    libigl==2.5.1 \
    numpy==1.26.4 \
    trimesh==4.4.0 \
    git+https://github.com/eliphatfs/cumesh2sdf.git \
    git+https://github.com/seonghunn/pdmc.git
  (
    cd "$SOURCE/simp_cuda"
    FORCE_CUDA=1 "$VENV/bin/python" -m pip install .
  )
  (
    cd "$SOURCE/simp_cuda/safe_project/warp_"
    chmod +x ./tools/packman/packman
    "$VENV/bin/python" build_lib.py --cuda_path "$CUDA_HOME"
    "$VENV/bin/python" -m pip install .
  )
  "$VENV/bin/python" -m pip install "$SOURCE/simp_cuda/safe_project"
}

run_cases() {
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
