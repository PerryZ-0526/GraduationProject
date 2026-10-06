"""在隔离副本中仅扩大近边射线相交的 FP32 重心坐标容差。"""

import argparse
import hashlib
from pathlib import Path
import shutil


SOURCE_SHA256 = "61553a5740ce71e4458ae39678d99a5a6cd586421884795011b83bc7e3af07b1"
OLD = "u >= -FLT_EPSILON && v >= -FLT_EPSILON && u + v <= 1 + FLT_EPSILON"
NEW = ("u >= -4.0f * FLT_EPSILON && v >= -4.0f * FLT_EPSILON "
       "&& u + v <= 1 + 4.0f * FLT_EPSILON")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    original = args.source / "geometry.cuh"
    if hashlib.sha256(original.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("源文件摘要与固定版本不一致")
    shutil.copytree(args.source, args.destination,
                    ignore=shutil.ignore_patterns(".git", "build", "*.egg-info", "*.so"))
    target = args.destination / "geometry.cuh"
    content = target.read_text(encoding="utf-8")
    if content.count(OLD) != 1:
        raise ValueError("射线边界容差替换点不唯一")
    # 仅修改一条命中判据；原有距离场、填充与 PaMO 三阶段保持固定。
    target.write_text(content.replace(OLD, NEW), encoding="utf-8")
    print(hashlib.sha256(target.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
