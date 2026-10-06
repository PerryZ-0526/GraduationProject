"""生成35号计划的预登记输入；不读取任何候选算法输出。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
import trimesh


HERE = Path(__file__).resolve().parent
COMMON = HERE.parent / "共同运动记录与方法对照"
sys.path.insert(0, str(COMMON))
from motion_record import replay_case

SEED = 20260922
KINDS = ("shallow", "repeat", "plan_edge", "vertical", "crossing", "stop_resume")
OFFSETS = {
    "shallow": ((-0.75, 0), (-0.3, 0), (0.2, 0), (0.7, 0)),
    "repeat": ((-0.65, -0.2), (0.15, -0.2), (0.15, -0.2), (0.65, -0.2)),
    "plan_edge": ((0.5, 0.1), (0.85, 0.1), (1.15, 0.1), (1.5, 0.1)),
    "vertical": ((0.1, 0.1), (0.1, 0.1), (0.1, 0.1), (0.1, 0.1)),
    "crossing": ((-0.7, -0.6), (0.6, 0.6), (-0.6, 0.6), (0.7, -0.6)),
    "stop_resume": ((-0.7, 0), (-0.25, 0), (0, 0), (0.3, 0.1), (0.4, 0.1), (0.7, 0.1)),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slab_mesh(slope: tuple[float, float], spacing: float = 0.2) -> trimesh.Trimesh:
    """复用既有闭合板体的顶底面与侧壁拓扑。"""
    import importlib.util

    source = HERE.parent / "共同运动记录与方法对照" / "geogram_baseline.py"
    sys.path.insert(0, str(source.parent))
    spec = importlib.util.spec_from_file_location("geogram_baseline_followup", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    case = {"initial_surface": {"kind": "plane", "height_coefficients": [*slope, 0.0]}}
    return module._slab_mesh(case, (-2.0, 2.0, -2.0, 2.0), -1.2, spacing)


def sphere_mesh() -> trimesh.Trimesh:
    return trimesh.creation.icosphere(subdivisions=4, radius=2.5)


def capsule_mesh(primitive: dict) -> trimesh.Trimesh:
    """按既有Geogram适配的球面分辨率离散扫掠工具。"""
    sphere = trimesh.creation.icosphere(subdivisions=3, radius=0.7)
    start, end = np.asarray(primitive["start"]), np.asarray(primitive["end"])
    if np.linalg.norm(start - end) <= 1e-14:
        sphere.apply_translation(start)
        return sphere
    points = np.vstack((sphere.vertices + start, sphere.vertices + end))
    return trimesh.convex.convex_hull(points)


def surface_z(body: str, x: float, y: float, slope: tuple[float, float]) -> float:
    if body == "slab":
        return slope[0] * x + slope[1] * y
    return math.sqrt(2.5**2 - x * x - y * y)


def route(split: str, kind: str, body: str, index: int, root: Path) -> dict:
    # 各路线使用独立随机流；生成后所有实际坐标进入清单。
    stream = f"{SEED}/{split}/{kind}/{body}/{index}"
    rng = random.Random(int.from_bytes(hashlib.sha256(stream.encode()).digest()[:8], "big"))
    shift_x, shift_y = rng.uniform(-0.09, 0.09), rng.uniform(-0.09, 0.09)
    slope = (round(rng.uniform(0.06, 0.16), 6), round(rng.uniform(-0.12, -0.04), 6))
    depth_shift = rng.uniform(-0.025, 0.025)
    case_id = f"{split}_{kind}_{body}_{index:02d}"
    mesh = slab_mesh(slope) if body == "slab" else sphere_mesh()
    if not mesh.is_watertight or not mesh.is_winding_consistent:
        raise ValueError(f"{case_id}: 初始输入不闭合或绕序不一致")
    mesh_path = root / f"{case_id}_initial.obj"
    mesh.export(mesh_path, file_type="obj", digits=17)
    events = []
    for n, (base_x, base_y) in enumerate(OFFSETS[kind]):
        x, y = round(base_x + shift_x, 6), round(base_y + shift_y, 6)
        depth = (0.12, 0.2, 0.3, 0.18)[n] if kind == "vertical" else 0.16
        z = round(surface_z(body, x, y, slope) + 0.7 - depth - depth_shift, 6)
        cutting = not (kind == "stop_resume" and n in (2, 4))
        connected = n > 0 and cutting and kind not in ("vertical", "crossing", "stop_resume")
        if kind == "crossing":
            connected = n in (1, 3)
        if kind == "stop_resume":
            connected = n in (1, 5)
        # 第五个事件晚到，按公共回放规则拒绝；缺失段只记账，不插值。
        timestamp = (0, 100, 200, 400, 350, 500)[n] if kind == "stop_resume" else n * 100
        events.append({
            "id": f"e{n}", "arrival_index": n, "timestamp_ms": timestamp,
            "position_mm": [x, y, z], "orientation_xyzw": [0.0, 0.0, 0.0, 1.0],
            "cutting": cutting, "connect_from_previous": connected,
        })
    cutting_prefixes = []
    tools = []
    policy = {"late_event": "reject", "max_link_gap_ms": 200, "interpolate_missing_motion": False}
    case_for_replay = {"id": case_id, "tool": {"radius_mm": 0.7}, "events": events}
    for event in events:
        replay = replay_case(case_for_replay, policy, through_event_id=event["id"])
        if not event["cutting"] or event["id"] in replay["late_event_ids"]:
            continue
        primitive = replay["primitives"][-1]
        tool_mesh = capsule_mesh(primitive)
        if not tool_mesh.is_watertight or not tool_mesh.is_winding_consistent:
            raise ValueError(f"{case_id}/{event['id']}: 工具网格无效")
        tool_path = root / f"{case_id}_{event['id']}_tool.obj"
        tool_mesh.export(tool_path, file_type="obj", digits=17)
        cutting_prefixes.append(event["id"])
        tools.append({"event_id": event["id"], "mesh": tool_path.name,
                      "sha256": digest(tool_path), "faces": int(len(tool_mesh.faces))})
    return {
        "id": case_id, "split": split, "category": kind, "body": body,
        "random_stream": stream, "initial_mesh": mesh_path.name,
        "initial_mesh_sha256": digest(mesh_path), "initial_faces": int(len(mesh.faces)),
        "analytic_body": {"kind": body, "slope_xy": list(slope) if body == "slab" else None,
                          "bounds_xy_mm": [-2, 2, -2, 2] if body == "slab" else None,
                          "bottom_z_mm": -1.2 if body == "slab" else None,
                          "radius_mm": 2.5 if body == "sphere" else None},
        "tool": {"kind": "sphere", "radius_mm": 0.7, "mesh_subdivisions": 3},
        "plan": {"center_xy_mm": [0, 0], "allowed_radius_mm": 1.2, "target_depth_mm": 0.25},
        "events": events, "cutting_prefix_ids": cutting_prefixes, "prefix_tools": tools,
        "expected_initial_topology": {"components": 1, "watertight": True, "cavities": 0},
        "expected_event_rejections": ["e4"] if kind == "stop_resume" else [],
        "missing_interval_ms": [200, 400] if kind == "stop_resume" else None,
        "reference": {"kind": "analytic_set_difference", "source": "analytic_body+exact_sphere_capsules",
                      "surface_mesh_reference_error_mm": None},
    }


def torus_mesh(major: float, minor: float) -> trimesh.Trimesh:
    """构造贯通孔的闭合解析参数曲面离散输入。"""
    nu, nv = 96, 24
    vertices = []
    faces = []
    for i in range(nu):
        u = 2 * math.pi * i / nu
        for j in range(nv):
            v = 2 * math.pi * j / nv
            vertices.append([(major + minor * math.cos(v)) * math.cos(u),
                             (major + minor * math.cos(v)) * math.sin(u), minor * math.sin(v)])
            a, b = i * nv + j, ((i + 1) % nu) * nv + j
            c, d = i * nv + (j + 1) % nv, ((i + 1) % nu) * nv + (j + 1) % nv
            faces.extend(((a, b, d), (a, d, c)))
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.invert() if mesh.volume < 0 else None
    return mesh


def negative_inputs(root: Path) -> list[dict]:
    cases = []
    for ratio in (0.5, 1.0, 2.0):
        width = round(0.02 * ratio, 6)
        for kind in ("thin_wall", "narrow_gap", "through_hole"):
            if kind == "thin_wall":
                mesh = trimesh.creation.box(extents=(2, 2, width))
                components, genus = 1, 0
            elif kind == "narrow_gap":
                left = trimesh.creation.box(extents=(1, 2, 1))
                right = left.copy()
                left.apply_translation((-(1 + width) / 2, 0, 0))
                right.apply_translation(((1 + width) / 2, 0, 0))
                mesh = trimesh.util.concatenate((left, right))
                components, genus = 2, 0
            else:
                # 中心孔径固定为width；小孔可能低于离散采样能力，预期应显式拒绝。
                mesh = torus_mesh(0.5 + width / 2, 0.5)
                components, genus = 1, 1
            case_id = f"negative_{kind}_{ratio:g}voxel"
            path = root / f"{case_id}.obj"
            mesh.export(path, file_type="obj", digits=17)
            cases.append({"id": case_id, "kind": kind, "nominal_voxel_mm": 0.02,
                          "feature_width_mm": width, "feature_to_nominal_voxel": ratio,
                          "mesh": path.name, "sha256": digest(path),
                          "expected_components": components, "expected_genus": genus,
                          "expected_policy": "preserve_or_reject"})
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("冻结目录已含文件；禁止覆盖输入")
    root.mkdir(parents=True, exist_ok=True)
    routes = []
    for kind in KINDS:
        body = "sphere" if kind in ("vertical", "stop_resume") else "slab"
        routes.append(route("development", kind, body, 1, root))
        for index, test_body in enumerate(("slab", "sphere"), start=1):
            routes.append(route("evaluation", kind, test_body, index, root))
    negatives = negative_inputs(root)
    protocol = {
        "schema_version": 1, "seed": SEED, "record_kind": "simulated",
        "coordinate_frame": {"name": "bone", "length_unit": "mm", "time_unit": "ms", "handedness": "right"},
        "replay_policy": {"late_event": "reject", "max_link_gap_ms": 200,
                          "interpolate_missing_motion": False},
        "quality": {"minimum_angle_deg": 25, "minimum_q": 0.4, "geometry_budget_mm": 0.1},
        "geometry_samples_per_direction": 8192,
        "geometry_seed": SEED, "statistics_unit": "route",
        "independent_repetitions": 3, "diagnostic_repeat_limit": 5,
        "primary_metric": "continuous_accepted_cutting_prefix_length_over_registered_prefix_count",
        "reference": "analytic solid minus union of arrived sphere capsules; sampled mesh error separately recorded",
        "evaluation_access": "candidate outputs remain unopened until code and parameters are frozen",
        "nominal_negative_voxel_mm": 0.02,
    }
    save_json(root / "02-评价协议.json", protocol)
    save_json(root / "01-冻结清单.json", {
        "schema_version": 1, "generator": Path(__file__).name,
        "generator_sha256": digest(Path(__file__)), "protocol_sha256": digest(root / "02-评价协议.json"),
        "reference_code_sha256": digest(HERE / "followup_reference.py"),
        "development_route_count": 6, "evaluation_route_count": 12,
        "routes": routes, "negative_inputs": negatives,
    })
    print(json.dumps({"output": str(root), "development": 6, "evaluation": 12,
                      "negative_inputs": len(negatives)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
