"""在隔离副本中冻结PaMO安全投影三轮开发对照。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED_NORMALIZED_SHA256 = "389865cbfebd13f63bd154497c980368840b5d771576cde49f15fea98df498ca"


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    if args.destination.exists():
        raise FileExistsError(args.destination)
    original = args.source.read_bytes().replace(b"\r\n", b"\n")
    if sha256(original) != EXPECTED_NORMALIZED_SHA256:
        raise ValueError("原版PaMO源码摘要不符")
    old = "                5,\n                system=self.system,"
    new = "                3,  # 开发对照：安全投影由五轮改为三轮。\n                system=self.system,"
    content = original.decode("utf-8")
    if content.count(old) != 1:
        raise ValueError("迭代参数锚点不唯一")
    args.destination.parent.mkdir(parents=True)
    args.destination.write_text(content.replace(old, new), encoding="utf-8", newline="\n")
    record = {"source_sha256_normalized": EXPECTED_NORMALIZED_SHA256,
              "destination_sha256": sha256(args.destination.read_bytes()),
              "change": "stage3 n_iters=5→3，仅隔离开发对照，不修改作者安装包"}
    args.destination.with_suffix(".variant.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    main()
