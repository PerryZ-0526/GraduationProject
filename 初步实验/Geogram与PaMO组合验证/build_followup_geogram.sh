#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo '用法: build_followup_geogram.sh <固定源码目录> <适配器CPP> <输出二进制>' >&2
    exit 2
fi

source_dir="$(realpath "$1")"
adapter="$(realpath "$2")"
binary="$3"
build_dir="${source_dir}/build/followup-linux64-gcc-dynamic"

cmake -S "${source_dir}" -B "${build_dir}" \
    -DCMAKE_BUILD_TYPE=Release \
    -DVORPALINE_PLATFORM=Linux64-gcc-dynamic \
    -DGEOGRAM_WITH_GRAPHICS=OFF \
    -DGEOGRAM_WITH_EXPLORAGRAM=OFF \
    -DGEOGRAM_WITH_TETGEN=OFF \
    -DGEOGRAM_WITH_TRIANGLE=OFF \
    -DGEOGRAM_WITH_HLBFGS=OFF \
    -DGEOGRAM_WITH_LEGACY_NUMERICS=OFF \
    -DGEOGRAM_WITH_LUA=OFF
cmake --build "${build_dir}" --target geogram -j 6

mkdir -p "$(dirname "${binary}")"
g++ -O3 -std=c++17 "${adapter}" \
    -I "${source_dir}/src/lib" \
    -L "${build_dir}/lib" \
    -Wl,-rpath,"${build_dir}/lib" \
    -lgeogram -o "${binary}"
sha256sum "${binary}"
