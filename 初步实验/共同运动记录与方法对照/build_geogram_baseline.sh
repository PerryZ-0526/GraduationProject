#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../.." && pwd)"
SOURCE="${ROOT}/reference/近期强基线_20260908/geogram"
BUILD="${SOURCE}/build/Darwin-aarch64-clang-dynamic-Release"
BINARY="${ROOT}/tmp/geogram/geogram_boolean"
EXPECTED_COMMIT="130442ff0f0c069d48ab4ebb4012218f3d861cf2"
UV="${HOME}/.local/bin/uv"

if ! git -C "${SOURCE}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "缺少Geogram子模块，请先执行: git submodule update --init --recursive" >&2
    exit 2
fi
if [[ "$(git -C "${SOURCE}" rev-parse HEAD)" != "${EXPECTED_COMMIT}" ]]; then
    echo "Geogram提交与冻结版本不一致" >&2
    exit 3
fi
if [[ ! -x "${UV}" ]]; then
    echo "未找到uv: ${UV}" >&2
    exit 4
fi

"${UV}" tool run --from cmake cmake \
    -S "${SOURCE}" \
    -B "${BUILD}" \
    -DCMAKE_BUILD_TYPE=Release \
    -DVORPALINE_PLATFORM=Darwin-aarch64-clang-dynamic \
    -DGEOGRAM_WITH_GRAPHICS=OFF \
    -DGEOGRAM_WITH_EXPLORAGRAM=OFF \
    -DGEOGRAM_WITH_TETGEN=OFF \
    -DGEOGRAM_WITH_TRIANGLE=OFF \
    -DGEOGRAM_WITH_HLBFGS=OFF \
    -DGEOGRAM_WITH_LEGACY_NUMERICS=OFF \
    -DGEOGRAM_WITH_LUA=OFF
"${UV}" tool run --from cmake cmake --build "${BUILD}" --target geogram -j 6

mkdir -p "$(dirname "${BINARY}")"
clang++ -O3 -std=c++17 \
    "${HERE}/geogram_boolean.cpp" \
    -I "${SOURCE}/src/lib" \
    -L "${BUILD}/lib" \
    -Wl,-rpath,"${BUILD}/lib" \
    -lgeogram \
    -o "${BINARY}"

echo "${BINARY}"
