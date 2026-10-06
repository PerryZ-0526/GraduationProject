"""审计冻结初态和逐前缀工具的几何输入合法性，不修改原文件。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import trimesh

from audit_followup_candidate import vertex_manifold_closed
from preflight_geogram_prefixes import self_intersection_faces


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    manifest_path = args.frozen / "01-冻结清单.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    now = datetime.now(timezone(timedelta(hours=8)))
    report = {"schema_version": 1, "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
              "frozen_manifest_sha256": sha256(manifest_path), "rows": []}
    for route in manifest["routes"]:
        if route["split"] != "development":
            continue
        files = [("initial", route["initial_mesh"], route["initial_mesh_sha256"])]
        files.extend((item["event_id"], item["mesh"], item["sha256"])
                     for item in route["prefix_tools"])
        for event, name, digest in files:
            path = args.frozen / name
            if sha256(path) != digest:
                raise ValueError(f"{route['id']}/{event}: 冻结输入哈希不符")
            mesh = trimesh.load(path, force="mesh", process=False)
            faces = np.asarray(mesh.faces)
            vertices = np.asarray(mesh.vertices)
            rounded = trimesh.Trimesh(vertices=vertices.astype(np.float32).astype(np.float64),
                                      faces=faces, process=False)
            result = {"route": route["id"], "event": event, "path": name,
                      "sha256": digest, "faces": len(faces),
                      "watertight": bool(mesh.is_watertight),
                      "winding_consistent": bool(mesh.is_winding_consistent),
                      "vertex_manifold_closed": vertex_manifold_closed(faces),
                      "zero_area_faces": int(np.count_nonzero(mesh.area_faces <= 1e-12)),
                      "fp32_zero_area_faces": int(np.count_nonzero(rounded.area_faces <= 1e-12)),
                      "self_intersection_faces": self_intersection_faces(mesh),
                      "volume_mm3": float(mesh.volume)}
            report["rows"].append(result)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    for row in report["rows"]:
        if row["self_intersection_faces"] or row["zero_area_faces"] or not row["watertight"]:
            print(row["route"], row["event"], row["self_intersection_faces"],
                  row["zero_area_faces"], row["watertight"])


if __name__ == "__main__":
    main()
