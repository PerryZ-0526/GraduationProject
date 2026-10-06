"""体检布尔来源、活动范围与全量PaMO的远区变化，不读取独立测试输出。"""

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from time import perf_counter

import numpy as np
import trimesh
from vtkmodules.vtkCommonCore import reference
from vtkmodules.vtkCommonDataModel import vtkStaticCellLocator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "共同运动记录与方法对照"))
from audit_pamo_outputs import as_polydata, area_samples
from audit_followup_candidate import quality_distribution
from motion_record import capsule_field, replay_case
from preflight_geogram_prefixes import metrics


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class SurfaceQuery:
    """最近三角面距离和法向；结果属于浮点数值查询。"""

    def __init__(self, mesh):
        self.locator = vtkStaticCellLocator()
        self.locator.SetDataSet(as_polydata(mesh))
        self.locator.BuildLocator()
        self.normals = mesh.face_normals

    def __call__(self, points):
        closest, cid, sid, square = [0.0] * 3, reference(0), reference(0), reference(0.0)
        distances = np.empty(len(points))
        normals = np.empty((len(points), 3))
        for i, point in enumerate(points):
            self.locator.FindClosestPoint(point, closest, cid, sid, square)
            distances[i] = np.sqrt(float(square))
            normals[i] = self.normals[int(cid)]
        return distances, normals


def source_region(mesh, bits, rings=2, allow_shared=False):
    """工具来源面及来源交界为核心，沿实际面邻接扩展固定层数。"""
    bits = np.asarray(bits)
    # 新协议保留位3身份；默认仍拒绝共同来源，以保持历史复现。
    if len(bits) != len(mesh.faces) or np.any(~np.isin(bits, [1, 2, 3] if allow_shared else [1, 2])):
        raise ValueError("来源缺失或多义，不能视为可靠活动域")
    adjacent = mesh.face_adjacency
    seam = bits[adjacent[:, 0]] != bits[adjacent[:, 1]]
    core = (bits & 2) != 0
    core[np.unique(adjacent[seam])] = True
    active = core.copy()
    for _ in range(rings):
        connected = np.any(active[adjacent], axis=1)
        active[np.unique(adjacent[connected])] = True
    return core, active, mesh.face_adjacency_edges[seam]


def conservative_far_faces(mesh, primitives, margin=0.1):
    """利用胶囊场的1-Lipschitz性质筛选整面远离累计扫掠的三角面。"""
    center = mesh.triangles_center
    radius = np.linalg.norm(mesh.triangles - center[:, None], axis=2).max(axis=1)
    clearance = np.min(np.stack([capsule_field(center, p) for p in primitives]), axis=0)
    return clearance - radius > margin


def region_stats(mesh, mask):
    selected = trimesh.Trimesh(mesh.vertices, mesh.faces[mask], process=False)
    return {"faces": int(mask.sum()), "fraction": float(mask.mean()),
            "area_fraction": float(mesh.area_faces[mask].sum() / mesh.area),
            "quality": quality_distribution(selected)}


def far_drift(source, candidate, primitives, count=8192):
    """双向面积样本检验同一独立扫掠定义下的远区变化。"""
    target_query = SurfaceQuery(candidate)
    source_query = SurfaceQuery(source)
    rows = []
    for mesh, own, other, seed in ((source, source_query, target_query, 20261004),
                                  (candidate, target_query, source_query, 20261005)):
        points = area_samples(as_polydata(mesh), count, seed)
        clearance = np.min(np.stack([capsule_field(points, p) for p in primitives]), axis=0)
        points = points[clearance > 0.1]
        distance, normal = other(points)
        _, own_normal = own(points)
        angles = np.degrees(np.arccos(np.clip(np.sum(normal * own_normal, axis=1), -1, 1)))
        rows.append({"samples": len(points), "max_mm": float(distance.max()) if len(points) else None,
                     "mean_mm": float(distance.mean()) if len(points) else None,
                     "p95_mm": float(np.percentile(distance, 95)) if len(points) else None,
                     "over_0_01_mm": int((distance > 0.01).sum()),
                     "normal_p95_deg": float(np.percentile(angles, 95)) if len(points) else None,
                     "normal_max_deg": float(angles.max()) if len(points) else None})
    return {"source_to_candidate": rows[0], "candidate_to_source": rows[1],
            "scope": "双向远区面积样本与最近面法向，非连续界或顶点对应"}


def verify_labels(mesh, bits, parent, tool, seam_edges, allow_shared=False):
    """用操作数几何核对来源及交界位置，不能只信任整数标签。"""
    query_parent, query_tool = SurfaceQuery(parent), SurfaceQuery(tool)
    rows = {}
    for bit, query in ((1, query_parent), (2, query_tool)):
        # 共同来源面必须同时对父表面和工具表面通过检查。
        selected = (np.asarray(bits) & bit) != 0 if allow_shared else np.asarray(bits) == bit
        triangles = mesh.triangles[selected]
        samples = np.concatenate((triangles.reshape(-1, 3), triangles.mean(axis=1)))
        distance, _ = query(samples)
        rows[str(bit)] = {"samples": len(samples), "sampled_max_mm": float(distance.max(initial=0))}
    points = mesh.vertices[np.unique(seam_edges)]
    d_parent, _ = query_parent(points)
    d_tool, _ = query_tool(points)
    rows["seam"] = {"vertices": len(points), "parent_sampled_max_mm": float(d_parent.max(initial=0)),
                    "tool_sampled_max_mm": float(d_tool.max(initial=0))}
    rows["passed_1e_8_mm_numerical_check"] = all(rows[str(b)]["sampled_max_mm"] <= 1e-8 for b in (1, 2)) and all(
        rows["seam"][k] <= 1e-8 for k in ("parent_sampled_max_mm", "tool_sampled_max_mm"))
    return rows


