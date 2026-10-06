"""新小特征经过同一浅磨CSG后比较，避免把恒等输出冒充保持能力。"""

import argparse
import json
from pathlib import Path

import trimesh

from audit_followup_candidate import sha256
from geometry_preservation_audit import mesh_valid
from locality_masks import save_obj_fp64
from locality_cleanup import clean_provenance
from run_constrained_batch import RemoteQuality, audit_candidate
from run_constrained_feedback import PROVENANCE
from run_geometry_study import execute, retrieve, save, now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    manifest_path = args.prepared / "01-完整范围冻结清单.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    supplementary = {"time_beijing": now(), "parent_manifest_sha256": sha256(manifest_path),
        "rule": "sphere_radius0.04mm_depth0.01mm_at_registered_surface; no_candidate_output_selection", "rows": []}
    # 工具规则只按生成器类型确定表面位置，算法本身不读取案例编号。
    for item in manifest["negative_inputs"]:
        kind = item["id"].removeprefix("new_negative_").rsplit("_", 1)[0]
        width = item["feature_width_mm"]
        center = [0., 0., width / 2 + .03] if kind == "thin_wall" else [
            -.5 if kind == "narrow_gap" else .5 + width / 2, 0., .53]
        tool = trimesh.creation.icosphere(subdivisions=3, radius=.04)
        tool.apply_translation(center)
        path = args.output / (item["id"] + "_tool.obj")
        save_obj_fp64(tool, path)
        supplementary["rows"].append({"id": item["id"], "center_mm": center, "radius_mm": .04,
            "tool": path.name, "sha256": sha256(path)})
    save(args.output / "01-小特征浅磨工具冻结.json", supplementary)
    report = {"time_beijing": now(), "manifest_sha256": sha256(manifest_path), "rows": [], "status": "running"}
    engine = RemoteQuality(args.output, args.port)
    try:
        report["environment"] = engine.setup()
        for item, registered in zip(manifest["negative_inputs"], supplementary["rows"]):
            initial = args.prepared / "inputs" / item["mesh"]
            if sha256(initial) != item["sha256"]:
                raise ValueError("新小特征冻结输入变化")
            tool = args.output / registered["tool"]
            remote = engine.remote + "/" + item["id"]
            execute(engine.client, ["mkdir", remote])
            engine.sftp.put(str(initial), remote + "/initial.obj")
            engine.sftp.put(str(tool), remote + "/tool.obj")
            folder = args.output / (item["id"] + "_input")
            folder.mkdir()
            result = execute(engine.client, [PROVENANCE, remote + "/initial.obj", remote + "/tool.obj",
                remote + "/source.obj", remote + "/labels.json", "--no-simplify"], remote + "/geogram.log", timeout=120)
            retrieve(engine.client, engine.sftp, remote + "/geogram.log", folder / "geogram.log")
            if result["returncode"]:
                report["rows"].append({"case": item["id"], "status": "geogram_failed", "execution": result})
                save(args.output / "02-浅磨特征保持审计.json", report)
                continue
            for name in ("source.obj", "labels.json"):
                retrieve(engine.client, engine.sftp, remote + "/" + name, folder / name)
            source = trimesh.load(folder / "source.obj", force="mesh", process=False)
            # 小特征与反馈路线采用相同的来源同步清理，原始文件不覆盖。
            bits = json.loads((folder / "labels.json").read_text())["operand_bits"]
            try:
                source, bits, cleanup = clean_provenance(source, bits)
            except ValueError as error:
                for method in ("full", "spatial", "boolean"):
                    report["rows"].append({"case": item["id"], "method": method,
                        "status": "source_cleanup_rejected", "error": str(error)})
                save(args.output / "02-浅磨特征保持审计.json", report)
                continue
            source_path, labels_path = folder / "clean_source.obj", folder / "clean_labels.json"
            save_obj_fp64(source, source_path)
            save(labels_path, {"operand_bits": bits.tolist()})
            valid, checks = mesh_valid(source)
            for method in ("full", "spatial", "boolean"):
                destination = args.output / (item["id"] + "_" + method)
                if not valid or checks["fp32_zero_area_faces"]:
                    row = {"method": method, "status": "input_rejected", "input_metrics": checks}
                else:
                    row = engine.run(source_path, labels_path, tool, method, destination)
                    row = audit_candidate(source_path, tool, labels_path, destination, row)
                row.update(case=item["id"], feature_width_mm=item["feature_width_mm"], expected_post_csg_topology=checks,
                           input_is_shallow_cut_closed_solid=True, source_cleanup=cleanup)
                report["rows"].append(row)
                save(args.output / "02-浅磨特征保持审计.json", report)
                print(item["id"], method, row["status"], flush=True)
        report["status"] = "completed_with_recorded_failures"
        save(args.output / "02-浅磨特征保持审计.json", report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
