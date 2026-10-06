"""仅诊断拒绝面自身法向是否能给出新的精确整面支撑，不移动任何顶点。"""

import json
from pathlib import Path
import numpy as np
import trimesh
from run_constrained_batch import RemoteQuality
from cut_exclusion import dot_intervals, certify_face_support
from audit_followup_candidate import sha256
from run_geometry_study import save, now


def main():
    root = Path("D:/GraduationProject_切削排斥证据")
    batch = root / "20261005_倍率4薄壁三刀真实父反馈"
    path = batch / "薄壁_新参数1p4375_交叉_e1_candidate_boolean/candidate.obj"
    mesh = trimesh.load(path, force="mesh", process=False)
    prepared = root / "可复用磨削测试集/两档切削排斥新参数七家族_v28"
    route = next(r for r in json.loads((prepared / "01-完整范围冻结清单.json").read_text("utf8"))["routes"] if r["id"] == "薄壁_新参数1p4375_交叉")
    item = next(t for t in route["prefix_tools"] if t["event_id"] == "e1")
    tool_path = prepared / "inputs" / item["mesh"]
    assert sha256(tool_path) == item["sha256"]
    tool = trimesh.load(tool_path, force="mesh", process=False)
    face = 2336
    normals = np.asarray([mesh.face_normals[face], -mesh.face_normals[face]])
    _, upper = dot_intervals(tool.vertices, normals)
    offsets = upper.max(axis=0)
    triangle = trimesh.Trimesh(mesh.vertices, [mesh.faces[face]], process=False)
    certificates = [certify_face_support(triangle, normals, offsets, [i]) for i in range(2)]
    output = root / "20261005_倍率4拒绝面自身法向精确分离诊断"
    output.mkdir(exist_ok=False)
    save(output / "01-新增自身法向整面支撑诊断.json", {"生成时间": now(), "修改时间及修改内容": "首次生成，不动顶点诊断新增支撑方向",
        "文档概述": "支撑偏置外舍入包围全部工具顶点；精确逐面三顶点证明，无误差容差",
        "索引目录": ["certificates"], "source_sha256": sha256(path), "tool_sha256": sha256(tool_path), "face": face,
        "normals": normals.tolist(), "offsets": offsets.tolist(), "certificates": certificates,
        "vertices_modified": False, "new_GPU_calls": 0, "published": False})
    print([c["passed"] for c in certificates], flush=True)


if __name__ == "__main__":
    main()
