#!/usr/bin/env bash
# 只在本实验隔离目录创建工具环境和构建产物，不执行系统安装。
set -eu
cd /root/autodl-tmp/graduation_project/build_rxmesh_dynamic_20260908_141858
export TZ=Asia/Shanghai
export OMP_NUM_THREADS=4
export PATH=/usr/local/cuda/bin:/root/miniconda3/bin:$PATH
mkdir -p tmp pip_cache
export TMPDIR="$PWD/tmp"
export PIP_CACHE_DIR="$PWD/pip_cache"
case "${1:?需要setup、dependencies、configure或build阶段}" in
  setup)
    # 已有专用环境不重新创建，系统Python与主项目环境不变。
    if [ ! -x cmake_venv/bin/python ]; then
      /root/miniconda3/bin/python -m venv cmake_venv
    fi
    timeout 180s cmake_venv/bin/python -m pip install cmake==3.31.6
    cmake_venv/bin/cmake --version
    ;;
  dependencies)
    # 官方同版本归档先下载到临时文件并校验，避免超时覆盖已验证归档。
    mkdir -p dependencies
    timeout 180s curl -fL --max-time 170 \
      https://www.graphics.rwth-aachen.de/media/openmesh_static/Releases/8.1/OpenMesh-8.1.tar.gz \
      -o dependencies/OpenMesh-8.1.tar.gz.partial
    echo "0953777f483d47ea9fa00c329838443a7a09dde8be77bf7de188001cb9e768a7  dependencies/OpenMesh-8.1.tar.gz.partial" | sha256sum -c -
    mv dependencies/OpenMesh-8.1.tar.gz.partial dependencies/OpenMesh-8.1.tar.gz
    sha256sum dependencies/OpenMesh-8.1.tar.gz
    tar -xzf dependencies/OpenMesh-8.1.tar.gz -C dependencies
    ;;
  configure)
    # 仅在隔离归档存在时使用FetchContent标准路径覆盖。
    extra=()
    if [ -f dependencies/OpenMesh-8.1/CMakeLists.txt ]; then
      extra+=("-DFETCHCONTENT_SOURCE_DIR_OPENMESH=$PWD/dependencies/OpenMesh-8.1")
    fi
    # 使用作者固定提交的归档，避免完整Git历史下载；不修改上游源码。
    if [ -f dependencies/glm-0af55ccecd98d4e5a8d1fad7de25ba429d60e863/CMakeLists.txt ]; then
      extra+=("-DFETCHCONTENT_SOURCE_DIR_GLM=$PWD/dependencies/glm-0af55ccecd98d4e5a8d1fad7de25ba429d60e863")
    fi
    timeout 360s cmake_venv/bin/cmake -S source -B build \
      -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=89 \
      -DRX_USE_POLYSCOPE=OFF -DRX_BUILD_TESTS=OFF -DRX_BUILD_APPS=ON \
      -DRX_USE_CUDSS=OFF -DRX_USE_SUITESPARSE=OFF -DRX_USE_DOUBLE=OFF \
      -DFETCHCONTENT_BASE_DIR="$PWD/build/_deps" "${extra[@]}"
    ;;
  build)
    # 无窗口构建缺失GLM平方范数声明；显式预包含原库头文件，不更改作者算法。
    export NVCC_PREPEND_FLAGS="--pre-include=glm/gtx/norm.hpp"
    timeout 480s cmake_venv/bin/cmake --build build --target Remesh -j 4
    ;;
  *) exit 2 ;;
esac
