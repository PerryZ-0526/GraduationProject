"""只读开发碎片重三角化诊断，不修改冻结候选或已发布状态。"""

import argparse
import json
from pathlib import Path

import trimesh

from audit_followup_candidate import sha256
from geometry_preservation_audit import mesh_valid
from locality_masks import save_obj_fp64
from locality_retriangulate import repair_degenerate
from locality_sliver_collapse import collapse_degenerate
from run_constrained_feedback import global_geometry
from run_geometry_study import now, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir()
    record = {"time_beijing": now(), "role": "已见开发阻断输入只读诊断；无新GPU或发布；未修改冻结方法", "rows": []}
    for folder in args.input:
        source_path = folder / "clean_source.obj"
        labels_path = folder / "clean_labels.json"
        source = trimesh.load(source_path, force="mesh", process=False)
        bits = json.loads(labels_path.read_text(encoding="utf-8"))["operand_bits"]
        for name, repair in (("flip", repair_degenerate), ("collapse", collapse_degenerate)):
            candidate, labels, details = repair(source, bits)
            destination = args.output / (folder.name + "_" + name + ".obj")
            save_obj_fp64(candidate, destination)
            reloaded = trimesh.load(destination, force="mesh", process=False)
            valid, checks = mesh_valid(reloaded)
            distance = global_geometry(reloaded, source)
            record["rows"].append({"input": str(folder.resolve()), "source_sha256": sha256(source_path),
                "method": name, "repair_details": details, "output": destination.name,
                "output_sha256": sha256(destination), "topology_and_finiteness_valid": valid,
                "checks": checks, "distance_to_input": distance, "source_bits": labels.tolist(),
                "published": False})
            save(args.output / "01-已见开发碎片修复只读诊断.json", record)
            print(folder.name, name, "remaining", details["remaining_invalid_faces"], "valid", valid,
                  "probe_mm", distance["probe_max_mm"], flush=True)
    record["status"] = "completed_read_only"
    save(args.output / "01-已见开发碎片修复只读诊断.json", record)


if __name__ == "__main__":
    main()