def mesh_pair_drift(first, second):
    """双向顶点及面心检查，不能单凭不同摘要认定几何发生变化。"""
    values = []
    for source, target in ((first, second), (second, first)):
        points = np.vstack((source.vertices, source.triangles_center))
        distance, _ = SurfaceQuery(target)(points)
        values.append(float(distance.max(initial=0)))
    return {"first_to_second_sampled_max_mm": values[0], "second_to_first_sampled_max_mm": values[1],
            "continuous_bound_certified": False, "signed_volume_delta_mm3": float(second.volume - first.volume)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    prepared = HERE / "实验结果/20260929_C1试运行准备"
    frozen = HERE / "实验结果/20260928_后续输入冻结_v3"
    manifest = json.loads((prepared / "01-C1试运行清单.json").read_text(encoding="utf-8"))
    frozen_protocol = json.loads((frozen / "02-评价协议.json").read_text(encoding="utf-8"))
    report = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "protocol": {"source_core": "tool_origin_faces_and_parent_tool_seam_incident_faces",
                           "transition_rings": 2, "far_margin_mm": 0.1, "samples_each_direction": 8192,
                           "provenance_mode": "no_simplify_for_complete_labels_only",
                           "access": "eight_seen_development_C1_frames_only"}, "rows": []}
    for route in manifest["routes"]:
        kind = "crossing" if route["category"] == "crossing" else "stop_resume"
        parent_path = frozen / route["initial_mesh"]
        initial = trimesh.load(parent_path, force="mesh", process=False)
        for event in route["cutting_prefix_ids"]:
            start = perf_counter()
            case = kind + "_" + event
            original = prepared / "取回输出" / case
            folder = args.provenance / case
            source = trimesh.load(original / "geogram.obj", force="mesh", process=False)
            candidate = trimesh.load(original / "pamo.obj", force="mesh", process=False)
            raw = trimesh.load(folder / "no_simplify.obj", force="mesh", process=False)
            replay_default = trimesh.load(folder / "default.obj", force="mesh", process=False)
            bits = json.loads((folder / "no_simplify.json").read_text())["operand_bits"]
            tool_path = frozen / next(t["mesh"] for t in route["prefix_tools"] if t["event_id"] == event)
            parent = trimesh.load(parent_path, force="mesh", process=False)
            tool = trimesh.load(tool_path, force="mesh", process=False)
            # 事件策略来自原冻结评价协议，C1子清单没有重复保存该字段。
            primitives = replay_case(route, frozen_protocol["replay_policy"], event)["primitives"]
            core, active, seam_edges = source_region(raw, bits)
            far = conservative_far_faces(source, primitives)
            log = (original / "pamo.log").read_text(encoding="utf-8")
            stage = {name: float(ms) * 1000 for name, ms in re.findall(r"Time for (Remeshing|Simplification): ([0-9.eE+-]+) sec", log)}
            row = {"case": case, "route": route["id"], "event": event,
                   "inputs_sha256": {"parent": digest(parent_path), "tool": digest(tool_path),
                                      "source": digest(original / "geogram.obj"), "candidate": digest(original / "pamo.obj")},
                   "source_default_faces": len(source.faces), "source_no_simplify_faces": len(raw.faces),
                   "replay_default_vs_historical": mesh_pair_drift(replay_default, source),
                   "no_simplify_vs_replay_default": mesh_pair_drift(raw, replay_default),
                   "source_label_validation": verify_labels(raw, bits, parent, tool, seam_edges),
                   "source_core": region_stats(raw, core), "source_active_two_rings": region_stats(raw, active),
                   "seam_edges": len(seam_edges), "conservative_far_region": region_stats(source, far),
                   "pamo_all_quality": quality_distribution(candidate),
                   "far_maintenance_drift": far_drift(source, candidate, primitives),
                   "far_cumulative_drift": far_drift(initial, candidate, primitives),
                   "default_and_no_simplify_topology": {"default": metrics(source), "no_simplify": metrics(raw)},
                   "historical_unsynchronized_stage_ms": stage,
                   "historical_step": json.loads((original / "step.json").read_text(encoding="utf-8")),
                   "diagnostic_wall_ms": (perf_counter() - start) * 1000}
            report["rows"].append(row)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(case, "active_fraction", round(row["source_active_two_rings"]["fraction"], 4),
                  "far_max", row["far_maintenance_drift"]["source_to_candidate"]["max_mm"], flush=True)
            parent_path = original / "pamo.obj"
    report["status"] = "completed"
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
