"""静态检查原始第三刀的少数拒绝面能否用三角边与工具边叉积方向分离。"""

import json
from pathlib import Path
import sys


def main():
    project = Path.cwd()
    sys.path.insert(0, str(project / "初步实验/Geogram与PaMO切削排斥冻结_20261005_补充面法向倍率4薄壁反馈"))
    import numpy as np
    import trimesh
    from run_constrained_batch import RemoteQuality
    from run_geometry_study import save, now
    from audit_followup_candidate import sha256
    from cut_exclusion import dot_intervals, certify_face_support
    from face_normal_support_completion import certify_tool_containment
    root = Path("D:/GraduationProject_切削排斥证据")
    input_record = root / "20261005_补充支撑薄壁第三刀原始GPU整面静态核查/01-原始第三刀不投影累计整面认证核查.json"
    previous = json.loads(input_record.read_text("utf8"))
    path = root / "20261005_补充面法向倍率4薄壁三刀真实反馈/薄壁_新参数1p4375_交叉_e2_candidate_boolean/raw_full_candidate.obj"
    assert sha256(path) == previous["raw_sha256"]
    mesh = trimesh.load(path, force="mesh", process=False)
    prepared = root / "可复用磨削测试集/两档切削排斥新参数七家族_v28"
    route = next(r for r in json.loads((prepared / "01-完整范围冻结清单.json").read_text("utf8"))["routes"] if r["id"].startswith("薄壁_"))
    rows = []
    for old in previous["rows"]:
        item = next(t for t in route["prefix_tools"] if t["event_id"] == old["event"])
        tp = prepared / "inputs" / item["mesh"]
        assert sha256(tp) == old["tool_sha256"]
        tool = trimesh.load(tp, force="mesh", process=False)
        tool_edges = tool.vertices[tool.edges_unique[:, 1]] - tool.vertices[tool.edges_unique[:, 0]]
        for face in old["support"]["failed_face_ids"]:
            points = mesh.triangles[face]
            edges = np.roll(points, -1, axis=0) - points
            axes = np.cross(edges[:, None, :], tool_edges[None, :, :]).reshape(-1, 3)
            length = np.linalg.norm(axes, axis=1)
            axes = axes[np.isfinite(length) & (length > 0)] / length[np.isfinite(length) & (length > 0), None]
            axes = np.unique(np.vstack([axes, -axes]), axis=0)
            best = None
            for start in range(0, len(axes), 256):
                normals = axes[start:start + 256]
                _, upper = dot_intervals(tool.vertices, normals)
                offsets = upper.max(axis=0)
                lower, _ = dot_intervals(points, normals)
                gaps = lower.min(axis=0) - offsets
                index = int(np.argmax(gaps))
                if best is None or gaps[index] > best[0]:
                    best = (float(gaps[index]), normals[index].copy(), float(offsets[index]))
            triangle = trimesh.Trimesh(mesh.vertices, [mesh.faces[face]], process=False)
            certificate = certify_face_support(triangle, np.asarray([best[1]]), np.asarray([best[2]]), [0])
            containment = certify_tool_containment(tool, best[1], best[2])
            rows.append({"event": old["event"], "face": face, "candidate_axes": len(axes),
                "conservative_best_gap_mm": best[0], "normal": best[1].tolist(), "offset_mm": best[2],
                "face_support": certificate, "tool_containment_exact": containment})
    output = root / "20261005_薄壁原始第三刀边叉积分离轴静态诊断"
    output.mkdir(exist_ok=False)
    save(output / "01-原始第三刀六拒绝面边轴精确分离诊断.json", {"生成时间": now(), "修改时间及修改内容": "首次生成，原始输出只读增加边轴诊断",
        "文档概述": "偏置外舍入及工具包含、整面三顶点精确复核；失败不构成真实相交证书",
        "索引目录": ["rows"], "raw_sha256": sha256(path), "input_record_sha256": sha256(input_record), "rows": rows,
        "new_GPU_calls": 0, "new_publications": 0, "vertices_modified": False})
    print([(r["event"], r["face"], r["conservative_best_gap_mm"], r["face_support"]["passed"]) for r in rows], flush=True)


if __name__ == "__main__":
    main()
