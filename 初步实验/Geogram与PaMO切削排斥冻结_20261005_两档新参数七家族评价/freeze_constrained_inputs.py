"""封存旧开发、全范围应用及未见十二路线，禁止从候选结果挑选输入。"""

from copy import deepcopy
import argparse
import json
from pathlib import Path
import shutil
import sys

import trimesh

import freeze_followup_inputs as generator
from locality_masks import save_obj_fp64
from run_geometry_study import now, save
from audit_followup_candidate import sha256

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    inputs = args.output / "inputs"
    inputs.mkdir(parents=True)
    old = HERE / "实验结果/20260928_后续输入冻结_v3"
    old_manifest = json.loads((old / "01-冻结清单.json").read_text(encoding="utf-8"))
    routes = []
    for route in old_manifest["routes"]:
        if route["split"] == "development":
            routes.append(deepcopy(route))
            for name in [route["initial_mesh"], *[r["mesh"] for r in route["prefix_tools"]]]:
                shutil.copy2(old / name, inputs / name)
    # 新随机流只改变输入生成；保留原生成器源码，不读取任何独立候选输出。
    generator.SEED = 20261004
    for kind in generator.KINDS:
        for index, body in enumerate(("slab", "sphere"), start=3):
            route = generator.route("independent20261004", kind, body, index, inputs)
            route["split"] = "evaluation"
            routes.append(route)
    previous = HERE / "实验结果/20261004_连续几何体检准备"
    geometry = json.loads((previous / "01-连续几何批次清单.json").read_text(encoding="utf-8"))
    for route in geometry["routes"]:
        if route["split"] in ("development", "application"):
            route = deepcopy(route)
            if route["split"] == "development":
                route["split"] = "long"
            routes.append(route)
            for name in [route["initial_mesh"], *[r["mesh"] for r in route["prefix_tools"]]]:
                shutil.copy2(previous / "inputs" / name, inputs / name)
    # 原138段保留历史计划约束工具定义，不将它冒称任意真实物理钻头扫掠。
    sys.path.insert(0, str(HERE.parent / "真实骨模型演示"))
    import real_bone_demo as original
    ct16 = next(r for r in routes if r["id"] == "application_ct_16")
    ct138 = deepcopy(ct16)
    ct138.update(id="application_ct_original138", events=[], cutting_prefix_ids=[], prefix_tools=[],
                 tool_definition="historical_simulated_capsule_intersect_plan_phase_cylinder; manifold_discrete_tool")
    radii = {"面粗": original.R_PLATE, "面精": original.R_PLATE,
             "台粗": original.R_BOSS, "台精": original.R_BOSS, "柱钻": original.R_POST}
    trajectory = original.trajectory()
    if len(trajectory) != 138:
        raise ValueError("原轨迹数量变更，禁止静默改变范围")
    for n, (phase, radius, start, end) in enumerate(trajectory):
        eid = f"e{n}"
        raw = original.sweep_capsule(radius, start, end)
        boundary = original._cyl_plan(radii[phase], -20, 20)
        tool = trimesh.boolean.intersection([raw, boundary], engine="manifold")
        name = f"application_ct_original138_{eid}_tool.obj"
        save_obj_fp64(tool, inputs / name)
        ct138["events"].append({"id": eid, "arrival_index": n, "timestamp_ms": n * 100,
            "position_mm": list(end), "explicit_sweep_start_mm": list(start), "tool_radius_mm": radius,
            "orientation_xyzw": [0, 0, 0, 1], "cutting": True, "connect_from_previous": False,
            "phase": phase, "plan_clip_radius_mm": radii[phase]})
        ct138["cutting_prefix_ids"].append(eid)
        ct138["prefix_tools"].append({"event_id": eid, "mesh": name, "sha256": sha256(inputs / name)})
    routes.append(ct138)
    negatives = []
    for width in (.015, .03, .05):
        for kind in ("thin_wall", "narrow_gap", "through_hole"):
            if kind == "thin_wall":
                mesh = trimesh.creation.box(extents=(2, 2, width))
            elif kind == "narrow_gap":
                left = trimesh.creation.box(extents=(1, 2, 1))
                right = left.copy()
                left.apply_translation([-(1 + width) / 2, 0, 0])
                right.apply_translation([(1 + width) / 2, 0, 0])
                mesh = trimesh.util.concatenate((left, right))
            else:
                mesh = generator.torus_mesh(.5 + width / 2, .5)
            name = f"new_negative_{kind}_{width:.3f}.obj"
            save_obj_fp64(mesh, inputs / name)
            negatives.append({"id": name[:-4], "mesh": name, "sha256": sha256(inputs / name),
                              "feature_width_mm": width})
    record = {"time_beijing": now(), "generator_sha256": sha256(Path(__file__)), "seed": 20261004,
        "routes": routes, "negative_inputs": negatives, "replay_policy": geometry["replay_policy"],
        "reference_error_status": "discrete_reference_error_not_certified", "independent_route_count": 12,
        "evaluation_access": "new_candidate_outputs_unopened_until_code_freeze",
        "prior_independent_routes_now_seen": True,
        "scope": "six_development; twelve_new_independent; two_long24; CT16; original_CT138; nine_new_small_features"}
    save(args.output / "01-完整范围冻结清单.json", record)
    print("routes", len(routes), "prefixes", sum(len(r["cutting_prefix_ids"]) for r in routes),
          "manifest_sha256", sha256(args.output / "01-完整范围冻结清单.json"), flush=True)


if __name__ == "__main__":
    main()
