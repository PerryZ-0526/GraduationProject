"""为PaMO符号场归因生成独立的退化面清理输入。"""

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
import trimesh


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prepared_manifest", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(args.prepared_manifest.read_text(encoding="utf-8"))
    result = {
        "time_beijing": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "purpose": "只用于FP32输入退化与SDF符号归因，不替代冻结六例",
        "source_manifest_sha256": file_hash(args.prepared_manifest),
        "cases": [],
    }

    for item in manifest["inputs"]:
        if item["case_id"] not in {"resolution_s3", "resolution_s4"}:
            continue
        source = Path(item["source"])
        if file_hash(source) != item["sha256"]:
            raise ValueError(f"输入摘要不匹配: {item['case_id']}")
        original = trimesh.load(source, force="mesh", process=False)
        rounded = trimesh.Trimesh(
            vertices=np.asarray(original.vertices).astype(np.float32).astype(np.float64),
            faces=np.asarray(original.faces),
            process=False,
        )
        cleaned = trimesh.Trimesh(
            vertices=np.asarray(original.vertices),
            faces=np.asarray(original.faces),
            process=True,
            validate=True,
        )
        target = args.output_dir / f"{item['case_id']}_clean.obj"
        cleaned.export(target)
        exported = trimesh.load(target, force="mesh", process=False)
        nearest = cKDTree(np.asarray(exported.vertices)).query(np.asarray(original.vertices))[0]
        result["cases"].append({
            "case_id": item["case_id"],
            "source_sha256": item["sha256"],
            "clean_sha256": file_hash(target),
            "clean_file": target.name,
            "original_faces": len(original.faces),
            "clean_faces": len(exported.faces),
            "original_vertices": len(original.vertices),
            "clean_vertices": len(exported.vertices),
            "fp32_zero_area_faces_before": int((rounded.area_faces == 0).sum()),
            "fp32_zero_area_faces_after": int((trimesh.Trimesh(
                vertices=np.asarray(exported.vertices).astype(np.float32).astype(np.float64),
                faces=np.asarray(exported.faces), process=False,
            ).area_faces == 0).sum()),
            "clean_watertight": bool(exported.is_watertight),
            "clean_components": len(exported.split(only_watertight=False)),
            "volume_difference_mm3": float(exported.volume - original.volume),
            "max_original_vertex_to_clean_vertex_mm": float(nearest.max()),
        })

    (args.output_dir / "manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(args.output_dir / "manifest.json")


if __name__ == "__main__":
    main()
