"""对全部共同来源批次面积拒绝输入做保存副本修复及双表面来源复核。"""
import json
from pathlib import Path
import numpy as np
import trimesh
from fragment_pipeline import repair_input
from exact_alarm_contact import mesh_valid_exact_contacts
from locality_diagnostic import source_region, verify_labels
from locality_masks import save_obj_fp64
from run_geometry_study import now


def main():
    here = Path(__file__).parent
    root = here / "实验结果/20261004_共同来源切空间公开骨面反馈"
    prepared = here.parent / "可复用磨削测试集/公开浅磨批次_v2"
    routes = {r["id"]:r for r in json.loads((prepared / "01-完整范围冻结清单.json").read_text(encoding="utf-8"))["routes"]}
    records = json.loads((root / "01-反馈执行与独立审计.json").read_text(encoding="utf-8"))["rows"]
    parents = {r["output_sha256"]: root / (r["route"]+"_"+r["event"]+"_"+r["branch"]+"_"+r["selected_method"]) / "candidate.obj"
               for r in records if r["status"] == "published_under_sampled_and_vertex_protocol"}
    rows = []
    for row in records:
        if row["status"] != "maintenance_input_invalid":
            continue
        folder = root / (row["route"]+"_"+row["event"]+"_candidate_input")
        source = trimesh.load(folder / "clean_source.obj", process=False)
        bits = json.loads((folder / "clean_labels.json").read_text())["operand_bits"]
        repaired, labels, details = repair_input(source, bits, audit=mesh_valid_exact_contacts, allow_shared=True)
        parent = trimesh.load(parents[row["parent_sha256"]], process=False)
        tool_info = next(t for t in routes[row["route"]]["prefix_tools"] if t["event_id"] == row["event"])
        tool = trimesh.load(prepared / "inputs" / tool_info["mesh"], process=False)
        _, _, seam = source_region(repaired, labels, allow_shared=True)
        check = verify_labels(repaired, labels, parent, tool, seam, allow_shared=True)
        save_obj_fp64(repaired, folder / "shared_repair_diagnostic.obj")
        rows.append(dict(route=row["route"], event=row["event"], repair=details, source_check=check,
                         accepted=details["accepted"] and check["passed_1e_8_mm_numerical_check"]))
        print(row["route"],rows[-1]["accepted"],details["initial_invalid_faces"],details["remaining_invalid_faces"])
    (root / "09-全部共同来源碎片与双表面核对.json").write_text(json.dumps(dict(time_beijing=now(), rows=rows),ensure_ascii=False,indent=2),encoding="utf-8")


if __name__ == "__main__":
    main()
