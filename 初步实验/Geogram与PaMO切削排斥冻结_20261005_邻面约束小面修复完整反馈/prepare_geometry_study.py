"""冻结研究一连续几何体检批次，沿用独立路线并加入长序列和CT应用。"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import argparse
import json
from pathlib import Path
import shutil
import tarfile

import numpy as np
import trimesh

from freeze_followup_inputs import capsule_mesh, digest, surface_z
from followup_reference import audit
from motion_record import replay_case


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
POLICY = {"late_event": "reject", "max_link_gap_ms": 200,
          "interpolate_missing_motion": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists():
        raise FileExistsError(out)
    frozen = HERE / "实验结果/20260928_后续输入冻结_v3"
    audit(frozen)
    original = json.loads((frozen / "01-冻结清单.json").read_text(encoding="utf-8"))
    out.mkdir(parents=True)
    inputs = out / "inputs"
    inputs.mkdir()
    routes = deepcopy([r for r in original["routes"] if r["split"] == "evaluation"])
    for route in routes:
        route["reference_role"] = "independent_analytic_and_discrete_mesh"
        for name in [route["initial_mesh"], *[t["mesh"] for t in route["prefix_tools"]]]:
            shutil.copy2(frozen / name, inputs / name)

    # 长序列只进入开发组，不冒充新的独立测试数据。
    for body in ("slab", "sphere"):
        base = next(r for r in original["routes"] if r["split"] == "development" and r["body"] == body)
        route = deepcopy(base)
        route.update(id=f"development_long_{body}_24", category="long", split="development",
                     reference_role="same_discrete_initial_and_cumulative_tools")
        route["initial_mesh"] = route["id"] + "_initial.obj"
        shutil.copy2(frozen / base["initial_mesh"], inputs / route["initial_mesh"])
        route["initial_mesh_sha256"] = digest(inputs / route["initial_mesh"])
        events = []
        for y in np.linspace(-0.8, 0.8, 8):
            xs = (-0.8, 0.0, 0.8) if len(events) % 6 == 0 else (0.8, 0.0, -0.8)
            for x in xs:
                n = len(events)
                z = surface_z(body, x, y, tuple(route["analytic_body"]["slope_xy"] or (0, 0))) + 0.54
                events.append({"id": f"e{n}", "arrival_index": n, "timestamp_ms": n * 100,
                               "position_mm": [float(x), float(y), float(z)],
                               "orientation_xyzw": [0, 0, 0, 1], "cutting": True,
                               "connect_from_previous": n > 0})
        route["events"] = events
        route["prefix_tools"] = []
        route["cutting_prefix_ids"] = [e["id"] for e in events]
        route["expected_event_rejections"] = []
        route["missing_interval_ms"] = None
        for p in replay_case(route, POLICY)["primitives"]:
            name = route["id"] + "_" + p["event_id"] + "_tool.obj"
            capsule_mesh(p).export(inputs / name, digits=17)
            route["prefix_tools"].append({"event_id": p["event_id"], "mesh": name,
                                          "sha256": digest(inputs / name)})
        routes.append(route)

    # CT初态沿用已保存的整骨拼接快照，明确区分原始CT与已维护的几何。
    joint = ROOT / "初步实验/边界过渡带联合重建/实验结果/joint.npz"
    data = np.load(joint)
    bone = trimesh.Trimesh(data["whole_vertices"], data["whole_faces"], process=False)
    if not bone.is_watertight or not bone.is_winding_consistent:
        raise ValueError("既有CT整骨快照不闭合或绕序不一致")
    name = "application_ct_16_initial.obj"
    bone.export(inputs / name, digits=17)
    route = {"id": "application_ct_16", "split": "application", "category": "ct_crossing",
             "body": "ct", "initial_mesh": name, "initial_mesh_sha256": digest(inputs / name),
             "reference_role": "same_preprocessed_ct_initial_and_discrete_cumulative_tools",
             "source_npz_sha256": digest(joint), "tool": {"radius_mm": 3.0},
             "events": [], "prefix_tools": [], "expected_event_rejections": []}
    sphere = trimesh.creation.icosphere(subdivisions=3, radius=3.0)
    segments = [(float(a), .037, float(b), .037) for a, b in zip(np.linspace(-1, 1, 9)[:-1], np.linspace(-1, 1, 9)[1:])]
    segments += [(.037, float(a), .037, float(b)) for a, b in zip(np.linspace(-1, 1, 9)[:-1], np.linspace(-1, 1, 9)[1:])]
    # 每段独立登记扫掠，第二条交叉路线的起点不与第一条路线末点相连。
    for n, (ax, ay, bx, by) in enumerate(segments):
        eid = f"e{n}"
        tool = trimesh.convex.convex_hull(np.vstack((sphere.vertices + [ax, ay, 1.8],
                                                    sphere.vertices + [bx, by, 1.8])))
        tool_name = f"application_ct_16_{eid}_tool.obj"
        tool.export(inputs / tool_name, digits=17)
        route["events"].append({"id": eid, "arrival_index": n, "timestamp_ms": n * 100,
                                "position_mm": [bx, by, 1.8], "orientation_xyzw": [0, 0, 0, 1],
                                "cutting": True, "connect_from_previous": False,
                                "explicit_sweep_start_mm": [ax, ay, 1.8]})
        route["prefix_tools"].append({"event_id": eid, "mesh": tool_name,
                                      "sha256": digest(inputs / tool_name)})
    route["cutting_prefix_ids"] = [e["id"] for e in route["events"]]
    routes.append(route)
    negatives = deepcopy(original["negative_inputs"])
    for item in negatives:
        shutil.copy2(frozen / item["mesh"], inputs / item["mesh"])
    manifest = {"schema_version": 1,
                "time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                "parent_manifest_sha256": digest(frozen / "01-冻结清单.json"),
                "replay_policy": POLICY, "routes": routes, "negative_inputs": negatives,
                "algorithm": "author_P_full_three_stages_ratio1_minvertex0_original_sign",
                "branches": {"C0": "Geogram parent feedback; PaMO display only",
                             "C1": "audited PaMO parent feedback",
                             "R": "original initial minus accumulated union of discrete tools"},
                "geometry_budget_mm": 0.1, "far_margin_mm": 0.1,
                "distance_samples_per_direction": 8192,
                "reference_error_status": "discrete_reference_error_not_certified",
                "test_access": "original baseline characterization; inspected routes become seen",
                "quality": "report angle fractions below 10/5/1 and high quality 25deg_q0.4; no hard angle rejection"}
    path = out / "01-连续几何批次清单.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with tarfile.open(out / "连续几何输入包.tar.gz", "w:gz") as archive:
        for item in sorted(inputs.glob("*.obj")):
            archive.add(item, arcname="inputs/" + item.name)
    print(json.dumps({"routes": len(routes), "cutting_prefixes": sum(len(r["cutting_prefix_ids"]) for r in routes),
                      "manifest_sha256": digest(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
