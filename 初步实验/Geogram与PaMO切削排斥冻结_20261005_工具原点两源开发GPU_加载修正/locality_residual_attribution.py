"""按父三角面、布尔新面及操作后残差定位局部维护的质量瓶颈。"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "共同运动记录与方法对照"))
from surface_methods import _triangle_quality_values
from locality_masks import make_masks


def keys(mesh):
    """仅用于数值归因的1e-12毫米舍入键，不作为严格几何对应证书。"""
    return [tuple(sorted(tuple(p) for p in np.round(triangle, 12))) for triangle in mesh.triangles]


def tail(mesh):
    return _triangle_quality_values(mesh.vertices, mesh.faces)[1] < 10


def main():
    prepared = HERE / "实验结果/20260929_C1试运行准备"
    frozen = HERE / "实验结果/20260928_后续输入冻结_v3"
    provenance = HERE / "实验结果/20261004_局部维护来源重放"
    manifest = json.loads((prepared / "01-C1试运行清单.json").read_text(encoding="utf-8"))
    output = HERE / "实验结果/20261004_局部维护八轮折叠开发/07-局部质量残差归因.json"
    if output.exists():
        raise FileExistsError(output)
    result = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "triangle_match": "coordinate_tuple_round_12_decimals_numerical_only",
              "quality_threshold_deg": 10, "rows": []}
    for route in manifest["routes"]:
        kind = "crossing" if route["category"] == "crossing" else "stop_resume"
        parent_path = frozen / route["initial_mesh"]
        for event in route["cutting_prefix_ids"]:
            case = kind + "_" + event
            source = trimesh.load(provenance / case / "no_simplify.obj", force="mesh", process=False)
            bits = np.array(json.loads((provenance / case / "no_simplify.json").read_text())["operand_bits"])
            parent = trimesh.load(parent_path, force="mesh", process=False)
            parent_keys = set(keys(parent))
            inherited = np.array([key in parent_keys for key in keys(source)])
            tool = trimesh.load(frozen / next(t["mesh"] for t in route["prefix_tools"] if t["event_id"] == event), force="mesh", process=False)
            active, fixed = make_masks(source, bits, tool, "boolean")
            bad = tail(source)
            row = {"case": case, "source_below_10_faces": int(bad.sum()),
                   "source_tail_numerically_inherited_parent_triangles": int((bad & inherited & (bits == 1)).sum()),
                   "source_tail_parent_split_or_retriangulated": int((bad & ~inherited & (bits == 1)).sum()),
                   "source_tail_tool_origin": int((bad & (bits == 2)).sum()),
                   "source_tail_outside_two_ring_activity": int((bad & ~active).sum()), "candidates": []}
            lookup = {tuple(sorted(map(int, face))): i for i, face in enumerate(source.faces)}
            for budget, directory, candidate_root in ((1, "20261004_局部维护保存帧开发", "saved_batch_outputs"),
                                                       (8, "20261004_局部维护八轮折叠开发", "eight_pass_outputs")):
                folder = HERE / "实验结果" / directory / "取回输出" / candidate_root / case
                if not folder.exists():
                    continue
                mesh = trimesh.load(folder / "r0_boolean.obj", force="mesh", process=False)
                ids = np.load(folder / "r0_boolean_original_ids.npy")
                bad_candidate = tail(mesh)
                unchanged_source_ids = []
                modified = 0
                for face in mesh.faces[bad_candidate]:
                    old = ids[face]
                    source_id = lookup.get(tuple(sorted(map(int, old))))
                    if source_id is not None and np.allclose(mesh.vertices[face], source.vertices[old], rtol=0, atol=1e-12):
                        unchanged_source_ids.append(source_id)
                    else:
                        modified += 1
                unchanged_source_ids = np.array(unchanged_source_ids, dtype=int)
                row["candidates"].append({"collapse_pass_budget": budget,
                                          "below_10_faces": int(bad_candidate.sum()),
                                          "tail_unchanged_source_triangles": len(unchanged_source_ids),
                                          "tail_unchanged_outside_activity": int((~active[unchanged_source_ids]).sum()),
                                          "tail_unchanged_tool_faces": int((bits[unchanged_source_ids] == 2).sum()),
                                          "tail_modified_geometry_or_connectivity": modified})
            result["rows"].append(row)
            parent_path = prepared / "取回输出" / case / "pamo.obj"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print([(r["case"], r["source_tail_outside_two_ring_activity"], r["candidates"]) for r in result["rows"]])


if __name__ == "__main__":
    main()
