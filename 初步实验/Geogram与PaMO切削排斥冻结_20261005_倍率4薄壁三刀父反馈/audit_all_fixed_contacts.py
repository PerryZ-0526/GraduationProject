"""逐项核对实际GPU异常接触的源身份与坐标量化，保留不能归因的项。"""
import argparse
import json
from pathlib import Path
import numpy as np
import trimesh
from pt_exact_reference import point_triangle_reference
from ee_exact_reference import edge_edge_reference
from audit_followup_candidate import sha256
from run_geometry_study import now, save


def audit_folder(folder):
    source = trimesh.load(folder / "source.obj", process=False)
    scale = 1.0 / np.ptp(source.vertices, axis=0).max()
    translation = -source.vertices.mean(axis=0) * scale
    results = []
    for method in ("boolean", "expanded"):
        root = folder / method
        trace = json.loads((root / "diff_trace.json").read_text(encoding="utf-8"))
        details = json.loads((root / "details.json").read_text(encoding="utf-8"))
        candidate = trimesh.load(root / "candidate.obj", process=False)
        ids = np.asarray(details["vertex_original_ids"])
        contact = trace["rows"][0]["collision_contacts"]
        if len(contact["samples"]) != contact["nonpositive_or_nonfinite"]:
            raise ValueError("接触记录仍被截断")
        rows = []
        for sample in contact["samples"]:
            vertices = np.asarray(sample["vertices"])
            original = ids[vertices]
            row = dict(contact=sample["contact"], type=sample["type"][0],
                       vertices=vertices.tolist(), original_ids=original.tolist(), fixed=sample["fixed"])
            # 不能映射到原始固定源的项必须单列，不用保存末态代替初态几何。
            if not all(sample["fixed"]) or np.any(original < 0):
                row["status"] = "not_original_fixed_contact"
            else:
                physical = source.vertices[original]
                np.testing.assert_array_equal(candidate.vertices[vertices], physical)
                encoded = (physical * scale + translation).astype(np.float32).astype(float)
                np.testing.assert_array_equal(encoded, sample["positions_normalized"])
                reference = point_triangle_reference if row["type"] == 3 else edge_edge_reference if row["type"] == 4 else None
                if reference is None:
                    raise ValueError("未知异常接触类型")
                _, raw_distance = reference(physical)
                _, encoded_distance = reference(encoded)
                row.update(points_fp64_mm=physical.tolist(), positions_fp32_normalized=encoded.tolist(),
                           distance_fp64_mm=raw_distance, distance_encoded_normalized=encoded_distance,
                           status="quantization_lost_positive_separation" if raw_distance > 0 and encoded_distance == 0
                           else "other_cause_requires_review")
            rows.append(row)
        results.append(dict(method=method, abnormal_contacts=contact["nonpositive_or_nonfinite"],
                            involving_free=contact["involving_free"], rows=rows,
                            quantization_cases=sum(row["status"] == "quantization_lost_positive_separation" for row in rows),
                            diff_calls=len(trace["rows"]), finite_energy_calls=sum(row["full_energy_finite"] for row in trace["rows"]),
                            trace_sha256=sha256(root / "diff_trace.json"), candidate_sha256=sha256(root / "candidate.obj")))
    return dict(time_beijing=now(), published=False, normalization_scale=float(scale),
                normalization_translation=translation.tolist(), source_sha256=sha256(folder / "source.obj"), methods=results,
                scope="完整已记录异常接触的坐标归因；不是全部接触、运动轨迹或算法成功证书")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, required=True)
    args = parser.parse_args()
    result = audit_folder(args.folder)
    save(args.folder / "02-全部异常固定接触坐标对拍.json", result)
    print([(row["method"], row["abnormal_contacts"], row["quantization_cases"]) for row in result["methods"]])
