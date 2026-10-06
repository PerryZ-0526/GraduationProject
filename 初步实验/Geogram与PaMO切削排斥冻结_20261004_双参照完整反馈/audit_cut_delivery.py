"""只读核对第二版的实际切削、父反馈哈希、整面排斥和远端执行源码。"""

import getpass
import json
from pathlib import Path

import numpy as np
import trimesh

from audit_followup_candidate import sha256
from cut_exclusion import supporting_planes, certify_face_support, certify_outside_anchor
from probe_removed_material import tool_clearance
from run_constrained_batch import RemoteQuality, HERE
from run_geometry_study import now, save


def load(path):
    return trimesh.load(path, force="mesh", process=False)


def certify(mesh, tools, details):
    # 复核原来冻结的支撑编号，不通过重新挑选支撑掩盖已保存结果的违反。
    attempt = details["attempts"][details["selected_level"]]["exclusion"]
    planes = [supporting_planes(tool) for tool in tools]
    normals = np.concatenate([item[0] for item in planes])
    offsets = np.concatenate([item[1] for item in planes])
    faces = [certify_face_support(mesh, normals, offsets, selection)
             for selection in attempt["frozen_face_support_ids"]]
    anchors = [certify_outside_anchor(mesh, tool, normal, offset)
               for tool, (normal, offset) in zip(tools, planes)]
    return {"face_certificates": faces, "anchor_certificates": anchors,
            "passed": all(x["passed"] for x in faces + anchors)}


def probes(mesh, tools):
    points = np.concatenate((mesh.vertices, mesh.triangles_center))
    values = np.min(np.array([tool_clearance(points, tool) for tool in tools]), axis=0)
    return {"inside_probe_count": int(np.sum(values < -1e-7)),
            "max_inward_plane_depth_mm": max(0., -float(np.min(values))),
            "scope": "顶点与面心有限见证，不是材料交叠体积"}


def main():
    results = HERE / "实验结果"
    static = results / "20261004_自适应切削排斥28几何体独立静态验证"
    feedback = results / "20261004_自适应切削排斥两路线父反馈开发"
    assets = HERE.parent / "可复用磨削测试集/独立切削约束输入_v2"
    prepared = results / "20261004_自适应切削排斥父反馈开发输入"
    output = results / "20261004_自适应切削排斥交付语义与溯源审计"
    output.mkdir(exist_ok=False)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，只读既有冻结结果",
              "文档概述": "重新认证保存表面、分开无切削对照、核对反馈链及实际远端源码",
              "索引目录": ["static", "feedback", "remote_provenance"],
              "static": [], "feedback": [], "remote_provenance": [], "status": "running"}
    record = output / "01-交付语义与溯源审计.json"
    (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    manifest = json.loads((assets / "01-完整范围冻结清单.json").read_text("utf8"))
    routes = {route["id"]: route for route in manifest["routes"]}
    study = json.loads((static / "02-独立静态执行与审计.json").read_text("utf8"))
    for row in study["rows"]:
        route = routes[row["route"]]
        initial = load(assets / "inputs" / route["initial_mesh"])
        source = load(static / row["route"] / "source.obj")
        entry = {"route": row["route"], "reference_signed_removed_volume_mm3": float(initial.volume - source.volume),
                 "methods": {name: {"accepted": method["accepted"], "inside_probe_count": method["inside_probe_count"],
                              "probe_max_mm": method["geometry"]["probe_max_mm"],
                              "small_angle_fraction": method["quality"]["angle_below_10_deg"]["fraction"],
                              "cpu_correction_ms": method["details"].get("correction_cpu_ms")}
                             for name, method in row["methods"].items()}}
        candidate = row["methods"]["exclusion"]
        if candidate["accepted"]:
            tool = load(assets / "inputs" / route["prefix_tools"][0]["mesh"])
            mesh_path = static / row["route"] / "exclusion.obj"
            entry.update(candidate_sha256=sha256(mesh_path),
                         selected_level=candidate["details"]["selected_level"],
                         exact_reaudit=certify(load(mesh_path), [tool], candidate["details"]))
        report["static"].append(entry)
        save(record, report)
    manifest = json.loads((prepared / "01-完整范围冻结清单.json").read_text("utf8"))
    routes = {route["id"]: route for route in manifest["routes"]}
    study = json.loads((feedback / "01-反馈执行与独立审计.json").read_text("utf8"))
    parents = {(route["id"], branch): route["initial_mesh_sha256"] for route in routes.values()
               for branch in ("full", "candidate")}
    for row in study["rows"]:
        if row.get("branch") not in ("full", "candidate"):
            continue
        key = row["route"], row["branch"]
        route = routes[row["route"]]
        current = route["cutting_prefix_ids"].index(row["event"])
        retained = set(route["cutting_prefix_ids"][:current + 1])
        paths = [prepared / "inputs" / entry["mesh"] for entry in route["prefix_tools"] if entry["event_id"] in retained]
        tools = [load(path) for path in paths]
        suffix = "boolean" if row["branch"] == "candidate" else "full"
        folder = feedback / f"{row['route']}_{row['event']}_{row['branch']}_{suffix}"
        mesh_path = folder / "candidate.obj"
        entry = {"route": row["route"], "event": row["event"], "branch": row["branch"], "status": row["status"],
                 "parent_chain_matches": row["parent_sha256"] == parents[key],
                 "saved_output_hash_matches": row["output_sha256"] == sha256(mesh_path),
                 "cumulative_tool_count": len(tools), "probes": probes(load(mesh_path), tools)}
        if row["branch"] == "candidate":
            details = row["attempts"][0]["cut_exclusion"]
            entry.update(exact_reaudit=certify(load(mesh_path), tools, details),
                         cumulative_tool_hashes_match=details["cumulative_tool_sha256"] == [sha256(path) for path in paths])
        report["feedback"].append(entry)
        parents[key] = row["output_sha256"]
        save(record, report)
    config = dict(line.split("=", 1) for line in (HERE.parents[1] / ".env").read_text("utf8").splitlines()
                  if line and not line.startswith("#"))
    original = getpass.getpass
    try:
        getpass.getpass = lambda _: config["CUDA_SSH_PASSWORD"]
        engine = RemoteQuality(output, int(config["CUDA_SSH_PORT"]))
    finally:
        getpass.getpass = original
        del config
    try:
        for root, filename in [(static, "02-独立静态执行与审计.json"), (feedback, "01-反馈执行与独立审计.json")]:
            previous = json.loads((root / filename).read_text("utf8"))
            # 只切换远端目录身份，不运行初始化、编译或CUDA工作进程。
            import hashlib
            identity = hashlib.sha256(str(root.resolve()).encode("utf8")).hexdigest()[:12]
            remote = engine.remote.rsplit("/", 1)[0] + "/constrained_" + root.name + "_" + identity
            folder = output / root.name
            folder.mkdir()
            for name, expected in previous["environment"]["code_sha256"].items():
                destination = folder / name
                engine.sftp.get(remote + "/" + name, str(destination))
                report["remote_provenance"].append({"batch": root.name, "file": name,
                    "expected": expected, "actual": sha256(destination), "matches": expected == sha256(destination)})
    finally:
        engine.close()
    report.update(status="completed_with_recorded_outcomes", finished_beijing=now())
    save(record, report)
    print("static", len(report["static"]), "feedback", len(report["feedback"]),
          "remote_code_match", all(x["matches"] for x in report["remote_provenance"]), flush=True)


if __name__ == "__main__":
    main()
