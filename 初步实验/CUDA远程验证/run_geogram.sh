#!/usr/bin/env bash
# 使用本地固定快照构建无窗口基线，不改动第三方源码。
set -euo pipefail
export TZ=Asia/Shanghai
cd /root/autodl-tmp/graduation_project
mkdir -p baselines
if [ ! -d baselines/geogram ]; then
    tar -xzf geogram-baseline.tar.gz -C baselines
fi
# GCC并行STL检测到系统TBB头文件，需要显式链接已安装的TBB运行库。
cmake -S baselines/geogram -B build/geogram -DCMAKE_BUILD_TYPE=Release -DGEOGRAM_WITH_GRAPHICS=OFF -DGEOGRAM_WITH_TETGEN=OFF -DGEOGRAM_WITH_TRIANGLE=OFF -DCMAKE_CXX_STANDARD_LIBRARIES=-ltbb
cmake --build build/geogram --target geocsg -j 6
mkdir -p results/geogram_smoke
# 作者自带例子仅用于构建验收，不是本课题轨迹竞争实验。
build/geogram/bin/geocsg example004 results/geogram_smoke/example004.obj
