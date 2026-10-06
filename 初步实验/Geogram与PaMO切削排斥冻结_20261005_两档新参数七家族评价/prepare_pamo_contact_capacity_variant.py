"""制作只缩小 PaMO 接触容量上限的隔离性能变体。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil


EXPECTED_CONFIG_SHA256 = "df1eb24db57394c32e31f6d67a58cd7ef6c25febc11aff39c5e9503ee82d6390"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-package", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--max-blocks-power", type=int, required=True)
    args = parser.parse_args()
    if not 16 <= args.max_blocks_power < 25:
        raise ValueError("开发容量指数限于16到24")
    source = args.source_package.resolve()
    destination = args.destination.resolve()
    target = destination / "pamo_safe_project"
    if target.exists():
        raise FileExistsError(target)
    source_file = source / "config.py"
    if sha256(source_file) != EXPECTED_CONFIG_SHA256:
        raise ValueError("作者配置源码哈希变化，停止制作变体")
    shutil.copytree(source, target)
    destination_file = target / "config.py"
    content = destination_file.read_text(encoding="utf-8")
    old = "        self.max_blocks = 1 << 25\n"
    new = (f"        # 仅调整接触缓冲区容量；接触超限仍走作者原有重试分支。\n"
           f"        self.max_blocks = 1 << {args.max_blocks_power}\n")
    if content.count(old) != 1:
        raise ValueError("作者接触容量锚点变化")
    destination_file.write_text(content.replace(old, new), encoding="utf-8")
    record = {"source_config_sha256": EXPECTED_CONFIG_SHA256,
              "variant_config_sha256": sha256(destination_file),
              "max_blocks": 1 << args.max_blocks_power,
              "change": "仅缩小接触缓冲区容量，计算路径和超限重试保留"}
    (destination / "variant.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    main()
