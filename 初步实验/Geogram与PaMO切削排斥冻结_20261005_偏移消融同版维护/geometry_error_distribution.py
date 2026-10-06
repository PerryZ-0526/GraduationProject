"""几何误差按面积采样比例和分位数报告，最大误差不单独决定质量结论。"""

import numpy as np
import trimesh

from audit_pamo_outputs import area_samples, as_polydata
from geometry_preservation_audit import MeshDistance


def distance_distribution(distances, thresholds=(.05, .1, .15, .2)):
    values = np.asarray(distances, dtype=float)
    finite = np.isfinite(values)
    if not len(values) or not finite.all():
        raise ValueError("距离统计包含非有限值或空集合")
    return {"count": len(values), "mean_mm": float(values.mean()), "max_mm": float(values.max()),
            "quantiles_mm": {str(q): float(np.quantile(values, q)) for q in (.5, .9, .95, .99)},
            "within_distance_fraction": {str(t): float(np.mean(values <= t)) for t in thresholds}}


def geometry_error_distribution(candidate, reference):
    source = as_polydata(candidate)
    target = reference if hasattr(reference, "points") else as_polydata(reference)
    forward, reverse = MeshDistance(target), MeshDistance(source)
    # 固定独立均匀面积样本；顶点密度不能代替表面面积权重，两类统计分别记录。
    area_forward = distance_distribution(forward(area_samples(source, 8192, 20260922)))
    area_reverse = distance_distribution(reverse(area_samples(target, 8192, 20260923)))
    coverage = min(area_forward["within_distance_fraction"]["0.1"], area_reverse["within_distance_fraction"]["0.1"])
    return {"area_forward": area_forward, "area_reverse": area_reverse,
            "vertices_forward": distance_distribution(forward(source.points)),
            "vertices_reverse": distance_distribution(reverse(target.points)),
            "minimum_bidirectional_area_fraction_within_0_1_mm": coverage,
            "coverage_profiles": {str(ratio): coverage >= ratio for ratio in (.95, .99)},
            "area_fraction_estimated_by_sampling": True, "continuous_geometry_certified": False}


def cutting_surface_distribution(candidate, maintenance_source, operand_bits):
    """维护源工具来源面的单向误差，区域直接由冻结来源标签确定。"""
    bits = np.asarray(operand_bits)
    if len(bits) != len(maintenance_source.faces):
        raise ValueError("切削面来源标签长度不同")
    mask = (bits.astype(int) & 2) != 0
    if not mask.any():
        return {"status": "no_tool_source_faces", "source_faces": 0}
    region = trimesh.Trimesh(maintenance_source.vertices.copy(), maintenance_source.faces[mask].copy(), process=False)
    points = area_samples(as_polydata(region), 8192, 20261005)
    # 只评价真实来源区域到候选的方向，不把这一方向称为双向局部证书。
    return {"status": "measured", "source_faces": int(mask.sum()), "source_area_mm2": float(region.area),
            "source_area_fraction": float(region.area / maintenance_source.area),
            "region_definition": "maintenance_source_operand_bits_contains_2", "direction": "cut_source_to_candidate",
            "sampling_seed": 20261005, "distribution": distance_distribution(MeshDistance(as_polydata(candidate))(points))}
