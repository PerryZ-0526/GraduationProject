"""只读复核真实局部C1父链、输出拓扑与离散网格数值距离区间。"""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

import pyvista as pv
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "共同运动记录与方法对照"))
from audit_pamo_outputs import as_polydata
from geometry_preservation_audit import directed_interval, mesh_valid
from locality_feedback import digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    args = parser.parse_args()
    output = args.batch / "03-C1父链与离散距离区间复核.json"
    if output.exists():
        raise FileExistsError(output)
    results = HERE / "实验结果"
    execution = json.loads((args.batch / "01-局部C1逐帧执行与独立审计.json").read_text(encoding="utf-8"))
    if execution["status"] != "completed_with_recorded_failures":
        raise ValueError("执行批次未结束")
    for filename, expected in execution["code_sha256"].items():
        if digest(args.batch / filename) != expected:
            raise ValueError("批次冻结代码改变")
    frozen = results / "20260928_后续输入冻结_v3"
    if digest(frozen / "01-冻结清单.json") != execution["manifest_sha256"]:
        raise ValueError("父输入清单改变")
    manifest = json.loads((frozen / "01-冻结清单.json").read_text(encoding="utf-8"))
    references = json.loads((results / "20260928_开发解析参照/01-参照审计.json").read_text(encoding="utf-8"))["rows"]
    state = {r["id"]: {"sha256": r["initial_mesh_sha256"], "version": 0, "stopped": False}
             for r in manifest["routes"] if r["split"] == "development"}
    report = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "execution_sha256": digest(args.batch / "01-局部C1逐帧执行与独立审计.json"),
              "scope": "后验离散网格数值区间，浮点查询与参照离散误差均未认证；不改变原发布记录",
              "rows": []}
    for row in execution["rows"]:
        parent = state[row["route"]]
        if row["status"] == "blocked_by_previous_failure":
            if not parent["stopped"]:
                raise ValueError("缺失导致阻断的前序失败")
            continue
        if parent["stopped"] or row["parent_sha256"] != parent["sha256"] or row["parent_version"] != parent["version"]:
            raise ValueError("C1父链或发布版本不一致")
        if row["status"] == "contained_reused":
            if row["published_state"]["sha256"] != parent["sha256"] or digest(row["published_state"]["mesh"]) != parent["sha256"]:
                raise ValueError("重复复用改变了父快照")
            continue
        if row["status"] == "geogram_failed":
            parent["stopped"] = True
            continue
        control = row["control"]
        source = Path(row.get("maintenance_source", args.batch / (row["route"] + "_" + row["event"]) / "source.obj"))
        if digest(source) != control["source_sha256"]:
            raise ValueError("布尔输入改变")
        if not control["published"]:
            if row["published_state"]["sha256"] != parent["sha256"] or control["published_version"] != parent["version"]:
                raise ValueError("失败帧更改了已发布父版本")
            parent["stopped"] = True
            continue
        candidate = Path(row["published_state"]["mesh"])
        if digest(candidate) != row["published_state"]["sha256"]:
            raise ValueError("已发布候选改变")
        if control["published_version"] != parent["version"] + 1:
            raise ValueError("发布版本未按单帧递增")
        mesh = trimesh.load(candidate, force="mesh", process=False)
        valid, topology = mesh_valid(mesh)
        topology_matches = valid and topology["components"] == 1 and topology["euler_number"] == 2
        ref = next(r for r in references if r["route"] == row["route"] and r["event"] == row["event"])
        path = results / "20260928_开发解析参照" / ref["mesh"]
        if digest(path) != ref["sha256"]:
            raise ValueError("独立离散参照改变")
        reference = pv.read(path)
        surface = as_polydata(mesh)
        forward = directed_interval(surface, reference)
        reverse = directed_interval(reference, surface)
        report["rows"].append({"route": row["route"], "event": row["event"], "parent_chain_verified": True,
            "candidate_sha256": digest(candidate), "topology_matches_expected": bool(topology_matches),
            "topology": topology, "candidate_to_reference": forward, "reference_to_candidate": reverse,
            "within_0_1_under_exact_query_assumption": bool(forward["within_budget_under_exact_distance_assumption"] and
                                                         reverse["within_budget_under_exact_distance_assumption"]),
            "certified_continuous_geometry": False})
        parent.update(sha256=row["published_state"]["sha256"], version=control["published_version"])
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(row["route"], row["event"], topology_matches, forward["upper_mm"], reverse["upper_mm"], flush=True)
    report.update(status="completed", planned_prefixes=len(execution["rows"]), all_parent_chains_verified=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
