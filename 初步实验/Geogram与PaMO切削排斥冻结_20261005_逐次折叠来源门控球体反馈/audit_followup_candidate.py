"""对冻结开发候选执行独立全网格、离散参照抽样审计。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import trimesh


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "共同运动记录与方法对照"))
from audit_pamo_outputs import audit_one
from surface_methods import _triangle_quality_values


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vertex_manifold_closed(faces: np.ndarray) -> bool:
    """闭合三角网格每个顶点的面邻接链接应为单个环。"""
    links = {}
    for a, b, c in faces:
        for center, first, second in ((a, b, c), (b, c, a), (c, a, b)):
            ring = links.setdefault(int(center), {})
            ring.setdefault(int(first), set()).add(int(second))
            ring.setdefault(int(second), set()).add(int(first))
    for ring in links.values():
        if not ring or any(len(neighbors) != 2 for neighbors in ring.values()):
            return False
        start = next(iter(ring))
        visited = {start}
        frontier = [start]
        while frontier:
            current = frontier.pop()
            for neighbor in ring[current] - visited:
                visited.add(neighbor)
                frontier.append(neighbor)
        if len(visited) != len(ring):
            return False
    return True


def quality_distribution(mesh: trimesh.Trimesh) -> dict:
    """按同一总面数分母统计小角尾部和严格高质量面。"""
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    q, angles, areas = _triangle_quality_values(vertices, faces)
    valid = (np.isfinite(q) & np.isfinite(angles) & np.isfinite(areas) &
             (areas > 1e-12))
    total = len(faces)
    total_area = float(np.sum(areas[valid]))

    def group(mask: np.ndarray) -> dict:
        count = int(np.count_nonzero(mask))
        return {"faces": count, "fraction": count / total if total else None,
                "area_fraction": float(np.sum(areas[mask]) / total_area) if total_area else None}

    result = {"total_faces": total, "invalid_faces": int(np.count_nonzero(~valid)),
              "denominator": "评价网格全部三角形，包括单列的退化或非有限面"}
    for threshold in (10, 5, 1):
        result[f"angle_below_{threshold}_deg"] = group(valid & (angles < threshold))
    result["high_quality_25_deg_q_0_4"] = group(valid & (angles >= 25) & (q >= 0.4))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--reference-sha256", required=True)
    parser.add_argument("--expected-components", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if sha256(args.reference) != args.reference_sha256:
        raise ValueError("离散参照摘要与冻结审计记录不符")
    for path in (args.source, args.candidate):
        if not path.is_file():
            raise FileNotFoundError(path)

    mesh = trimesh.load(args.candidate, force="mesh", process=False)
    components = len(mesh.split(only_watertight=False))
    vertex_manifold = vertex_manifold_closed(np.asarray(mesh.faces))
    metrics = audit_one(args.source, args.candidate, args.reference)
    distribution = quality_distribution(mesh)
    topology_passed = bool(metrics["topology_passed"] and
                           components == args.expected_components and vertex_manifold)
    sampled_passed = bool(distribution["invalid_faces"] == 0 and topology_passed and
                          metrics["sampled_geometry_passed"])
    now = datetime.now(timezone(timedelta(hours=8)))
    report = {
        "schema_version": 2,
        "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
        "inputs": {name: {"path": str(path), "sha256": sha256(path)} for name, path in
                   (("source", args.source), ("candidate", args.candidate),
                    ("reference", args.reference))},
        "expected_components": args.expected_components,
        "observed_components": components,
        "vertex_manifold_closed": vertex_manifold,
        "topology_passed_with_vertex_check": topology_passed,
        "quality_distribution": distribution,
        "legacy_strict_quality_passed": bool(metrics["quality_passed"]),
        "accepted_under_sampled_protocol_with_vertex_check": sampled_passed,
        "accepted_under_common_budget": None,
        "reason_common_budget_unknown": "离散参照误差和连续双向表面距离界尚未证实",
        "metrics": metrics,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sampled_passed": sampled_passed,
                      "angle_below_10_fraction": distribution["angle_below_10_deg"]["fraction"],
                      "common_budget": None}, ensure_ascii=False))


if __name__ == "__main__":
    main()
