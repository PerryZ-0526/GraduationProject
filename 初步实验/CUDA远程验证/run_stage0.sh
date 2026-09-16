#!/usr/bin/env bash
# 仅在项目远端目录编译和运行，不修改系统驱动与全局环境。
set -euo pipefail
export TZ=Asia/Shanghai
export PATH=/usr/local/cuda/bin:/root/autodl-tmp/graduation_project/venv/bin:$PATH
cd /root/autodl-tmp/graduation_project
stamp=$(date +%Y%m%d_%H%M%S)
out="results/$stamp"
mkdir -p "$out"
nvidia-smi -q > "$out/gpu.txt"
nvcc --version > "$out/toolkit.txt"
python -m pip freeze > "$out/python_packages.txt"
lscpu > "$out/cpu.txt"
# 双端关闭融合，禁止fast-math，CUDA按实际设备sm_89编译。
nvcc -O3 -std=c++17 -arch=sm_89 --fmad=false -Xcompiler=-fopenmp,-ffp-contract=off cuda_stage0/sweep_benchmark.cu -o cuda_stage0/sweep_benchmark
sha256sum cuda_stage0/sweep_benchmark.cu cuda_stage0/sweep_benchmark > "$out/checksums.txt"
OMP_NUM_THREADS=4 cuda_stage0/sweep_benchmark > "$out/sweep.json"
printf '%s\n' "$out"
