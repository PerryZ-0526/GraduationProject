"""制作仅跳过正常模式无用残差读回的 PaMO 隔离副本。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil


EXPECTED_SHA256 = "e37f579478c0618fa0f3919d2919d6584d62376e909a902ae295acc1af1db7fc"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-package", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    source = args.source_package.resolve()
    target = args.destination.resolve() / "pamo_safe_project"
    source_file = source / "cg_solver.py"
    if sha256(source_file) != EXPECTED_SHA256:
        raise ValueError("作者CG源码哈希变化，停止制作变体")
    if target.exists():
        raise FileExistsError(target)
    shutil.copytree(source, target)
    destination_file = target / "cg_solver.py"
    content = destination_file.read_text(encoding="utf-8")
    original = "            z_r_start = self.z_r.numpy()[0]\n"
    replacement = (
        "            if c.debug:\n"
        "                # 仅调试日志和断言需要初始残差的主机值。\n"
        "                z_r_start = self.z_r.numpy()[0]\n"
    )
    if content.count(original) != 1:
        raise ValueError("作者CG源码锚点变化")
    destination_file.write_text(content.replace(original, replacement), encoding="utf-8")
    record = {
        "source_cg_sha256": EXPECTED_SHA256,
        "variant_cg_sha256": sha256(destination_file),
        "change": "正常模式不读取仅用于调试的初始残差；其余求解操作不变",
    }
    (args.destination / "variant.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    main()
