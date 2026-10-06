"""核对三个倍率实际简化输入逐位相同，并报告同源各阶段统计。"""

import hashlib
import json
from pathlib import Path

import numpy as np
import trimesh
from run_constrained_batch import RemoteQuality
from run_geometry_study import save, now
from audit_followup_candidate import sha256, quality_distribution
from geometry_error_distribution import geometry_error_distribution


def main():
    root = Path("D:/GraduationProject_切削排斥证据")
    source_path = root / "20261005_严格无变化复用薄壁三刀真实反馈/薄壁_新参数1p4375_交叉_e0_candidate_input/clean_source.obj"
    source = trimesh.load(source_path, force="mesh", process=False)
    output = root / "20261005_薄壁同源三简化预算完整对照核对"
    output.mkdir(exist_ok=False)
    baseline = None
    rows = []
    for ratio in (1, 2, 4):
        batch = root / f"20261005_薄壁首刀同源简化预算对照_ratio{ratio}"
        execution = json.loads((batch / "02-执行终态.json").read_text("utf8"))
        full = json.loads((batch / "01-薄壁首刀完整三阶段观测终态.json").read_text("utf8"))
        assert execution["execution"]["returncode"] == 0 and full["source_sha256"] == sha256(source_path)
        arrays = {name: array.copy() for name, array in np.load(batch / "stage_observations/stage1_centered.npz").items()}
        if baseline is None:
            baseline = arrays
        assert all(np.array_equal(arrays[name], baseline[name]) for name in arrays)
        tensor_hashes = {name: hashlib.sha256(array.tobytes()).hexdigest() for name, array in arrays.items()}
        stages = json.loads((batch / "stage_observations/01-薄壁同次完整GPU三阶段保存.json").read_text("utf8"))
        for item in stages["rows"]:
            path = batch / "stage_observations" / item["file"]
            assert sha256(path) == item["sha256"] and item["embedding"]["embedded_closed"]
            mesh = trimesh.load(path, force="mesh", process=False)
            rows.append({"ratio": ratio, "stage": item["stage"], "saved_sha256": sha256(path),
                "volume_mm3": float(mesh.volume), "volume_ratio_to_source": float(mesh.volume / source.volume),
                "faces": len(mesh.faces), "embedding": item["embedding"], "quality": quality_distribution(mesh),
                "geometry_distribution": geometry_error_distribution(mesh, source),
                "stage1_tensor_hashes": tensor_hashes, "full_execution_record_sha256": sha256(batch / "02-执行终态.json")})
    save(output / "01-三预算同源实际张量与各阶段统计.json", {"生成时间": now(), "修改时间及修改内容": "首次生成，三组实际简化输入逐位核对",
        "文档概述": "倍率1/2/4共用同一实际简化输入数组；误差和质量分开报告，保留所有组",
        "索引目录": ["rows"], "source_sha256": sha256(source_path), "source_volume_mm3": float(source.volume),
        "stage1_tensor_bitwise_identical": True, "new_full_GPU_calls": 3, "new_publications": 0,
        "timing_evidence": False, "continuous_geometry_certified": False, "rows": rows})
    print([(r["ratio"], r["stage"], r["faces"], r["volume_mm3"], r["geometry_distribution"]["minimum_bidirectional_area_fraction_within_0_1_mm"],
        r["geometry_distribution"]["vertices_reverse"]["max_mm"]) for r in rows], flush=True)


if __name__ == "__main__":
    main()
