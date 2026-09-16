#!/usr/bin/env bash
# 固定线程预算和北京时间，全部GPU实验串行，失败即停止。
set -euo pipefail
export TZ=Asia/Shanghai
export PATH=/root/autodl-tmp/graduation_project/venv/bin:/usr/local/cuda/bin:$PATH
export CUDA_PATH=/usr/local/cuda
export OMP_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4
export MKL_NUM_THREADS=4
export QT_QPA_PLATFORM=offscreen
cd /root/autodl-tmp/graduation_project/stage1
# 独立I/O适配器不修改Geogram布尔算法；显式构建以确保新环境可复现。
g++ -O3 -std=c++17 -I/root/autodl-tmp/graduation_project/baselines/geogram/src/lib 初步实验/CUDA真实骨面对照/geogram_double_io.cpp -L/root/autodl-tmp/graduation_project/build/geogram/lib -Wl,-rpath,/root/autodl-tmp/graduation_project/build/geogram/lib -lgeogram -ltbb -o /root/autodl-tmp/graduation_project/cuda_stage0/geogram_double_io
python 初步实验/局部适用域与核显计算/test_local.py
python 初步实验/边界过渡带联合重建/test_joint.py
python 初步实验/真实骨面共边拼接/test_stitch.py
python 初步实验/真实骨面高度图验证/test_projection.py
python 初步实验/局部区域重建阶段一/test_patch.py
python 初步实验/CUDA真实骨面对照/test_cuda.py
python 初步实验/CUDA真实骨面对照/test_geogram_io.py
python 初步实验/CUDA真实骨面对照/run_comparison.py
