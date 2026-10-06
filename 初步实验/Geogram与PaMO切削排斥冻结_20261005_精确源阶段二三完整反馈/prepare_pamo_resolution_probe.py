"""从固定PaMO源码生成仅改栅格分辨率的隔离诊断副本。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED_SOURCE_SHA256 = "389865cbfebd13f63bd154497c980368840b5d771576cde49f15fea98df498ca"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replace_once(content: str, old: str, new: str) -> str:
    if content.count(old) != 1:
        raise ValueError(f"固定作者源码锚点不唯一：{old[:48]}")
    return content.replace(old, new)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--resolution", type=int, choices=(256, 512), required=True)
    args = parser.parse_args()
    original = args.source.read_bytes().replace(b"\r\n", b"\n")
    if sha256(original) != EXPECTED_SOURCE_SHA256:
        raise ValueError("PaMO作者源码哈希不符")
    if args.destination.exists():
        raise ValueError("隔离诊断目标已存在，禁止覆盖")
    content = original.decode("utf-8")
    content = replace_once(
        content,
        "        self.R = 256\n        self.band = 3 / self.R # 3",
        f"        # 分辨率诊断：仅固定SDF栅格，不改几何或质量算子。\n        self.R = {args.resolution}\n        self.band = 3 / self.R # 3",
    )
    content = replace_once(
        content,
        "            if self.target_faces <= 1000:\n                self.R = 128\n            if self.target_faces <= 50:\n                self.R = 64",
        "            # 分辨率诊断：暂停按面数降采样，保持初始化时的固定分辨率。\n"
        "            if False and self.target_faces <= 1000:\n                self.R = 128\n"
        "            if False and self.target_faces <= 50:\n                self.R = 64",
    )
    args.destination.parent.mkdir(parents=True, exist_ok=False)
    args.destination.write_text(content, encoding="utf-8", newline="\n")
    record = {"source_sha256_normalized": EXPECTED_SOURCE_SHA256,
              "resolution": args.resolution,
              "destination_sha256": sha256(args.destination.read_bytes()),
              "difference": "仅固定PaMO阶段一SDF分辨率，禁用按目标面数降采样"}
    args.destination.with_suffix(".resolution.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    main()
