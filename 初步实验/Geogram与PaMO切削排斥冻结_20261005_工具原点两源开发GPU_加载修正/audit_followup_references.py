"""审计冻结路线逐前缀离散参照的文件与闭合拓扑。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pyvista as pv
import trimesh


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--references", type=Path, required=True)
    parser.add_argument("--split", choices=("development", "evaluation"), default="development")
    args = parser.parse_args()
    frozen, references = args.frozen.resolve(), args.references.resolve()
    target = references / "01-参照审计.json"
    if target.exists():
        raise ValueError("参照审计已存在，禁止覆盖")
    manifest_path = frozen / "01-冻结清单.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    aliases = {"shallow": "shallow", "repeat": "repeat", "plan_edge": "plan_edge",
               "vertical": "vertical_sphere", "crossing": "crossing",
               "stop_resume": "stop_resume"}
    rows = []
    for route in manifest["routes"]:
        if route["split"] != args.split:
            continue
        for event_id in route["cutting_prefix_ids"]:
            name = (f"{aliases[route['category']]}_{event_id}" if args.split == "development"
                    else f"{route['id']}_{event_id}")
            path, record_path = references / f"{name}.vtp", references / f"{name}.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            if record["route"] != route["id"] or record["event"] != event_id or record["reference_sha256"] != sha256(path):
                raise ValueError(f"{name}: 参照文件哈希或路线不匹配")
            surface = pv.read(path)
            faces = np.asarray(surface.faces).reshape(-1, 4)[:, 1:]
            mesh = trimesh.Trimesh(vertices=np.asarray(surface.points), faces=faces, process=False)
            components = len(mesh.split(only_watertight=False))
            if not mesh.is_watertight or not mesh.is_winding_consistent or components != 1 or mesh.euler_number != 2:
                raise ValueError(f"{name}: 离散参照拓扑不符合预期")
            rows.append({"route": route["id"], "event": event_id, "mesh": path.name,
                         "sha256": record["reference_sha256"], "faces": len(faces),
                         "max_analytic_field_residual_mm": record["max_analytic_field_residual_mm"]})
    now = datetime.now(timezone(timedelta(hours=8)))
    result = {"schema_version": 1,
              "生成时间": now.strftime("%Y年%m月%d日%H时%M分%S秒（北京时间）"),
              "修改时间及修改内容": f"首次生成：审计{args.split}路线全部切削前缀的离散参照。",
              "文档概述": "文件哈希与单分量水密拓扑核查；不提供连续距离界。",
              "索引目录": ["冻结清单哈希", "逐前缀参照"],
              "frozen_manifest_sha256": sha256(manifest_path),
              "split": args.split, "reference_count": len(rows),
              "reference_discretization_error_status": "unknown",
              "rows": rows}
    expected = 24 if args.split == "development" else 48
    if len(rows) != expected:
        raise ValueError(f"{args.split}参照数应为{expected}，实际{len(rows)}")
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"references": len(rows), "max_field_residual_mm":
                      max(item["max_analytic_field_residual_mm"] for item in rows),
                      "audit_sha256": sha256(target)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
