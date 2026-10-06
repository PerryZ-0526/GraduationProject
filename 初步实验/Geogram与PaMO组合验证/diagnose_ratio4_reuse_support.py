"""精确核对倍率4第二刀拒绝面的所有工具支撑，不按浮点最大值放宽证明。"""

from fractions import Fraction
import json
from pathlib import Path

import numpy as np
import trimesh
from run_constrained_batch import RemoteQuality
from cut_exclusion import supporting_planes, face_separators
from audit_followup_candidate import sha256
from run_geometry_study import save, now


def main():
    root = Path("D:/GraduationProject_切削排斥证据")
    batch = root / "20261005_倍率4薄壁三刀真实父反馈"
    record = batch / "01-统一配置完整父反馈记录.json"
    row = json.loads(record.read_text("utf8"))["rows"][1]
    rid = row["route"]
    path = batch / f"{rid}_e1_candidate_boolean/candidate.obj"
    mesh = trimesh.load(path, force="mesh", process=False)
    prepared = root / "可复用磨削测试集/两档切削排斥新参数七家族_v28"
    route = next(r for r in json.loads((prepared / "01-完整范围冻结清单.json").read_text("utf8"))["routes"] if r["id"] == rid)
    item = next(t for t in route["prefix_tools"] if t["event_id"] == "e1")
    tool_path = prepared / "inputs" / item["mesh"]
    assert sha256(tool_path) == item["sha256"]
    tool = trimesh.load(tool_path, force="mesh", process=False)
    normals, offsets = supporting_planes(tool)
    selections, slacks = face_separators(mesh, tool)
    failures = row["attempt"]["cumulative_tools"][1]["face_support"]["failed_face_ids"]
    rows = []
    for face in failures:
        triangle = [[Fraction(float(x)) for x in point] for point in mesh.triangles[face]]
        exact = [min(sum(Fraction(float(a)) * b for a, b in zip(normal, point)) - Fraction(float(offset)) for point in triangle)
                 for normal, offset in zip(normals, offsets)]
        best = max(range(len(exact)), key=exact.__getitem__)
        rows.append({"face": face, "vertices_mm": mesh.triangles[face].tolist(),
            "original_float_selected_plane": int(selections[face]), "original_float_slack_mm": float(slacks[face]),
            "exact_best_plane": best, "exact_best_slack_fraction": str(exact[best]),
            "exact_best_slack_mm": float(exact[best]), "any_existing_plane_certifies": bool(exact[best] >= 0)})
    output = root / "20261005_倍率4无变化第二刀拒绝面精确支撑诊断"
    output.mkdir(exist_ok=False)
    save(output / "01-无变化拒绝面全支撑有理数核查.json", {"生成时间": now(), "修改时间及修改内容": "首次生成，全部支撑精确枚举",
        "文档概述": "判定是否仅浮点支撑选错，不将现有支撑证明失败等同真实材料相交", "索引目录": ["rows"],
        "saved_sha256": sha256(path), "tool_sha256": sha256(tool_path), "batch_sha256": sha256(record),
        "rows": rows, "new_GPU_calls": 0})
    print(json.dumps(rows, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
