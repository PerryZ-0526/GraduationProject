"""在隔离目录编译固定掩码扩展，不安装或覆盖作者PaMO包。"""

import argparse
import os
from pathlib import Path
from torch.utils.cpp_extension import load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    directory = args.directory.resolve()
    build = directory / "build"
    build.mkdir(exist_ok=True)
    os.environ["TORCH_CUDA_ARCH_LIST"] = "8.9"
    os.environ["MAX_JOBS"] = "3"
    extension = load(name="pamo_order_sorted", sources=[str(directory / "src" / f) for f in
                     ("pybind.cpp", "cusimp.cu", "cusimp_free.cu")],
                     build_directory=str(build), extra_cflags=["-O3"],
                     extra_cuda_cflags=["-O3", "--extended-lambda", "--fmad=false"], verbose=True)
    print(extension.__file__, flush=True)


if __name__ == "__main__":
    main()
