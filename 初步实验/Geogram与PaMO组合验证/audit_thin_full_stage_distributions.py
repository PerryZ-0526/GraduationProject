"""对同一次薄壁GPU各阶段保存网格核对体积与误差分布，不改变评价门槛。"""

import json
from pathlib import Path

import trimesh
from run_constrained_batch import RemoteQuality
from run_geometry_study import save, now
from audit_followup_candidate import sha256, quality_distribution
from geometry_error_distribution import geometry_error_distribution


def main():
    root = Path("D:/GraduationProject_切削排斥证据")
    output = root / "20261005_薄壁首刀同次完整GPU三阶段定位"
    source_path = root / "20261005_严格无变化复用薄壁三刀真实反馈/薄壁_新参数1p4375_交叉_e0_candidate_input/clean_source.obj"
    source = trimesh.load(source_path, force="mesh", process=False)
    observed_path = output / "stage_observations/01-薄壁同次完整GPU三阶段保存.json"
    observed = json.loads(observed_path.read_text("utf8"))
    full = json.loads((output / "01-薄壁首刀完整三阶段观测终态.json").read_text("utf8"))
    assert full["source_sha256"] == sha256(source_path)
    rows = []
    for item in observed["rows"]:
        path = output / "stage_observations" / item["file"]
        assert sha256(path) == item["sha256"]
        mesh = trimesh.load(path, force="mesh", process=False)
        assert item["embedding"]["embedded_closed"]
        rows.append({"stage": item["stage"], "sha256": sha256(path), "volume_mm3": float(mesh.volume),
            "volume_ratio_to_source": float(mesh.volume / source.volume),
            "geometry_distribution_to_physical_source": geometry_error_distribution(mesh, source),
            "quality": quality_distribution(mesh)})
    assert rows[-1]["sha256"] == full["output_sha256"]
    save(output / "03-同次各阶段体积与误差分布.json", {"生成时间": now(), "修改时间及修改内容": "首次生成，同次GPU保存阶段复审",
        "文档概述": "体积与面积误差、顶点尾部分开，不设固定最大值，不以距离小推断薄壁保留",
        "索引目录": ["rows"], "source_sha256": sha256(source_path), "source_volume_mm3": float(source.volume),
        "observation_sha256": sha256(observed_path), "rows": rows,
        "continuous_geometry_certified": False, "new_GPU_calls": 0})
    print([(r["stage"], r["volume_mm3"], r["geometry_distribution_to_physical_source"]["minimum_bidirectional_area_fraction_within_0_1_mm"],
        r["geometry_distribution_to_physical_source"]["vertices_reverse"]["max_mm"]) for r in rows], flush=True)


if __name__ == "__main__":
    main()
