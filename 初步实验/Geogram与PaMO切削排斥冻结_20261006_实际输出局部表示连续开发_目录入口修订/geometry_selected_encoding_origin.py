"""按同源实际FP32闭合嵌入检查选择表示原点，不修改物理网格。"""

import numpy as np
import trimesh


def select_encoding_origin(source, original_origin, audit):
    vertices = np.asarray(source.vertices, dtype=np.float64)
    faces = np.asarray(source.faces)
    attempts = []

    def probe(name, origin):
        origin = np.asarray(origin, dtype=np.float64)
        encoded = (vertices - origin).astype(np.float32).astype(np.float64)
        mesh = trimesh.Trimesh(encoded, faces.copy(), process=False)
        result = audit(mesh, len(attempts))
        row = {"name": name, "origin_mm": origin.tolist(), "audit": result,
               "encoding_vertex_correspondence_max_mm": float(
                   np.linalg.norm(encoded + origin - vertices, axis=1).max())}
        attempts.append(row)
        return row

    def accepted(row):
        return row["audit"]["embedding"].get("embedded_closed", False)

    def finish(row):
        return {"status": "selected" if row is not None else "no_embedded_encoding_found",
                "physical_mesh_changed": False, "selection": row, "attempts": attempts,
                "requires_actual_CUDA_working_source_gates": True}

    # 合法的默认表示立即保留，不根据误差大小主动改变已有表示。
    first = probe("original_tool_origin", original_origin)
    if accepted(first):
        return finish(first)
    pairs = np.asarray(first["audit"]["pairs"].get("pair_face_ids_zero_based", []), dtype=int)
    candidates = [("source_vertex_mean", vertices.mean(axis=0)),
                  ("source_bbox_center", np.asarray(source.bounds).mean(axis=0))]
    if pairs.size:
        # 候选位置只由本次精确检查发现的交叠面决定，没有特定输入或面号分支。
        triangles = vertices[faces]
        candidates.append(("all_intersection_faces_center",
                           triangles[np.unique(pairs)].reshape(-1, 3).mean(axis=0)))
        candidates.extend(("intersection_pair_" + str(i), triangles[ids].reshape(-1, 3).mean(axis=0))
                          for i, ids in enumerate(pairs))
    for name, origin in candidates:
        row = probe(name, origin)
        if accepted(row):
            return finish(row)
    return finish(None)
