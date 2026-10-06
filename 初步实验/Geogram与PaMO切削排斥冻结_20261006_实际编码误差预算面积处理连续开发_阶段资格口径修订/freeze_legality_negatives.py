"""补充混合绕序和零面积面的预登记拒绝输入。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import trimesh


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen", type=Path, required=True)
    args = parser.parse_args()
    root = args.frozen.resolve()
    manifest_path = root / "01-冻结清单.json"
    target = root / "04-输入合法性反例.json"
    if target.exists():
        raise ValueError("合法性反例附表已存在，禁止覆盖")
    box = trimesh.creation.box(extents=(2, 2, 1))
    vertices = np.asarray(box.vertices, dtype=np.float64)
    faces = np.asarray(box.faces, dtype=np.int64)
    mixed = faces.copy()
    mixed[0] = mixed[0, ::-1]
    degenerate = np.vstack((faces, [0, 0, 1]))
    rows = []
    for case_id, kind, triangles in (
        ("negative_mixed_winding", "inconsistent_winding", mixed),
        ("negative_zero_area_face", "degenerate_face", degenerate),
    ):
        path = root / f"{case_id}.obj"
        if path.exists():
            raise ValueError(f"{path}: 目标文件已存在")
        trimesh.Trimesh(vertices=vertices, faces=triangles, process=False).export(
            path, file_type="obj", digits=17)
        rows.append({"id": case_id, "kind": kind, "mesh": path.name,
                     "sha256": sha256(path), "expected_policy": "reject_before_PaMO"})
    now = datetime.now(timezone(timedelta(hours=8)))
    addendum = {
        "schema_version": 1,
        "生成时间": now.strftime("%Y年%m月%d日%H时%M分%S秒（北京时间）"),
        "修改时间及修改内容": "首次生成：补齐输入合法性否定性检查；未读取算法输出。",
        "文档概述": "两个新OBJ分别有局部绕序不一致及零面积三角面，预期由入口拒绝。",
        "索引目录": ["原清单哈希", "反例清单"],
        "frozen_manifest_sha256": sha256(manifest_path),
        "cases": rows,
    }
    target.write_text(json.dumps(addendum, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"file": str(target), "sha256": sha256(target),
                      "new_negative_inputs": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
