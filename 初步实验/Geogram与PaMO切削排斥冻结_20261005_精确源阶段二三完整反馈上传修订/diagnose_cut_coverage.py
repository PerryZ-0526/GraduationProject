"""保留整面排斥合法但目标几何失败的实际中间对象，分解双向覆盖误差。"""

import argparse
import json
from pathlib import Path
import shutil

import numpy as np
import trimesh

from audit_followup_candidate import sha256
from audit_pamo_outputs import as_polydata
from geometry_preservation_audit import MeshDistance
from run_geometry_study import save, now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--asset", type=Path, required=True)
    args = parser.parse_args()
    # 之前解析诊断失败时只有空目录；不能覆盖已有诊断或冻结资产。
    for folder in (args.output, args.asset):
        folder.mkdir(exist_ok=True)
        if any(folder.iterdir()):
            raise ValueError("诊断输出或资产目录已有内容")
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，两个真实几何失败的最优合法中间层",
              "文档概述": "排斥及完整嵌入合法不代表目标表面覆盖；所有输入均为已见开发",
              "索引目录": ["rows"], "status": "running", "rows": []}
    for key in ("FJ3368", "FJ3262"):
        rid = "BP3D_" + key + "_交叉浅磨"
        batch = args.batch / rid
        record = batch / "01-统一配置完整父反馈记录.json"
        data = json.loads(record.read_text("utf8"))
        details = data["rows"][0]["attempt"]["cut_exclusion"]
        best = min((x for x in details["attempts"] if x["mesh_valid"] and x["exclusion"]["accepted"]),
                   key=lambda x: x["geometry"]["probe_max_mm"])
        anchors = best["exclusion"]["outside_anchor_certificate"]
        anchor = anchors if isinstance(anchors, dict) else anchors[0]
        certificate = anchor["classification"]
        candidate = next(p for p in batch.glob("side_*.obj") if sha256(p) == certificate["saved_mesh_sha256"])
        reference = batch / (rid + "_e0_reference") / "validated_reference.obj"
        if not reference.exists():
            reference = reference.with_name("reference.obj")
        case = args.asset / key
        case.mkdir()
        paths = [(candidate, "排斥合法但几何失败候选.obj"), (reference, "独立累计参照.obj"),
                 (args.prepared / "inputs" / (rid + "_e0_tool.obj"), "首刀工具.obj"),
                 (batch / (rid + "_e0_candidate_input/clean_source.obj"), "合法布尔源.obj"),
                 (batch / (rid + "_e0_candidate_boolean/raw_full_candidate.obj"), "实际GPU原对象.obj")]
        for path, name in paths:
            shutil.copyfile(path, case / name)
        mesh = trimesh.load(candidate, force="mesh", process=False)
        target = trimesh.load(reference, force="mesh", process=True, validate=True)
        forward = MeshDistance(as_polydata(target))(mesh.vertices)
        reverse = MeshDistance(as_polydata(mesh))(target.vertices)
        fi, ri = int(np.argmax(forward)), int(np.argmax(reverse))
        entry = {"case": key, "selected_legal_level": best["level"], "faces": len(mesh.faces),
                 "files": {name: sha256(case / name) for _, name in paths}, "embedding_certificate": certificate,
                 "frozen_face_support_ids": best["exclusion"]["frozen_face_support_ids"],
                 "outside_anchor_certificate": anchors, "recorded_geometry": best["geometry"],
                 "forward_all_vertex_max_mm": float(forward[fi]), "reverse_all_vertex_max_mm": float(reverse[ri]),
                 "forward_witness_mm": mesh.vertices[fi].tolist(), "reverse_witness_mm": target.vertices[ri].tolist(),
                 "forward_over_0_1_count": int((forward > .1).sum()), "reverse_over_0_1_count": int((reverse > .1).sum()),
                 "source_record_sha256": sha256(record)}
        report["rows"].append(entry)
        save(args.output / "01-两几何负例双向覆盖诊断.json", report)
        print(key, "forward", entry["forward_all_vertex_max_mm"], "reverse", entry["reverse_all_vertex_max_mm"], flush=True)
    report.update(status="completed", finished_beijing=now())
    save(args.output / "01-两几何负例双向覆盖诊断.json", report)
    save(args.asset / "01-排斥合法与覆盖失败真实负例清单.json", report)


if __name__ == "__main__":
    main()
