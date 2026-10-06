"""核对冻结符号反例在原版与变体中的分量、孔洞及网格合法性。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import trimesh

from audit_followup_candidate import vertex_manifold_closed


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "共同运动记录与方法对照"))
from audit_pamo_outputs import as_polydata
from surface_methods import mesh_quality, mesh_topology


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    frozen_path = args.frozen / "01-冻结清单.json"
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    record_path = args.run_dir / "01-符号否定性执行记录.json"
    runs = json.loads(record_path.read_text(encoding="utf-8"))
    expected = {item["id"]: item for item in frozen["negative_inputs"]}
    if len(expected) != 9 or len(runs["rows"]) != 9:
        raise ValueError("符号否定性输入数量不符")
    now = datetime.now(timezone(timedelta(hours=8)))
    report = {"schema_version": 1, "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
              "variant": runs["variant"], "frozen_manifest_sha256": sha256(frozen_path),
              "run_record_sha256": sha256(record_path), "rows": []}
    for run in runs["rows"]:
        case = expected[run["id"]]
        expected_euler = 2 * case["expected_components"] - 2 * case["expected_genus"]
        source = args.frozen / case["mesh"]
        output = args.run_dir / f"{case['id']}.obj"
        row = {"id": case["id"], "status": "audit_failed",
               "expected_components": case["expected_components"],
               "expected_euler_number": expected_euler}
        report["rows"].append(row)
        if (sha256(source) != case["sha256"] or run["input_sha256"] != case["sha256"]):
            row["status"] = "input_invalid"
        elif run["status"] != "completed" or not output.is_file() or sha256(output) != run["output_sha256"]:
            row["status"] = "execution_invalid"
        else:
            input_mesh = trimesh.load(source, force="mesh", process=False)
            mesh = trimesh.load(output, force="mesh", process=False)
            topology = mesh_topology(as_polydata(mesh))
            quality = mesh_quality(as_polydata(mesh))
            manifold = vertex_manifold_closed(np.asarray(mesh.faces))
            topology_expected = bool(
                mesh.is_watertight and mesh.is_winding_consistent and manifold and
                topology["connected_components"] == case["expected_components"] and
                mesh.euler_number == expected_euler and
                topology["boundary_edges"] == 0 and topology["non_manifold_edges"] == 0 and
                topology["inconsistent_interior_edges"] == 0 and
                topology["self_intersection_faces"] == 0)
            row.update({"status": "audited", "output_sha256": sha256(output),
                        "faces": len(mesh.faces), "watertight": bool(mesh.is_watertight),
                        "winding_consistent": bool(mesh.is_winding_consistent),
                        "vertex_manifold_closed": manifold,
                        "observed_components": topology["connected_components"],
                        "observed_euler_number": int(mesh.euler_number),
                        "self_intersection_faces": topology["self_intersection_faces"],
                        "volume_ratio_to_input": float(mesh.volume / input_mesh.volume),
                        "bad_faces": quality["bad_faces"],
                        "expected_topology_passed": topology_expected,
                        "full_geometry_certificate": None})
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        print(case["id"], row["status"], row.get("expected_topology_passed"), flush=True)


if __name__ == "__main__":
    main()
