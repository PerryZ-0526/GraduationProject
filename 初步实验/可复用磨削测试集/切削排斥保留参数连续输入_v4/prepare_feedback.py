"""把可复用网格和运动转换成连续组合的冻结输入，登记每段离散工具。"""

import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import sys
import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "Geogram与PaMO组合验证"))
sys.path.insert(0, str(HERE.parent / "共同运动记录与方法对照"))
from locality_masks import save_obj_fp64
from geogram_baseline import _capsule_mesh


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_route(body, name, motion, initial, inputs, split, source_kind):
    """使用已有运动端点，不省略重复段；后续执行器决定包含复用。"""
    rid = body["id"] + "_" + name
    radius = motion["tool_radius_mm"]
    route = {"id": rid, "split": split, "category": name, "body": "ct", "source_kind": source_kind,
             "body_dispatch_note": "兼容旧执行器的离散网格分支，body=ct不代表输入是CT",
             "initial_mesh": initial.name, "initial_mesh_sha256": digest(initial),
             "tool": {"kind": "sphere", "radius_mm": radius, "mesh_subdivisions": 3},
             "events": [], "cutting_prefix_ids": [], "prefix_tools": [],
             "reference": {"kind": "same_discrete_tools_cumulative_CSG", "certified": False}}
    points = [np.asarray(e["position_mm"]) for e in motion["events"]]
    for index, (start, end) in enumerate(zip(points, points[1:])):
        eid = f"e{index}"
        route["events"].append({"id": eid, "arrival_index": index, "timestamp_ms": (index + 1) * 100,
                                "position_mm": end.tolist(), "explicit_sweep_start_mm": start.tolist(),
                                "tool_radius_mm": radius, "orientation_xyzw": [0, 0, 0, 1],
                                "cutting": True, "connect_from_previous": False})
        tool = _capsule_mesh({"start": start, "end": end, "radius": radius}, subdivisions=3)
        path = inputs / (rid + "_" + eid + "_tool.obj")
        save_obj_fp64(tool, path)
        route["cutting_prefix_ids"].append(eid)
        route["prefix_tools"].append({"event_id": eid, "mesh": path.name, "sha256": digest(path), "faces": len(tool.faces)})
    return route


def prepare(output):
    inputs = output / "inputs"
    inputs.mkdir(parents=True, exist_ok=False)
    root = HERE / "合成输入_v1"
    manifest_path = root / "01-测试集清单.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    routes = []
    for body in manifest["bodies"]:
        source = root / body["mesh"]
        if digest(source) != body["sha256"]:
            raise ValueError("合成原件摘要改变")
        initial = inputs / source.name
        shutil.copyfile(source, initial)
        for item in body["routes"]:
            path = root / item["file"]
            if digest(path) != item["sha256"]:
                raise ValueError("运动原件摘要改变")
            motion = json.loads(path.read_text(encoding="utf-8"))
            routes.append(make_route(body, item["name"], motion, initial, inputs,
                                     "development" if body["split"] == "development" else "evaluation", "synthetic"))
    report = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "generator_sha256": digest(Path(__file__)), "asset_manifest_sha256": digest(manifest_path),
              "routes": routes, "negative_inputs": [], "units": {"length": "mm", "time": "ms"},
              "replay_policy": {"late_event": "reject", "max_link_gap_ms": 200},
              "scope": "35个不同合成体、140条完整冻结路线，不代表已经运行维护",
              "tool_discretization": "icosphere subdivisions=3端点凸包，参照离散误差未认证"}
    (output / "01-完整范围冻结清单.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"routes": len(routes), "prefixes": sum(len(r["cutting_prefix_ids"]) for r in routes)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    prepare(parser.parse_args().output)
