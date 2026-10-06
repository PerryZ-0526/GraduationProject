"""逐前缀审计Geogram原始输出与独立清理副本，保留拒绝依据。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pymeshlab as pm
from scipy.spatial import cKDTree
import trimesh

from audit_followup_candidate import vertex_manifold_closed


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def self_intersection_faces(mesh: trimesh.Trimesh) -> int:
    mesh_set = pm.MeshSet()
    mesh_set.add_mesh(pm.Mesh(np.asarray(mesh.vertices), np.asarray(mesh.faces)))
    mesh_set.compute_selection_by_self_intersections_per_face()
    return int(mesh_set.current_mesh().selected_face_number())


def metrics(mesh: trimesh.Trimesh) -> dict:
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    rounded = trimesh.Trimesh(vertices=vertices.astype(np.float32).astype(np.float64),
                              faces=faces, process=False)
    return {
        "vertices": len(vertices),
        "faces": len(faces),
        "finite": bool(np.isfinite(vertices).all()),
        "zero_area_faces": int(np.count_nonzero(mesh.area_faces <= 1e-12)),
        "fp32_zero_area_faces": int(np.count_nonzero(rounded.area_faces <= 1e-12)),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "vertex_manifold_closed": vertex_manifold_closed(faces),
        "euler_number": int(mesh.euler_number),
        "self_intersection_faces": self_intersection_faces(mesh),
        "volume_mm3": float(mesh.volume),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prefix", nargs=2, action="append", metavar=("EVENT", "OBJ"), required=True)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError("输出目录已有文件，禁止覆盖")
    args.output.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone(timedelta(hours=8)))
    result = {"schema_version": 1, "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
              "cleanup": "Trimesh process=True, validate=True; diagnostic copy only",
              "rows": []}
    for event, path_text in args.prefix:
        path = Path(path_text)
        raw = trimesh.load(path, force="mesh", process=False)
        clean = trimesh.Trimesh(vertices=np.asarray(raw.vertices), faces=np.asarray(raw.faces),
                                process=True, validate=True)
        cleaned_path = args.output / f"{event}_clean.obj"
        clean.export(cleaned_path)
        reloaded = trimesh.load(cleaned_path, force="mesh", process=False)
        raw_metrics, clean_metrics = metrics(raw), metrics(reloaded)
        valid = all((clean_metrics["finite"], clean_metrics["zero_area_faces"] == 0,
                     clean_metrics["fp32_zero_area_faces"] == 0, clean_metrics["watertight"],
                     clean_metrics["winding_consistent"], clean_metrics["vertex_manifold_closed"],
                     clean_metrics["euler_number"] == 2,
                     clean_metrics["self_intersection_faces"] == 0))
        result["rows"].append({
            "event": event,
            "raw_path": str(path), "raw_sha256": sha256(path), "raw": raw_metrics,
            "clean_path": str(cleaned_path), "clean_sha256": sha256(cleaned_path),
            "clean": clean_metrics,
            "max_raw_vertex_to_clean_vertex_mm": float(cKDTree(reloaded.vertices).query(raw.vertices)[0].max()),
            "volume_delta_mm3": float(reloaded.volume - raw.volume),
            "valid_pamo_input_under_listed_checks": bool(valid),
        })
    report = args.output / "01-逐前缀输入审计.json"
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for row in result["rows"]:
        print(row["event"], row["valid_pamo_input_under_listed_checks"],
              row["clean"]["self_intersection_faces"])


if __name__ == "__main__":
    main()
