"""生成新参数弯曲体的表面锚定路线，保留逐工具材料内部接触见证。"""
import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import numpy as np
import trimesh
from build_cases import make_body, digest
from prepare_feedback import make_route, save_obj_fp64


def contact_witness(mesh, tool):
    """先找严格位于离散凸工具内部的点，再独立查询其骨实体成员关系。"""
    points = mesh.triangles_center - .001*mesh.face_normals
    normals = tool.face_normals
    offsets = np.einsum("ij,ij->i", tool.triangles_center, normals)
    maximum = np.max(points @ normals.T-offsets, axis=1)
    candidates = np.flatnonzero(maximum < -1e-6)
    for index in candidates[np.argsort(maximum[candidates])]:
        if bool(mesh.contains([points[index]])[0]):
            return {"status": "interior_witness_found", "point_mm": points[index].tolist(),
                    "source_face": int(index), "tool_halfspace_maximum_mm": float(maximum[index]),
                    "bone_membership_check": "trimesh_ray_contains", "certified_volume": False}
    return {"status": "no_verified_interior_witness", "strict_tool_candidates": len(candidates)}


def build(output, parameters=(2.4, 3.4, 3.9)):
    if len(set(parameters)) != len(parameters) or not parameters or not all(0 <= value <= 4 for value in parameters):
        raise ValueError("参数必须唯一且位于原家族0至4范围")
    output.mkdir(parents=True, exist_ok=False)
    inputs = output / "inputs"
    inputs.mkdir()
    report = {"time_beijing": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "routes": [],
              "negative_inputs": [], "units": {"length": "mm", "time": "ms"},
              "source_hashes": {name: digest(Path(__file__).with_name(name)) for name in
                                ("build_curved_contact_cases.py", "build_cases.py", "prepare_feedback.py")},
              "scope": "同家族新插值参数；不是新患者，接触见证不等于实际去除体积"}
    for value in parameters:
        mesh = make_body("弯曲骨样体", value)
        body_id = "弯曲骨样体_接触参数" + format(value, ".6g").replace(".", "p")
        initial = inputs / (body_id+".obj")
        save_obj_fp64(mesh, initial)
        face = int(np.argmax(mesh.triangles_center[:, 2]))
        anchor, normal = mesh.triangles_center[face], mesh.face_normals[face]
        radius = .6
        axis = np.eye(3)[int(np.argmin(np.abs(normal)))]
        tangent = np.cross(normal, axis)
        tangent /= np.linalg.norm(tangent)
        second = np.cross(normal, tangent)
        center = anchor + .35*radius*normal
        points = [center+1.5*radius*(x*tangent+y*second) for x, y in ((-1, -1), (1, 1), (-1, 1), (1, -1))]
        body = {"id": body_id}
        motion = {"tool_radius_mm": radius, "events": [{"position_mm": point.tolist()} for point in points]}
        route = make_route(body, "交叉", motion, initial, inputs, "evaluation", "synthetic_surface_anchored_curved")
        route["parameter"] = value
        route["initial_surface_anchor"] = {"face": face, "point_mm": anchor.tolist(), "normal": normal.tolist()}
        route["contact_witnesses"] = []
        for tool in route["prefix_tools"]:
            tool_mesh = trimesh.load(inputs / tool["mesh"], process=False)
            route["contact_witnesses"].append({"event": tool["event_id"], **contact_witness(mesh, tool_mesh)})
        report["routes"].append(route)
    (output / "01-完整范围冻结清单.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build(args.output)
    print([(route["id"], [item["status"] for item in route["contact_witnesses"]]) for route in report["routes"]])
