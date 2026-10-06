"""35号冻结路线的独立解析集合参照与输入完整性审计。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import trimesh


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "共同运动记录与方法对照"))
from motion_record import motion_field, replay_case


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def initial_field(points: np.ndarray, route: dict) -> np.ndarray:
    """负值表示处于闭合初始材料内部。"""
    points = np.asarray(points, dtype=np.float64)
    body = route["analytic_body"]
    if body["kind"] == "sphere":
        return np.linalg.norm(points, axis=-1) - body["radius_mm"]
    a, b = body["slope_xy"]
    xmin, xmax, ymin, ymax = body["bounds_xy_mm"]
    return np.maximum.reduce((
        points[..., 2] - a * points[..., 0] - b * points[..., 1],
        body["bottom_z_mm"] - points[..., 2],
        xmin - points[..., 0], points[..., 0] - xmax,
        ymin - points[..., 1], points[..., 1] - ymax,
    ))


def material_field(points: np.ndarray, route: dict, through_event_id: str | None = None) -> np.ndarray:
    """解析差集：初始材料减去已到达且被接受的球形扫掠并集。"""
    replay = replay_case(route, {"late_event": "reject", "max_link_gap_ms": 200,
                                 "interpolate_missing_motion": False}, through_event_id)
    return np.maximum(initial_field(points, route), -motion_field(points, replay))


def audit(root: Path) -> dict:
    manifest_path, protocol_path = root / "01-冻结清单.json", root / "02-评价协议.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if sha256(protocol_path) != manifest["protocol_sha256"]:
        raise ValueError("评价协议哈希不匹配")
    if sha256(HERE / manifest["generator"]) != manifest["generator_sha256"]:
        raise ValueError("输入生成器哈希不匹配")
    if sha256(Path(__file__)) != manifest["reference_code_sha256"]:
        raise ValueError("解析参照代码哈希不匹配")
    route_ids = set()
    rows = []
    for route in manifest["routes"]:
        if route["id"] in route_ids:
            raise ValueError("路线编号重复")
        route_ids.add(route["id"])
        path = root / route["initial_mesh"]
        if sha256(path) != route["initial_mesh_sha256"]:
            raise ValueError(f"{route['id']}: 初始网格哈希不匹配")
        mesh = trimesh.load(path, force="mesh", process=False)
        if not mesh.is_watertight or not mesh.is_winding_consistent or len(mesh.split(only_watertight=False)) != 1:
            raise ValueError(f"{route['id']}: 初始网格闭合拓扑无效")
        if len(route["prefix_tools"]) != len(route["cutting_prefix_ids"]):
            raise ValueError(f"{route['id']}: 前缀工具数量不一致")
        for tool in route["prefix_tools"]:
            tool_path = root / tool["mesh"]
            if sha256(tool_path) != tool["sha256"]:
                raise ValueError(f"{route['id']}/{tool['event_id']}: 工具哈希不匹配")
        inside = np.array([[0.0, 0.0, -0.5 if route["body"] == "slab" else 0.0]])
        outside = np.array([[0.0, 0.0, 3.0]])
        if initial_field(inside, route)[0] >= 0 or initial_field(outside, route)[0] <= 0:
            raise ValueError(f"{route['id']}: 解析初态内外探针无效")
        replay = replay_case(route, json.loads(protocol_path.read_text(encoding="utf-8"))["replay_policy"])
        if replay["late_event_ids"] != route["expected_event_rejections"]:
            raise ValueError(f"{route['id']}: 晚到事件与预登记不符")
        rows.append({"id": route["id"], "initial_faces": len(mesh.faces),
                     "prefixes": len(route["cutting_prefix_ids"]), "late_events": replay["late_event_ids"]})
    negative_rows = []
    for case in manifest["negative_inputs"]:
        path = root / case["mesh"]
        if sha256(path) != case["sha256"]:
            raise ValueError(f"{case['id']}: 符号检查输入哈希不匹配")
        mesh = trimesh.load(path, force="mesh", process=False)
        components = len(mesh.split(only_watertight=False))
        if not mesh.is_watertight or components != case["expected_components"]:
            raise ValueError(f"{case['id']}: 符号检查输入拓扑不符")
        negative_rows.append({"id": case["id"], "components": components, "euler_number": int(mesh.euler_number)})
    return {"routes": rows, "negative_inputs": negative_rows,
            "development": sum(row["id"].startswith("development_") for row in rows),
            "evaluation": sum(row["id"].startswith("evaluation_") for row in rows)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.root.resolve()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
