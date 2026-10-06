"""原工具面方向不足时补充骨三角面法向，仅扩充证明方向，不移动网格。"""

from fractions import Fraction
import numpy as np
import trimesh
from cut_exclusion import supporting_planes, face_separators, certify_face_support, dot_intervals


def certify_tool_containment(tool, normal, offset):
    normal = np.asarray(normal, np.float64)
    if normal.shape != (3,) or not np.isfinite(normal).all() or not np.any(normal) or not np.isfinite(offset):
        return False
    exact_normal = [Fraction(float(x)) for x in normal]
    exact_offset = Fraction(float(offset))
    return all(sum(a * Fraction(float(b)) for a, b in zip(exact_normal, point)) <= exact_offset
               for point in tool.vertices)


def complete_face_support(mesh, tool):
    normals, offsets = supporting_planes(tool)
    selected, _ = face_separators(mesh, tool)
    certificate = certify_face_support(mesh, normals, offsets, selected)
    initial_failures = certificate["failed_face_count"]
    additions, tested = [], set()
    while not certificate["passed"]:
        pending = [i for i in certificate["failed_face_ids"] if i not in tested]
        if not pending:
            break
        for face in pending:
            tested.add(face)
            triangle = trimesh.Trimesh(mesh.vertices, [mesh.faces[face]], process=False)
            # 两个方向分别尝试；偏置外舍入包围整个凸工具，不用骨面位置代替工具支撑。
            for normal in (mesh.face_normals[face], -mesh.face_normals[face]):
                _, upper = dot_intervals(tool.vertices, np.asarray([normal]))
                offset = float(upper.max())
                containment = certify_tool_containment(tool, normal, offset)
                support = certify_face_support(triangle, np.asarray([normal]), np.asarray([offset]), [0])
                if containment and support["passed"]:
                    selected[face] = len(normals)
                    normals = np.vstack([normals, normal])
                    offsets = np.append(offsets, offset)
                    additions.append({"face": face, "plane_id": int(selected[face]),
                        "normal": normal.tolist(), "offset_mm": offset,
                        "tool_containment_exact": True, "face_support_exact": support})
                    break
        certificate = certify_face_support(mesh, normals, offsets, selected)
    return normals, offsets, selected, certificate, {"initial_failed_faces": initial_failures,
        "tested_faces": len(tested), "added_planes": additions, "vertices_modified": False,
        "scope": "原方向及拒绝面自身正负法向的充分证明；失败不等同实际材料相交"}
